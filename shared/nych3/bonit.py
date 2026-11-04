""".bonit v3 writer/parser. Line-oriented: KEYWORD rest. The per-run .bonit points
to README.md / CLAUDE.md and carries the original prompt and story losslessly as
JSON string literals (SOURCE_PROMPT_JSON / SOURCE_STORY_JSON) plus their sha256."""
from __future__ import annotations
import json
from .config import REPO

MULTI = {"POINTER", "WORKFLOW", "VALIDATION"}


def parse(text: str) -> dict:
    lines = text.rstrip("\n").split("\n")
    if not lines or not lines[0].startswith("BONIT/"):
        raise ValueError("not a .bonit file (missing BONIT/ header)")
    out = {"version": lines[0].split("/", 1)[1]}
    for ln in lines[1:]:
        if not ln.strip() or ln.startswith("#"):
            continue
        k, _, v = ln.partition(" ")
        if k.endswith("_JSON"):
            out[k] = json.loads(v)
        elif k in MULTI:
            out.setdefault(k, []).append(v)
        else:
            out[k] = v
    return out


def render_run_bonit(gst_filename: str, gst_sha: str, prompt: str, story: str, prompt_sha: str, story_sha: str) -> str:
    base = (REPO / "_config" / "nych3.bonit").read_text(encoding="utf-8").rstrip("\n")
    return "\n".join([
        base,
        f"REPO {REPO}",
        f"GST {gst_filename} sha256={gst_sha}",
        f"SOURCE_SHA256 prompt={prompt_sha} story={story_sha}",
        "SOURCE_PROMPT_JSON " + json.dumps(prompt, ensure_ascii=True),
        "SOURCE_STORY_JSON " + json.dumps(story, ensure_ascii=True),
    ]) + "\n"
