import json
import pytest
from nych3.harvest.harvester import Harvester
from nych3.harvest.source import paragraphs
from nych3.store.tote_db import ToteDB

HTML_A = """<html><body><p>*** START OF THE PROJECT GUTENBERG EBOOK TEST ***</p>
<h2>Planing</h2>
<p><span class="pagenum" id="Page12">[12]</span>Plane the board until the edge is square. Hold the plane with both hands.</p>
<p>The plane is pressed to the board with the right hand. "Is it square?" he asked. Is the edge true?</p>
<p><span class="pagenum" id="Page13">[13]</span>Wood is a useful material. Plane the board until the edge is square.</p>
<p>Cut the board with a saw and sand the edge.</p>
<p>*** END OF THE PROJECT GUTENBERG EBOOK TEST ***</p></body></html>"""
HTML_B = """<html><body><p>*** START OF THE PROJECT GUTENBERG EBOOK B ***</p>
<p>Stir the soup for 10 minutes. Cut the board with a saw.</p>
<p>*** END OF THE PROJECT GUTENBERG EBOOK B ***</p></body></html>"""
BOOK_A = {"book_id": "tA", "gutenberg_id": 1, "title": "A", "isbn": None, "isbn_status": "none_exists_pre_isbn", "domain": "craft.test",
          "page_mode": "printed", "page_marker": "span.pagenum", "url": "x"}
BOOK_B = {"book_id": "tB", "gutenberg_id": 2, "title": "B", "isbn": None, "isbn_status": "none_found_in_source", "domain": "cooking.test",
          "page_mode": "derived", "page_marker": None, "url": "y"}
HTML = {"tA": HTML_A, "tB": HTML_B}


@pytest.fixture
def H(tmp_path):
    db = tmp_path / "h.kuzu"
    ToteDB(db, rebuild=True)
    def make():
        return Harvester(db, tmp_path / "out", fetcher=lambda b: HTML[b["book_id"]])
    return make


def rows(h):
    return h.db.q("MATCH (l:TOTELoop) WHERE l.loop_id STARTS WITH 'TL-H-' RETURN l.loop_id AS id, l.action_lemma AS a, l.object_lemma AS o, "
                  "l.repeat_count AS n, l.status AS s, l.actor_cell AS actor, l.modality_cell AS m, l.exit_gate_id AS g ORDER BY id")


def test_pages_printed_and_derived():
    pa = paragraphs(HTML_A, BOOK_A)
    assert [p["page"] for p in pa if "Plane the board" in p["text"]] == ["12", "13"]
    assert all(p["page_kind"] == "printed" for p in pa if p["page"] in ("12", "13"))
    pb = paragraphs(HTML_B, BOOK_B)
    assert pb[0]["page"] == "1" and pb[0]["page_kind"] == "derived" and "2000" in pb[0]["page_method"]


def test_harvest_extracts_skips_and_dedupes(H):
    h = H()
    st = h.run(books=[BOOK_A])
    assert st["skipped_dialogue"] == 1 and st["skipped_question"] == 1
    assert st["non_action"] >= 2          # heading 'Planing' + 'Wood is a useful material.'
    r = {(x["a"], x["o"]): x for x in rows(h)}
    plane = r[("plane", "board")]
    assert plane["n"] == 2 and plane["s"] == "candidate" and plane["actor"] == "you(implied),"
    assert st["loops_repeat"] >= 1
    gate = h.db.gate(plane["g"])
    assert gate["conditions"][0].startswith("until the edge is square") and "[explicit]" in gate["conditions"][0]
    assert r[("hold", "plane")]["m"] == "Hold,🙌"
    assert r[("press", "plane")]["actor"].startswith("agent(implied")
    assert ("cut", "board") in r and ("sand", "edge") in r   # coordinated imperatives split
    refs = h.db.q("MATCH (l:TOTELoop {loop_id:$l})-[:SOURCED_FROM]->(s:SourceRef) RETURN s.isbn AS i, s.isbn_status AS st, s.page AS p, "
                  "s.page_kind AS k, s.fallback_gutenberg_id AS g ORDER BY p", {"l": plane["id"]})
    assert [(x["i"], x["p"], x["k"], x["g"]) for x in refs] == [("", "12", "printed", "1"), ("", "13", "printed", "1")]
    stats = json.loads(next((h.out / "runs").glob("*.json")).read_text())
    assert stats["loops_new"] == st["loops_new"] and "no_match" in stats and "errors" in stats


def test_resumable_and_at_most_once(H):
    h1 = H(); s1 = h1.run(books=[BOOK_A], max_sentences=3); h1.close()
    h2 = H(); s2 = h2.run(books=[BOOK_A])
    total = s1["sentences_seen"] + s2["sentences_seen"]
    assert s1["sentences_seen"] == 3 and total == len(h2.db.q("MATCH (h:HarvestSentence) RETURN h.sent_key AS k"))
    (h2.out / "checkpoint.json").unlink(); h2.close()
    h3 = H(); s3 = h3.run(books=[BOOK_A])
    assert s3["sentences_seen"] == 0 and s3["loops_new"] == 0 and s3["loops_repeat"] == 0
    assert s3["skipped_already_processed"] == total


def test_duration_exit_and_cross_domain(H):
    h = H(); h.run(books=[BOOK_A, BOOK_B])
    r = {(x["a"], x["o"]): x for x in rows(h)}
    stir = r[("stir", "soup")]
    assert h.db.gate(stir["g"])["conditions"][0] == "elapsed >= 10 minute [explicit]"
    doms = h.db.domains_of(r[("cut", "board")]["id"])
    assert {(d["domain"], d["role"]) for d in doms} == {("craft.test", "primary"), ("cooking.test", "cross_link")}
    assert any(c["loop_id"] == r[("cut", "board")]["id"] for c in h.db.commonality())


def test_promotion_needs_authority_and_suggest_is_not_applied(H):
    h = H(); h.run(books=[BOOK_A, BOOK_B])
    lid = {(x["a"], x["o"]): x for x in rows(h)}[("cut", "board")]["id"]
    sug = h.db.suggest_promotions(min_repeats=2, min_sources=2)
    assert [x["loop_id"] for x in sug] == [lid]
    assert h.db.get(lid)["status"] == "candidate"
    with pytest.raises(ValueError):
        h.db.promote(lid, "  ")
    h.db.promote(lid, "N Hartman", "test")
    row = h.db.get(lid)
    assert row["status"] == "canonical" and row["provenance"]["authority"] == "N Hartman"
