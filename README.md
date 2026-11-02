# knowledge-graph
A graph database (Kùzu 0.11.3) that is the shared store for the **NYCH 3.0 encoder** and **T.O.T.E. task loops**. A sentence is encoded by NYCH 3.0 (modality emojis 🫶 🙌 👀¹²³ 👁️ 👂 👂👂 💭 🧠🗯 👃 👅, actor, action, object, perspective/location), bound to a TOTE loop by exact structured lookup, checked by a gate (PASS / FAIL / INTERMEDIATE), given a permit if it passes, and recorded in a tamper-evident QSON audit file. A batch harvester fills the same store with candidate TOTE rows from public-domain instructional books, with ISBN + page provenance and the sentence text.

Organised with **Interpretable Context Methodology (ICM)**: https://arxiv.org/abs/2603.16021. Work moves through the numbered folders in `stages/`; each has `CONTEXT.md`, `references/`, `output/`; a person approves a stage by editing `output/GATE.md`.

## Setup
```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install --no-deps -r requirements-mg8.txt     # optional, private: enables mg8-engine .gst compat tests
pytest -q                                         # KG suite (tests/) + NYCH 3.0 suite (tests/nych3/)
```

## Run (stage 04)
```
python stages/04-kg-run/kg_run.py "Peter looked at the stars."            # needs stage 03 APPROVED
python stages/04-kg-run/kg_run.py --file sentences.txt                     # or: echo "..." | kg_run.py -
python stages/04-kg-run/kg_run.py verify stages/04-kg-run/output/traces/*.qson
python stages/04-kg-run/kg_run.py --force-demo "..."   # demo before approval -> stages/04-kg-run/demo_pre_approval/
```
`--rebuild` reloads the store; otherwise it persists. The runner uses the NYCH 3.0 encoder first (`match_method: nych3:*`); if no TOTE row matches it falls back to the legacy vendored-nych grounding adapter for the legacy loop set (`legacy:*`). The old POC runner `poc.py` is retired.

## NYCH 3.0 encoder + harvester (stage 05)
```
export PYTHONPATH=shared
python -m nych3.store.tote_db                                   # standalone seed store (shared/data/tote.kuzu)
nych3 encode --prompt "Encode this story with NYCH." --story tests/nych3/golden/peter/story.txt --name peter
python -m nych3.harvest.cli run --max-sentences 8000            # resumable, polite, at-most-once per sentence
```
See `stages/05-nych3-encoder/README.md`, `CONTEXT.md`, `HARVEST.md`.

## Demo + measured accuracy (round 4, local only)
Paste an instructional sentence; see the encoded TOTE loop(s) with modality emojis, the exit gate and
its tier, provenance, and a graph lookup of matching stored loops (same structure, its book sources,
same-action loops). The store is opened read-only; the web page binds 127.0.0.1 only (not deployed).
```
export PYTHONPATH=shared
python -m nych3.demo "Stir the sauce with a spoon until thick, exactly as last time."     # CLI (add --json, --domain craft.knitting)
python -m nych3.demo --serve --port 8765                                                 # page at http://127.0.0.1:8765/
python -m nych3.eval.accuracy [--json report.json]                                       # gold-set accuracy (also: nych3-eval)
```
Sample transcript:
```
$ python -m nych3.demo "Stir the sauce with a spoon until thick, exactly as last time."
sentence: Stir the sauce with a spoon until thick, exactly as last time.
domain:   cooking   outcome: action

LOOP 1  TL-H-adf1a0c0945a
  modality : Stir,🙌
  actor    : you(implied),
  action   : stir,
  object   : sauce, ; tool: spoon,
  location : UNRESOLVED,
  exit gate: G-TL-H-adf1a0c0945a  [explicit]  until thick [explicit]  PASS->exit FAIL->repeat
  exit     : 🫶💭 feel thick   (marker 💭, cue: exactly as last time)
  provenance: demo input (pasted by user) (no ISBN/page)
  graph: same structure not in store (new loop)
         same action: stir [cooking, 69x]; stir soup [cooking, 4x]; stir fork [cooking, 4x]; stir [cooking, 2x]; stir stock [cooking, 2x]
         lookup(stir): exact_action_object -> TL-STIR-SAUCE-001
```
Accuracy is measured against `tests/nych3/gold/gold_v1.jsonl` (300 sentences, 75 per domain), which is
**agent-graded, pending human review** — see `tests/nych3/gold/README.md` for notation and judgment
calls. `tests/nych3/test_round4.py::test_accuracy_report` prints the per-field / per-domain table on
every test run (non-failing; xfails only if a field collapses below a floor).

