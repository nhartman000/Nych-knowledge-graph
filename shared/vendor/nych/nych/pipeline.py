"""
NYCH Pipeline Orchestrator
===========================
Orchestrates the complete NYCH pipeline from input to evidence emission
following the canonical architecture diagrams and white paper §25.

Pipeline stages:
1. INGEST (Machine Sensor / Natural Language Input)
2. IDENTITY / VERNACULAR (Time Embedding + Vernacular Check)
3. FEATURE NORMALIZATION (Fidelity & Pattern Evaluation)
4. INVARIANT EXTRACTION (Modality operators invariant)
5. SYMBOLIZATION (Gestalt Extraction & Emoji Selection)
6. CONTEXT BUILD (Domain of the Machine / Field of Influence)
7. DOMAIN EXPANSION (DOTM Cataloging)
8. INVERSE TRANSFORM / CONSTRAINT MASK
9. CANDIDATE SELECTION
10. THREE-GATE MGATE (G1 -> G2 -> G3 per trajectory rung)
11. BACKTRACK / ADVANCE (hierarchical trajectory search)
12. FAST/SLOW PATH (adaptive resolution)
13. LLM / PROBABILISTIC REASONING (if slow path)
14. OKA / BEHAVIORAL ENCRYPTION
15. MACHINE B VALIDATOR (Deterministic Verification)
16. MEMORY UPDATE (State Persistence)
17. MG8 / G8SON CONTAINER ASSEMBLY
18. EVIDENCE EMISSION (QSON TraceID Audit Ledger)
19. PACKAGE/RETURN
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

from nych.constraint import apply_constraints
from nych.container import MG8ContainerAssembly, G8SONGate
from nych.context import build_context
from nych.domain import expand_domain
from nych.encryption import BehavioralEncryption
from nych.evidence import create_audit_unit, emit_evidence, update_gst_state
from nych.exceptions import (
    ConstraintViolationError,
    DomainExpansionError,
    IngestionError,
    SymbolizationError,
    TOTEError,
    ValidationError,
)
from nych.fast_slow import decide_path
from nych.gates import (
    ActionPermit,
    GateExecutionResult,
    GateOutcome,
    MGateOrchestrator,
    ThreeGateSet,
)
from nych.hdrp import HDRPSymbolicTrajectoryPredictor
from nych.identity import analyze_identity
from nych.invariant import extract_invariants
from nych.machine_b import MachineBValidator
from nych.memory import MemoryUpdate
from nych.normalization import normalize_features
from nych.reasoning import LLMReasoningEngine, OKAIntegrator
from nych.selection import select_candidate
from nych.symbolization import symbolicate
from nych.tote import execute_tote
from nych.types import (
    CandidateTransform,
    InputType,
    NychContext,
    NychPacket,
    NychState,
    NYCHPipelineResult,
    ValidationResult,
)
from nych.validation import validate_continuity, validate_result


class _NoMGateResult:
    """Minimal stand-in for GateExecutionResult when MGate is disabled."""
    __slots__ = ("candidate", "new_state")
    
    def __init__(self, candidate: Any, new_state: dict[str, Any]) -> None:
        self.candidate = candidate
        self.new_state = new_state


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for the NYCH pipeline."""
    packet_version: str = "1.0.0"
    use_probabilistic_selection: bool = False
    selection_seed: int | None = None
    max_tote_iterations: int = 10
    max_mgate_iterations: int = 5
    max_backtrack_steps: int = 10
    confidence_threshold: float = 0.5
    enable_encryption: bool = False
    enable_oka: bool = False
    enable_machine_b: bool = True
    enable_memory_persistence: bool = True
    enable_mgate: bool = True
    congruence_loop_interval: int = 5


