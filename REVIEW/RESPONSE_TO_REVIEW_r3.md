# Response to the third-opinion review (r3, 2026-11-03 evening ET)

Prepared by Grok Bot for N Hartman. The reviewers sent six files: a summary, four detailed reports (engine/NYCH, formats,
TOTE + knowledge graph, runtime), and a pip/test log. The reports are not committed here. The parent agent received them as
attachments, and N Hartman holds the originals. Each finding below cites the report and section it came from.

**Scope note.** The reviewers pinned the knowledge graph at `main@c4d3a14` (the old `stages/04-poc-run/poc.py`). This branch
(`nych3-integration`) replaced that runner with `stages/04-kg-run/kg_run.py`, so each graph finding was re-checked against this
branch. Most findings concern *other* repositories (mg8-engine, T.O.T.E-loops, qson, mg8). For those repos the fixes are on a branch with an
open PR and are **not merged**, per the push rules.

Status key: **Fixed**: the change and its regression test are committed. **Already fixed on branch**: the finding is valid for the
reviewed SHA, but this branch already differs. **Partial**: a real mitigation, but the underlying claim is still open.
**Decision**: N Hartman must decide. **Experiment**: needs a new measurement. **No action**: informational, or the reviewer
did not ask for a change.

| # | Source | Finding (deduplicated) | Valid? | Status | Action / commit | Verify |
|---|---|---|---|---|---|---|
| R3-01 | summary 1; engine F1 (P1) | mg8-engine README quickstart `pip install -e . -e ../nych` fails `ResolutionImpossible` against the pinned NYCH VCS dependency | valid | Fixed (PR, unmerged) | README now uses `pip install -e .`, with an optional `--no-deps -e ../nych`. It also notes that demo.py's sys.path is not wheel provenance. mg8-engine `67bc75a`, PR nhartman000/mg8-engine#7 | fresh venv: `pip install -e . && pip check`; test `test_readme_quickstart_does_not_use_conflicting_double_editable` |
| R3-02 | summary 2; engine F2 | Congruence validator accepts a flow covering only some files, or in reversed order | valid | Fixed (PR) | `validate_congruence_response` rejects duplicate gate ids and any flow that is not every declared gate exactly once in declared order. `67bc75a`, PR #7 | `tests/test_review_20261103.py::FlowCoverageOrderTests` (these tests fail on the old code) |
| R3-03 | summary 3; engine F3 | Manifest-bound `trace.qson` stays empty; sequences collide as `[0,1,2,1,2,3]` | valid | Fixed (PR) | Sequences are renumbered 0..n-1 across the run. Gate entries keep the executor's counter as `gate_step`. `trace.qson` gets the same entries as output.mg8. `67bc75a`, PR #7 | `TracePersistenceTests` |
| R3-04 | summary 7; engine F4 | README documents the removed `run_pipeline(gst, mapping_llm, out_dir)` and the one-call plan | valid | Fixed (PR) | README documents the two-call pipeline and the 4-arg signature, and labels `validate_plan` as legacy. `67bc75a`, PR #7 | `test_readme_documents_current_run_pipeline_signature` |
| R3-05 | summary 7; engine F5 | A supplied modality table can replace canonical glyphs (`{**CANON, **supplied}`) | valid (altered-input only) | Fixed (PR) | Canonical entries are applied last. Supplied values are protected as well. `67bc75a`, PR #7 | `ModalityTableReplacementTests` |
| R3-06 | summary 4; tote-graph F3 | T.O.T.E-loops `build_db` unlinks the old DB before reading the schema, so a failure leaves a 0-byte DB | valid | Fixed (PR) | The build is staged into `*.staged`, passes integrity and foreign-key checks, then `os.replace` swaps it in. On error the old DB and export are kept. Export SHA is unchanged (`aa39db7b…`). T.O.T.E-loops `e75d8f6`, PR nhartman000/T.O.T.E-loops#4 | `tests/test_atomic_rebuild.py` (the missing-schema test fails on the old builder); 30/30 unittest |
| R3-07 | summary 5; tote-graph F1 | Graph gate PASSes wrong-domain and negated prompts ("repair the failing pregnancy test", "do not repair …") | valid; **reproduced on this branch** (all 6 controls PASSed at d27056f) | Partial + Decision + Experiment | `kg_run.context_guard`: a negation cue or a content word outside the selected loop's vocabulary → INTERMEDIATE, no permit. The evaluation records `negated` and `unaccounted_words`. Gate conditions are listed in the Gate node. LIMITATIONS 24 names the gate "lexical-membership consistency, not semantic approval". This repo `3bb3225` | `tests/test_review_r3.py` (8 negative and 2 positive controls). The guards are heuristics with known false INTERMEDIATEs (LIMITATIONS 24). No error rate has been measured (E1) |
| R3-08 | summary 6; tote-graph F2 | `previous_event_hash = sha256(trace_id)` does not bind the prior event's content | valid for main@c4d3a14; **already fixed on this branch** | Already fixed; regression test added | `qson_ledger.py` (profile `kg-sha256-chain-v1`, since `d3ea015`) hashes the canonical prior event, and `verify` rejects edits. The new test `test_r3_06_previous_hash_binds_prior_content` is in `3bb3225`. The chain is still unkeyed (LIMITATIONS 21). | `pytest tests/test_kg.py -k tamper tests/test_review_r3.py`; `python stages/04-kg-run/kg_run.py verify <file>` |
| R3-09 | summary 8; tote-graph inventories | All 14 Sense and 11 Span nodes are disconnected | valid for main; **already fixed on this branch** | Already fixed | `SENSE_OF` / `SPANS` edges are created in `load_base` | `tests/test_kg.py::test_every_sense_and_span_linked_to_gestalt` |
| R3-10 | summary 8; tote-graph F4 | The graph is not a portable provenance bundle: it omits TOTE candidate/source/review sidecars, and step `provenance` is a 4-value vocabulary, not a citation | valid | Decision | Not changed. Fixing this needs a choice of which upstream TOTE evidence bundle (commit) to vendor, and how to model Source/Candidate nodes. Until then, do not claim source-grounded portable auditability. | — |
| R3-11 | tote-graph "Current CI" | No CI run at the reviewed graph SHA | valid for main@c4d3a14 | Already addressed on branch; Decision for main | `.github/workflows/ci.yml` on this branch has green runs, including at d27056f, and runs on the new head. `main` still has no workflow. Merging the branch is N Hartman's decision. | `gh run list --repo nhartman000/Nych-knowledge-graph --branch nych3-integration` |
| R3-12 | tote-graph readiness | Stage human sign-off is pending | valid (03 and 04 `GATE.md` are `PENDING`) | Decision | Only a person may set `status: APPROVED` | `stages/0*/output/GATE.md` |
| R3-13 | summary 7; formats F1 | The QSON spec §4 "minimum event" omits the schema-required `event_type` | valid | Fixed (PR) | Added `event_type`, plus `tools/check_spec_examples.py` and a CI workflow that check doc fences and examples against the schema. qson PR nhartman000/qson#3. The vendored copy `shared/qson/qson_v1.md` here stays byte-identical to upstream `main` until that PR merges. | `python tools/check_spec_examples.py` in the qson PR branch (old spec: 1 error; new: 0) |
| R3-14 | summary 7; formats F2 | QSON CITATION.cff expands the acronym, but the README says no expansion is assigned | valid | Decision | The reviewer explicitly asked not to pick one silently | — |
| R3-15 | formats (hardening); engine (claims) | `verify_evidence.py` relies on `assert`, so it is not a valid check under `python -O` | valid (hardening) | Fixed (PRs) | Explicit `check()` calls. mg8-engine `884be26` (PR #7) and mg8 PR nhartman000/mg8#8 (the two copies stay byte-identical) | `python -O experiments/response-contracts/verify_evidence.py` → PASS; a one-byte tamper → FAIL |
| R3-16 | tote-graph F1 (lookup) | TOTE lookup ignores state/context: PostgreSQL vs MySQL, Linux/Windows, failing/passing all select the same loop | valid | Partial / Decision | On this branch the legacy path now sends such inputs to INTERMEDIATE when the context word is not in the loop's vocabulary (R3-07), and the nych3 store lookup already has domain/platform preference (r2 #3). The vendored `nych/tote_lookup.py` is unchanged, because changing selection is a design decision. | `tests/test_review_r3.py` |
| R3-17 | engine F2 note; formats matrix | The legacy generic executor trusts callback results, defaults to dummy PASS, and advances on FAIL. The engine's CITATION title says "deterministic logic-gated execution engine" | valid; the boundary is already disclosed in the compatibility matrix | Decision | Either reword the CITATION title or harden the executor. Not changed. | — |
| R3-18 | formats | GST, G8SON, and QSON have no standalone CI | valid | Partial | Added for QSON only (R3-13). GST is a conceptual spec with no schema to check. G8SON is a decision. | — |
| R3-19 | tote-graph "Extraction evaluation" | No held-out extractor corpus, blinded annotation, or end-to-end precision/recall for loop extraction | valid (this repo already says the 86% figure is self-graded; LIMITATIONS 1–2) | Experiment | See E2 below | — |
| R3-20 | runtime-review | The runtime deep review was cut short by a provider policy block, so no security verdict was given | valid statement by the reviewer | No action | Ask for a completed runtime review if one is wanted | — |
| R3-21 | engine "Identity" | Dependencies are lower bounds, not a full transitive lock (engine, NYCH) | valid (informational) | Decision | This repo ships `REVIEW/requirements.lock`. The engine and NYCH do not. | — |
| R3-22 | formats | QSON schema accepts duplicate events (same trace_id and sequence) | valid observation; the reviewer says it is not a blocker | No action | The schema does not claim cross-event invariants. `qson_ledger.verify` here does check sequence and chain. | — |
| R3-23 | summary "Limits" | Do not use the outreach/adoption inference or XERJ material as technical validation | agreed | No action | None of it is cited in this package | — |

Disputed: none of the findings is disputed as stated. R3-08, R3-09 and R3-11 are *not current* on this branch: they are correct for
`main@c4d3a14`, which the reviewers pinned. They will stay true of `main` until the branch is merged.

## Verification on this branch
- `PYTHONPATH=shared pytest tests -q` → 201 passed (189 before r3, plus 12 in `tests/test_review_r3.py`).
- `PYTHONPATH=shared python tools/core_tote/validate.py` → 0 errors.
- `bash REVIEW/reproduce.sh` in a fresh clone of the pushed branch: see `REVIEW/RUNLOG.md` (r3 row).
- Only `REVIEW/MANIFEST.sha256` changed (code and docs changed). `inputs.sha256`, `expected_store.json` and `expected_eval.json`
  are unchanged, because no data, store or eval output changed.

## Proposed experiments (not run)
- **E1: gate error rate.** Build a labelled set of about 300 utterances: in-domain positives, paraphrases, wrong-domain near
  misses, negations, and multi-action inputs. Have it labelled by someone who is not the agent. Report PASS precision and recall
  for the old lexical gate vs the r3 guarded gate, with confidence intervals. This replaces "controlled negative examples" with a rate.
- **E2: extraction accuracy.** Use a held-out, blinded double-annotated sample of harvested pages (with an adjudication
  protocol). Report end-to-end loop precision and recall, with missed and spurious loops in the denominators (r2 already added the end-to-end metric).
- **E3: do the loops improve model prediction?** Use a pre-registered A/B test on held-out tasks, such as next-step prediction or
  instruction following on UI how-to items not used to build the loops. Compare (a) the model alone, (b) the model plus the
  retrieved TOTE loop, and (c) the model plus a random or shuffled loop of the same length (the length/format control). Use the same
  prompts and several samples per item. Score exact step-match and success with a fixed rubric, graded blind to the arm. Report the
  effect size with CIs. A gain from (b) only counts if it exceeds (c). This costs money for live model calls, so it needs N Hartman's go-ahead.
