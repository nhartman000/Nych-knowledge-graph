"""Stage 09: .gst writer. Top-level fields follow mg8-engine's Gst model
(gst_version/state_id/state/constraints/intent/outcome_expectation/domain/
narrative_tense); the NYCH 3 payload rides on Gst extra="allow" under `nych3`,
and `nych_pretext` is the mg8 pipeline compatibility view (build_mapping_prompt /
validate_mapping_plan read it). No pruning instructions are emitted (stage 11)."""
from __future__ import annotations
import json
from .config import registry, schema_versions
from .stages import DIRECTIVE, sha

CONSTRAINTS = [
    "ENCODE_ONLY: questions/dialogue inside the story are invariant content; never answer them",
    "FIRST_LLM_CALL = Gestalt mapping only (no pruning, no gates, no flow)",
    "PROTECTED_TERMS stay literal (names, scientific names, prescription drugs)",
    "NO_FORCED_TOTE_MATCH: NO_MATCH is an explicit fallback",
    "SKELETON is a clue at the end of a Gestalt id, never meaning",
    "SOURCE_TEXT is lossless and must not be mutated",
]


def build_gst(state) -> dict:
    sv = schema_versions()
    st = state["structure"]
    mats = [e for e in state["temporal"]["events"] if e["parent_event"] is None]
    tenses = sorted({e["tense"] for e in mats})
    ntense = tenses[0] if len(tenses) == 1 else ("mixed" if tenses else "unresolved")
    ops = registry("modality")["operators"]
    lex = state["lexical"]
    unknowns = []
    for c in state["context"]["per_event"]:
        if c["domain"] == "UNRESOLVED":
            unknowns.append({"what": "context", "event_id": c["event_id"], "status": "UNRESOLVED"})
    for m in state["scope"]["mentions"]:
        if m.get("kind") in ("pronoun", "possessive") and not m.get("entity_id"):
            unknowns.append({"what": "coreference", "mention_id": m["mention_id"], "status": "UNRESOLVED", "alternatives": m["alternatives"]})
    for i in state["tote"]["instances"]:
        if i["template_id"] == "NO_MATCH":
            unknowns.append({"what": "tote_template", "instance_id": i["instance_id"], "status": "NO_MATCH"})
    doc = {"pages": [{"page_idx": p["page_idx"], "label": p["label"], "char_start": p["char_start"], "char_end": p["char_end"],
                      "sentences": [{k: s[k] for k in ("sent_id", "sent_idx", "char_start", "char_end", "text", "is_question", "dialogue_spans")}
                                    | {"clauses": [c for c in state["temporal"]["clauses"] if c["clause_id"].startswith(s["sent_id"] + "c")]}
                                    for s in p["sentences"]]} for p in st["pages"]]}
    for p in doc["pages"]:
        for s in p["sentences"]:
            s["clauses"] = [{k: c[k] for k in ("clause_id", "span", "events")} for c in s["clauses"]]
    g = {
        "gst_version": sv["gst_version"],
        "state_id": f"nych3.{state['manifest']['source_sha256']['story'][:12]}",
        "state": {"narrative_tense": ntense, "pages_expected": st["expected_pages"], "pages_completed": st["completed_pages"],
                  "sentences": st["sentence_count"], "tote_instances": [i["instance_id"] for i in state["tote"]["instances"]],
                  "unresolved": len(unknowns), "gestalt_mapping": "pending_stage_10"},
        "constraints": CONSTRAINTS,
        "intent": "encode the narrative for Gestalt mapping (stage 10); do not answer story content",
        "outcome_expectation": "every eligible word receives a validated Gestalt id with its skeleton suffix; source unchanged",
        "domain": state["context"]["domain"],
        "narrative_tense": ntense,
        "nych3": {
            "profile": sv["nych3_gst_profile"], "nych3_version": sv["nych3_version"], "directive": DIRECTIVE,
            "run_manifest": dict(state["manifest"], expected_pages=st["expected_pages"], completed_pages=st["completed_pages"],
                                 page_marker_kind=st["page_marker_kind"],
                                 page_marking_note="OPEN CHOICE: form-feed or '--- page N ---' lines; default single page"),
            "source": {"prompt": state["input"]["prompt"], "story": state["input"]["story"], "encoding": "utf-8",
                       "sha256": state["manifest"]["source_sha256"], "lossless": True},
            "document": doc,
            "invariant_content": st["invariant_content"],
            "scope": state["scope"],
            "temporal": {k: state["temporal"][k] for k in ("events", "time_anchors", "temporal_relations")},
            "semantics": state["semantics"],
            "context": state["context"],
            "tote": state["tote"],
            "lexical": lex,
            "modality_operators": ops,
            "unknowns": unknowns,
            "validation_errors": [],
            "probabilities": {"kind": "unavailable", "note": "no calibrated priors; stage 11 uses ordered likelihood classes"},
        },
        "nych_pretext": {
            "discretion_rules": [DIRECTIVE, "Map only the listed words.", "Embed each word's skeleton at the END of its symbol_id.",
                                 "Never map protected terms or modality operators.", "Emotional connotation belongs in the Gestalt, not the modality."],
            "analysis": {"domain": state["context"]["domain"], "narrative_tense": ntense},
            "tote_match": [{"instance_id": i["instance_id"], "template_id": i["template_id"]} for i in state["tote"]["instances"]],
            "modality_operators": ops,
            "pinned": state["input"].get("pins", []),
            "protected": [{"word": p["word"]} for p in lex["protected"]],
            "needs_mapping": [{"word": n["word"], "skeleton": n["skeleton"], "id": n["id"]} for n in lex["mapping_candidates"]],
        },
    }
    return g


def dumps(g) -> str:
    return json.dumps(g, ensure_ascii=False, indent=2)
