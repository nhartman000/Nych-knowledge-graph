import pytest
pytest.importorskip("spacy")
from nych3.config import registry
from nych3.provenance import PROVENANCE, PROVENANCE_RANK
from nych3.harvest.spacy_extract import extract, is_apparatus

M = registry("modality"); V = set(registry("lexicon")["verbs"])


def X(t):
    o, loops, r = extract(t, M, V)
    return o, loops, r


def test_unit_is_quantity_modifier_not_object():
    o, l, _ = X("Melt two tablespoons butter.")
    obj = l[0]["objects"][0]
    assert (obj["lemma"], obj["quantity"]) == ("butter", "2 tablespoon")
    assert l[0]["tool"] is None and l[0]["object_lemma"] == "butter"
    o, l, _ = X("Add 1 cup of milk and 2 eggs.")
    assert [(x["lemma"], x["quantity"]) for x in l[0]["objects"]] == [("milk", "1 cup"), ("egg", "2")]


def test_coordinated_objects_one_loop():
    o, l, _ = X("Add flour, milk and butter.")
    assert len(l) == 1 and sorted(x["lemma"] for x in l[0]["objects"]) == ["butter", "flour", "milk"]


def test_with_resolution_by_noun_class():
    _, l, _ = X("Stir with a spoon.")
    assert l[0]["tool"]["lemma"] == "spoon" and not l[0]["objects"]
    _, l, _ = X("Sprinkle with salt and pepper.")
    assert l[0]["tool"] is None and {x["lemma"] for x in l[0]["objects"]} == {"salt", "pepper"}
    assert all(x["role"] == "with_ingredient" for x in l[0]["objects"])
    _, l, _ = X("Rub the bowl with a clove of garlic.")
    assert l[0]["tool"] is None


@pytest.mark.parametrize("text,kind,cond,prov", [
    ("Ride to the store.", "actor_location", "actor_location == store", "implied_by_text"),
    ("Cut the dough into slices.", "result_state", "object_state == slice", "implied_by_text"),
    ("Put the potatoes into a kettle.", "object_location", "object_location == kettle", "implied_by_text"),
    ("Stir with a spoon until smooth.", "until", "until smooth", "explicit"),
    ("Stir the soup for ten minutes.", "duration", "elapsed >= 10 minute", "explicit"),
    ("Cook the potatoes ten minutes.", "duration", "elapsed >= 10 minute", "implied_by_text"),
])
def test_implied_and_explicit_exits(text, kind, cond, prov):
    _, l, _ = X(text)
    e = l[0]["exit"]
    assert (e["kind"], e["condition"], e["provenance"]) == (kind, cond, prov)
    assert l[0]["row"]["exit"] == f"{cond} [{prov}]"


def test_provenance_tier_rank():
    assert PROVENANCE[:3] == ("explicit", "implied_by_text", "inferred")
    assert PROVENANCE_RANK["explicit"] < PROVENANCE_RANK["implied_by_text"] < PROVENANCE_RANK["inferred"]


@pytest.mark.parametrize("text", ["DOUBLE CUT SAW MILL, PINOGRANDE, CALIFORNIA.",
                                  "Page 116: PART THREE has been changed to PART III for consistency.",
                                  "Transcriber's note: obvious errors were corrected.", "Fig. 67 illustrates a way to square ends.",
                                  "[Illustration: A square knot]"])
def test_apparatus_filtered(text):
    assert is_apparatus(text)
    assert X(text)[0] == "skipped_apparatus"


@pytest.mark.parametrize("text", ["This cap-iron serves a double purpose.", "Locks are used on drawers.",
                                  "It is not expected that the book will be studied."])
def test_descriptive_and_stative_rejected(text):
    assert X(text)[0] in ("non_action", "no_match") and not X(text)[1]


def test_mood_and_passive_carry_over():
    _, l, _ = X("Cut the board and sand the edge.")
    assert [(x["lemma"], x["mood"], x["row"]["actor"]) for x in l] == [("cut", "imperative", "you(implied),"), ("sand", "imperative", "you(implied),")]
    _, l, _ = X("The edge should be planed and then sanded.")
    assert all(x["passive"] and x["row"]["actor"].startswith("agent(implied") for x in l)
    _, l, _ = X("Narrow at the end of the needle until 26 stitches are left.")
    assert l[0]["lemma"] == "narrow" and l[0]["exit"]["provenance"] == "explicit"
