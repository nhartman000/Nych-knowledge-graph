"""
NYCH Epistemic Status Module
=============================
Canonical definition of the epistemic-status axis: what a proposition is
licensed to do downstream, independent of which perceptual channel produced
it.

This axis is orthogonal to nych.types.Modality. Modality answers "which
sense produced this" (VE/VI/AE/AI/KE/KI/SME/TAS/MEN/IMG/REM), already mapped
to the 👀/👁️/👂/💪/👃/👅/🧠/🗯️/💭 symbol set in nych.invariant. EpistemicStatus
answers a different question -- "what is this proposition licensed to do
downstream" (OBS/MODEL/INTENT/ACT) -- and is deliberately word-only: three of
those same emoji (👀, 🗯️, 💪) already carry a different canonical meaning on
the Modality axis, so reusing them here would silently collapse two distinct
axes into one symbol space. See ANTI_PROMOTION_INVARIANTS below for the rules
that keep the two axes from being conflated even informally.

Origin: this status set and the anti-promotion invariants were established
during a PhiPhi multi-agent mesh run, recorded in
T.O.T.E-loops/docs/mesh/NYCH_PhiPhi_mesh_run_ex-1789523032006.md. That
document is the design record; this module is the canonical, importable
definition.

Canonical home: every .bonit file (nych.bonit, mg8.bonit, TOTElibrary.bonit,
and any future ork.bonit/tote.bonit) references this module rather than
restating EpistemicStatus or ANTI_PROMOTION_INVARIANTS inline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EpistemicStatus(str, Enum):
    """Invariant epistemic-status operators. Word-only -- see module
    docstring for why this does not reuse nych.types.Modality's emoji."""
    OBS = "OBS"        # external observation / sensor-licensed capture
    MODEL = "MODEL"    # internal model, prediction, expectation, belief
    INTENT = "INTENT"  # explicitly licensed operative intention / target
    ACT = "ACT"        # executed physical or operational action


class ResidualState(str, Enum):
    """Domain of a residual comparison. UNKNOWN whenever either required
    operand is absent, unlicensed, stale, or conflicted -- absence of
    mismatch is never evidence of match."""
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


# Anti-promotion invariants. These never change per schema; any .bonit that
# adopts EpistemicStatus adopts these four rules unconditionally, by
# reference, not by restating them.
ANTI_PROMOTION_INVARIANTS: tuple[str, ...] = (
    "ACT !-> OBS_POSTCONDITION",  # execution never proves its expected result
    "ACT !-> INTENT",             # an action never proves the actor's goal
    "MODEL !-> OBS",               # belief/prediction never becomes observation via confidence alone
    "END !-> EXIT",                 # narrative termination is not verified goal satisfaction
)


@dataclass(frozen=True)
class Residual:
    """A single Delta(a, b) comparison result, always carrying its domain."""
    kind: str  # "E_MODEL" | "E_GOAL"
    state: ResidualState


def missing_operand_residual(kind: str) -> Residual:
    """A residual computed with a missing/unlicensed operand is always
    UNKNOWN -- never defaulted to MATCH or MISMATCH."""
    return Residual(kind=kind, state=ResidualState.UNKNOWN)
