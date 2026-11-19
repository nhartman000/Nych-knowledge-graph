# Recorded results (2026-11-19, ET)

Inputs: the 3 bundled sources (`pg_verifybackup`, `pg_checksums`, `original_release_check_sop`), 5 reruns each.
Pipeline: `python demo/run_demo.py --runs 5`. Baseline: `gemini-3.1-flash-lite-preview` (Google), temperature 0, same
schema, 5 calls per source, raw outputs in `baseline_raw_gemini-3.1-flash-lite-preview.json`; scored with
`python demo/run_demo.py --runs 5 --baseline-raw demo/results/baseline_raw_gemini-3.1-flash-lite-preview.json`.

| Metric (15 runs, 3 sources) | Pipeline (deterministic, no model) | Baseline (plain model, JSON) |
| --- | --- | --- |
| Runs that parse and match the schema | 15 / 15 | 15 / 15 |
| Sources with identical output on all 5 reruns | 3 / 3 | 3 / 3 |
| Steps traceable (cited lines exist, quote verbatim) | 45 / 45 | 45 / 45 |
| Steps with a machine-checkable exit check that compiles to a gate | 30 / 45 | 30 / 45 |
| Numeric limits not present in the cited lines | 0 | 0 |
| API errors (excluded) | 0 | 0 |

## Honest reading

* **On these metrics and these three tiny inputs, a plain modern model ties the deterministic pipeline.** The demo does
  not show that the pipeline extracts better. Do not claim it does.
* The baseline's 5 reruns were identical, but that was one burst of calls at temperature 0 on one day; model versions
  and serving can drift. The pipeline is identical by construction (same code, same input).
* Not scored, looked at by hand (first baseline run; all 5 were identical): for `pg_verifybackup` the baseline omitted
  the `pg_basebackup` command line (line 9); for `pg_checksums` it created a step from the option description
  "--enable Enables checksums." (line 10-11), which is not an instruction; on the SOP it merged lines 6-8 into one step.
  The pipeline skipped line 6 ("Run the unit tests before tagging a release.") as unmapped and listed it. Neither is
  graded for correctness, and with three sources this is an anecdote, not a result.
* What the pipeline does that a JSON-only model call does not: runs offline for free, labels each check's basis
  (`source_stated` / `convention_default` / `human_judgement`), reports unmapped lines, and its output feeds mg8-runtime
  gates and hash-chained logs directly. The audit/gating layer is the product difference, not the extraction.
* A first baseline attempt with `gemini-3-flash-preview` was cut short by the free tier's 20-requests-per-day limit
  (HTTP 429); those partial outputs are not used. Rate-limit errors are excluded from metrics and reported separately.
* The earlier run used a stricter traceability rule (quote must sit inside a single cited line) and scored the baseline
  35 / 45, because it joined several lines into one quote. The rule was relaxed to accept quotes spanning the cited
  lines; the numbers above use the relaxed rule.
