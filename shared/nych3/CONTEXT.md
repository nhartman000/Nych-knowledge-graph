# shared/
- `nych3/` library: `nlp/` (segmenter, parser_adapter, analysis), `store/tote_db.py` (Kuzu), `stages.py` (01-08), `gst.py` + `bonit.py` (09), `llm/gestalt_call.py` (10, the only LLM call site), `paths.py` (11), `pipeline.py`, `cli.py`.
- `schemas/tote_kuzu.cypher`: single source of DDL (knowledge-graph style).
- `data/tote_seed.json`: seed TOTE rows (Peter loops). `data/tote.kuzu` is a build artifact (gitignored).
- `vendor/`: salvaged dictionary word list (ESDB/SCOWL size 60, license alongside) from nych@57b81e9.
