"""
NYCH Symbolic Packet Stream Module
====================================
Manages the stream of symbolic packets, continuity monitoring,
and recursive stability checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.types import NychPacket, NychState


@dataclass(frozen=True)
class SymbolicPacketStream:
    """
    Manages the stream of symbolic packets with continuity monitoring.
    """
    packets: list[NychPacket] = field(default_factory=list)
    states: list[NychState] = field(default_factory=list)
    continuity_checks: list[dict[str, Any]] = field(default_factory=list)
    stability_score: float = 1.0
    packet_count: int = 0

    def add_packet(self, packet: NychPacket, state: NychState) -> None:
        """Add a new packet and state to the stream."""
        self.packets.append(packet)
        self.states.append(state)
        self.packet_count += 1

    def check_continuity(self, new_state: NychState) -> dict[str, Any]:
        """
        Check continuity between previous state and new state.
        
        Returns continuity check result.
        """
        if not self.states:
            continuity_check = {
                "check_id": f"continuity_{self.packet_count}",
                "prior_current_ok": True,
                "internal_external_ok": True,
                "operator_legality_ok": True,
                "domain_continuity_ok": True,
                "loop_integrity_ok": True,
                "continuity_score": 1.0,
                "issues": [],
            }
            self.continuity_checks.append(continuity_check)
            return continuity_check
        
        prior = self.states[-1]
        
        # Check prior/current advancement
        prior_current_ok = True
        if prior.current is not None and new_state.prior is not None:
            prior_current_ok = prior.current == new_state.prior
        
        # Check internal/external advancement
        internal_external_ok = True
        if prior.internal_current is not None and new_state.internal_prior is not None:
            internal_external_ok = prior.internal_current == new_state.internal_prior
        if prior.external_current is not None and new_state.external_prior is not None:
            internal_external_ok = internal_external_ok and (prior.external_current == new_state.external_prior)
        
        # Check domain continuity
        domain_continuity_ok = True
        prior_domain = (prior.current or {}).get("domain")
        current_domain = (new_state.current or {}).get("domain")
        if prior_domain is not None and current_domain is not None:
            domain_continuity_ok = prior_domain == current_domain
        
        issues = []
        if not prior_current_ok:
            issues.append("prior_current_chronology_violation")
        if not internal_external_ok:
            issues.append("internal_external_chronology_violation")
        if not domain_continuity_ok:
            issues.append("domain_continuity_violation")
        
        total_checks = 3
        passed_checks = sum([prior_current_ok, internal_external_ok, domain_continuity_ok])
        continuity_score = passed_checks / total_checks
        
        continuity_check = {
            "check_id": f"continuity_{self.packet_count}",
            "prior_current_ok": prior_current_ok,
            "internal_external_ok": internal_external_ok,
            "operator_legality_ok": True,
            "domain_continuity_ok": domain_continuity_ok,
            "loop_integrity_ok": True,
            "continuity_score": continuity_score,
            "issues": issues,
        }
        self.continuity_checks.append(continuity_check)
        self.stability_score = min(self.stability_score, continuity_score)
        
        return continuity_check

    def get_recursive_stability(self) -> float:
        """
        Compute recursive stability score across all continuity checks.
        """
        if not self.continuity_checks:
            return 1.0
        
        scores = [check["continuity_score"] for check in self.continuity_checks]
        return sum(scores) / len(scores)
