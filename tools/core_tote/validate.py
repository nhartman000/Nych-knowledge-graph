"""Strict validator for shared/data/tech_ui/core_tote/core_loops.json (no network, no raw cache).
Exit code 1 and a list of errors if any loop violates the CORE contract."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "shared/data/tech_ui/core_tote/core_loops.json"
OFFICIAL = {"support.google.com", "support.microsoft.com", "support.claude.com", "www.samsung.com", "support.apple.com"}
MAX_RETRIES_CAP = 2


def errors(doc: dict) -> list[str]:
    errs, ids = [], set()
    for L in doc["loops"]:
        i = L.get("loop_id", "?")
        e = lambda m: errs.append(f"{i}: {m}")
        if i in ids: e("duplicate loop_id")
        ids.add(i)
        if L.get("status") != "CANONICAL-CANDIDATE": e("status must be CANONICAL-CANDIDATE")
        if L.get("verified_by_human") is not False: e("verified_by_human must be False")
        a = L.get("actor", {})
        if a.get("kind") != "declared_function" or a.get("goal_seeking") is not False or a.get("may_chain") is not False \
                or a.get("acts_on_behalf_of") is not None or "declared-function-only" not in a.get("authority", ""):
            e("actor/authority must declare a non-agentic declared function")
        t = L.get("tote", {})
        for k in ("test_pre", "operate", "test_post", "exit"):
            if k not in t: e(f"missing tote.{k}")
        if errs and errs[-1].startswith(f"{i}: missing"): continue
        if not t["test_pre"].get("predicate") or not t["test_post"].get("predicate"): e("empty pre/post predicate")
        if t["test_pre"].get("operator") != "👀²" or t["test_post"].get("operator") != "👀²": e("tests must be 👀² observations")
        if t["operate"].get("operator") != "🙌" or t["operate"].get("count") != 1: e("operate must be a single 🙌 operation")
        if t["exit"].get("predicate") != t["test_post"]["predicate"]: e("exit predicate must equal post-condition")
        w = t["test_post"].get("observation_window_s", {})
        if not (isinstance(w.get("min"), (int, float)) and isinstance(w.get("max"), (int, float)) and w["min"] <= w["max"]):
            e("observation window must be a range")
        b = L.get("bounds", {})
        r = b.get("max_retries")
        if not isinstance(r, int) or not 0 <= r <= MAX_RETRIES_CAP: e("max_retries must be int in [0,2]")
        elif b.get("max_attempts") != r + 1: e("max_attempts must equal max_retries+1")
        if b.get("open_ended") is not False: e("open_ended must be False")
        if not b.get("failure_signals") or not b.get("stop_conditions"): e("failure signals / stop conditions required")
        if not isinstance(L.get("platform_variants"), dict): e("platform_variants must be a dict")
        S = L.get("sources", [])
        if len({s["url"] for s in S}) < 2: e("needs >=2 distinct sources")
        for s in S:
            if urlparse(s["url"]).netloc not in OFFICIAL: e(f"non-official source {s['url']}")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s.get("retrieved", "")): e("bad retrieved date")
            q = s.get("quote", "")
            if not q or len(q.split()) > 25 or "…" in q: e(f"quote must be 1..25 tokens, untruncated: {q[:40]!r}")
            if s.get("quote_found_in_raw_page") is not True: e("quote not verified against cached page")
        if L.get("second_pass", {}).get("grade") not in ("correct", "partial"): e("second_pass grade missing")
    if doc.get("n_loops") != len(doc["loops"]): errs.append("n_loops mismatch")
    return errs


def main():
    errs = errors(json.loads(PATH.read_text()))
    for x in errs: print("ERROR", x)
    print(f"{len(errs)} errors")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
