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
    assert [s["op"] for s in r["techniques"]] == ["🙌", "🫶🧠🗯", "🙌", "👀"]   # internal sense carries its mental marker
    ops = db.q("MATCH (l:TOTELoop {loop_id:'TL-STIR-SAUCE-001'})-[u:USES_MODALITY]->(o:Operator) RETURN o.symbol AS s ORDER BY u.word")
    assert sorted(o["s"] for o in ops) == sorted(["🙌", "🫶", "🙌", "👀", "🧠🗯"])
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


# ---- round 2 (2026-11-02, user-approved) ----
@pytest.mark.parametrize("t", ["These slippers are very easily knitted.", "Canned peas are often drained, rinsed, and reheated in this way.",
                               "Slabs are sawed to a length of four feet.", "The plane is pressed to the board with the right hand."])
def test_descriptive_and_passive_rejected(t):
    assert X(t)[0] != "action"


def test_exit_and_sense_go_to_the_right_verb():
    _, loops, _ = X("Spread saltines with mixture and bake until delicately browned.")
    by = {lp["lemma"]: lp for lp in loops}
    assert set(by) == {"spread", "bake"}
    assert by["spread"]["exit"] is None and not by["spread"]["sense_tests"]
    assert by["bake"]["exit"]["kind"] == "until" and by["bake"]["sense_tests"][0]["step"] == "👀 verify color browned"
    _, loops, _ = X("Then add milk, stir lightly with a fork, cover, and steam until rice is soft.")
    by = {lp["lemma"]: lp for lp in loops}
    assert by["steam"]["exit"]["kind"] == "until" and by["stir"]["exit"] is None


def test_objects_whites_verbs_containers():
    _, loops, _ = X("Beat whites until stiff, and continue beating until mixture will hold its shape.")
    assert all(lp["objects"] and lp["objects"][0]["head"] == "whites" for lp in loops if lp["lemma"] == "beat")
    _, loops, _ = X("Add milk, season, and bind.")
    assert all(o["lemma"] not in ("season", "bind") for lp in loops for o in lp["objects"])
    _, loops, _ = X("Put on a sheet and bake until the cheese melts.")
    assert all(o["lemma"] != "bake" for lp in loops for o in lp["objects"])
    _, loops, _ = X("Put in a stone jar or tumblers.")
    assert loops[0]["objects"] == [] and "in jar," in loops[0]["row"]["perspective_location"]


def test_fractions_and_sizes():
    _, loops, _ = X("Add one-half cup cracker crumbs, 1/2 teaspoon salt and one and one-half cups milk.")
    q = {o["head"]: o["quantity"] for o in loops[0]["objects"]}
    assert q == {"crumbs": "1/2 cup", "salt": "1/2 teaspoon", "milk": "1 1/2 cup"}
    _, loops, _ = X("Add one-fourth cup rice.")
    assert loops[0]["objects"][0]["quantity"] == "1/4 cup"
    _, loops, _ = X("Add gradually two-thirds of sugar.")
    assert loops[0]["objects"][0]["quantity"] == "2/3"
    _, loops, _ = X("Use No. 16 steel needles.", "craft.knitting")
    o = loops[0]["objects"][0]
    assert o["size"] == "No. 16" and o["quantity"] is None


def test_cross_reference_and_prohibition():
    assert X("See directions for freezing, page 434.") == ("non_action", [], "cross_reference")
    for t in ["Never put cogs of a Dover Egg-beater in water.", "Do not stir the sauce."]:
        _, loops, _ = X(t)
        assert loops[0]["prohibition"] and loops[0]["row"]["action"].startswith("NEVER ") and "PROHIBIT" in loops[0]["key"]
    a = X("Stir the sauce.")[1][0]["key"]; b = X("Do not stir the sauce.")[1][0]["key"]
    assert a != b   # a prohibition never merges with the positive action


