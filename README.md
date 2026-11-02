# knowledge-graph
A graph database (Kùzu 0.11.3) that is the shared store for the **NYCH 3.0 encoder** and **T.O.T.E. task loops**. A sentence is encoded by NYCH 3.0 (modality emojis 🫶 🙌 👀¹²³ 👁️ 👂 👂👂 💭 👁️‍🗨️ 👃 👅, actor, action, object, perspective/location), bound to a TOTE loop by exact structured lookup, checked by a gate (PASS / FAIL / INTERMEDIATE), given a permit if it passes, and recorded in a tamper-evident QSON audit file. A batch harvester fills the same store with candidate TOTE rows from public-domain instructional books, with ISBN + page provenance and the sentence text.

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

## Schema (single source: `stages/02-schema/output/schema.cypher`)
- TOTELoop: legacy columns + NYCH 3.0 row cells (`modality_cell`, `actor_cell`, `action_cell`, `object_cell`, `perspective_cell`), lemmas, triggers, status (candidate/canonical), provenance, repeat_count.
- Mapped onto existing tables: modality operators are `Operator` rows (`USES_MODALITY`); cells link to `Gestalt` / `Sense` (`CELL_GESTALT`, `CELL_SENSE`); exits are `Gate` rows (`GUARDS`).
- Domains: `Domain`, `IN_DOMAIN`, cross-domain `DOMAIN_LINK` (derived from loops in >1 domain).
- Measures invariants: `Measure`, `MeasureRule`, `MEASURE_WEIGHT_IN` (loaded from `_config/invariants/measures.json`; weights are `assumed_prior` classes).
- Source records: `SourceRef` (isbn, isbn_status, page, page_kind, page_method, fallback_gutenberg_id, sentence_text, flags), `SOURCED_FROM`, `HarvestSentence` ledger.
- Symbol-only pattern store (schema only): `SymbolPattern`, `INSTANTIATES`, `PATTERN_OPERATOR`, `PATTERN_GESTALT`.
- Ontology map: `stages/03-ontology/output/ONTOLOGY.md` · QSON hash chain: `stages/04-kg-run/qson_ledger.py`.
