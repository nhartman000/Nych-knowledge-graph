"""Runs stages 01-09. Each stage reads the previous stage's output/state.json and
writes its own; stage 09 writes <name>.gst and <name>.bonit."""
from __future__ import annotations
import json
from pathlib import Path
from .config import REPO
from .stages import STAGES, sha
from . import gst as gstmod, bonit


def _write(d: Path, name: str, obj):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def s09_gst(state, out_dir: Path, name: str):
    g = gstmod.build_gst(state)
    text = gstmod.dumps(g)
    out_dir.mkdir(parents=True, exist_ok=True)
    gp = out_dir / f"{name}.gst"
    gp.write_text(text, encoding="utf-8")
    ms = state["manifest"]["source_sha256"]
    bp = out_dir / f"{name}.bonit"
    bp.write_text(bonit.render_run_bonit(gp.name, sha(text), state["input"]["prompt"], state["input"]["story"],
                                         ms["prompt"], ms["story"]), encoding="utf-8")
    return g, gp, bp


def run(prompt: str, story: str, *, name: str = "run", root: Path | None = None, write_stage_outputs: bool = True, **opts):
    root = Path(root) if root else REPO
    state = {"input": {"prompt": prompt, "story": story, "name": name, **opts}}
    for stage, fn in STAGES:
        state = fn(state)
        if write_stage_outputs:
            _write(root / stage / "output", "state.json", state)
    g, gp, bp = s09_gst(state, root / "09_gst_pretext" / "output", name)
    return state, g, gp, bp


def run_stage(stage_name: str, root: Path | None = None):
    """Run a single stage from its predecessor's output (ICM: read only previous output)."""
    root = Path(root) if root else REPO
    names = [s for s, _ in STAGES]
    if stage_name == "09_gst_pretext":
        state = json.loads((root / names[-1] / "output" / "state.json").read_text(encoding="utf-8"))
        return s09_gst(state, root / "09_gst_pretext" / "output", state["input"].get("name", "run"))
    i = names.index(stage_name)
    if i == 0:
        state = json.loads((root / "01_boot" / "input.json" if (root / "01_boot" / "input.json").exists() else root / "01_boot" / "input.example.json").read_text(encoding="utf-8"))
        state = {"input": state}
    else:
        state = json.loads((root / names[i - 1] / "output" / "state.json").read_text(encoding="utf-8"))
    state = STAGES[i][1](state)
    _write(root / stage_name / "output", "state.json", state)
    return state