def test_bore_and_smooth_plane():
    _, loops, _ = X("Bore these holes so that they connect.", "craft.woodworking")
    assert loops[0]["lemma"] == "bore"
    _, loops, _ = X("Where one plane is made to serve the purpose of smooth, jack and fore-plane, it should be ground straight across.", "craft.woodworking")
    assert all(t["word"] != "smooth" for lp in loops for t in lp["sense_tests"])


# ---- round 3 (2026-11-02): 🧠🗯 imagine, mental markers, verbs, place, inch fractions ----
def test_imagine_glyph_replaced_everywhere():
    assert MR["operators"]["imagine"] == "🧠🗯"
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    while not (root / "_config").exists():
        root = root.parent
    for f in [root / "_config/registries/modality.json", root / "shared/data/tote_seed.json"]:
        assert "👁️‍🗨️" not in f.read_text(encoding="utf-8")


def test_mental_verbs_are_imagine():
    for v in ["Determine the size of the views.", "Estimate the amount of lumber.", "Plan the cuts carefully.", "Decide the order of the steps."]:
        _, loops, _ = X(v, "craft.woodworking")
        assert loops and any(ln["channel"] == "imagine" for ln in loops[0]["modality_links"]), v
        assert "🧠🗯" in loops[0]["row"]["modality"]


def test_internal_sense_carries_mental_marker():
    _, loops, _ = X("Stir until thick.")
    t = loops[0]["sense_tests"][0]
    assert t["op"] == "🫶🧠🗯" and t["mental_marker"] == "🧠🗯" and t["marker_cue"] == "no_memory_cue"
    _, loops, _ = X("Beat until stiff, as before.")
    t = loops[0]["sense_tests"][0]
    assert t["op"] == "🫶💭" and t["marker_cue"] == "as before"
    _, loops, _ = X("Remember to feel the dough.")
    assert all(x for x in loops)   # parses; any internal link has its marker
    for lp in loops:
        internal = [l for l in lp["modality_links"] if l["channel"] in MR["mental_markers"]["internal_channels"]]
        markers = [l for l in lp["modality_links"] if l["role"] == "mental_marker"]
        assert len(markers) >= len(internal)
    _, loops, _ = X("Fry until golden.")          # external senses carry no mental marker
    assert "mental_marker" not in loops[0]["sense_tests"][0]


def test_more_verbs_attach_time_and_until():
    _, loops, _ = X("Clean one-fourth pound mushrooms, break caps in pieces, and sauté five minutes in one tablespoon butter.")
    by = {lp["lemma"]: lp for lp in loops}
    assert by["sauté"]["exit"]["condition"] == "elapsed >= 5 minute" and by["clean"]["exit"] is None
    _, loops, _ = X("Line melon mould with ice, turn in mixture, and let stand three hours.")
    by = {lp["lemma"]: lp for lp in loops}
    assert by["stand"]["exit"]["condition"] == "elapsed >= 3 hour" and by["line"]["exit"] is None
    _, loops, _ = X("Braise the beef until tender.")
    assert loops[0]["lemma"] == "braise" and loops[0]["objects"][0]["head"] == "beef"


def test_dry_cool_warm_as_verbs_are_actions():
    st = {}
    _, loops, _ = X("Take from water, dry between towels, and fry in deep fat.", st=st)
    assert {"take", "dry", "fry"} <= {lp["lemma"] for lp in loops}
    assert all(t["word"] != "dry" for lp in loops for t in lp["sense_tests"])


def test_only_in_place_of_is_dropped():
    _, loops, _ = X("Meat should be kept in a cool place.")
    assert "in place," in loops[0]["row"]["perspective_location"]
    _, loops, _ = X("Use butter in place of lard.")
    assert "place" not in loops[0]["row"]["perspective_location"]


def test_inch_fraction_is_length_not_time():
    _, loops, _ = X("Chisel a line parallel to the given line, about one thirty-second of an inch away from it.", "craft.woodworking")
    assert loops and all(not (lp["exit"] and lp["exit"]["kind"] == "duration") for lp in loops)
