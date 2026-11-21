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
python demo/run_demo.py --all-sources        # all 10 public procedures (3 bundled + 7 fetched)
pytest -q tests/demo                          # 24 tests, offline
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
* Ten sources are bundled (PostgreSQL 18 docs under the PostgreSQL License, a Python tutorial page, three FEMA
  Ready.gov pages, and one original SOP). `demo/tools/build_sources.py` rebuilds the 7 fetched ones and records
  provenance. On long or messy text the rules fall down: `pg_continuous_archiving` yields 3 steps and `python_venv`
  turns sample terminal output into dozens of bogus `$` steps (see `results/RESULTS.md`).
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

## Bigger baseline: 10 sources, two model settings, step recall

```sh
export GEMINI_API_KEY=...        # or OPENAI_API_KEY=... (read from the environment only; never written to a file)
python demo/run_demo.py --all-sources --compare --model gemini --runs 3 --temperature both   # default flash-lite model
python demo/run_demo.py --all-sources --compare --model openai --runs 3 --temperature both   # default gpt-4.1-mini
python demo/run_demo.py --all-sources --runs 3 --baseline-raw demo/results/benchmark_baseline_raw_gemini-3.1-flash-lite-preview.json   # re-score saved outputs, no model call
python demo/tools/make_report.py                                                              # demo/results/report.html
```

* `--model gemini|openai`, `--model-name ID`, `--temperature 0|default|both` ("default" omits the parameter).
* **Step recall** uses `demo/gold/*.json`: for 6 sources, a list of the real steps with the source lines that state
  them. **The gold lists were written by an AI assistant, not a human expert**; treat recall as indicative until a
  person reviews them. Matching is mechanical: a gold step is covered when a produced step cites at least one of its
  lines; a produced step is "spurious" when it cites no gold line.
* OpenAI path: implemented and unit-tested against a mock server. Not yet run for real because the key supplied on
  2026-11-19 had no API credit (every completion returned HTTP 429 `insufficient_quota`); the report shows PENDING.
* `demo/results/report.html` is a single offline file: procedure beside checklist with quotes, gate outcomes under
  three scenarios, a tamper test (three edits, all caught) and the comparison table.

## Edge-device footprint benchmark ("gumball machine")

```sh
pip install -r demo/edge_bench/requirements.txt      # numpy + torch; plus nych-language-model (see that file)
python demo/run_edge_benchmark.py                     # trains a clearly labelled PLACEHOLDER model if no weights
python demo/run_edge_benchmark.py --package <D16 dir> # real trained weights (or NYCH_WEIGHTS=<dir>)
pytest -q tests/demo/test_edge_bench.py
```

Measures installed footprint (code, symbol tables, gate files, weights as float32 / int8 / 4-bit), peak memory,
seconds per procedure for the checklist pipeline, and model load and per-token latency, under two simulated device
profiles (1 CPU / 512 MB, 4 CPUs / 1 GB), with weights fully in RAM or memory-mapped from a simulated SD card.
Includes a NumPy-only runtime for the V1 decoder (`demo/edge_bench/npdecoder.py`) so a device needs no PyTorch.
Results: `results/edge-footprint.md` / `.html` / `.json`. Constraints are simulated on x86; see the page for how.
