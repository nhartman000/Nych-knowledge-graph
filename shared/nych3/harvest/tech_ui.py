"""Ingest the tech.ui canonical UI-action harvest (nych-ui-actions) into the TOTE store.

- 1 canonical-action loop per canonical UI action (TL-UI-<ACTION>): 🙌 operate + 👀² verify, g8son exit gate G-UI-<ACTION>.
- Instance loops (TL-UI-I-<hash>) = extracted actions deduped by (canonical, verb, object); repeat_count = occurrences;
  each occurrence is a SourceRef (URL, retrieval date, section, step #, quote; no article text).
  Quote definition: at most 25 whitespace tokens of source text; when truncated, a leading and/or trailing "…"
  marker is added, so a stored quote can be up to 27 whitespace tokens (25 source + 2 markers).
  Locator quality: section headings and step numbers are not always present. Each SourceRef carries a
  flag "locator_quality:<section+step|section_only|step_only|url_only>"; ingest() returns the counts
  (in the shipped export 1,257 records are url_only, i.e. neither section nor step).
- Instance groups span platforms/modifiers: an instance loop's perspective_cell is the FIRST occurrence's platform;
  techniques[0].platforms lists all of them. ingest() reports groups with >1 platform or conflicting modifiers.
  INSTANCE_OF links instance -> canonical loop.
- EVERYTHING is status=candidate, epistemic_status=PROVISIONAL, provenance.review_status=provisional_unreviewed
  (spot check 21/40 correct). Nothing is promoted; canonical status still requires authority metadata (a name; not authenticated).
Usage: python -m nych3.harvest.tech_ui [--db PATH] [--export DIR] [--replace]"""
from __future__ import annotations
import argparse, gzip, hashlib, json, os, re, sys
import kuzu
from pathlib import Path
from ..config import SHARED
from ..store.tote_db import ToteDB, DEFAULT_DB

DOMAIN = "tech.ui"
EXPORT = SHARED / "data" / "tech_ui"
LOOK = {"VERIFY_STATE", "REVIEW_CONTENT", "WAIT"}
REVIEW = {"review_status": "provisional_unreviewed", "spot_check": "21/40 correct, 6 partial, 13 wrong (agent-graded 2026-11-02, pending human review)"}
SRC = "nych-ui-actions tech help-center harvest (Microsoft/Google/Claude/Apple/Samsung/Microsoft Copilot support pages)"
INSTANCE_DDL = "CREATE REL TABLE INSTANCE_OF(FROM TOTELoop TO TOTELoop, method STRING, provenance STRING)"


def norm_obj(s: str) -> str:
    s = re.sub(r"^(the|a|an|your|any|all|this|that)\s+", "", (s or "").lower().strip())
    s = re.sub(r"[^\w\s>&+/-]", "", s)
    return re.sub(r"\s+", " ", s).strip()[:60] or "*"


def locator_quality(a: dict) -> str:
    s, t = bool((a.get("section") or "").strip()), bool(a.get("step_no"))
    return "section+step" if s and t else "section_only" if s else "step_only" if t else "url_only"


MODIFIERS = ("direction", "count", "duration", "param")


def context_conflicts(groups: dict) -> dict:
    """Count instance groups (canonical, verb, object) whose occurrences disagree on platform or on a modifier."""
    multi_plat = sum(1 for occ in groups.values() if len({a["platform"] for a in occ}) > 1)
    mod = {k: sum(1 for occ in groups.values() if len({a[k] for a in occ if a.get(k)}) > 1) for k in MODIFIERS}
    any_mod = sum(1 for occ in groups.values() if any(len({a[k] for a in occ if a.get(k)}) > 1 for k in MODIFIERS))
    either = sum(1 for occ in groups.values() if len({a["platform"] for a in occ}) > 1
                 or any(len({a[k] for a in occ if a.get(k)}) > 1 for k in MODIFIERS))
    return {"groups": len(groups), "multi_platform": multi_plat, "conflicting_modifier_any": any_mod,
            "conflicting_modifier_by_field": mod, "platform_or_modifier_conflict": either}


def ensure_schema(db: ToteDB):
    """Migrate an older store in place (nych-3-pro stores predate these): SourceRef.sentence_text/flags, DOMAIN_LINK, INSTANCE_OF."""
    tables = {r["name"] for r in db.q("CALL show_tables() RETURN name")}
    cols = {r["name"] for r in db.q("CALL table_info('SourceRef') RETURN name")}
    if "sentence_text" not in cols:
        db.c.execute("ALTER TABLE SourceRef ADD sentence_text STRING DEFAULT ''")
    if "flags" not in cols:
        db.c.execute("ALTER TABLE SourceRef ADD flags STRING[]")
    if "DOMAIN_LINK" not in tables:
        db.c.execute("CREATE REL TABLE DOMAIN_LINK(FROM Domain TO Domain, kind STRING, shared_loops INT64, evidence STRING, provenance STRING)")
    if "INSTANCE_OF" not in tables:
        db.c.execute(INSTANCE_DDL)


