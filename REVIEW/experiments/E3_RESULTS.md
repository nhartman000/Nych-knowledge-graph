# E3 results: INTERIM and PRELIMINARY (snapshot 2026-11-03, about 11:50 PM EST)

> **Status: incomplete.** The free-tier run (Deviation 2b) is still going. Only **12 of the 180 tasks** have all three conditions graded for step mode: **10 for gemma-4-26b-a4b-it and 2 for gemma-4-31b-it.** Next-action mode has 1 task per model. **No conclusion can be drawn yet.** This file will be replaced when the run finishes.

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
| gemma-4-26b-a4b-it | 10 | 0.524 | 0.524 | 0.524 | 0.000 [0.000, 0.000] | 0.000 [−0.170, +0.171] | 0% / 0% |
| gemma-4-31b-it | 2 | 0.500 | 0.500 | 0.500 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0% / 0% |

- **Pre-registered rule:** loops help only if the B−C CI lower bound is above 0. **It isn't met for either model so far.** With n=10 and n=2, that is not evidence of no effect.
- **Grading pattern:** the grader usually gave all three answers for a task the same score. In 8 of the 10 gemma-26b tasks, A, B and C scored identically.
- **Well-matched subset (retrieval score at or above the median, 4.08):** gemma-26b n=8, with A, B and C all at 0.655. B−C is 0.000 [0, 0] and B−A is 0.000 [−0.21, +0.21]. gemma-31b n=2, with all scores identical.
- **Unparseable grades:** 0.

## Grader agreement (agent hand check, blind; grader agreement only, not primary grading)
- **Sample:** 30 random step-mode answers scored by the agent, with the condition hidden.
- **Agreement:** Spearman ρ = **0.855**, mean absolute difference = **0.152**. The agent's mean was 0.617 and the grader's 0.568.
- **Bigger disagreements:** on some answers that found the right Settings path through different menu names, the grader gave 0 where the agent gave 0.67.
- **Files:** `E3/results_v2b/handcheck_v1_*`. ρ ≥ 0.6, so the grader is not flagged as low-trust.

## Cross-provider check (GPT, graded by hand in a chat app)
- **Packet:** `E3/gpt_chat_packet/`, with 32 blinded items so far (9 A, 11 B, 12 C, condition hidden), in 2 chunks of 20 and 12. It contains a strict JSON rubric and a README.
- **Key:** `E3/gpt_chat_key_SECRET.json`, kept outside the packet.
- **Ingest:** `PYTHONPATH=shared /workspace/kgenv/bin/python tools/e3/gpt_packet.py ingest`, which writes `E3/gpt_chat_agreement.json`.
- **Rebuild:** to grow it to about 60 items once more data exists, run `tools/e3/gpt_packet.py build`. That replaces the packet and the key.

## Caveats
1. **Tiny n.** 12 of 180 tasks, so nothing here is conclusive.
2. **Same-provider grader** (Gemini grading Gemma). Batched grading may also push the three scores toward each other.
3. **Empty answers.** 4 of the 30 gemma-26b step answers were empty, probably because the model's thinking used up the output budget. They're scored 0 in every condition, which dilutes any effect.
4. **Loose retrieval.** The 88 core loops are generic, so the B loop is often only loosely related to the task.
5. **Model changes.** The models changed three times from the original plan (Deviations 1, 2, 2a and 2b, all logged before data). The 17 records from the 2a pilot are excluded.

## Run state, and what resumes tomorrow
- **Workers:** `tools/e3/worker.sh <model>` runs one per subject, detached with `setsid nohup`, and resumes from `results_v2b/raw_*.jsonl`.
- **Daily quota:** a daily free-tier quota error makes a worker sleep until 03:10 EST (after the midnight-Pacific reset) and then resume.
- **Hard stops:** any billing, out-of-credit or non-free-tier quota error stops the worker for good.
- **Throughput:** about 100 records an hour for gemma-26b and much less for gemma-31b. The 1,080 step-mode records still to do will take days.
- **Reanalyse:** `tools/e3/run_e3.py --gemini-free --analyze-only`.
