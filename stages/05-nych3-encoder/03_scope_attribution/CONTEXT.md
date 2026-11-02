# 03_scope_attribution -- S3 Scope and attribution

**Reads:** 02_structure/output/state.json

**Writes:** parser tags (rule default, spaCy optional), entities, mentions, coref chains, narrator/person, focalizer, speakers

**Musts:**
- Grammatical person is kept distinct from focalization.
- A user label that differs from the normalized grammar is kept and flagged (user_label_differs).
- Sentence-initial dictionary-word names (Peter) are detected as names.

**Run:** `python 03_scope_attribution/run.py`
