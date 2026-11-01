"""
NYCH Invariant Extraction Module
=================================
Extract modality, person, tense, cognitive/control operators, domain markers,
narrative perspective, pronouns, domain, subject and subdomains per canonical rule set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from nych.types import (
    CognitiveOperator,
    ControlOperator,
    Modality,
    NychPacket,
    NychState,
    Perspective,
    Tense,
)


@dataclass(frozen=True)
class InvariantExtract:
    """Result of invariant extraction."""
    modality: Modality = Modality.LANGUAGE
    person: str | None = None
    tense: Tense | None = None
    perspective: Perspective | None = None
    cognitive_operators: list[CognitiveOperator] = field(default_factory=list)
    control_operators: list[ControlOperator] = field(default_factory=list)
    domain_markers: list[str] = field(default_factory=list)
    numerical_constants: list[float] = field(default_factory=list)
    modality_operators: list[str] = field(default_factory=list)
    pronouns: list[str] = field(default_factory=list)


# Mapping of keywords to operators per canonical rule set
_COGNITIVE_KEYWORDS: dict[str, CognitiveOperator] = {
    "remember": CognitiveOperator.REMEMBER,
    "recall": CognitiveOperator.REMEMBER,
    "imagine": CognitiveOperator.IMAGINE,
    "visualize": CognitiveOperator.IMAGINE,
    "compare": CognitiveOperator.COMPARE,
    "contrast": CognitiveOperator.COMPARE,
    "equal": CognitiveOperator.EQUAL,
    "same": CognitiveOperator.EQUAL,
    "not equal": CognitiveOperator.NOT_EQUAL,
    "different": CognitiveOperator.NOT_EQUAL,
    "differs": CognitiveOperator.NOT_EQUAL,
}

_CONTROL_KEYWORDS: dict[str, ControlOperator] = {
    "loop": ControlOperator.LOOP_START,
    "repeat": ControlOperator.LOOP_START,
    "iterate": ControlOperator.LOOP_START,
    "exit": ControlOperator.LOOP_EXIT,
    "break": ControlOperator.LOOP_EXIT,
    "stop": ControlOperator.LOOP_EXIT,
    "test": ControlOperator.TEST,
    "check": ControlOperator.TEST,
    "verify": ControlOperator.TEST,
    "operate": ControlOperator.OPERATE,
    "execute": ControlOperator.OPERATE,
    "perform": ControlOperator.OPERATE,
    "run": ControlOperator.OPERATE,
}

# Mapping of modality emoji symbols to operators per canonical rule set
_MODALITY_EMOJI_MAP: dict[str, Modality] = {
    "👀": Modality.VE,
    "👁️": Modality.VI,
    "👂": Modality.AE,
    "👂🏼": Modality.AE,
    "💪": Modality.KE,
    "💪🏼": Modality.KE,
    "👃": Modality.SME,
    "👅": Modality.TAS,
    "🧠": Modality.MEN,
    "🗯️": Modality.IMG,
    "💭": Modality.REM,
}

_PERSON_PRONOUNS: dict[str, str] = {
    "i": "first",
    "me": "first",
    "my": "first",
    "mine": "first",
    "we": "first",
    "us": "first",
    "our": "first",
    "you": "second",
    "your": "second",
    "yours": "second",
    "he": "third",
    "she": "third",
    "it": "third",
    "they": "third",
    "them": "third",
    "their": "third",
}

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "programming": ["code", "function", "variable", "program", "software", "debug", "compile", "deploy"],
    "medical": ["doctor", "intern", "patient", "diagnosis", "treatment", "symptom", "medicine", "health", "hospital"],
    "construction": ["build", "construct", "hammer", "nail", "foundation", "framework", "materials", "tools"],
    "design": ["design", "plan", "sketch", "prototype", "wireframe", "layout", "creative", "aesthetic"],
    "data_processing": ["data", "analyze", "analyze", "dataset", "database", "query", "transform", "pipeline"],
    "testing": ["test", "validate", "verify", "qa", "automation", "coverage", "assertion"],
    "legal": ["law", "court", "contract", "legal", "compliance", "regulation", "attorney", "judge"],
    "finance": ["money", "invest", "trade", "stock", "budget", "finance", "bank", "accounting"],
}


def extract_invariants(
    packet: NychPacket,
    state: NychState,
    normalized: Any,
) -> InvariantExtract:
    """
    Extract invariant operators and markers from normalized input.
    
    The first processing done is to determine the narrative perspective, tense,
    pronouns, domain, subject and subdomains which include specialties which are
    made up of functions made up of techniques which terminate as object actor,
    action T.O.T.E loops.
    
    Args:
        packet: The current NYCH packet.
        state: The current NYCH state.
        normalized: Normalized features from the normalization stage.
    
    Returns:
        InvariantExtract with extracted invariants.
    """
    text = normalized.text if hasattr(normalized, "text") else str(normalized)
    text_lower = text.lower()
    
    # Extract modality operators (invariant)
    modality, modality_operators = _extract_modality_operators(text)
    
    # Extract cognitive operators
    cognitive_ops = _extract_cognitive_operators(text_lower)
    
    # Extract control operators
    control_ops = _extract_control_operators(text_lower)
    
    # Extract person/pronouns
    person, pronouns = _extract_person_and_pronouns(text_lower)
    
    # Extract narrative perspective
    perspective = _infer_perspective(text_lower, person)
    
    # Extract tense
    tense = _infer_tense(text_lower)
    
    # Extract domain markers
    domain_markers = _extract_domain_markers(text_lower)
    
    # Extract numerical constants
    numerical_constants = normalized.numbers if hasattr(normalized, "numbers") else []
    
    return InvariantExtract(
        modality=modality,
        person=person,
        tense=tense,
        perspective=perspective,
        cognitive_operators=cognitive_ops,
        control_operators=control_ops,
        domain_markers=domain_markers,
        numerical_constants=numerical_constants,
        modality_operators=modality_operators,
        pronouns=pronouns,
    )


def _extract_modality_operators(text: str) -> tuple[Modality, list[str]]:
    """
    Extract invariant modality operators from text.
    
    Modality operators are invariant and remain unchanged through the pipeline.
    """
    found_operators = []
    found_modality = Modality.LANGUAGE
    
    for emoji, modality in _MODALITY_EMOJI_MAP.items():
        if emoji in text:
            found_operators.append(modality.value)
            if found_modality == Modality.LANGUAGE:
                found_modality = modality
    
    return found_modality, found_operators


def _extract_cognitive_operators(text: str) -> list[CognitiveOperator]:
    """Extract cognitive operators from text."""
    found = []
    for keyword, op in _COGNITIVE_KEYWORDS.items():
        if keyword in text:
            if op not in found:
                found.append(op)
    return found


def _extract_control_operators(text: str) -> list[ControlOperator]:
    """Extract control operators from text."""
    found = []
    for keyword, op in _CONTROL_KEYWORDS.items():
        if keyword in text:
            if op not in found:
                found.append(op)
    return found


def _extract_person_and_pronouns(text: str) -> tuple[str | None, list[str]]:
    """Extract grammatical person and pronouns from text."""
    words = set(text.split())
    found_pronouns = []
    found_person = None
    
    for pronoun, person in _PERSON_PRONOUNS.items():
        if pronoun in words:
            found_pronouns.append(pronoun)
            if found_person is None:
                found_person = person
    
    return found_person, found_pronouns


def _infer_perspective(text: str, person: str | None) -> Perspective | None:
    """Infer narrative perspective from person."""
    if person is None:
        return None
    
    mapping = {
        "first": Perspective.FIRST,
        "second": Perspective.SECOND,
        "third": Perspective.THIRD,
    }
    return mapping.get(person)


def _infer_tense(text: str) -> Tense | None:
    """Infer tense from text."""
    past_markers = {"ed", "was", "were", "had", "did", "went", "came", "built", "tested", "saw"}
    future_markers = {"will", "shall", "going to", "gonna", "about to", "plan to"}
    
    words = set(text.lower().split())
    if any(marker in words for marker in future_markers):
        return Tense.FUTURE
    elif any(marker in words for marker in past_markers):
        return Tense.PAST
    else:
        return Tense.PRESENT


def _extract_domain_markers(text: str) -> list[str]:
    """
    Extract domain markers from text.
    
    This uses the canonical domain ontology to identify domain-specific terminology.
    """
    found = []
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            found.append(domain)
    return found
