"""Pass 2 (independent of build.py's regex selection): resolve each curated quote to
a cached record, re-check it verbatim against the cached raw help page, enforce the
quote/locator/date rules and >=2 distinct sources, then emit CANONICAL-CANDIDATE loops.

Outputs shared/data/tech_ui/core_tote/core_loops.json and verify_report.json.
Raw cache dir: $NYCH_UI_RAW (default /workspace/nych-ui-actions/data/raw)."""
from __future__ import annotations
import gzip, hashlib, html, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import spec, curation  # noqa: E402
from build import SITES  # noqa: E402

RAW = Path(os.environ.get("NYCH_UI_RAW", "/workspace/nych-ui-actions/data/raw"))
OUT = ROOT / "shared/data/tech_ui/core_tote"
MAX_TOK = 25
STATUS = "CANONICAL-CANDIDATE"
AUTHORITY = ("declared-function-only: performs exactly the one operation named in `operate` when invoked; "
             "does not choose goals, act on anyone's behalf, chain to other loops, or extend its own bounds")
INVIS = dict.fromkeys(map(ord, "\u2060\u200b\u00ad\ufeff"), None)


def norm(t: str) -> str:
    t = html.unescape(t).translate(INVIS).replace("\u00a0", " ").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def page_text(path: Path) -> str:
    h = path.read_text(encoding="utf-8", errors="replace")
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    return norm(re.sub(r"<[^>]+>", " ", h))


def raw_index():
    idx = {}
    if RAW.is_dir():
        for f in RAW.glob("*/_index.jsonl"):
            for line in f.open(encoding="utf-8"):
                r = json.loads(line)
                idx[r["url"]] = (f.parent / r["file"], r.get("retrieved"))
    return idx


def records():
    for name in ("ui_actions.jsonl.gz", "ui_actions_unmapped.jsonl.gz"):
        with gzip.open(ROOT / "shared/data/tech_ui" / name, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("quote"):
                    yield r


def in_page(quote: str, text_nospace: str) -> bool:
    """Quote must occur verbatim in the page text, comparing with all whitespace removed
    (the extractor inserts spaces before punctuation, e.g. "Bookmark ." vs "Bookmark.")."""
    return norm(quote.replace("…", " ")).replace(" ", "") in text_nospace


def main():
    want = {(p[1] if isinstance(p, tuple) else p): None for v in curation.PICK.values() for p in v}
    by_prefix = {p: [] for p in want}
    npref = {p: norm(p) for p in want}
    for r in records():
        nq = norm(r["quote"])
        for p, np_ in npref.items():
            if nq.startswith(np_):
                by_prefix[p].append(r)
    idx, cache = raw_index(), {}
    loops, report = [], {"kept": [], "dropped": [], "raw_cache": str(RAW), "raw_cache_present": RAW.is_dir()}
    for s in spec.S:
        if s["id"] in curation.DROP:
            report["dropped"].append({"id": s["id"], "stage": "second-pass review", "reason": curation.DROP[s["id"]]})
            continue
        srcs, used, problems = [], set(), []
        for p in curation.PICK[s["id"]]:
            site_pin, p = p if isinstance(p, tuple) else (None, p)
            cands = [r for r in by_prefix[p] if r["url"] not in used and r["site"] in SITES[s["category"]]
                     and (site_pin is None or r["site"] == site_pin)]
            ok = None
            for r in cands:
                toks = len(r["quote"].replace("…", " ").split())
                if toks > MAX_TOK or "…" in r["quote"]:
                    continue
                raw_ok = None
                if r["url"] in idx:
                    fp, rdate = idx[r["url"]]
                    if fp not in cache:
                        cache[fp] = page_text(fp).replace(" ", "") if fp.exists() else ""
                    raw_ok = in_page(r["quote"], cache[fp])
                    if rdate and rdate != r["retrieved"]:
                        raw_ok = False
                if raw_ok is False:
                    continue
                ok = r
                break
            if ok is None:
                problems.append(f"quote not resolved/verified: {p[:60]!r}")
                continue
            used.add(ok["url"])
            srcs.append({"url": ok["url"], "retrieved": ok["retrieved"], "publisher_site": ok["site"],
                         "section": ok.get("section") or "", "step_no": ok.get("step_no"),
                         "quote": ok["quote"], "quote_tokens": len(ok["quote"].split()),
                         "raw_page_checked": ok["url"] in idx, "quote_found_in_raw_page": ok["url"] in idx,
                         "platform": ok.get("platform") or ""})
        if len(srcs) < 2:
            report["dropped"].append({"id": s["id"], "stage": "mechanical verification",
                                      "reason": "fewer than 2 verified official sources", "problems": problems})
            continue
        loops.append(make_loop(s, srcs))
        report["kept"].append({"id": s["id"], "n_sources": len(srcs), "problems": problems})
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {"schema": "nych3.core_tote/v1", "status_meaning": f"{STATUS}: authored + two-pass agent-checked; NOT verified by a human",
           "n_loops": len(loops), "loops": loops}
    (OUT / "core_loops.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    (OUT / "verify_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n")
    print(f"kept {len(loops)} dropped {len(report['dropped'])}")


def make_loop(s, srcs):
    r = s["max_retries"]
    return {
        "loop_id": f"TL-CORE-{s['id']}", "name": s["name"], "category": s["category"],
        "canonical_action": s["canonical_action"], "status": STATUS, "verified_by_human": False,
        "actor": {"kind": "declared_function", "authority": AUTHORITY, "acts_on_behalf_of": None,
                  "goal_seeking": False, "may_chain": False},
        "tote": {
            "test_pre": {"predicate": s["pre"], "operator": "👀²", "modality_operator": "OP-VE", "process_operator": "external_observe",
                         "on_false": "EXIT(not_applicable): do not operate"},
            "operate": {"function": s["op"], "operator": "🙌", "modality_operator": "OP-KE", "process_operator": "execute", "count": 1,
                        "intent_marker": "🧠🗯", "intent_modality_operator": "OP-IMG", "intent_process_operator": "operative_intent",
                        "intent_mapping_flag": "GAP-2: 🗯️ operative_intent has no exact 10-operator equivalent; 🧠🗯 used by marker convention"},
            "test_post": {"predicate": s["post"], "operator": "👀²", "modality_operator": "OP-VE", "process_operator": "external_observe",
                          "observation_window_s": {"min": 0, "max": 30, "kind": "authored range, not sourced"}},
            "exit": {"success": "EXIT(success) when test_post is observed true",
                     "failure": f"EXIT(failure) after {r + 1} attempt(s) with test_post false, or immediately on a failure signal",
                     "predicate": s["post"]},
        },
        "bounds": {"max_attempts": r + 1, "max_retries": r,
                   "retry_policy": ("retry only if test_pre still holds and test_post is false; re-run test_pre before each retry"
                                    if r else "no automatic retry: operation is non-idempotent or irreversible; report and stop"),
                   "failure_signals": s["fail"],
                   "stop_conditions": ["failure signal observed", "test_pre false", f"attempts == {r + 1}",
                                       "any prompt requiring a decision not declared in this loop (confirmation, payment, permission, sign-in)"],
                   "open_ended": False},
        "platform_variants": s["variants"],
        "platform_variants_status": "authored hint from general platform knowledge; not part of quoted grounding",
        "sources": srcs,
        "second_pass": {"grade": "partial" if s["id"] in curation.PARTIAL else "correct",
                        "note": curation.PARTIAL.get(s["id"], "all sources state this function directly"),
                        "grader": "authoring agent (not human)"},
    }


if __name__ == "__main__":
    main()
