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
# Deviation 2026-11-03 (see E3_PREREG.md): Anthropic replaced by Gemini (no Anthropic key).
MODELS = {  # subject models (cheap, strong) per provider; override with --models
    "openai": ["gpt-4.1-mini", "gpt-4.1"],
    "gemini": ["gemini-3.5-flash-lite", "gemini-3.8-flash"]}
GRADER = {"openai": ("gemini", "gemini-3.8-flash"), "gemini": ("openai", "gpt-4.1")}
OTHER = {"openai": "gemini", "gemini": "openai"}
# USD per 1M in/out tokens, verified 2026-11-03 on platform.openai.com/docs/pricing and ai.google.dev pricing
# (Gemini output includes thinking tokens; gemini-3.8-flash promo price through 2026-12-31).
PRICE = {"gpt-4.1-mini": (0.4, 1.6), "gpt-4.1": (2.0, 8.0), "gemini-3.5-flash-lite": (0.3, 2.5),
         "gemini-3.8-flash": (0.75, 3.75), "mock": (0, 0)}
FREE_TIER_PRICE = {"gemini-3.5-flash-lite": (0, 0), "gemma-4-26b-a4b-it": (0, 0), "gemma-4-31b-it": (0, 0)}
# Deviation 2 (2026-11-03): Gemini-only, FREE TIER, zero spend. Grader differs from both subjects.
# 2b: free-tier Gemini 3.x flash models allow only ~20 requests/day/model -> subjects moved to Gemma 4 (same free API),
# grader = gemini-3.5-flash-lite (different model family from subjects), grading batched 3 answers/call.
FREE_SUBJECTS = [("gemini", "gemma-4-26b-a4b-it"), ("gemini", "gemma-4-31b-it")]
FREE_GRADER = ("gemini", "gemini-3.5-flash-lite")
FREE_ALLOW = {m for _, m in FREE_SUBJECTS} | {FREE_GRADER[1]}   # all "Free of charge" on the free tier (pricing page 2026-11-03)
CAP_USD = 20.0  # TOTAL across both providers incl. grading; enforced on a combined running total
def usd(model, ti, to): p = PRICE.get(model, (0, 0)); return ti * p[0] / 1e6 + to * p[1] / 1e6
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
def grade_batch_prompt(task, mode, labelled):
    """labelled: list of (label, answer). Answers are anonymized and shuffled; grader can't see condition."""
    body = "\n\n".join(f"### Answer {lab}\n{ans.strip()}" for lab, ans in labelled)
    labs = ", ".join(l for l, _ in labelled)
    if mode == "steps":
        g = "\n".join(f"{k+1}. {s}" for k, s in enumerate(task["gold_steps"]))
        head = RUBRIC.replace("Return ONLY JSON: {", "For EACH answer return ONLY a JSON object keyed by answer label, e.g. {\"X\": {").replace('"score": float}', '"score": float}, ...}')
        return (f"{head}\nGrade each answer independently against the gold; do not rank them against each other.\n\n"
                f"Task: {task['prompt']}\nGold steps ({len(task['gold_steps'])}):\n{g}\n\nAnswers to grade ({labs}):\n\n{body}")
    return (f"{NEXT_RUBRIC}\nReturn ONLY a JSON object keyed by answer label, e.g. {{\"X\": {{\"score\": 1, \"wrong_or_invented\": 0}}, ...}}. "
            f"Grade each independently.\n\nTask: {task['prompt']}\nGold next action: {task['next_action_gold']}\n\nPredictions ({labs}):\n\n{body}")
def grade_prompt(task, mode, answer):
    if mode == "steps":
        g = "\n".join(f"{k+1}. {s}" for k, s in enumerate(task["gold_steps"]))
        return f"{RUBRIC}\n\nTask: {task['prompt']}\nGold steps ({len(task['gold_steps'])}):\n{g}\n\nAnswer to grade:\n{answer}"
    return f"{NEXT_RUBRIC}\n\nTask: {task['prompt']}\nGold next action: {task['next_action_gold']}\n\nPredicted: {answer}"

# ---------- model calls ----------
class Stop(Exception):
    """Non-retryable: out of credit, daily quota, or any sign the call could be billed."""
