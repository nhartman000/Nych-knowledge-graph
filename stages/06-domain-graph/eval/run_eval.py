"""Score `resolve` on sentences.tsv: is the expected NAICS sector / CIP family the first item, or in the top 3?

  PYTHONPATH=shared python stages/06-domain-graph/eval/run_eval.py --db PATH [--out results.json]

The expected labels were written by Claude (2026-11-23), one plain sentence per field; they are a working test set,
not owner-approved ground truth. Several sectors are allowed where a field honestly spans two (e.g. 54;92 for law).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import kuzu

from nych3.taxonomy.resolve import resolve

HERE = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default=str(HERE / "results.json"))
    a = ap.parse_args()
    conn = kuzu.Connection(kuzu.Database(a.db, read_only=True))
    rows = list(csv.DictReader(open(HERE / "sentences.tsv", encoding="utf-8"), delimiter="\t"))
    out, tally = [], {"sector@1": 0, "sector@3": 0, "cip@1": 0, "cip@3": 0, "unresolved": 0}
    for r in rows:
        res = resolve(conn, r["text"], k=3)
        if "sectors" not in res:
            tally["unresolved"] += 1
            out.append({**r, "unresolved": True})
            continue
        sec = [s["id"].split(":", 1)[1] for s in res["sectors"]]
        cip = [s["id"].split(":", 1)[1] for s in res["study_areas"]]
        es, ec = r["expected_sectors"].split(";"), r["expected_cip"].split(";")
        hit = {"sector@1": sec[:1] and sec[0] in es, "sector@3": any(s in es for s in sec[:3]),
               "cip@1": cip[:1] and cip[0] in ec, "cip@3": any(c in ec for c in cip[:3])}
        for k, v in hit.items():
            tally[k] += bool(v)
        out.append({"field": r["field"], "text": r["text"], **{k: bool(v) for k, v in hit.items()},
                    "sectors": [(s["title"], s["terms"]) for s in res["sectors"][:3]],
                    "industry_groups": [(s["title"], s["terms"]) for s in res["industry_groups"][:3]],
                    "professions": [p["title"] for p in res["professions"][:3]],
                    "study_areas": [s["title"] for s in res["study_areas"][:3]],
                    "terms": [t["term"] for t in res["terms"]], "off_context": res["off_context"],
                    "expected_sectors": es, "expected_cip": ec})
    n = len(rows)
    summary = {"n": n, **{k: f"{v}/{n}" for k, v in tally.items()}}
    Path(a.out).write_text(json.dumps({"summary": summary, "results": out}, indent=1, ensure_ascii=False))
    print(json.dumps(summary))
    for o in out:
        if not o.get("sector@1") or not o.get("cip@1"):
            print(f"- {o['field']}: sector@1={o.get('sector@1')} cip@1={o.get('cip@1')} got {o.get('sectors')} | {o.get('study_areas')}")


if __name__ == "__main__":
    main()
