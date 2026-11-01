# Stage 04 — POC run (Layer 2)
Job: run sentences through `python stages/04-poc-run/poc.py "sentence"` (or --file / stdin). Each run writes a QSON v1 ledger to output/traces/<run_id>.qson (hash-chained, see qson_ledger.py). Check with `python stages/04-poc-run/poc.py verify output/traces/*.qson`.
