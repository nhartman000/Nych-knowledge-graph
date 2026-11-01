"""
skeleton.py -- consonant-skeleton disambiguation clues for Gestalt ids.

There aren't enough glyphs to cover all of English, so the discretionary
Gestalt-mapping step (performed by an LLM, outside this package) embeds a
compressed form of the source word into the chosen symbol's id string as a
disambiguation clue. The rule, as specified: the word sans vowels and
doubled consonants.

This module is the deterministic half of that rule. It never chooses a
glyph and never calls an LLM; it only computes the skeleton and formats the
id string an external mapper should embed it into.

Honesty note, same bar as the rest of this package: this is a mechanical
letter transform, not phonology. Words whose letters are all vowels (e.g.
"eau") produce an empty skeleton; `skeleton_id` then falls back -- disclosed
via the "skeleton_fallback" return field of `describe` -- to the plain
lowercase letters rather than inventing consonants.
"""

from __future__ import annotations

import re

VOWELS = set("aeiou")


def consonant_skeleton(word: str) -> str:
    """Lowercase `word`, keep letters only, collapse doubled letters as
    written in the word, then drop vowels ("pattern" -> "ptrn", "suites"
    -> "sts"). Doubling is judged on the original spelling, so "Re-ran"
    -> "rrn": its two r's were never adjacent in the word itself."""
    letters = re.sub(r"[^a-z]", "", word.lower())
    dedoubled: list[str] = []
    for ch in letters:
        if dedoubled and dedoubled[-1] == ch:
            continue
        dedoubled.append(ch)
    return "".join(ch for ch in dedoubled if ch not in VOWELS)


def skeleton_id(word: str, namespace: str = "gestalt") -> str:
    """Format the id string a Gestalt mapper should assign: the namespace
    plus the consonant skeleton ("gestalt.ptrn"). Falls back to the plain
    lowercase letters when the skeleton is empty (all-vowel words)."""
    skel = consonant_skeleton(word)
    if not skel:
        skel = re.sub(r"[^a-z]", "", word.lower())
    return f"{namespace}.{skel}" if skel else namespace


def describe(word: str, namespace: str = "gestalt") -> dict:
    """Full disclosed record for one word: the source word, its skeleton,
    the id to embed, and whether a fallback was needed."""
    skel = consonant_skeleton(word)
    return {
        "word": word,
        "skeleton": skel,
        "id": skeleton_id(word, namespace),
        "skeleton_fallback": skel == "",
    }
