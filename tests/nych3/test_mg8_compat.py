"""Compatibility with mg8-engine's OWN code (installed from /workspace/mg8-engine, no-deps)."""
import json
import pytest

mg8 = pytest.importorskip("mg8_engine")
from mg8_engine.models import Gst
from mg8_engine.keeper import load_context_gst
from mg8_engine.core import load_mg8, execute_ork
from mg8_engine.pipeline import build_mapping_prompt, validate_mapping_plan, PipelineError
from nych3.llm.gestalt_call import build_request, MockProvider, validate_with_mg8
from nych3.store.tote_db import ToteDB


def test_gst_validates_with_mg8_model(peter):
    _, g, gp, _ = peter
    m = Gst.model_validate(json.loads(gp.read_text(encoding="utf-8")))
    assert m.gst_version == "1.0" and m.domain == g["domain"] and m.narrative_tense == "past"
    assert m.model_extra["nych3"]["source"]["story"] == g["nych3"]["source"]["story"]
    k = load_context_gst(gp)
    assert k.state_id == g["state_id"]


def test_mg8_canonical_unit_loads_and_runs(peter, tmp_path, db_path):
    _, g, gp, _ = peter
    unit = tmp_path / "unit"; (unit / "state").mkdir(parents=True); (unit / "gates").mkdir()
    (unit / "state" / "peter.gst").write_text(gp.read_text(encoding="utf-8"), encoding="utf-8")
    db = ToteDB(db_path)
    gate = db.gate(g["nych3"]["tote"]["instances"][0]["exit"]["gate"]["gate_id"])
    (unit / "gates" / "exit.g8son").write_text(json.dumps({"g8son_version": "1.0", "file_id": gate["file_id"], "gates": [gate]}), encoding="utf-8")
    (unit / "flow.ork").write_text(json.dumps({"flow": [gate["gate_id"]]}), encoding="utf-8")
    (unit / "peter.mg8").write_text(json.dumps({"mg8_version": "1.0", "unit_id": "nych3.peter", "entry": "flow.ork",
                                                 "state": ["state/peter.gst"], "gates": ["gates/exit.g8son"], "trace": "trace/run.qson"}), encoding="utf-8")
    u = load_mg8(unit / "peter.mg8")
    assert u.gst.state_id == g["state_id"]
    out = execute_ork(u)
    assert [e.gate_id for e in out.qson.entries] == [gate["gate_id"]]


def test_mg8_mapping_prompt_and_validator(peter):
    _, g, *_ = peter
    prompt = build_mapping_prompt(g)
    assert "stars" in prompt and "Peter" in prompt
    plan = MockProvider().propose(build_request(g))
    assert validate_with_mg8(plan, g) == "passed"
    with pytest.raises(PipelineError, match="protected"):
        validate_mapping_plan({"mappings": [{"word": "Peter", "symbol_id": "g.ptr", "glyph": "◌"}]}, g)
