"""Review r2 regressions: lookup context filters + platform collisions (finding 3), authority registry (6),
duplicate occurrence mappings (7), quote definition and locator_quality."""
import gzip, json, pytest
from nych3.harvest.tech_ui import ingest, context_conflicts, locator_quality
from nych3.store.tote_db import ToteDB
from nych3.llm.gestalt_call import build_request, MockProvider, validate_plan, ValidationError


def _export(d, rows):
    tpl = lambda c: {"test_entry": "👀² verify precondition", "exit_gate": {"conditions": f"screen_shows({c})"}}
    acts = [{"canonical": c, "count": 1, "share_pct": 1.0, "platform_split": {}, "top_surface_verbs": [], "top_object_types": [],
             "examples": [], "tote_template": tpl(c)} for c in ("TAP_OR_CLICK", "SELECT_ITEM")]
    (d / "canonical_actions.json").write_text(json.dumps({"actions": acts}), encoding="utf-8")
    base = dict(param="", obj_type="button", platform_hints="", site="s", url="https://example.invalid/a", retrieved="2026-11-02",
                section="Steps", step_no=1, kind="ol", quote="tap Settings", direction="", count="", duration="", condition_cues="")
    with gzip.open(d / "ui_actions.jsonl.gz", "wt", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps(dict(base, id=f"{i}:0", **r)) + "\n")


ROWS = [dict(canonical="TAP_OR_CLICK", verb="tap", object="Settings", platform="android"),
        dict(canonical="TAP_OR_CLICK", verb="tap", object="the Settings", platform="windows", direction="up"),   # same group, 2nd platform
        dict(canonical="TAP_OR_CLICK", verb="tap", object="Settings", platform="android", direction="down", section="", step_no=None),
        dict(canonical="SELECT_ITEM", verb="tap", object="Settings", platform="ios")]                              # same lookup key, other group


@pytest.fixture
def ui_db(tmp_path):
    _export(tmp_path, ROWS); dbp = tmp_path / "t.kuzu"
    st = ingest(dbp, tmp_path)
    db = ToteDB(dbp); yield db, st; db.close()


def test_conflict_counts(ui_db):
    _, st = ui_db
    cc = st["context_conflicts"]
    assert (cc["groups"], cc["multi_platform"], cc["conflicting_modifier_any"], cc["platform_or_modifier_conflict"]) == (2, 1, 1, 1)
    assert cc["conflicting_modifier_by_field"]["direction"] == 1
    assert st["locator_quality"] == {"section+step": 3, "url_only": 1}


def test_lookup_without_context_unchanged(ui_db):
    db, _ = ui_db
    r = db.lookup("tap", "settings")
    assert r["method"] == "exact_action_object" and len(r["alternatives"]) == 1
    assert r["context"] == {"requested": {"domain": None, "platform": None}, "used": False, "matched": None, "fell_back": False}


def test_lookup_prefers_platform_match_across_collision(ui_db):
    db, _ = ui_db
    plain = db.lookup("tap", "settings")["match"]["loop_id"]
    for plat, want_canon in (("ios", "SELECT_ITEM"), ("android", "TAP_OR_CLICK"), ("windows", "TAP_OR_CLICK")):
        r = db.lookup("tap", "settings", platform=plat)
        assert r["context"]["matched"] is True and r["context"]["fell_back"] is False
        assert r["match"]["techniques"][0]["canonical"] == want_canon
        assert plat in r["match"]["techniques"][0]["platforms"]
    assert {db.lookup("tap", "settings", platform=p)["match"]["loop_id"] for p in ("ios", "android")} >= {plain}


def test_lookup_falls_back_and_records_it(ui_db):
    db, _ = ui_db
    plain = db.lookup("tap", "settings")
    r = db.lookup("tap", "settings", platform="mac")
    assert r["context"]["fell_back"] is True and r["context"]["matched"] is False
    assert r["match"]["loop_id"] == plain["match"]["loop_id"] and r["alternatives"] == plain["alternatives"]
    r = db.lookup("tap", "settings", domain="cooking")
    assert r["context"]["fell_back"] is True
    r = db.lookup("tap", "settings", domain="tech.ui", platform="ios")
    assert r["context"]["matched"] is True and r["match"]["techniques"][0]["canonical"] == "SELECT_ITEM"


def test_multi_platform_group_matches_every_platform(ui_db):
    db, _ = ui_db
    a = db.lookup("tap", "settings", platform="android")["match"]["loop_id"]
    w = db.lookup("tap", "settings", platform="windows")["match"]["loop_id"]
    assert a == w   # one instance group spanning android + windows


def test_context_conflicts_unit():
    g = {("A", "tap", "x"): [dict(platform="android", direction="", count="", duration="", param=""),
                             dict(platform="android", direction="", count="2", duration="", param="")],
         ("A", "tap", "y"): [dict(platform="android", direction="up", count="2", duration="", param=""),
                             dict(platform="ios", direction="up", count="3", duration="", param="")]}
    cc = context_conflicts(g)
    assert cc["multi_platform"] == 1 and cc["conflicting_modifier_by_field"]["count"] == 1 and cc["platform_or_modifier_conflict"] == 1


def test_locator_quality():
    assert locator_quality({"section": "S", "step_no": 2}) == "section+step"
    assert locator_quality({"section": " ", "step_no": None}) == "url_only"
    assert locator_quality({"section": "", "step_no": 3}) == "step_only"


def test_authority_registry(db_path):
    db = ToteDB(db_path)
    lid = db.q("MATCH (l:TOTELoop) WHERE l.status='candidate' RETURN l.loop_id AS l LIMIT 1")
    if not lid:
        pytest.skip("no candidate row in seed store")
    lid = lid[0]["l"]
    with pytest.raises(ValueError, match="authority metadata"):
        db.promote(lid, "  ")
    db.authority_registry = {"Dr. Reviewer"}
    with pytest.raises(ValueError, match="not in the authority registry"):
        db.promote(lid, "Someone Else")
    db.promote(lid, "Dr. Reviewer")
    assert db.get(lid)["status"] == "canonical"
    db.close()


def test_duplicate_occurrence_mapping_rejected(peter):
    req = build_request(peter[1])
    plan = MockProvider().propose(req)
    plan["mappings"].append(dict(plan["mappings"][0]))
    with pytest.raises(ValidationError, match="duplicate mapping"):
        validate_plan(plan, req)


def test_quote_definition_in_shipped_export():
    """<= 25 source tokens; '…' markers (at most 2) are not content words, so stored quotes can be 27 tokens."""
    from nych3.config import SHARED
    for name in ("ui_actions.jsonl.gz", "ui_actions_unmapped.jsonl.gz"):
        for line in gzip.open(SHARED / "data" / "tech_ui" / name, "rt", encoding="utf-8"):
            q = json.loads(line)["quote"].split()
            assert len([w for w in q if w != "…"]) <= 25 and len(q) <= 27   # source text may itself contain "…"
