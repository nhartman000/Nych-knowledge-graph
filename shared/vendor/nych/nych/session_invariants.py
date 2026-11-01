"""
session_invariants.py -- the "#temp-invariant" session memory for
discretionary Gestalt mappings.

Pipeline position (per the NYCH design): everything deterministic -- state
roles, domain/subdomain, vernacular competency, TOTE lookup -- runs first,
with no LLM. The Gestalt symbol assignment itself is handed to an LLM
(there aren't enough glyphs for all of English). Once that LLM commits to a
word -> symbol mapping within a conversation, the mapping is pinned as a
"#temp-invariant": stable for the rest of that session so the same word is
never re-mapped mid-conversation.

This module is that pin store, and only that. nych never makes the LLM
call; the caller (e.g. mg8-engine's gate loop) owns the LLM boundary and
the store's lifetime, and records pins into its own audit trail (.qson).

Two levels of invariance, deliberately distinct:

    PERMANENT  -- the four modality operators (external observation,
                  internal model, operative intention, execution). These
                  are invariant by rule, never session-pinned, never
                  overridable. Attempting to pin over one raises.
    #temp-invariant -- a session-scoped pin created the first time the LLM
                  maps a word. Re-pinning the same word to the same symbol
                  is a no-op; re-pinning to a different symbol raises
                  unless explicitly forced (force=True), and a forced
                  repin is recorded in the pin's history, not silently.

Honesty note, same bar as the rest of this package: this is a dict with
rules, not memory management magic. Persistence (save/load) is plain JSON
and only happens when the caller asks.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

# The invariant modality operators, mirroring T.O.T.E-loops'
# modality_operators table. These may never be remapped.
MODALITY_OPERATORS = {
    "external_observe": "👀",
    "internal_model": "👁️🧠",
    "operative_intent": "🗯️",
    "execute": "💪",
}

_OPERATOR_WORDS = set(MODALITY_OPERATORS) | set(MODALITY_OPERATORS.values())


class InvariantViolation(Exception):
    """Raised on an attempt to remap a permanent operator or to silently
    overwrite an existing #temp-invariant pin."""


class SessionInvariants:
    """Session-scoped #temp-invariant pin store for word -> symbol-id
    Gestalt mappings."""

    def __init__(self) -> None:
        self._pins: dict[str, dict] = {}

    @staticmethod
    def _key(word: str) -> str:
        return word.lower()

    def is_protected(self, word: str) -> bool:
        """True for the permanent modality operators (by id or glyph)."""
        return word in _OPERATOR_WORDS or self._key(word) in MODALITY_OPERATORS

    @staticmethod
    def is_operator_symbol(symbol_id: str) -> bool:
        """True when `symbol_id` contains any modality operator glyph.
        Operators are invariant in both directions: an operator is never
        remapped, and no other word may be given an operator's glyph."""
        # Strip emoji variation selectors so "🗯" and "🗯️" compare equal.
        def bare(s: str) -> str:
            return s.replace("️", "").replace("︎", "")
        sid = bare(str(symbol_id))
        return any(bare(glyph) in sid for glyph in MODALITY_OPERATORS.values())

    def pin(self, word: str, symbol_id: str, *, source: str = "llm",
            force: bool = False) -> dict:
        """Pin `word` -> `symbol_id` as a #temp-invariant.

        Idempotent for an identical repeat. Raises InvariantViolation when
        `word` is a permanent modality operator, or when it is already
        pinned to a different symbol and force is False. A forced repin
        appends the old value to the pin's "history"."""
        if self.is_protected(word):
            raise InvariantViolation(
                f"{word!r} is a permanent modality operator; it is never "
                "session-pinned or remapped"
            )
        if self.is_operator_symbol(symbol_id):
            raise InvariantViolation(
                f"{symbol_id!r} carries a permanent modality operator glyph; "
                f"assigning it to {word!r} would give the operator a second "
                "meaning"
            )
        key = self._key(word)
        existing = self._pins.get(key)
        if existing is not None:
            if existing["symbol_id"] == symbol_id:
                return existing
            if not force:
                raise InvariantViolation(
                    f"{word!r} already pinned to {existing['symbol_id']!r} "
                    f"this session (#temp-invariant); refusing silent remap "
                    f"to {symbol_id!r}"
                )
            history = existing.get("history", [])
            history.append({"symbol_id": existing["symbol_id"],
                            "source": existing["source"]})
            pin = {"word": word, "symbol_id": symbol_id, "source": source,
                   "tag": "#temp-invariant", "history": history}
            self._pins[key] = pin
            return pin
        pin = {"word": word, "symbol_id": symbol_id, "source": source,
               "tag": "#temp-invariant", "history": []}
        self._pins[key] = pin
        return pin

    def lookup(self, word: str) -> dict | None:
        """The pin for `word`, or the permanent operator record, or None.
        None means "not yet mapped this session" -- disclosed, not guessed."""
        if self.is_protected(word):
            key = self._key(word)
            op = key if key in MODALITY_OPERATORS else next(
                k for k, v in MODALITY_OPERATORS.items() if v == word)
            return {"word": word, "symbol_id": MODALITY_OPERATORS[op],
                    "source": "canon", "tag": "permanent-invariant",
                    "operator_id": op}
        return self._pins.get(self._key(word))

    def pinned_words(self) -> list[str]:
        return sorted(self._pins)

    def as_dict(self) -> dict:
        # Deep copy: callers mutating the snapshot must never alter live pins.
        return {"tag": "#temp-invariant", "pins": copy.deepcopy(self._pins)}

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "SessionInvariants":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls()
        for key, pin in dict(data.get("pins", {})).items():
            # A saved file is input like any other: the same invariance
            # rules apply on load, so a hand-edited file can't smuggle in
            # an operator remap or an operator glyph.
            if store.is_protected(pin.get("word", key)):
                raise InvariantViolation(
                    f"pin file remaps permanent operator {pin.get('word', key)!r}")
            if store.is_operator_symbol(pin.get("symbol_id", "")):
                raise InvariantViolation(
                    f"pin file assigns operator glyph {pin.get('symbol_id')!r} "
                    f"to {pin.get('word', key)!r}")
            store._pins[store._key(pin.get("word", key))] = copy.deepcopy(pin)
        return store
