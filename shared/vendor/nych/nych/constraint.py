"""
NYCH Constraint / Inverse Transform Module
=========================================
Reject candidates outside domain, capability, competency, physical/state
constraints, policy, or declared admissibility rules.

Inverse transform is a prune of all domains outside the relevant domain(s)
with special attention heads on the admissible transforms that cross this
boundary yet end with state representations that are a match to the target
state rep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.exceptions import ConstraintViolationError
from nych.types import CandidateTransform, NychContext, NychPacket, NychState


@dataclass(frozen=True)
class ConstraintMask:
    """Result of constraint masking."""
    admissible_candidates: list[CandidateTransform] = field(default_factory=list)
    rejected_candidates: list[CandidateTransform] = field(default_factory=list)
    rejection_reasons: dict[str, list[str]] = field(default_factory=dict)
    admissible_count: int = 0
    rejected_count: int = 0


def apply_constraints(
    candidates: list[CandidateTransform],
    context: NychContext,
    packet: NychPacket,
    state: NychState,
) -> ConstraintMask:
    """
    Apply inverse transform / constraint mask to filter candidates.
    
    Prune all domains outside the relevant domain(s) with special attention
    heads on the admissible transforms that cross this boundary yet end with
    state representations that are a match to the target state rep.
    
    Args:
        candidates: List of candidate transforms to filter.
        context: The current NYCH context.
        packet: The current NYCH packet.
        state: The current NYCH state.
    
    Returns:
        ConstraintMask with admissible and rejected candidates.
    """
    admissible = []
    rejected = []
    reasons = {}
    
    for candidate in candidates:
        rejection_reasons = _check_constraints(candidate, context, packet, state)
        if rejection_reasons:
            rejected.append(candidate)
            reasons[candidate.transform_id] = rejection_reasons
        else:
            admissible.append(candidate)
    
    return ConstraintMask(
        admissible_candidates=admissible,
        rejected_candidates=rejected,
        rejection_reasons=reasons,
        admissible_count=len(admissible),
        rejected_count=len(rejected),
    )


def _check_constraints(
    candidate: CandidateTransform,
    context: NychContext,
    packet: NychPacket,
    state: NychState,
) -> list[str]:
    """
    Check a candidate against all constraints.
    
    Returns a list of rejection reasons (empty if admissible).
    """
    reasons = []
    
    # Domain constraint - inverse transform prune
    candidate_domain = candidate.output_state.get("domain", "")
    if candidate_domain and candidate_domain != context.domain:
        reasons.append(f"domain_mismatch: expected {context.domain}, got {candidate_domain}")
    
    # Subdomain boundary check - admissible transforms crossing domain boundary
    candidate_subdomains = candidate.output_state.get("subdomains", [])
    if candidate_subdomains:
        # Check if any cross-domain transforms end with state matching target
        target_state = candidate.output_state.get("target_state", {})
        if not _check_boundary_cross_match(candidate, context, target_state):
            reasons.append("boundary_cross_no_match")
    
    # Competency constraint
    candidate_competency = candidate.output_state.get("competency", "")
    if candidate_competency and candidate_competency != context.competency:
        reasons.append(f"competency_mismatch: expected {context.competency}, got {candidate_competency}")
    
    # Physical/state constraints
    if not _check_state_feasibility(candidate, state):
        reasons.append("state_infeasible")
    
    # Policy constraints (placeholder)
    if not _check_policy_compliance(candidate, context):
        reasons.append("policy_violation")
    
    # Admissibility rules
    if not candidate.admissibility_evidence:
        reasons.append("missing_admissibility_evidence")
    
    return reasons


def _check_boundary_cross_match(
    candidate: CandidateTransform,
    context: NychContext,
    target_state: dict[str, Any],
) -> bool:
    """
    Check if admissible transforms crossing domain boundary end with
    state representations matching target state.
    """
    if not target_state:
        return True
    
    # Check if output state keys match target state keys
    candidate_output = candidate.output_state
    for key in target_state:
        if key in candidate_output and candidate_output[key] == target_state[key]:
            return True
    
    return False


def _check_state_feasibility(candidate: CandidateTransform, state: NychState) -> bool:
    """
    Check if the candidate's output state is feasible given current state.
    """
    required_tools = candidate.output_state.get("required_tools", [])
    available_tools = state.current.get("available_tools", []) if state.current else []
    
    for tool in required_tools:
        if tool not in available_tools:
            return False
    
    return True


def _check_policy_compliance(candidate: CandidateTransform, context: NychContext) -> bool:
    """
    Check if the candidate complies with declared policies.
    """
    constraints = context.constraints
    for constraint in constraints:
        if constraint == "no_destructive_actions":
            if candidate.output_state.get("destructive", False):
                return False
    return True
