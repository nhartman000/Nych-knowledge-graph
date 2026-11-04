"""QSON v1 ledger writer/verifier (spec: shared/qson/qson_v1.md, schema: shared/qson/qson.schema.json).

Hash-chain profile (QSON §12 "stronger profile", §16.7 canonicalization) — local profile 'kg-sha256-chain-v1':
  canonical(x)  = json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))  (same as mg8-runtime canonical.py)
  event_hash    = sha256(canonical(event minus the 'event_hash' key))
  previous_event_hash of event n = event_hash of event n-1 (i.e. sha256 of the prior event's canonical content);
  first event uses GENESIS (64 zeros).

SECURITY NOTE: the chain is UNKEYED (plain SHA-256, no HMAC/signature). verify() detects accidental corruption and
naive edits, but anyone who can rewrite the file can recompute every hash. Strong tamper-evidence claims require
external anchoring of the final event_hash (e.g. a signed/timestamped receipt or a write-once log held elsewhere);
none is implemented here.
Permit ordering: the permit is issued (event 'review'/permit_issued) before the state transition; the transition
('state_commit') consumes it single-use in the same Kuzu transaction that mirrors this ledger (kg_run.record_trace).
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[2] / 'shared' / 'qson' / 'qson.schema.json'
QSON_VERSION = '1.0'
PROFILE = 'kg-sha256-chain-v1'
GENESIS = '0' * 64
ACTOR = {'type': 'runtime', 'id': 'knowledge-graph/kg_run.py'}


def canonical(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def event_hash(ev: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in ev.items() if k != 'event_hash'}).encode()).hexdigest()


def build_ledger(run: dict, gate_id: str, file_id: str, timestamp: str) -> dict:
    rid = run['run_id']
    specs = [dict(event_type='external_input', input_state_id=run['input_state_id'], action='continue',
                  evidence={'utterance': run['text'], 'match_method': run['match_method'], 'matched_words': run['matched_words']}),
             dict(event_type='gate_attempt', file_id=file_id, gate_id=gate_id, input_state_id=run['input_state_id'],
                  result=run['result'], action={'PASS': 'continue', 'FAIL': 'stop', 'INTERMEDIATE': 'review'}[run['result']],
                  output_state_id=run['output_state_id'], operation=run['loop_id'], evidence=run['evaluation'])]
    if run['permit_id']:
        specs.append(dict(event_type='review', action='permit_issued', gate_id=gate_id, evidence={'permit_id': run['permit_id']}))
        specs.append(dict(event_type='state_commit', input_state_id=run['input_state_id'], output_state_id=run['output_state_id'],
                          action='continue', operation=run['loop_id'], evidence={'permit_id': run['permit_id'], 'permit_use': 'single-use; consumed atomically with this commit'}))
    events, prev = [], GENESIS
    for i, s in enumerate(specs, 1):
        ev = {'trace_id': f'trace-{rid}-{i:06d}', 'run_id': rid, 'sequence': i, 'actor': ACTOR, 'timestamp': timestamp,
              'previous_event_hash': prev, **s}
        if i > 1: ev['references'] = [events[-1]['trace_id']]
        ev['event_hash'] = event_hash(ev); prev = ev['event_hash']; events.append(ev)
    return {'qson_version': QSON_VERSION, 'run_id': rid, 'events': events,
            'metadata': {'hash_profile': PROFILE, 'utt_id': run['utt_id'], 'text': run['text']}}


def write(ledger: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    return path


def verify(ledger_or_path) -> list[str]:
    """Return list of problems; empty list = valid and untampered."""
    if isinstance(ledger_or_path, (str, Path)):
        try:
            led = json.loads(Path(ledger_or_path).read_text())
        except Exception as e:  # noqa: BLE001
            return [f'unreadable: {e}']
    else:
        led = ledger_or_path
    errs = []
    try:
        import jsonschema
        for e in jsonschema.Draft7Validator(json.loads(SCHEMA.read_text())).iter_errors(led):
            errs.append(f'schema: {e.message}')
    except ImportError:
        errs.append('jsonschema not installed; schema check skipped')
    prev = GENESIS
    for i, ev in enumerate(led.get('events', []), 1):
        tag = ev.get('trace_id', f'#{i}')
        if ev.get('sequence') != i: errs.append(f'{tag}: sequence {ev.get("sequence")} != {i}')
        if ev.get('run_id') != led.get('run_id'): errs.append(f'{tag}: run_id mismatch')
        if ev.get('previous_event_hash') != prev: errs.append(f'{tag}: previous_event_hash breaks chain')
        h = event_hash(ev)
        if ev.get('event_hash') != h: errs.append(f'{tag}: event_hash mismatch (content altered)')
        prev = ev.get('event_hash', h)
    return errs
