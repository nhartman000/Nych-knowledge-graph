"""E3b builder (observe-and-assist reframe). Reads non-computer TOTE loops (Gutenberg cookery/woodworking/knitting/
ropework books) from the Kuzu store READ-ONLY (shared flock), rebuilds paragraph headings from the cached public-domain
HTML, and writes tasks with: sensor-style observation (no task name), SYNTHETIC person profile, rule-derived physical
requirements per step, rule-derived gold struggle steps + completion bucket. Deterministic (seed 31).
Run: flock -s /workspace/kg.ingest.lock env PYTHONPATH=shared /workspace/kgenv/bin/python tools/e3b/build_e3b.py"""
import json, random, re, collections, fcntl
from pathlib import Path
import kuzu
from nych3.harvest.source import paragraphs, sources
R = Path(__file__).resolve().parents[2]; OUT = R / "REVIEW/experiments/E3b"; OUT.mkdir(parents=True, exist_ok=True)
DOM = {"65061": "cooking", "71855": "woodworking", "26113": "knitting/crochet", "13510": "ropework"}
QUOTA = {"65061": 48, "71855": 16, "26113": 14, "13510": 10}
db = kuzu.Database(str(R / "shared/data/tote.kuzu"), read_only=True); c = kuzu.Connection(db)
rows = c.execute("""MATCH (l:TOTELoop)-[:SOURCED_FROM]->(s:SourceRef)
 WHERE l.domain IN ['cooking','craft.woodworking','craft.knitting','craft.ropework'] AND s.fallback_gutenberg_id <> ''
 RETURN l.loop_id,l.name,l.domain,l.modality_cell,l.actor_cell,l.action_cell,l.object_cell,l.action_lemma,l.object_lemma,
 l.techniques,l.termination_triggers,s.sent_key,s.sentence_text,s.fallback_gutenberg_id""").get_all()
K = "loop_id name domain modality actor action object action_lemma object_lemma techniques triggers sent_key sentence book".split()
rows = [dict(zip(K, r)) for r in rows]
def nych_ok(r):  # NYCH rule: modality operator, actor, action, tool/object all present
    return all(r[k] and "UNRESOLVED" not in r[k] and r[k].strip(" ,") for k in ("modality", "actor", "action", "object"))
loops = {}
for r in rows:
    L = loops.setdefault(r["loop_id"], {**{k: r[k] for k in K if k not in ("sent_key", "sentence", "book")}, "grounding": [], "nych_ok": nych_ok(r)})
    L["grounding"].append({"sent_key": r["sent_key"], "sentence": r["sentence"], "book": r["book"]})
para = collections.defaultdict(dict)   # (book, p) -> {s: (sentence, [loop_ids])}
for r in rows:
    b, p, s = r["sent_key"].split(":"); e = para[(r["book"], int(p[1:]))].setdefault(int(s[1:]), [r["sentence"], [], []])
    e[1].append(r["loop_id"]); e[2].append(r)
S = sources(); books = {str(b["gutenberg_id"]): b for b in S["books"]}
P = {g: paragraphs(open(R / f"shared/data/corpus/{g}.html").read(), books[g]) for g in DOM}
HEAD = re.compile(r"^(\d+\.\s*)?[A-Z][A-Za-z,'’\- ]{2,60}\.?$")
def heading(g, i):
    for j in range(i - 1, max(-1, i - 25), -1):
        t = P[g][j]["text"].strip()
        if re.match(r"^[\d½⅓¼⅔¾⅛]|^Fig\.", t): continue          # ingredient lines, figure captions
        if HEAD.match(t) and len(t.split()) <= 8 and not t.endswith(":"): return re.sub(r"^\d+\.\s*|\.$", "", t).strip()
        if len(t.split()) > 12: return None
    return None
