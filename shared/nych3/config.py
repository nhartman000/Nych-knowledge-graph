"""Repo paths and registry loading. Registries live in _config/; code never hard-codes vocab."""
from __future__ import annotations
import functools, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "_config"
REGISTRIES = CONFIG / "registries"
SHARED = REPO / "shared"
SCHEMAS = SHARED / "schemas"


@functools.lru_cache(maxsize=None)
def registry(name: str) -> dict:
    return json.loads((REGISTRIES / f"{name}.json").read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def schema_versions() -> dict:
    import yaml
    return yaml.safe_load((CONFIG / "schema_versions.yaml").read_text(encoding="utf-8"))
