"""Consonant skeleton (salvaged from nych/skeleton.py @57b81e9, rule unchanged):
lowercase, letters only, collapse adjacent repeated letters, drop vowels.
A clue embedded at the END of a Gestalt id -- never a key, never meaning.
Added in 3.0: collision detection over normalized (punctuation-free) words."""
from __future__ import annotations
import re
from collections import defaultdict

VOWELS = set("aeiou")


def consonant_skeleton(word: str) -> str:
    letters = re.sub(r"[^a-z]", "", word.lower())
    out: list[str] = []
    for ch in letters:
        if out and out[-1] == ch:
            continue
        out.append(ch)
    return "".join(c for c in out if c not in VOWELS) or re.sub(r"[^a-z]", "", word.lower())


def collisions(words) -> dict[str, list[str]]:
    """skeleton -> sorted distinct lowercase words, only where >1 word shares it."""
    by = defaultdict(set)
    for w in words:
        by[consonant_skeleton(w)].add(w.lower())
    return {k: sorted(v) for k, v in by.items() if len(v) > 1}
