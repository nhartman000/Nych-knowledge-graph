"""
NYCH Feature Normalization Module
==================================
Preserve numbers; convert sensor patterns to typed gestalts;
remove non-semantic language filler only under explicit rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from nych.types import NychPacket, NychState


@dataclass(frozen=True)
class NormalizedFeatures:
    """Result of feature normalization."""
    text: str
    numbers: list[float] = field(default_factory=list)
    gestalts: list[str] = field(default_factory=list)
    filler_removed: list[str] = field(default_factory=list)
    is_sensor: bool = False


def normalize_features(
    packet: NychPacket,
    state: NychState,
    raw_input: Any,
) -> NormalizedFeatures:
    """
    Normalize features from the input.
    
    - Preserve numerical values.
    - Convert sensor patterns to typed gestalts.
    - Remove non-semantic language filler only under explicit rules.
    
    Args:
        packet: The current NYCH packet.
        state: The current NYCH state.
        raw_input: The original raw input data.
    
    Returns:
        NormalizedFeatures with normalized content.
    """
    if packet.source_type.value == "sensor":
        return _normalize_sensor(packet, state, raw_input)
    else:
        return _normalize_text(packet, state, raw_input)


def _normalize_text(
    packet: NychPacket,
    state: NychState,
    raw_input: Any,
) -> NormalizedFeatures:
    """Normalize text input."""
    text = ""
    if hasattr(raw_input, "text"):
        text = raw_input.text
    elif isinstance(raw_input, dict):
        text = raw_input.get("text", str(raw_input))
    else:
        text = str(raw_input)
    
    # Extract and preserve numbers
    numbers = _extract_numbers(text)
    
    # Remove filler words (explicit rule: only common filler)
    filler_words = {
        "um", "uh", "er", "ah", "like", "you know", "i mean",
        "basically", "actually", "literally", "so", "well",
    }
    words = text.split()
    filler_removed = [w for w in words if w.lower().strip(".,!?;:") in filler_words]
    cleaned_words = [w for w in words if w.lower().strip(".,!?;:") not in filler_words]
    cleaned_text = " ".join(cleaned_words)
    
    return NormalizedFeatures(
        text=cleaned_text,
        numbers=numbers,
        filler_removed=filler_removed,
        is_sensor=False,
    )


def _normalize_sensor(
    packet: NychPacket,
    state: NychState,
    raw_input: Any,
) -> NormalizedFeatures:
    """Normalize sensor input to typed gestalts."""
    data = {}
    if hasattr(raw_input, "data"):
        data = raw_input.data
    elif isinstance(raw_input, dict):
        data = raw_input
    
    # Extract numbers from sensor data
    numbers = _extract_numbers_from_dict(data)
    
    # Convert sensor patterns to typed gestalts
    gestalts = _extract_gestalts(data)
    
    return NormalizedFeatures(
        text=str(data),
        numbers=numbers,
        gestalts=gestalts,
        is_sensor=True,
    )


def _extract_numbers(text: str) -> list[float]:
    """Extract numerical values from text."""
    pattern = r"-?\d+\.?\d*"
    matches = re.findall(pattern, text)
    return [float(m) for m in matches if m]


def _extract_numbers_from_dict(data: dict[str, Any]) -> list[float]:
    """Recursively extract numerical values from a dictionary."""
    numbers = []
    for value in data.values():
        if isinstance(value, (int, float)):
            numbers.append(float(value))
        elif isinstance(value, dict):
            numbers.extend(_extract_numbers_from_dict(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (int, float)):
                    numbers.append(float(item))
                elif isinstance(item, dict):
                    numbers.extend(_extract_numbers_from_dict(item))
    return numbers


def _extract_gestalts(data: dict[str, Any]) -> list[str]:
    """
    Convert sensor patterns to typed gestalts.
    
    This is a placeholder implementation. In production, this would
    use a trained model or rule set to identify sensor gestalts.
    """
    gestalts = []
    for key, value in data.items():
        if isinstance(value, bool):
            gestalts.append(f"BOOL:{key}:{value}")
        elif isinstance(value, (int, float)):
            gestalts.append(f"NUM:{key}:{value}")
        elif isinstance(value, str):
            gestalts.append(f"STR:{key}:{value[:32]}")
    return gestalts
