# 05_semantics -- S5 Nested semantic structure

**Reads:** 04_temporal/output/state.json

**Writes:** propositions: actor (control for nested events), object, locations (perspective level 2 for from-PP), spatial relations (behind(hill, house)), polarity, grammatical modality, sensory channel

**Musts:**
- Nested actions stay under their governing predicate.
- Channel (actor's modality) is separate from provenance (how the system knows).

**Run:** `python 05_semantics/run.py`
