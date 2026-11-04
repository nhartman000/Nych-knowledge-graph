# E3 pre-registration: do NYCH TOTE loops help a model on how-to tasks?

Committed 2026-11-03 before any model call. No paid calls have been made. Any change after this commit will be logged as a deviation in E3_RESULTS.md.

## Question
Does giving a model a retrieved NYCH TOTE loop improve its how-to answers **more than giving it an unrelated loop of the same length**?

## Tasks
- **Count:** 180 held-out tasks in `REVIEW/experiments/E3/tasks.jsonl`, built by `tools/e3/build_tasks.py` (deterministic, seed 3).
- **Source:** ordered (ol) step lists from official public help pages in `shared/data/tech_ui/ui_actions.jsonl.gz`. The pages cover Google products, Microsoft, Copilot, Apple, Samsung and Claude, capped at 13 tasks per site.
- **Held out:** a task's page URL never appears among the sources or candidates of any core loop (457 URLs excluded).
- **Filters:** a task has 3 to 8 steps and no truncated quotes.
- **Gold:** the verbatim step quotes. The success criteria are listed per task.
- **Next-action variant:** the model sees the first half of the gold steps, and the gold answer is the following step.
- **Restricted material:** none of the MG8 layer, the defense plan, DARPA material or roadmaps is used. The runner refuses any prompt matching those terms.

## Conditions (within-task, paired)
- **A:** the model alone.
- **B:** the model plus the top-1 core loop. It's retrieved by IDF-weighted lexical overlap between the task title and the loop name, category, object, action and operate text, from the 88 core loops.
- **C:** the model plus a random core loop other than B, drawn from the 5 loops closest to B in word length (seed 3).
- **Loop wording:** in B and C the loop is labelled "Reference material (may or may not be relevant)".
- **Order:** the order of the conditions is randomized per task.
- **Provisional loops:** the 105k provisional Kuzu loops are **not** used in the primary analysis.

## Models
- **Subjects:** for each provider with a key, a cheap model and a strong model: OpenAI gpt-4o-mini and gpt-4o, and Anthropic claude-3-5-haiku and claude-sonnet-4-5.
- **Settings:** temperature 0.
- **Grader:** always a strong model from the *other* provider (gpt-4o grades Anthropic answers, and claude-sonnet-4-5 grades OpenAI answers). The grader never sees the condition or the loop.
- **Keys:** both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are required. If a model name is unavailable, the nearest current tier is substituted and logged.

## Outcomes
- **Primary:** the step-mode rubric score in [0,1]. It's correct gold steps divided by the number of gold steps, minus 0.1 per wrong or invented step, with a floor of 0.
- **Rubric fields:** correct steps, missing steps, wrong or invented steps, and safe stopping.
- **Secondary:**
  - next-action score (0, 0.5 or 1);
  - wrong or invented steps per answer;
  - safe-stopping rate;
  - B-C on the subset where the retrieval score is at or above the median.

## Success rule (decided in advance)
Loops "help" for a given subject model only if the **mean B−C** paired difference in primary score is positive **and** its paired bootstrap 95% CI (10,000 resamples, seed 0) excludes 0.
- **B vs A:** reported, but it cannot establish a gain on its own.
- **Overall:** loops help if the rule holds for at least one model. Results are reported for every model, with no selective reporting.

## Statistics
- **Reported for B−C, B−A and C−A:** means per condition, paired bootstrap 95% CIs and win/tie/loss rates.
- **Multiple comparisons:** none are corrected for, because there are 4 models × 2 modes. This is stated as a caveat.
- **Unparseable grades:** dropped. The count is reported.

## Grader check
I (the agent) blindly hand-score 30 random step-mode answers from `handcheck_blind.jsonl`, with the condition hidden. Agreement with the grader is reported as Spearman ρ and mean absolute difference. If ρ < 0.6, the result is flagged as low-trust.

## Cost
Estimated under $20 in total. The actual token-based cost is logged in `summary.json`.

## Known limitations, stated in advance
- The 88 loops each describe a single generic function, while the tasks are product-specific, multi-step procedures. B often retrieves a loosely related loop, so a null result is plausible.
- The gold steps are scraped quotes and may be incomplete.
- The same family of model that wrote parts of the pipeline is also being tested.

