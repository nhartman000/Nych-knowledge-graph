"""Harvest job B (howto.* domains, 2026-11-03): pure rules + incremental, provisional ingest."""
import gzip, json, sys
from pathlib import Path
from nych3.harvest.howto import ingest
from nych3.store.tote_db import ToteDB

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "howto_harvest"))
import rules  # noqa: E402


def test_ranges_and_markers():
    r = rules.ranges("Gather two or three references, then wait 2-3 days.")
    assert [(x["min"], x["max"], x["unit"]) for x in r] == [(2, 3, "references"), (2, 3, "days")]
    assert rules.ranges("Call 1-800 now") == [] and rules.ranges("since 2019-2024 rules") == []
    assert rules.modality("remember", "Remember your PIN", "")[0] == "💭"
    assert rules.modality("decide", "Decide which unit fits", "")[0] == "🧠🗯"          # internal sense default
    assert rules.modality("keep", "Keep in mind the fee", "")[0] == "🧠🗯"
    assert rules.modality("make", "Make sure the lease is signed", "VERIFY_STATE", "sure the lease is signed")[0] == "🧠🗯"
    assert rules.modality("keep", "Keep your app updated", "")[0] == "🙌"
    assert rules.modality("check", "Check the lease", "")[0] == "👀²"
    q = rules.quote(" ".join(f"w{i}" for i in range(60)), "w30")
    assert len([w for w in q.split() if w != "…"]) == 25 and q.startswith("…") and q.endswith("…")


def _export(d, rows):
    with gzip.open(d / "howto_actions.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


def _row(i, dom, verb, obj, md, canonical="", rng=()):
    return dict(id=f"x{i}", domain=dom, platform="web", platform_hints="", site="cfpb", canonical=canonical, verb=verb, object=obj,
                obj_type="other", modality=md, modality_rule="t", amount_ranges=list(rng), condition_cues="", url=f"https://example.gov/{i}",
                retrieved="2026-11-03", title="t", section="Steps", step_no=i, kind="ol", quote=f"{verb} {obj}")


def test_howto_ingest_incremental(tmp_path):
    dbp = tmp_path / "t.kuzu"
    rows = [_row(1, "howto.rental", "gather", "two or three references", "🙌", rng=[{"min": 2, "max": 3, "unit": "references"}]),
            _row(2, "howto.rental", "decide", "which apartment fits", "🧠🗯"),
            _row(3, "howto.digital_life", "remember", "your recovery codes", "💭")]
    _export(tmp_path, rows)
    st = ingest(dbp, tmp_path)
    assert st["new_loops"] == 3 and st["new_source_refs"] == 3
    db = ToteDB(dbp)
    loops = db.q("MATCH (l:TOTELoop) WHERE l.loop_id STARTS WITH 'TL-HT-' RETURN l.loop_id AS id, l.status AS s, l.epistemic_status AS e, "
                 "l.modality_cell AS m, l.techniques AS t, l.domain AS d")
    assert all(r["s"] == "candidate" and r["e"] == "PROVISIONAL" for r in loops)
    cells = {r["m"] for r in loops}
    assert {"decide,🧠🗯 ; verify,👀²", "remember,💭 ; verify,👀²", "gather,🙌 ; verify,👀²"} == cells
    rent = [json.loads(r["t"])[0] for r in loops if r["m"].startswith("gather")][0]
    assert rent["amount_ranges"][0]["min"] == 2 and rent["amount_ranges"][0]["max"] == 3
    db.close()
    _export(tmp_path, rows + [_row(4, "howto.rental", "gather", "Two or three references", "🙌")])     # same loop, new source
    st2 = ingest(dbp, tmp_path)
    assert st2["new_loops"] == 0 and st2["new_source_refs"] == 1 and st2["existing_loops_extended"] == 1
    db = ToteDB(dbp)
    assert db.q("MATCH (s:SourceRef) WHERE s.ref_id STARTS WITH 'HT:' RETURN count(s) AS n")[0]["n"] == 4
    db.close()
