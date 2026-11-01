"""
NYCH Evidence Emission Module
==============================
Emit legacy NYCH audit events and update local state; not canonical QSON.
The historical event shape is retained without a silent format migration.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from nych.schemas.qson import PROFILE_ID
from nych.types import (
    AuditUnit,
    NychContext,
    NychPacket,
    NychState,
    NYCHPipelineResult,
    ValidationResult,
)


@dataclass(frozen=True)
class EvidenceEvent:
    """A single legacy NYCH audit event (see PROFILE_ID)."""
    event_id: str
    event_type: str
    actor: str
    sequence: int
    timestamp: str
    payload: dict[str, Any]
    validation: dict[str, Any]
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "validation": self.validation,
            "hash": self.hash,
        }


def emit_evidence(
    result: NYCHPipelineResult,
    sequence: int = 0,
) -> list[EvidenceEvent]:
    """
    Emit legacy NYCH audit events, not dedicated canonical QSON records.
    
    Args:
        result: The complete pipeline result.
        sequence: Sequence number for this event.
    
    Returns:
        List of EvidenceEvent objects.
    """
    events = []
    
    # Ingest event
    ingest_event = _create_event(
        event_type="ingest",
        actor="nych_pipeline",
        sequence=sequence,
        payload={
            "packet": result.packet.to_dict(),
            "context": result.context.to_dict(),
        },
        validation={"valid": True},
    )
    events.append(ingest_event)
    
    # Transform event
    transform_event = _create_event(
        event_type="transform",
        actor="nych_pipeline",
        sequence=sequence + 1,
        payload={
            "state_before": result.state.prior,
            "state_after": result.state.current,
        },
        validation=result.validation.to_dict(),
    )
    events.append(transform_event)
    
    # Validation event
    validation_event = _create_event(
        event_type="validation",
        actor="nych_validator",
        sequence=sequence + 2,
        payload={
            "validation_result": result.validation.to_dict(),
        },
        validation={"valid": result.validation.valid},
    )
    events.append(validation_event)
    
    # Audit event
    audit_event = _create_event(
        event_type="audit",
        actor="nych_auditor",
        sequence=sequence + 3,
        payload={
            "audit_unit": result.audit.to_dict(),
        },
        validation={"valid": True},
    )
    events.append(audit_event)
    
    return events


def _create_event(
    event_type: str,
    actor: str,
    sequence: int,
    payload: dict[str, Any],
    validation: dict[str, Any],
) -> EvidenceEvent:
    """Create a single evidence event with deterministic hash."""
    event_id = hashlib.sha256(
        f"{event_type}:{actor}:{sequence}:{json.dumps(payload, sort_keys=True)}".encode()
    ).hexdigest()[:16]
    
    event_hash = hashlib.sha256(
        json.dumps({
            "event_id": event_id,
            "event_type": event_type,
            "actor": actor,
            "sequence": sequence,
            "payload": payload,
            "validation": validation,
        }, sort_keys=True).encode()
    ).hexdigest()
    
    return EvidenceEvent(
        event_id=event_id,
        event_type=event_type,
        actor=actor,
        sequence=sequence,
        timestamp="2026-08-23T15:49:19.666Z",  # Placeholder: use actual timestamp
        payload=payload,
        validation=validation,
        hash=event_hash,
    )


def update_gst_state(
    current_state: NychState,
    new_data: dict[str, Any],
) -> NychState:
    """
    Update GST-compatible state with new data.
    
    Advances state chronology: previous current becomes prior,
    new observation becomes current.
    
    Args:
        current_state: The current NYCH state.
        new_data: New data to incorporate into state.
    
    Returns:
        Updated NychState with advanced chronology.
    """
    return current_state.advance(new_data)


def create_audit_unit(
    packet: NychPacket,
    context: NychContext,
    state: NychState,
    validation: ValidationResult,
    metrics: dict[str, Any] | None = None,
) -> AuditUnit:
    """
    Create an audit unit for this pipeline run.
    
    Args:
        packet: The NYCH packet.
        context: The NYCH context.
        state: The NYCH state.
        validation: The validation result.
        metrics: Optional performance metrics.
    
    Returns:
        AuditUnit with audit information.
    """
    unit_id = hashlib.sha256(
        f"{packet.packet_id}:{context.domain}:{validation.valid}".encode()
    ).hexdigest()[:16]
    
    return AuditUnit(
        unit_id=unit_id,
        source_refs=[packet.packet_id],
        state_refs=[state.current.get("state_ref", "unknown")] if state.current else [],
        transform_ref=state.current.get("last_transform") if state.current else None,
        metrics=metrics or {},
        hashes={
            "packet_hash": hashlib.sha256(packet.packet_id.encode()).hexdigest()[:16],
            "validation_hash": hashlib.sha256(str(validation.valid).encode()).hexdigest()[:16],
        },
    )
