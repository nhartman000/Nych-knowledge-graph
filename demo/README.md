# Procedure → checklist → gated audit log (demo)

A short public procedure goes in. A checklist of T.O.T.E. (Test–Operate–Test–Exit) steps comes out, each with
**exit checks a machine can evaluate**, a **source line number and verbatim quote**, and a **hash-chained audit
log** written by [mg8-runtime](https://github.com/nhartman000/mg8-runtime) gates and single-use permits.

No model call and no API key are needed for the demo. A plain-model **baseline** is included and optional.

## Run it

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r demo/requirements.txt          # this repo's requirements + mg8-runtime (Python 3.11+)
python demo/run_demo.py                       # deterministic demo, all-pass scenario
python demo/run_demo.py --scenario one-fails  # a failing exit check: FAIL, nothing committed
python demo/run_demo.py --scenario evidence-missing   # no evidence: INTERMEDIATE, nothing committed
python demo/run_demo.py --compare --runs 5    # also run the plain-model baseline (needs GEMINI_API_KEY)
pytest -q tests/demo                          # 17 tests, offline
```

Outputs go to `demo/output/` (git-ignored): `<source>.checklist.json`, `audit/<source>/*.qson` (one hash chain per
step), `audit/<source>/audit_manifest.json`, `summary.json`.

## What is real and what is simulated

| Part | Status |
| --- | --- |
| Checklist from source text | Real, deterministic, offline. Uses the existing `nych3` encoder plus the documented rules in `procedure_demo/checklist.py`. |
| Exit checks compiled to G8SON gates | Real. Gate evaluation, permits, commit and QSON log come from mg8-runtime unchanged. |
| Evidence that the checks run against | **Simulated.** The demo does not execute `pg_verifybackup` etc. `--scenario` generates observed values (exit status, stdout empty, measured number, human sign-off). Replace `audit.make_evidence` with real collectors to use it for real. |
| "Signed" log | **Hash-chained, not signed.** Tampering is detected (`audit.verify_audit`, tested), but there is no key, so it proves integrity, not who wrote it. |

Exit-check types: `exit_code_equals`, `stdout_empty`, `numeric_at_most` (tool evidence), `human_review` (human
evidence). A tool check fed human-provenance evidence does not pass (tested). Each check is labelled
`source_stated`, `convention_default` (e.g. "exit status 0 means success" when the source does not say so) or
`human_judgement`. Lines the rules cannot place are listed in `unmapped_lines`, never dropped silently.

## Known limits (read before showing anyone)

* The existing `nych3` encoder was tuned on cookbooks. On technical manuals it recognises few imperatives, so the
  demo adds a handful of regex rules (shell lines, "exit status is zero if", "do not print anything when",
  "must not be higher than N unit"). These work on the bundled sources; they are not a general parser.
* Only 3 small sources are bundled (two PostgreSQL 18 doc excerpts under the PostgreSQL License, plus one original
  SOP written for this demo). Counts below say nothing about large or messy documents.
* The metrics measure mechanical properties. They do **not** measure whether each step is *correct*; that needs
  human grading.

## Baseline and metrics

`procedure_demo/baseline.py` asks a plain model (Gemini, temperature 0) for the same checklist as JSON using the same
schema, then both producers are scored by `procedure_demo/compare.py`:

1. **Schema validity**: output parses and validates against `CHECKLIST_SCHEMA`.
2. **Determinism**: distinct canonical outputs across N reruns of the same input (1 = fully reproducible).
3. **Traceability**: step cites existing source lines and its `source_quote` is a verbatim substring of them.
4. **Runnable exit checks**: step has at least one machine-type check that compiles into a valid gate.
Also reported: numeric limits that do not appear in the cited lines (invented thresholds). API errors (e.g. rate
limits) are reported separately and excluded from every metric.

Results from the run recorded on 2026-11-19 are in `results/RESULTS.md`.
