# 01_boot -- S1 Load boot instructions

**Reads:** _config/nych3.bonit, _config/schema_versions.yaml, input prompt + story (01_boot/input.json when run standalone)

**Writes:** run manifest: nych3 version, repo commit, schema pins, bonit sha256, parser name/version, source sha256, invariant-content flags (questions/dialogue flagged at the start)

**Musts:**
- The .bonit directive is: encode, never answer story questions.
- No LLM.

**Run:** `python 01_boot/run.py`