def run_pipeline(
    input_data: InputType,
    config: PipelineConfig | None = None,
) -> NYCHPipelineResult:
    """
    Run the complete NYCH pipeline on the given input.
    
    Per white paper §25, the control sequence is:
    1. INGEST
    2. Resolve perspective, tense, pronouns, domain, subject, context, modality
    3. Construct/retrieve symbols and candidate Gestalts
    4. Gestalt recognition
    5. TCTA admissible transform envelope
    6. Select candidate trajectory
    7. Three sequential G8SON/TOTE gate loops per rung
    8. TEST -> OPERATE -> TEST -> EXIT within each gate
    9. If all three EXIT, advance; else backtrack
    10. Increase resolution on ambiguity/contradiction
    11. ActionPermit before external actuation
    12. Fresh OBS after ACT
    13. QSON evidence
    14. Memory update
    
    Args:
        input_data: The input to process.
        config: Optional pipeline configuration.
    
    Returns:
        NYCHPipelineResult with complete pipeline output.
    
    Raises:
        IngestionError: If ingestion fails.
        SymbolizationError: If symbolization fails.
        DomainExpansionError: If domain expansion fails.
        ConstraintViolationError: If no admissible candidates.
        TOTEError: If TOTE/MGate execution fails.
        ValidationError: If validation fails.
    """
    if config is None:
        config = PipelineConfig()
    
    start_time = time.time()
    metrics = {}
    
    # Initialize deterministic components
    hdrp_predictor = HDRPSymbolicTrajectoryPredictor()
    llm_engine = LLMReasoningEngine(constrained=True)
    oka_integrator = OKAIntegrator()
    encryption = BehavioralEncryption(enabled=config.enable_encryption)
    machine_b = MachineBValidator()
    memory = MemoryUpdate()
    mg8_assembly = MG8ContainerAssembly()
    mgate_orchestrator = MGateOrchestrator(max_gate_iterations=config.max_mgate_iterations)
    
    # Stage 1: INGEST
    packet, context, state = _ingest_stage(input_data, config.packet_version)
    metrics["ingest_time"] = time.time() - start_time
    
    # Stage 2: IDENTITY / VERNACULAR
    identity = _identity_stage(packet, context, input_data)
    metrics["identity_time"] = time.time() - start_time - metrics["ingest_time"]
    context = _update_context_with_identity(context, identity)
    
    # Stage 3: FEATURE NORMALIZATION
    normalized = _normalization_stage(packet, state, input_data)
    metrics["normalization_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 4: INVARIANT EXTRACTION
    invariants = _invariant_stage(packet, state, normalized)
    metrics["invariant_time"] = time.time() - start_time - sum(metrics.values())
    
    # Update state with invariant modality operators
    state = state.__class__(
        prior=state.prior,
        current=state.current,
        internal_prior=state.internal_prior,
        internal_current=state.internal_current,
        external_prior=state.external_prior,
        external_current=state.external_current,
        continuity_reference=state.continuity_reference,
        modality_operators=invariants.modality_operators,
    )
    
    # Stage 5: SYMBOLIZATION
    symbolization = _symbolization_stage(packet, state, invariants, normalized)
    metrics["symbolization_time"] = time.time() - start_time - sum(metrics.values())
    
    # Update packet with symbols
    packet = packet.__class__(
        packet_id=packet.packet_id,
        version=packet.version,
        source_type=packet.source_type,
        symbols=symbolization.symbols,
        operators=[op.value for op in invariants.cognitive_operators] + [op.value for op in invariants.control_operators],
        numeric_values=normalized.numbers,
        metadata_refs={
            **packet.metadata_refs,
            "consonant_skeletons": symbolization.consonant_skeletons,
            "gestalt_emoji": symbolization.gestalt_emoji,
            "numeric_embeddings": symbolization.numeric_embeddings,
        },
    )
    
    # Stage 6: CONTEXT BUILD
    constructed_context = _context_stage(packet, state, identity, invariants, symbolization)
    context = constructed_context.context
    metrics["context_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 7: DOMAIN EXPANSION
    expansion = _domain_stage(packet, context, state)
    metrics["domain_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 8: INVERSE TRANSFORM / CONSTRAINT MASK
    candidates = _generate_candidates(expansion)
    constraint_mask = _constraint_stage(candidates, context, packet, state)
    metrics["constraint_time"] = time.time() - start_time - sum(metrics.values())
    
    if not constraint_mask.admissible_candidates:
        raise ConstraintViolationError(
            "No admissible candidates after constraint masking. "
            f"Rejection reasons: {constraint_mask.rejection_reasons}"
        )
    
    # Stage 9: CANDIDATE SELECTION
    selection = _selection_stage(
        constraint_mask.admissible_candidates,
        context,
        packet,
        state,
        config.use_probabilistic_selection,
        config.selection_seed,
    )
    metrics["selection_time"] = time.time() - start_time - sum(metrics.values())
    
    if selection.selected is None:
        raise ConstraintViolationError("No candidate selected")
    
    # Stage 10-11: THREE-GATE MGATE + BACKTRACK
    # Per white paper §12-§14: hierarchical trajectory search with backtracking
    if config.enable_mgate:
        mgate_results, final_state, action_permit, backtrack_count = _mgate_stage(
            mgate_orchestrator,
            selection.selected,
            constraint_mask.admissible_candidates,
            context,
            packet,
            state,
            config.max_backtrack_steps,
        )
    else:
        # No MGate: advance with selected candidate directly
        mgate_results = []
        final_state = selection.selected.output_state
        action_permit = None
        backtrack_count = 0
    metrics["mgate_time"] = time.time() - start_time - sum(metrics.values())
    
    if config.enable_mgate and (not mgate_results or not any(r.passed for r in mgate_results)):
        raise TOTEError(
            f"All candidates failed MGate validation after {backtrack_count} backtrack steps. "
            f"Gate failures: {[r.backtrack_reason for r in mgate_results if not r.passed]}"
        )
    
    # Take the first successful result (or construct one when MGate is disabled)
    if config.enable_mgate:
        successful_result = next(r for r in mgate_results if r.passed)
    else:
        successful_result = _NoMGateResult(selection.selected, final_state)
    
    # Stage 12: CONTINUITY VALIDATION
    prior_state = state
    current_state = state.advance(final_state)
    continuity = _validation_stage(prior_state, current_state, context, packet, successful_result)
    validation = validate_result(continuity, context)
    metrics["validation_time"] = time.time() - start_time - sum(metrics.values())
    
    if not validation.valid:
        raise ValidationError(
            f"Validation failed: {validation.reasons}. "
            f"Continuity score: {validation.continuity_score}"
        )
    
    # Stage 13: FAST/SLOW PATH
    confidence = successful_result.candidate.score if successful_result.candidate else 1.0
    path_decision = _fast_slow_stage(
        packet, context, current_state, invariants, validation, confidence,
        config.congruence_loop_interval
    )
    metrics["path_decision_time"] = time.time() - start_time - sum(metrics.values())
    
    if not path_decision.use_fast_path:
        # Stage 14: LLM / PROBABILISTIC REASONING ENGINE
        reasoning_result = _reasoning_stage(
            packet, context, current_state, constraint_mask.admissible_candidates
        )
        metrics["reasoning_time"] = time.time() - start_time - sum(metrics.values())
        
        if config.enable_oka:
            _oka_stage(oka_integrator, packet, context, current_state, reasoning_result)
            metrics["oka_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 15: BEHAVIORAL ENCRYPTION
    encrypted_payload = _encryption_stage(
        encryption, packet, context, current_state, successful_result
    )
    metrics["encryption_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 16: MACHINE B VALIDATOR
    machine_b_validation = _machine_b_stage(
        machine_b, packet, context, current_state, successful_result
    )
    metrics["machine_b_time"] = time.time() - start_time - sum(metrics.values())
    
    if config.enable_machine_b and not machine_b_validation.valid:
        raise ValidationError(
            f"Machine B validation failed: {machine_b_validation.rule_checks}"
        )
    
    if config.enable_machine_b:
        validation = machine_b.to_validation_result(machine_b_validation)
    
    # Stage 17: MEMORY UPDATE
    memory_result = _memory_stage(
        memory, packet, context, current_state, successful_result
    )
    metrics["memory_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 18: MG8 / G8SON CONTAINER ASSEMBLY
    g8son_gates = mg8_assembly.create_g8son_gates(constraint_mask)
    mg8_container = _mg8_stage(
        mg8_assembly, packet, context, current_state, validation, g8son_gates, []
    )
    metrics["mg8_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 19: EVIDENCE EMISSION
    evidence_events = _evidence_stage(
        packet, context, current_state, validation, prior_state
    )
    metrics["evidence_time"] = time.time() - start_time - sum(metrics.values())
    
    # Stage 20: PACKAGE/RETURN
    audit = create_audit_unit(packet, context, current_state, validation, metrics)
    
    # Build MGate execution summary
    mgate_summary = {
        "total_rungs": len(mgate_results),
        "successful_rungs": sum(1 for r in mgate_results if r.passed),
        "backtrack_count": backtrack_count,
        "gate_executions": [r.gate_set.to_dict() for r in mgate_results],
        "action_permit": action_permit.to_dict() if action_permit else None,
    }
    
    result = NYCHPipelineResult(
        packet=packet,
        context=context,
        state=current_state,
        validation=validation,
        audit=audit,
        evidence=[e.to_dict() if hasattr(e, "to_dict") else e for e in evidence_events],
        g8son=mg8_container.g8son,
        mg8={
            "orchestration": mg8_container.orchestration,
            "state": mg8_container.state_refs,
            "gates": mg8_container.gates,
            "evidence": mg8_container.evidence_refs,
            "container_id": mg8_container.container_id,
        },
        mgate_summary=mgate_summary,
    )
    
    return result


# Stage implementations (private)

def _ingest_stage(input_data: InputType, version: str) -> tuple[NychPacket, NychContext, NychState]:
    from nych.ingest import ingest
    return ingest(input_data, version)


def _update_context_with_identity(context: NychContext, identity: Any) -> NychContext:
    modality = getattr(identity, "modality", context.modality)
    perspective = getattr(identity, "perspective", context.perspective)
    tense = getattr(identity, "tense", context.tense)
    
    return context.__class__(
        domain=context.domain,
        subject=context.subject,
        intent=context.intent,
        competency=context.competency,
        modality=modality,
        perspective=perspective,
        tense=tense,
        tools=context.tools,
        constraints=context.constraints,
        subdomains=context.subdomains,
        specialties=context.specialties,
    )


def _identity_stage(packet: NychPacket, context: NychContext, raw_input: Any) -> Any:
    from nych.identity import analyze_identity
    return analyze_identity(packet, context, raw_input)


def _normalization_stage(packet: NychPacket, state: NychState, raw_input: Any) -> Any:
    from nych.normalization import normalize_features
    return normalize_features(packet, state, raw_input)


def _invariant_stage(packet: NychPacket, state: NychState, normalized: Any) -> Any:
    from nych.invariant import extract_invariants
    return extract_invariants(packet, state, normalized)


def _symbolization_stage(packet: NychPacket, state: NychState, invariants: Any, normalized: Any) -> Any:
    from nych.symbolization import symbolicate
    return symbolicate(packet, state, invariants, normalized)


def _context_stage(packet: NychPacket, state: NychState, identity: Any, invariants: Any, symbolization: Any) -> Any:
    from nych.context import build_context
    return build_context(packet, state, identity, invariants, symbolization)


def _domain_stage(packet: NychPacket, context: NychContext, state: NychState) -> Any:
    from nych.domain import expand_domain
    return expand_domain(packet, context, state)


def _generate_candidates(expansion: Any) -> list[Any]:
    from nych.types import CandidateTransform
    candidates = []
    for tote in expansion.tote_candidates:
        candidate = CandidateTransform(
            transform_id=tote["tote_id"],
            input_state={"domain": expansion.domain},
            output_state={"domain": expansion.domain, "technique": expansion.technique},
            technique=expansion.technique,
            tote=tote,
            admissibility_evidence=["domain_match", "competency_match"],
            score=tote.get("admissibility_score", 1.0),
        )
        candidates.append(candidate)
    return candidates


def _constraint_stage(candidates: list[Any], context: NychContext, packet: NychPacket, state: NychState) -> Any:
    return apply_constraints(candidates, context, packet, state)


def _selection_stage(candidates: list[Any], context: NychContext, packet: NychPacket, state: NychState, use_prob: bool, seed: int | None) -> Any:
    from nych.selection import select_candidate
    return select_candidate(candidates, context, packet, state, use_probabilistic=use_prob, seed=seed)


def _mgate_stage(
    orchestrator: MGateOrchestrator,
    initial_candidate: CandidateTransform,
    admissible_candidates: list[CandidateTransform],
    context: NychContext,
    packet: NychPacket,
    state: NychState,
    max_backtrack: int,
) -> tuple[List[GateExecutionResult], dict[str, Any], Optional[ActionPermit], int]:
    """
    Execute hierarchical trajectory search with three-gate MGate and backtracking.
    
    Per white paper §13-§14:
    - Instantiate three-gate set for each trajectory rung
    - If gate fails, backtrack to remaining admissible transforms
    - Continue until success or exhaustion
    
    Returns:
        Tuple of (gate_results, final_state, action_permit, total_backtracks)
    """
    results: List[GateExecutionResult] = []
    current_state = state
    action_permit: Optional[ActionPermit] = None
    total_backtracks = 0
    
    # Work with a mutable list of remaining candidates
    remaining = list(admissible_candidates)
    tried_candidates = set()
    
    for attempt in range(max_backtrack + 1):
        if not remaining:
            break
        
        # Select next candidate
        candidate = remaining.pop(0)
        tried_candidates.add(candidate.transform_id)
        
        # Execute three-gate MGate for this candidate
        result = orchestrator.execute_mgate_for_rung(
            rung_index=attempt,
            candidate=candidate,
            context=context,
            packet=packet,
            current_state=current_state,
            remaining_admissible=remaining,
        )
        
        results.append(result)
        
        if result.passed:
            # Success - advance state
            current_state = NychState(
                prior=current_state.current,
                current=result.new_state,
                internal_prior=current_state.internal_current,
                internal_current=current_state.internal_current,
                external_prior=current_state.external_current,
                external_current=current_state.external_current,
                continuity_reference=current_state.continuity_reference,
                modality_operators=current_state.modality_operators,
            )
            action_permit = result.action_permit
            return results, result.new_state, action_permit, total_backtracks
        
        # Failure - backtrack if we have remaining candidates
        total_backtracks += 1
        if remaining:
            # Continue to next candidate
            continue
        else:
            # No more candidates to try
            break
    
    # All candidates exhausted or max backtrack reached
    return results, current_state.current or {}, action_permit, total_backtracks


def _validation_stage(prior: NychState, current: NychState, context: NychContext, packet: NychPacket, tote_result: Any) -> Any:
    from nych.validation import validate_continuity
    return validate_continuity(prior, current, context, packet, tote_result)


def _fast_slow_stage(packet: NychPacket, context: NychContext, state: NychState, invariants: Any, validation: Any, confidence: float, congruence_interval: int) -> Any:
    from nych.fast_slow import decide_path
    return decide_path(packet, context, state, invariants, validation, confidence)


def _reasoning_stage(packet: NychPacket, context: NychContext, state: NychState, candidates: list[Any]) -> Any:
    from nych.reasoning import LLMReasoningEngine
    engine = LLMReasoningEngine(constrained=True)
    boundary = [c.transform_id for c in candidates]
    return engine.generate(context, packet, state, boundary)


def _oka_stage(oka: Any, packet: NychPacket, context: NychContext, state: NychState, reasoning: Any) -> None:
    oka.integrate(context, packet, state, context.domain, "unknown")


def _encryption_stage(encryption: Any, packet: NychPacket, context: NychContext, state: NychState, tote_result: Any) -> dict[str, Any]:
    payload = {
        "tote_result": tote_result.new_state if hasattr(tote_result, "new_state") else {},
        "state": state.current,
        "context": context.to_dict(),
    }
    result = encryption.encrypt(packet, context, state, payload)
    return result.encrypted_payload


def _machine_b_stage(machine_b: Any, packet: NychPacket, context: NychContext, state: NychState, tote_result: Any) -> Any:
    return machine_b.verify(packet, context, state, tote_result)


def _memory_stage(memory: Any, packet: NychPacket, context: NychContext, state: NychState, tote_result: Any) -> Any:
    return memory.update(packet, context, state)


def _mg8_stage(mg8_assembly: Any, packet: NychPacket, context: NychContext, state: NychState, validation: ValidationResult, gates: list[Any], evidence_refs: list[Any]) -> Any:
    return mg8_assembly.assemble(packet, context, state, validation, gates, evidence_refs)


def _evidence_stage(packet: NychPacket, context: NychContext, state: NychState, validation: ValidationResult, prior_state: NychState) -> list[Any]:
    from nych.evidence import emit_evidence, create_audit_unit, update_gst_state
    from nych.types import NYCHPipelineResult
    result = NYCHPipelineResult(
        packet=packet,
        context=context,
        state=state,
        validation=validation,
        audit=create_audit_unit(packet, context, state, validation),
    )
    return emit_evidence(result)
