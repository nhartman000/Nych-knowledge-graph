"""Four-part TOTE rule + 'senses never assert the action' (owner rule 2026-11-03)."""
import copy, json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/core_tote"))
import validate  # noqa: E402
from nych3.tote_four_part import missing_parts, check, operators_never_assert_action

SEED = json.loads((ROOT / "shared/data/tote_seed.json").read_text())
DOC = json.loads((ROOT / "shared/data/tech_ui/core_tote/core_loops.json").read_text())


def test_no_modality_operator_asserts_action():
    assert operators_never_assert_action(SEED["operators"]) == []
    ext = {o[0] for o in SEED["operators"] if o[3] == "actor_external"}
    assert {"OP-VE", "OP-AE", "OP-KE", "OP-OLF", "OP-GUS"} <= ext


def test_all_88_core_loops_have_four_parts():
    assert len(DOC["loops"]) == 88
    assert all(missing_parts(L) == [] for L in DOC["loops"])
    assert validate.errors(DOC) == []


@pytest.mark.parametrize("part,mutate", [
    ("tool_or_object", lambda L: L.pop("tool_or_object")),
    ("actor", lambda L: L.__setitem__("actor", {})),
    ("action", lambda L: L.__setitem__("canonical_action", "")),
    ("modality_operator", lambda L: [s.pop("modality_operator", None) for s in L["tote"].values() if isinstance(s, dict)]),
])
def test_core_loop_rejected_when_part_missing(part, mutate):
    d = copy.deepcopy(DOC); mutate(d["loops"][0])
    assert part in missing_parts(d["loops"][0])
    assert any("four-part" in e for e in validate.errors(d))
    with pytest.raises(ValueError):
        check(d["loops"][0])


def test_core_step_may_not_assert_action():
    d = copy.deepcopy(DOC); d["loops"][0]["tote"]["test_pre"]["may_assert_action"] = True
    assert any("may not assert" in e for e in validate.errors(d))


def test_seed_store_rows():
    for row in SEED["loops"]:
        assert missing_parts(row, modality_links=row.get("modality_links")) == []
    bad = {"loop_id": "X", "modality_cell": "", "actor_cell": "<actor>,", "action_cell": "", "object_cell": ","}
    assert missing_parts(bad) == ["modality_operator", "action", "tool_or_object"]
    assert "actor" in missing_parts(bad, allow_placeholders=False)
    assert missing_parts({"modality_cell": "", "actor_cell": "a", "action_cell": "b,", "object_cell": "c"},
                         modality_links=[{"channel": "external_visual"}]) == []


def test_gap4_documented_resolved():
    md = (ROOT / "shared/data/tech_ui/core_tote/OPERATOR_MAPPING.md").read_text()
    assert "GAP-4" in md and "RESOLVED" in md and "input data" in md
