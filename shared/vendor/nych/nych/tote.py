"""
NYCH TOTE Execution Module
==========================
Test -> Operate -> Test -> Exit with bounded steps and fail-closed behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nych.exceptions import TOTEError
from nych.types import CandidateTransform, NychContext, NychPacket, NychState


@dataclass(frozen=True)
class TOTEResult:
    """Result of TOTE execution."""
    success: bool
    exit_reason: str
    iterations: int
    final_state: dict[str, Any] = field(default_factory=dict)
    test_results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def execute_tote(
    candidate: CandidateTransform,
    context: NychContext,
    packet: NychPacket,
    state: NychState,
    max_iterations: int = 10,
) -> TOTEResult:
    """
    Execute a TOTE (Test-Operate-Test-Exit) loop.
    
    Args:
        candidate: The selected candidate transform.
        context: The current NYCH context.
        packet: The current NYCH packet.
        state: The current NYCH state.
        max_iterations: Maximum number of iterations before forced exit.
    
    Returns:
        TOTEResult with execution outcome.
    
    Raises:
        TOTEError: If TOTE execution fails catastrophically.
    """
    tote_config = candidate.tote
    current_state = state.current or {}
    test_results = []
    
    for iteration in range(max_iterations):
        # TEST phase
        test_passed, test_result = _test_phase(
            current_state, tote_config, context, iteration
        )
        test_results.append({
            "iteration": iteration,
            "phase": "test",
            "passed": test_passed,
            "result": test_result,
        })
        
        if not test_passed:
            # Exit condition met
            return TOTEResult(
                success=True,
                exit_reason="test_failed_exit",
                iterations=iteration + 1,
                final_state=current_state,
                test_results=test_results,
            )
        
        # OPERATE phase
        try:
            current_state = _operate_phase(
                current_state, tote_config, context, candidate
            )
        except Exception as e:
            return TOTEResult(
                success=False,
                exit_reason="operate_failed",
                iterations=iteration + 1,
                final_state=current_state,
                test_results=test_results,
                error=str(e),
            )
        
        test_results.append({
            "iteration": iteration,
            "phase": "operate",
            "result": "completed",
        })
    
    # Max iterations reached - fail closed
    return TOTEResult(
        success=False,
        exit_reason="max_iterations_exceeded",
        iterations=max_iterations,
        final_state=current_state,
        test_results=test_results,
        error=f"TOTE exceeded maximum iterations ({max_iterations})",
    )


def _test_phase(
    current_state: dict[str, Any],
    tote_config: dict[str, Any],
    context: NychContext,
    iteration: int,
) -> tuple[bool, str]:
    """
    Test phase: check if exit condition is met.
    
    Returns:
        Tuple of (test_passed, test_result).
        test_passed=False means exit condition is met.
    """
    exit_condition = tote_config.get("exit_condition", f"exit_{iteration}")
    
    # Placeholder: in production, this would evaluate the actual exit condition
    # against the current state. For now, we use a simple heuristic.
    
    # Simulate: exit after 2 iterations for demonstration
    if iteration >= 2:
        return False, f"exit_condition_met: {exit_condition}"
    
    return True, f"test_passed: {tote_config.get('test_condition', 'test')}"


def _operate_phase(
    current_state: dict[str, Any],
    tote_config: dict[str, Any],
    context: NychContext,
    candidate: CandidateTransform,
) -> dict[str, Any]:
    """
    Operate phase: apply the transform to the state.
    
    Returns:
        Updated state after operation.
    """
    operate_action = tote_config.get("operate_action", "operate")
    
    # Placeholder: in production, this would execute the actual operation
    # For now, we simulate state advancement
    new_state = dict(current_state)
    new_state["last_operation"] = operate_action
    new_state["iteration"] = new_state.get("iteration", 0) + 1
    new_state["tote_id"] = tote_config.get("tote_id", "unknown")
    
    # Apply candidate's output state as transformation
    for key, value in candidate.output_state.items():
        if key != "domain":  # Don't overwrite domain in state
            new_state[key] = value
    
    return new_state
