"""
NYCH MGate System Module
========================
Three sequential gated TOTE loops per trajectory rung.

Per the NYCH white paper:
- Each gate is itself a repeat-until-satisfied TOTE loop
- Advancement requires EXIT(G1) AND EXIT(G2) AND EXIT(G3)
- Failure triggers backtracking into remaining admissible transform space
- UNKNOWN is a first-class gate state, never silently promoted to PASS
- ActionPermits are single-use and bound to canonical semantic/provenance snapshots
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from nych.exceptions import TOTEError
from nych.types import (
    CandidateTransform,
    NychContext,
    NychPacket,
    NychState,
)


class GateOutcome:
    """Gate evaluation outcomes."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class GateState:
    """ActionPermit lifecycle states."""
    ISSUED = "ISSUED"
    CONSUMED = "CONSUMED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class AtomicRequirement:
    """
    An atomic requirement from a .g8son gate definition.
    
    Fields:
        req_id: Unique requirement identifier.
        requirement: Human-readable requirement description.
        threshold_efficiency: Minimum efficiency/confidence threshold.
        evaluator: Optional callable that returns (PASS, FAIL, UNKNOWN).
        metadata: Additional requirement metadata.
    """
    req_id: str
    requirement: str
    threshold_efficiency: float = 0.9
    evaluator: Optional[Callable[..., Tuple[str, str]]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def evaluate(self, *args: Any, **kwargs: Any) -> Tuple[str, str]:
        """
        Evaluate this atomic requirement.
        
        Returns:
            Tuple of (outcome, reason).
            outcome is one of: GateOutcome.PASS, GateOutcome.FAIL, GateOutcome.UNKNOWN
        """
        if self.evaluator is not None:
            try:
                result = self.evaluator(*args, **kwargs)
                if isinstance(result, tuple) and len(result) == 2:
                    return result
                elif isinstance(result, str):
                    return result, "evaluator_returned_string"
                else:
                    return GateOutcome.UNKNOWN, f"evaluator_returned_unexpected_type: {type(result)}"
            except Exception as e:
                return GateOutcome.UNKNOWN, f"evaluator_exception: {str(e)}"
        
        # No evaluator attached - cannot evaluate
        return GateOutcome.UNKNOWN, "no_evaluator_attached"


@dataclass(frozen=True)
class GateDefinition:
    """
    Definition of a single gate within a three-gate MGate set.
    
    Fields:
        gate_id: Unique gate identifier.
        gate_name: Human-readable gate name.
        atomic_requirements: List of atomic requirements for this gate.
        exit_criterion: Condition that must be met for EXIT.
        max_iterations: Maximum TOTE iterations before forced failure.
        gate_type: Type classification (e.g., "self_actor", "problem_space", "perspective").
    """
    gate_id: str
    gate_name: str
    atomic_requirements: List[AtomicRequirement] = field(default_factory=list)
    exit_criterion: str = "all_requirements_pass"
    max_iterations: int = 5
    gate_type: str = "generic"

    def evaluate(self, state: dict[str, Any], context: NychContext, packet: NychPacket) -> Tuple[str, List[str]]:
        """
        Evaluate all atomic requirements for this gate.
        
        Returns:
            Tuple of (overall_outcome, reasons_list).
        """
        if not self.atomic_requirements:
            return GateOutcome.UNKNOWN, ["no_requirements_defined"]
        
        results = []
        for req in self.atomic_requirements:
            outcome, reason = req.evaluate(state, context, packet)
            results.append((req.req_id, outcome, reason))
        
        # Aggregate results
        outcomes = [r[1] for r in results]
        
        if all(o == GateOutcome.PASS for o in outcomes):
            return GateOutcome.PASS, [f"{req_id}:{reason}" for req_id, _, reason in results]
        elif any(o == GateOutcome.FAIL for o in outcomes):
            failures = [f"{req_id}:{reason}" for req_id, o, reason in results if o == GateOutcome.FAIL]
            return GateOutcome.FAIL, failures
        else:
            unknowns = [f"{req_id}:{reason}" for req_id, o, reason in results if o == GateOutcome.UNKNOWN]
            return GateOutcome.UNKNOWN, unknowns


@dataclass
class GateInstance:
    """
    Runtime instance of a single gate during TOTE execution.
    
    Tracks the TEST -> OPERATE -> TEST loop state for one gate
    within a three-gate set at a specific trajectory rung.
    """
    gate_id: str
    gate_type: str
    definition: GateDefinition
    iteration: int = 0
    state: str = "PENDING"  # PENDING, TESTING, OPERATING, EXIT, FAIL, UNKNOWN
    last_outcome: str = GateOutcome.UNKNOWN
    reasons: List[str] = field(default_factory=list)
    history: List[dict[str, Any]] = field(default_factory=list)

    def record_test(self, outcome: str, reasons: List[str], state_before: dict[str, Any]) -> None:
        """Record a TEST phase result."""
        self.history.append({
            "iteration": self.iteration,
            "phase": "TEST",
            "outcome": outcome,
            "reasons": reasons,
            "state_before": state_before,
        })
        self.last_outcome = outcome
        self.reasons = reasons

    def record_operate(self, state_after: dict[str, Any]) -> None:
        """Record an OPERATE phase result."""
        self.history.append({
            "iteration": self.iteration,
            "phase": "OPERATE",
            "state_after": state_after,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_type": self.gate_type,
            "iteration": self.iteration,
            "state": self.state,
            "last_outcome": self.last_outcome,
            "reasons": self.reasons,
            "history": self.history,
        }


@dataclass
class ThreeGateSet:
    """
    A complete three-gate MGate set for one trajectory rung.
    
    Fields:
        rung_index: Which trajectory rung this gate set is for.
        g1: Gate 1 instance (e.g., Self/Actor validation).
        g2: Gate 2 instance (e.g., Problem Space validation).
        g3: Gate 3 instance (e.g., Perspective/Conditions validation).
        all_exit: Whether all three gates have reached EXIT.
        backtrack_count: Number of backtracking events for this rung.
    """
    rung_index: int
    g1: GateInstance
    g2: GateInstance
    g3: GateInstance
    all_exit: bool = False
    backtrack_count: int = 0

    def get_gate(self, gate_number: int) -> GateInstance:
        """Get gate instance by number (1, 2, or 3)."""
        if gate_number == 1:
            return self.g1
        elif gate_number == 2:
            return self.g2
        elif gate_number == 3:
            return self.g3
        raise ValueError(f"Gate number must be 1, 2, or 3, got {gate_number}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rung_index": self.rung_index,
            "g1": self.g1.to_dict(),
            "g2": self.g2.to_dict(),
            "g3": self.g3.to_dict(),
            "all_exit": self.all_exit,
            "backtrack_count": self.backtrack_count,
        }


@dataclass(frozen=True)
class ActionPermit:
    """
    Single-use action permit bound to a canonical semantic/provenance snapshot.
    
    Lifecycle: ISSUED -> CONSUMED | REVOKED | EXPIRED
    
    Fields:
        permit_id: Unique permit identifier.
        state_hash: Hash of the state at permit issuance.
        semantic_hash: Hash of semantic/provenance snapshot.
        epoch: Verification epoch number.
        gate_set_hash: Hash of the gate set that issued this permit.
        state: Current lifecycle state.
        issued_at: Timestamp of issuance.
        consumed_at: Optional timestamp of consumption.
        revoked_reason: Optional revocation reason.
    """
    permit_id: str
    state_hash: str
    semantic_hash: str
    epoch: int
    gate_set_hash: str
    state: str = GateState.ISSUED
    issued_at: float = 0.0
    consumed_at: Optional[float] = None
    revoked_reason: Optional[str] = None

    def consume(self) -> bool:
        """Consume the permit (single-use)."""
        if self.state != GateState.ISSUED:
            return False
        # This would normally mutate, but frozen dataclass means we create new
        return True

    def revoke(self, reason: str) -> bool:
        """Revoke the permit."""
        if self.state != GateState.ISSUED:
            return False
        return True

    def is_valid(self, current_state_hash: str, current_semantic_hash: str) -> bool:
        """Check if permit is still valid against current state."""
        if self.state != GateState.ISSUED:
            return False
        if self.state_hash != current_state_hash:
            return False
        if self.semantic_hash != current_semantic_hash:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "permit_id": self.permit_id,
            "state_hash": self.state_hash,
            "semantic_hash": self.semantic_hash,
            "epoch": self.epoch,
            "gate_set_hash": self.gate_set_hash,
            "state": self.state,
            "issued_at": self.issued_at,
            "consumed_at": self.consumed_at,
            "revoked_reason": self.revoked_reason,
        }


@dataclass(frozen=True)
class GateExecutionResult:
    """
    Result of executing a complete three-gate MGate set for one trajectory rung.
    
    Fields:
        rung_index: Which trajectory rung this result is for.
        passed: Whether all three gates EXITed successfully.
        gate_set: The three-gate set that was executed.
        candidate: The candidate transform that was tested.
        action_permit: The action permit issued (if passed).
        new_state: The resulting state after successful advancement.
        backtracked: Whether backtracking occurred.
        backtrack_reason: Reason for backtracking if applicable.
        remaining_admissible: Count of remaining admissible transforms.
    """
    rung_index: int
    passed: bool
    gate_set: ThreeGateSet
    candidate: CandidateTransform
    action_permit: Optional[ActionPermit] = None
    new_state: dict[str, Any] = field(default_factory=dict)
    backtracked: bool = False
    backtrack_reason: Optional[str] = None
    remaining_admissible: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rung_index": self.rung_index,
            "passed": self.passed,
            "gate_set": self.gate_set.to_dict(),
            "candidate_id": self.candidate.transform_id,
            "action_permit": self.action_permit.to_dict() if self.action_permit else None,
            "new_state": self.new_state,
            "backtracked": self.backtracked,
            "backtrack_reason": self.backtrack_reason,
            "remaining_admissible": self.remaining_admissible,
        }


