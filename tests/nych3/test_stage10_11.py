import json, pytest
from nych3.llm.gestalt_call import build_request, MockProvider, validate_plan, fill_cells, persist, ValidationError
from nych3.paths import candidate_paths
from nych3.store.tote_db import ToteDB


def test_request_is_mapping_only(peter):
    req = build_request(peter[1])
    assert req["task"] == "ASSIGN_GESTALTS_ONLY"
    s = json.dumps(req).lower()
    assert "prun" not in s and "g8son" not in s and ".ork" not in s


def test_mock_validate_fill_persist(peter, db_path):
    g = peter[1]
    req = build_request(g)
    acc = validate_plan(MockProvider().propose(req), req)
    assert all(a["symbol_id"].endswith("." + a["skeleton"]) for a in acc)
    row = fill_cells(g["nych3"]["tote"]["instances"][0]["row"], acc)
    assert row["object"].startswith("stars,gst3.mock.") and row["object"].endswith(".strs")
    assert row["actor"] == "Peter,[protected]"
    db = ToteDB(db_path)
    with pytest.raises(PermissionError):
        persist(db, acc, g, "s1")
    assert persist(db, acc, g, "s1", approved=True) == len(acc)
    r = db.q("MATCH (e:LexicalEntry {word_full:'stars'})-[:MAPPED_TO]->(x:Gestalt) RETURN x.gestalt_id AS g")
    assert r and r[0]["g"].endswith(".strs")


def test_bad_skeleton_and_operator_glyph_rejected(peter):
    req = build_request(peter[1])
    plan = MockProvider().propose(req)
    plan["mappings"][0]["symbol_id"] = "g.wrong"
    with pytest.raises(ValidationError, match="skeleton"):
        validate_plan(plan, req)
    plan = MockProvider().propose(req)
    plan["mappings"][0]["glyph"] = "🫶"
    with pytest.raises(ValidationError, match="operator"):
        validate_plan(plan, req)


def _floats(x):
    if isinstance(x, float):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from _floats(v)
    elif isinstance(x, list):
        for v in x:
            yield from _floats(v)


def test_paths_ordered_classes_no_numbers(peter):
    res = candidate_paths(peter[1])
    assert list(_floats(res)) == []
    hill = next(c for c in res["candidates"] if c["template_id"] == "TL-APPROACH-LOCATION-001")
    assert [(p["technique"], p["status"], p["confidence"]["value"]) for p in hill["paths"]] == [
        ("walking", "default", "high"), ("biking", "latent", "latent")]
    assert any(p["reason"].startswith("no template") for p in res["pruned"])
