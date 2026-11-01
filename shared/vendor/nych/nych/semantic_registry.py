"""Validated persistent registry for NYCH senses and multiword Gestalts."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("data") / "sense_registry.json"


class RegistryError(ValueError):
    """Raised when canonical registry structure is incomplete or ambiguous."""


def validate_registry(data: dict) -> None:
    if not isinstance(data, dict) or not data.get("registry_version"):
        raise RegistryError("registry_version is required")
    senses = data.get("senses")
    spans = data.get("gestalt_spans")
    if not isinstance(senses, list) or not isinstance(spans, list):
        raise RegistryError("senses and gestalt_spans must be arrays")

    for entries, id_key in ((senses, "sense_id"), (spans, "span_id")):
        ids = [entry.get(id_key) for entry in entries]
        if None in ids or len(ids) != len(set(ids)):
            raise RegistryError(f"{id_key} values must be present and unique")

    for entry in senses:
        if not entry.get("gestalt") or not entry.get("surface_forms"):
            raise RegistryError(f"incomplete sense: {entry.get('sense_id')}")
    for entry in spans:
        if not entry.get("gestalt") or not entry.get("phrases"):
            raise RegistryError(f"incomplete span: {entry.get('span_id')}")
        if not entry.get("protected_invariants"):
            raise RegistryError(f"span has no invariants: {entry.get('span_id')}")


def load_registry(path: str | Path | None = None) -> dict:
    source = Path(path) if path else DEFAULT_REGISTRY_PATH
    data = json.loads(source.read_text(encoding="utf-8"))
    validate_registry(data)
    return data


def sense_by_id(sense_id: str, registry: dict | None = None) -> dict | None:
    registry = registry or load_registry()
    return next((entry for entry in registry["senses"] if entry["sense_id"] == sense_id), None)
