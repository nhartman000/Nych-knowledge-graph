"""
gst_export.py -- package the deterministic NYCH findings as a .gst pretext
file for the LLM pruning + Gestalt-mapping step.

Per the NYCH design: the inverse-transform/dither pruning is performed by
an LLM, not by deterministic code. Narrowing the problemspace by the factor
of the inverse transform -- the coarse domain prune, the subdomain prune,
and the competency check within domain, with a controlled boundary-leakage
margin ("dither") -- is accomplished by the LLM, and all the initial
deterministic findings are passed to it as the pretext in a .gst file.

The shape here is grounded against mg8-engine's actual Gst model
(src/mg8_engine/models.py): plain JSON, `extra="allow"`, with optional
gst_version / state_id / state / domain fields. Everything nych adds rides
under the extra key "nych_pretext" so the engine's Gst parser accepts the
file unchanged.

Honesty note: this module serializes what the deterministic side found --
including UNRESOLVED domains, None competency, and TOTE fallbacks -- and
the instructions for the LLM. It does not execute the pruning, call an
LLM, or guess any field it couldn't compute.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .gestalt_handoff import build_handoff
from .session_invariants import SessionInvariants

GST_VERSION = "1.0"
DEFAULT_DITHER = 0.1

PRUNING_INSTRUCTIONS = [
    "Narrow the problemspace by the factor of the inverse transform using "
    "the deterministic findings below as pretext.",
    "Coarse prune by domain first: discard content outside the classified "
    "domain (treat UNRESOLVED as no domain constraint).",
    "Fine prune by subdomain within the surviving domain when a subdomain "
    "is given.",
    "Apply the competency check within domain: gate content depth to the "
    "reported competency score (None means no competency gate).",
    "Apply the dither margin as controlled boundary leakage: allow content "
    "within the margin just outside the pruned boundary through, so access "
    "widens gradually from novice to expert rather than cliff-edging.",
]


def build_gst(text: str, *, db_path: str | Path | None = None,
              session: SessionInvariants | None = None,
              subdomain: str | None = None,
              dither: float = DEFAULT_DITHER) -> dict:
    """Build the .gst pretext payload for `text`.

    Runs the deterministic pipeline (build_handoff) and wraps the result in
    an mg8-engine-compatible Gst JSON shape. `dither` is the boundary-
    leakage margin handed to the LLM pruning step (0.0 = hard boundary)."""
    if not 0.0 <= dither <= 1.0:
        raise ValueError(f"dither must be within [0.0, 1.0], got {dither}")

    handoff = build_handoff(text, db_path=db_path, session=session,
                            subdomain=subdomain)
    analysis = handoff["analysis"]
    tote = handoff["tote"]
    state_id = "nych-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    return {
        "gst_version": GST_VERSION,
        "state_id": state_id,
        "domain": (analysis["domain"].lower()
                   if analysis["domain"] != "UNRESOLVED" else "general"),
        "state": {
            "source_text": text,
            "roles": handoff["roles"],
        },
        # Everything below rides on Gst's extra="allow".
        "nych_pretext": {
            "analysis": analysis,
            "subdomain": subdomain,
            "tote_match": tote["loop"] if tote and tote.get("matched") else None,
            "tote_fallback": (None if tote is None or tote.get("matched")
                              else tote),
            "modality_operators": handoff["modality_operators"],
            "needs_mapping": handoff["needs_mapping"],
            "pinned": handoff["pinned"],
            "protected": handoff["protected"],
            "discretion_rules": handoff["discretion_rules"],
            "pruning": {
                "dither": dither,
                "instructions": list(PRUNING_INSTRUCTIONS),
            },
        },
    }


def write_gst(payload: dict, path: str | Path) -> Path:
    """Write a build_gst payload to `path` as UTF-8 JSON."""
    path = Path(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
