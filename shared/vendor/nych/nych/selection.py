"""
NYCH Candidate Selection Module
===============================
Deterministic selector where possible; probabilistic model may rank/propose
only within the admissible boundary.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from nych.types import CandidateTransform, NychContext, NychPacket, NychState


@dataclass(frozen=True)
class SelectionResult:
    """Result of candidate selection."""
    selected: CandidateTransform | None = None
    ranked_candidates: list[CandidateTransform] = field(default_factory=list)
    selection_method: str = "deterministic"
    selection_reason: str = ""


def select_candidate(
    admissible_candidates: list[CandidateTransform],
    context: NychContext,
    packet: NychPacket,
    state: NychState,
    use_probabilistic: bool = False,
    seed: int | None = None,
) -> SelectionResult:
    """
    Select the best candidate from admissible transforms.
    
    Uses deterministic selection by default. Probabilistic model may
    rank/propose only within the admissible boundary.
    
    Args:
        admissible_candidates: List of admissible candidate transforms.
        context: The current NYCH context.
        packet: The current NYCH packet.
        state: The current NYCH state.
        use_probabilistic: Whether to use probabilistic ranking.
        seed: Optional seed for deterministic probabilistic selection.
    
    Returns:
        SelectionResult with the selected candidate.
    """
    if not admissible_candidates:
        return SelectionResult(
            selection_reason="no_admissible_candidates",
        )
    
    if use_probabilistic:
        return _probabilistic_select(admissible_candidates, seed)
    else:
        return _deterministic_select(admissible_candidates)


def _deterministic_select(
    candidates: list[CandidateTransform],
) -> SelectionResult:
    """
    Deterministic selection: highest admissibility score wins.
    Tie-breaking is explicit and stable (first in list wins).
    """
    # Sort by score descending, then by transform_id for stable tie-breaking
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (-c.score, c.transform_id),
    )
    
    selected = sorted_candidates[0]
    
    return SelectionResult(
        selected=selected,
        ranked_candidates=sorted_candidates,
        selection_method="deterministic",
        selection_reason=f"highest_score_{selected.score}",
    )


def _probabilistic_select(
    candidates: list[CandidateTransform],
    seed: int | None = None,
) -> SelectionResult:
    """
    Probabilistic selection within admissible boundary.
    
    The probabilistic model may rank/propose only within the admissible
    boundary. The output is treated as a proposal and must re-enter
    deterministic validation.
    """
    rng = random.Random(seed)
    
    # Weight by score (higher score = higher probability)
    scores = [max(0.01, c.score) for c in candidates]
    total = sum(scores)
    if total == 0:
        # Fallback to uniform
        weights = [1.0 / len(candidates)] * len(candidates)
    else:
        weights = [s / total for s in scores]
    
    selected = rng.choices(candidates, weights=weights, k=1)[0]
    
    # Sort by score for ranking
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (-c.score, c.transform_id),
    )
    
    return SelectionResult(
        selected=selected,
        ranked_candidates=sorted_candidates,
        selection_method="probabilistic",
        selection_reason=f"weighted_random_{selected.transform_id}",
    )
