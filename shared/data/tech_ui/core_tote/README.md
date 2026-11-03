# CORE TOTE loops: basic software and AI-tool functions

A small, high-accuracy set of Test-Operate-Test-Exit loops. Each loop describes **one declared function performing as intended**: a precondition test, one operation, an observable post-condition test, an exit, and bounded retry/stop rules. A loop is **not an agent**. It does not seek goals, act on anyone's behalf, chain to other loops, or extend its own bounds (`actor.kind = declared_function`).

**Status of every loop:** `CANONICAL-CANDIDATE` with `verified_by_human: false`. The loops were authored and checked in two passes by an agent. They are not human-verified and are not ingested into the Kùzu store. This is a dataset. It is not a runtime executor, and nothing here enforces the bounds at run time.

## Files
- `core_loops.json`: the loops (schema `nych3.core_tote/v1`)
- `verify_report.json`: what was kept and dropped, and why
- `candidates.json`: pass-1 candidate quote pools (the review input)
- `OPERATOR_MAPPING.md`: explicit 4-op ↔ 10-op mapping, with gaps flagged

## Pipeline (`tools/core_tote/`)
1. `spec.py`: hand-authored function specs (pre/op/post/fail, retry class, platform variants, quote and section filters)
2. `build.py`, **pass 1**: selects candidate quotes from `ui_actions*.jsonl.gz`. A candidate must come from the category's official sites, match the quote regex, sit under a section heading about the function, be ≤25 tokens, and be untruncated.
3. `curation.py`, **pass 2 (review)**: an agent reads each candidate pool and picks quotes that directly state the function, or drops the loop with a reason. It also grades each kept loop `correct` or `partial`.
4. `verify.py`, **pass 2 (mechanical)**: re-finds each chosen quote **verbatim in the cached raw help page** (`$NYCH_UI_RAW`). It checks that the retrieval date matches the cache index, requires ≥2 distinct URLs, and emits the loops.
5. `validate.py`: strict schema/contract validation. It needs no network or cache. `tests/nych3/test_core_tote.py` runs it.

Rebuild: `PYTHONPATH=shared python tools/core_tote/build.py && python tools/core_tote/verify.py && python tools/core_tote/validate.py`

## Retry classes
- Idempotent operations (open, toggle, navigate, upload, search): `max_retries=2`. A retry happens only if `test_pre` still holds and `test_post` is false.
- Non-idempotent or irreversible operations (send, delete, print, install, sign-in, share, purchase-adjacent): `max_retries=0`. On failure the loop reports and stops. Example: for Send, check Sent/Outbox; never resend automatically.
- Every loop stops on any prompt asking for a decision the loop did not declare (confirmation, payment, permission, sign-in).

Platform variants (keyboard shortcuts and similar) are authored from general platform knowledge. **They are not part of the quoted grounding.** Treat them as unverified hints.
