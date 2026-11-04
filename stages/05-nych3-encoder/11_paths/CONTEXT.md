# 11_paths -- S11 Prune and candidate paths

**Reads:** 10_gestalt_llm/output + the .gst

**Writes:** candidate paths per TOTE instance with ordered likelihood classes; trace.jsonl

**Musts:**
- No fabricated numbers: likelihood_class or unavailable.
- Separate from stage 10 and from MG8 gate authoring.

**Run:** `python 11_paths/run.py`
