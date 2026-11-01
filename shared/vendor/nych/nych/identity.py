"""
NYCH Identity / Vernacular Module
=================================
For language: determine speaker/narrative perspective, competency level
(novice vs expert), and vernacular context.
For sensor streams: bind source/device identity and modality metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.types import CompetencyLevel, Modality, NychContext, NychPacket, Perspective, SourceType, Tense


@dataclass(frozen=True)
class IdentityResult:
    """Result of identity/vernacular analysis."""
    speaker: str | None = None
    perspective: Perspective | None = None
    tense: Tense | None = None
    vernacular_markers: list[str] = field(default_factory=list)
    device_id: str | None = None
    modality: Modality = Modality.LANGUAGE
    competency_level: CompetencyLevel = CompetencyLevel.INTERMEDIATE
    competency_evidence: list[str] = field(default_factory=list)
    pronouns: list[str] = field(default_factory=list)


def analyze_identity(
    packet: NychPacket,
    context: NychContext,
    raw_input: Any,
) -> IdentityResult:
    """
    Determine speaker/narrative perspective and vernacular context
    for language inputs, or bind source/device identity for sensor inputs.
    
    Also performs competency check using vernacular to ascertain if the user
    is highly competent (expert) or a novice.
    
    Args:
        packet: The current NYCH packet.
        context: The current NYCH context.
        raw_input: The original raw input data.
    
    Returns:
        IdentityResult with identity and competency information.
    """
    if packet.source_type == SourceType.NATURAL_LANGUAGE:
        return _analyze_language_identity(packet, context, raw_input)
    elif packet.source_type == SourceType.SENSOR:
        return _analyze_sensor_identity(packet, context, raw_input)
    else:
        return IdentityResult()


def _analyze_language_identity(
    packet: NychPacket,
    context: NychContext,
    raw_input: Any,
) -> IdentityResult:
    """Analyze language input for speaker, perspective, tense, and competency."""
    text = ""
    speaker = None
    perspective = None
    tense = None
    vernacular_markers = []
    pronouns = []
    competency_level = CompetencyLevel.INTERMEDIATE
    competency_evidence = []
    
    if hasattr(raw_input, "text"):
        text = raw_input.text
        speaker = getattr(raw_input, "speaker", None)
        raw_perspective = getattr(raw_input, "perspective", None)
        raw_tense = getattr(raw_input, "tense", None)
        
        perspective = _infer_perspective(text, raw_perspective)
        tense = _infer_tense(text, raw_tense)
        vernacular_markers = _extract_vernacular_markers(text)
        pronouns = _extract_pronouns(text)
        
        # Competency check using vernacular
        competency_level, competency_evidence = _assess_competency(text)
    
    return IdentityResult(
        speaker=speaker,
        perspective=perspective,
        tense=tense,
        vernacular_markers=vernacular_markers,
        pronouns=pronouns,
        competency_level=competency_level,
        competency_evidence=competency_evidence,
    )


def _analyze_sensor_identity(
    packet: NychPacket,
    context: NychContext,
    raw_input: Any,
) -> IdentityResult:
    """Analyze sensor input for device identity and modality."""
    device_id = None
    modality = context.modality
    
    if hasattr(raw_input, "source_device"):
        device_id = raw_input.source_device
    elif hasattr(raw_input, "data") and isinstance(raw_input.data, dict):
        device_id = raw_input.data.get("device_id") or raw_input.data.get("source")
    
    if hasattr(raw_input, "modality"):
        modality = raw_input.modality
    
    return IdentityResult(
        device_id=device_id,
        modality=modality,
        competency_level=CompetencyLevel.INTERMEDIATE,
    )


def _infer_perspective(text: str, explicit: str | None) -> Perspective | None:
    """Infer narrative perspective from text."""
    if explicit:
        mapping = {
            "first": Perspective.FIRST,
            "second": Perspective.SECOND,
            "third": Perspective.THIRD,
            "1st": Perspective.FIRST,
            "2nd": Perspective.SECOND,
            "3rd": Perspective.THIRD,
        }
        return mapping.get(explicit.lower())
    
    # Simple heuristic: first-person pronouns
    first_person = {"i", "me", "my", "mine", "we", "us", "our"}
    second_person = {"you", "your", "yours"}
    
    words = set(text.lower().split())
    if words & first_person:
        return Perspective.FIRST
    elif words & second_person:
        return Perspective.SECOND
    else:
        return Perspective.THIRD


def _infer_tense(text: str, explicit: str | None) -> Tense | None:
    """Infer tense from text."""
    if explicit:
        mapping = {
            "past": Tense.PAST,
            "present": Tense.PRESENT,
            "future": Tense.FUTURE,
        }
        return mapping.get(explicit.lower())
    
    # Simple heuristic checks
    past_markers = {"ed", "was", "were", "had", "did", "went", "came"}
    future_markers = {"will", "shall", "going to", "gonna", "about to"}
    
    words = set(text.lower().split())
    if any(marker in words for marker in future_markers):
        return Tense.FUTURE
    elif any(marker in words for marker in past_markers):
        return Tense.PAST
    else:
        return Tense.PRESENT


def _extract_pronouns(text: str) -> list[str]:
    """Extract pronouns from text."""
    _PRONOUNS = {
        "i", "me", "my", "mine", "we", "us", "our", "ours",
        "you", "your", "yours", "he", "him", "his", "she", "her", "hers",
        "it", "its", "they", "them", "their", "theirs",
    }
    words = set(text.lower().split())
    return list(words & _PRONOUNS)


def _extract_vernacular_markers(text: str) -> list[str]:
    """Extract vernacular/dialect markers from text."""
    markers = []
    # Placeholder: in production, this would use a vernacular model
    # or lookup table. For now, return empty list.
    return markers


def _assess_competency(text: str) -> tuple[CompetencyLevel, list[str]]:
    """
    Assess user competency level from vernacular.
    
    This is the point in the pipeline that the competency check is performed
    using vernacular to ascertain if the user is highly competent or a novice.
    Prune response vector to accommodate the anticipated response space.
    
    Novice: broad strokes, more explanation
    Expert: pointed, speaks to mastery
    
    Returns:
        Tuple of (competency_level, evidence_list)
    """
    evidence = []
    text_lower = text.lower()
    words = set(text_lower.split())
    
    # Expert indicators
    expert_indicators = {
        "elegant", "optimize", "refactor", "idiomatic", "asynchronous",
        "concurrent", "deterministic", "probabilistic", "invariant",
        "symbolic", "canonical", "orthogonal", "semantic", "gestalt",
        "trajectory", "modality", "operator", "tote", "loop",
        "validate", "constraint", "admissible", "feasibility",
        "implementation", "architecture", "abstraction", "polymorphism",
    }
    
    # Novice indicators
    novice_indicators = {
        "simple", "basic", "easy", "beginner", "learn", "tutorial",
        "step by step", "help me", "i don't understand", "confused",
        "explain", "what is", "how do i", "can you show",
    }
    
    expert_count = len(words & expert_indicators)
    novice_count = len(words & novice_indicators)
    
    # Score-based classification
    if expert_count >= 3:
        competency_level = CompetencyLevel.EXPERT
        evidence = [f"expert_indicators_found_{expert_count}"]
    elif expert_count >= 1:
        competency_level = CompetencyLevel.INTERMEDIATE
        evidence = [f"mixed_indicators_found_{expert_count}_{novice_count}"]
    elif novice_count >= 2:
        competency_level = CompetencyLevel.NOVICE
        evidence = [f"novice_indicators_found_{novice_count}"]
    else:
        competency_level = CompetencyLevel.INTERMEDIATE
        evidence = ["default_intermediate"]
    
    return competency_level, evidence
