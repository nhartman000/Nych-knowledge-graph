"""Ingest harvest job B (modern everyday how-to pages; tools/howto_harvest) into the TOTE store.

Domains: howto.{tech_phone, ai_tools, social_creator, rental, marketplace, shopping_returns, digital_life}.
- Instance loops TL-HT-<hash>, deduped by (domain, verb, normalized object); repeat_count = occurrences; each occurrence is a
  SourceRef "HT:<id>" (URL, retrieval date, section | step, quote <= 25 source tokens + '…' markers; no article text).
- Operate/verify/exit: modality cell "<verb>,<m> ; verify,👀²" where m is 🙌 (operate), 👀² (look), 👂👂 (listen),
  🧠🗯 (default for internal senses: decide/consider/plan/make sure ...) or 💭 ONLY for explicit recall cues
  (remember, recall, as before, as last time).
- Exit gate: if the action maps to a tech.ui canonical action already in the store, the instance uses that canonical gate
  G-UI-<ACTION> and gets INSTANCE_OF -> TL-UI-<ACTION> (no IN_DOMAIN tech.ui edge is added, so no new DOMAIN_LINK is built); otherwise a per-modality gate G-HT-<M>.
- Approximate amounts ("two or three", "2-3 days", "a few") are stored as ranges in techniques[0].amount_ranges.
- Tags: domain via IN_DOMAIN; platform in perspective_cell (first occurrence), techniques[0].platforms and SourceRef flags.
- EVERYTHING status=candidate, epistemic_status=PROVISIONAL, review_status=provisional_unreviewed. Nothing is promoted.
- Incremental + idempotent: existing loops only get the SourceRefs they do not have yet (batch ingests during a long harvest).
- Memory: bounded buffer pool (NYCH3_KUZU_BUFFER_POOL, default 2 GiB) and a fresh connection every 500 loops.
  Kuzu allows one writer: run under `flock /workspace/kg.ingest.lock`.
Usage: python -m nych3.harvest.howto [--db PATH] [--export DIR]"""
from __future__ import annotations
import argparse, gzip, hashlib, json, sys
import kuzu
from pathlib import Path
from ..config import SHARED
from ..store.tote_db import DEFAULT_DB
from .tech_ui import open_limited, ensure_schema, norm_obj, locator_quality

EXPORT = SHARED / "data" / "howto"
SRC = "harvest job B: everyday how-to pages (FTC, CFPB, usa.gov, CISA, platform help/guide pages; see tools/howto_harvest/sources.py)"
REVIEW = {"review_status": "provisional_unreviewed", "spot_check": "see REVIEW/howto_spotcheck_20.csv (agent-graded, pending human review)"}
OPS = {"🙌": "OP-KE", "👀²": "OP-VE", "👂👂": "OP-AE", "🧠🗯": "OP-IMG", "💭": "OP-MEM"}
GATES = {"🙌": "step_effect_observed(👀² verify)", "👀²": "observation_recorded", "👂👂": "sound_or_message_heard",
         "🧠🗯": "decision_or_judgement_made(self-report; internal)", "💭": "recalled_item_available"}
GNAME = {"🙌": "OPERATE", "👀²": "LOOK", "👂👂": "LISTEN", "🧠🗯": "INTERNAL", "💭": "RECALL"}


def group_key(a):
    return (a["domain"], a["verb"], norm_obj(a["object"]))


