"""Recompute the tech.ui coverage curve from the compact export and compare with the committed coverage.json.

The denominator (coverage.json n_actions = 65,929 extracted actions, NON_ACTION rows excluded) is rebuilt from
ui_actions.jsonl.gz (mapped to one of the 81 authored classes) + ui_actions_unmapped.jsonl.gz (UNMAPPED:<verb>).
Also reports locator quality (section / step presence) and quote token lengths."""
import gzip, json, sys, collections, pathlib
d = pathlib.Path(sys.argv[1]); cov = json.load(open(d / "coverage.json"))
rd = lambda n: [json.loads(l) for l in gzip.open(d / n, "rt", encoding="utf-8")]
mapped, unmapped = rd("ui_actions.jsonl.gz"), rd("ui_actions_unmapped.jsonl.gz")
C = collections.Counter(a["canonical"] for a in mapped)
N = len(mapped) + len(unmapped); m = [n for _, n in C.most_common()]
got = {str(k): round(100 * sum(m[:k]) / N, 1) for k in (10, 25, 50, 100, 150)}
print("mapped:", len(mapped), "| unmapped:", len(unmapped), "| rebuilt denominator:", N, "| committed n_actions:", cov["n_actions"], "| canonical used:", len(m))
print("unmapped share %:", round(100 * len(unmapped) / N, 1), "(committed", cov["unmapped_share"], ")")
print("recomputed top-N %:", got); print("committed  top-N %:", cov["coverage_topN_canonical_pct"])
def lq(a):
    s, t = bool((a["section"] or "").strip()), bool(a["step_no"])
    return "section+step" if s and t else "section_only" if s else "step_only" if t else "url_only"
print("locator_quality (mapped):", dict(collections.Counter(lq(a) for a in mapped)))
print("quote whitespace tokens > 25 (ellipsis markers included):", dict(sorted(collections.Counter(len(a["quote"].split()) for a in mapped + unmapped if len(a["quote"].split()) > 25).items())))
mx = max(len([w for w in a["quote"].split() if w != "…"]) for a in mapped + unmapped)
print("max source tokens (ellipsis markers excluded):", mx)
ok = (got == {str(k): v for k, v in cov["coverage_topN_canonical_pct"].items()} and len(m) == cov["n_canonical"] and N == cov["n_actions"]
      and all(a["canonical"].startswith("UNMAPPED") for a in unmapped) and mx <= 25)
sys.exit(0 if ok else 1)
