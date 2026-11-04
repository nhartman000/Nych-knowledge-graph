"""Stage functions 01-09. Each takes the cumulative state dict from the previous
stage's output and returns it with its own section added. Deterministic; no LLM."""
from __future__ import annotations
import hashlib, json, subprocess
from .config import REPO, registry, schema_versions
from .nlp import segmenter, analysis
from .nlp.parser_adapter import get_parser
from .provenance import prov, likelihood
from .skeleton import consonant_skeleton, collisions
from .store.tote_db import ToteDB, DEFAULT_DB

DIRECTIVE = ("This pipeline ENCODES the narrative. Questions or dialogue inside the story are invariant story "
             "content: flag them, keep them verbatim, never answer them.")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _commit():
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


# 01 ------------------------------------------------------------------------
def s01_boot(state):
    prompt, story = state["input"]["prompt"], state["input"]["story"]
    bonit = (REPO / "_config" / "nych3.bonit").read_text(encoding="utf-8")
    parser = get_parser(state["input"].get("parser", "rule"))
    state["manifest"] = {
        "nych3_version": schema_versions()["nych3_version"], "repo_commit": _commit(), "schema_versions": schema_versions(),
        "bonit_sha256": sha(bonit), "directive": DIRECTIVE, "parser": {"name": parser.name, "version": parser.version},
        "source_sha256": {"prompt": sha(prompt), "story": sha(story)},
        "invariant_story_content_flags": {
            "contains_question_mark": "?" in story,
            "contains_dialogue_quotes": any(q in story for q in ('"', "“", "”")),
            "policy": "flag_and_preserve_never_answer"},
        "llm_calls_in_stages_01_09": 0,
    }
    return state


# 02 ------------------------------------------------------------------------
def s02_structure(state):
    st = segmenter.structure(state["input"]["story"], state["input"].get("expected_pages"))
    inv = []
    for p in st["pages"]:
        for s in p["sentences"]:
            if s["is_question"]:
                inv.append({"kind": "question", "sent_id": s["sent_id"], "text": s["text"], "answer": None,
                            "policy": "invariant story content; never answered"})
            for d in s["dialogue_spans"]:
                inv.append({"kind": "dialogue", "sent_id": s["sent_id"], "text": d["text"], "char_start": d["char_start"],
                            "char_end": d["char_end"], "policy": "invariant story content; never answered"})
    st["invariant_content"] = inv
    st["run_counts"] = {"expected_pages": st["expected_pages"], "completed_pages": st["completed_pages"],
                        "complete": st["expected_pages"] == st["completed_pages"]}
    state["structure"] = st
    return state


# 03 ------------------------------------------------------------------------
def s03_scope(state):
    parser = get_parser(state["input"].get("parser", "rule"))
    tagged = {s["sent_id"]: parser.tag(s["tokens"]) for s in analysis.iter_sentences(state["structure"])}
    state["tagged"] = tagged
    state["scope"] = analysis.scope_attribution(state["structure"], tagged, state["input"]["prompt"])
    return state


# 04 ------------------------------------------------------------------------
def s04_temporal(state):
    state["temporal"] = analysis.temporal(state["structure"], state["tagged"])
    return state


# 05 ------------------------------------------------------------------------
def s05_semantics(state):
    state["semantics"] = analysis.semantics(state["structure"], state["tagged"], state["scope"], state["temporal"])
    return state


# 06 ------------------------------------------------------------------------
def _ctx_rule(lemma, obj):
    for r in registry("context")["rules"]:
        if r["lemma"] == lemma and (r["object"] == obj or r["object"] == "*"):
            return r
    return None


