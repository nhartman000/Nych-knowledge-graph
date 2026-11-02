"""Fixes 2026-11-02: instruction gate, pronoun/number objects, 'in place of', default modality,
sense mentions tied to a loop, user seed loop, parallel shards + single-writer merge."""
import json
import pytest
from nych3.config import registry
from nych3.harvest.spacy_extract import extract, strip_enumerator
from nych3.harvest import parallel
from nych3.harvest.harvester import Harvester
from nych3.store.tote_db import ToteDB

MR, LV = registry("modality"), set(registry("lexicon")["verbs"])


def X(t, dom="cooking", st=None):
    return extract(t, MR, LV, dom, st)


@pytest.mark.parametrize("t", ["He cut the board with a saw.", "The men stirred the pot slowly.", "Take care not to burn the sauce.",
                               "They were tying knots all evening."])
def test_narrative_and_figurative_rejected(t):
    assert X(t)[0] != "action"


@pytest.mark.parametrize("t", ["Stir the sauce with a spoon.", "You should stir the sauce with a spoon.", "The board should be planed until square."])
def test_instructions_pass(t):
    assert X(t)[0] == "action"


def test_pronouns_and_numbers_never_objects():
    for t, dom in [("Stir it until thick.", "cooking"), ("Beat them well with a fork.", "cooking"), ("Add 2.", "cooking"),
                   ("Slip 1, purl 1, knit 2, turn.", "craft.knitting")]:
        _, loops, _ = X(t, dom)
        for lp in loops:
            for o in lp["objects"]:
                assert o["lemma"] not in ("it", "them", "1", "2") and not o["head"].isdigit()
    _, loops, _ = X("Knit 2, purl 2.", "craft.knitting")
    assert [(lp["lemma"], lp["objects"][0]["lemma"], lp["objects"][0]["quantity"]) for lp in loops] == [("knit", "stitch", "2"), ("purl", "stitch", "2")]


def test_in_place_of_is_not_location():
    _, loops, _ = X("Use butter in place of lard.")
    assert loops and "place" not in loops[0]["row"]["perspective_location"]


def test_every_action_verb_has_default_modality():
    _, loops, _ = X("Fry the potatoes in deep fat.")
    assert loops[0]["row"]["modality"].startswith("Fry,🙌") and "[default]" in loops[0]["row"]["modality"]
    assert {ln["channel"] for ln in loops[0]["modality_links"]} == {"external_kinesthetic"}
    for v in [x for x in MR["operators"]]:
        assert MR["operators"][v]   # every channel has an invariant emoji


def test_sense_mention_attached_to_parent_loop_as_exit():
    st = {}
    _, loops, _ = X("Fry the potatoes until golden.", st=st)
    lp = loops[0]
    assert lp["lemma"] == "fry"
    assert lp["sense_tests"] == [{"op": "👀", "channel": "external_visual", "word": "golden", "step": "👀 verify color golden", "role": "exit"}]
    assert any(ln["channel"] == "external_visual" and ln["role"] == "exit" for ln in lp["modality_links"])
    assert st == {"sense_attached": 1, "sense_unattached": 0}
    st = {}
    _, loops, _ = X("Season to taste.", st=st)
    assert loops and loops[0]["exit"]["kind"] == "sense_test" and loops[0]["sense_tests"][0]["op"] == "👅"
    st = {}
    assert X("The cake was golden and fragrant.", st=st)[1] == []      # no action loop -> never stored, only counted
    assert st["sense_unattached"] == 2 and st.get("sense_attached", 0) == 0


def test_enumerator_and_label_stripped():
    assert strip_enumerator("8. Slip 1, purl 1.") == "Slip 1, purl 1."
    assert strip_enumerator("Left front: Cast on 65 stitches.") == "Cast on 65 stitches."


def test_user_seed_loop_canonical(tmp_path):
    db = ToteDB(tmp_path / "s.kuzu", rebuild=True)
    r = db.get("TL-STIR-SAUCE-001")
    assert r["status"] == "canonical" and r["domain"] == "cooking" and r["object_lemma"] == "sauce"
    assert r["provenance"]["source_kind"] == "user_prior_knowledge" and r["provenance"]["isbn"] is None
    assert [s["op"] for s in r["techniques"]] == ["🙌", "🫶", "🙌", "👀"]
    ops = db.q("MATCH (l:TOTELoop {loop_id:'TL-STIR-SAUCE-001'})-[u:USES_MODALITY]->(o:Operator) RETURN o.symbol AS s ORDER BY u.word")
    assert sorted(o["s"] for o in ops) == sorted(["🙌", "🫶", "🙌", "👀"])
    db.close()


HTML = """<html><body><p>*** START OF THE PROJECT GUTENBERG EBOOK T ***</p>
<p>Fry the potatoes until golden. He fried them yesterday.</p><p>Stir the sauce with a spoon.</p>
<p>Cut the board with a saw.</p><p>Stir the sauce with a spoon until thick.</p>
<p>*** END OF THE PROJECT GUTENBERG EBOOK T ***</p></body></html>"""
BOOK = {"book_id": "tP", "gutenberg_id": 9, "title": "P", "isbn": None, "isbn_status": "none_found_in_source", "domain": "cooking",
        "page_mode": "derived", "page_marker": None, "url": "z"}


def fake_fetch(b):   # module level: picklable for worker processes
    return HTML


def test_parallel_shards_merge_resumable(tmp_path):
    db = tmp_path / "p.kuzu"; ToteDB(db, rebuild=True).close()
    r = parallel.run_parallel(2, out_dir=tmp_path / "o", shard_paras=1, books=[BOOK], fetcher=fake_fetch)
    assert r["shards"] == 4 and r["done"] == 4
    st = parallel.merge(db, tmp_path / "o", books=[BOOK])
    assert st["sense_attached"] >= 1 and st["loops_new"] >= 3 and st["modality_links"] >= 3
    r2 = parallel.run_parallel(2, out_dir=tmp_path / "o", shard_paras=1, books=[BOOK], fetcher=fake_fetch)
    assert r2["cached"] == 4
    st2 = parallel.merge(db, tmp_path / "o", books=[BOOK])
    assert st2["loops_new"] == 0 and st2["loops_repeat"] == 0
    h = ToteDB(db)
    n = h.q("MATCH (h:HarvestSentence) RETURN count(h) AS n")[0]["n"]
    assert n == 5
    unlinked = h.q("MATCH (l:TOTELoop) WHERE l.loop_id STARTS WITH 'TL-H-' AND NOT EXISTS { MATCH (l)-[:USES_MODALITY]->(:Operator) } RETURN count(l) AS n")[0]["n"]
    assert unlinked == 0
    h.close()


def test_attributive_sense_words_are_not_tests():
    _, loops, _ = X("Add vegetables and three quarts boiling water.")
    assert loops and all(not lp["sense_tests"] for lp in loops)
    assert X("Half of the fat may be used for frying.")[0] != "action"
