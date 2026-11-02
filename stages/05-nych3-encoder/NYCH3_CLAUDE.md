# NYCH 3.0 Pro -- Layer 0 (where am I?)
ICM workspace. A fresh, deterministic rebuild of the NYCH narrative encoder. Not a retrofit of nhartman000/nych.

- Read `CONTEXT.md` next, then the stage you are working in (`NN_*/CONTEXT.md`).
- Stage order: 01_boot -> 02_structure -> 03_scope_attribution -> 04_temporal -> 05_semantics -> 06_context -> 07_tote_bind -> 08_lexical_ids -> 09_gst_pretext -> 10_gestalt_llm [GATE] -> 11_paths [GATE] -> 12_mg8_handoff.
- Each stage reads ONLY the previous stage's `output/` plus `_config/` and `shared/`.
- **Authority boundary:** stages 01-09 are deterministic and make no LLM call. Stage 10 is the first and only LLM call in 01-10, and it does Gestalt mapping ONLY. Pruning/paths are stage 11. Gate authoring is MG8's.
- **Encode, don't answer:** questions or dialogue inside a story are invariant story content. They are flagged at the start (01/02), kept verbatim, and never answered.
- Stable rules: `_config/` (bonit, schema pins, registries). Library: `shared/nych3/`. Per-run artifacts: `NN_*/output/` (gitignored except .gitkeep).
- Never force a TOTE nearest match. Never emit a bare probability without a calibrated source.
