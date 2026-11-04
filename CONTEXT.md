# Layer 1 — task routing (where do I go?)
| Stage | Job | Reads | Writes | Gate |
|---|---|---|---|---|
| 01-inputs | Verify vendored NYCH + TOTE inputs | shared/data, shared/vendor | output/inputs_manifest.md | output/GATE.md |
| 02-schema | Maintain Kùzu DDL (single source for the WHOLE repo, incl. NYCH 3.0) | 01 output, _config/conventions.md | output/schema.cypher | output/GATE.md |
| 03-ontology | Maintain ontology map | 02 output | output/ONTOLOGY.md, output/ontology.json | output/GATE.md |
| 04-kg-run | Run sentences end-to-end: NYCH 3.0 encoder -> TOTE loop -> KG gate -> Permit/GST -> QSON hash-chain trace (replaces retired 04-poc-run/poc.py) | 02 output, 05 encoder, shared/ | output/kg.kuzu, output/traces/*.qson | output/GATE.md |
| 05-nych3-encoder | NYCH 3.0 Pro encoder sub-stages 01_boot … 12_mg8_handoff (own CONTEXT.md; GATE.md at 10 and 11) + batch TOTE harvester (HARVEST.md) | _config/, shared/nych3, shared/data | NN_*/output/ (gitignored), shared/data/harvest/ (gitignored) | 10_gestalt_llm/GATE.md, 11_paths/GATE.md |
Rule: a stage may start only when the previous stage's `output/GATE.md` says `status: APPROVED` (human edits this line). Inside 05, follow `stages/05-nych3-encoder/CONTEXT.md`.

## Shared store
One Kùzu store, one DDL (`stages/02-schema/output/schema.cypher`). `kg_run.py` and `nych3.store.tote_db.ToteDB` (encoder stage 07 + harvester) load the same DDL; the runner hands its open connection to the encoder (`ToteDB.on_connection`) so both write one graph.
