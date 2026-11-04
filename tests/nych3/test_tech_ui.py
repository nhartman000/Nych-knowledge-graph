"""tech.ui ingest (2026-11-02): canonical UI actions + instance loops, all provisional candidates with web provenance."""
import gzip, json
from nych3.harvest.tech_ui import ingest, norm_obj
from nych3.store.tote_db import ToteDB


def _export(d):
    tpl = lambda c: {"test_entry": "👀² verify precondition", "exit_gate": {"conditions": f"screen_shows({c})"}}
    acts = [{"canonical": c, "count": 2, "share_pct": 50.0, "platform_split": {"android": 2}, "top_surface_verbs": [["tap", 2]],
             "top_object_types": [["button", 2]], "examples": [], "tote_template": tpl(c)} for c in ("TAP_OR_CLICK", "VERIFY_STATE")]
    (d / "canonical_actions.json").write_text(json.dumps({"actions": acts}), encoding="utf-8")
    rows = [dict(id=f"{i}:0", canonical=c, param="", verb=v, object=o, obj_type="button", platform="android", platform_hints="", site="google_android",
                 url="https://support.google.com/android/answer/1", retrieved="2026-11-02", section="Steps", step_no=i, kind="ol", quote=f"{v} {o}",
                 direction="", count="", duration="", condition_cues="")
            for i, (c, v, o) in enumerate([("TAP_OR_CLICK", "tap", "the Settings"), ("TAP_OR_CLICK", "tap", "Settings"), ("VERIFY_STATE", "check", "the screen")])]
    with gzip.open(d / "ui_actions.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows) + "\n")


def test_tech_ui_ingest(tmp_path):
    _export(tmp_path); dbp = tmp_path / "t.kuzu"
    st = ingest(dbp, tmp_path)
    assert (st["canonical_loops"], st["instance_loops"], st["source_refs"]) == (2, 2, 3)   # 'the Settings' == 'Settings'
    db = ToteDB(dbp)
    rows = db.q("MATCH (l:TOTELoop) WHERE l.domain='tech.ui' RETURN l.status AS s, l.epistemic_status AS e, l.provenance AS p")
    assert all(r["s"] == "candidate" and r["e"] == "PROVISIONAL" and json.loads(r["p"])["review_status"] == "provisional_unreviewed" for r in rows)
    assert db.q("MATCH (i:TOTELoop)-[:INSTANCE_OF]->(c:TOTELoop {loop_id:'TL-UI-TAP_OR_CLICK'}) RETURN i.repeat_count AS n")[0]["n"] == 2
    assert db.get("TL-UI-TAP_OR_CLICK")["modality_cell"] == "tap_or_click,🙌 ; verify,👀²"
    assert db.get("TL-UI-VERIFY_STATE")["modality_cell"].startswith("verify_state,👀²")
    assert db.gate("G-UI-TAP_OR_CLICK")["conditions"] == ["screen_shows(TAP_OR_CLICK)"]
    assert db.lookup("tap", "settings")["method"] == "exact_action_object"
    assert all(len([w for w in r["t"].split() if w != "…"]) <= 25 for r in db.q("MATCH (s:SourceRef) RETURN s.sentence_text AS t"))
    db.close()


def test_norm_obj():
    assert norm_obj("the Settings app") == "settings app" and norm_obj("") == "*"
