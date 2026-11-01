"""
gestalt_handoff.py -- the deterministic/LLM boundary of the NYCH pipeline.

Pipeline, per the NYCH design:

    USER -> natural-language input -> NYCH encoder (deterministic, this
    package) -> ... -> Gestalt mapping (LLM discretion) -> MG8 engine

Everything up to Gestalt mapping is pre-LLM: the state representation
(state_roles.tag_roles), the relational tense, the action, the domain and
subdomain, the vernacular competency (competency.analyze_utterance), the
TOTE-loop lookup (tote_lookup.lookup_loop). All of that is extracted FIRST,
before any word is Gestalt-mapped to any symbol.

At Gestalt mapping, discretion is deferred to an LLM, because there aren't
enough symbols to handle all of English. The rules handed over with that
discretion:

    1. map by most obvious visual match;
    2. embed the word sans vowels and doubled consonants into the id
       string as a disambiguation clue (skeleton.py);
    3. the four modality operators are invariant -- never remapped, and
       their glyphs never assigned to another word;
    4. once a word is mapped this session it is pinned #temp-invariant
       (session_invariants.py) and reused, never re-decided;
    5. chunk/compress whatever of the deterministic findings can be
       compressed before rendering symbol matches;
    6. scientific names, names of people, and prescription drug names are
       NOT rendered into Gestalt -- they pass through literally
       (protected_terms.py), with no glyph, skeleton id, or session pin.

This module builds that handoff package. It does NOT call an LLM -- nych
stays deterministic end to end; the caller (e.g. mg8-engine's gate loop)
owns the LLM boundary and passes this package as the prompt context.

Honesty note: `build_handoff` reports exactly what the deterministic side
found, including UNRESOLVED domains, None roles, and TOTE fallbacks. Words
already pinned this session appear under "pinned", not "needs_mapping" --
nothing already decided is re-opened.
"""

from __future__ import annotations

import re
from pathlib import Path

from .competency import analyze_utterance
from .protected_terms import protected_positions
from .session_invariants import MODALITY_OPERATORS, SessionInvariants
from .skeleton import describe
from .state_roles import tag_roles
from .tote_lookup import lookup_loop

# The standing discretionary instruction handed to the LLM alongside the
# findings. Kept as data so callers can render it into their own prompts.
DISCRETION_RULES = [
    "Chunk and compress any deterministic findings that can be compressed "
    "before rendering symbol matches.",
    "Map each word needing a symbol by the most obvious visual match.",
    "Embed the provided consonant skeleton (word sans vowels and doubled "
    "consonants) into the chosen symbol's id string as a disambiguation "
    "clue.",
    "The four modality operators are invariant: they are never remapped, "
    "and their glyphs are never assigned to any other word.",
    "A word already pinned #temp-invariant this session keeps its existing "
    "mapping; do not re-decide it.",
    "Scientific names, names of people, and prescription drug names are "
    "NOT rendered into Gestalt symbols: pass them through literally, with "
    "no glyph, no skeleton id, and no session pin.",
]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "my", "our", "their", "this", "that", "these", "those", "it", "its",
}


def _mapping_words(roles: dict, protected: dict[int, dict] | None = None) -> list[str]:
    """Content words from the tagged roles, in sentence order, that are
    candidates for Gestalt mapping: action, enumerator, object span,
    tense marker, state span. Stopwords and protected-term positions
    excluded, order preserved."""
    protected = protected or {}
    picks: list[tuple[int, str]] = []
    for role in ("action", "enumerator", "tense"):
        r = roles.get(role)
        if r:
            picks.append((r["position"], r["word"]))
    for role in ("object", "state"):
        r = roles.get(role)
        if r:
            for offset, word in enumerate(r["word"].split()):
                picks.append((r["start"] + offset, word))
    seen: set[str] = set()
    out: list[str] = []
    for position, word in sorted(picks):
        if position in protected:
            continue
        core = re.sub(r"[^a-z']", "", word.lower())
        if core and core not in _STOPWORDS and core not in seen:
            seen.add(core)
            out.append(word)
    return out


def build_handoff(text: str, *, db_path: str | Path | None = None,
                  session: SessionInvariants | None = None,
                  subdomain: str | None = None) -> dict:
    """Run the full deterministic pre-LLM pipeline over `text` and package
    the result for the discretionary Gestalt-mapping step.

    Returns a dict with: the raw findings (roles, analysis, tote), the
    invariant operator table, the discretion rules, the words still
    needing a mapping (each with its consonant-skeleton clue), and the
    words already pinned this session."""
    roles = tag_roles(text)
    analysis = analyze_utterance(text)

    tote = None
    if db_path is not None:
        tote = lookup_loop(
            roles, db_path,
            domain=analysis["domain"] if analysis["domain"] != "UNRESOLVED" else None,
            subdomain=subdomain,
        )

    protected = protected_positions(text)

    session = session or SessionInvariants()
    needs_mapping = []
    pinned = []
    for word in _mapping_words(roles, protected):
        pin = session.lookup(word)
        if pin is not None:
            pinned.append(pin)
        else:
            needs_mapping.append(describe(word))

    return {
        "text": text,
        "roles": roles,
        "analysis": analysis,
        "tote": tote,
        "modality_operators": dict(MODALITY_OPERATORS),
        "discretion_rules": list(DISCRETION_RULES),
        "needs_mapping": needs_mapping,
        "pinned": pinned,
        "protected": [dict(r, render="literal") for r in protected.values()],
    }