def clear(db: ToteDB):
    while db.q("MATCH (s:SourceRef) WHERE s.ref_id STARTS WITH 'UI:' RETURN count(s) AS n")[0]["n"]:   # batched: bounded memory
        db.c.execute("MATCH (s:SourceRef) WHERE s.ref_id STARTS WITH 'UI:' WITH s LIMIT 5000 DETACH DELETE s")
    while db.q("MATCH (l:TOTELoop) WHERE l.domain=$d RETURN count(l) AS n", {"d": DOMAIN})[0]["n"]:
        db.c.execute("MATCH (l:TOTELoop) WHERE l.domain=$d WITH l LIMIT 5000 DETACH DELETE l", {"d": DOMAIN})
    db.c.execute("MATCH (g:Gate) WHERE g.file_id='nych3.tech_ui.exit' DETACH DELETE g")


def modality(verb: str, canon: str) -> tuple[str, list]:
    if canon in LOOK:
        return f"{verb},👀² ; verify,👀²", [("OP-VE", f"{verb}|operate"), ("OP-VE", "verify|test")]
    if canon == "KEEP_REMEMBER":
        return f"{verb},🙌 ; remember,💭 ; verify,👀²", [("OP-KE", f"{verb}|operate"), ("OP-MEM", "remember|explicit_recall_cue"), ("OP-VE", "verify|test")]
    return f"{verb},🙌 ; verify,👀²", [("OP-KE", f"{verb}|operate"), ("OP-VE", "verify|test")]


BUFFER_POOL = int(os.environ.get("NYCH3_KUZU_BUFFER_POOL", str(2 << 30)))   # default 2 GiB; Kuzu's default (80% RAM) OOM-killed a 15.6 GB box


def open_limited(db_path) -> ToteDB:
    """Open the store with a bounded Kuzu buffer pool (creating + seeding it first if it does not exist)."""
    p = Path(db_path)
    if not p.exists():
        ToteDB(p).close()
    d = kuzu.Database(str(p), buffer_pool_size=BUFFER_POOL); db = ToteDB.__new__(ToteDB)
    db.path, db.db, db.c = p, d, kuzu.Connection(d)
    return db


