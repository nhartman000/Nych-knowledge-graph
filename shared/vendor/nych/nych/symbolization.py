"""
NYCH Symbolization Module
=========================
Select deterministic semantic anchor from a versioned symbol table/model;
produce consonant skeleton for lexical payload where applicable.
Gestalt extraction maps sensor data and words to emoji representations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from nych.exceptions import SymbolizationError
from nych.types import Modality, NychPacket, NychState


@dataclass(frozen=True)
class SymbolizationResult:
    """Result of symbolization."""
    symbols: list[str] = field(default_factory=list)
    consonant_skeletons: list[str] = field(default_factory=list)
    semantic_anchors: list[str] = field(default_factory=list)
    symbol_table_version: str = "1.0.0"
    gestalt_emoji: list[str] = field(default_factory=list)
    numeric_embeddings: list[float] = field(default_factory=list)


# Versioned symbol table (canonical mapping)
_SYMBOL_TABLE: dict[str, dict[str, str]] = {
    "1.0.0": {
        # Domain markers
        "programming": "💻",
        "data": "📊",
        "build": "🔨",
        "design": "🎨",
        "test": "🧪",
        "validate": "✅",
        "loop": "🔄",
        "exit": "🚪",
        "error": "❌",
        "success": "✅",
        # Medical
        "doctor": "🩺",
        "intern": "🏥",
        "patient": "🤒",
        "diagnosis": "🔬",
        "treatment": "💊",
        "medicine": "💉",
        "health": "❤️",
        "hospital": "🏥",
        # Construction
        "hammer": "🔨",
        "nail": "📌",
        "foundation": "🏗️",
        "framework": "🏗️",
        "materials": "🧱",
        "tools": "🛠️",
        # Cognitive operators
        "remember": "💭",
        "imagine": "🗯️",
        "compare": "⚖️",
        "equal": "=",
        "not_equal": "≠",
        # Common concepts
        "system": "⚙️",
        "process": "⚙️",
        "input": "📥",
        "output": "📤",
        "state": "📋",
        "transform": "🔄",
        "action": "⚡",
        # Actions
        "swing": "💪",
        "check": "✅",
        "observe": "👀",
        "visualize": "👁️",
        "hear": "👂",
        "smell": "👃",
        "taste": "👅",
        "think": "🧠",
    }
}

# Gestalt emoji mapping for sensor data types
_GESTALT_EMOJI_MAP: dict[str, str] = {
    "temperature": "🌡️",
    "humidity": "💧",
    "pressure": "📈",
    "vision": "👁️",
    "audio": "🔊",
    "kinematic": "🏃",
    "telemetry": "📡",
    "error": "❌",
    "warning": "⚠️",
    "success": "✅",
}


def symbolicate(
    packet: NychPacket,
    state: NychState,
    invariants: Any,
    normalized: Any,
) -> SymbolizationResult:
    """
    Select deterministic semantic anchors and produce consonant skeletons.
    Gestalt extraction maps sensor data to emoji representations.
    
    Args:
        packet: The current NYCH packet.
        state: The current NYCH state.
        invariants: Extracted invariants.
        normalized: Normalized features.
    
    Returns:
        SymbolizationResult with symbols, skeletons, and gestalt emoji.
    """
    text = normalized.text if hasattr(normalized, "text") else str(normalized)
    version = packet.version
    
    # Get symbol table for this version
    table = _SYMBOL_TABLE.get(version, _SYMBOL_TABLE.get("1.0.0", {}))
    
    # Select semantic anchors via gestalt match
    symbols = _select_semantic_anchors(text, table)
    
    # Produce consonant skeletons for lexical payloads
    consonant_skeletons = _produce_consonant_skeletons(text)
    
    # Extract gestalt emoji for sensor data or modal representations
    gestalt_emoji = _extract_gestalt_emoji(text, normalized, invariants)
    
    # Extract numeric embeddings
    numeric_embeddings = _extract_numeric_embeddings(normalized)
    
    return SymbolizationResult(
        symbols=symbols,
        consonant_skeletons=consonant_skeletons,
        semantic_anchors=symbols,
        symbol_table_version=version,
        gestalt_emoji=gestalt_emoji,
        numeric_embeddings=numeric_embeddings,
    )


def _select_semantic_anchors(text: str, table: dict[str, str]) -> list[str]:
    """
    Select deterministic semantic anchors from the symbol table.
    
    Uses gestalt matching: first match wins, sorted by position.
    """
    text_lower = text.lower()
    found = []
    seen_positions = set()
    
    # Sort by length descending to match longer phrases first
    sorted_terms = sorted(table.keys(), key=len, reverse=True)
    
    for term in sorted_terms:
        pos = text_lower.find(term)
        if pos != -1 and pos not in seen_positions:
            symbol = table[term]
            if symbol not in found:
                found.append(symbol)
            # Mark positions as used to avoid overlaps
            for i in range(pos, pos + len(term)):
                seen_positions.add(i)
    
    return found


def _produce_consonant_skeletons(text: str) -> list[str]:
    """
    Produce consonant skeletons by removing vowels and duplicate consonants.
    
    Per canonical rule set: all other words that can be reduced to a single symbol
    by gestalt match are converted and vowels omitted and double consonants.
    The resulting string is appended to the symbol trace id.
    
    Example: "hammer" -> "hmmr", "nail" -> "nl"
    """
    words = text.split()
    skeletons = []
    
    for word in words:
        # Remove non-alphabetic characters
        clean = re.sub(r"[^a-zA-Z]", "", word).lower()
        if not clean:
            continue
        
        # Remove vowels
        consonants = re.sub(r"[aeiou]", "", clean)
        
        # Remove duplicate consecutive consonants
        deduped = re.sub(r"(.)\1+", r"\1", consonants)
        
        if deduped and len(deduped) > 1:
            skeletons.append(deduped)
    
    return skeletons


def _extract_gestalt_emoji(text: str, normalized: Any, invariants: Any) -> list[str]:
    """
    Extract gestalt emoji representations for sensor data or modal content.
    
    Sensor Data -> Gestalt -> Emoji Representation
    Numbers -> Numerical Embeddings | Data Type Iconization
    """
    gestalts = []
    
    # Extract from normalized gestalts (sensor data)
    if hasattr(normalized, "gestalts"):
        for gestalt in normalized.gestalts:
            if isinstance(gestalt, str):
                for key, emoji in _GESTALT_EMOJI_MAP.items():
                    if key in gestalt.lower():
                        gestalts.append(emoji)
                        break
    
    # Extract modality-based gestalt from invariants
    if invariants and hasattr(invariants, "modality_operators"):
        for op in invariants.modality_operators:
            gestalts.append(op)
    
    # Extract from text keywords
    text_lower = text.lower()
    for key, emoji in _GESTALT_EMOJI_MAP.items():
        if key in text_lower and emoji not in gestalts:
            gestalts.append(emoji)
    
    return gestalts


def _extract_numeric_embeddings(normalized: Any) -> list[float]:
    """Extract numeric embeddings from normalized features."""
    if hasattr(normalized, "numbers"):
        return normalized.numbers
    elif hasattr(normalized, "numeric_values"):
        return normalized.numeric_values
    return []


def get_symbol_table_version() -> str:
    """Get the current symbol table version."""
    return "1.0.0"


def validate_symbol_table(version: str) -> bool:
    """Validate that a symbol table version exists."""
    return version in _SYMBOL_TABLE
