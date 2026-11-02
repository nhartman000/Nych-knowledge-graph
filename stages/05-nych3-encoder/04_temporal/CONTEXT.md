# 04_temporal -- S4 Temporal structure

**Reads:** 03_scope_attribution/output/state.json

**Writes:** events with tense/aspect/finite, nested non-finite events (governed tense), time anchors scoped to their clause events, temporal relations

**Musts:**
- An anchor never propagates backward (One clear night scopes only sentence 2).
- A gerund/infinitive under a past clause is not present tense.

**Run:** `python 04_temporal/run.py`
