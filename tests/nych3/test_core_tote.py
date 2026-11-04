"""CORE TOTE loops: contract tests (no network, no raw cache needed)."""
import copy, json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/core_tote"))
import validate, spec, curation  # noqa: E402

DOC = json.loads((ROOT / "shared/data/tech_ui/core_tote/core_loops.json").read_text())
REPORT = json.loads((ROOT / "shared/data/tech_ui/core_tote/verify_report.json").read_text())
LOOPS = {L["loop_id"]: L for L in DOC["loops"]}


def test_strict_validation_passes():
    assert validate.errors(DOC) == []


def test_every_spec_is_kept_or_dropped_with_reason():
    kept = {k["id"] for k in REPORT["kept"]}
    dropped = {d["id"]: d["reason"] for d in REPORT["dropped"]}
    assert kept | set(dropped) == {s["id"] for s in spec.S}
    assert not kept & set(dropped)
    assert all(r for r in dropped.values())
    assert {f"TL-CORE-{k}" for k in kept} == set(LOOPS)


def test_size_and_categories():
    assert 80 <= len(LOOPS) <= 120
    cats = {L["category"] for L in LOOPS.values()}
    assert cats == {"files", "text_editing", "browser", "settings", "accounts", "messaging", "ai_chat"}


def test_non_idempotent_ops_never_auto_retry():
    for k in ("MAIL_SEND", "FILE_DELETE", "ACC_DELETE", "AI_SEND_PROMPT", "FILE_PRINT", "ACC_SIGN_IN"):
        b = LOOPS[f"TL-CORE-{k}"]["bounds"]
        assert b["max_retries"] == 0 and b["max_attempts"] == 1


def test_bounded_everywhere():
    for L in LOOPS.values():
        assert L["bounds"]["open_ended"] is False
        assert L["bounds"]["max_attempts"] <= 3
        assert any("decision not declared" in s for s in L["bounds"]["stop_conditions"])


def test_not_agentic_and_not_human_verified():
    for L in LOOPS.values():
        assert L["status"] == "CANONICAL-CANDIDATE" and L["verified_by_human"] is False
        assert L["actor"]["acts_on_behalf_of"] is None and L["actor"]["goal_seeking"] is False


def test_sources_grounded_and_quotes_short():
    for L in LOOPS.values():
        urls = [s["url"] for s in L["sources"]]
        assert len(set(urls)) == len(urls) >= 2
        for s in L["sources"]:
            assert len(s["quote"].split()) <= 25 and s["quote_found_in_raw_page"] is True


def test_operator_labels_both_sets():
    for L in LOOPS.values():
        t = L["tote"]
        assert (t["test_pre"]["modality_operator"], t["test_pre"]["process_operator"]) == ("OP-VE", "external_observe")
        assert (t["operate"]["modality_operator"], t["operate"]["process_operator"]) == ("OP-KE", "execute")
        assert t["operate"]["intent_marker"] == "🧠🗯" and "GAP-2" in t["operate"]["intent_mapping_flag"]


def test_partial_grades_match_curation():
    for k, L in LOOPS.items():
        assert (L["second_pass"]["grade"] == "partial") == (k[8:] in curation.PARTIAL)


def test_mapping_doc_flags_gaps():
    md = (ROOT / "shared/data/tech_ui/core_tote/OPERATOR_MAPPING.md").read_text()
    for g in ("GAP-1", "GAP-2", "GAP-3", "GAP-4", "external_observe", "internal_model", "operative_intent", "execute"):
        assert g in md
    for op in ("OP-KI", "OP-KE", "OP-VE", "OP-VI", "OP-AI", "OP-AE", "OP-MEM", "OP-IMG", "OP-OLF", "OP-GUS"):
        assert op in md


@pytest.mark.parametrize("mutate,needle", [
    (lambda L: L["bounds"].update(max_retries=5), "max_retries"),
    (lambda L: L["bounds"].update(open_ended=True), "open_ended"),
    (lambda L: L.update(status="CANONICAL"), "status"),
    (lambda L: L["actor"].update(goal_seeking=True), "actor"),
    (lambda L: L["sources"].pop(), ">=2"),
    (lambda L: L["sources"][0].update(quote="word " * 30), "quote"),
    (lambda L: L["sources"][0].update(url="https://example.com/x"), "non-official"),
    (lambda L: L["tote"]["operate"].update(count=2), "single"),
])
def test_validator_rejects_bad_loops(mutate, needle):
    d = copy.deepcopy(DOC)
    mutate(d["loops"][0])
    if needle == ">=2" and len(d["loops"][0]["sources"]) > 1:
        d["loops"][0]["sources"] = d["loops"][0]["sources"][:1]
    assert any(needle in e for e in validate.errors(d))
