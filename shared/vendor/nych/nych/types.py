"""
NYCH Typed Interfaces
=====================
Canonical data contracts for the NYCH symbolic pipeline.
All types are frozen dataclasses to enforce immutability and determinism.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SourceType(str, Enum):
    """Origin of the input data."""
    NATURAL_LANGUAGE = "natural_language"
    SENSOR = "sensor"
    SYMBOLIC_PACKET = "symbolic_packet"
    INTERNAL_STATE = "internal_state"


class Modality(str, Enum):
    """Invariant perceptual modality operators."""
    VE = "VE"
    VI = "VI"
    AE = "AE"
    AI = "AI"
    KE = "KE"
    KI = "KI"
    SME = "SME"
    TAS = "TAS"
    MEN = "MEN"
    IMG = "IMG"
    REM = "REM"
    LANGUAGE = "LANGUAGE"


class CognitiveOperator(str, Enum):
    """Invariant cognitive operators."""
    REMEMBER = "Remember"
    IMAGINE = "Imagine"
    COMPARE = "Compare"
    EQUAL = "Equal"
    NOT_EQUAL = "NotEqual"
    AI = "AI"
    AE = "AE"
    VE = "VE"
    VI = "VI"
    KE = "KE"
    KI = "KI"


class ControlOperator(str, Enum):
    """Invariant control operators."""
    LOOP_START = "LoopStart"
    LOOP_EXIT = "LoopExit"
    TEST = "Test"
    OPERATE = "Operate"
    EXIT = "Exit"


class Tense(str, Enum):
    """Temporal perspective."""
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"


class Perspective(str, Enum):
    """Narrative perspective."""
    FIRST = "first"
    SECOND = "second"
    THIRD = "third"


class CompetencyLevel(str, Enum):
    """Competency levels for user classification."""
    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


@dataclass(frozen=True)
class NychPacket:
    """
    Canonical NYCH packet representing a normalized input.
    
    Fields:
        packet_id: Unique identifier for this packet.
        version: Version of the symbol table/model used.
        source_type: Origin of the input data.
        symbols: List of semantic anchors selected from symbol table.
        operators: List of invariant operators extracted.
        numeric_values: Preserved numerical quantities.
        metadata_refs: References to additional metadata (e.g., lexical payloads).
    """
    packet_id: str
    version: str
    source_type: SourceType
    symbols: list[str] = field(default_factory=list)
    operators: list[str] = field(default_factory=list)
    numeric_values: list[float] = field(default_factory=list)
    metadata_refs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.packet_id:
            raise ValueError("packet_id must be non-empty")
        if not self.version:
            raise ValueError("version must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "version": self.version,
            "source_type": self.source_type.value,
            "symbols": self.symbols,
            "operators": self.operators,
            "numeric_values": self.numeric_values,
            "metadata_refs": self.metadata_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NychPacket:
        return cls(
            packet_id=data["packet_id"],
            version=data["version"],
            source_type=SourceType(data["source_type"]),
            symbols=data.get("symbols", []),
            operators=data.get("operators", []),
            numeric_values=data.get("numeric_values", []),
            metadata_refs=data.get("metadata_refs", {}),
        )


@dataclass(frozen=True)
class NychContext:
    """
    Contextual information surrounding a NYCH packet.
    
    Fields:
        domain: Primary domain of operation.
        subject: Subject of the operation/statement.
        intent: Declared or inferred target-state preference.
        competency: Required competency level.
        modality: Perceptual modality.
        perspective: Narrative perspective (for language).
        tense: Temporal perspective (for language).
        tools: Available tools/objects.
        constraints: Active constraints.
        subdomains: List of subdomains within the domain.
        specialties: List of specialties within the domain.
    """
    domain: str
    subject: str
    intent: str
    competency: str
    modality: Modality = Modality.LANGUAGE
    perspective: Optional[Perspective] = None
    tense: Optional[Tense] = None
    tools: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    subdomains: list[str] = field(default_factory=list)
    specialties: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.domain:
            raise ValueError("domain must be non-empty")
        if not self.subject:
            raise ValueError("subject must be non-empty")
        if not self.intent:
            raise ValueError("intent must be non-empty")
        if not self.competency:
            raise ValueError("competency must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "subject": self.subject,
            "intent": self.intent,
            "competency": self.competency,
            "modality": self.modality.value,
            "perspective": self.perspective.value if self.perspective else None,
            "tense": self.tense.value if self.tense else None,
            "tools": self.tools,
            "constraints": self.constraints,
            "subdomains": self.subdomains,
            "specialties": self.specialties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NychContext:
        return cls(
            domain=data["domain"],
            subject=data["subject"],
            intent=data["intent"],
            competency=data["competency"],
            modality=Modality(data.get("modality", "LANGUAGE")),
            perspective=Perspective(data["perspective"]) if data.get("perspective") else None,
            tense=Tense(data["tense"]) if data.get("tense") else None,
            tools=data.get("tools", []),
            constraints=data.get("constraints", []),
            subdomains=data.get("subdomains", []),
            specialties=data.get("specialties", []),
        )


@dataclass(frozen=True)
class NychState:
    """
    State model with prior/current and internal/external channels.
    
    Fields:
        prior: Previous current state.
        current: Current observed/result state.
        internal_prior: Previous internal state.
        internal_current: Current internal state.
        external_prior: Previous external state.
        external_current: Current external state.
        continuity_reference: Optional 0,0 reference position.
        modality_operators: Invariant modality operators extracted.
    """
    prior: Optional[dict[str, Any]] = None
    current: Optional[dict[str, Any]] = None
    internal_prior: Optional[dict[str, Any]] = None
    internal_current: Optional[dict[str, Any]] = None
    external_prior: Optional[dict[str, Any]] = None
    external_current: Optional[dict[str, Any]] = None
    continuity_reference: Optional[str] = None
    modality_operators: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.current is None and self.prior is None:
            raise ValueError("At least one of current or prior must be set")

    def to_dict(self) -> dict[str, Any]:
        return {
            "prior": self.prior,
            "current": self.current,
            "internal_prior": self.internal_prior,
            "internal_current": self.internal_current,
            "external_prior": self.external_prior,
            "external_current": self.external_current,
            "continuity_reference": self.continuity_reference,
            "modality_operators": self.modality_operators,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NychState:
        return cls(
            prior=data.get("prior"),
            current=data.get("current"),
            internal_prior=data.get("internal_prior"),
            internal_current=data.get("internal_current"),
            external_prior=data.get("external_prior"),
            external_current=data.get("external_current"),
            continuity_reference=data.get("continuity_reference"),
            modality_operators=data.get("modality_operators", []),
        )

    def advance(self, new_current: dict[str, Any]) -> NychState:
        """
        Advance state chronology: previous current becomes prior,
        new observation becomes current. Internal/external channels
        advance independently.
        """
        return NychState(
            prior=self.current,
            current=new_current,
            internal_prior=self.internal_current,
            internal_current=self.internal_current,
            external_prior=self.external_current,
            external_current=self.external_current,
            continuity_reference=self.continuity_reference,
            modality_operators=self.modality_operators,
        )


@dataclass(frozen=True)
class CandidateTransform:
    """
    A candidate transform with admissibility evidence.
    
    Fields:
        transform_id: Unique identifier for this transform.
        input_state: Input state reference.
        output_state: Expected output state.
        technique: Technique used.
        tote: TOTE loop configuration.
        admissibility_evidence: Evidence supporting admissibility.
        score: Ranking score (from probabilistic model, if used).
        admissible: Whether the candidate passed constraint masking.
    """
    transform_id: str
    input_state: dict[str, Any]
    output_state: dict[str, Any]
    technique: str
    tote: dict[str, Any]
    admissibility_evidence: list[str] = field(default_factory=list)
    score: float = 0.0
    admissible: bool = True

    def __post_init__(self) -> None:
        if not self.transform_id:
            raise ValueError("transform_id must be non-empty")
        if not self.technique:
            raise ValueError("technique must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform_id": self.transform_id,
            "input_state": self.input_state,
            "output_state": self.output_state,
            "technique": self.technique,
            "tote": self.tote,
            "admissibility_evidence": self.admissibility_evidence,
            "score": self.score,
            "admissible": self.admissible,
        }


@dataclass(frozen=True)
class ValidationResult:
    """
    Result of validating a candidate transform or state transition.
    
    Fields:
        valid: Whether the validation passed.
        reasons: List of reasons for the result.
        anomaly_flags: Flags indicating anomalies detected.
        continuity_score: Score indicating continuity preservation.
        closure_state: State of loop/process closure.
        fast_path_used: Whether fast path was used.
    """
    valid: bool
    reasons: list[str] = field(default_factory=list)
    anomaly_flags: list[str] = field(default_factory=list)
    continuity_score: float = 1.0
    closure_state: str = "open"
    fast_path_used: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reasons": self.reasons,
            "anomaly_flags": self.anomaly_flags,
            "continuity_score": self.continuity_score,
            "closure_state": self.closure_state,
            "fast_path_used": self.fast_path_used,
        }


@dataclass(frozen=True)
class AuditUnit:
    """
    Minimal auditable representation of a transform.
    
    Fields:
        unit_id: Unique identifier for this audit unit.
        source_refs: References to source inputs.
        state_refs: References to state objects.
        transform_ref: Reference to the transform applied.
        metrics: Performance/quality metrics.
        hashes: Version identifiers and hashes.
        qson_ref: QSON trace reference.
        g8son_ref: G8SON gate reference.
    """
    unit_id: str
    source_refs: list[str] = field(default_factory=list)
    state_refs: list[str] = field(default_factory=list)
    transform_ref: Optional[str] = None
    metrics: dict[str, Any] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    qson_ref: Optional[str] = None
    g8son_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.unit_id:
            raise ValueError("unit_id must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "source_refs": self.source_refs,
            "state_refs": self.state_refs,
            "transform_ref": self.transform_ref,
            "metrics": self.metrics,
            "hashes": self.hashes,
            "qson_ref": self.qson_ref,
            "g8son_ref": self.g8son_ref,
        }


@dataclass(frozen=True)
class NYCHPipelineResult:
    """
    Complete result of running the NYCH pipeline.
    
    Fields:
        packet: The normalized NYCH packet.
        context: The constructed context.
        state: The resulting state.
        validation: Validation result.
        audit: Audit unit for this pipeline run.
        evidence: Emitted evidence events (QSON-compatible).
        g8son: G8SON gate results.
        mg8: MG8 container assembly.
        mgate_summary: Summary of three-gate MGate execution.
    """
    packet: NychPacket
    context: NychContext
    state: NychState
    validation: ValidationResult
    audit: AuditUnit
    evidence: list[dict[str, Any]] = field(default_factory=list)
    g8son: Optional[dict[str, Any]] = None
    mg8: Optional[dict[str, Any]] = None
    mgate_summary: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet": self.packet.to_dict(),
            "context": self.context.to_dict(),
            "state": self.state.to_dict(),
            "validation": self.validation.to_dict(),
            "audit": self.audit.to_dict(),
            "evidence": self.evidence,
            "g8son": self.g8son,
            "mg8": self.mg8,
            "mgate_summary": self.mgate_summary,
        }

    def to_gst_dict(self) -> dict[str, Any]:
        """
        Convert to .gst (Global State & Tense) format for downstream pipeline.
        
        Per white paper §18, GST is a situated context/state representation
        including interpretation posture, modality, and constraints.
        """
        return {
            "gst_id": self.packet.packet_id,
            "timecode": self.state.current.get("timestamp", "") if self.state.current else "",
            "domain": self.context.domain,
            "subject": self.context.subject,
            "perspective": self.context.perspective.value if self.context.perspective else None,
            "tense": self.context.tense.value if self.context.tense else None,
            "pronouns": [],  # Placeholder - would extract from packet
            "competency_level": self.context.competency,
            "subdomains": self.context.subdomains,
            "specialties": self.context.specialties,
            "functions": [],  # Placeholder - would extract from domain expansion
            "techniques": [],  # Placeholder - would extract from domain expansion
            "legend": {},  # Placeholder - would extract from symbolization
            "legend_confidence": {},  # Placeholder
            "symbols": [
                {
                    "symbol": s,
                    "original": s,
                    "modality": self.context.modality.value,
                    "confidence": 1.0,
                }
                for s in self.packet.symbols
            ],
            "gestalt_id": None,  # Placeholder - would extract from packet
            "admissible_actions": [],  # Placeholder
            "mgate_summary": self.mgate_summary,
        }


@dataclass(frozen=True)
class NaturalLanguageInput:
    """Raw natural language input."""
    text: str
    speaker: str | None = None
    perspective: str | None = None
    tense: str | None = None
    modality: Optional[Modality] = None


@dataclass(frozen=True)
class SensorInput:
    """Raw sensor/telemetry input."""
    data: dict[str, Any]
    source_device: str
    modality: Modality
    timestamp: str | None = None


@dataclass(frozen=True)
class ExistingSymbolicPacket:
    """Pre-existing symbolic packet to re-ingest."""
    packet: dict[str, Any]


# Union type for all accepted inputs
InputType = NaturalLanguageInput | SensorInput | ExistingSymbolicPacket
