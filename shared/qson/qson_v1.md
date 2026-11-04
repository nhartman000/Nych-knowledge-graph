# QSON Specification v1

**Author:** Nicholas Hartman / American Milestone Inc.  
**Scope:** immutable/auditable execution-event tracing for the MG8 file family

## 1. Purpose

QSON records realized execution events. It is the provenance layer that answers:

- what state was presented,
- what gate was attempted,
- which exact execution occurrence was involved,
- what result was produced,
- what action or branch was selected,
- what resulting state was produced,
- what later review, override, or correction occurred.

QSON does not define the canonical state model, gate language, or orchestration grammar. Those belong to `.gst`, `.g8son`, and `.ork` respectively.

## 2. Event identity

Every attempted gate execution MUST receive a unique `trace_id`.

The identity model is:

```text
file_id != gate_id != trace_id
```

A repeated execution of the same gate therefore creates a new event identity even when the gate definition and input state are unchanged.

A `run_id` MAY group multiple events that belong to one larger pipeline or `.mg8` execution without replacing the event-level `trace_id`.

## 3. Event ordering

A QSON ledger MUST preserve event order.

A deterministic profile SHOULD carry an integer `sequence` that is unique within a run:

```text
run_id + sequence
```

This prevents ambiguity when timestamps have insufficient precision or when more than one event occurs at the same wall-clock time.

## 4. Minimum trace event

A minimum event contains:

```json
{
  "trace_id": "trace-000001",
  "run_id": "run-001",
  "sequence": 1,
  "event_type": "gate_attempt",
  "file_id": "example.eligibility.001",
  "gate_id": "object_confidence",
  "input_state_id": "state-0001",
  "result": "PASS",
  "action": "continue",
  "output_state_id": "state-0002",
  "actor": {
    "type": "runtime",
    "id": "mg8-runtime"
  },
  "timestamp": "2026-08-22T05:00:00Z"
}
```

`event_type` is REQUIRED on every event (schema `required`); the allowed values are the `event_type` enum in `schema/qson.schema.json`.

`output_state_id` MAY be absent when the gate attempt does not produce a new state.

## 5. Result space

When QSON records a G8SON gate evaluation, `result` MUST be one of:

```text
PASS
FAIL
INTERMEDIATE
```

QSON records the result; it does not redefine its semantics.

## 6. State linkage

Input and output state references point to `.gst` state identities.

Conceptually:

```text
input_state_id
      ↓
gate execution
      ↓
trace_id
      ↓
result/action
      ↓
output_state_id
```

This preserves the connection between state chronology and realized execution.

## 7. Gate linkage

A QSON event SHOULD retain both:

- `file_id`
- `gate_id`

This prevents a gate identifier from being ambiguous when multiple `.g8son` files use similar local names.

## 8. Action / branch linkage

`action` records the continuation selected after the gate result, such as:

```text
continue
stop
review
branch:<identifier>
retry
```

The QSON standard does not prescribe the full routing vocabulary. `.ork` or the active execution profile defines the valid action targets.

## 9. Actor / evaluator

A trace event MAY identify the actor or evaluator that produced or authorized the event.

Examples include:

- deterministic runtime,
- human reviewer,
- external tool,
- model-assisted evaluator,
- system service.

The actor record should distinguish **who/what evaluated** from **who/what later overrode** the result.

## 10. Override semantics

An override MUST NOT silently rewrite the original event.

A new event should reference the event it supersedes or overrides:

```json
{
  "trace_id": "trace-000002",
  "event_type": "override",
  "references": ["trace-000001"],
  "action": "continue",
  "actor": {
    "type": "human",
    "id": "reviewer-1"
  }
}
```

This preserves both the original gate result and the later decision.

## 11. Correction / supersession

If a stored event is discovered to contain incorrect metadata, the ledger should append a correction/supersession event rather than mutating historical content.

A profile may use fields such as:

- `references`
- `supersedes`
- `reason`

provided their semantics are explicit.

## 12. Append-only semantics

QSON is semantically append-only.

This means historical events are treated as committed execution claims. It does not require a particular storage engine or cryptographic mechanism.

A stronger profile MAY add:

- event hashes,
- previous-event hashes,
- digital signatures,
- Merkle roots,
- external timestamping/notarization.

These mechanisms are optional until separately specified.

## 13. Evidence and metadata

A trace event MAY carry or reference evidence such as:

- gate inputs,
- output summaries,
- external measurement references,
- validation results,
- error information,
- human-review rationale,
- runtime version,
- relevant configuration identifiers.

Large evidence artifacts SHOULD normally be referenced rather than embedded when doing so improves reproducibility and integrity.

## 14. Event types

The minimum profile recognizes execution events. Extended profiles MAY distinguish event types such as:

```text
gate_attempt
override
correction
state_commit
external_input
runtime_error
review
```

No event type should erase the event it refers to.

## 15. Relationship to CIIU

Where a QSON event represents a realized transformation, it can carry the runtime evidence corresponding to:

\[
CIIU=(SR_{in},T,SR_{out},M)
\]

Mapping conceptually:

```text
input_state_id  → SR_in
operation       → T
output_state_id → SR_out
QSON metadata   → M
```

This is an interoperability relationship, not a claim that QSON and TCTA are the same framework.

## 16. Deterministic trace requirements

For reproducible event ordering, an MG8/QSON runtime SHOULD define:

1. unique `trace_id` generation,
2. unique `run_id + sequence` ordering,
3. canonical state identifiers,
4. actor identity rules,
5. timestamp normalization,
6. override/correction semantics,
7. serialization canonicalization if hashes/signatures are used.

## 17. Scope boundary

This specification defines the QSON execution/audit trace contract.

It does not fully specify `.gst`, `.g8son`, `.ork`, `.mg8`, or `.mg8pk`, and it does not claim cryptographic immutability unless a stronger profile explicitly implements and validates it.
