"""Compact export for the NYCH TOTE store: out/kg_export/{canonical_actions.json, ui_actions.jsonl.gz}. No article text, quote <= 25 words."""
import json, os, gzip, shutil, re
ROOT = os.path.join(os.path.dirname(__file__), ".."); O = lambda *p: os.path.join(ROOT, "out", *p)
def quote(a):
    w = a["text"].split()
    if len(w) <= 25: return a["text"]
    i = next((k for k, x in enumerate(w) if a["surface"].lower() in x.lower()), 0); s = max(0, i - 5)
    return ("… " if s else "") + " ".join(w[s:s + 25]) + " …"
os.makedirs(O("kg_export"), exist_ok=True)
A = [a for a in json.load(open(O("actions_canon.json"))) if a["canonical"] != "NON_ACTION" and not a["canonical"].startswith("UNMAPPED")]
with gzip.open(O("kg_export", "ui_actions.jsonl.gz"), "wt", encoding="utf-8") as f:
    for a in A:
        f.write(json.dumps({"id": f"{a['step_id']}:{a['action_idx']}", "canonical": a["canonical"], "param": a.get("canonical_param", ""), "verb": a["verb"], "object": a["object"],
            "obj_type": a["obj_type"], "platform": a["platform"], "platform_hints": a["platform_hints"], "site": a["site"], "url": a["url"], "retrieved": a["retrieved"],
            "section": a["section"], "step_no": a["step_no"], "kind": a["kind"], "quote": quote(a), "direction": a["direction"], "count": a["count"],
            "duration": a["duration"], "condition_cues": a["condition_cues"]}, ensure_ascii=False) + "\n")
shutil.copy(O("canonical_actions.json"), O("kg_export", "canonical_actions.json"))
shutil.copy(O("coverage.json"), O("kg_export", "coverage.json"))
print("exported", len(A))
