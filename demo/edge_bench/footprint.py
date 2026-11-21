# Copyright (c) 2026 American Milestone Inc. All rights reserved.
# Proprietary and confidential. See LICENSE at the repository root.
"""Installed footprint: what would have to sit on the SD card."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKIP_PARTS = {"__pycache__", ".git", "output", ".pytest_cache", ".venv"}


def tree_bytes(path: Path, suffixes: tuple[str, ...] | None = None) -> tuple[int, int]:
    path = Path(path)
    if path.is_file():
        return path.stat().st_size, 1
    total = count = 0
    for f in path.rglob("*"):
        if f.is_file() and not SKIP_PARTS & set(f.relative_to(path).parts):
            if suffixes is None or f.suffix in suffixes:
                total += f.stat().st_size
                count += 1
    return total, count


def package_dir(module: str) -> Path | None:
    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin:
        return None
    origin = Path(spec.origin)
    return origin.parent if origin.name == "__init__.py" else origin


def _row(group: str, label: str, path: Path | None, suffixes=None) -> dict:
    if path is None or not Path(path).exists():
        return {"group": group, "item": label, "bytes": 0, "files": 0, "path": None}
    b, n = tree_bytes(path, suffixes)
    try:
        shown = str(Path(path).relative_to(REPO))
    except ValueError:
        shown = Path(path).name
    return {"group": group, "item": label, "bytes": b, "files": n, "path": shown}


def measure(weight_files: dict[str, Path]) -> list[dict]:
    rows = [
        _row("code", "checklist pipeline (demo/procedure_demo)", REPO / "demo" / "procedure_demo", (".py",)),
        _row("code", "NYCH3 encoder (shared/nych3)", REPO / "shared" / "nych3", (".py",)),
        _row("code", "vendored nych tokenizer (shared/vendor)", REPO / "shared" / "vendor", (".py",)),
        _row("code", "edge runtime: numpy decoder + loader (demo/edge_bench)", REPO / "demo" / "edge_bench", (".py",)),
        _row("code", "mg8-runtime (gates, permits, QSON log)", package_dir("mg8_runtime"), (".py",)),
        _row("code", "nych-language-model package (.py only)", package_dir("nych_language_model"), (".py",)),
        _row("symbol tables", "_config (NYCH3 registries, BONIT config)", REPO / "_config"),
        _row("symbol tables", "shared/data (sense registry, TOTE seed, how-to tables)", REPO / "shared" / "data"),
        _row("symbol tables", "NYCH emoji inventory + dictionaries (nych-language-model data)",
             (package_dir("nych_language_model") or Path("/nonexistent")) / "pipeline" / "data"),
        _row("symbol tables", "spaCy English model (en_core_web_sm)", package_dir("en_core_web_sm")),
        _row("gate / context files", ".qson / .gst / .g8son files in the repo", REPO, (".qson", ".gst", ".g8son")),
    ]
    for label, path in weight_files.items():
        rows.append(_row("model weights", label, path))
    for mod in ("numpy", "torch", "spacy", "thinc", "kuzu"):
        rows.append(_row("runtime libraries (not ours, x86 wheels)", mod, package_dir(mod)))
    return rows
