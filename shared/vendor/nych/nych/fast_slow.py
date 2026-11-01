"""
NYCH Fast/Slow Path Module
=========================
Fast path operates on operators, semantic anchors, loop markers, domain
markers and compact state identifiers. Fast track omits reliably consistent
modality operators.

Slow path is triggered by domain drift, grammar/operator mismatch,
unexpected symbolic sequence, continuity failure, low confidence, or
loop-integrity failure. Slow track loops back every x amount of processing
to ensure congruence with context (surrounding symbols and their direct
relationships to neighboring symbols).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.exceptions import AnomalyDetectedError
from nych.invariant import ControlOperator
from nych.types import NychContext, NychPacket, NychState


@dataclass(frozen=True)
class PathDecision:
    """Result of fast/slow path decision."""
    use_fast_path: bool
    anomaly_type: str | None = None
    expanded_metadata: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    modality_operators_omitted: list[str] = field(default_factory=list)
    congruence_loops: int = 0


def decide_path(
    packet: NychPacket,
    context: NychContext,
    state: NychState,
    invariants: Any,
    validation: Any,
    confidence: float = 1.0,
) -> PathDecision:
    """
    Decide whether to use fast or slow path.
    
    Fast track: omits reliably consistent modality operators.
    Slow track: loops back every x amount of processing to ensure
    congruence with context (surrounding symbols and their direct
    relationships to neighboring symbols).
    
    Args:
        packet: The current NYCH packet.
        context: The current NYCH context.
        state: The current NYCH state.
        invariants: Extracted invariants.
        validation: Validation result.
        confidence: Confidence score (0.0 to 1.0).
    
    Returns:
        PathDecision indicating which path to use.
    """
    anomalies = _detect_anomalies(packet, context, state, invariants, validation, confidence)
    
    if anomalies:
        anomaly_type, reason = anomalies[0]
        # Slow track: loop back for congruence verification
        congruence_loops = _compute_congruence_loops(packet, state, invariants)
        return PathDecision(
            use_fast_path=False,
            anomaly_type=anomaly_type,
            expanded_metadata=_expand_metadata(packet, state, invariants),
            reason=reason,
            congruence_loops=congruence_loops,
        )
    
    # Fast track: omit reliably consistent modality operators
    modality_operators_omitted = _get_consistent_modality_operators(state, invariants)
    
    return PathDecision(
        use_fast_path=True,
        reason="no_anomalies_detected",
        modality_operators_omitted=modality_operators_omitted,
    )


def _detect_anomalies(
    packet: NychPacket,
    context: NychContext,
    state: NychState,
    invariants: Any,
    validation: Any,
    confidence: float,
) -> list[tuple[str, str]]:
    """Detect anomalies that would trigger the slow path."""
    anomalies = []
    
    # Domain drift: check if domain changed unexpectedly
    prior_domain = (state.prior or {}).get("domain")
    current_domain = (state.current or {}).get("domain")
    if prior_domain and current_domain and prior_domain != current_domain:
        anomalies.append(("domain_drift", f"domain_changed: {prior_domain} -> {current_domain}"))
    
    # Grammar/operator mismatch
    control_ops = getattr(invariants, "control_operators", [])
    if ControlOperator.LOOP_START in control_ops and ControlOperator.LOOP_EXIT not in control_ops:
        anomalies.append(("grammar_mismatch", "loop_start_without_exit"))
    
    # Unexpected symbolic sequence
    symbols = getattr(packet, "symbols", [])
    if len(symbols) > 10:  # Arbitrary threshold
        anomalies.append(("unexpected_symbolic_sequence", f"too_many_symbols: {len(symbols)}"))
    
    # Continuity failure
    if hasattr(validation, "valid") and not validation.valid:
        anomalies.append(("continuity_failure", "validation_failed"))
    
    # Low confidence
    if confidence < 0.5:
        anomalies.append(("low_confidence", f"confidence: {confidence}"))
    
    # Loop integrity failure
    if hasattr(validation, "anomaly_flags") and "loop_integrity_failure" in validation.anomaly_flags:
        anomalies.append(("loop_integrity_failure", "tote_loop_failed"))
    
    return anomalies


def _get_consistent_modality_operators(state: NychState, invariants: Any) -> list[str]:
    """
    Get modality operators that are reliably consistent and can be omitted
    in fast path processing.
    
    Fast track omits reliably consistent modality operators.
    """
    current_ops = getattr(invariants, "modality_operators", [])
    state_ops = getattr(state, "modality_operators", [])
    
    # Operators that appear in both current and prior state are consistent
    consistent = list(set(current_ops) & set(state_ops)) if state_ops else []
    
    return consistent


def _compute_congruence_loops(packet: NychPacket, state: NychState, invariants: Any) -> int:
    """
    Compute how many congruence loops the slow path needs.
    
    Slow track loops back every x amount of processing to ensure
    congruence with context (surrounding symbols and their direct
    relationships to neighboring symbols).
    """
    symbols = getattr(packet, "symbols", [])
    # Loop back every 5 symbols for congruence verification
    return max(1, len(symbols) // 5)


def _expand_metadata(
    packet: NychPacket,
    state: NychState,
    invariants: Any,
) -> dict[str, Any]:
    """
    Expand lexical/semantic metadata for slow path processing.
    
    Returns expanded metadata dictionary.
    """
    expanded = {
        "packet_version": packet.version,
        "source_type": packet.source_type.value,
        "symbols": packet.symbols,
        "operators": getattr(invariants, "cognitive_operators", []) + getattr(invariants, "control_operators", []),
        "domain_markers": getattr(invariants, "domain_markers", []),
        "state_current": state.current,
        "state_prior": state.prior,
        "modality_operators": getattr(invariants, "modality_operators", []),
        "subdomains": getattr(invariants, "subdomains", []),
    }
    return expanded
