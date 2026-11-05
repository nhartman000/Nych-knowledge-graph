# E3 results: INTERIM and PRELIMINARY (snapshot 2026-11-05, about 12:03 PM EST)

> **Status: incomplete.** The free-tier run (Deviation 2b) is still going. About **28 of the 180 tasks** have all three step-mode conditions graded so far (**26 for gemma-4-26b-a4b-it and 2 for gemma-4-31b-it**). Next-action mode has 1 task per model. **No conclusion can be drawn yet.** This file will be replaced when the run finishes.

## Setup actually used
- **Tasks:** 180 held-out how-to tasks (see `E3_PREREG.md`).
- **Conditions:** A (model alone), B (+ retrieved core TOTE loop), C (+ random loop of matched length).
- **Subjects:** gemma-4-26b-a4b-it (cheaper) and gemma-4-31b-it (stronger), on the Gemini API free tier.
- **Grader:** gemini-3.5-flash-lite, blind to condition, grading 3 anonymized answers per call (Deviation 2b).
- **Same-provider grading:** the grader comes from the same provider as the subjects. **This is a weakness**, and it's why the result is labelled PRELIMINARY.
- **Cost:** **$0.00.** All calls ran on the free tier, which was verified because a paid-only model returned `free_tier limit: 0`. The ledger is `E3/cost_ledger.json`.

## Primary outcome (step-mode rubric score, 0–1), interim
Mean B−C is the paired difference; the 95% CI comes from a paired bootstrap with 10,000 resamples.

| Subject | n tasks | A | B | C | B−C (95% CI) | B−A (95% CI) | B vs C win/loss |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gemma-4-26b-a4b-it | 26 | 0.348 | 0.324 | 0.298 | +0.026 [−0.021, +0.089] | −0.026 [−0.095, +0.044] | 8% / 8% |
| gemma-4-31b-it | 2 | 0.522 | 0.522 | 0.522 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0% / 0% |

- **Pre-registered rule:** loops help only if the B−C CI lower bound is above 0. **It isn't met for either model so far.** With n=26 and n=2, that is still not evidence of no effect.
- **Grading pattern:** the grader often gives all three answers for a task the same score (ties dominate the B vs C comparison).
- **Unparseable grades:** 0.

## Grader agreement (agent hand check, blind; grader agreement only, not primary grading)
- **Sample:** 30 random step-mode answers scored by the agent, with the condition hidden.
- **Agreement:** Spearman ρ = **0.855**, mean absolute difference = **0.152**. The agent's mean was 0.617 and the grader's 0.568.
- **Files:** `E3/results_v2b/handcheck_v1_*`. ρ ≥ 0.6, so the grader is not flagged as low-trust.

## Cross-provider check (GPT, graded by hand in a chat app)
- **Packet:** `E3/gpt_chat_packet/`, with 32 blinded items so far (9 A, 11 B, 12 C, condition hidden), in 2 chunks of 20 and 12.
- **Ingest so far:** chunk 1 responses are in `E3/gpt_chat_packet/responses/chunk_1.json` (Spearman ρ ≈ 0.78 vs Gemini on those items). Chunk 2 still needs a response file.

## Caveats
1. **Small n.** 28 of 180 tasks, so nothing here is conclusive.
2. **Same-provider grader** (Gemini grading Gemma). Batched grading may also push the three scores toward each other.
3. **Empty answers.** Some subject answers come back empty (thinking budget), scored 0 in every condition, which dilutes any effect.
4. **Loose retrieval.** The 88 core loops are generic, so the B loop is often only loosely related to the task.
5. **Model changes.** The models changed three times from the original plan (Deviations 1, 2, 2a and 2b, all logged before data). The 17 records from the 2a pilot are excluded.

## Run state
- **Workers:** `tools/e3/worker.sh <model>` runs one per subject, detached with `setsid nohup`, and resumes from `results_v2b/raw_*.jsonl`.
- **Restarted 2026-11-05 ~11:58 EST** after both workers had exited (31b on a network timeout, exit 3). Free-tier workers are running again.
- **Daily quota:** a daily free-tier quota error makes a worker sleep until 03:10 EST (after the midnight-Pacific reset) and then resume.
- **Hard stops:** any billing, out-of-credit or non-free-tier quota error stops the worker for good.
- **Reanalyse:** `tools/e3/run_e3.py --gemini-free --analyze-only`.
