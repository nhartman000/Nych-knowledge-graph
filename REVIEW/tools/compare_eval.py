"""Compare nych3-eval JSON to expected headline numbers (exact). usage: compare_eval.py got.json expected.json"""
import json, sys
got, want = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
def pick(d, path):
    for k in path.split("."): d = d[k]
    return d
bad = [(k, v, pick(got, k)) for k, v in want.items() if pick(got, k) != v]
print("mismatches:", bad or "none"); sys.exit(1 if bad else 0)
