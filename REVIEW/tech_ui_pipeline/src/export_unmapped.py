"""Companion to export_kg.py (nych-ui-actions): writes out/kg_export/ui_actions_unmapped.jsonl.gz with the
2,442 extracted actions that the authored mapping did NOT assign to one of the 81 canonical classes
(canonical = "UNMAPPED:<verb>"). Same compact record format as ui_actions.jsonl.gz (no article text; quote =
at most 25 whitespace tokens of source text, plus a leading and/or trailing "…" marker when truncated).
mapped (ui_actions.jsonl.gz) + unmapped (this file) = the 65,929 extracted-action denominator in coverage.json.
NON_ACTION rows (3,797) are excluded from the denominator and are not exported."""
import json, os, gzip
ROOT = os.path.join(os.path.dirname(__file__), ".."); O = lambda *p: os.path.join(ROOT, "out", *p)
def quote(a):
    w = a["text"].split()
    if len(w) <= 25: return a["text"]
    i = next((k for k, x in enumerate(w) if a["surface"].lower() in x.lower()), 0); s = max(0, i - 5)
    return ("… " if s else "") + " ".join(w[s:s + 25]) + " …"
A = [a for a in json.load(open(O("actions_canon.json"))) if a["canonical"].startswith("UNMAPPED")]
with gzip.open(O("kg_export", "ui_actions_unmapped.jsonl.gz"), "wt", encoding="utf-8") as f:
    for a in A:
        f.write(json.dumps({"id": f"{a['step_id']}:{a['action_idx']}", "canonical": a["canonical"], "param": a.get("canonical_param", ""), "verb": a["verb"], "object": a["object"],
            "obj_type": a["obj_type"], "platform": a["platform"], "platform_hints": a["platform_hints"], "site": a["site"], "url": a["url"], "retrieved": a["retrieved"],
            "section": a["section"], "step_no": a["step_no"], "kind": a["kind"], "quote": quote(a), "direction": a["direction"], "count": a["count"],
            "duration": a["duration"], "condition_cues": a["condition_cues"]}, ensure_ascii=False) + "\n")
print("exported unmapped", len(A))
