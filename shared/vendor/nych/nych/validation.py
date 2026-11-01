"""
NYCH Validation Module
======================
Compare prior/current state, internal/external state, operator legality,
domain continuity and loop integrity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.exceptions import ValidationError
from nych.types import NychContext, NychPacket, NychState, ValidationResult


@dataclass(frozen=True)
class ContinuityCheck:
    """Result of continuity validation."""
    prior_current_ok: bool = True
    internal_external_ok: bool = True
    operator_legality_ok: bool = True
    domain_continuity_ok: bool = True
    loop_integrity_ok: bool = True
    continuity_score: float = 1.0
    issues: list[str] = field(default_factory=list)


def validate_continuity(
    prior_state: NychState,
    current_state: NychState,
    context: NychContext,
    packet: NychPacket,
    tote_result: Any,
) -> ContinuityCheck:
    """
    Validate state continuity and transition integrity.
    
    Args:
        prior_state: The previous state.
        current_state: The current state.
        context: The current NYCH context.
        packet: The current NYCH packet.
        tote_result: Result of TOTE execution.
    
    Returns:
        ContinuityCheck with validation results.
    """
    issues = []
    
    # Check prior/current advancement
    prior_current_ok = _check_prior_current(prior_state, current_state)
    if not prior_current_ok:
        issues.append("prior_current_chronology_violation")
    
    # Check internal/external advancement
    internal_external_ok = _check_internal_external(prior_state, current_state)
    if not internal_external_ok:
        issues.append("internal_external_chronology_violation")
    
    # Check operator legality
    operator_legality_ok = _check_operator_legality(packet, context)
    if not operator_legality_ok:
        issues.append("operator_illegality")
    
    # Check domain continuity
    domain_continuity_ok = _check_domain_continuity(prior_state, current_state, context)
    if not domain_continuity_ok:
        issues.append("domain_continuity_violation")
    
    # Check loop integrity
    loop_integrity_ok = _check_loop_integrity(tote_result)
    if not loop_integrity_ok:
        issues.append("loop_integrity_violation")
    
    # Calculate continuity score
    total_checks = 5
    passed_checks = sum([
        prior_current_ok,
        internal_external_ok,
        operator_legality_ok,
        domain_continuity_ok,
        loop_integrity_ok,
    ])
    continuity_score = passed_checks / total_checks
    
    return ContinuityCheck(
        prior_current_ok=prior_current_ok,
        internal_external_ok=internal_external_ok,
        operator_legality_ok=operator_legality_ok,
        domain_continuity_ok=domain_continuity_ok,
        loop_integrity_ok=loop_integrity_ok,
        continuity_score=continuity_score,
        issues=issues,
    )


def _check_prior_current(prior: NychState, current: NychState) -> bool:
    """Check that prior/current state chronology is valid."""
    # Prior's current should match current's prior (if both exist)
    if prior.current is not None and current.prior is not None:
        return prior.current == current.prior
    return True


def _check_internal_external(prior: NychState, current: NychState) -> bool:
    """Check that internal/external state chronology is valid."""
    # Internal and external channels should advance independently
    # but not regress
    if prior.internal_current is not None and current.internal_prior is not None:
        if prior.internal_current != current.internal_prior:
            return False
    if prior.external_current is not None and current.external_prior is not None:
        if prior.external_current != current.external_prior:
            return False
    return True


def _check_operator_legality(packet: NychPacket, context: NychContext) -> bool:
    """Check that operators used are legal for the current context."""
    # Placeholder: in production, this would check against an operator legality matrix
    return True


def _check_domain_continuity(
    prior: NychState,
    current: NychState,
    context: NychContext,
) -> bool:
    """Check that domain continuity is maintained."""
    # Domain should not change without explicit transition
    prior_domain = (prior.current or {}).get("domain")
    current_domain = (current.current or {}).get("domain")
    
    if prior_domain is not None and current_domain is not None:
        return prior_domain == current_domain
    return True


def _check_loop_integrity(tote_result: Any) -> bool:
    """Check that TOTE loop completed with integrity."""
    if hasattr(tote_result, "success"):
        return tote_result.success
    return True


def validate_result(
    continuity: ContinuityCheck,
    context: NychContext,
) -> ValidationResult:
    """
    Produce final validation result from continuity check.
    
    Args:
        continuity: The continuity check result.
        context: The current NYCH context.
    
    Returns:
        ValidationResult with final validation outcome.
    """
    valid = (
        continuity.prior_current_ok
        and continuity.internal_external_ok
        and continuity.operator_legality_ok
        and continuity.domain_continuity_ok
        and continuity.loop_integrity_ok
    )
    
    reasons = []
    if not valid:
        reasons = continuity.issues
    
    anomaly_flags = []
    if continuity.continuity_score < 0.8:
        anomaly_flags.append("low_continuity_score")
    if not continuity.loop_integrity_ok:
        anomaly_flags.append("loop_integrity_failure")
    
    closure_state = "closed" if valid else "open"
    
    return ValidationResult(
        valid=valid,
        reasons=reasons,
        anomaly_flags=anomaly_flags,
        continuity_score=continuity.continuity_score,
        closure_state=closure_state,
    )