def s06_context(state):
    per_event = []
    for p in state["semantics"]["propositions"]:
        if p["complement_event"]:
            continue
        obj = (p["object"] or {}).get("head_lemma")
        r = _ctx_rule(p["lemma"], obj)
        per_event.append({"event_id": p["event_id"],
                          "domain": r["domain"] if r else "UNRESOLVED", "function": r["function"] if r else "UNRESOLVED",
                          "technique": (r["technique"] or "UNRESOLVED") if r else "UNRESOLVED",
                          **prov(r["rule_id"] if r else "CTX-NO-REGISTRY-SUPPORT", "explicit" if r else "inferred", status="inferred")})
    doms = sorted({e["domain"] for e in per_event if e["domain"] != "UNRESOLVED"})
    state["context"] = {"per_event": per_event, "domains_supported": doms,
                        "domain": doms[0] if len(doms) == 1 else ("UNRESOLVED" if not doms else "MULTIPLE"),
                        "unresolved_events": [e["event_id"] for e in per_event if e["domain"] == "UNRESOLVED"],
                        "user_competency": state["input"].get("user_competency") or "UNRESOLVED",
                        "reader_level": state["input"].get("reader_level"),
                        "note": "user/domain competency is kept separate from estimated reader level"}
    return state


# 07 ------------------------------------------------------------------------
def _entity_name(state, eid):
    return next((e["name"] for e in state["scope"]["entities"] if e["entity_id"] == eid), None)


def _cell(word, protected=False):
    return f"{word},[protected]" if protected else f"{word},"


def _chain(props, leaf):
    by = {p["event_id"]: p for p in props}
    out, cur = [leaf], leaf
    while cur["parent_event"]:
        cur = by[cur["parent_event"]]; out.insert(0, cur)
    return out


