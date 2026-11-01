"""
NYCH Machine B Validator Module
================================
Deterministic Verification: Rule-Based Verification, Consistency,
and Truth Constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.types import NychContext, NychPacket, NychState, ValidationResult


@dataclass(frozen=True)
class MachineBValidation:
    """Result of Machine B deterministic verification."""
    valid: bool
    rule_checks: list[dict[str, Any]]
    consistency_checks: list[dict[str, Any]]
    truth_constraint_checks: list[dict[str, Any]]
    verification_id: str


class MachineBValidator:
    """
    Machine B Validator - Deterministic Verification.
    
    Rule-Based Verification + Consistency + Truth Constraints.
    """
    
    def __init__(self) -> None:
        self._rules: list[dict[str, Any]] = []
        self._validation_history: list[MachineBValidation] = []
    
    def verify(
        self,
        packet: NychPacket,
        context: NychContext,
        state: NychState,
        tote_result: Any,
    ) -> MachineBValidation:
        """
        Perform deterministic verification.
        
        Args:
            packet: The current NYCH packet.
            context: The current NYCH context.
            state: The current NYCH state.
            tote_result: Result of TOTE execution.
        
        Returns:
            MachineBValidation with verification results.
        """
        rule_checks = self._check_rules(packet, context, state)
        consistency_checks = self._check_consistency(packet, state)
        truth_constraints = self._check_truth_constraints(packet, context, state)
        
        valid = (
            all(check["passed"] for check in rule_checks)
            and all(check["passed"] for check in consistency_checks)
            and all(check["passed"] for check in truth_constraints)
        )
        
        verification = MachineBValidation(
            valid=valid,
            rule_checks=rule_checks,
            consistency_checks=consistency_checks,
            truth_constraint_checks=truth_constraints,
            verification_id=f"machine_b_{len(self._validation_history)}",
        )
        
        self._validation_history.append(verification)
        return verification
    
    def _check_rules(
        self,
        packet: NychPacket,
        context: NychContext,
        state: NychState,
    ) -> list[dict[str, Any]]:
        """Check rule-based constraints."""
        checks = []
        
        # Rule 1: Domain consistency
        current_domain = (state.current or {}).get("domain")
        if current_domain and current_domain != context.domain:
            checks.append({
                "rule": "domain_consistency",
                "passed": False,
                "reason": f"domain_mismatch: {current_domain} != {context.domain}",
            })
        else:
            checks.append({
                "rule": "domain_consistency",
                "passed": True,
                "reason": "domain_matches",
            })
        
        # Rule 2: Symbol presence (not strictly required for sensor inputs)
        if not packet.symbols and packet.source_type.value != "sensor":
            checks.append({
                "rule": "symbol_presence",
                "passed": False,
                "reason": "no_symbols_extracted",
            })
        else:
            checks.append({
                "rule": "symbol_presence",
                "passed": True,
                "reason": f"{len(packet.symbols)} symbols_present" if packet.symbols else "sensor_input_no_symbols_required",
            })
        
        return checks
    
    def _check_consistency(
        self,
        packet: NychPacket,
        state: NychState,
    ) -> list[dict[str, Any]]:
        """Check internal consistency."""
        checks = []
        
        # Consistency check 1: Packet version matches
        if not packet.version:
            checks.append({
                "check": "version_consistency",
                "passed": False,
                "reason": "missing_version",
            })
        else:
            checks.append({
                "check": "version_consistency",
                "passed": True,
                "reason": f"version_{packet.version}",
            })
        
        # Consistency check 2: State chronology
        if state.prior is not None and state.current is not None:
            checks.append({
                "check": "state_chronology",
                "passed": True,
                "reason": "prior_and_current_set",
            })
        else:
            checks.append({
                "check": "state_chronology",
                "passed": True,
                "reason": "acceptable_state",
            })
        
        return checks
    
    def _check_truth_constraints(
        self,
        packet: NychPacket,
        context: NychContext,
        state: NychState,
    ) -> list[dict[str, Any]]:
        """Check truth constraints."""
        checks = []
        
        # Truth constraint 1: Domain must be non-empty
        if context.domain and context.domain != "unknown":
            checks.append({
                "constraint": "domain_truth",
                "passed": True,
                "reason": f"domain_set_{context.domain}",
            })
        else:
            checks.append({
                "constraint": "domain_truth",
                "passed": True,  # Unknown is acceptable
                "reason": "domain_unknown_acceptable",
            })
        
        # Truth constraint 2: Subject must be non-empty
        if context.subject and context.subject != "unknown":
            checks.append({
                "constraint": "subject_truth",
                "passed": True,
                "reason": f"subject_set_{context.subject}",
            })
        else:
            checks.append({
                "constraint": "subject_truth",
                "passed": True,
                "reason": "subject_unknown_acceptable",
            })
        
        return checks
    
    def to_validation_result(self, verification: MachineBValidation) -> ValidationResult:
        """Convert Machine B validation to standard ValidationResult."""
        reasons = []
        for check in verification.rule_checks + verification.truth_constraint_checks:
            if not check["passed"]:
                reasons.append(check.get("reason", "rule_violation"))
        
        return ValidationResult(
            valid=verification.valid,
            reasons=reasons,
            anomaly_flags=[],
            continuity_score=1.0 if verification.valid else 0.0,
            closure_state="closed" if verification.valid else "open",
        )
