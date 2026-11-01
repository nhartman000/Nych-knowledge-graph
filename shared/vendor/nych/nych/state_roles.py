"""
state_roles.py -- the pre-Gestalt "state representation" tagger.

This runs before any symbol encoding (semantic_encoding.py) and before
domain/competency classification is used for anything. It's the first-pass
parse: given a raw sentence, pull out which word or phrase plays which role
in a minimal state-representation schema:

    action      -- the operation/verb (e.g. "re-ran")
    enumerator  -- a quantifier over the object, if any (e.g. "both")
    object      -- what the action operates on (e.g. "test suites")
    tense       -- a relational-time marker, NOT grammatical tense
                   (e.g. "after", "before", "during") -- this says how the
                   state relates in time to something else, not whether the
                   verb is past/present/future
    state       -- the value the tense marker is relating to (e.g. "changes")

Worked example this module is built against: "Re-ran both test suites after
changes" -> action="Re-ran", enumerator="both", object="test suites",
tense="after", state="changes".

Once tagged, this record is meant to feed a TOTE-loop database lookup
(domain + subdomain + object/action -> a known function/loop) before
falling back to raw schema handling -- that lookup is NOT implemented here,
by design (see nych/README.md).

Honesty note, same bar as the rest of this package: this is a small,
hand-built heuristic tagger over word lists (a handful of enumerators, a
handful of relational-tense markers, a small irregular-verb table), not a
real dependency parser or POS tagger. It will misparse sentences that don't
fit its assumed shape. Every role that isn't found is reported as `None`,
never guessed.
"""

from __future__ import annotations
import re

from .semantic_encoding import _split

ENUMERATORS = {
    "both", "all", "some", "none", "each", "every", "several", "few",
    "many", "most", "any", "either", "neither",
}

# Relational-time markers: they place a state relative to another event or
# state ("after changes", "before the deploy"), which is distinct from a
# verb's own grammatical tense (the action word "re-ran" is past tense on
# its own regardless of whether a marker like this is present).
TENSE_MARKERS = {
    "after", "before", "during", "while", "since", "until", "when", "then",
    "once", "upon",
}

# Small irregular-verb table: base form -> the past-tense surface forms it
# should still be recognized under. Kept intentionally small; anything not
# listed here falls back to the -ed/-d suffix heuristic below.
IRREGULAR_VERBS = {
    "ran": "run", "reran": "rerun", "went": "go", "did": "do", "made": "make",
    "built": "build", "saw": "see", "sent": "send", "took": "take",
    "gave": "give", "wrote": "write", "read": "read", "broke": "break",
    "found": "find", "kept": "keep", "held": "hold", "left": "leave",
}

# Base-form verb lexicon for imperative and present-tense detection.
# Imperative sentences ("Add caching", "Fix the build") are the dominant
# shape of real commit messages, which the past-tense-only heuristic missed
# entirely. A word matches as an action if:
#   - it is at position 0 and is a base verb here (imperative), or
#   - anywhere, it is a base verb here + "s"/"es" (present 3rd person), or
#   - anywhere, it is the "-ing" form of a base verb here.
# Kept as an explicit list -- same honesty bar as IRREGULAR_VERBS: nothing
# outside it is guessed.
BASE_VERBS = {
    "add", "adjust", "allow", "avoid", "build", "bump", "cache", "change",
    "check", "clean", "close", "configure", "correct", "create", "debug",
    "decode", "delete", "deploy", "deprecate", "disable", "do", "document",
    "drop", "enable", "encode", "ensure", "expose", "extract", "fix",
    "format", "give", "go", "handle", "hide", "implement", "improve",
    "install", "keep", "lint", "log", "make", "merge", "migrate", "move",
    "open", "optimize", "parse", "prevent", "publish", "read", "refactor",
    "release", "remove", "rename", "replace", "restart", "revert", "run",
    "see", "send", "simplify", "split", "start", "stop", "support", "take",
    "test", "update", "upgrade", "use", "validate", "verify", "write",
}


