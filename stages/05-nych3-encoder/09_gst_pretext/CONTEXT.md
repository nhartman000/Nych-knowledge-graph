# 09_gst_pretext -- S9 Write the .gst pretext

**Reads:** 08_lexical_ids/output/state.json

**Writes:** <name>.gst (mg8-engine Gst compatible; NYCH3 payload under `nych3`, mg8 pipeline view under `nych_pretext`) and <name>.bonit (points to README.md/CLAUDE.md, carries prompt+story losslessly)

**Musts:**
- No pruning instructions in the .gst (that is stage 11).

**Run:** `python 09_gst_pretext/run.py`
