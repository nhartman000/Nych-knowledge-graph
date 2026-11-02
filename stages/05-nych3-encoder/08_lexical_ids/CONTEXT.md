# 08_lexical_ids -- S8 Lexical identifiers

**Reads:** 07_tote_bind/output/state.json

**Writes:** every word occurrence (full word + span), mapping candidates with skeletons, protected terms, skeleton collisions

**Musts:**
- Pronouns/closed-class words are not mapped (fixes his/house -> gestalt.hs).
- Protected names never mapped.
- Skeleton is a clue at the end of the id, never meaning.

**Run:** `python 08_lexical_ids/run.py`
