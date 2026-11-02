# Stage 04 — POC run (Layer 2)
Precondition: `stages/03-ontology/output/GATE.md` has `status: APPROVED`. The runner refuses otherwise (exit 2).
Job: `python stages/04-poc-run/poc.py --file sentences.txt` (or a sentence arg, or `-` for stdin).
- Store is persistent at output/kg.kuzu; `--rebuild` reloads it from schema.cypher + shared/data.
- Each run writes a QSON v1 ledger to output/traces/<run_id>.qson; check with `poc.py verify output/traces/*.qson`.
- `--force-demo` bypasses the gate for a demo only; outputs go to demo_pre_approval/ (not a deliverable).