## Reproduce
```
PYTHONPATH=shared /workspace/kgenv/bin/python tools/e3/build_tasks.py
/workspace/kgenv/bin/python tools/e3/run_e3.py --dry-run --limit 20   # mock models, no network
/workspace/kgenv/bin/python tools/e3/run_e3.py --limit 5              # paid smoke test
/workspace/kgenv/bin/python tools/e3/run_e3.py                        # full run
```

## Deviation 1 (2026-11-03, 9:15 PM EST, committed before any paid call)
- **Why:** there's no Anthropic API key (`ANTHROPIC_API_KEY` on the box is a copy of the OpenAI key), so Anthropic is replaced by Google Gemini.
- **Subjects:** OpenAI **gpt-4.1-mini** (cheap) and **gpt-4.1** (strong); Gemini **gemini-3.5-flash-lite** (cheap) and **gemini-3.8-flash** (strong).
- **Model choice:** gpt-4o and gpt-4o-mini were swapped for the gpt-4.1 tier, which is cheaper per unit of quality and still non-reasoning, so temperature 0 holds. gemini-2.5-* is deprecated, so the current Gemini models are used.
- **Graders (cross-provider and blind):** **gemini-3.8-flash** grades the OpenAI answers, and **gpt-4.1** grades the Gemini answers.
- **Gemini settings:** temperature 0 and `thinkingLevel: low`. Thinking tokens are billed as output.
- **Prices:** USD per 1M input/output tokens, verified 2026-11-03 on the providers' pricing pages.

  | Model | Input | Output |
  | --- | --- | --- |
  | gpt-4.1-mini | 0.40 | 1.60 |
  | gpt-4.1 | 2.00 | 8.00 |
  | gemini-3.5-flash-lite | 0.30 | 2.50 |
  | gemini-3.8-flash | 0.75 | 3.75 (promo price through 2026-12-31) |

- **Cost cap:** **$20 total across both providers, including grading and the smoke test.** It's enforced as a combined running total in `REVIEW/experiments/E3/cost_ledger.json`. The runner stops before any call pair whose pessimistic cost would push the total over $20. If the cap cuts the run short, the analysis covers only tasks with all three conditions complete, and that is reported.
- **Unchanged:** tasks, conditions, rubric, success rule and statistics.

## Deviation 2 (2026-11-03, about 10:00 PM EST, committed before any experiment call). Status: PRELIMINARY
- **Why:** the OpenAI account has no credits, and there's no budget for any paid API. E3 runs on **Google Gemini only, on the free tier, with zero spend.**
- **Free tier verified (zero cost):** a 1-token call to a paid-only model (gemini-3.1-pro-preview) returned `generate_content_free_tier_* limit: 0`, which shows the key's project is on the free tier.
- **Subjects (all "Free of charge" on the free tier):**
  - **gemini-3.1-flash-lite** (cheaper);
  - **gemini-3.8-flash** (stronger).
- **Grader:** **gemini-3.6-flash**, a different model from both subjects. It never sees the condition or the loop, and is temperature 0. **It replaces the strong cross-provider graders of Deviation 1.**
- **Weakness stated up front:** the grader comes from the same provider and model family as the subjects, so it may share their blind spots or favour their style. Results are labelled **PRELIMINARY**.
- **Throttling:** at most one call per 6.5 s per model.
  - Calls are ordered steps-mode first, interleaved across tasks and subjects, so a partial run stays balanced.
  - Per-minute free-tier 429s wait 65 s and then retry.
  - These stop the run without retrying: daily quota exhausted, any out-of-credit or billing error, and any Gemini quota error **not** tagged `free_tier` (a possible billed tier).
  - The run is resumable from `results/raw.jsonl`.
- **Partial runs:** if daily quotas stop the run, results are reported for the tasks completed, with n, and the run resumes the next day.
- **Hand check (30 items, blind):** done by the agent. It is reported **as grader agreement only**, not as primary grading.
- **Cross-provider check (added on request):** a blinded packet of about 60 step-mode answers (20 per condition, shuffled, condition hidden) goes in `E3/gpt_chat_packet/`, in 3 chunks with a strict JSON rubric. Nick will have GPT grade it by hand in its chat app.
  - The key is `E3/gpt_chat_key_SECRET.json`, kept outside the packet.
  - `tools/e3/gpt_packet.py ingest` computes GPT-vs-Gemini grader agreement.
  - This is a check on the grader, not primary grading.
- **Unchanged:** tasks, conditions, rubric, success rule (B−C 95% CI > 0) and statistics.
