// knowledge-graph schema — SINGLE SOURCE OF TRUTH. poc.py loads this file; do not duplicate DDL elsewhere.
// Field provenance: [poc] nych-kg-poc/T.O.T.E-loops/nych registry; [g8son] g8son/schema/g8son.schema.json;
// [mg8-runtime] mg8-runtime/src/mg8_runtime/runtime.py permit dict; [gst] gst/spec/gst_v1.md; [qson] qson/schema/qson.schema.json.
// NEW = proposed here, not present in any source repo. One statement per line-group, terminated by ';'.

// ---- NYCH / TOTE (existing, [poc]) ----
CREATE NODE TABLE Gestalt(gestalt_id STRING, glyph STRING, lexical_form STRING, sense STRING, route STRING, recoverability_note STRING, origin STRING /* NEW: 'tote_db' | 'registry_glyph' */, PRIMARY KEY(gestalt_id));
CREATE NODE TABLE Sense(sense_id STRING, gestalt STRING, surface_forms STRING[], cue_words STRING[], PRIMARY KEY(sense_id));
CREATE NODE TABLE Span(span_id STRING, phrases STRING[], gestalt STRING, canonical_expression STRING, protected_invariants STRING[], PRIMARY KEY(span_id));
CREATE NODE TABLE Operator(operator_id STRING, symbol STRING, canonical_name STRING, evidence_channel STRING, may_assert_action BOOLEAN, PRIMARY KEY(operator_id));
CREATE NODE TABLE TOTELoop(loop_id STRING, name STRING, domain STRING, objective STRING, initial_test STRING, exit_predicate STRING, max_iterations INT64, epistemic_status STRING, PRIMARY KEY(loop_id));
CREATE NODE TABLE Step(step_key STRING, step_index INT64, phase STRING, plain_text STRING, nych_text STRING, proposition_kind STRING, provenance STRING, PRIMARY KEY(step_key));
CREATE NODE TABLE Utterance(utt_id STRING, text STRING, PRIMARY KEY(utt_id));

// ---- Gate ([g8son] gate object; file_id from g8son root) ----
CREATE NODE TABLE Gate(gate_id STRING, file_id STRING, `order` INT64, type STRING, conditions STRING[], outcomes STRING /* JSON of PASS/FAIL/INTERMEDIATE routes */, PRIMARY KEY(gate_id));

// ---- Permit ([mg8-runtime] permit dict; its 'id' key is stored as permit_id) ----
CREATE NODE TABLE Permit(permit_id STRING, run_id STRING, proposal_id STRING, status STRING, purpose STRING, expires_at STRING, version INT64, epoch INT64, evaluation_digest STRING, actor STRING, operation STRING, PRIMARY KEY(permit_id));

// ---- GSTState ([gst]; nested objects stored as canonical JSON strings) ----
CREATE NODE TABLE GSTState(state_id STRING, gst_version STRING, internal STRING, external STRING, continuity STRING, intent STRING, outcome_expectation STRING, constraints STRING, PRIMARY KEY(state_id));

// ---- QSON trace event ([qson] event; replaces former TraceEvent table) ----
CREATE NODE TABLE QSONTrace(trace_id STRING, run_id STRING, sequence INT64, event_type STRING, file_id STRING, gate_id STRING, input_state_id STRING, result STRING, action STRING, output_state_id STRING, actor_type STRING, actor_id STRING, timestamp STRING, previous_event_hash STRING, event_hash STRING, PRIMARY KEY(trace_id));

// ---- Relations ----
CREATE REL TABLE USES_GESTALT(FROM TOTELoop TO Gestalt, role STRING);
CREATE REL TABLE HAS_STEP(FROM TOTELoop TO Step);
CREATE REL TABLE NEXT_ON_MATCH(FROM Step TO Step);
CREATE REL TABLE NEXT_ON_MISMATCH(FROM Step TO Step);
CREATE REL TABLE USES_OPERATOR(FROM Step TO Operator);
CREATE REL TABLE SENSE_OF(FROM Sense TO Gestalt);            // NEW (via Sense.gestalt = Gestalt.glyph)
CREATE REL TABLE SPANS(FROM Span TO Gestalt);                // NEW (via Span.gestalt = Gestalt.glyph)
CREATE REL TABLE GROUNDED_TO(FROM Utterance TO Gestalt, word STRING);
CREATE REL TABLE SELECTED_LOOP(FROM Utterance TO TOTELoop, match_method STRING);
CREATE REL TABLE GUARDS(FROM Gate TO TOTELoop);              // NEW
CREATE REL TABLE ISSUES(FROM Gate TO Permit);                // NEW
CREATE REL TABLE AUTHORIZES(FROM Permit TO TOTELoop);        // NEW (was Permit->Step in draft)
CREATE REL TABLE TRANSITIONS_TO(FROM GSTState TO GSTState);  // NEW
CREATE REL TABLE INPUT_STATE(FROM QSONTrace TO GSTState);    // NEW edge; field input_state_id is [qson]
CREATE REL TABLE OUTPUT_STATE(FROM QSONTrace TO GSTState);   // NEW edge; field output_state_id is [qson]
CREATE REL TABLE RECORDS(FROM QSONTrace TO Gate);            // NEW
CREATE REL TABLE TRACE_OF(FROM QSONTrace TO Utterance);
CREATE REL TABLE PRECEDES(FROM QSONTrace TO QSONTrace);
