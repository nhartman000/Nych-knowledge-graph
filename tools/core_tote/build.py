"""Pass 1: select grounding quotes for each CORE spec from the cached official
help-center extraction (shared/data/tech_ui/ui_actions*.jsonl.gz). Writes
shared/data/tech_ui/core_tote/candidates.json. Read-only on the Kuzu store."""
from __future__ import annotations
import gzip, json, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import spec  # noqa: E402

SITES = {
    "files": {"microsoft", "google_drive", "apple", "samsung", "google_android", "claude"},
    "text_editing": {"microsoft", "google_drive", "apple", "samsung", "google_mail", "google_android", "google_chrome", "claude"},
    "browser": {"google_chrome", "microsoft", "apple", "samsung"},
    "settings": {"microsoft", "samsung", "google_android", "apple"},
    "accounts": {"google_accounts", "microsoft", "apple", "samsung", "claude", "ms_copilot"},
    "messaging": {"google_mail", "microsoft", "samsung", "apple"},
    "ai_chat": {"claude", "google_gemini", "ms_copilot"},
}
MAX_TOK = 25
PER_LOOP = 3


def records():
    for name in ("ui_actions.jsonl.gz", "ui_actions_unmapped.jsonl.gz"):
        with gzip.open(ROOT / "shared/data/tech_ui" / name, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)


def score(s, r):
    q, sec = r["quote"].lower(), (r.get("section") or "").lower()
    if not all(re.search(p, q) for p in s["q"]):
        return None
    if not re.search(s["sec"], sec):                          # heading must be about this function
        return None
    sc = 0
    sc += 3 if any(v in q for v in s["v"]) else 0
    sc += 2 if r.get("step_no") not in ("", None) else 0      # numbered step
    sc += 1 if len(q.split()) <= 20 else 0
    sc -= 5 if "…" in r["quote"] else 0                       # prefer untruncated quotes
    return sc


def main():
    specs = spec.S
    best = defaultdict(list)
    for r in records():
        if not r.get("url") or not r.get("quote"):
            continue
        if len(r["quote"].replace("…", " ").split()) > MAX_TOK:
            continue
        for s in specs:
            if r["site"] not in SITES[s["category"]]:
                continue
            sc = score(s, r)
            if sc is not None:
                best[s["id"]].append((sc, r))
    out = []
    for s in specs:
        cands = sorted(best[s["id"]], key=lambda t: (-t[0], t[1]["url"], t[1]["id"]))
        seen, picked = set(), []
        for sc, r in cands:
            if r["url"] in seen or r["quote"] in seen:
                continue
            seen.update((r["url"], r["quote"]))
            picked.append(dict(url=r["url"], site=r["site"], retrieved=r["retrieved"], section=r.get("section") or "",
                               step=r.get("step_no"), quote=r["quote"], platform=r.get("platform"), score=sc))
            if len(picked) >= PER_LOOP + 3:  # extra spares for second pass
                break
        out.append(dict(id=s["id"], candidates=picked, n_pool=len(cands)))
    dst = ROOT / "shared/data/tech_ui/core_tote"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(sum(1 for o in out if len(o["candidates"]) >= 2), "/", len(out), "specs with >=2 candidate sources")


if __name__ == "__main__":
    main()
