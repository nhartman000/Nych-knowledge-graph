"""Golden case defined by the user (2026-11-01)."""
import json
from pathlib import Path

GOLDEN = json.loads((Path(__file__).parent / "golden" / "peter" / "expected_s1_row.json").read_text(encoding="utf-8"))


def ev(state, eid):
    return next(e for e in state["temporal"]["events"] if e["event_id"] == eid)


def prop(state, eid):
    return next(p for p in state["semantics"]["propositions"] if p["event_id"] == eid)


def test_structure_two_sentences_one_page(peter):
    st = peter[0]["structure"]
    assert st["sentence_count"] == 2
    assert [s["text"] for s in st["pages"][0]["sentences"]] == [
        "Peter loved looking at the stars from the hill behind his house.", "One clear night he noticed a wolf."]
    assert st["run_counts"] == {"expected_pages": 1, "completed_pages": 1, "complete": True}
    assert st["page_marker_kind"] == "single_page_default"


def test_s1_blanket_past_no_anchor(peter):
    loved = ev(peter[0], "ev0")
    assert (loved["predicate"], loved["lemma"], loved["tense"]) == ("loved", "love", "past")
    assert loved["blanket_statement"] is True and loved["time_anchor"] is None


def test_s1_looking_nested_not_present(peter):
    looking = ev(peter[0], "ev1")
    assert looking["parent_event"] == "ev0"
    assert looking["tense"] is None and looking["finite"] is False
    assert looking["governed_tense"] == "past"
    assert looking["tense"] != "present"


def test_s1_roles(peter):
    p = prop(peter[0], "ev1")
    assert p["object"]["head"] == "stars" and p["object"]["via_prep"] == "at"
    loc = p["locations"][0]
    assert (loc["prep"], loc["head"], loc["role"], loc["perspective_level"]) == ("from", "hill", "perspective", 2)
    rel = loc["located_by"][0]
    assert (rel["relation"], rel["figure"], rel["ground"]) == ("behind", "hill", "house")
    assert rel["ground_arg"]["possessor"]["text"] == "his"
    assert rel["ground_arg"]["possessor"]["entity_id"] == "E0"
    assert peter[0]["scope"]["entities"][0]["name"] == "Peter"


def test_s1_tote_row_matches_golden(peter):
    inst = peter[0]["tote"]["instances"][0]
    assert inst["template_id"] == GOLDEN["template_id"]
    assert inst["row"] == GOLDEN["row"]
    assert inst["exit"]["status"] == "inferred"
    assert {t["trigger"] for t in inst["termination_triggers"]} == {"daylight", "falls_asleep"}
    assert all(t["provenance"] == "inferred" and t["occurred"] == "not_stated_in_text" for t in inst["termination_triggers"])


def test_s1_hill_approach(peter):
    inst = peter[0]["tote"]["instances"][1]
    assert inst["template_id"] == "TL-APPROACH-LOCATION-001" and inst["provenance"] == "inferred"
    techs = {t["technique"]: t for t in inst["alternative_techniques"]}
    assert techs["walking"]["likelihood_class"] == "high" and techs["walking"]["provenance"] == "assumed_default"
    assert techs["biking"]["likelihood_class"] == "latent"
    assert inst["initial_state"]["start_position"] == "UNRESOLVED"


def test_s2_anchor_scoped_only_to_s2(peter):
    a = peter[0]["temporal"]["time_anchors"]
    assert len(a) == 1 and a[0]["text"] == "One clear night"
    assert a[0]["scoped_to_events"] == ["ev2"] and a[0]["propagates_backward"] is False
    assert ev(peter[0], "ev0")["time_anchor"] is None and ev(peter[0], "ev1")["time_anchor"] is None


def test_s2_he_is_peter_and_no_forced_match(peter):
    he = next(m for m in peter[0]["scope"]["mentions"] if m["text"] == "he")
    assert he["entity_id"] == "E0" and he["provenance"] == "inferred"
    p = prop(peter[0], "ev2")
    assert p["object"]["head"] == "wolf"
    assert p["channel"] == "external_visual" and p["channel_provenance"] == "inferred" and "unresolved" in p["channel_alternatives"]
    inst = peter[0]["tote"]["instances"][2]
    assert inst["template_id"] == "NO_MATCH" and inst["fallback"]["nearest_match_forced"] is False


def test_peter_protected(peter):
    lex = peter[0]["lexical"]
    assert {p["word"] for p in lex["protected"]} == {"Peter"}
    assert "Peter" not in {n["word"] for n in lex["mapping_candidates"]}