LAST = collections.defaultdict(float); MIN_INTERVAL = {"gemini": 6.5, "openai": 0.0}  # free-tier throttle (~9 RPM/model)
def _post(url, hdr, body, prov="?", model="?"):
    for a in range(8):
        wait = MIN_INTERVAL.get(prov, 0) - (time.time() - LAST[model])
        if wait > 0: time.sleep(wait)
        LAST[model] = time.time()
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), {**hdr, "content-type": "application/json"})
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")
            if re.search(r"insufficient_quota|credit_balance|no credits|billing_not_active|PAYMENT", msg):
                raise Stop(f"{prov}:{model} out of credit / billing: {msg[:300]}")
            if e.code == 429:
                if prov == "gemini" and "free_tier" not in msg:
                    raise Stop(f"{prov}:{model} quota error not tagged free_tier (possible billed tier) -> stop: {msg[:300]}")
                with open(E3 / "quota_errors.log", "a") as qf: qf.write(time.strftime("%FT%T%z ") + model + " " + msg.replace("\n", " ") + "\n")
                try: det = json.loads(msg)["error"].get("details", [])
                except Exception: det = []
                qids = [v.get("quotaId", "") for d in det for v in d.get("violations", [])]
                delay = next((float(str(d.get("retryDelay", "60s")).rstrip("s")) for d in det if "RetryInfo" in d.get("@type", "")), 60.0)
                if any("PerDay" in q for q in qids) or (not qids and re.search(r"(?i)per ?day", msg)):
                    raise Stop(f"{prov}:{model} DAILY quota exhausted {qids}")
                if a >= 6: raise Stop(f"{prov}:{model} persistent per-minute rate limit {qids}")
                time.sleep(delay + 5); continue
            if e.code >= 500 and a < 7: time.sleep(min(300, 15 * 2 ** a)); continue   # 503 overload: transient, back off
            raise Stop(f"{prov}:{model} HTTP {e.code}: {msg[:300]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if a >= 5: raise Stop(f"{prov}:{model} network: {e}")
            time.sleep(2 ** a * 3)
    raise Stop("retries exhausted")
def call(provider, model, system, user, max_tokens=600):
    assert not FORBIDDEN.search(user), "refusing to send restricted material"
    if model == "mock":
        rng = random.Random(hash(user) & 0xffff)
        if "Answers to grade (" in user or "Predictions (" in user:
            return json.dumps({L: {"score": round(rng.random(), 2), "wrong_or_invented_steps": 0} for L in "XYZ"}), 0, 0
        if user.startswith(RUBRIC[:20]) or user.startswith(NEXT_RUBRIC[:20]):
            return json.dumps({"correct_steps": rng.randint(0, 3), "missing_steps": 1, "wrong_or_invented_steps": rng.randint(0, 1),
                               "safe_stopping": None, "score": round(rng.random(), 2), "wrong_or_invented": 0}), 0, 0
        return "1. Open the app.\n2. Go to Settings.\n3. Do the thing.", 0, 0
    if provider == "openai":
        r = _post("https://api.openai.com/v1/chat/completions", {"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                  {"model": model, "temperature": 0, "max_tokens": max_tokens,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, prov=provider, model=model)
        return r["choices"][0]["message"]["content"], r["usage"]["prompt_tokens"], r["usage"]["completion_tokens"]
    if provider == "gemini":
        r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                  {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                  {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                   "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens + 1024,
                                        **({} if model.startswith("gemma") else {"thinkingConfig": {"thinkingLevel": "low"}})}}, prov=provider, model=model)
        u = r.get("usageMetadata", {}); parts = r["candidates"][0].get("content", {}).get("parts", [])
        txt = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return txt, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
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

def _ledger(p, total, dry):
    if not dry: p.write_text(json.dumps({"total_usd": round(total, 4), "cap_usd": CAP_USD}, indent=1))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--limit", type=int)
    ap.add_argument("--models", nargs="*", help="provider:model ...")
    ap.add_argument("--only-subject", help="run one subject model (parallel worker); writes raw_<model>.jsonl")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--gemini-free", action="store_true", help="Deviation 2: Gemini free tier only, zero spend")
    ap.add_argument("--out", default=str(E3 / "results_v2b"))
    a = ap.parse_args()
    out = Path(a.out + ("_dryrun" if a.dry_run else "")); out.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(E3 / "tasks.jsonl")][: a.limit]
    loops = json.load(open(LOOPS))["loops"]; texts = [render(l) for l in loops]; ret = Retriever(loops)
    if a.dry_run: subjects = [("openai", "mock"), ("gemini", "mock")]
    elif a.gemini_free:
        PRICE.update(FREE_TIER_PRICE)   # verified free tier: paid-only model returned free_tier limit 0
        if not os.environ.get("GEMINI_API_KEY"): raise SystemExit("Need GEMINI_API_KEY")
        subjects = [x for x in FREE_SUBJECTS if not a.only_subject or x[1] == a.only_subject]
    elif a.models: subjects = [tuple(m.split(":", 1)) for m in a.models]
    else:
        subjects = [(p, m) for p, ms in MODELS.items() if os.environ.get(f"{p.upper()}_API_KEY") for m in ms]
        if not subjects or not all(os.environ.get(k) for k in ("OPENAI_API_KEY", "GEMINI_API_KEY")):
            raise SystemExit("Need both OPENAI_API_KEY and GEMINI_API_KEY (cross-provider blind grading).")
    rng = random.Random(3); assign = {}
    for t in tasks:
        i, sc = ret.top(t["prompt"]); j = matched_random(i, texts, rng)
        assign[t["task_id"]] = {"B": loops[i]["loop_id"], "B_score": sc, "C": loops[j]["loop_id"]}
    (out / "loop_assignment.json").write_text(json.dumps(assign, indent=1))
    by_id = {l["loop_id"]: texts[k] for k, l in enumerate(loops)}
    raw = out / (f"raw_{a.only_subject}.jsonl" if a.only_subject else "raw.jsonl"); done = set()
    for rf in out.glob("raw*.jsonl"):
        for l in open(rf): r = json.loads(l); done.add((r["subject"], r["mode"], r["task_id"], r["cond"]))
    if a.analyze_only: subjects = []
    cost = collections.Counter(); spent = 0.0
    ledger = R / "REVIEW/experiments/E3/cost_ledger.json"   # combined total across ALL runs (smoke + full)
    spent_prior = json.loads(ledger.read_text())["total_usd"] if ledger.exists() and not a.dry_run else 0.0
    f = open(raw, "a"); stop_reason = None
    try:
      for mode in ("steps", "next"):             # primary outcome first; balanced across subjects if cut short
        for t in tasks:
          for prov, model in subjects:
                if a.dry_run: gprov, gmodel = (OTHER[prov], "mock")
                elif a.gemini_free: gprov, gmodel = FREE_GRADER
                else: gprov, gmodel = GRADER[prov]
                if a.gemini_free: assert model in FREE_ALLOW and gmodel in FREE_ALLOW and gmodel != model
                conds = list("ABC"); random.Random(t["task_id"] + model + mode).shuffle(conds)  # randomized order
                todo = [c for c in conds if (f"{prov}:{model}", mode, t["task_id"], c) not in done]
                if not todo: continue
                worst = 3 * usd(model, 2500, 2000) + usd(gmodel, 6000, 3000)
                if spent_prior + spent + worst > CAP_USD:
                    raise Stop(f"COST CAP: stopping at ${spent_prior + spent:.2f} (cap ${CAP_USD})")
                ansd = {}
                for c in todo:
                    lt = None if c == "A" else by_id[assign[t["task_id"]][c]]
                    up = subj_prompt(t, mode, lt)
                    if model.startswith("gemma"): up = SYS + "\n\n" + up   # Gemma: no system instruction support
                    ans, ti, to = call(prov, model, SYS, up, 600 if mode == "steps" else 120)
                    ansd[c] = (ans, ti, to)
                labels = random.Random("lab" + t["task_id"] + model + mode).sample(["X", "Y", "Z"], len(todo))
                lab_of = dict(zip(todo, labels))
                order = sorted(todo, key=lambda c: lab_of[c])
                g, gi, go = call(gprov, gmodel, "You are a strict, impartial grader.",
                                 grade_batch_prompt(t, mode, [(lab_of[c], ansd[c][0]) for c in order]), 400)
                jj = parse_json(g) or {}
                for c in todo:
                    ans, ti, to = ansd[c]; j = jj.get(lab_of[c]) if isinstance(jj.get(lab_of[c]), dict) else {}
                    c1, c2 = usd(model, ti, to), usd(gmodel, gi, go) / len(todo); cost[model] += c1; cost[gmodel] += c2; spent += c1 + c2
                    rec = {"subject": f"{prov}:{model}", "mode": mode, "task_id": t["task_id"], "cond": c, "answer": ans,
                           "grader": f"{gprov}:{gmodel}", "grade_label": lab_of[c], "grade_raw": g,
                           "score": float(j["score"]) if isinstance(j.get("score"), (int, float)) else None,
                           "wrong": j.get("wrong_or_invented_steps", j.get("wrong_or_invented")),
                           "safe_stopping": j.get("safe_stopping"), "tokens": [ti, to, gi, go], "usd": c1 + c2,
                           "B_score": assign[t["task_id"]]["B_score"], "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
                    f.write(json.dumps(rec) + "\n")
                f.flush(); _ledger(ledger, spent_prior + spent, a.dry_run)
    except Stop as e:
        stop_reason = str(e); print("STOPPED:", stop_reason, flush=True)
    f.close(); _ledger(ledger, spent_prior + spent, a.dry_run)
    rows = [json.loads(l) for rf in sorted(out.glob("raw*.jsonl")) for l in open(rf)]
    summ = summarize(rows)
    med = sorted(v["B_score"] for v in assign.values())[len(assign) // 2]
    summ["_secondary_well_matched (B_score >= median %.2f)" % med] = summarize([r for r in rows if assign[r["task_id"]]["B_score"] >= med])
    summ["_unparseable_grades"] = sum(r["score"] is None for r in rows)
    summ["_cost_usd_this_invocation"] = dict(cost)
    summ["_stop_reason"] = stop_reason
    summ["_records_total"] = len(rows)
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
    if stop_reason: raise SystemExit(4 if "DAILY" in stop_reason else 3)

if __name__ == "__main__": main()
