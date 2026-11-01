"""ogsi.py -- NYCH's own Gamma (invariant projection) and Psi (OGSI family
resolution), grounded in domain.py's actual domain-expansion path.

docs/OGSI.md in the TCTA repo is explicit that Gamma/Psi are domain-specific
modeling decisions it does not make on any domain's behalf -- it supplies
only the GammaOperator/PsiOperator call shapes and the H1 (prefix
stability) test function. This module is NYCH's own answer for ONE
concrete trajectory shape that already exists in this package:
`domain.expand_domain`'s Domain -> Discipline -> Function -> Technique
expansion path (see pipeline.py's stage 7, `_domain_stage`, and
`DomainExpansion.expansion_path`).

What a "trajectory" is here: each step of the expansion path (domain ->
discipline, discipline -> function, function -> technique) becomes one
`tcta_engine.core.Transform`, carrying the domain label forward in its
result state unchanged. A length-3 `Trajectory` is the full path; a
length-1 or length-2 prefix is a partial expansion.

What Gamma is here: the domain label carried on the trajectory's result
state. This is deliberately the SIMPLEST invariant available in
`expand_domain`'s own output -- the domain is fixed before discipline,
function, or technique are chosen (see `expand_domain`'s body: `ontology =
_DOMAIN_ONTOLOGY.get(domain, ...)` runs once, before any of the three
narrowing selections). Honesty note, same bar as the rest of this
package's modules: because Gamma reads a field that this construction
holds fixed across every step, prefix stability (H1) holds for this Gamma
BY CONSTRUCTION, for any domain-expansion trajectory built the way this
module builds them. That is not evidence that invariant projection "works"
for NYCH in general -- it is a true but narrow fact about this one,
deliberately simple Gamma. A richer Gamma (one that also tracks e.g.
subdomain or specialty, which COULD vary independently of domain) would
need its own H1 evidence, not inherit this one's.

What Psi is here: resolving Gamma's domain-label signature to one of the
domain families `domain.get_domain_ontology()` actually defines. Given a
signature and a set of candidate family labels, Psi picks the matching
label if present, or discloses `None` (unresolved) rather than guessing --
same disclosed-uncertainty convention as `competency.classify_domain` and
`tote_lookup.lookup_loop`'s fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .domain import DomainExpansion, get_domain_ontology

try:
    # tcta_engine is an optional dependency (see pyproject.toml): the
    # Trajectory type alias and Transform dataclass this module builds
    # against. Imported lazily/guarded so this module can still be read
    # and its pure-Python helpers used without tcta_engine installed;
    # build_expansion_trajectory and the H1/H2 demonstrations need it.
    from tcta_engine.core import Transform, Trajectory
except ImportError:  # pragma: no cover - exercised only without the dep
    Transform = None  # type: ignore[assignment]
    Trajectory = list  # type: ignore[assignment]


@dataclass(frozen=True)
class GammaSignature:
    """Gamma's output for a domain-expansion trajectory: just the domain
    label, carried as a 1-tuple so it is hashable/comparable like any other
    signature a GammaOperator might return (transform_algebra_axioms_v1.md
    SS6 requires only that Gamma's output support equality comparison)."""

    domain: str


def build_expansion_trajectory(expansion: DomainExpansion) -> "Trajectory":
    """Builds a length-3 `tcta_engine.core.Trajectory` from one
    `DomainExpansion`'s path: domain -> discipline -> function -> technique.

    Each `Transform.apply` ignores its input state and returns the next
    fixed waypoint `{"level": ..., "value": ..., "domain": expansion.domain}`
    -- these are not live, re-runnable functions, they are a replay of an
    already-computed expansion path (the same kind of wrapping
    tcta_bridge.py uses for `CandidateTransform`, which also carries
    pre-computed input/output states rather than a callable).
    """
    if Transform is None:  # pragma: no cover
        raise ImportError(
            "tcta_engine is required to build a Trajectory; install it "
            "(see pyproject.toml's tcta-engine dependency)"
        )
    domain = expansion.domain
    waypoints = [
        ("discipline", expansion.discipline),
        ("function", expansion.function),
        ("technique", expansion.technique),
    ]
    transforms = []
    for level, value in waypoints:
        result = {"level": level, "value": value, "domain": domain}
        transforms.append(
            Transform(transform_id=f"{domain}.{level}.{value}", apply=lambda _s, r=result: r)
        )
    return transforms


def gamma_domain_signature(trajectory: "Trajectory") -> GammaSignature:
    """GammaOperator: the domain label carried by the trajectory's LAST
    transform's result state (any step would do -- see module docstring on
    why this is invariant by construction for trajectories this module
    builds). Raises ValueError on an empty trajectory, same as asking for
    an invariant of nothing."""
    if not trajectory:
        raise ValueError("cannot project Gamma over an empty trajectory")
    last_result = trajectory[-1].apply(None)
    return GammaSignature(domain=last_result["domain"])


def psi_resolve_family(
    signature: GammaSignature,
    candidate_families: Iterable[str],
) -> Optional[str]:
    """PsiOperator: resolves `signature` to one of `candidate_families`
    (expected to be domain labels, e.g. from
    `domain.get_domain_ontology().keys()`, or any caller-chosen subset of
    them). Returns the matching label, or `None` -- disclosed unresolved,
    never a guessed default -- when `signature.domain` is not among the
    candidates."""
    candidates = list(candidate_families)
    if signature.domain in candidates:
        return signature.domain
    return None


def known_domain_families() -> list[str]:
    """Convenience: the domain labels Psi can ever resolve to, per the
    canonical ontology `domain.get_domain_ontology()` defines right now."""
    return [d for d in get_domain_ontology() if d != "unknown"]
