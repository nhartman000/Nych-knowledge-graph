"""Apply config/mapping.json to out/actions.jsonl -> canonical labels, coverage curve, canonical_actions.json, steps CSV."""
import json, os, re, csv, collections
ROOT = os.path.join(os.path.dirname(__file__), "..")
MAP = json.load(open(os.path.join(ROOT, "config", "mapping.json")))["rules"]
for r in MAP: r["_rx"] = re.compile(r["text"], re.I) if "text" in r else None
NONACT = set(json.load(open(os.path.join(ROOT, "config", "mapping.json"))).get("non_action_verbs", []))
def canon(a):
    v = a["verb"]; v1 = v.split()[0]
    if v in NONACT or v1 in NONACT: return "NON_ACTION"
    if v1 == "make" and re.match(r"(?i)sure|certain", a["object"]): return "VERIFY_STATE"
    if v1 == "doubleclick": return "DOUBLE_CLICK_TAP"
    if v1 == "rightclick": return "RIGHT_CLICK"
    for r in MAP:
        if r["_rx"] is not None:
            if v1 in ("touch", "press", "tap", "click", "hold", "triple", "double", "long", "control") and re.search(r"(?i)\b" + re.escape(a["surface"]) + r"\b(\s+and\s+hold|-?press|-?click|-?tap)?", a["text"]) and r["_rx"].search(a["text"][max(0, a["text"].lower().find(a["surface"].lower()) - 16):a["text"].lower().find(a["surface"].lower()) + len(a["surface"]) + 12]): return r["canon"]
            continue
        vs = r.get("verbs", [])
        if v in vs or (v1 in vs and " " not in v and True) or (v1 in vs and v not in {x for rr in MAP for x in rr.get("verbs", [])}):
            if "obj_types" in r and a["obj_type"] not in r["obj_types"]: continue
            return r["canon"]
    for r in MAP:  # fallback: ignore obj_types
        vs = r.get("verbs", [])
        if v in vs or v1 in vs: return r["canon"]
    return "UNMAPPED:" + v
def main():
    A = [json.loads(l) for l in open(os.path.join(ROOT, "out", "actions.jsonl"))]
    for a in A:
        a["canonical"] = canon(a)
        if a["canonical"] == "SWIPE" and a["direction"]: a["canonical_param"] = a["direction"].split(";")[0].lower()
    n_non = sum(a["canonical"] == "NON_ACTION" for a in A); ALL = A; A = [a for a in A if a["canonical"] != "NON_ACTION"]
    N = len(A); C = collections.Counter(a["canonical"] for a in A)
    mapped = [(k, n) for k, n in C.most_common() if not k.startswith("UNMAPPED")]
    cum, curve = 0, {}
    for i, (k, n) in enumerate(mapped, 1):
        cum += n; curve[i] = cum / N
    pts = {n: round(100 * curve[min(n, len(mapped))], 1) for n in (10, 25, 50, 100, 150)}
    V = collections.Counter(a["verb"] for a in A); vc, vcurve = 0, {}
    for i, (k, n) in enumerate(V.most_common(), 1): vc += n; vcurve[i] = vc / N
    vpts = {n: round(100 * vcurve[min(n, len(V))], 1) for n in (10, 25, 50, 100, 150)}
    json.dump({"n_actions": N, "n_non_action_excluded": n_non, "n_canonical": len(mapped), "unmapped_share": round(100 * sum(n for k, n in C.items() if k.startswith("UNMAPPED")) / N, 1),
               "coverage_topN_canonical_pct": pts, "coverage_topN_raw_verb_lemmas_pct": vpts, "n_distinct_verbs": len(V),
               "curve": {k: round(v, 4) for k, v in curve.items()}, "verb_curve": {k: round(v, 4) for k, v in list(vcurve.items())[:300]},
               "top_unmapped": collections.Counter(a["verb"] for a in A if a["canonical"].startswith("UNMAPPED")).most_common(40)},
              open(os.path.join(ROOT, "out", "coverage.json"), "w"), indent=1)
    with open(os.path.join(ROOT, "out", "steps_all.csv"), "w", newline="") as f:
        cols = ["step_id", "action_idx", "canonical", "canonical_param", "verb", "surface", "object", "obj_type", "direction", "count", "duration", "condition_cues", "platform", "platform_hints", "site", "url", "retrieved", "section", "step_no", "kind", "text"]
        w = csv.DictWriter(f, cols, extrasaction="ignore"); w.writeheader(); [w.writerow(a) for a in A]
    json.dump(A, open(os.path.join(ROOT, "out", "actions_canon.json"), "w"))
    print(json.dumps({k: v for k, v in json.load(open(os.path.join(ROOT, "out", "coverage.json"))).items() if k not in ("curve", "verb_curve")}, indent=0)[:3000])
    print(C.most_common(30))
if __name__ == "__main__": main()