def ingest(db_path=DEFAULT_DB, export: Path = EXPORT, replace=False):
    export = Path(export)
    canon = json.loads((export / "canonical_actions.json").read_text(encoding="utf-8"))["actions"]
    db = open_limited(db_path)
    ensure_schema(db)
    if db.q("MATCH (l:TOTELoop) WHERE l.domain=$d RETURN count(l) AS n", {"d": DOMAIN})[0]["n"]:
        if not replace:
            raise SystemExit("tech.ui already ingested; rerun with --replace")
        clear(db)
    st = {"canonical_loops": 0, "instance_loops": 0, "source_refs": 0, "instance_of": 0, "modality_links": 0, "gates": 0,
          "locator_quality": {}, "context_conflicts": {}}
    gate_of = {}
    for c in canon:
        name = c["canonical"]; lid = f"TL-UI-{name}"; gid = f"G-UI-{name}"; t = c["tote_template"]
        db.add_gate({"gate_id": gid, "file_id": "nych3.tech_ui.exit", "order": 1, "type": "condition",
                     "conditions": [t["exit_gate"]["conditions"]], "outcomes": {"PASS": "exit", "FAIL": "repeat (max 3)", "INTERMEDIATE": "escalate"}})
        st["gates"] += 1; gate_of[name] = (gid, t["exit_gate"]["conditions"])
        verb = name.lower(); mc, links = modality(verb, name)
        db.add_loop({"loop_id": lid, "name": name, "domain": DOMAIN, "objective": f"canonical UI action {name}",
                     "initial_test": t["test_entry"], "exit_predicate": gid, "max_iterations": 3, "epistemic_status": "PROVISIONAL",
                     "modality_cell": mc, "actor_cell": "user,", "action_cell": f"{verb},", "object_cell": "<target>,", "perspective_cell": "screen/device,",
                     "exit_gate_id": gid, "action_lemma": verb, "object_lemma": "*",
                     "termination_triggers": [{"trigger": t["exit_gate"]["conditions"], "provenance": "template"}],
                     "techniques": [{"kind": "canonical_action", "frequency": c["count"], "share_pct": c["share_pct"], "platform_split": c["platform_split"],
                                     "top_surface_verbs": c["top_surface_verbs"], "top_object_types": c["top_object_types"], "examples": c["examples"]}],
                     "version": "1", "repeat_count": c["count"], "structure_key": json.dumps(["tech.ui", name]),
                     "in_domain": [[DOMAIN, "primary", "canonical UI action (provisional)"]]},
                    status="candidate", provenance={"source": SRC, "method": "UI-CANON-1", "authority": None, **REVIEW,
                                                    "mapping": "nych-ui-actions/config/mapping.json"})
        for op, w in links:
            db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(o:Operator {operator_id:$o}) CREATE (l)-[:USES_MODALITY {word:$w}]->(o)", {"l": lid, "o": op, "w": w})
            st["modality_links"] += 1
        st["canonical_loops"] += 1
    # instances, grouped
    groups: dict = {}
    with gzip.open(export / "ui_actions.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            a = json.loads(line)
            if a["canonical"] not in gate_of:
                continue
            key = (a["canonical"], a["verb"], norm_obj(a["object"]))
            groups.setdefault(key, []).append(a)
    st["context_conflicts"] = context_conflicts(groups)
    db.c.execute("BEGIN TRANSACTION"); n = 0
    for (cn, verb, obj), occ in groups.items():
        sk = json.dumps(["tech.ui", cn, verb, obj], ensure_ascii=False)
        lid = "TL-UI-I-" + hashlib.sha1(sk.encode()).hexdigest()[:12]; gid, cond = gate_of[cn]; a0 = occ[0]
        cues = sorted({c for a in occ for c in (a["condition_cues"] or "").split(";") if c})
        mods = {k: sorted({a[k] for a in occ if a[k]})[:5] for k in ("direction", "count", "duration", "param")}
        mc, links = modality(verb, cn)
        db.add_loop({"loop_id": lid, "name": f"{verb} {obj}".strip(), "domain": DOMAIN, "objective": f"instance of {cn}",
                     "initial_test": f"👀² verify {a0['obj_type']} '{obj}' visible", "exit_predicate": gid, "max_iterations": 3, "epistemic_status": "PROVISIONAL",
                     "modality_cell": mc, "actor_cell": "user,", "action_cell": f"{verb},", "object_cell": f"{obj},", "perspective_cell": f"{a0['platform']},",
                     "exit_gate_id": gid, "action_lemma": verb, "object_lemma": obj,
                     "termination_triggers": [{"trigger": cond, "provenance": "canonical_template"}] + [{"trigger": c, "provenance": "explicit_cue"} for c in cues[:5]],
                     "techniques": [{"kind": "canonical_action", "canonical": cn, "canonical_loop": f"TL-UI-{cn}", "obj_type": a0["obj_type"],
                                     "platforms": sorted({a["platform"] for a in occ}), "modifiers": {k: v for k, v in mods.items() if v}}],
                     "version": "1", "repeat_count": len(occ), "structure_key": sk, "in_domain": [[DOMAIN, "primary", "harvested"]]},
                    status="candidate", provenance={"source": SRC, "method": "UI-HARVEST-1", "authority": None, **REVIEW,
                                                    "first_ref": {"url": a0["url"], "retrieved": a0["retrieved"]}})
        db.c.execute("MATCH (i:TOTELoop {loop_id:$i}),(c:TOTELoop {loop_id:$c}) CREATE (i)-[:INSTANCE_OF {method:'mapping.json',provenance:'UI-HARVEST-1 provisional'}]->(c)",
                     {"i": lid, "c": f"TL-UI-{cn}"})
        for op, w in links:
            db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(o:Operator {operator_id:$o}) CREATE (l)-[:USES_MODALITY {word:$w}]->(o)", {"l": lid, "o": op, "w": w})
        for a in occ:
            rid = "UI:" + a["id"]; lq = locator_quality(a)
            st["locator_quality"][lq] = st["locator_quality"].get(lq, 0) + 1
            db.c.execute("CREATE (:SourceRef {ref_id:$r,isbn:'',isbn_status:'web_source',page:$p,page_kind:'web_section',page_method:'html_heading+list_index',fallback_gutenberg_id:'',sent_key:$u,sentence_text:$t,flags:$f})",
                         dict(r=rid, p=f"{a['section'][:100]} | step {a['step_no'] or '-'}", u=a["url"], t=a["quote"],
                              f=["web_source", f"retrieved:{a['retrieved']}", f"site:{a['site']}", f"kind:{a['kind']}", f"locator_quality:{lq}", "provisional_unreviewed"]))
            db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(s:SourceRef {ref_id:$r}) CREATE (l)-[:SOURCED_FROM]->(s)", {"l": lid, "r": rid})
            st["source_refs"] += 1
        st["instance_loops"] += 1; st["instance_of"] += 1; st["modality_links"] += len(links); n += 1
        if n % 500 == 0:
            db.c.execute("COMMIT"); db.c.close(); db.c = kuzu.Connection(db.db)   # fresh connection per batch bounds memory
            db.c.execute("BEGIN TRANSACTION"); print("…", n, file=sys.stderr, flush=True)
    db.c.execute("COMMIT")
    st["domain_links"] = db.refresh_domain_links()
    st["store_loops"] = db.count(); st["store_by_status"] = {s: db.count(s) for s in ("candidate", "canonical")}
    db.close()
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nych3-tech-ui")
    ap.add_argument("--db", default=str(DEFAULT_DB)); ap.add_argument("--export", default=str(EXPORT)); ap.add_argument("--replace", action="store_true")
    a = ap.parse_args(argv)
    print(json.dumps(ingest(a.db, a.export, a.replace), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