# ---- physical requirement rules (keyword -> requirement), documented in prereg ----
REQ = {"fine_motor": r"knit|purl|crochet|stitch|thread|needle|tie|splice|tuck|strand|loop|knot|mark|pencil|garnish|pick up|seam|button",
       "grip_force": r"plane|saw|chisel|beat|knead|whip|grate|pull (it )?(tight|taut)|haul|twist|wring|bore|screw|clamp|rub|stir constantly",
       "lifting_load": r"pour|lift|kettle|board|turn out|invert|carry|remove from (the )?(oven|fire)|drain|lumber|plank",
       "bimanual": r"hold|both hands|knit|purl|splice|clamp|tie|plane|saw|fold|roll",
       "heat_hazard": r"oven|boil|fry|fat|hot|bake|broil|saut|scald|simmer|fire|chafing|steam",
       "sharp_tool": r"knife|cut|chop|slice|saw|chisel|plane|carve|trim|pare|shave|knife",
       "fine_vision": r"count|measure|mark|stitch|row|thread|gauge|line|square|even|until .*(brown|clear|thick)",
       "sustained_standing": r"stir constantly|knead|beat .* minutes|plane|saw|for (ten|fifteen|twenty|thirty|\d+) minutes",
       "balance_reach": r"high|overhead|reach|shelf|ladder|stoop|bend|floor|bench"}
def reqs(s): s = s.lower(); return sorted(k for k, rx in REQ.items() if re.search(rx, s))
LIMIT = {"fine_motor": ["hand_tremor", "low_dexterity"], "grip_force": ["low_grip"], "lifting_load": ["low_lift"],
         "bimanual": ["one_hand_use"], "heat_hazard": ["reduced_heat_sense"], "sharp_tool": ["hand_tremor", "low_vision"],
         "fine_vision": ["low_vision"], "sustained_standing": ["low_standing_endurance"], "balance_reach": ["poor_balance", "short_reach"]}
def profile(rng, k):
    lim = rng.sample(["hand_tremor", "low_dexterity", "low_grip", "low_lift", "one_hand_use", "reduced_heat_sense", "low_vision",
                      "low_standing_endurance", "poor_balance", "short_reach"], rng.choice([0, 1, 1, 2, 2, 3]))
    h = rng.randint(150, 192)
    return {"profile_id": f"SYN-{k:03d}", "SYNTHETIC": True, "note": "synthetic profile, invented for testing; not a real person",
            "height_cm": h, "weight_kg": rng.randint(48, 105), "arm_reach_cm": int(h * 0.44) - (8 if "short_reach" in lim else 0),
            "grip_strength_kg": rng.randint(12, 20) if "low_grip" in lim else rng.randint(24, 48),
            "max_comfortable_lift_kg": rng.choice([2, 3]) if "low_lift" in lim else rng.choice([8, 12, 15]),
            "hand_tremor": "moderate" if "hand_tremor" in lim else "none", "finger_dexterity": "reduced" if "low_dexterity" in lim else "typical",
            "hands_available": 1 if "one_hand_use" in lim else 2, "heat_sensation_in_hands": "reduced" if "reduced_heat_sense" in lim else "typical",
            "near_vision": "low (no aid)" if "low_vision" in lim else "corrected/typical",
            "standing_tolerance_min": rng.choice([5, 8]) if "low_standing_endurance" in lim else rng.choice([30, 60]),
            "balance": "unsteady, uses cane" if "poor_balance" in lim else "steady",
            "gait": "slow, short stride" if "poor_balance" in lim else "typical", "posture_seen": rng.choice(["upright", "slight forward lean"]),
            "_limitations": lim}
