# Gate — 03-ontology
status: PENDING
reviewer:
date:
notes:

## Review checklist (edit `status:` to APPROVED only when all are ticked)
- [ ] `schema.cypher` is accepted as the single source (ontology.json is generated from it).
- [ ] Gate fields from g8son (gate_id, file_id, order, type, conditions, outcomes) are correct.
- [ ] Permit fields from mg8-runtime are correct, incl. storing its `id` as `permit_id`.
- [ ] GSTState fields from gst are correct; nested objects as JSON strings is acceptable.
- [ ] QSONTrace replacing TraceEvent, with actor split into actor_type/actor_id, is acceptable.
- [ ] NEW relations accepted: SENSE_OF, SPANS, GUARDS, ISSUES, AUTHORIZES (Permit→TOTELoop, changed from Permit→Step), TRANSITIONS_TO, INPUT_STATE, OUTPUT_STATE, RECORDS.
- [ ] Creating `origin='registry_glyph'` Gestalt nodes for registry glyphs absent from the TOTE DB is acceptable (alternative: leave those Senses/Spans unlinked).
- [ ] `Step -[:IN_STATE]-> GSTState` from the earlier draft is dropped in favour of QSON input/output state edges.
