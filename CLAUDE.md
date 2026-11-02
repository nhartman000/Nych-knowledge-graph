# knowledge-graph — Layer 0 (where am I?)
ICM workspace (Interpretable Context Methodology, arXiv:2603.16021). A Kùzu knowledge graph — the SHARED STORE — linking NYCH 3.0 encodings (modality/actor/action/object/perspective cells), harvested TOTE loops with ISBN+page provenance, NYCH gestalts/senses/spans, operators, gates, permits, GST states and QSON traces.
- Routing: read `CONTEXT.md` next. Never skip a stage gate.
- Layer 3 (stable rules): `_config/` (conventions, nych3.bonit, registries/, invariants/ incl. measures.json), `shared/` (nych3 library, data, vendor, qson), each stage's `references/`.
- Layer 4 (per-run artifacts): each stage's `output/`.
- Plain text between stages (md/json/cypher). Binary DBs (`*.kuzu`) and harvest data are run artifacts, gitignored.
- DDL lives ONLY in `stages/02-schema/output/schema.cypher`. Never add CREATE TABLE elsewhere.
- NYCH 3.0 rules (see `stages/05-nych3-encoder/NYCH3_CLAUDE.md`): stages 01-09 deterministic, no LLM; never force a nearest TOTE match; canonical rows need a named authority; sense weights are ordered classes / `assumed_prior`, never calibrated probabilities; ISBN is never invented.
- Setup: one venv, `pip install -r requirements.txt -r requirements-dev.txt` (optional `--no-deps -r requirements-mg8.txt`); `pytest -q` runs both suites.
