"""tcta_bridge.py -- wires tcta_engine's Omega(C)/SPREAD/ALGORITHM_SELECT
onto NYCH's OWN, already-running candidate/constraint/selection stage
(domain.expand_domain -> constraint.apply_constraints ->
selection.select_candidate; pipeline.py's stages 7, 8, 9).

Why this stage and not mg8-engine's: that pipeline (domain expansion,
constraint masking, candidate selection) is where NYCH already enumerates
more than one candidate and narrows them -- `ConstraintMask` IS an
admissible/rejected split, `SelectionResult` IS a final choice among the
admissible set. mg8-engine's Gestalt-mapping pipeline, by contrast, is a
single LLM call with no enumerated candidate set to narrow (see
mg8_engine.tcta_bridge for the thinner, honestly-scoped version of this
same algebra applied there instead).

This module does not change `apply_constraints`/`select_candidate`'s own
decisions -- it reads their already-computed `ConstraintMask`/
`SelectionResult` and re-expresses the same admissible/selected split in
tcta_engine's SR/Transform/Omega(C)/SPREAD vocabulary, as a disclosed
audit layer, not a second, competing decision process. The cross-check in
`verify_omega_c_matches_constraint_mask` exists precisely to catch the two
ever disagreeing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .constraint import ConstraintMask
from .selection import SelectionResult
from .types import CandidateTransform

from tcta_engine.core import (
    StateRepresentation,
    Transform,
    Trajectory,
    admissible_trajectory_space,
    compute_spread,
    select_algorithm,
)


def _candidate_transform(candidate: CandidateTransform) -> Transform:
    """Wraps an already-resolved `CandidateTransform` (its output_state is
    precomputed, not a function of input_state) as a `tcta_engine.core.
    Transform`. `apply` ignores its argument and replays the known
    output_state, stamped with `_transform_id` so a `constraint_check`
    that only sees `(result_state, constraints)` (tcta_engine.core's call
    shape) can still look the candidate up by id -- see
    `constraint_check_from_mask` -- without changing output_state's own
    keys. See nych.ogsi's build_expansion_trajectory for the same
    wrapping pattern applied to domain-expansion waypoints."""
    return Transform(
        transform_id=candidate.transform_id,
        apply=lambda _s, c=candidate: {**c.output_state, "_transform_id": c.transform_id},
    )


def candidates_to_trajectories(
    candidates: List[CandidateTransform],
) -> Dict[str, Trajectory]:
    """Each `CandidateTransform` becomes its own length-1 `Trajectory`,
    keyed by transform_id. Honesty note: NYCH's current TOTE-candidate
    selection stage picks one TOTE loop per domain expansion in a single
    step, not a multi-step composed path, so length-1 is what the actual
    data supports today -- this is not a simplification this module
    chose, it is what `_generate_candidates` (pipeline.py) produces."""
    return {c.transform_id: [_candidate_transform(c)] for c in candidates}


def constraint_check_from_mask(mask: ConstraintMask):
    """Builds the `constraint_check(result_state, constraints) -> bool`
    callable `tcta_engine.core.is_admissible_trajectory`/
    `admissible_trajectory_space` require, from an already-computed
    `ConstraintMask` -- reusing NYCH's own admissibility decision (by
    transform_id) rather than re-deriving a second one."""
    admissible_ids = {c.transform_id for c in mask.admissible_candidates}

    def _check(result_state: Dict[str, Any], constraints: Any) -> bool:
        return result_state.get("_transform_id") in admissible_ids

    return _check


def _sr0_for(domain: str) -> StateRepresentation:
    return StateRepresentation(s={"domain": domain}, domain=domain, constraints=None)


def verify_omega_c_matches_constraint_mask(
    candidates: List[CandidateTransform],
    mask: ConstraintMask,
) -> bool:
    """Cross-check: recomputes Omega(C) via `tcta_engine.core.
    admissible_trajectory_space` against the SAME admissibility decision
    `constraint_check_from_mask` exposes, and confirms it reproduces
    exactly `mask.admissible_candidates` (by transform_id, order-
    independent). This is the actual integration test for this bridge --
    a mismatch would mean the wrapping above lost or mislabeled a
    candidate, not that NYCH's own constraint logic is wrong."""
    trajectories = candidates_to_trajectories(candidates)
    check = constraint_check_from_mask(mask)
    domain = mask.admissible_candidates[0].output_state.get("domain") if mask.admissible_candidates else (
        mask.rejected_candidates[0].output_state.get("domain") if mask.rejected_candidates else ""
    )
    sr0 = _sr0_for(domain)

    recomputed_ids = set()
    for tid, trajectory in trajectories.items():
        if admissible_trajectory_space([trajectory], sr0, check):
            recomputed_ids.add(tid)

    expected_ids = {c.transform_id for c in mask.admissible_candidates}
    return recomputed_ids == expected_ids


@dataclass(frozen=True)
class TctaNarrowingResult:
    """Disclosed record of the SPREAD/ALGORITHM_SELECT computation over
    one constraint+selection pass. `omega_c_count` is
    `mask.admissible_count`; `t_g_count` is 1 if a candidate was selected,
    else 0 (SelectionResult.selected is None when
    admissible_candidates was empty -- see selection.select_candidate)."""

    omega_c_count: int
    t_g_count: int
    spread: Optional[float]
    algorithm_select_result: Optional[str]
    algorithm_select_reason: Optional[str]
    note: Optional[str] = None


def compute_narrowing(
    mask: ConstraintMask,
    selection: SelectionResult,
    *,
    spread_low: float = 0.2,
    spread_high: float = 0.8,
) -> TctaNarrowingResult:
    """SPREAD = S(T_G)/S(Omega(C)) for one TOTE-candidate selection pass,
    using `mask.admissible_count` as S(Omega(C)) and 1 (one candidate
    selected) or 0 (none) as S(T_G). Compliance's own rule --
    SPREAD_NOT_COMPUTED_BEFORE_SELECTION -- is enforced by construction by
    always computing SPREAD here before calling `select_algorithm`,
    mirroring `tcta_engine.core.select_algorithm`'s own guard.

    When `omega_c_count` is 0 (every candidate was rejected), SPREAD is
    undefined (`compute_spread` requires S(Omega(C)) > 0) -- this is
    disclosed as `spread=None`, `algorithm_select_result=None`, with a
    `note`, rather than forcing a value or raising."""
    omega_c_count = mask.admissible_count
    t_g_count = 1 if selection.selected is not None else 0

    if omega_c_count <= 0:
        return TctaNarrowingResult(
            omega_c_count=omega_c_count,
            t_g_count=t_g_count,
            spread=None,
            algorithm_select_result=None,
            algorithm_select_reason=None,
            note="no admissible candidates; SPREAD is undefined (S(Omega(C)) must be > 0)",
        )

    spread = compute_spread(s_tg=float(t_g_count), s_omega_c=float(omega_c_count))
    result, reason = select_algorithm(spread, spread_low=spread_low, spread_high=spread_high)
    return TctaNarrowingResult(
        omega_c_count=omega_c_count,
        t_g_count=t_g_count,
        spread=spread,
        algorithm_select_result=result,
        algorithm_select_reason=reason,
    )
