"""Noise filters in the procedure -> checklist pipeline (rules-2): sample terminal output, REPL sessions,
continued shell commands and cross-references must not become steps. No network, no model key."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))

from procedure_demo import compare  # noqa: E402
from procedure_demo.checklist import build_checklist  # noqa: E402

pytest.importorskip("spacy", reason="pip install -r requirements.txt")
pytest.importorskip("nych3", reason="needs shared/ on sys.path")

HEADER = "PUBLIC PROCEDURE EXCERPT\ntitle\nhttps://example.test/x\nRights: test\nChange notice: test\n"


def build(tmp_path, body_lines):
    p = tmp_path / "src.txt"
    p.write_text(HEADER + "\n".join(body_lines) + "\n", encoding="utf-8")
    return build_checklist(p)


def lines_of(cl, key):
    return [st["source_lines"] for st in cl[key]] if key == "steps" else [u["line"] for u in cl[key]]


def test_plain_commands_are_still_steps(tmp_path):
    cl = build(tmp_path, ["Create the environment:", "$ python -m venv .venv", "$ source .venv/bin/activate"])
    assert [st["kind"] for st in cl["steps"] if st["kind"] == "command"] == ["command", "command"]


def test_output_after_echoed_prompt_is_not_a_step(tmp_path):
    cl = build(tmp_path, [
        "Install it:",
        "$ (env) $ python -m pip install novas",   # line 7: echoed prompt -> a command
        "$ Collecting novas",                       # sample output
        "$ Successfully installed novas-3.1.1.3",   # sample output
        "Now remove it:",
        "$ deactivate",                             # new block, plain command again
    ])
    cmds = [st for st in cl["steps"] if st["kind"] == "command"]
    assert [c["tote"]["operate"] for c in cmds] == ["python -m pip install novas", "deactivate"]
    skipped = {u["line"]: u["reason"] for u in cl["unmapped_lines"]}
    assert set(skipped) >= {8, 9}                   # output lines are reported, never silently dropped
    assert all("sample terminal output" in skipped[n] for n in (8, 9))


def test_repl_session_lines_are_not_shell_commands(tmp_path):
    cl = build(tmp_path, ["Try it:", "$ (env) $ python", "$ >>> import sys", "$ >>> sys.path", "$ ..."])
    assert [st["tote"]["operate"] for st in cl["steps"] if st["kind"] == "command"] == ["python"]
    assert {u["line"] for u in cl["unmapped_lines"]} >= {8, 9, 10}


def test_backslash_continuation_is_one_command(tmp_path):
    cl = build(tmp_path, ["Copy it:", "$ rsync --archive \\", "$ /a /b host:/c", "Then check it."])
    cmds = [st for st in cl["steps"] if st["kind"] == "command"]
    assert len(cmds) == 1
    assert cmds[0]["source_lines"] == [7, 8]
    assert cmds[0]["tote"]["operate"] == "rsync --archive /a /b host:/c"


def test_cross_reference_is_not_a_step(tmp_path):
    cl = build(tmp_path, ["The steps for logical replication are not covered here; refer to Section 29.13 for details.",
                          "See Section 19.2 for how to relocate the files."])
    assert not [st for st in cl["steps"] if st["kind"] == "instruction"]
    assert {u["line"] for u in cl["unmapped_lines"]} == {6, 7}


def test_filters_cut_spurious_steps_without_losing_recall():
    """Regression guard on the bundled sources: spurious steps <= 15% (was 43%), gold recall >= 69%,
    every quote traceable, output deterministic."""
    gold = compare.load_gold(ROOT / "demo" / "gold")
    paths = {n: ROOT / "demo" / "sources" / f"{n}.txt" for n in gold}
    runs = {n: [build_checklist(p)] for n, p in paths.items()}
    t = compare.summarize(runs, paths, gold)["total"]
    assert t["gold_covered"] / t["gold_steps"] >= 0.69
    assert t["spurious_steps"] / t["steps_on_gold_sources"] <= 0.15
    assert t["traceable"] == t["steps"]
    assert t["numeric_limits_not_in_cited_lines"] == 0


def test_python_venv_sample_output_is_gone():
    cl = build_checklist(ROOT / "demo" / "sources" / "python_venv.txt")
    quotes = [st["source_quote"] for st in cl["steps"]]
    assert not any("Collecting" in q or "Successfully installed" in q or "Metadata-Version" in q for q in quotes)


def test_obligation_wording_in_prose_becomes_a_review_step(tmp_path):
    cl = build(tmp_path, ["It is important that the archive command return zero exit status if and only if it succeeds.",
                          "This log exists primarily for crash-safety purposes."])
    assert [st["source_lines"] for st in cl["steps"]] == [[6]]
    assert cl["steps"][0]["exit_checks"][0]["type"] == "human_review"


def test_pg_continuous_archiving_finds_more_than_config_lines():
    cl = build_checklist(ROOT / "demo" / "sources" / "pg_continuous_archiving.txt")
    kinds = [st["kind"] for st in cl["steps"]]
    assert kinds.count("instruction") >= 6
    assert {53, 82} <= {n for st in cl["steps"] for n in st["source_lines"]}
