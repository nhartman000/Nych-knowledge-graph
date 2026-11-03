"""Stage 10: FIRST LLM CALL CONTRACT -- Gestalt mapping only.

Input  (build_request): eligible mapping candidates, protected terms, pins,
       invariant modality operators, directive. NO pruning, gates, or flow.
Output (provider):      {"mappings": [{"word", "occurrence_ref", "symbol_id", "glyph"}]}
Validation:             validate_plan (NYCH3 rules) and, when mg8-engine is
                        importable, mg8_engine.pipeline.validate_mapping_plan.
Persistence:            persist() writes to Kuzu ONLY with approved=True (GATE.md).

The only provider shipped is MockProvider (deterministic, offline). A real
provider implements the same `propose(request) -> dict` method."""
from __future__ import annotations
import hashlib, json, unicodedata
from ..stages import DIRECTIVE


class ValidationError(Exception):
    pass


def build_request(gst: dict) -> dict:
    lex = gst["nych3"]["lexical"]
    return {
        "contract": "nych3.gestalt_call.v1", "task": "ASSIGN_GESTALTS_ONLY", "directive": DIRECTIVE,
        "rules": ["Return one mapping per listed occurrence; map nothing else.",
                  "symbol_id MUST end with '.' + the word's skeleton.",
                  "Never map protected terms; never use a modality operator glyph in symbol_id or glyph.",
                  "Pinned words reuse their pinned symbol_id.",
                  "Different words that share a skeleton must get different symbol_ids.",
                  "Emotional connotation belongs in the Gestalt (the modality operator is invariant)."],
        "modality_operators": gst["nych3"]["modality_operators"],
        "protected": [p["word"] for p in lex["protected"]],
        "pinned": gst["nych_pretext"].get("pinned", []),
        "eligible": [{k: c[k] for k in ("word", "lemma", "occurrence_ref", "skeleton", "collision_with")} for c in lex["mapping_candidates"]],
        "context_summary": {"domain": gst["domain"], "narrative_tense": gst["narrative_tense"]},
    }


def prompt_text(request: dict) -> str:
    return ("You are NYCH stage 10 (Gestalt mapping ONLY). " + request["directive"] + "\n"
            + json.dumps({k: v for k, v in request.items() if k != "directive"}, ensure_ascii=False, indent=2)
            + '\nReturn ONLY JSON: {"mappings": [{"word":..., "occurrence_ref":..., "symbol_id":..., "glyph":...}]}')


class MockProvider:
    """Deterministic stub: symbol_id = gst3.mock.<lemma-hash6>.<skeleton>. Not a real Gestalt choice."""
    name = "mock"
    version = "mock-1"

    def propose(self, request: dict) -> dict:
        pins = {p["word"].lower(): p["symbol_id"] for p in request.get("pinned", [])}
        out = []
        for c in request["eligible"]:
            sid = pins.get(c["word"].lower()) or f"gst3.mock.{hashlib.sha1(c['lemma'].encode()).hexdigest()[:6]}.{c['skeleton']}"
            out.append({"word": c["word"], "occurrence_ref": c["occurrence_ref"], "symbol_id": sid, "glyph": "◌"})
        return {"mappings": out, "provider": self.name, "provider_version": self.version}


def _bare(s: str) -> str:
    return "".join(ch for ch in s if ch not in "\ufe0f\ufe0e\u200d")


def validate_plan(plan: dict, request: dict) -> list[dict]:
    """Raise ValidationError on the first violation; return accepted mappings with full words kept."""
    elig = {c["occurrence_ref"]: c for c in request["eligible"]}
    protected = {p.lower() for p in request["protected"]}
    pins = {p["word"].lower(): p["symbol_id"] for p in request.get("pinned", [])}
    glyphs = {_bare(g) for g in request["modality_operators"].values()}
    single = {g for g in glyphs if len(g) == 1}
    sid_to_lemma, accepted, seen_occ = {}, [], set()
    for m in plan.get("mappings", []):
        w = m.get("word", ""); occ = m.get("occurrence_ref")
        if occ in seen_occ:
            raise ValidationError(f"duplicate mapping for occurrence {occ!r} ({w!r})")
        seen_occ.add(occ)
        if w.lower() in protected:
            raise ValidationError(f"protected term {w!r} was Gestalt-mapped")
        if occ not in elig or elig[occ]["word"] != w:
            raise ValidationError(f"mapping for {w!r} ({occ}) was not requested")
        sid, glyph = str(m.get("symbol_id") or ""), str(m.get("glyph") or "")
        for field, val in (("symbol_id", sid), ("glyph", glyph)):
            b = _bare(val)
            if any(g in b for g in glyphs) or any(ch in single for ch in b):
                raise ValidationError(f"{field} for {w!r} uses a modality operator glyph")
        if w.lower() in pins and sid != pins[w.lower()]:
            raise ValidationError(f"{w!r} is pinned to {pins[w.lower()]!r}; got {sid!r}")
        skel = elig[occ]["skeleton"]
        if not sid.endswith("." + skel):
            raise ValidationError(f"symbol_id {sid!r} for {w!r} does not end with its skeleton '.{skel}'")
        lem = elig[occ]["lemma"]
        if sid in sid_to_lemma and sid_to_lemma[sid] != lem:
            raise ValidationError(f"skeleton collision unresolved: {sid!r} used for {sid_to_lemma[sid]!r} and {lem!r}")
        sid_to_lemma[sid] = lem
        accepted.append({"word_full": w, "lemma": lem, "occurrence_ref": occ, "skeleton": skel, "symbol_id": sid, "glyph": glyph,
                         "provenance": {"provenance": "predicted", "produced_by": plan.get("provider", "unknown"),
                                        "status": "proposed_pending_gate_10"}})
    missing = set(elig) - {a["occurrence_ref"] for a in accepted}
    if missing:
        raise ValidationError(f"eligible occurrences left unmapped: {sorted(missing)}")
    return accepted


