#!/usr/bin/env python3
"""One-command procedure -> checklist -> gated audit log demo, plus optional baseline comparison.

  python demo/run_demo.py                       # deterministic demo on the bundled sources, no key needed
  python demo/run_demo.py --compare --runs 5    # also run the plain-model baseline if GEMINI_API_KEY is set
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "shared"))

from procedure_demo import audit, baseline, compare  # noqa: E402
from procedure_demo.checklist import build_checklist  # noqa: E402
from procedure_demo.common import canonical  # noqa: E402

DEFAULT_SOURCES = ["pg_verifybackup.txt", "pg_checksums.txt", "original_release_check_sop.txt"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", action="append", help="procedure text file (repeatable); default: bundled sources")
    ap.add_argument("--out", default=str(HERE / "output"), help="output directory (default demo/output)")
    ap.add_argument("--scenario", default="all-pass", choices=audit.SCENARIOS,
                    help="simulated evidence for the gate run (default all-pass)")
    ap.add_argument("--compare", action="store_true", help="also run the plain-model baseline (needs GEMINI_API_KEY)")
    ap.add_argument("--baseline-raw", help="re-score saved baseline outputs (JSON {source: [raw,...]}) without calling a model")
    ap.add_argument("--runs", type=int, default=5, help="reruns per source for determinism metrics (default 5)")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.source] if args.source else [HERE / "sources" / n for n in DEFAULT_SOURCES]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names = {p.stem: p for p in paths}
    summary = {"scenario": args.scenario, "sources": {}}

    pipeline_runs = {}
    for name, path in names.items():
        runs = [build_checklist(path) for _ in range(args.runs)]
        pipeline_runs[name] = runs
        cl = runs[0]
        (out / f"{name}.checklist.json").write_text(json.dumps(cl, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        manifest = audit.run_audit(cl, args.scenario, out / "audit" / name)
        ok, problems = audit.verify_audit(out / "audit" / name)
        outcomes = [r["outcome"] for r in manifest["results"]]
        summary["sources"][name] = {
            "steps": len(cl["steps"]), "unmapped_lines": len(cl["unmapped_lines"]),
            "outcomes": {o: outcomes.count(o) for o in sorted(set(outcomes))},
            "audit_chain_verified": ok, "audit_problems": problems,
            "checklist_sha256": cl["checklist_sha256"]}
        print(f"\n== {name}: {len(cl['steps'])} steps, {len(cl['unmapped_lines'])} unmapped lines "
              f"(scenario: {args.scenario}, evidence SIMULATED)")
        for step, res in zip(cl["steps"], manifest["results"]):
            checks = ",".join(c["type"] for c in step["exit_checks"])
            print(f"  {step['step_id']:<5} {res['outcome']:<12} committed={str(res['committed']):<5} "
                  f"machine_checkable={str(res['machine_checkable']):<5} [{checks}]  {step['tote']['operate'][:60]}")
        print(f"  audit log: {len(manifest['results'])} hash-chained QSON files, independent verification: "
              f"{'OK' if ok else 'FAILED ' + str(problems)}")

    pipe = compare.summarize(pipeline_runs, names)
    summary["pipeline_metrics"] = pipe["total"]
    print("\npipeline metrics:", json.dumps(pipe["total"], sort_keys=True))

    if args.baseline_raw:
        raw = json.loads(Path(args.baseline_raw).read_text())
        base = compare.summarize({k: v for k, v in raw.items() if k in names}, names)
        summary["baseline"] = {"rescored_from": args.baseline_raw, **base}
        print("\nbaseline (re-scored from saved outputs):", json.dumps(base["total"], sort_keys=True))
    elif args.compare:
        if not baseline.have_key():
            print("\nBASELINE PENDING: GEMINI_API_KEY is not set, so the plain-model comparison was not run. "
                  "No baseline numbers are reported.")
            summary["baseline"] = "PENDING (no model key)"
        else:
            model = __import__("os").environ.get("BASELINE_MODEL", baseline.DEFAULT_MODEL)
            raw = {}
            for name, path in names.items():
                print(f"  baseline: {name} ...", flush=True)
                raw[name] = baseline.run_baseline(path, args.runs)
                print(f"  baseline: {name} done ({sum(x.startswith('ERROR:') for x in raw[name])} API errors)", flush=True)
            (out / "baseline_raw.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False) + "\n")
            base = compare.summarize(raw, names)
            summary["baseline"] = {"model": model, "temperature": 0, "runs_per_source": args.runs, **base}
            print(f"\nbaseline ({model}, temperature 0, {args.runs} runs/source):",
                  json.dumps(base["total"], sort_keys=True))
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(f"\nwrote {out}/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
