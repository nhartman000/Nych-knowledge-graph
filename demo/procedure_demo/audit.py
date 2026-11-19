"""Run every checklist step's exit checks through mg8-runtime (gates, single-use permits, hash-chained QSON log).

Evidence is SIMULATED by scenario because the demo does not execute the procedure's commands
(pg_verifybackup needs a PostgreSQL cluster). What is real: the gate evaluation, the permit, the commit
and the tamper-evident log.
"""
import json
import tempfile
from pathlib import Path

from .common import canonical, evidence_paths, sha256_text
from .exitchecks import compile_step, is_machine_checkable

SCENARIOS = ("all-pass", "one-fails", "evidence-missing")


def make_evidence(checklist, scenario):
    """Deterministic simulated evidence: {step_id: [(key, value, kind)]}. Returns (evidence, description)."""
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    ev, broken = {}, None
    for step in checklist["steps"]:
        good = {}
        for c in step["exit_checks"]:
            t = c["type"]
            if t == "exit_code_equals":
                good["exit_code"] = (c["params"]["value"], "tool")
            elif t == "stdout_empty":
                good["stdout_empty"] = (True, "tool")
            elif t == "numeric_at_most":
                good["value"] = (c["params"]["limit"], "tool")
            elif t == "human_review":
                good["approved"] = (True, "human")
        ev[step["step_id"]] = good
    machine = [s for s in checklist["steps"] if is_machine_checkable(s)]
    if scenario == "one-fails" and machine:
        broken = machine[0]["step_id"]
        first = machine[0]["exit_checks"][0]
        if first["type"] == "exit_code_equals":
            ev[broken]["exit_code"] = (first["params"]["value"] + 1, "tool")
        elif first["type"] == "stdout_empty":
            ev[broken]["stdout_empty"] = (False, "tool")
        else:
            ev[broken]["value"] = (first["params"]["limit"] + 1, "tool")
    if scenario == "evidence-missing" and machine:
        broken = machine[0]["step_id"]
        ev[broken] = {}
    return ev, broken


def run_audit(checklist, scenario, out_dir):
    """Returns a report dict. Writes <out_dir>/runtime.sqlite, <step>.qson per step, audit_manifest.json."""
    from mg8_runtime.gates import Registry
    from mg8_runtime.runtime import Runtime

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    evidence, broken = make_evidence(checklist, scenario)
    runtime = Runtime(out / "runtime.sqlite", Registry())
    results = []
    for step in checklist["steps"]:
        sid = step["step_id"]
        run = runtime.create_run({"step_done": False}, [compile_step(step)], actors=["operator"],
                                 writable_paths=["/step_done"], max_attempts=3)
        proposal = runtime.propose(run, "operator", {"step_done": True}, base_version=0)
        _record(runtime, proposal, sid, evidence[sid])
        outcome = runtime.evaluate(proposal)["outcome"]
        committed = False
        if outcome == "PASS":
            runtime.commit(runtime.authorize(proposal))
            committed = True
        qson_path = out / f"{sid}.qson"
        runtime.store.export_qson(run, qson_path)
        events = json.loads(qson_path.read_text())["events"]
        results.append({"step_id": sid, "outcome": outcome, "committed": committed,
                        "machine_checkable": is_machine_checkable(step), "events": len(events),
                        "head_event_hash": events[-1]["event_hash"], "qson": qson_path.name})
    manifest = {"checklist_sha256": checklist["checklist_sha256"], "scenario": scenario,
                "simulated_evidence_step": broken, "results": results}
    manifest["manifest_sha256"] = sha256_text(canonical({k: v for k, v in manifest.items()}))
    (out / "audit_manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def _record(runtime, proposal, sid, items):
    """One receipt per step, stored under the step id so gate paths are /evidence/<step>/<field>."""
    if not items:
        return  # evidence-missing scenario: nothing is recorded, the gate must answer INTERMEDIATE
    kinds = {kind for _v, kind in items.values()}
    if len(kinds) != 1:
        raise ValueError(f"step {sid} mixes evidence provenance kinds {sorted(kinds)}")
    runtime.record_evidence(proposal, sid, {k: v for k, (v, _kind) in items.items()}, kind=kinds.pop())


def verify_audit(out_dir):
    """Independently re-verify every exported chain and the manifest. Returns (ok, problems)."""
    from mg8_runtime import canonical as c

    out = Path(out_dir)
    problems = []
    manifest = json.loads((out / "audit_manifest.json").read_text())
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if sha256_text(canonical(body)) != manifest["manifest_sha256"]:
        problems.append("manifest hash mismatch")
    for r in manifest["results"]:
        events = json.loads((out / r["qson"]).read_text())["events"]
        prev = None
        for e in events:
            unsigned = dict(e)
            h = unsigned.pop("event_hash", None)
            if e.get("previous_event_hash") != prev:
                problems.append(f"{r['qson']}: broken chain at sequence {e.get('sequence')}")
                break
            if c.digest(unsigned) != h:
                problems.append(f"{r['qson']}: bad event hash at sequence {e.get('sequence')}")
                break
            prev = h
        else:
            if prev != r["head_event_hash"]:
                problems.append(f"{r['qson']}: head hash differs from manifest")
    return (not problems), problems