def s07_tote_bind(state):
    db = ToteDB.open(state["input"].get("db_path") or DEFAULT_DB)
    modreg = registry("modality")
    events = {e["event_id"]: e for e in state["temporal"]["events"]}
    props = state["semantics"]["propositions"]
    doc_sha = state["manifest"]["source_sha256"]["story"]
    instances, harvest, no_match = [], [], []

    def actor_info(p):
        a = p["actor"] or {}
        eid = a.get("entity_id")
        name = _entity_name(state, eid) if eid else None
        return {"entity_id": eid, "text": a.get("text"), "resolved_name": name,
                "binding": p["actor_binding"], "provenance": "explicit" if p["actor_binding"] == "grammatical_subject" and a.get("text") == name else "inferred"}

    def loc_cell(p):
        parts = []
        for l in p["locations"]:
            parts.append(_cell(l["head"]))
            for rel in l.get("located_by", []):
                g = rel["ground_arg"]
                poss = g.get("possessor")
                pn = f"({poss['text']}→{_entity_name(state, poss['entity_id'])})" if poss and poss.get("entity_id") else ""
                parts.append(f"{rel['relation']} {g['head']}{pn},")
        return " ; ".join(parts) if parts else "UNRESOLVED,"

    for p in props:
        if p["complement_event"]:
            continue
        ev = events[p["event_id"]]
        chain = _chain(props, p)
        ops = [c for c in (analysis.operator_cell(x, events[x["event_id"]], modreg) for x in chain) if c]
        act = actor_info(p)
        obj = p["object"]
        cdom = (state.get("context") or {}).get("domain")
        res = db.lookup(p["lemma"], obj["head_lemma"] if obj else None,
                        domain=cdom if cdom not in (None, "UNRESOLVED", "MULTIPLE") else None)
        row = {"modality": " ; ".join(ops) or "UNRESOLVED,", "actor": _cell(act["resolved_name"] or act["text"] or "UNRESOLVED", bool(act["resolved_name"])),
               "action": _cell(p["lemma"]), "object": _cell(obj["head"]) if obj else "UNRESOLVED,",
               "perspective_location": loc_cell(p)}
        refs = [x["span"] for x in chain]
        anchor = ev.get("time_anchor")
        base = {"instance_id": f"ti{len(instances)}", "event_id": p["event_id"], "event_chain": [x["event_id"] for x in chain],
                "actor": act, "object": obj, "locations": p["locations"], "time_anchor": anchor, "source_refs": refs,
                "retrieval": {"method": res["method"], "key": res["key"], "alternatives": res["alternatives"], "context": res.get("context"),
                              "forbidden_methods": ["word_overlap", "nearest_match", "objective_text_match"]}}
        if res["match"]:
            t = res["match"]
            gate = db.gate(t["exit_gate_id"]) if t["exit_gate_id"] else None
            row["exit"] = f"{gate['gate_id']}: {' AND '.join(gate['conditions'])}" if gate else "UNRESOLVED"
            if t["termination_triggers"]:
                row["exit"] += " [inferred candidates: " + " | ".join(x["trigger"] for x in t["termination_triggers"]) + "]"
            inst = dict(base, template_id=t["loop_id"], template_status=t["status"], template_version=t["version"],
                        domains=db.domains_of(t["loop_id"]),
                        initial_state={"predicate": t["initial_test"], "status": "inferred"},
                        target_state={"predicate": "loop exits via gate", "status": "inferred"},
                        test={"predicate": t["initial_test"], "status": "inferred"},
                        operate={"action": p["lemma"], "status": "explicit", "span": p["span"]},
                        retest={"predicate": t["initial_test"], "status": "inferred"},
                        exit={"gate": gate, "status": "inferred",
                              "note": "exit is not narrated; represented as inferred, never as fact"},
                        termination_triggers=[dict(x, occurred="not_stated_in_text") for x in t["termination_triggers"]],
                        iteration_policy={"max_iterations": t["max_iterations"], "bounded_by": "exit gate"},
                        alternative_techniques=t["techniques"], admissibility=[], row=row,
                        **prov(f"TOTE-BIND/{t['loop_id']}", "inferred", status="inferred", version=t["version"]))
            instances.append(inst)
            # inferred precondition: a perspective vantage implies the actor got there
            for l in p["locations"]:
                if l["role"] != "perspective":
                    continue
                r2 = db.lookup("approach", l["head_lemma"])
                if not r2["match"]:
                    continue
                t2 = r2["match"]
                g2 = db.gate(t2["exit_gate_id"])
                default = next((x for x in t2["techniques"] if x["likelihood_class"] == "high"), None)
                row2 = {"modality": "(walking),🙌 [assumed_default]", "actor": row["actor"], "action": "approach,",
                        "object": _cell(l["head"]), "perspective_location": "start: UNRESOLVED,",
                        "exit": f"{g2['gate_id']}: {' AND '.join(g2['conditions'])}"}
                instances.append(dict(
                    base, instance_id=f"ti{len(instances)}", event_id=None, event_chain=[], object=l, locations=[],
                    retrieval={"method": r2["method"], "key": r2["key"], "alternatives": r2["alternatives"],
                               "triggered_by": "TOTE-PRECOND-VANTAGE (from-PP vantage implies arrival)"},
                    template_id=t2["loop_id"], template_status=t2["status"], template_version=t2["version"],
                    domains=db.domains_of(t2["loop_id"]),
                    initial_state={"predicate": "actor_position != hill", "start_position": "UNRESOLVED", "status": "inferred"},
                    target_state={"predicate": f"actor_position == {l['head_lemma']}", "status": "explicit",
                                  "note": "the hill is stated; route and start are not"},
                    test={"predicate": t2["initial_test"], "status": "inferred"},
                    operate={"action": "one external-kinesthetic step via default technique", "technique": default, "status": "assumed_default"},
                    retest={"predicate": t2["initial_test"], "status": "inferred"},
                    exit={"gate": g2, "status": "inferred"}, termination_triggers=t2["termination_triggers"],
                    iteration_policy={"max_iterations": t2["max_iterations"], "bounded_by": "exit gate"},
                    alternative_techniques=t2["techniques"], admissibility=[], row=row2,
                    **prov("TOTE-PRECOND-VANTAGE", "inferred", status="inferred")))
        else:
            row["exit"] = "UNRESOLVED (no template)"
            cand_id = f"TL-H-{p['lemma'].upper()}-{(obj['head_lemma'] if obj else 'NONE').upper()}-{doc_sha[:8]}"
            cand = {"loop_id": cand_id, "name": f"{p['lemma']} {obj['head_lemma'] if obj else ''}".strip(),
                    "domain": "UNRESOLVED", "objective": "UNRESOLVED", "initial_test": "UNRESOLVED", "exit_predicate": "UNRESOLVED",
                    "max_iterations": -1, "epistemic_status": "ACT", "modality_cell": row["modality"], "actor_cell": "<actor>,",
                    "action_cell": row["action"], "object_cell": row["object"], "perspective_cell": row["perspective_location"],
                    "exit_gate_id": "", "action_lemma": p["lemma"], "object_lemma": obj["head_lemma"] if obj else "",
                    "termination_triggers": [], "techniques": [], "status": "candidate", "version": "1",
                    "provenance": {"source": "harvested from narrative text", "method": "HARVEST-NL-1", "doc_sha256": doc_sha,
                                   "span": p["span"], "authority": None},
                    "in_domain": [["UNRESOLVED", "primary", "harvested; domain not yet supported"]]}
            harvest.append(cand)
            inst = dict(base, template_id="NO_MATCH", template_status=None,
                        fallback={"kind": "explicit_fallback", "reason": f"no TOTE row for key {res['key']} or ({p['lemma']}, *)",
                                  "nearest_match_forced": False, "harvest_candidate": cand_id},
                        operate={"action": p["lemma"], "status": "explicit", "span": p["span"]},
                        exit={"gate": None, "status": "unresolved"}, row=row,
                        **prov("TOTE-NO-MATCH-FALLBACK", "explicit", status="inferred"))
            instances.append(inst); no_match.append(inst["instance_id"])
    persisted = []
    if state["input"].get("harvest"):
        persisted = [c["loop_id"] for c in harvest if db.harvest(c)]
    state["tote"] = {"instances": instances, "no_match": no_match, "harvest_candidates": harvest,
                     "harvest_persisted": persisted, "db": {"path": str(db.path), "loops": db.count(),
                                                            "canonical": db.count("canonical"), "candidate": db.count("candidate")}}
    return state


