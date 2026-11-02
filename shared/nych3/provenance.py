"""Provenance record attached to every extracted/inferred item (spec section 3).
Confidence is never a bare float: kind is calibrated | likelihood_class | unavailable."""
from __future__ import annotations

PROVENANCE = ("explicit", "inferred", "predicted", "assumed_default")
PROPOSITION_STATUS = ("narrator_asserted", "explicit_dialogue", "inferred", "predicted")
LIKELIHOOD_CLASSES = ("high", "medium", "low", "latent")   # ordered, uncalibrated


def prov(rule_id: str, provenance: str = "explicit", *, status: str = "narrator_asserted",
         confidence: dict | None = None, alternatives: list | None = None, version: str = "1") -> dict:
    assert provenance in PROVENANCE, provenance
    assert status in PROPOSITION_STATUS, status
    conf = confidence or {"kind": "unavailable", "value": None, "source": None}
    if conf["kind"] == "likelihood_class":
        assert conf["value"] in LIKELIHOOD_CLASSES
    if conf["kind"] == "calibrated":
        assert conf.get("source"), "calibrated confidence requires a named source"
    return {"provenance": provenance, "proposition_status": status, "confidence": conf,
            "alternatives": alternatives or [], "produced_by": {"rule_id": rule_id, "version": version}}


def likelihood(cls: str, rule_id: str) -> dict:
    assert cls in LIKELIHOOD_CLASSES
    return {"kind": "likelihood_class", "value": cls, "source": rule_id}
