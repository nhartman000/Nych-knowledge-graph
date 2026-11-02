"""(a) master measurement list with domain overrides, (b) sense weights as assumed priors with context overrides,
(c) 'X's worth' indirect measures are always amounts."""
import json
import pytest
pytest.importorskip("spacy")
from nych3.config import CONFIG, registry
from nych3.harvest.spacy_extract import extract, sense_weight, measure_decision, nlp

M = registry("modality"); V = set(registry("lexicon")["verbs"])
MEAS = json.loads((CONFIG / "invariants" / "measures.json").read_text(encoding="utf-8"))


def objs(text, domain=None):
    _, l, _ = extract(text, M, V, domain)
    return l[0]["objects"], l[0]["tool"]


# (a) -----------------------------------------------------------------
def test_master_list_is_shared_with_domain_overrides():
    assert "units" not in json.loads((CONFIG / "invariants" / "domain_invariants.json").read_text())
    assert sense_weight("stitch", "craft.knitting")[0] == "high"
    assert sense_weight("stitch", "cooking")[0] == "low"
    assert sense_weight("foot", "craft.woodworking")[0] == "high" and sense_weight("foot", "scouting.first_aid.outdoor")[0] == "low"
    assert sense_weight("elephant") is None


def test_collision_with_literal_sense_avoided():
    o, _ = objs("Cut the foot of the board.", "craft.woodworking")
    assert o[0]["lemma"] == "foot" and o[0]["quantity"] is None          # literal: definite reference
    o, _ = objs("Saw off 2 feet of the board.", "craft.woodworking")
    assert o[0]["quantity"] and "foot" in o[0]["quantity"]               # measurement: number before
    o, _ = objs("Slip the stitches of both pieces on to 3 needles.", "craft.knitting")
    assert o[0]["lemma"] == "stitch"


# (b) -----------------------------------------------------------------
def test_weights_are_ordered_assumed_priors_never_calibrated():
    assert MEAS["weight_source"] == "assumed_prior" and MEAS["classes"] == ["high", "medium", "low"]
    for e in MEAS["entries"].values():
        assert e["sense_weight"] in MEAS["classes"] and all(v in MEAS["classes"] for v in e.get("domains", {}).values())
        assert not any(isinstance(v, float) for v in e.values())
    for w in ("mouthful", "dash", "handful", "pinch", "splash", "tablespoon"):
        assert MEAS["entries"][w]["sense_weight"] == "high"
    assert sense_weight("tablespoon", "cooking") == ("high", "assumed_prior")


def test_context_rules_override_weight():
    d = nlp()("you stir with a cup.")
    cup = [t for t in d if t.lower_ == "cup"][0]
    assert measure_decision(cup, "cooking")[:2] == (False, "MEAS-WITH-TOOL")      # high weight, but tool after 'with'
    o, tool = objs("Stir with a cup.", "cooking")
    assert tool["lemma"] == "cup" and not o
    o, tool = objs("Add 2 cups milk.", "cooking")
    assert (o[0]["lemma"], o[0]["quantity"]) == ("milk", "2 cup")
    o, tool = objs("Add a pinch of salt.", "cooking")
    assert (o[0]["lemma"], o[0]["quantity"]) == ("salt", "pinch")
    o, tool = objs("Rub the bowl with a clove of garlic.", "cooking")
    assert tool is None and any(x["lemma"] == "garlic" for x in o)


# (c) -----------------------------------------------------------------
@pytest.mark.parametrize("text,lemma,qty", [
    ("Pack a day's worth of food.", "food", "1 day worth"),
    ("Pack a month's worth of supplies.", "supply", "1 month worth"),
    ("Add a cup's worth of milk.", "milk", "1 cup worth"),
    ("Add a cup worth of milk.", "milk", "1 cup worth"),
    ("Pack three days' worth of food.", "food", "3 day worth"),
])
def test_worth_is_always_an_amount(text, lemma, qty):
    o, tool = objs(text)
    assert (o[0]["lemma"], o[0]["quantity"], o[0]["rule"]) == (lemma, qty, "MEAS-WORTH") and tool is None


def test_bare_worth_without_noun_is_still_amount():
    o, _ = objs("Pack a month's worth.")
    assert o[0]["lemma"] == "amount" and o[0]["quantity"] == "1 month worth"