## Schema (single source: `stages/02-schema/output/schema.cypher`)
- TOTELoop: legacy columns + NYCH 3.0 row cells (`modality_cell`, `actor_cell`, `action_cell`, `object_cell`, `perspective_cell`), lemmas, triggers, status (candidate/canonical), provenance, repeat_count.
- Mapped onto existing tables: modality operators are `Operator` rows (`USES_MODALITY`); cells link to `Gestalt` / `Sense` (`CELL_GESTALT`, `CELL_SENSE`); exits are `Gate` rows (`GUARDS`).
- Domains: `Domain`, `IN_DOMAIN`, cross-domain `DOMAIN_LINK` (derived from loops in >1 domain).
- Measures invariants: `Measure`, `MeasureRule`, `MEASURE_WEIGHT_IN` (loaded from `_config/invariants/measures.json`; weights are `assumed_prior` classes).
- Source records: `SourceRef` (isbn, isbn_status, page, page_kind, page_method, fallback_gutenberg_id, sentence_text, flags), `SOURCED_FROM`, `HarvestSentence` ledger.
- Symbol-only pattern store (schema only): `SymbolPattern`, `INSTANTIATES`, `PATTERN_OPERATOR`, `PATTERN_GESTALT`.
- Ontology map: `stages/03-ontology/output/ONTOLOGY.md` · QSON hash chain: `stages/04-kg-run/qson_ledger.py`.

## tech.ui domain (2026-11-02, PROVISIONAL / UNREVIEWED)
Canonical UI actions harvested from 2,887 tech help-center articles (Microsoft 1,500, YouTube 436, Claude 367, Android 222, Chrome 197,
Gemini 136, Apple 29) by the nych-ui-actions pipeline (copy in `REVIEW/tech_ui_pipeline/`).
`shared/data/tech_ui/` holds the compact export (81 canonical actions + 63,487 mapped actions: URL, retrieval date, section/step,
quote <= 25 words; no article text). Top-10/25/50/100 canonical actions cover 55.9/79.7/93.1/96.3% of 65,929 extracted actions.
Ingest: `cd shared && python -m nych3.harvest.tech_ui [--replace]` -> 81 `TL-UI-<ACTION>` canonical-action loops (🙌 operate / 👀² verify,
g8son gate `G-UI-<ACTION>`), 36,445 `TL-UI-I-*` instance loops (deduped by canonical+verb+object, `repeat_count`), 63,487 web `SourceRef`s,
`INSTANCE_OF` instance->canonical. All rows `status=candidate`, `epistemic_status=PROVISIONAL`, `review_status=provisional_unreviewed`
(spot check 21/40 correct, agent-graded). `tote.kuzu` stays gitignored.

## Evaluation caveat
The 300-sentence gold set (`tests/nych3/gold/`) is AGENT-GRADED, PENDING HUMAN REVIEW. See `REVIEW/LIMITATIONS.md` and
`REVIEW/REVIEWER_BRIEF.md`; reproduce everything with `bash REVIEW/reproduce.sh`.

## How to cite
See `CITATION.cff` (also in `REVIEW/`; GitHub shows a "Cite this repository" button). Suggested:
Hartman, N. C. (American Milestone Inc). *NYCH 3.0 TOTE-Loop Knowledge Graph (MG8 family)*, version nych3-2026.11.02, released 2026-11-02.
https://github.com/nhartman000/knowledge-graph
No LICENSE file is present yet; citation does not grant a license.
