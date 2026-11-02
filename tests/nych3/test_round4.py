"""Round 4 (2026-11-02): index lines dropped, 'X or Y' ranges, 🧠🗯 default mental marker, gold-set accuracy harness."""
import json
from pathlib import Path
import pytest
from nych3.config import registry
from nych3.harvest.spacy_extract import extract, normalize_quantity, is_apparatus

MR, LV = registry("modality"), set(registry("lexicon")["verbs"])
GOLD = Path(__file__).parent / "gold" / "gold_v1.jsonl"


def X(t, dom="cooking"):
    return extract(t, MR, LV, dom)


@pytest.mark.parametrize("t", ["Live, to Broil, 189.", "Ice Cream, 446, 447.", "Apple Fritters I, 349.", "Pear Salad.—Page 340."])
def test_index_and_caption_lines_dropped(t):
    o, loops, _ = X(t)
    assert o == "skipped_apparatus" and not loops


@pytest.mark.parametrize("t", ["Knit 2, purl 1.", "Knit 7, purl 2, knit 10."])
def test_knitting_counts_are_not_index_lines(t):
    assert is_apparatus(t) is None


def test_or_numbers_are_ranges():
    assert normalize_quantity(["two", "or", "three"]) == "2-3"
    assert normalize_quantity(["18", "to", "20"]) == "18-20"
    _, loops, _ = X("Put two or three buttered muffin rings in the water.")
    o = loops[0]["objects"][0]
    assert o["quantity"] == "2-3" and o["quantity_range"] == ["2", "3"]
    _, loops, _ = X("Boil three or four hours.")
    assert loops[0]["exit"]["condition"] == "3 hour <= elapsed <= 4 hour"   # a window, never just the upper bound


def test_ordinal_is_position_not_amount():
    _, loops, _ = X("Slip 1st 18 stitches on to the needle, join in the color, knit 21 stitches, turn and knit back.", "craft.knitting")
    assert loops[0]["objects"][0]["quantity"] == "18"


def _marker(t):
    _, loops, _ = X(t)
    return [(s.get("mental_marker"), s.get("marker_cue")) for lp in loops for s in lp["sense_tests"]]


def test_imagined_is_default_memory_only_on_explicit_recall_cue():
    mm = MR["mental_markers"]
    assert mm["imagined"] == "🧠🗯" and mm["memory"] == "💭"
    assert set(mm["memory_cues"]) >= {"remember", "recall", "as before", "exactly as last time"}
    assert "recollect" not in mm["memory_cues"] and "as previously" not in mm["memory_cues"]
    assert _marker("Knead the dough until smooth.") == [("🧠🗯", "no_memory_cue")]
    assert _marker("Knead the dough until smooth, exactly as last time.") == [("💭", "exactly as last time")]
    assert _marker("Knead the dough until smooth as before.") == [("💭", "as before")]


def test_reduced_clause_sense_is_not_a_test_of_the_main_verb():
    _, loops, _ = X("Add yolk of egg, seasonings, corn-starch, and cream beaten until stiff.")
    assert loops and not loops[0]["sense_tests"] and loops[0]["exit"] is None


def test_crochet_ring_is_not_a_sound():
    _, loops, _ = X("Pass the end around the post, ring, or other object.", "craft.ropework")
    assert all(s["channel"] != "external_auditory" for lp in loops for s in lp["sense_tests"])


def test_seed_stir_sauce_feel_step_stays_imagined():
    seed = json.loads((Path(__file__).resolve().parents[2] / "shared" / "data" / "tote_seed.json").read_text(encoding="utf-8"))
    lp = next(x for x in seed["loops"] if x["loop_id"] == "TL-STIR-SAUCE-001")
    assert "feel,🫶🧠🗯" in lp["modality_cell"] and lp["initial_test"].startswith("🫶🧠🗯")


def test_gold_set_shape():
    rows = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 300
    assert {r["domain"] for r in rows} == {"cooking", "craft.woodworking", "craft.knitting", "craft.ropework"}
    assert all("PENDING HUMAN REVIEW" in r["grading"] for r in rows)
    assert all(r["sent_key"] and r["page"] for r in rows)


def test_accuracy_report(capsys):
    """Non-failing threshold report: prints the per-field / per-domain table; only xfails on collapse."""
    from nych3.eval.accuracy import evaluate, fmt
    rep = evaluate(GOLD)
    with capsys.disabled():
        print("\n" + fmt(rep))
    f = rep["fields"]["all"]
    for k, floor in {"instruction_sentence": 0.80, "action": 0.60, "objects": 0.70, "modality": 0.80, "exit_tier": 0.75}.items():
        if f[k]["f1"] < floor:
            pytest.xfail(f"accuracy below reporting floor: {k} F1 {f[k]['f1']:.3f} < {floor}")


def test_demo_encode_offline(tmp_path):
    from nych3.demo import encode, render
    res = encode("Stir the sauce with a spoon until thick, exactly as last time", "cooking", tmp_path / "none.kuzu")
    lp = res["loops"][0]
    assert res["sentence"].endswith(".") and lp["row"]["action"] == "stir," and lp["exit_gate"]["tier"] == "explicit"
    assert lp["steps"][0]["mental_marker"] == "💭" and lp["provenance"]["isbn"] is None and lp["graph"] == {"available": False}
    assert "UNRESOLVED" in lp["row"]["perspective_location"]   # 'as last time' is not a place
    assert "LOOP 1" in render(res)
