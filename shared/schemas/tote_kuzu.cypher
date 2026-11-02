// NYCH 3.0 Pro TOTE store -- Kuzu 0.11.3. Style and shared tables follow
// /workspace/knowledge-graph stages/02-schema/output/schema.cypher ([kg]).
// NEW = not in the knowledge-graph schema. One statement per ';'.

// ---- [kg] tables, same columns ----
CREATE NODE TABLE Gestalt(gestalt_id STRING, glyph STRING, lexical_form STRING, sense STRING, route STRING, recoverability_note STRING, origin STRING, PRIMARY KEY(gestalt_id));
CREATE NODE TABLE Operator(operator_id STRING, symbol STRING, canonical_name STRING, evidence_channel STRING, may_assert_action BOOLEAN, PRIMARY KEY(operator_id));
CREATE NODE TABLE Gate(gate_id STRING, file_id STRING, `order` INT64, type STRING, conditions STRING[], outcomes STRING, PRIMARY KEY(gate_id));

// ---- [kg] TOTELoop columns first, then NEW row-model cells (user TOTE DB model) ----
// Each *_cell holds 'word,Gestalt' (Gestalt blank until stage 10). modality_cell holds every operator: 'loved,🫶 ; looking,👀¹'.
CREATE NODE TABLE TOTELoop(loop_id STRING, name STRING, domain STRING, objective STRING, initial_test STRING, exit_predicate STRING, max_iterations INT64, epistemic_status STRING, modality_cell STRING, actor_cell STRING, action_cell STRING, object_cell STRING, perspective_cell STRING, exit_gate_id STRING, action_lemma STRING, object_lemma STRING, termination_triggers STRING, techniques STRING, status STRING, provenance STRING, version STRING, PRIMARY KEY(loop_id));

// ---- NEW: domain partition + commonality (5th dimension = a loop linked to >1 domain) ----
CREATE NODE TABLE Domain(domain_id STRING, name STRING, PRIMARY KEY(domain_id));
CREATE REL TABLE IN_DOMAIN(FROM TOTELoop TO Domain, role STRING, evidence STRING, provenance STRING);

// ---- exit condition = a g8son gate that TEST checks; stored in the DB ----
CREATE REL TABLE GUARDS(FROM Gate TO TOTELoop);               // [kg]
CREATE REL TABLE USES_MODALITY(FROM TOTELoop TO Operator, word STRING);   // NEW

// ---- NEW: lexical store (full words always kept; skeleton is an attribute, never a key) ----
CREATE NODE TABLE LexicalEntry(entry_id STRING, word_full STRING, lemma STRING, skeleton STRING, protected BOOLEAN, PRIMARY KEY(entry_id));
CREATE NODE TABLE Occurrence(occ_id STRING, word_full STRING, doc_sha256 STRING, page_idx INT64, sent_idx INT64, char_start INT64, char_end INT64, PRIMARY KEY(occ_id));
CREATE REL TABLE OCCURS_AS(FROM LexicalEntry TO Occurrence);
CREATE REL TABLE MAPPED_TO(FROM LexicalEntry TO Gestalt, session STRING, status STRING, provenance STRING);