# 08 ------------------------------------------------------------------------
ELIGIBLE_POS = {"NOUN", "VERB", "ADJ", "ADV"}


def s08_lexical(state):
    protected_names = {e["name"] for e in state["scope"]["entities"] if e["protected"]}
    occ, needs, protected = [], [], []
    for s in analysis.iter_sentences(state["structure"]):
        for t in state["tagged"][s["sent_id"]]:
            if not t["text"][:1].isalpha():
                continue
            o = {"occ_id": f"{s['sent_id']}t{t['tok_idx']}", "word_full": t["text"], "lemma": t["lemma"], "pos": t["pos"],
                 "page_idx": s["page_idx"], "sent_idx": s["sent_idx"], "char_start": t["char_start"], "char_end": t["char_end"],
                 "skeleton": consonant_skeleton(t["text"])}
            occ.append(o)
            if t["pos"] == "PROPN" or t["text"] in protected_names:
                protected.append({"word": t["text"], "occ_id": o["occ_id"], "reason": "name (protected, never Gestalt-mapped)"})
            elif t["pos"] in ELIGIBLE_POS and not (t["pos"] == "ADV" and t["rule"] == "POS-CLOSED"):
                needs.append({"word": t["text"], "lemma": t["lemma"], "occurrence_ref": o["occ_id"], "pos": t["pos"],
                              "skeleton": o["skeleton"], "id": f"gestalt.{o['skeleton']}",
                              "span": {k: o[k] for k in ("page_idx", "sent_idx", "char_start", "char_end")}})
    coll = collisions(n["word"] for n in needs)
    for n in needs:
        n["collision_with"] = [w for w in coll.get(n["skeleton"], []) if w != n["word"].lower()]
    state["lexical"] = {"occurrences": occ, "mapping_candidates": needs, "protected": protected,
                        "skeleton_collisions": [{"skeleton": k, "words": v, "status": "must_be_disambiguated_in_stage_10"} for k, v in coll.items()],
                        "rule": "skeleton = remove repeated adjacent letters then vowels; a clue at the END of the Gestalt id, never meaning",
                        "note": "pronouns and closed-class words are not mapped; pronouns resolve to entities (coref)"}
    return state


STAGES = [("01_boot", s01_boot), ("02_structure", s02_structure), ("03_scope_attribution", s03_scope),
          ("04_temporal", s04_temporal), ("05_semantics", s05_semantics), ("06_context", s06_context),
          ("07_tote_bind", s07_tote_bind), ("08_lexical_ids", s08_lexical)]
