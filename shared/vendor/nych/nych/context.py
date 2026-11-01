"""
NYCH Context Construction Module
=================================
Construct Domain + Subject + Intent + Competency + available objects/tools
+ prior/current internal/external state.
Domain and subdomains and everything within will populate a hierarchical
domain database and ultimately a TOTE loop database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.types import CognitiveOperator, CompetencyLevel, ControlOperator, Modality, NychContext, NychPacket, NychState, Perspective, Tense


@dataclass(frozen=True)
class ConstructedContext:
    """Result of context construction."""
    context: NychContext
    domain_expansion_path: list[str] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)
    prior_state_ref: str | None = None
    subdomains: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)
    competency_level: CompetencyLevel = CompetencyLevel.INTERMEDIATE


def build_context(
    packet: NychPacket,
    state: NychState,
    identity: Any,
    invariants: Any,
    symbolization: Any,
) -> ConstructedContext:
    """
    Construct the full NYCH context from pipeline outputs.
    
    Domain + Subject + Intent + Competency + tools + state
    Domain and subdomains and everything within will begin to populate a
    hierarchical domain database.
    
    Args:
        packet: The current NYCH packet.
        state: The current NYCH state.
        identity: Identity analysis result.
        invariants: Extracted invariants.
        symbolization: Symbolization result.
    
    Returns:
        ConstructedContext with full context information.
    """
    # Determine domain from domain markers
    domain = _determine_domain(invariants, symbolization)
    
    # Determine subject
    subject = _determine_subject(packet, identity, state)
    
    # Determine intent
    intent = _determine_intent(invariants, symbolization, packet)
    
    # Determine competency level
    competency_level = getattr(identity, "competency_level", CompetencyLevel.INTERMEDIATE)
    competency = competency_level.value if isinstance(competency_level, CompetencyLevel) else str(competency_level)
    
    # Determine available tools
    available_tools = _determine_tools(domain, competency)
    
    # Build domain expansion path
    domain_expansion_path = _build_domain_path(domain)
    
    # Determine subdomains and specialties
    subdomains, specialties = _determine_subdomains_specialties(domain)
    
    # Determine modality
    modality = getattr(identity, "modality", Modality.LANGUAGE)
    if invariants and hasattr(invariants, "modality") and invariants.modality != Modality.LANGUAGE:
        modality = invariants.modality
    
    # Determine perspective and tense
    perspective = getattr(identity, "perspective", None)
    tense = getattr(identity, "tense", None)
    
    context = NychContext(
        domain=domain,
        subject=subject,
        intent=intent,
        competency=competency,
        modality=modality,
        perspective=perspective,
        tense=tense,
        tools=available_tools,
        subdomains=subdomains,
        specialties=specialties,
    )
    
    return ConstructedContext(
        context=context,
        domain_expansion_path=domain_expansion_path,
        available_tools=available_tools,
        subdomains=subdomains,
        specialties=specialties,
        competency_level=competency_level,
    )


def _determine_domain(invariants: Any, symbolization: Any) -> str:
    """Determine the primary domain from invariants and symbols."""
    domain_markers = getattr(invariants, "domain_markers", [])
    if domain_markers:
        return domain_markers[0]
    
    # Fallback: infer from symbols
    symbols = getattr(symbolization, "symbols", [])
    if symbols:
        return "general"
    
    return "unknown"


def _determine_subject(packet: NychPacket, identity: Any, state: NychState) -> str:
    """Determine the subject of the operation."""
    if packet.source_type.value == "sensor":
        device = getattr(identity, "device_id", None)
        if device:
            return device
    
    # Try to extract from state
    current = state.current or {}
    subject = current.get("subject")
    if subject:
        return str(subject)
    
    # Try to extract from packet metadata
    metadata = packet.metadata_refs or {}
    subject = metadata.get("subject")
    if subject:
        return str(subject)
    
    return "unknown"


def _determine_intent(invariants: Any, symbolization: Any, packet: NychPacket) -> str:
    """Determine the intent from cognitive operators and symbols."""
    cognitive_ops = getattr(invariants, "cognitive_operators", [])
    
    if CognitiveOperator.IMAGINE in cognitive_ops:
        return "imagine"
    elif CognitiveOperator.COMPARE in cognitive_ops:
        return "compare"
    elif CognitiveOperator.REMEMBER in cognitive_ops:
        return "remember"
    elif CognitiveOperator.EQUAL in cognitive_ops or CognitiveOperator.NOT_EQUAL in cognitive_ops:
        return "evaluate"
    
    # Check control operators
    control_ops = getattr(invariants, "control_operators", [])
    if ControlOperator.LOOP_START in control_ops:
        return "iterate"
    elif ControlOperator.TEST in control_ops:
        return "test"
    elif ControlOperator.OPERATE in control_ops:
        return "operate"
    
    # Check symbols for intent hints
    symbols = getattr(symbolization, "symbols", [])
    symbol_intents = {
        "🧪": "test",
        "🔨": "build",
        "✅": "validate",
        "🔄": "iterate",
        "📊": "analyze",
        "🎨": "design",
        "💻": "develop",
    }
    for sym in symbols:
        if sym in symbol_intents:
            return symbol_intents[sym]
    
    return "process"


def _determine_tools(domain: str, competency: str) -> list[str]:
    """Determine available tools for the domain and competency."""
    domain_tools = {
        "programming": ["compiler", "interpreter", "debugger", "linter"],
        "data_processing": ["analyzer", "transformer", "validator"],
        "testing": ["test_runner", "coverage_tool", "mock_framework"],
        "medical": ["stethoscope", "syringe", "monitor", "xray"],
        "construction": ["hammer", "saw", "drill", "level", "tape_measure"],
        "design": ["sketchpad", "prototype_tool", "wireframe_editor"],
        "legal": ["legal_db", "document_manager", "citation_tool"],
        "finance": ["accounting_software", "spreadsheet", "trading_platform"],
    }
    return domain_tools.get(domain, ["generic_tool"])


def _build_domain_path(domain: str) -> list[str]:
    """
    Build the domain expansion path: Domain -> Discipline -> Function -> Technique.
    """
    return [domain, f"{domain}_discipline", f"{domain}_function", f"{domain}_technique"]


def _determine_subdomains_specialties(domain: str) -> tuple[list[str], list[str]]:
    """Determine subdomains and specialties for a domain."""
    from nych.domain import get_domain_ontology
    ontology = get_domain_ontology().get(domain, {})
    subdomains = ontology.get("subdomains", ["general"])
    specialties = ontology.get("specialties", ["general"])
    return subdomains, specialties