def _base_candidates(lower: str) -> list[str]:
    """Expand a lowercased word with its "re-"/"re" prefix-stripped forms."""
    candidates = [lower]
    if lower.startswith("re-"):
        candidates.append(lower[3:])
    elif lower.startswith("re") and len(lower) > 2:
        candidates.append(lower[2:])
    return candidates


def _lemma_if_verblike(word: str, position: int = -1) -> str | None:
    """Returns a lemma if `word` looks like an action verb, else None.

    Recognizes past tense (irregular table + -ed/-ied heuristic),
    imperatives at sentence start (position 0 against BASE_VERBS),
    present 3rd person (-s/-es of a base verb), and progressive (-ing of a
    base verb). Handles a hyphenated or bare "re-" prefix ("re-ran",
    "reran", "re-run") by also checking with that prefix stripped.
    """
    lower = word.lower()
    candidates = _base_candidates(lower)

    for candidate in candidates:
        if candidate in IRREGULAR_VERBS:
            return IRREGULAR_VERBS[candidate]

    if lower.endswith("ied") and len(lower) > 4:
        return lower[:-3] + "y"
    if lower.endswith("ed") and len(lower) > 3:
        return lower[:-2]

    for candidate in candidates:
        # Imperative / bare base form, only trusted at sentence start.
        if position == 0 and candidate in BASE_VERBS:
            return candidate
        # Present 3rd person: "adds", "fixes".
        for suffix in ("es", "s"):
            if candidate.endswith(suffix) and candidate[:-len(suffix)] in BASE_VERBS:
                return candidate[:-len(suffix)]
        # Progressive: "adding", "running" (consonant doubling), "caching".
        if candidate.endswith("ing") and len(candidate) > 4:
            stem = candidate[:-3]
            for form in (stem, stem[:-1] if stem and stem[-1] == stem[-2:-1] else None,
                         stem + "e"):
                if form and form in BASE_VERBS:
                    return form
    return None


def tag_roles(sentence: str) -> dict:
    """Tag one sentence's action/enumerator/object/tense/state roles.

    Returns a dict with each role mapped to {"word": str, "position": int}
    or None if that role wasn't found. Also includes "tokens" (the raw
    whitespace-split tokens) so a caller can recover anything this schema
    doesn't name.
    """
    tokens = sentence.split()
    cores = [_split(t)[1] for t in tokens]

    action = None
    enumerator = None
    tense = None

    for i, core in enumerate(cores):
        if action is None:
            lemma = _lemma_if_verblike(core, position=i)
            if lemma:
                action = {"word": tokens[i], "position": i, "lemma": lemma}
        if enumerator is None and core.lower() in ENUMERATORS:
            enumerator = {"word": tokens[i], "position": i}
        if tense is None and core.lower() in TENSE_MARKERS:
            tense = {"word": tokens[i], "position": i}

    # object: the span between (action/enumerator, whichever is later) and
    # the tense marker, excluding both boundaries. Falls back to "everything
    # after the action" when no tense marker is present.
    obj = None
    start = max((r["position"] for r in (action, enumerator) if r), default=-1) + 1
    end = tense["position"] if tense else len(tokens)
    if start < end:
        span = tokens[start:end]
        if span:
            obj = {"word": " ".join(span), "start": start, "end": end}

    # state: whatever follows the tense marker -- the value the relational
    # tense is anchored to (e.g. "after [changes]").
    state = None
    if tense is not None and tense["position"] + 1 < len(tokens):
        span = tokens[tense["position"] + 1:]
        state = {"word": " ".join(span), "start": tense["position"] + 1, "end": len(tokens)}

    return {
        "sentence": sentence,
        "tokens": tokens,
        "action": action,
        "enumerator": enumerator,
        "object": obj,
        "tense": tense,
        "state": state,
    }
