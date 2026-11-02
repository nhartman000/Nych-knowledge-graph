# 07_tote_bind -- S7 Retrieve and bind TOTE templates

**Reads:** 06_context/output/state.json + Kuzu TOTE DB (shared/data/tote.kuzu)

**Writes:** TOTE instances with the row cells (modality, actor, action, object, perspective/location, exit gate), explicit/inferred status per component, NO_MATCH fallbacks, harvest candidates

**Musts:**
- Lookup is exact on (action lemma, object lemma) or a declared '*' row. Never word overlap, never nearest match.
- Harvested rows are status=candidate with provenance; canonical needs a named authority.

**Run:** `python 07_tote_bind/run.py`
