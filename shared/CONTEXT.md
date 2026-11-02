# shared/ (Layer 3, cross-stage)
- `data/tote_loops.sqlite3` — snapshot of nhartman000/T.O.T.E-loops `data/tote_loops.sqlite3`.
- `data/sense_registry.json` — snapshot of nhartman000/nych `nych/data/sense_registry.json`.
- `vendor/nych/nych/` — vendored nhartman000/nych package (MIT) providing `gestalt_handoff.build_handoff`.
Refresh by re-copying from the source repos; record the commit in stages/01-inputs/output/inputs_manifest.md.
- `nych3/` — NYCH 3.0 encoder + harvester library (see `nych3/CONTEXT.md`); DDL comes from `stages/02-schema/output/schema.cypher`.
- `data/tote_seed.json` — NYCH 3.0 seed (modality operators, domains, exit gates, canonical seed loops).
- `vendor/dictionary_words.txt.gz` — word list used by nych3 skeleton checks (licence alongside).
