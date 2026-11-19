"""Tests for demo/ (procedure -> checklist -> gated audit log). No network, no model key."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))

from procedure_demo import audit, baseline, compare  # noqa: E402
from procedure_demo.checklist import build_checklist  # noqa: E402
from procedure_demo.common import canonical, load_source  # noqa: E402
from procedure_demo.exitchecks import CompileError, compile_check, is_machine_checkable  # noqa: E402

SRC = ROOT / "demo" / "sources"
NAMES = ["pg_verifybackup", "pg_checksums", "original_release_check_sop"]

mg8 = pytest.importorskip("mg8_runtime", reason="pip install -r demo/requirements.txt")


@pytest.mark.parametrize("name", NAMES)
def test_checklist_is_deterministic_and_schema_valid(name):
    runs = [build_checklist(SRC / f"{name}.txt") for _ in range(3)]
    assert len({canonical(r) for r in runs}) == 1
    assert compare.schema_valid(runs[0])
    assert runs[0]["steps"], "no steps produced"


@pytest.mark.parametrize("name", NAMES)
def test_every_step_traces_to_a_real_source_line(name):
    cl = build_checklist(SRC / f"{name}.txt")
    lines = dict(load_source(SRC / f"{name}.txt")["body"])
    for step in cl["steps"]:
        for n in step["source_lines"]:
            assert n in lines
        assert any(step["source_quote"].strip() in lines[n] for n in step["source_lines"])
    m = compare.step_metrics(cl, SRC / f"{name}.txt")
    assert m["traceable"] == m["steps"]


def test_pg_verifybackup_checks_come_from_the_source():
    cl = build_checklist(SRC / "pg_verifybackup.txt")
    verify = next(s for s in cl["steps"] if "pg_verifybackup /usr" in s["tote"]["operate"])
    types = {c["type"]: c["basis"] for c in verify["exit_checks"]}
    assert types["stdout_empty"] == "source_stated"      # "Don't print anything when ... verified"
    assert types["exit_code_equals"] == "convention_default"  # not stated in source: must be labelled
    assert verify["source_lines"] == [10, 11]


def test_threshold_limit_must_appear_in_cited_line():
    cl = build_checklist(SRC / "original_release_check_sop.txt")
    step = next(s for s in cl["steps"] if s["kind"] == "threshold")
    assert step["exit_checks"][0]["params"]["limit"] == 250
    assert compare.step_metrics(cl, SRC / "original_release_check_sop.txt")["numeric_limits_not_in_cited_lines"] == 0


def test_unmatched_lines_are_reported_not_dropped():
    cl = build_checklist(SRC / "pg_checksums.txt")
    assert {u["line"] for u in cl["unmapped_lines"]} == {10, 11, 12}


def test_machine_checkable_vs_human_review():
    cl = build_checklist(SRC / "pg_verifybackup.txt")
    kinds = {s["step_id"]: is_machine_checkable(s) for s in cl["steps"]}
    assert kinds == {"S9": True, "S10": True, "S12": False}


def test_compile_rejects_bad_params_and_unknown_types():
    with pytest.raises(CompileError):
        compile_check("S1", {"type": "exit_code_equals", "params": {"value": "0"}})
    with pytest.raises(CompileError):
        compile_check("S1", {"type": "numeric_at_most", "params": {"limit": True}})
    with pytest.raises(CompileError):
        compile_check("S1", {"type": "vibes", "params": {}})


def _outcomes(manifest):
    return {r["step_id"]: r["outcome"] for r in manifest["results"]}


def test_scenarios_produce_pass_fail_and_intermediate(tmp_path):
    cl = build_checklist(SRC / "pg_verifybackup.txt")
    ok = audit.run_audit(cl, "all-pass", tmp_path / "a")
    assert set(_outcomes(ok).values()) == {"PASS"}
    bad = audit.run_audit(cl, "one-fails", tmp_path / "b")
    assert _outcomes(bad)["S9"] == "FAIL" and not next(r for r in bad["results"] if r["step_id"] == "S9")["committed"]
    missing = audit.run_audit(cl, "evidence-missing", tmp_path / "c")
    assert _outcomes(missing)["S9"] == "INTERMEDIATE"   # no evidence must never pass
    assert not next(r for r in missing["results"] if r["step_id"] == "S9")["committed"]


def test_human_evidence_cannot_satisfy_a_tool_check(tmp_path):
    """Provenance matters: a tool check fed 'human' evidence must not pass."""
    from mg8_runtime.gates import Registry
    from mg8_runtime.runtime import Runtime
    from procedure_demo.exitchecks import compile_step

    cl = build_checklist(SRC / "pg_verifybackup.txt")
    step = next(s for s in cl["steps"] if s["step_id"] == "S9")
    rt = Runtime(tmp_path / "r.sqlite", Registry())
    run = rt.create_run({"step_done": False}, [compile_step(step)], actors=["operator"], writable_paths=["/step_done"])
    p = rt.propose(run, "operator", {"step_done": True}, base_version=0)
    rt.record_evidence(p, "S9", {"exit_code": 0}, kind="human")
    assert rt.evaluate(p)["outcome"] == "INTERMEDIATE"


def test_audit_chain_verifies_and_detects_tampering(tmp_path):
    cl = build_checklist(SRC / "pg_verifybackup.txt")
    audit.run_audit(cl, "all-pass", tmp_path)
    ok, problems = audit.verify_audit(tmp_path)
    assert ok and not problems
    target = tmp_path / "S10.qson"
    doc = json.loads(target.read_text())
    doc["events"][1]["evidence"] = {"tampered": True}
    target.write_text(json.dumps(doc))
    ok, problems = audit.verify_audit(tmp_path)
    assert not ok and any("S10.qson" in p for p in problems)


def test_manifest_tampering_is_detected(tmp_path):
    cl = build_checklist(SRC / "pg_checksums.txt")
    audit.run_audit(cl, "all-pass", tmp_path)
    m = json.loads((tmp_path / "audit_manifest.json").read_text())
    m["scenario"] = "doctored"
    (tmp_path / "audit_manifest.json").write_text(json.dumps(m))
    ok, problems = audit.verify_audit(tmp_path)
    assert not ok and "manifest hash mismatch" in problems


def test_compare_metrics_on_known_inputs():
    good = build_checklist(SRC / "pg_verifybackup.txt")
    bad_trace = json.loads(json.dumps(good))
    bad_trace["steps"][0]["source_quote"] = "text that is not in the source"
    invented = json.loads(json.dumps(good))
    invented["steps"][0]["exit_checks"] = [{"type": "numeric_at_most", "params": {"limit": 99}, "basis": "source_stated"}]
    out = compare.summarize({"x": [good, bad_trace, invented, "ERROR: HTTP 500", "not json"]},
                            {"x": SRC / "pg_verifybackup.txt"})
    t = out["total"]
    assert t["api_errors"] == 1            # infrastructure errors are excluded, never counted as model failures
    assert t["runs"] == 4 and t["schema_valid_runs"] == 3
    assert t["traceable"] == 3 + 2 + 3
    assert t["numeric_limits_not_in_cited_lines"] == 1


def test_baseline_without_key_is_pending_not_invented(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert baseline.have_key() is False
    prompt = baseline.build_prompt(SRC / "pg_verifybackup.txt")
    assert "10| $ pg_verifybackup" in prompt and "exit_code_equals" in prompt
