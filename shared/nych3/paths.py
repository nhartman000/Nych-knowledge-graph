"""Stage 11: pruning + candidate paths with ORDERED likelihood classes
(high > medium > low > latent). No numbers unless a calibrated prior with a named
source exists (none does yet), so every path carries confidence.kind=likelihood_class
and outcome probability kind=unavailable. Commonality informs reuse, never probability."""
from __future__ import annotations
import json
from pathlib import Path
from .provenance import LIKELIHOOD_CLASSES, likelihood

SENSORY_EXPAND = {"external_auditory", "smell"}


def candidate_paths(gst: dict) -> dict:
    n3 = gst["nych3"]
    props = n3["semantics"]["propositions"]
    out, pruned = [], []
    for inst in n3["tote"]["instances"]:
        if inst["template_id"] == "NO_MATCH":
            pruned.append({"instance_id": inst["instance_id"], "reason": "no template: no path generated (explicit fallback kept)"})
            continue
        techs = inst.get("alternative_techniques") or []
        if not techs:
            out.append({"instance_id": inst["instance_id"], "template_id": inst["template_id"],
                        "paths": [{"path_id": f"{inst['instance_id']}.p0", "technique": None, "status": "default",
                                   "confidence": likelihood("high", "PATH-SINGLE-TEMPLATE"),
                                   "steps": ["TEST", "OPERATE", "RETEST", "EXIT(inferred)"]}],
                        "outcome_probability": {"kind": "unavailable"}})
            continue
        ranked = sorted(techs, key=lambda t: LIKELIHOOD_CLASSES.index(t["likelihood_class"]))
        actor = (inst.get("actor") or {}).get("entity_id")
        # Expand a latent alternative only if a later event could perceive the actor by sound/smell.
        trigger = next((p for p in props if p.get("channel") in SENSORY_EXPAND and (p.get("object") or {}).get("entity_id") == actor
                        and (p.get("actor") or {}).get("entity_id") != actor), None)
        paths = []
        for k, t in enumerate(ranked):
            status = "default" if k == 0 else ("expanded" if trigger else "latent")
            paths.append({"path_id": f"{inst['instance_id']}.p{k}", "technique": t["technique"], "status": status,
                          "confidence": likelihood(t["likelihood_class"], f"PATH-TEMPLATE-PRIOR ({t['source']})"),
                          "provenance": t["provenance"],
                          "expansion_reason": (f"event {trigger['event_id']} perceives the actor via {trigger['channel']}" if trigger and k else
                                               ("not expanded: no later event makes the technique outcome-relevant" if k else None)),
                          "steps": ["TEST position", f"OPERATE step ({t['technique']})", "RETEST", "EXIT at target"]})
        out.append({"instance_id": inst["instance_id"], "template_id": inst["template_id"], "paths": paths,
                    "outcome_probability": {"kind": "unavailable", "note": "no calibrated priors recorded"}})
    return {"candidates": out, "pruned": pruned, "formula_status": "Bayesian path formula (spec section 6) NOT evaluated: no priors with a recorded source"}


def write_trace(result: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for c in result["candidates"]:
            for p in c["paths"]:
                f.write(json.dumps({"event": "predicted_path", **p, "instance_id": c["instance_id"], "later_evidence": None}, ensure_ascii=False) + "\n")
        for p in result["pruned"]:
            f.write(json.dumps({"event": "pruned", **p}, ensure_ascii=False) + "\n")
