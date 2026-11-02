# 10_gestalt_llm -- S10 First LLM call: Gestalt mapping only

**Reads:** 09_gst_pretext/output/<name>.gst

**Writes:** proposed mappings, validation result (NYCH3 + mg8-engine validator), filled cells; persisted to Kuzu only after GATE.md approval

**Musts:**
- Only shared/nych3/llm/gestalt_call.py may call a provider. Shipped provider: MockProvider (stub).

**Run:** `python 10_gestalt_llm/run.py`