def obs_of(steps_rows, n_seen):
    """Sensor-style observation of the first n_seen steps. Senses are INPUT data (what the system perceives), not actions."""
    out = []
    for k, rr in enumerate(steps_rows[:n_seen]):
        r = rr[0]; tool = re.search(r"tool: ([^,;]+)", r["object"] or ""); objs = sorted({x["object_lemma"] for x in rr if x["object_lemma"]})
        acts = sorted({x["action_lemma"] for x in rr})
        out.append(f"t{k+1}: hands perform motion consistent with [{', '.join(acts)}]; objects in view: {', '.join(objs) or 'unclear'}"
                   + (f"; tool in hand: {tool.group(1).strip()}" if tool else "") + f"; modality cues sensed: {r['modality']}")
    return out
def is_head(g, j):
    t = P[g][j]["text"].strip()
    if re.match(r"^[\d½⅓¼⅔¾⅛]|^Fig\.", t) and not re.match(r"^\d+\.\s+[A-Z]", t): return None
    return re.sub(r"^\d+\.\s*|\.$", "", t).strip() if HEAD.match(t) and len(t.split()) <= 8 and not t.endswith(":") else None
# A task = all harvested action sentences between one heading and the next (a section can span several paragraphs).
rng = random.Random(31); cands = collections.defaultdict(list); sect = collections.defaultdict(list)
for g in DOM:
    cur = None
    for j in range(len(P[g])):
        h = is_head(g, j)
        if h: cur = (j, h); continue
        if cur and (g, j) in para: sect[(g,) + cur].append(j)
for (g, hj, title), ps in sect.items():
    ss = [(p, s) for p in ps for s in sorted(para[(g, p)])]
    if not (3 <= len(ss) <= 8) or ps[-1] - hj > 12: continue
    steps = [para[(g, p)][s][0].strip() for p, s in ss]
    if any(len(x.split()) > 50 for x in steps) or len(set(steps)) < len(steps): continue
    okf = sum(any(loops[l]["nych_ok"] for l in para[(g, p)][s][1]) for p, s in ss) / len(ss)
    if okf < 2 / 3: continue
    cands[g].append({"book": g, "para": ps[0], "title": title, "steps": steps,
                     "own_loops": sorted({l for p, s in ss for l in para[(g, p)][s][1]}), "rows": [para[(g, p)][s][2] for p, s in ss]})
print({g: len(v) for g, v in cands.items()})
tasks = []
for g in DOM:
    pool = cands[g]; rng.shuffle(pool); seen = set()
    for t in pool:
        if sum(x["book"] == g for x in tasks) >= QUOTA[g] or t["title"].lower() in seen: continue
        seen.add(t["title"].lower()); tasks.append(t)
rng.shuffle(tasks)
out = []
for i, t in enumerate(tasks):
    pr = profile(rng, i); n_seen = max(1, len(t["steps"]) // 2)
    sreq = [reqs(s) for s in t["steps"]]
    gold_struggle = [k + 1 for k, rq in enumerate(sreq) if any(set(LIMIT[q]) & set(pr["_limitations"]) for q in rq)]
    frac = len(gold_struggle) / len(t["steps"])
    out.append({"task_id": f"E3b-{i:03d}", "domain": DOM[t["book"]], "source": f"Project Gutenberg #{t['book']} para {t['para']}",
                "title_hidden_from_model": t["title"], "gold_steps": t["steps"], "step_requirements": sreq,
                "observation": obs_of(t["rows"], n_seen), "n_steps_seen": n_seen, "profile": pr,
                "gold_struggle_steps": gold_struggle, "gold_completion_bucket": "high" if frac == 0 else ("medium" if frac <= .4 else "low"),
                "own_loops_heldout": t["own_loops"]})
# loop library for retrieval/random (non-computer, NYCH-complete only); grounding sentence carried for rendering
lib = [{k: v for k, v in L.items()} for L in loops.values() if L["nych_ok"]]
(OUT / "tasks.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))
(OUT / "loop_library.json").write_text(json.dumps(lib, ensure_ascii=False))
print(len(out), collections.Counter(x["domain"] for x in out), "library", len(lib),
      "struggle-free", sum(not x["gold_struggle_steps"] for x in out))
