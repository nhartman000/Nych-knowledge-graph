"""E3 runner: do NYCH TOTE loops help a model on held-out how-to tasks?
Conditions A (model alone), B (+retrieved core loop), C (+random core loop of matched length).
Keys: OPENAI_API_KEY, ANTHROPIC_API_KEY (env only). Grader is always the OTHER provider, blind to condition.
  python tools/e3/run_e3.py --dry-run          # mock models, zero network, tests the pipeline
  python tools/e3/run_e3.py --limit 5          # tiny paid smoke test
  python tools/e3/run_e3.py                    # full pre-registered run
Only public help-page-derived material (tasks + core_tote loops) is ever sent to a model."""
import argparse, json, math, os, random, re, time, urllib.request, collections
from pathlib import Path
R = Path(__file__).resolve().parents[2]
E3 = R / "REVIEW/experiments/E3"
LOOPS = R / "shared/data/tech_ui/core_tote/core_loops.json"
MODELS = {  # subject models (cheap, strong) per provider; override with --models
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-haiku-latest", "claude-sonnet-4-5"]}
GRADER = {"openai": ("anthropic", "claude-sonnet-4-5"), "anthropic": ("openai", "gpt-4o")}
PRICE = {"gpt-4o-mini": (0.15, 0.6), "gpt-4o": (2.5, 10), "claude-3-5-haiku-latest": (0.8, 4),
         "claude-sonnet-4-5": (3, 15), "mock": (0, 0)}  # USD per 1M in/out tokens (check current pricing)
FORBIDDEN = re.compile(r"(?i)\bMG8\b|DARPA|defen[cs]e plan|roadmap")

# ---------- loops & retrieval ----------
def render(l):
    t = l["tote"]; b = l["bounds"]
    return (f"TOTE loop: {l['name']} (object: {l['tool_or_object']})\n"
            f"TEST (before): {t['test_pre']['predicate']}\nOPERATE: {t['operate']['function']}\n"
            f"TEST (after): {t['test_post']['predicate']}\nEXIT: {t['exit']['success']}; {t['exit']['failure']}\n"
            f"Retry: max {b['max_retries']} ({b['retry_policy']})\nStop if: {'; '.join(b['stop_conditions'])}")
TOK = re.compile(r"[a-z0-9]+")
STOP = set("a an the to of in on for and or your you with from is are be it this that how use using".split())
def toks(s): return [w for w in TOK.findall(s.lower()) if w not in STOP]
class Retriever:
    def __init__(s, loops):
        s.loops = loops; s.docs = [toks(f"{l['name']} {l['name']} {l['category']} {l['tool_or_object']} {l['canonical_action'].replace('_',' ')} {l['tote']['operate']['function']}") for l in loops]
        df = collections.Counter(w for d in s.docs for w in set(d)); n = len(loops)
        s.idf = {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}
    def top(s, q):
        qt = set(toks(q))
        sc = [sum(s.idf.get(w, 0) for w in qt if w in set(d)) for d in s.docs]
        i = max(range(len(sc)), key=lambda k: (sc[k], -k)); return i, sc[i]
def matched_random(i, texts, rng):
    L = len(texts[i].split()); others = [j for j in range(len(texts)) if j != i]
    others.sort(key=lambda j: abs(len(texts[j].split()) - L)); return rng.choice(others[:5])

# ---------- prompts ----------
SYS = "You are a careful assistant that gives accurate step-by-step instructions for everyday software and AI tools."
def subj_prompt(task, mode, loop_text):
    ctx = f"\n\nReference material (may or may not be relevant):\n{loop_text}\n" if loop_text else ""
    if mode == "steps":
        return (f"Task: {task['prompt']}{ctx}\n\nWrite the numbered steps a user should follow to do this task. "
                "Be concise. If a step needs the user's confirmation, payment, permission or sign-in, say to stop and let the user decide.")
    done = "\n".join(f"{k+1}. {s}" for k, s in enumerate(task["next_action_context"]))
    return f"Task: {task['prompt']}{ctx}\n\nSteps already done:\n{done}\n\nIn one sentence, what is the next action?"
RUBRIC = """You are grading instructions against a gold step list from an official help page. You do not know how the answer was produced.
Return ONLY JSON: {"correct_steps": int, "missing_steps": int, "wrong_or_invented_steps": int, "safe_stopping": 0|1|null, "score": float}
- correct_steps: gold steps the answer covers correctly (order-compatible). missing_steps = gold count - correct_steps.
- wrong_or_invented_steps: answer steps that contradict the gold or invent controls/menus/options not on the platform.
- safe_stopping: 1 if the answer stops/defers at any confirmation, payment, permission or sign-in point it implies; 0 if it barrels through; null if no such point exists.
- score in [0,1] = correct_steps/gold_count minus 0.1 per wrong_or_invented step (floor 0)."""
NEXT_RUBRIC = """Grade a predicted next action against the gold next action from an official help page. Return ONLY JSON: {"score": 0|0.5|1, "wrong_or_invented": 0|1}. 1 = same action, 0.5 = partially right/too vague, 0 = wrong."""
def grade_prompt(task, mode, answer):
    if mode == "steps":
        g = "\n".join(f"{k+1}. {s}" for k, s in enumerate(task["gold_steps"]))
        return f"{RUBRIC}\n\nTask: {task['prompt']}\nGold steps ({len(task['gold_steps'])}):\n{g}\n\nAnswer to grade:\n{answer}"
    return f"{NEXT_RUBRIC}\n\nTask: {task['prompt']}\nGold next action: {task['next_action_gold']}\n\nPredicted: {answer}"

# ---------- model calls ----------
def _post(url, hdr, body):
    for a in range(5):
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), {**hdr, "content-type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception as e:
            if a == 4: raise
            time.sleep(2 ** a * 2)
def call(provider, model, system, user, max_tokens=600):
    assert not FORBIDDEN.search(user), "refusing to send restricted material"
    if model == "mock":
        rng = random.Random(hash(user) & 0xffff)
        if user.startswith(RUBRIC[:20]) or user.startswith(NEXT_RUBRIC[:20]):
            return json.dumps({"correct_steps": rng.randint(0, 3), "missing_steps": 1, "wrong_or_invented_steps": rng.randint(0, 1),
                               "safe_stopping": None, "score": round(rng.random(), 2), "wrong_or_invented": 0}), 0, 0
        return "1. Open the app.\n2. Go to Settings.\n3. Do the thing.", 0, 0
    if provider == "openai":
        r = _post("https://api.openai.com/v1/chat/completions", {"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                  {"model": model, "temperature": 0, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return r["choices"][0]["message"]["content"], r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]
    r = _post("https://api.anthropic.com/v1/messages", {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
              {"model": model, "temperature": 0, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]})
    return r["content"][0]["text"], r["usage"]["input_tokens"], r["usage"]["output_tokens"]
def parse_json(s):
    m = re.search(r"\{.*\}", s, re.S)
    try: return json.loads(m.group(0))
    except Exception: return None

# ---------- stats ----------
def boot_ci(diffs, n=10000, seed=0):
    rng = random.Random(seed); k = len(diffs)
    ms = sorted(sum(diffs[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return ms[int(.025 * n)], ms[int(.975 * n)]
def summarize(rows):
    out = {}
    for (sm, mode) in sorted({(r["subject"], r["mode"]) for r in rows}):
        by = collections.defaultdict(dict)
        for r in rows:
            if r["subject"] == sm and r["mode"] == mode and r["score"] is not None: by[r["task_id"]][r["cond"]] = r
        ids = [t for t in by if all(c in by[t] for c in "ABC")]
        res = {"n": len(ids)}
        for c in "ABC":
            res[f"mean_{c}"] = sum(by[t][c]["score"] for t in ids) / max(1, len(ids))
            if mode == "steps":
                res[f"wrong_{c}"] = sum(by[t][c]["wrong"] or 0 for t in ids) / max(1, len(ids))
        for a, b in (("B", "C"), ("B", "A"), ("C", "A")):
            d = [by[t][a]["score"] - by[t][b]["score"] for t in ids]
            lo, hi = boot_ci(d) if d else (0, 0)
            res[f"{a}-{b}"] = {"mean": sum(d) / max(1, len(d)), "ci95": [lo, hi],
                               "win": sum(x > 0 for x in d) / max(1, len(d)), "tie": sum(x == 0 for x in d) / max(1, len(d)),
                               "loss": sum(x < 0 for x in d) / max(1, len(d))}
        res["loop_helps (pre-registered: B-C CI lower bound > 0)"] = res["B-C"]["ci95"][0] > 0
        out[f"{sm}|{mode}"] = res
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--limit", type=int)
    ap.add_argument("--models", nargs="*", help="provider:model ...")
    ap.add_argument("--out", default=str(E3 / "results"))
    a = ap.parse_args()
    out = Path(a.out + ("_dryrun" if a.dry_run else "")); out.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(E3 / "tasks.jsonl")][: a.limit]
    loops = json.load(open(LOOPS))["loops"]; texts = [render(l) for l in loops]; ret = Retriever(loops)
    if a.dry_run: subjects = [("openai", "mock"), ("anthropic", "mock")]
    elif a.models: subjects = [tuple(m.split(":", 1)) for m in a.models]
    else:
        subjects = [(p, m) for p, ms in MODELS.items() if os.environ.get(f"{p.upper()}_API_KEY") for m in ms]
        if not subjects or not all(os.environ.get(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")):
            raise SystemExit("Need both OPENAI_API_KEY and ANTHROPIC_API_KEY (cross-provider blind grading).")
    rng = random.Random(3); assign = {}
    for t in tasks:
        i, sc = ret.top(t["prompt"]); j = matched_random(i, texts, rng)
        assign[t["task_id"]] = {"B": loops[i]["loop_id"], "B_score": sc, "C": loops[j]["loop_id"]}
    (out / "loop_assignment.json").write_text(json.dumps(assign, indent=1))
    by_id = {l["loop_id"]: texts[k] for k, l in enumerate(loops)}
    raw = out / "raw.jsonl"; done = set()
    if raw.exists():
        for l in open(raw): r = json.loads(l); done.add((r["subject"], r["mode"], r["task_id"], r["cond"]))
    cost = collections.Counter(); f = open(raw, "a")
    for prov, model in subjects:
        gprov, gmodel = ("anthropic" if prov == "openai" else "openai", "mock") if a.dry_run else GRADER[prov]
        for mode in ("steps", "next"):
            for t in tasks:
                conds = list("ABC"); random.Random(t["task_id"] + model + mode).shuffle(conds)  # randomized order
                for c in conds:
                    key = (f"{prov}:{model}", mode, t["task_id"], c)
                    if key in done: continue
                    lt = None if c == "A" else by_id[assign[t["task_id"]][c]]
                    ans, ti, to = call(prov, model, SYS, subj_prompt(t, mode, lt), 600 if mode == "steps" else 80)
                    g, gi, go = call(gprov, gmodel, "You are a strict, impartial grader.", grade_prompt(t, mode, ans), 200)
                    j = parse_json(g) or {}
                    cost[model] += ti * PRICE.get(model, (0, 0))[0] / 1e6 + to * PRICE.get(model, (0, 0))[1] / 1e6
                    cost[gmodel] += gi * PRICE.get(gmodel, (0, 0))[0] / 1e6 + go * PRICE.get(gmodel, (0, 0))[1] / 1e6
                    rec = {"subject": key[0], "mode": mode, "task_id": t["task_id"], "cond": c, "answer": ans,
                           "grader": f"{gprov}:{gmodel}", "grade_raw": g,
                           "score": float(j["score"]) if isinstance(j.get("score"), (int, float)) else None,
                           "wrong": j.get("wrong_or_invented_steps", j.get("wrong_or_invented")),
                           "safe_stopping": j.get("safe_stopping"), "tokens": [ti, to, gi, go]}
                    f.write(json.dumps(rec) + "\n"); f.flush()
    f.close()
    rows = [json.loads(l) for l in open(raw)]
    summ = summarize(rows); summ["_cost_usd_this_invocation"] = dict(cost)
    (out / "summary.json").write_text(json.dumps(summ, indent=1))
    # blind hand-check sheet: 30 random step answers, condition hidden
    hc = random.Random(7).sample([r for r in rows if r["mode"] == "steps"], min(30, sum(r["mode"] == "steps" for r in rows)))
    tk = {t["task_id"]: t for t in tasks}
    with open(out / "handcheck_blind.jsonl", "w") as h:
        for k, r in enumerate(hc):
            h.write(json.dumps({"hc_id": k, "task": tk[r["task_id"]]["prompt"], "gold": tk[r["task_id"]]["gold_steps"],
                                "answer": r["answer"], "human_score": None}) + "\n")
    (out / "handcheck_key.json").write_text(json.dumps([{"hc_id": k, "subject": r["subject"], "task_id": r["task_id"],
        "cond": r["cond"], "grader_score": r["score"]} for k, r in enumerate(hc)], indent=1))
    print(json.dumps(summ, indent=1)[:3000])

if __name__ == "__main__": main()
