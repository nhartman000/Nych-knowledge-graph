"""Compact loop notation shared by the gold set and the accuracy harness.

One sentence = loops separated by '||'; '-' = no loop expected.
loop:  action: obj1, obj2 [@prep head ...] [; mod 🙌,👀] [; exit TIER "text"] [; amt q1, q2] [; actor KIND]
  TIER = explicit | implied | inferred (inferred may be omitted); mod omitted = 🙌 only.
"""
from __future__ import annotations
import re

TIERS = {"explicit": "explicit", "implied": "implied_by_text", "implied_by_text": "implied_by_text", "inferred": "inferred"}
_PL = re.compile(r"(?:(?<=sh)|(?<=ch)|(?<=x)|(?<=z))es$|(?<=[a-z]{2})s$")


def norm(w: str) -> str:
    w = w.lower().strip(" ,.;:()").replace("(implied)", "")
    if w.endswith("ss") or w.endswith("us"):
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    return _PL.sub("", w)


def parse_loop(s: str) -> dict:
    parts = [p.strip() for p in s.split(";")]
    head = parts[0]
    act, _, rest = head.partition(":")
    locs = re.findall(r"@(\w+(?:\s+\w+)?)", rest)   # '@in pan'
    rest = re.sub(r"@\w+(?:\s+\w+)?", "", rest)
    lp = {"action": act.strip().lower(), "objects": [norm(o) for o in rest.split(",") if o.strip()],
          "locations": [norm(l.split()[-1]) for l in locs], "modality": ["🙌"], "exit_tier": "inferred", "exit": "",
          "amount": [], "actor": "you"}
    for p in parts[1:]:
        k, _, v = p.partition(" ")
        if k == "mod":
            lp["modality"] = [x.strip() for x in v.split(",") if x.strip()]
        elif k == "exit":
            t, _, txt = v.partition(" ")
            lp["exit_tier"] = TIERS[t]; lp["exit"] = txt.strip().strip('"')
        elif k == "amt":
            lp["amount"] = [x.strip() for x in v.split(",") if x.strip()]
        elif k == "actor":
            lp["actor"] = v.strip()
    return lp


def parse_sentence(s: str) -> list[dict]:
    s = s.strip()
    return [] if s in ("-", "") else [parse_loop(x) for x in s.split("||")]


_GLYPHS = re.compile(r"(🙌|👀²|👀|👁️|👂|🫶|👃|👅|🗣️|🗣|🧠🗯|💭|🤲|✋|👂²)")


def from_extracted(lp: dict) -> dict:
    """harvester loop dict -> compact dict (same keys as parse_loop)."""
    objs = [norm(o["lemma"]) for o in lp.get("objects", [])] + ([norm(lp["tool"]["lemma"])] if lp.get("tool") else [])
    locs = []
    for c in (lp["row"]["perspective_location"] or "").split(";"):
        c = c.strip().rstrip(",").replace("(?)", "")
        if c and c != "UNRESOLVED":
            locs.append(norm(c.split()[-1]))
    mods = []
    for cell in lp["row"]["modality"].split(";"):
        g = "".join(_GLYPHS.findall(cell.split(",", 1)[-1])) if "," in cell else ""
        if g:
            mods.append(g)
    mods += ["".join(_GLYPHS.findall(t["op"])) for t in lp.get("sense_tests", [])]
    ex = lp.get("exit")
    tier = ex.get("provenance", "explicit") if ex else "inferred"
    amt = [o["quantity"] for o in lp.get("objects", []) if o.get("quantity")]
    ak = "you" if lp["row"]["actor"].startswith("you") else lp["row"]["actor"].rstrip(",")
    return {"action": lp["lemma"].lower(), "objects": objs, "locations": locs, "modality": mods or ["🙌"],
            "exit_tier": tier, "exit": (ex or {}).get("text", ""), "amount": amt, "actor": ak,
            "prohibition": bool(lp.get("prohibition"))}


def to_compact(c: dict) -> str:
    s = f"{c['action']}: {', '.join(c['objects'])}" + "".join(f" @{l}" for l in c["locations"])
    if c["modality"] != ["🙌"]:
        s += f" ; mod {','.join(c['modality'])}"
    if c["exit_tier"] != "inferred":
        s += f" ; exit {'implied' if c['exit_tier'] == 'implied_by_text' else c['exit_tier']} \"{c['exit']}\""
    if c["amount"]:
        s += f" ; amt {', '.join(c['amount'])}"
    if c["actor"] != "you":
        s += f" ; actor {c['actor']}"
    return s
