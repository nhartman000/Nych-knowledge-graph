"""NYCH four-part TOTE rule (owner decision, N Hartman, 2026-11-03).

Exterior senses (👀, 👂👂, touch 🙌, 👃, 👅) are INPUT DATA, like a robot's sensor
stream. A sense never equals, and never asserts, the loop's action by itself.
"Look" etc. is a sub-action: a modality operator that is PART of a TOTE loop.

Every TOTE loop must have ALL FOUR of:
  1. >=1 modality operator   2. an actor   3. an action   4. a tool or object
Works on CORE loops (nych3.core_tote/v1) and on Kuzu/seed TOTELoop rows (*_cell columns).
"""
from __future__ import annotations

PARTS = ("modality_operator", "actor", "action", "tool_or_object")
MODALITY_IDS = {"OP-KI", "OP-KE", "OP-VE", "OP-VI", "OP-AI", "OP-AE", "OP-MEM", "OP-IMG", "OP-OLF", "OP-GUS"}
MODALITY_SYMBOLS = ("🫶", "🙌", "👀", "👁", "👂", "💭", "🧠", "👃", "👅")


def _cell(v) -> str:
    """'look,' -> 'look'; strip slot separators and whitespace."""
    return str(v or "").strip().strip(",").strip()


def _is_placeholder(v: str) -> bool:
    return v.startswith("<") and v.endswith(">")


def missing_parts(loop: dict, *, allow_placeholders: bool = True, modality_links=None) -> list[str]:
    """Return the missing parts (empty list == passes). `allow_placeholders=False` treats '<actor>' slots as missing."""
    def ok(v):
        v = _cell(v)
        return bool(v) and (allow_placeholders or not _is_placeholder(v))
    miss = []
    if "tote" in loop:  # CORE loop
        t = loop["tote"]
        mods = [s.get("modality_operator") for s in t.values() if isinstance(s, dict)]
        if not any(m in MODALITY_IDS for m in mods): miss.append("modality_operator")
        a = loop.get("actor") or {}
        if not ok(a.get("kind") if isinstance(a, dict) else a): miss.append("actor")
        if not (ok(loop.get("canonical_action")) and ok((t.get("operate") or {}).get("function"))): miss.append("action")
        if not ok(loop.get("tool_or_object")): miss.append("tool_or_object")
        return miss
    mc = _cell(loop.get("modality_cell"))
    if not (any(s in mc for s in MODALITY_SYMBOLS) or modality_links): miss.append("modality_operator")
    if not ok(loop.get("actor_cell")): miss.append("actor")
    if not (ok(loop.get("action_cell")) or ok(loop.get("action_lemma"))): miss.append("action")
    if not (ok(loop.get("object_cell")) or ok(loop.get("object_lemma"))): miss.append("tool_or_object")
    return miss


def check(loop: dict, **kw) -> None:
    m = missing_parts(loop, **kw)
    if m:
        raise ValueError(f"{loop.get('loop_id', '?')}: TOTE loop rejected, missing {', '.join(m)} "
                         "(needs >=1 modality operator, an actor, an action, and a tool or object)")


def operators_never_assert_action(seed_operators) -> list[str]:
    """Seed rows are [id, symbol, name, channel, may_assert_action]; all must be False."""
    return [op[0] for op in seed_operators if op[4] is not False]
