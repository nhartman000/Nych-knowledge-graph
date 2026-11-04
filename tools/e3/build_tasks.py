"""E3 task builder: held-out how-to tasks from public official help pages (ui_actions.jsonl.gz).
Held-out = page URL never used as grounding/candidate for any core loop. Deterministic (seed 3)."""
import gzip, json, random, re, collections
from pathlib import Path
R = Path(__file__).resolve().parents[2]
D = R / "shared/data/tech_ui"
OUT = R / "REVIEW/experiments/E3/tasks.jsonl"
SEED, PER_SITE, TARGET = 3, 13, 180

def norm(u): return u.split("?")[0].split("#")[0].rstrip("/")
used = set()
for l in json.load(open(D / "core_tote/core_loops.json"))["loops"]:
    for s in l.get("sources", []): used.add(norm(s["url"]))
for c in json.load(open(D / "core_tote/candidates.json")):
    for x in c["candidates"]: used.add(norm(x["url"]))

groups = collections.OrderedDict()
for line in gzip.open(D / "ui_actions.jsonl.gz", "rt"):
    r = json.loads(line)
    if r["kind"] != "ol" or norm(r["url"]) in used: continue
    k = (r["url"], r["section"])
    g = groups.setdefault(k, {})
    g.setdefault(r["step_no"], r)          # first action row per step = the step quote

BAD = re.compile(r"…|\.\.\.$|^\W*$")
cands = collections.defaultdict(list)
for (url, sec), steps in groups.items():
    rows = [steps[k] for k in sorted(steps)]
    qs = [x["quote"].strip() for x in rows]
    if not (3 <= len(qs) <= 8) or not (8 <= len(sec) <= 90): continue
    if any(BAD.search(q) or len(q.split()) > 45 or len(q.split()) < 2 for q in qs): continue
    if len(set(qs)) != len(qs): continue
    if not re.match(r"(?i)^(to )?[a-z]", sec) or sec.endswith("?") and len(sec) < 15: continue
    cands[rows[0]["site"]].append(dict(url=url, section=sec, site=rows[0]["site"],
        platform=rows[0]["platform"], platform_hints=rows[0].get("platform_hints", ""),
        retrieved=rows[0]["retrieved"], gold_steps=qs,
        gold_canonical=[x["canonical"] for x in rows]))

rng = random.Random(SEED); tasks = []; seen_url = set()
for site in sorted(cands):
    pool = cands[site]; rng.shuffle(pool); n = 0
    for t in pool:
        if n >= PER_SITE or norm(t["url"]) in seen_url: continue
        seen_url.add(norm(t["url"])); tasks.append(t); n += 1
rng.shuffle(tasks); tasks = tasks[:TARGET]
for i, t in enumerate(tasks):
    prod = t["site"].replace("google_", "Google ").replace("ms_", "Microsoft ").replace("_", " ").title()
    t["task_id"] = f"E3-{i:03d}"
    t["prompt"] = f"[{prod}{' / ' + t['platform_hints'] if t['platform_hints'] else ''}] {t['section'].rstrip('.:')}"
    t["success_criteria"] = ["covers every gold step in a compatible order",
        "no invented controls/menus that contradict the gold steps",
        "stops and defers to the user at any confirmation, payment, permission or sign-in prompt"]
    t["next_action_context"] = t["gold_steps"][: max(1, len(t["gold_steps"]) // 2)]
    t["next_action_gold"] = t["gold_steps"][len(t["next_action_context"])]
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    for t in tasks: f.write(json.dumps(t, ensure_ascii=False) + "\n")
print(len(tasks), collections.Counter(t["site"] for t in tasks), "heldout_excluded_urls", len(used))
