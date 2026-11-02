"""Old wrong outputs from the audit run (/workspace/nych3-audit/peter_run.txt) must not recur."""
import pytest
from nych3.nlp.parser_adapter import verb_lemma
from nych3.skeleton import collisions
from nych3.llm.gestalt_call import build_request, validate_plan, ValidationError, MockProvider
from nych3.store.tote_db import ToteDB


def test_no_lov_or_notic(peter):
    lemmas = {e["predicate"]: e["lemma"] for e in peter[0]["temporal"]["events"]}
    assert lemmas == {"loved": "love", "looking": "look", "noticed": "notice"}
    for w, l in [("loved", "love"), ("noticed", "notice"), ("shoved", "shove"), ("danced", "dance"), ("hopped", "hop"), ("cried", "cry")]:
        assert verb_lemma(w)[0] == l


def test_no_from_false_match(peter, db_path):
    insts = peter[0]["tote"]["instances"]
    assert all("MB-B-WAI-001" not in str(i["template_id"]) for i in insts)
    assert all("from" not in i["retrieval"]["key"] for i in insts)
    db = ToteDB(db_path)
    assert db.lookup("from", None)["method"] == "NO_MATCH"


def test_weak_word_overlap_never_matches(encode):
    st = encode("Maria reviewed the page title from the archive.")[0]
    assert [i["template_id"] for i in st["tote"]["instances"]] == ["NO_MATCH"]


def test_his_house_do_not_share_gestalt(peter):
    needs = peter[0]["lexical"]["mapping_candidates"]
    assert "his" not in {n["word"].lower() for n in needs}
    ids = {}
    for n in needs:
        ids.setdefault(n["id"], set()).add(n["word"].lower())
    assert all(len(v) == 1 for v in ids.values())
    assert collisions(["his", "house"]) == {"hs": ["his", "house"]}


def test_collision_must_be_disambiguated():
    req = {"eligible": [{"word": "hose", "lemma": "hose", "occurrence_ref": "a", "skeleton": "hs", "collision_with": ["house"]},
                        {"word": "house", "lemma": "house", "occurrence_ref": "b", "skeleton": "hs", "collision_with": ["hose"]}],
           "protected": [], "pinned": [], "modality_operators": {"x": "👀"}}
    plan = {"mappings": [{"word": "hose", "occurrence_ref": "a", "symbol_id": "g.hs", "glyph": "◌"},
                         {"word": "house", "occurrence_ref": "b", "symbol_id": "g.hs", "glyph": "◌"}]}
    with pytest.raises(ValidationError, match="collision"):
        validate_plan(plan, req)


def test_peter_mapping_rejected(peter):
    req = build_request(peter[1])
    plan = MockProvider().propose(req)
    plan["mappings"].append({"word": "Peter", "occurrence_ref": "p0s0t0", "symbol_id": "g.ptr", "glyph": "◌"})
    with pytest.raises(ValidationError, match="protected"):
        validate_plan(plan, req)


def test_no_sentence_merging(encode):
    st = encode("Dr. Smith arrived at noon. He sat down! Was it late? \"Yes,\" she said.")[0]["structure"]
    assert [s["text"] for s in st["pages"][0]["sentences"]] == [
        "Dr. Smith arrived at noon.", "He sat down!", "Was it late?", "\"Yes,\" she said."]


def test_punctuation_not_in_words_and_domain_not_general(peter):
    assert all(n["word"].isalpha() for n in peter[0]["lexical"]["mapping_candidates"])
    assert peter[1]["domain"] != "general"
