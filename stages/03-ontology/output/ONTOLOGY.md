# Ontology map
**Single source:** `stages/02-schema/output/schema.cypher`. `ontology.json` is generated from it. This page is the human view. **NEW** = proposed here, not in any source repo.

```mermaid
graph LR
  TOTELoop -->|USES_GESTALT role| Gestalt
  TOTELoop -->|HAS_STEP| Step
  Step -->|NEXT_ON_MATCH / NEXT_ON_MISMATCH| Step
  Step -->|USES_OPERATOR| Operator
  Sense -->|SENSE_OF NEW| Gestalt
  Span -->|SPANS NEW| Gestalt
  Utterance -->|GROUNDED_TO| Gestalt
  Utterance -->|SELECTED_LOOP| TOTELoop
  Gate -->|GUARDS NEW| TOTELoop
  Gate -->|ISSUES NEW| Permit
  Permit -->|AUTHORIZES NEW| TOTELoop
  GSTState -->|TRANSITIONS_TO NEW| GSTState
  QSONTrace -->|INPUT_STATE / OUTPUT_STATE NEW| GSTState
  QSONTrace -->|RECORDS NEW| Gate
  QSONTrace -->|TRACE_OF| Utterance
  QSONTrace -->|PRECEDES| QSONTrace
```

| Node | Fields from | Notes |
|---|---|---|
| Gestalt, Sense, Span, Operator, TOTELoop, Step, Utterance | poc / TOTE DB / nych registry | `Gestalt.origin` NEW |
| Gate | g8son schema: gate_id, order, type, conditions, outcomes; file_id (g8son root) | |
| Permit | mg8-runtime runtime.py: id→permit_id, run_id, proposal_id, status, purpose, expires_at, version, epoch, evaluation_digest, actor, operation | |
| GSTState | gst spec: state_id, gst_version, internal, external, continuity, intent, outcome_expectation, constraints | nested objects stored as JSON strings |
| QSONTrace | qson schema event fields; actor split to actor_type/actor_id | replaces TraceEvent |

**Sense/Span → Gestalt linking:** registry `gestalt` values are glyphs. Only `✅` matches a TOTE-DB Gestalt glyph; the other registry glyphs get a Gestalt node with `origin='registry_glyph'` (NEW) so every Sense/Span is connected.
