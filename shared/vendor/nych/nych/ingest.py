"""
NYCH Ingestion Module
=====================
Accepts NaturalLanguageInput | SensorInput | ExistingSymbolicPacket
and normalizes both into a shared NYCH packet/state model.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from nych.exceptions import IngestionError
from nych.types import (
    InputType,
    Modality,
    NaturalLanguageInput,
    NychContext,
    NychPacket,
    NychState,
    Perspective,
    SensorInput,
    SourceType,
    Tense,
)


def ingest(input_data: InputType, packet_version: str = "1.0.0") -> tuple[NychPacket, NychContext, NychState]:
    """
    Ingest input data and produce initial NychPacket, NychContext, and NychState.
    
    This is the entry point for the NYCH pipeline. It accepts any of the
    three input types and normalizes them into the canonical internal model.
    
    Args:
        input_data: The input to ingest.
        packet_version: Version of the symbol table/model to use.
    
    Returns:
        Tuple of (NychPacket, NychContext, NychState).
    
    Raises:
        IngestionError: If the input cannot be ingested.
    """
    if isinstance(input_data, NaturalLanguageInput):
        return _ingest_natural_language(input_data, packet_version)
    elif isinstance(input_data, SensorInput):
        return _ingest_sensor(input_data, packet_version)
    elif isinstance(input_data, ExistingSymbolicPacket):
        return _ingest_symbolic_packet(input_data, packet_version)
    else:
        raise IngestionError(f"Unsupported input type: {type(input_data)}")


def _ingest_natural_language(
    input_data: NaturalLanguageInput,
    packet_version: str,
) -> tuple[NychPacket, NychContext, NychState]:
    """Ingest natural language input."""
    packet_id = _generate_packet_id(input_data.text)
    
    # Initial packet with raw text preserved in metadata
    packet = NychPacket(
        packet_id=packet_id,
        version=packet_version,
        source_type=SourceType.NATURAL_LANGUAGE,
        metadata_refs={
            "raw_text": input_data.text,
            "speaker": input_data.speaker,
        },
    )
    
    # Initial context
    context = NychContext(
        domain="unknown",
        subject="unknown",
        intent="unknown",
        competency="unknown",
        modality=Modality.LANGUAGE,
        perspective=_parse_perspective(input_data.perspective),
        tense=_parse_tense(input_data.tense),
    )
    
    # Initial state
    state = NychState(
        current={"raw_text": input_data.text},
        continuity_reference="0,0",
    )
    
    return packet, context, state


def _ingest_sensor(
    input_data: SensorInput,
    packet_version: str,
) -> tuple[NychPacket, NychContext, NychState]:
    """Ingest sensor input."""
    packet_id = _generate_packet_id(str(input_data.data))
    
    packet = NychPacket(
        packet_id=packet_id,
        version=packet_version,
        source_type=SourceType.SENSOR,
        metadata_refs={
            "source_device": input_data.source_device,
            "timestamp": input_data.timestamp,
            "raw_data": input_data.data,
        },
    )
    
    context = NychContext(
        domain="sensor",
        subject=input_data.source_device,
        intent="perception",
        competency="sensor_processing",
        modality=input_data.modality,
    )
    
    state = NychState(
        current={"sensor_data": input_data.data},
        continuity_reference="0,0",
    )
    
    return packet, context, state


def _ingest_symbolic_packet(
    input_data: ExistingSymbolicPacket,
    packet_version: str,
) -> tuple[NychPacket, NychContext, NychState]:
    """Re-ingest an existing symbolic packet."""
    raw = input_data.packet
    packet_id = raw.get("packet_id", _generate_packet_id(str(raw)))
    
    source_type = SourceType(raw.get("source_type", "symbolic_packet"))
    
    packet = NychPacket(
        packet_id=packet_id,
        version=packet_version,
        source_type=source_type,
        symbols=raw.get("symbols", []),
        operators=raw.get("operators", []),
        numeric_values=raw.get("numeric_values", []),
        metadata_refs=raw.get("metadata_refs", {}),
    )
    
    context = NychContext(
        domain=raw.get("domain", "unknown"),
        subject=raw.get("subject", "unknown"),
        intent=raw.get("intent", "unknown"),
        competency=raw.get("competency", "unknown"),
    )
    
    state = NychState(
        current=raw.get("state", {}),
        continuity_reference=raw.get("continuity_reference", "0,0"),
    )
    
    return packet, context, state


def _generate_packet_id(content: str) -> str:
    """Generate a deterministic packet ID from content hash."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _parse_perspective(perspective: str | None) -> Perspective | None:
    """Parse perspective string to enum."""
    if perspective is None:
        return None
    mapping = {
        "first": Perspective.FIRST,
        "second": Perspective.SECOND,
        "third": Perspective.THIRD,
        "1st": Perspective.FIRST,
        "2nd": Perspective.SECOND,
        "3rd": Perspective.THIRD,
    }
    return mapping.get(perspective.lower())


def _parse_tense(tense: str | None) -> Tense | None:
    """Parse tense string to enum."""
    if tense is None:
        return None
    mapping = {
        "past": Tense.PAST,
        "present": Tense.PRESENT,
        "future": Tense.FUTURE,
    }
    return mapping.get(tense.lower())