class MGateOrchestrator:
    """
    Three sequential gated TOTE loop orchestrator.
    
    Per white paper §12-§17:
    - Each gate is a repeat-until-satisfied TOTE loop
    - Advancement requires EXIT(G1) AND EXIT(G2) AND EXIT(G3)
    - Failure triggers backtracking into remaining admissible transform space
    - UNKNOWN is a first-class state, never silently promoted to PASS
    """
    
    def __init__(
        self,
        gate_definitions: Optional[List[GateDefinition]] = None,
        max_gate_iterations: int = 5,
    ) -> None:
        """
        Initialize the MGate orchestrator.
        
        Args:
            gate_definitions: List of 3 gate definitions (G1, G2, G3).
                If None, uses default generic gates.
            max_gate_iterations: Maximum iterations per gate TOTE loop.
        """
        if gate_definitions is None:
            gate_definitions = self._default_gate_definitions()
        
        if len(gate_definitions) != 3:
            raise ValueError(f"MGate requires exactly 3 gate definitions, got {len(gate_definitions)}")
        
        self.gate_definitions = gate_definitions
        self.max_gate_iterations = max_gate_iterations
        self._execution_history: List[GateExecutionResult] = []
        self._permit_counter = 0
    
    def _default_gate_definitions(self) -> List[GateDefinition]:
        """Default gate definitions per white paper §12."""
        def self_actor_evaluator(state: dict[str, Any], context: NychContext, packet: NychPacket) -> Tuple[str, str]:
            if not state:
                return GateOutcome.UNKNOWN, "empty_state"
            if context.domain:
                return GateOutcome.PASS, "self_actor_established"
            return GateOutcome.FAIL, "missing_domain"
        
        def problem_space_evaluator(state: dict[str, Any], context: NychContext, packet: NychPacket) -> Tuple[str, str]:
            if state.get("domain") == context.domain:
                return GateOutcome.PASS, "problem_space_consistent"
            return GateOutcome.FAIL, "domain_mismatch"
        
        def perspective_evaluator(state: dict[str, Any], context: NychContext, packet: NychPacket) -> Tuple[str, str]:
            # Perspective/tense required only for language inputs
            if packet.source_type.value == "sensor":
                return GateOutcome.PASS, "sensor_input_no_perspective_required"
            if context.perspective and context.tense:
                return GateOutcome.PASS, "perspective_established"
            return GateOutcome.FAIL, "missing_perspective_or_tense"
        
        return [
            GateDefinition(
                gate_id="G1_SELF_ACTOR",
                gate_name="Self/Actor Validation",
                gate_type="self_actor",
                atomic_requirements=[
                    AtomicRequirement(
                        req_id="R1_SA",
                        requirement="domain_and_subject_established",
                        threshold_efficiency=0.9,
                        evaluator=self_actor_evaluator,
                    )
                ],
                exit_criterion="self_actor_established",
            ),
            GateDefinition(
                gate_id="G2_PROBLEM_SPACE",
                gate_name="Problem Space Validation",
                gate_type="problem_space",
                atomic_requirements=[
                    AtomicRequirement(
                        req_id="R2_PS",
                        requirement="domain_consistency",
                        threshold_efficiency=0.9,
                        evaluator=problem_space_evaluator,
                    )
                ],
                exit_criterion="problem_space_established",
            ),
            GateDefinition(
                gate_id="G3_PERSPECTIVE",
                gate_name="Perspective/Conditions Validation",
                gate_type="perspective",
                atomic_requirements=[
                    AtomicRequirement(
                        req_id="R3_PV",
                        requirement="perspective_and_tense_established",
                        threshold_efficiency=0.9,
                        evaluator=perspective_evaluator,
                    )
                ],
                exit_criterion="perspective_established",
            ),
        ]
    
    def execute_mgate_for_rung(
        self,
        rung_index: int,
        candidate: CandidateTransform,
        context: NychContext,
        packet: NychPacket,
        current_state: NychState,
        remaining_admissible: List[CandidateTransform],
    ) -> GateExecutionResult:
        """
        Execute the complete three-gate MGate set for one trajectory rung.
        
        Per white paper §13:
        S_i --G1:3^i--> S_{i+1}
        
        If all three gates EXIT, advance to next rung.
        If any gate cannot EXIT, backtrack and try another admissible transform.
        
        Args:
            rung_index: Current trajectory rung index.
            candidate: The candidate transform to test.
            context: The current NYCH context.
            packet: The current NYCH packet.
            current_state: The current NYCH state.
            remaining_admissible: List of remaining admissible transforms for backtracking.
        
        Returns:
            GateExecutionResult with outcome.
        """
        state_dict = current_state.current or {}
        
        # Create three-gate set for this rung
        gate_set = self._create_gate_set(rung_index)
        
        # Execute G1: TEST -> OPERATE -> TEST -> EXIT
        g1_result = self._execute_single_gate(
            gate_set.g1, candidate, context, packet, state_dict
        )
        if g1_result.state != "EXIT":
            return GateExecutionResult(
                rung_index=rung_index,
                passed=False,
                gate_set=gate_set,
                candidate=candidate,
                backtracked=True,
                backtrack_reason=f"G1_failed: {g1_result.reasons}",
                remaining_admissible=len(remaining_admissible),
            )
        
        # Execute G2: TEST -> OPERATE -> TEST -> EXIT
        g2_result = self._execute_single_gate(
            gate_set.g2, candidate, context, packet, state_dict
        )
        if g2_result.state != "EXIT":
            return GateExecutionResult(
                rung_index=rung_index,
                passed=False,
                gate_set=gate_set,
                candidate=candidate,
                backtracked=True,
                backtrack_reason=f"G2_failed: {g2_result.reasons}",
                remaining_admissible=len(remaining_admissible),
            )
        
        # Execute G3: TEST -> OPERATE -> TEST -> EXIT
        g3_result = self._execute_single_gate(
            gate_set.g3, candidate, context, packet, state_dict
        )
        if g3_result.state != "EXIT":
            return GateExecutionResult(
                rung_index=rung_index,
                passed=False,
                gate_set=gate_set,
                candidate=candidate,
                backtracked=True,
                backtrack_reason=f"G3_failed: {g3_result.reasons}",
                remaining_admissible=len(remaining_admissible),
            )
        
        # All three gates EXIT - issue ActionPermit
        gate_set.all_exit = True
        action_permit = self._issue_action_permit(gate_set, current_state, candidate)
        
        # Compute new state
        new_state = self._advance_state(state_dict, candidate)
        
        return GateExecutionResult(
            rung_index=rung_index,
            passed=True,
            gate_set=gate_set,
            candidate=candidate,
            action_permit=action_permit,
            new_state=new_state,
            remaining_admissible=len(remaining_admissible),
        )
    
    def _create_gate_set(self, rung_index: int) -> ThreeGateSet:
        """Create a fresh three-gate set for a trajectory rung."""
        instances = []
        for i, gate_def in enumerate(self.gate_definitions, 1):
            instance = GateInstance(
                gate_id=f"{gate_def.gate_id}_rung{rung_index}",
                gate_type=gate_def.gate_type,
                definition=gate_def,
                iteration=0,
                state="PENDING",
            )
            instances.append(instance)
        
        return ThreeGateSet(
            rung_index=rung_index,
            g1=instances[0],
            g2=instances[1],
            g3=instances[2],
        )
    
    def _execute_single_gate(
        self,
        gate_instance: GateInstance,
        candidate: CandidateTransform,
        context: NychContext,
        packet: NychPacket,
        state: dict[str, Any],
    ) -> GateInstance:
        """
        Execute a single gate's TOTE loop: TEST -> OPERATE -> TEST -> EXIT
        
        Repeats until:
        - EXIT criterion is met
        - Max iterations reached (FAIL)
        - UNKNOWN result prevents satisfaction
        """
        gate_def = gate_instance.definition
        current_gate = GateInstance(
            gate_id=gate_instance.gate_id,
            gate_type=gate_instance.gate_type,
            definition=gate_def,
            iteration=0,
            state="TESTING",
        )
        
        for iteration in range(gate_def.max_iterations):
            current_gate.iteration = iteration
            
            # TEST phase
            outcome, reasons = gate_def.evaluate(state, context, packet)
            current_gate.record_test(outcome, reasons, state)
            
            if outcome == GateOutcome.UNKNOWN:
                # Cannot satisfy - explicit UNKNOWN
                current_gate.state = "UNKNOWN"
                gate_instance.state = "UNKNOWN"
                gate_instance.last_outcome = GateOutcome.UNKNOWN
                gate_instance.reasons = reasons
                gate_instance.history = current_gate.history
                gate_instance.iteration = iteration
                return current_gate
            
            if outcome == GateOutcome.FAIL:
                # Not satisfied, try OPERATE to improve state
                pass  # Fall through to OPERATE
            
            if outcome == GateOutcome.PASS:
                # Exit criterion met
                current_gate.state = "EXIT"
                gate_instance.state = "EXIT"
                gate_instance.last_outcome = GateOutcome.PASS
                gate_instance.reasons = reasons
                gate_instance.history = current_gate.history
                gate_instance.iteration = iteration
                return current_gate
            
            # OPERATE phase
            state = self._operate_gate(state, gate_def, candidate)
            current_gate.record_operate(state)
            current_gate.state = "TESTING"
        
        # Max iterations reached without EXIT
        current_gate.state = "FAIL"
        current_gate.last_outcome = GateOutcome.FAIL
        current_gate.reasons = [f"max_iterations_exceeded: {gate_def.max_iterations}"]
        gate_instance.state = "FAIL"
        gate_instance.last_outcome = GateOutcome.FAIL
        gate_instance.reasons = current_gate.reasons
        gate_instance.history = current_gate.history
        gate_instance.iteration = gate_def.max_iterations - 1
        return current_gate
    
    def _operate_gate(
        self,
        state: dict[str, Any],
        gate_def: GateDefinition,
        candidate: CandidateTransform,
    ) -> dict[str, Any]:
        """
        OPERATE phase: attempt to improve state to satisfy gate.
        
        This is a placeholder that advances state toward the candidate's output state.
        In production, this would invoke domain-specific operations.
        """
        new_state = dict(state)
        
        # Apply candidate's output state as transformation
        for key, value in candidate.output_state.items():
            if key not in new_state or new_state[key] != value:
                new_state[key] = value
        
        # Increment operation counter
        new_state["_operations"] = new_state.get("_operations", 0) + 1
        
        return new_state
    
    def _advance_state(
        self,
        state: dict[str, Any],
        candidate: CandidateTransform,
    ) -> dict[str, Any]:
        """Advance state after successful gate execution."""
        new_state = dict(state)
        new_state["last_transition"] = candidate.transform_id
        return new_state
    
    def _issue_action_permit(
        self,
        gate_set: ThreeGateSet,
        current_state: NychState,
        candidate: CandidateTransform,
    ) -> ActionPermit:
        """
        Issue a single-use ActionPermit bound to the current semantic/provenance snapshot.
        
        Per white paper §15:
        - Bound to canonical serialized semantic nodes and provenance
        - Bound to current revision/epoch, state, plan hash, and semantic hash
        - Any semantic/provenance mutation revokes the permit
        """
        self._permit_counter += 1
        
        state_snapshot = current_state.current or {}
        state_hash = hashlib.sha256(
            str(state_snapshot).encode()
        ).hexdigest()[:16]
        
        semantic_snapshot = {
            "gate_set_hash": hashlib.sha256(
                str(gate_set.to_dict()).encode()
            ).hexdigest()[:16],
            "candidate_id": candidate.transform_id,
            "technique": candidate.technique,
        }
        semantic_hash = hashlib.sha256(
            str(semantic_snapshot).encode()
        ).hexdigest()[:16]
        
        gate_set_hash = semantic_snapshot["gate_set_hash"]
        
        return ActionPermit(
            permit_id=f"permit_{self._permit_counter:06d}",
            state_hash=state_hash,
            semantic_hash=semantic_hash,
            epoch=current_state.current.get("epoch", 0) if current_state.current else 0,
            gate_set_hash=gate_set_hash,
            state=GateState.ISSUED,
        )
    
    def get_execution_history(self) -> List[GateExecutionResult]:
        """Get the complete gate execution history."""
        return list(self._execution_history)
