import ast
from pathlib import Path
from nych3 import bonit

PKG = Path(__file__).resolve().parents[1] / "shared" / "nych3"
FORBIDDEN = {"openai", "anthropic", "google", "requests", "httpx", "urllib", "socket", "http", "aiohttp"}


def test_stages_01_09_import_no_llm_or_network():
    files = [PKG / "stages.py", PKG / "gst.py", PKG / "bonit.py", PKG / "pipeline.py", PKG / "skeleton.py", PKG / "provenance.py",
             *(PKG / "nlp").glob("*.py"), *(PKG / "store").glob("*.py")]
    for f in files:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for n in names:
                assert n.split(".")[0] not in FORBIDDEN, f"{f.name} imports {n}"
                assert "llm" not in n.split("."), f"{f.name} imports {n}"


def test_bonit_lossless_and_points_to_docs(encode):
    story = "Peter\u00a0ran.\f  \"Who?\" 🫶\n\n--- not a marker\r\nEnd…"
    state, g, gp, bp = encode(story, prompt="Encode.\tKeep\u2028all.")
    b = bonit.parse(bp.read_text(encoding="utf-8"))
    assert b["SOURCE_STORY_JSON"] == story and b["SOURCE_PROMPT_JSON"] == "Encode.\tKeep\u2028all."
    assert {"README.md", "CLAUDE.md"} <= set(b["POINTER"])
    assert any("ASSIGN_GESTALTS" in w for w in b["WORKFLOW"])
    assert "never answer" in b["DIRECTIVE"]
    assert g["nych3"]["source"]["story"] == story
