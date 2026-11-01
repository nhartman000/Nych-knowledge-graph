"""
tote_lookup.py -- TOTE-loop database lookup over a state-role record.

This is the step the README has described as designed-but-not-implemented:
given the roles tagged by state_roles.tag_roles() (action/enumerator/object/
tense/state) plus an optional domain and subdomain, query the T.O.T.E-loops
SQLite database (https://github.com/nhartman000/T.O.T.E-loops, built there
by `python -m src.build_db` into data/tote_loops.sqlite3) for a matching
known function/loop. When nothing matches, fall back -- honestly and
explicitly -- to the raw state-role record.

Schema facts this module relies on (from T.O.T.E-loops/schema.sql):

    tote_loops(loop_id, name, domain, objective, initial_test,
               exit_predicate, max_iterations, epistemic_status)
    gestalts(gestalt_id, glyph, lexical_form, sense, route, ...)
    loop_gestalts(loop_id, gestalt_id, role)

Loop IDs are namespaced like "code.unit_test_repair" / "ai.output_gate";
the prefix before the first "." is treated as the subdomain key here.

Matching order (most to least specific, each disclosed as "match_method"):

    1. "gestalt-lexical" -- a gestalt lexical_form joined to the loop
       matches a word in the object span or the action lemma/word;
    2. "name"            -- a candidate word appears in the loop name;
    3. "objective"       -- a candidate word appears in the loop objective.

Within a method, loops matching more candidate words rank first; remaining
ties break on total candidate hits across all three fields (so a word that
also appears in the loop name outranks a gestalt-only hit), then on
loop_id for determinism. The database path is always
caller-supplied -- this package bundles no database and probes no sibling
repository paths.

Domain bridging: nych.competency uses labels like COMPUTER_SCIENCE while
T.O.T.E-loops uses labels like software-engineering. DOMAIN_MAP below is a
small, hand-built, disclosed translation table -- not an ontology claim. A
nych domain with no mapping simply does not constrain the query.

Candidate words also match under a naive plural rule (a trailing "s"/"es"
is stripped to produce extra candidates, so "suites" can match "suite").
That is the only normalization performed -- it is a disclosed heuristic,
not stemming.

Honesty note, same bar as the rest of this package: this is substring-free
word matching over small curated text fields, not retrieval or semantic
search. A record with no match comes back as {"matched": False,
"fallback": "state_roles", ...} carrying the raw roles -- never a forced
best guess. A missing or unreadable database is likewise a disclosed
fallback reason, not a masked error.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

# nych competency domain label -> list of T.O.T.E-loops `domain` values it
# may constrain to. Hand-built and deliberately small.
DOMAIN_MAP = {
    "COMPUTER_SCIENCE": [
        "software-engineering", "ai-governance", "ai-retrieval", "ai-agents",
        "multi-agent-ai", "ai-memory", "machine-learning",
    ],
}

# Words too common in these curated fields to be evidence of a match.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "my", "our", "their", "this", "that", "these", "those", "it", "its",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _candidate_words(roles: dict) -> list[str]:
    """Non-stopword match candidates from a tag_roles() record: the object
    span's words, then the action lemma and surface word. Order preserved,
    deduplicated."""
    out: list[str] = []
    obj = roles.get("object")
    if obj:
        out.extend(_words(obj["word"]))
    action = roles.get("action")
    if action:
        out.extend(_words(action.get("lemma") or ""))
        out.extend(_words(action["word"]))
    expanded: list[str] = []
    for w in out:
        expanded.append(w)
        # naive plural normalization, disclosed in the module docstring
        if w.endswith("es") and len(w) > 4:
            expanded.append(w[:-2])
        if w.endswith("s") and len(w) > 3:
            expanded.append(w[:-1])
    seen = set()
    result = []
    for w in expanded:
        if w not in seen and w not in _STOPWORDS:
            seen.add(w)
            result.append(w)
    return result


def _loop_rows(conn: sqlite3.Connection, domain: str | None,
               subdomain: str | None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM tote_loops"
    clauses, params = [], []
    tote_domains = DOMAIN_MAP.get(domain.upper(), []) if domain else []
    if tote_domains:
        clauses.append("domain IN (%s)" % ",".join("?" * len(tote_domains)))
        params.extend(tote_domains)
    if subdomain:
        clauses.append("loop_id LIKE ?")
        params.append(subdomain + ".%")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY loop_id"
    return list(conn.execute(sql, params))


def _loop_lexical_forms(conn: sqlite3.Connection, loop_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT g.lexical_form FROM gestalts g "
        "JOIN loop_gestalts lg USING (gestalt_id) "
        "WHERE lg.loop_id = ? ORDER BY g.gestalt_id",
        (loop_id,),
    )
    return [r[0] for r in rows]


def _fallback(roles: dict, reason: str) -> dict:
    return {
        "matched": False,
        "fallback": "state_roles",
        "reason": reason,
        "roles": roles,
    }


def lookup_loop(roles: dict, db_path: str | Path,
                domain: str | None = None,
                subdomain: str | None = None) -> dict:
    """Look up a known TOTE loop for a tag_roles() record.

    Returns, on a match:
        {"matched": True, "match_method": ..., "matched_words": [...],
         "loop": {<tote_loops row>, "gestalts": [lexical forms]},
         "roles": <raw record>}
    and on no match (or no usable database/candidates) the disclosed
    fallback: {"matched": False, "fallback": "state_roles",
    "reason": ..., "roles": <raw record>}.
    """
    path = Path(db_path)
    if not path.is_file():
        return _fallback(roles, f"database not found: {path}")

    candidates = _candidate_words(roles)
    if not candidates:
        return _fallback(roles, "no object/action words to match on")

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return _fallback(roles, f"database unreadable: {exc}")

    try:
        conn.row_factory = sqlite3.Row
        try:
            loops = _loop_rows(conn, domain, subdomain)
        except sqlite3.Error as exc:
            return _fallback(roles, f"query failed (schema mismatch?): {exc}")

        best = None  # (method_rank, -hit_count, loop_id, loop, method, hits)
        for row in loops:
            lexical = _loop_lexical_forms(conn, row["loop_id"])
            lexical_words = {w for lf in lexical for w in _words(lf)}
            name_words = set(_words(row["name"])) - _STOPWORDS
            objective_words = set(_words(row["objective"])) - _STOPWORDS

            all_words = lexical_words | name_words | objective_words
            total_hits = sum(1 for w in candidates if w in all_words)

            for rank, (method, field_words) in enumerate([
                ("gestalt-lexical", lexical_words),
                ("name", name_words),
                ("objective", objective_words),
            ]):
                hits = [w for w in candidates if w in field_words]
                if hits:
                    key = (rank, -len(hits), -total_hits, row["loop_id"])
                    if best is None or key < best[0]:
                        best = (key, row, method, hits, lexical)
                    break

        if best is None:
            return _fallback(roles, "no loop matched the object/action words")

        _, row, method, hits, lexical = best
        loop = dict(row)
        loop["gestalts"] = lexical
        return {
            "matched": True,
            "match_method": method,
            "matched_words": hits,
            "loop": loop,
            "roles": roles,
        }
    finally:
        conn.close()
