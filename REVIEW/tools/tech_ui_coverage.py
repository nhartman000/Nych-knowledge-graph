"""Recompute the tech.ui coverage curve from the compact export and compare with the committed coverage.json."""
import gzip, json, sys, collections, pathlib
d = pathlib.Path(sys.argv[1]); cov = json.load(open(d / "coverage.json"))
C = collections.Counter(json.loads(l)["canonical"] for l in gzip.open(d / "ui_actions.jsonl.gz", "rt", encoding="utf-8"))
N = cov["n_actions"]; m = [n for _, n in C.most_common()]
got = {str(k): round(100 * sum(m[:k]) / N, 1) for k in (10, 25, 50, 100, 150)}
print("mapped actions in export:", sum(m), "| all actions (incl. unmapped):", N, "| canonical used:", len(m))
print("recomputed top-N %:", got); print("committed  top-N %:", cov["coverage_topN_canonical_pct"])
sys.exit(0 if got == {str(k): v for k, v in cov["coverage_topN_canonical_pct"].items()} and len(m) == cov["n_canonical"] else 1)
