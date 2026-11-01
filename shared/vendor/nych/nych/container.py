"""
NYCH MG8 Container Assembly Module
====================================
Assembles the legacy NYCH MG8 container profile, not a canonical MG8 manifest.
Embedded G8SON-shaped records are local evaluator results, not dedicated
G8SON gate-condition files. Public names and serialized shapes are retained.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from nych.schemas.g8son import validate_g8son, to_canonical_g8son
from nych.schemas.mg8 import PROFILE_ID, validate_mg8, to_canonical_mg8
from nych.types import NychContext, NychPacket, NychState, ValidationResult


@dataclass(frozen=True)
class MG8Container:
    """Legacy NYCH MG8 container; not a dedicated MG8 resource manifest."""
    orchestration: dict[str, Any]
    state_refs: dict[str, Any]
    gates: list[dict[str, Any]]
    evidence_refs: list[dict[str, Any]]
    g8son: dict[str, Any]
    container_id: str
    valid: bool = True


@dataclass(frozen=True)
class G8SONGate:
    """Legacy NYCH evaluator result; not a G8SON condition declaration."""
    gate_id: str
    gate_type: str
    transform_id: str
    passed: bool
    reason: str
    metadata: dict[str, Any]


class MG8ContainerAssembly:
    """
    MG8 Container Assembly.
    
    Project / Domain Context + Gate Selection + Resource Bindings.
    """
    
    def __init__(self) -> None:
        self._containers: list[MG8Container] = []
    
    def assemble(
        self,
        packet: NychPacket,
        context: NychContext,
        state: NychState,
        validation: ValidationResult,
        gate_results: list[G8SONGate],
        evidence_refs: list[dict[str, Any]],
    ) -> MG8Container:
        """
        Assemble MG8 container.
        
        Args:
            packet: The current NYCH packet.
            context: The current NYCH context.
            state: The current NYCH state.
            validation: The validation result.
            gate_results: List of G8SON gate results.
            evidence_refs: List of evidence references.
        
        Returns:
            MG8Container with assembled container.
        """
        # Build orchestration section
        orchestration = {
            "pipeline_id": packet.packet_id,
            "run_id": f"run_{hashlib.sha256(packet.packet_id.encode()).hexdigest()[:8]}",
            "timestamp": "2026-08-23T15:49:19.666Z",
            "config": {
                "version": packet.version,
                "source_type": packet.source_type.value,
            },
        }
        
        # Build state references
        state_refs = {
            "gst_ref": f"gst_{packet.packet_id}",
            "nych_ref": f"nych_{packet.packet_id}",
            "state_hash": hashlib.sha256(
                json.dumps(state.to_dict(), sort_keys=True).encode()
            ).hexdigest()[:16],
        }
        
        # Build gates section (G8SON)
        gates = []
        for gate in gate_results:
            gates.append({
                "gate_id": gate.gate_id,
                "g8son_ref": gate.gate_id,
                "gate_type": gate.gate_type,
                "transform_id": gate.transform_id,
                "passed": gate.passed,
                "reason": gate.reason,
                "metadata": gate.metadata,
            })
        
        # Build evidence section
        evidence = []
        for ev in evidence_refs:
            evidence.append({
                "qson_ref": ev.get("event_id", "unknown"),
                "event_type": ev.get("event_type", "unknown"),
            })
        
        g8son = {
            "gates": gates,
            "container_id": f"g8son_{packet.packet_id}",
            "valid": validation.valid,
        }
        
        mg8 = {
            "orchestration": orchestration,
            "state": state_refs,
            "gates": gates,
            "evidence": evidence,
            "container_id": f"mg8_{packet.packet_id}",
            "valid": validation.valid,
        }
        
        # Validate G8SON and MG8
        g8son_valid = validate_g8son(g8son)
        mg8_valid = validate_mg8(mg8)
        
        container = MG8Container(
            orchestration=orchestration,
            state_refs=state_refs,
            gates=gates,
            evidence_refs=evidence,
            g8son=g8son,
            container_id=f"mg8_{packet.packet_id}",
            valid=g8son_valid and mg8_valid,
        )
        
        self._containers.append(container)
        return container
    
    def create_g8son_gates(
        self,
        constraint_mask: Any,
    ) -> list[G8SONGate]:
        """Create G8SON gates from constraint mask results."""
        gates = []
        
        # Gate for each admissible candidate
        for candidate in constraint_mask.admissible_candidates:
            gate = G8SONGate(
                gate_id=f"gate_{candidate.transform_id}",
                gate_type="admissibility",
                transform_id=candidate.transform_id,
                passed=True,
                reason="admissible",
                metadata={"score": candidate.score},
            )
            gates.append(gate)
        
        # Gate for each rejected candidate
        for candidate in constraint_mask.rejected_candidates:
            reasons = constraint_mask.rejection_reasons.get(candidate.transform_id, ["unknown"])
            gate = G8SONGate(
                gate_id=f"gate_{candidate.transform_id}",
                gate_type="admissibility",
                transform_id=candidate.transform_id,
                passed=False,
                reason="|".join(reasons),
                metadata={"rejection_reasons": reasons},
            )
            gates.append(gate)
        
        return gates
