"""Compile exit checks into G8SON gate documents that mg8-runtime can evaluate mechanically."""
from .common import MACHINE_TYPES, evidence_paths


class CompileError(ValueError):
    pass


def compile_check(step_id, check):
    """One exit check -> one G8SON condition (path/op/value + required evidence provenance)."""
    kind = check["type"]
    params = check.get("params") or {}
    if kind not in evidence_paths(step_id):
        raise CompileError(f"unknown check type {kind!r}")
    path = evidence_paths(step_id)[kind]
    if kind == "exit_code_equals":
        value = params.get("value")
        if type(value) is not int:
            raise CompileError("exit_code_equals needs integer params.value")
        return {"path": path, "op": "eq", "value": value, "evidence_kind": "tool"}
    if kind == "stdout_empty":
        return {"path": path, "op": "eq", "value": True, "evidence_kind": "tool"}
    if kind == "numeric_at_most":
        limit = params.get("limit")
        if type(limit) not in (int, float) or isinstance(limit, bool):
            raise CompileError("numeric_at_most needs numeric params.limit")
        return {"path": path, "op": "lte", "value": limit, "evidence_kind": "tool"}
    if kind == "human_review":
        return {"path": path, "op": "eq", "value": True, "evidence_kind": "human"}
    raise CompileError(f"unknown check type {kind!r}")


def compile_step(step):
    sid = step["step_id"]
    conds = [compile_check(sid, c) for c in step["exit_checks"]]
    return {"g8son_version": "1.0", "file_id": f"exit.{sid}", "gates": [{
        "gate_id": f"exit_{sid}".replace("-", "_"), "type": "AND", "conditions": conds,
        "outcomes": {"PASS": "commit", "FAIL": "repeat", "INTERMEDIATE": "review"}}]}


def is_machine_checkable(step):
    """True if at least one exit check is a machine type AND the whole step compiles to a valid gate."""
    if not any(c.get("type") in MACHINE_TYPES for c in step.get("exit_checks", [])):
        return False
    try:
        from mg8_runtime.gates import GateSet
        GateSet(compile_step(step))
        return True
    except (CompileError, ValueError, KeyError, TypeError):
        return False
