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

### Deviation 2a (2026-11-03, about 10:10 PM EST, before any experiment data)
- **What happened:** a smoke call produced no data. gemini-3.1-flash-lite and gemini-3.8-flash both returned HTTP 503 ("high demand").
- **New subjects:** **gemini-3.5-flash-lite** (cheaper) and **gemini-3.6-flash** (stronger).
- **New grader:** **gemini-3-flash-preview**, still a different model from both subjects.
- **Free tier:** all three are free of charge on the free tier.
- **Overload errors:** 503s now back off from 15 s up to 300 s and retry, because they're transient and not quota errors.

### Deviation 2b (2026-11-03, about 10:35 PM EST, before any data in the analysed run)
- **What happened:** the free tier allows only **20 requests per day per model** for the Gemini 3.x Flash models (quota `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, value 20). The 2a grader ran out after 17 records.
- **Pilot data excluded:** those 17 records are kept in `E3/results_pilot_2a/` and left out of the analysis.
- **New subjects (same free API):** **gemma-4-26b-a4b-it** (cheaper, MoE) and **gemma-4-31b-it** (stronger).
- **New grader:** **gemini-3.5-flash-lite**. It's a different model family from the subjects (Gemini vs Gemma) but from the same provider.
- **Batched grading:** each grader call grades the 3 answers for one (subject, task) together. The answers are anonymized as X/Y/Z in random order, and the grader is told to grade each one independently against the gold. This cuts grader calls by 3×.
  - Risk: the grader may score the answers relative to each other. That's stated as a caveat.
- **Run order:** steps mode runs first for all tasks; next-action mode runs only if quota remains.
- **Quota handling:** per-minute free-tier 429s wait for the server's `retryDelay`. Daily-quota 429s stop the run, which resumes the next day (quotas reset at midnight Pacific, 3:00 AM EST).
- **Output directory:** `E3/results_v2b/`.

---

## E3b addendum: non-computer physical tasks, observe-and-assist framing (PRELIMINARY)

Written 2026-11-04 at about 12:55 AM EST, **before any E3b model call**. It doesn't change E3. Builder: `tools/e3b/build_e3b.py`. Runner: `tools/e3b/run_e3b.py`. Worker: `tools/e3b/worker_e3b.sh`. Data: `REVIEW/experiments/E3b/`.

**Status: PRELIMINARY.** This is an exploratory pilot of a redesigned test. It's free tier only, with $0 spend; the shared ledger `E3/cost_ledger.json` must stay at $0.00, and the hard cap stays $20 total.

### Purpose and use framing
- **Civilian uses only:** assistive robotics, accessibility, elder-care help and ergonomics. The intended system watches a person doing an everyday physical task, matches a TOTE loop, and uses physical-capability factors to decide where to offer help.
- **Hypotheses, not judgments:** ability predictions only guide offers of help. They are never a judgment of the person.
- **No protected-trait proxies:** profiles hold physical capability only (height, weight, reach, grip, lift, tremor, dexterity, hands available, heat sensation, near vision, standing tolerance, balance, gait, posture). They contain no age, sex, race, disability label or other protected trait.
- **Synthetic profiles:** every profile is **synthetic**, labelled `SYNTHETIC: true` with an explicit note, and is not a real person.

### Tasks
- **Count:** 77 tasks in `E3b/tasks.jsonl`, built deterministically (seed 31): **48 cooking**, **16 woodworking** and **13 knitting/crochet**.
- **Source:** the only non-computer sources harvested in the Kuzu store, all public-domain Project Gutenberg books:
  - #65061 *Boston Cooking-School Cook Book*
  - #71855 *Essentials of Woodworking*
  - #26113 *Handbook of Wool Knitting and Crochet*
  - #13510 *Knots, Splices and Rope Work* (0 tasks passed the filters)
- **Domains the store doesn't cover:** home repair, cleaning, first aid, car care, gardening and personal care. They aren't in the store yet and are **out of scope** until they're harvested.
- **One task** is one book section: a heading plus the harvested action sentences under it.
  - Section size is 3 to 8 steps, each at most 50 words.
  - At least 2/3 of the steps must have a NYCH-complete loop.
  - Titles are de-duplicated.
  - The heading is recovered from the cached Gutenberg HTML.
- **Reference steps:** the harvested action sentences, verbatim.
- **NYCH rule:** loops used anywhere (tasks or library) must have a modality operator, actor, action and object/tool cell. Senses are **input data**: observations report "modality cues sensed", never sensing as an action.
- **Observation (model input):** sensor-style lines for the first half of the steps. They give the motion consistent with the action lemmas, the objects in view, the tool in hand and the modality cues. The **task name is never given**.
- **Step requirements (rule-based keywords; table in the builder):** fine_motor, grip_force, lifting_load, bimanual, heat_hazard, sharp_tool, fine_vision, sustained_standing and balance_reach.
- **Profile limitations:** each profile has 0 to 3 limitations, mapped to the requirements by a fixed table.
- **Gold struggle steps:** the steps whose requirements hit one of the profile's limitations.
- **Gold completion bucket:** high (no struggle steps), medium (40% of steps or fewer) or low (more than 40%).

### Conditions (paired, randomized order per task)
- **A:** no loop.
- **B:** up to 3 retrieved loops.
- **C:** the same number of random NYCH-complete non-computer loops.
- **Loop wording:** in B and C the loops are labelled "may or may not be relevant".
- **Hold-out:** every loop grounded in the task's own section is removed from retrieval and from C. A loop is never rendered with a grounding sentence equal to any gold step.

### Retrieval fix (vs E3)
E3 matched the task title loosely against the loop name and text with TF-IDF and kept the top 1. B was often irrelevant, and in the interim GPT check of 20 items B scored .463 vs C .571 and A .665. E3b changes retrieval as follows:
1. Matching is on the loop's NYCH cells against the observation cues: object lemma (weight 2), tool (weight 1.5) and action lemma (weight 1), each IDF-weighted.
2. An **object or tool match is required**. If nothing matches, B gets no loop and C gets one loop (logged).
3. Only NYCH-complete loops (3,167 in the library) are eligible.
4. The top 3 must come from 3 **distinct source paragraphs**, so they aren't near-duplicates.
5. The retrieval score is logged per task (`B_score`). 76 of 77 tasks get at least one B loop.

### Outputs and scoring (rule-based, no LLM grader)
1. **Task identification:** the model ranks the top 5 of 20 candidate titles: the truth, up to 9 from the same domain and the rest from other domains (fixed per task). Scores: `identify_top1` and `identify_top5` (0/1).
2. **Ability:** the model is given the observation, the profile and the matched step list. It returns `struggle_steps` and a `completion_likelihood`.
   - Score = mean of (F1 of struggle steps vs gold, where both empty = 1) and (completion: exact = 1, adjacent = 0.5, else 0).

### Models and quota
- **Subjects:** gemma-4-26b-a4b-it and gemma-4-31b-it on the Gemini API free tier, temperature 0.
- **No grader:** scoring is rule-based, so no grader quota is used.
- **Spacing:** 12 s between calls, which is politer than E3's 6.5 s, because the quota is shared with the running E3 workers.
- **Quota handling:** a daily-quota stop sleeps until 3:10 AM EST and resumes. Transient errors retry after 10 min, up to 6 times. Any billing or non-free-tier signal stops the run.
- **Run order:** identification runs first for all tasks, then ability.

### Success rule and analysis
- **Success rule:** for each subject and metric, the loop helps only if the **B−C** paired bootstrap 95% CI lower bound is above 0 (10k resamples). B−A and C−A are reported.
- **Secondary:** results split by the B_score median.

### Known limitations, stated up front
- **Rule-derived gold:** the requirement tags and gold struggle steps come from keyword rules, not from human or biomechanical ground truth. That makes the ability metric a test of consistency with the rules.
- **Text only:** observations are synthesized from loop fields, not real sensor data.
- **Unbalanced domains:** cooking dominates.
- **Step list in the ability prompt:** the ability prompt reveals the true step list, which separates ability from identification.
- **Restricted material:** none of the unpublished MG8 layer, defense or DARPA material is used, and the E3 FORBIDDEN guard is applied to every prompt.

#### E3b deviation 1 (2026-11-04, about 12:50 AM EST, before any scored E3b data)
- **What happened:** the first 2 calls returned empty text. Gemma 4's default thinking used 1.2k to 4k tokens and never emitted an answer.
- **Data discarded:** those records were deleted.
- **Fix:** E3b now sends `thinkingLevel: minimal` for Gemma, with a 400-token answer budget. A test call returned valid JSON.
- **E3 untouched:** E3 code and its runs are not changed.

---

## E3c addendum: run-to-run consistency / auditability (PRELIMINARY)

Written 2026-11-04 at about 1:10 AM EST, **before any E3c model call**. Runner: `tools/e3c/run_e3c.py`. Worker: `tools/e3c/worker_e3c.sh`. Output: `REVIEW/experiments/E3c/results_prelim/`.

**Question:** given the same loop, does the model keep giving the same answer while the no-loop answer changes? Hypothesis: **B is more stable than A and C**.

### Tasks (10, hand-picked where the B match is semantically solid)
**Computer (E3), with the B loop for each:**
- **E3-105** Samsung, check for software updates: `SET_UPDATE`
- **E3-167** Google Account, sign out of someone else's device: `ACC_SIGN_OUT`
- **E3-012** Drive/Android, automatically back up your device: `SET_BACKUP`
- **E3-066** Docs, permanently delete all files in trash: `FILE_DELETE`
- **E3-009** Android, find AICore updates: `SET_UPDATE`

**Physical (E3b), each with 3 retrieved loops:**
- **E3b-050** Vol-au-vents
- **E3b-020** Miter joint
- **E3b-057** Stuffed onions
- **E3b-070** Stewed mushrooms
- **E3b-071** Broiled venison steak

**Loop contexts:** B and C are the fixed loops already assigned by the E3 and E3b runs. They're identical across the 20 repeats.

### Design
- **Model:** **gemma-4-31b-it** on the Gemini free tier, $0 spend, hard cap $20 total. Its E3 worker is stopped (taken as is, not restarted), so its quota is the least contended.
- **Sampling:** **temperature 0.7** for every condition, other settings default, minimal thinking, 600-token answers.
- **Repeats:** **20 per condition** (A, B, C), so 10 × 3 × 20 = 600 calls. Repeats are interleaved, so a partial run stays balanced.
- **Prompt:** the E3 steps prompt. Physical tasks give the task name directly; E3c tests stability, not identification.
- **Spacing:** 15 s between calls, the politest of the three runs.
- **Resuming:** the run is resumable and detached. A daily-quota stop resumes at 3:10 AM EST.

### Metrics (all rule-based, computed per task and condition over the 20 answers)
1. **Pairwise step-set Jaccard:** steps are content-word bags (stemmed, stopwords removed). Two steps match if their token Jaccard is at least .3 (greedy alignment). Score = matched / (|A| + |B| − matched). This is the **primary** metric.
2. **Pairwise order agreement:** the fraction of concordant matched pairs.
3. **Distinct answers:** the number of distinct canonicalized step lists.
4. **Spread:** variance of the gold score and SD of the step count.
5. **Gold score:** gold coverage (token Jaccard of at least .2) minus 0.1 per invented step.
6. **Invented-step rate:** the share of answer steps that share less than 10% of their tokens with every gold step. This is a crude proxy.

### Success rule
- **Primary:** B is more stable only if the paired-over-tasks bootstrap 95% CI (10k resamples) lower bound is above 0 for **both** B−A and B−C on pairwise step-set Jaccard.
- **Secondary:** the other metrics are descriptive. With n = 10 tasks, this is a pilot.

### Caveats
- **Lexical similarity:** the metrics compare words, not meaning.
- **Selected tasks:** the tasks were chosen for good B matches, so they favour B by design.
- **Verbatim copying:** a loop can make answers stable simply because the model copies it word for word. Stability isn't correctness, so the gold score is reported alongside.
