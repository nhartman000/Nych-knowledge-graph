# Layer 1 — task routing (where do I go?)
| Stage | Job | Reads | Writes | Gate |
|---|---|---|---|---|
| 01-inputs | Verify vendored NYCH + TOTE inputs | shared/data, shared/vendor | output/inputs_manifest.md | output/GATE.md |
| 02-schema | Maintain Kùzu DDL | 01 output, _config/conventions.md | output/schema.cypher | output/GATE.md |
| 03-ontology | Maintain ontology map | 02 output | output/ONTOLOGY.md, output/ontology.json | output/GATE.md |
| 04-poc-run | Load graph, run one sentence end-to-end | 02 output, shared/ | output/run_output.txt | output/GATE.md |
Rule: a stage may start only when the previous stage's `output/GATE.md` says `status: APPROVED` (human edits this line).
