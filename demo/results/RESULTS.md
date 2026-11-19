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


---

# Bigger run, 2026-11-19 (10 sources, 3 reruns, two temperatures)

Model: `gemini-3.1-flash-lite-preview` (a small, cheap model on a free-tier key; cost about $0). **OpenAI: not run** (key
accepted but no API credit; every completion returned HTTP 429 `insufficient_quota`). Raw outputs:
`benchmark_baseline_raw_gemini-3.1-flash-lite-preview.json`; scores: `benchmark_summary_2026-11-19.json`;
visual: `report.html`. 30 runs per setting, no API errors.

| Measure | Pipeline | Model, temp 0 | Model, default temp |
| --- | --- | --- | --- |
| Schema-valid outputs | 30/30 | 30/30 | 30/30 |
| Sources with identical output on every rerun | 10/10 | 10/10 | **0/10** |
| Steps whose quote is verbatim in the cited lines | 588/588 (100%) | 105/114 (92%) | 107/115 (93%) |
| Steps with a machine-runnable exit check | 273/588 (46%) | 66/114 (58%) | 66/115 (57%) |
| Numeric limits not in the cited line | 0 | 9 | 8 |
| Gold steps covered (6 sources, sums over reruns) | 129/186 (69%) | 66/186 (35%) | 66/186 (35%) |
| Produced steps matching no gold step | 147/342 (43%) *(before the noise fix; see the section below)* | 0/66 (0%) | 0/66 (0%) |

Gold lists: hand-made by an AI assistant, not a human (see `gold/*.json`). Recall is line-overlap based.

Where the pipeline wins: it covers about twice the gold steps (69% vs 35%) on the long procedures (pg_upgrade 39/60
vs 15/60; ready_power_outages 36/63 vs 12/63; python_venv 27/33 vs 12/33), never cites a line that does not support a
step, never invents a number, and gives the same output every time at any setting.

Where the model wins or ties: at temperature 0 the same small model was also schema-valid and 100% reproducible
on these inputs (the earlier "determinism" gap only appears at default temperature). The model has zero spurious
steps; the pipeline has 43% (python_venv: 123 of 159 steps are bogus, mostly sample terminal output read as commands;
pg_upgrade 21 of 111). The model beat the pipeline on pg_checksums (9/9 vs 6/9) and tied on the original SOP. It
produces more machine-runnable checks per step (58% vs 46%), but 8-9 of its numeric limits do not appear in the cited
line, and 7-9% of its quotes are not verbatim. On `pg_continuous_archiving` (long, prose-heavy) the pipeline found
only 3 steps (no gold list for this one; the model also found 3).

What this does and does not show: it does not show better semantic accuracy than a strong model; only one small
model was tested. The defensible claim is reproducibility and traceability by construction, plus the gate/audit
layer that the plain model has no equivalent of.


---

# Noise-fix run, 2026-11-19 (pipeline rules-2; same 10 sources, 3 reruns, two temperatures)

Change: the pipeline no longer turns sample terminal output into steps. Four filters, all in `checklist.py`: (1) plain
`$ ` lines that follow an echoed prompt (`$ (env) $ cmd`) in the same block are sample output; (2) interpreter
sessions (`>>>`, `...`) are not shell commands; (3) a command ending in a backslash is joined with its continuation
line; (4) cross-reference/scope notes ("see Section 19.2", "not covered here") are not actions. Skipped lines are listed
in `unmapped_lines` with a reason, never silently dropped. A second, separate commit adds one recall rule: sentences
with explicit obligation wording ("you should", "it is important that", "you are advised to") become review steps.
The model side was re-run live (fresh calls, no API errors); its numbers are within noise of the first run.

| Measure | Pipeline before | Pipeline after | Model, temp 0 | Model, default temp |
| --- | --- | --- | --- | --- |
| Steps whose quote is verbatim in the cited lines | 588/588 (100%) | 507/507 (100%) | 105/114 (92%) | 113/121 (93%) |
| Numeric limits not in the cited line | 0 | 0 | 9 | 8 |
| Gold steps covered | 129/186 (69%) | 132/186 (71%) | 66/186 (35%) | 68/186 (37%) |
| Produced steps matching no gold step | 147/342 (43%) | 33/228 (14%) | 0/66 | 0/66 |
| Steps with a machine-runnable exit check | 273/588 (46%) | 153/507 (30%) | 66/114 (58%) | 66/121 (55%) |
| Identical output on every rerun | 10/10 | 10/10 | 10/10 | 0/10 |

* The filters alone give 27/219 spurious (12%) with recall unchanged at 129/186 (69%). The obligation rule adds 3
  recall points (132/186) but also 6 more spurious steps; drop the second commit if you prefer the cleaner list.
* python_venv: 159 steps over 3 runs down to 48 (spurious 123 down to 36). pg_upgrade: 111 down to 105 (spurious 21 down to 15).
* The share of machine-checkable steps fell from 46% to 30% because most of the "commands" removed were sample output
  that had been given a fake exit-code check. The remaining machine checks are real commands.
* `pg_continuous_archiving` (no gold list): 3 steps before, 12 after. The 3 old ones were two configuration lines and one
  expanded example; the new ones are mostly "you should / it is important that" requirements. By eye about half are
  real requirements; the rest are explanatory sentences. It is still not a step-by-step procedure, so this is a
  modest gain, not a fix.
* Still spurious by the gold lists: a few real commands that the gold author left out (`$ (env) $ python`, the tablespace
  `rsync`), and advisory sentences ("Do not start any servers yet", "Avoid carbon monoxide poisoning").
* Same caveats as before: gold lists written by an AI assistant, one small model, simulated gate evidence.