def ingest(db_path=DEFAULT_DB, export: Path = EXPORT, batch=500):
    export = Path(export)
    db = open_limited(db_path); ensure_schema(db)
    st = {"new_loops": 0, "existing_loops_extended": 0, "new_source_refs": 0, "instance_of_tech_ui": 0, "gates_created": 0,
          "new_loops_by_domain": {}, "locator_quality": {}}
    for m, cond in GATES.items():
        gid = f"G-HT-{GNAME[m]}"
        if not db.q("MATCH (g:Gate {gate_id:$g}) RETURN g.gate_id AS g", {"g": gid}):
            db.add_gate({"gate_id": gid, "file_id": "nych3.howto.exit", "order": 1, "type": "condition", "conditions": [cond],
                         "outcomes": {"PASS": "exit", "FAIL": "repeat (max 3)", "INTERMEDIATE": "escalate"}}); st["gates_created"] += 1
    ui = {r["l"][6:] for r in db.q("MATCH (l:TOTELoop) WHERE l.loop_id STARTS WITH 'TL-UI-' AND NOT l.loop_id STARTS WITH 'TL-UI-I-' RETURN l.loop_id AS l")}
    ui_gate = {r["g"][5:]: r["c"] for r in db.q("MATCH (g:Gate) WHERE g.file_id='nych3.tech_ui.exit' RETURN g.gate_id AS g, g.conditions AS c")}
    have_refs = {r["r"] for r in db.q("MATCH (s:SourceRef) WHERE s.ref_id STARTS WITH 'HT:' RETURN s.ref_id AS r")}
    have_loops = {r["l"] for r in db.q("MATCH (l:TOTELoop) WHERE l.loop_id STARTS WITH 'TL-HT-' RETURN l.loop_id AS l")}
    groups: dict = {}
    with gzip.open(export / "howto_actions.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            a = json.loads(line); groups.setdefault(group_key(a), []).append(a)
    db.c.execute("BEGIN TRANSACTION"); n = 0
    for (dom, verb, obj), occ in groups.items():
        new = [a for a in occ if "HT:" + a["id"] not in have_refs]
        if not new:
            continue
        sk = json.dumps(["howto", dom, verb, obj], ensure_ascii=False)
        lid = "TL-HT-" + hashlib.sha1(sk.encode()).hexdigest()[:12]; a0 = occ[0]
        md = a0["modality"]; cn = a0["canonical"] if a0["canonical"] in ui and a0["canonical"] in ui_gate else ""
        if lid not in have_loops:
            gid = f"G-UI-{cn}" if cn else f"G-HT-{GNAME[md]}"
            cond = ui_gate.get(cn) if cn else GATES[md]
            mc = f"{verb},👀² ; verify,👀²" if md == "👀²" else f"{verb},{md} ; verify,👀²"
            plats = sorted({p for a in occ for p in [a["platform"]] + [x for x in a["platform_hints"].split("|") if x]})
            cues = sorted({c for a in occ for c in (a["condition_cues"] or "").split(";") if c})
            rngs = [r for a in occ for r in a["amount_ranges"]][:5]
            db.add_loop({"loop_id": lid, "name": f"{verb} {obj}".strip()[:120], "domain": dom, "objective": f"{dom} step: {verb} {obj}"[:200],
                         "initial_test": f"👀² verify precondition for '{verb} {obj}'"[:200], "exit_predicate": gid, "max_iterations": 3,
                         "epistemic_status": "PROVISIONAL", "modality_cell": mc, "actor_cell": "user,", "action_cell": f"{verb},",
                         "object_cell": f"{obj},", "perspective_cell": f"{a0['platform']},", "exit_gate_id": gid, "action_lemma": verb, "object_lemma": obj,
                         "termination_triggers": [{"trigger": cond, "provenance": "canonical_template" if cn else "modality_template"}]
                                                 + [{"trigger": c, "provenance": "explicit_cue"} for c in cues[:5]],
                         "techniques": [{"kind": "howto_step", "canonical": cn, "canonical_loop": f"TL-UI-{cn}" if cn else "", "obj_type": a0["obj_type"],
                                         "platforms": plats, "modality_rule": a0["modality_rule"], "amount_ranges": rngs}],
                         "version": "1", "repeat_count": len(occ), "structure_key": sk,
                         "in_domain": [[dom, "primary", "harvested"]]},
                        status="candidate", provenance={"source": SRC, "method": "HOWTO-HARVEST-1", "authority": None, **REVIEW,
                                                        "first_ref": {"url": a0["url"], "retrieved": a0["retrieved"]}})
            op = OPS[md]
            db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(o:Operator {operator_id:$o}) CREATE (l)-[:USES_MODALITY {word:$w}]->(o)", {"l": lid, "o": op, "w": f"{verb}|{a0['modality_rule']}"})
            if md != "👀²":
                db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(o:Operator {operator_id:'OP-VE'}) CREATE (l)-[:USES_MODALITY {word:'verify|test'}]->(o)", {"l": lid})
            if cn:
                db.c.execute("MATCH (i:TOTELoop {loop_id:$i}),(c:TOTELoop {loop_id:$c}) CREATE (i)-[:INSTANCE_OF {method:'tech_ui mapping.json',provenance:'HOWTO-HARVEST-1 provisional'}]->(c)",
                             {"i": lid, "c": f"TL-UI-{cn}"}); st["instance_of_tech_ui"] += 1
            have_loops.add(lid); st["new_loops"] += 1; st["new_loops_by_domain"][dom] = st["new_loops_by_domain"].get(dom, 0) + 1
        else:
            db.c.execute("MATCH (l:TOTELoop {loop_id:$l}) SET l.repeat_count=$n", {"l": lid, "n": len(occ)}); st["existing_loops_extended"] += 1
        for a in new:
            rid = "HT:" + a["id"]; lq = locator_quality(a); st["locator_quality"][lq] = st["locator_quality"].get(lq, 0) + 1
            db.c.execute("CREATE (:SourceRef {ref_id:$r,isbn:'',isbn_status:'web_source',page:$p,page_kind:'web_section',page_method:'html_heading+list_index',fallback_gutenberg_id:'',sent_key:$u,sentence_text:$t,flags:$f})",
                         dict(r=rid, p=f"{a['section'][:100]} | step {a['step_no'] or '-'}", u=a["url"], t=a["quote"],
                              f=["web_source", f"retrieved:{a['retrieved']}", f"site:{a['site']}", f"domain:{a['domain']}", f"platform:{a['platform']}",
                                 f"kind:{a['kind']}", f"locator_quality:{lq}", "provisional_unreviewed"]))
            db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(s:SourceRef {ref_id:$r}) CREATE (l)-[:SOURCED_FROM]->(s)", {"l": lid, "r": rid})
            have_refs.add(rid); st["new_source_refs"] += 1
        n += 1
        if n % batch == 0:
            db.c.execute("COMMIT"); db.c.close(); db.c = kuzu.Connection(db.db)   # fresh connection per 500 loops bounds memory
            db.c.execute("BEGIN TRANSACTION"); print("…", n, file=sys.stderr, flush=True)
    db.c.execute("COMMIT")
    st["domain_links"] = db.refresh_domain_links()
    st["store_loops"] = db.count()
    db.close()
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nych3-howto")
    ap.add_argument("--db", default=str(DEFAULT_DB)); ap.add_argument("--export", default=str(EXPORT))
    a = ap.parse_args(argv)
    print(json.dumps(ingest(a.db, a.export), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