def validate_with_mg8(plan: dict, gst: dict) -> str:
    """Run mg8-engine's own validator. Returns 'passed' or 'mg8-engine not installed'."""
    try:
        from mg8_engine.pipeline import validate_mapping_plan
    except Exception as e:  # pragma: no cover
        return f"mg8-engine not importable: {e}"
    validate_mapping_plan({"mappings": [{"word": m["word"], "symbol_id": m["symbol_id"], "glyph": m["glyph"]} for m in plan["mappings"]]}, gst)
    return "passed"


def fill_cells(row: dict, accepted: list[dict]) -> dict:
    """Write Gestalts into 'word,' cells after acceptance (word kept, Gestalt after the comma)."""
    by = {a["word_full"].lower(): a["symbol_id"] for a in accepted}
    by.update({a["lemma"]: a["symbol_id"] for a in accepted})
    out = {}
    for k, cell in row.items():
        parts = []
        for part in cell.split(" ; "):
            if part.endswith(",") and not part.startswith("UNRESOLVED"):
                word = part[:-1].split()[-1].split("(")[0]
                parts.append(part + by.get(word.lower(), ""))
            else:
                parts.append(part)
        out[k] = " ; ".join(parts)
    return out


def persist(db, accepted: list[dict], gst: dict, session: str, approved: bool = False):
    """Persist after GATE 10. Full word + occurrence kept; skeleton is an attribute."""
    if not approved:
        raise PermissionError("GATE 10 not approved: mappings stay proposed (see 10_gestalt_llm/GATE.md)")
    doc = gst["nych3"]["source"]["sha256"]["story"]
    occ = {o["occ_id"]: o for o in gst["nych3"]["lexical"]["occurrences"]}
    for a in accepted:
        eid = f"lex:{a['word_full'].lower()}"
        if not db.q("MATCH (e:LexicalEntry {entry_id:$e}) RETURN e.entry_id AS e", {"e": eid}):
            db.c.execute("CREATE (:LexicalEntry {entry_id:$e,word_full:$w,lemma:$l,skeleton:$s,protected:false})",
                         dict(e=eid, w=a["word_full"], l=a["lemma"], s=a["skeleton"]))
        if not db.q("MATCH (g:Gestalt {gestalt_id:$g}) RETURN g.gestalt_id AS g", {"g": a["symbol_id"]}):
            db.c.execute("CREATE (:Gestalt {gestalt_id:$g,glyph:$y,lexical_form:$w,sense:'',route:'nych3.stage10',recoverability_note:$n,origin:'nych3_stage10'})",
                         dict(g=a["symbol_id"], y=a["glyph"], w=a["word_full"], n=f"skeleton clue {a['skeleton']}"))
        o = occ[a["occurrence_ref"]]
        oid = f"{doc[:12]}:{o['occ_id']}"
        if not db.q("MATCH (o:Occurrence {occ_id:$o}) RETURN o.occ_id AS o", {"o": oid}):
            db.c.execute("CREATE (:Occurrence {occ_id:$o,word_full:$w,doc_sha256:$d,page_idx:$p,sent_idx:$s,char_start:$a,char_end:$b})",
                         dict(o=oid, w=o["word_full"], d=doc, p=o["page_idx"], s=o["sent_idx"], a=o["char_start"], b=o["char_end"]))
            db.c.execute("MATCH (e:LexicalEntry {entry_id:$e}),(o:Occurrence {occ_id:$o}) CREATE (e)-[:OCCURS_AS]->(o)", dict(e=eid, o=oid))
        db.c.execute("MATCH (e:LexicalEntry {entry_id:$e}),(g:Gestalt {gestalt_id:$g}) CREATE (e)-[:MAPPED_TO {session:$s,status:'accepted',provenance:$p}]->(g)",
                     dict(e=eid, g=a["symbol_id"], s=session, p=json.dumps(a["provenance"])))
    return len(accepted)
