// knowledge-graph schema — SINGLE SOURCE OF TRUTH. poc.py loads this file; do not duplicate DDL elsewhere.
// [nych3] = NYCH 3.0 Pro encoder + harvester (shared/nych3); merged here, the former shared/schemas/tote_kuzu.cypher is retired.
// Field provenance: [poc] nych-kg-poc/T.O.T.E-loops/nych registry; [g8son] g8son/schema/g8son.schema.json;
// [mg8-runtime] mg8-runtime/src/mg8_runtime/runtime.py permit dict; [gst] gst/spec/gst_v1.md; [qson] qson/schema/qson.schema.json.
// NEW = proposed here, not present in any source repo. One statement per line-group, terminated by ';'.

// ---- NYCH / TOTE (existing, [poc]) ----
CREATE NODE TABLE Gestalt(gestalt_id STRING, glyph STRING, lexical_form STRING, sense STRING, route STRING, recoverability_note STRING, origin STRING /* NEW: 'tote_db' | 'registry_glyph' */, PRIMARY KEY(gestalt_id));
CREATE NODE TABLE Sense(sense_id STRING, gestalt STRING, surface_forms STRING[], cue_words STRING[], PRIMARY KEY(sense_id));
CREATE NODE TABLE Span(span_id STRING, phrases STRING[], gestalt STRING, canonical_expression STRING, protected_invariants STRING[], PRIMARY KEY(span_id));
CREATE NODE TABLE Operator(operator_id STRING, symbol STRING, canonical_name STRING, evidence_channel STRING, may_assert_action BOOLEAN, PRIMARY KEY(operator_id));
// TOTELoop: [poc] columns first (legacy rows fill only these), then [nych3] row-model cells.
// *_cell = 'word,Gestalt' (Gestalt blank until stage 10); modality_cell lists every operator, e.g. 'loved,🫶 ; looking,👀¹'.
// status: candidate | canonical (canonical needs a named authority in provenance). Legacy rows: status '' and epistemic_status CANONICAL/DRAFT.
CREATE NODE TABLE TOTELoop(loop_id STRING, name STRING, domain STRING, objective STRING, initial_test STRING, exit_predicate STRING, max_iterations INT64, epistemic_status STRING, modality_cell STRING, actor_cell STRING, action_cell STRING, object_cell STRING, perspective_cell STRING, exit_gate_id STRING, action_lemma STRING, object_lemma STRING, termination_triggers STRING, techniques STRING, status STRING, provenance STRING, version STRING, repeat_count INT64, structure_key STRING, PRIMARY KEY(loop_id));
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

// ======================= [nych3] additions (NEW) =======================
// Modality operators (🫶 🙌 👀¹²³ 👁️ 👂 👂👂 💭 🧠🗯 👃 👅) are rows of the existing Operator table (ids OP-*), not a new table.
CREATE REL TABLE USES_MODALITY(FROM TOTELoop TO Operator, word STRING);
// Cell -> existing Gestalt / Sense tables (filled when stage 10 resolves a cell's Gestalt); no duplicate gestalt table.
CREATE REL TABLE CELL_GESTALT(FROM TOTELoop TO Gestalt, cell STRING, word STRING, session STRING, provenance STRING);
CREATE REL TABLE CELL_SENSE(FROM TOTELoop TO Sense, cell STRING, word STRING, provenance STRING);

// ---- domain partitions + cross-domain links (commonality: one loop IN_DOMAIN of >1 domain) ----
CREATE NODE TABLE Domain(domain_id STRING, name STRING, PRIMARY KEY(domain_id));
CREATE REL TABLE IN_DOMAIN(FROM TOTELoop TO Domain, role STRING, evidence STRING, provenance STRING);
CREATE REL TABLE DOMAIN_LINK(FROM Domain TO Domain, kind STRING, shared_loops INT64, evidence STRING, provenance STRING);

// ---- measures invariants (_config/invariants/measures.json; weights are ordered classes, weight_source assumed_prior, never calibrated) ----
CREATE NODE TABLE Measure(word STRING, kind STRING, sense_weight STRING, weight_source STRING, PRIMARY KEY(word));
CREATE NODE TABLE MeasureRule(rule_id STRING, rank INT64, pattern STRING, effect STRING, PRIMARY KEY(rule_id));
CREATE REL TABLE MEASURE_WEIGHT_IN(FROM Measure TO Domain, sense_weight STRING, weight_source STRING);

// ---- lexical store (full words always kept; skeleton is an attribute, never a key) ----
CREATE NODE TABLE LexicalEntry(entry_id STRING, word_full STRING, lemma STRING, skeleton STRING, protected BOOLEAN, PRIMARY KEY(entry_id));
CREATE NODE TABLE Occurrence(occ_id STRING, word_full STRING, doc_sha256 STRING, page_idx INT64, sent_idx INT64, char_start INT64, char_end INT64, PRIMARY KEY(occ_id));
CREATE REL TABLE OCCURS_AS(FROM LexicalEntry TO Occurrence);
CREATE REL TABLE MAPPED_TO(FROM LexicalEntry TO Gestalt, session STRING, status STRING, provenance STRING);

// ---- source records: ISBN + page; isbn may be '' (never invented) -> gutenberg id is a flagged fallback.
// sentence_text is kept per row so quality can be judged exactly. flags e.g. isbn_null_gutenberg_fallback, page_derived.
CREATE NODE TABLE SourceRef(ref_id STRING, isbn STRING, isbn_status STRING, page STRING, page_kind STRING, page_method STRING, fallback_gutenberg_id STRING, sent_key STRING, sentence_text STRING, flags STRING[], PRIMARY KEY(ref_id));
CREATE REL TABLE SOURCED_FROM(FROM TOTELoop TO SourceRef);
CREATE NODE TABLE HarvestSentence(sent_key STRING, book_id STRING, sent_offset INT64, outcome STRING, PRIMARY KEY(sent_key));

// ---- symbol-only pattern store (SCHEMA ONLY; not populated yet). A pattern carries symbols/slots, never words. ----
CREATE NODE TABLE SymbolPattern(pattern_id STRING, symbols STRING[], slots STRING[], structure_key STRING, arity INT64, provenance STRING, PRIMARY KEY(pattern_id));
CREATE REL TABLE INSTANTIATES(FROM TOTELoop TO SymbolPattern, bindings STRING);
CREATE REL TABLE PATTERN_OPERATOR(FROM SymbolPattern TO Operator, slot STRING);
CREATE REL TABLE PATTERN_GESTALT(FROM SymbolPattern TO Gestalt, slot STRING);

// ---- tech.ui (2026-11-02): instance loop -> canonical-action loop (both provisional candidates) ----
CREATE REL TABLE INSTANCE_OF(FROM TOTELoop TO TOTELoop, method STRING, provenance STRING);
