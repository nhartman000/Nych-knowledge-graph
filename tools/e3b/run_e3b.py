"""E3b runner (PRELIMINARY): observe-and-assist test of NYCH TOTE loops on non-computer tasks. Gemini FREE tier only
(Gemma 4 subjects), $0. Scoring is fully rule-based (no LLM grader -> no grader quota, no grader bias).
Conditions: A no loop, B retrieved loops (own loops held out), C random non-computer loops (same count).
  python tools/e3b/run_e3b.py --dry-run | --gemini-free [--only-subject M] | --analyze-only"""
import argparse, json, math, os, random, re, collections, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e3"))
import run_e3 as E   # reuse free-tier call(), quota/billing stops, FORBIDDEN guard, bootstrap CI
R = Path(__file__).resolve().parents[2]; D = R / "REVIEW/experiments/E3b"
LEDGER = R / "REVIEW/experiments/E3/cost_ledger.json"   # shared combined ledger; free tier -> stays $0
E.MIN_INTERVAL["gemini"] = 12.0   # politer than E3 (6.5s): free quota is shared with the running E3 workers
_post0 = E._post
def _post_min_think(url, hdr, body, **kw):   # Gemma 4 default thinking ran ~3-4k tokens and returned empty text; use minimal
    if "gemma" in url: body.setdefault("generationConfig", {})["thinkingConfig"] = {"thinkingLevel": "minimal"}
    return _post0(url, hdr, body, **kw)
E._post = _post_min_think
K_LOOPS, N_CAND = 3, 20
STOP = set("a an the to of in on for and or with from is are be it this that until".split())
def cues(t):
    o = " ".join(t["observation"])
    acts = re.findall(r"\[([^\]]*)\]", o); objs = re.findall(r"objects in view: ([^;]*)", o); tools = re.findall(r"tool in hand: ([^;]*)", o)
    sp = lambda xs: {w.strip() for x in xs for w in x.split(",") if w.strip() and w.strip() != "unclear"}
    return sp(acts), sp(objs), sp(tools)
class Retriever:
    """Fix vs E3 (loose TF-IDF over loop names, top-1, no hold-out of near-duplicates): match on the loop's NYCH cells
    -- object lemma (x2), tool (x1.5), action lemma (x1), IDF-weighted -- an object or tool match is REQUIRED,
    only NYCH-complete loops, task's own loops held out, top-3 from 3 distinct source paragraphs, score logged."""
    def __init__(s, lib):
        s.lib = lib
        s.f = [(l["action_lemma"] or "", l["object_lemma"] or "", (re.search(r"tool: ([^,;]+)", l["object"] or "") or [None, ""])[1].strip()) for l in lib]
        df = collections.Counter(w for f in s.f for w in set(f) if w); n = len(lib)
        s.idf = {w: math.log((n + 1) / (c + .5)) for w, c in df.items()}
    def top(s, t, k=K_LOOPS):
        A, O, T = cues(t); held = set(t["own_loops_heldout"]); gold = set(t["gold_steps"]); sc = []
        for i, (a, o, tl) in enumerate(s.f):
            if s.lib[i]["loop_id"] in held: continue
            m_obj = o in O or o in T; m_tool = bool(tl) and (tl in T or tl in O)
            if not (m_obj or m_tool): continue
            v = 2 * s.idf.get(o, 0) * m_obj + 1.5 * s.idf.get(tl, 0) * m_tool + s.idf.get(a, 0) * (a in A)
            sc.append((v, i))
        sc.sort(key=lambda x: (-x[0], x[1])); out, used = [], set()
        for v, i in sc:
            g = next((x for x in s.lib[i]["grounding"] if x["sentence"] not in gold), None)
            if not g: continue
            para = g["sent_key"].rsplit(":", 1)[0]
            if para in used: continue
            used.add(para); out.append((i, v, g))
            if len(out) == k: break
        return out
def render(l, g):
    tech = json.loads(l["techniques"] or "[]"); trig = json.loads(l["triggers"] or "[]")
    return (f"TOTE loop {l['loop_id']}: {l['name']} [{l['domain']}]\n  actor: {l['actor']} | action: {l['action']} | object/tool: {l['object']}\n"
            f"  modality operators: {l['modality']}\n  exit: {'; '.join(str(x.get('trigger')) for x in trig)}"
            + (f"\n  notes: {'; '.join(x.get('note', x.get('text', '')) for x in tech if isinstance(x, dict))}" if tech else "")
            + f"\n  grounding (public-domain book): \"{g['sentence']}\"")
SYS = ("You assist a civilian assistive system (accessibility / elder-care help / ergonomics) that watches a person doing an everyday "
       "physical task and offers help. Sensor cues are input data. Any ability estimate is a hypothesis to guide offers of help, never a judgment of the person.")
def id_prompt(t, cands, ctx):
    c = "\n".join(f"{k+1}. {x}" for k, x in enumerate(cands))
    return (f"{SYS}\n\nObservation so far (sensor-style, task name not given):\n" + "\n".join(t["observation"]) + ctx +
            f"\n\nWhich task is the person most likely doing? Candidates:\n{c}\n\nReturn ONLY JSON: {{\"top5\": [candidate numbers, most likely first]}}")
def ab_prompt(t, ctx):
    p = {k: v for k, v in t["profile"].items() if not k.startswith("_")}
    st = "\n".join(f"{k+1}. {s}" for k, s in enumerate(t["gold_steps"]))
    return (f"{SYS}\n\nObservation so far:\n" + "\n".join(t["observation"]) + f"\n\nPerson profile (SYNTHETIC, invented for testing):\n{json.dumps(p)}"
            + ctx + f"\n\nThe system has matched this procedure:\n{st}\n\nConsidering only physical capability, which step numbers will this person "
            "likely struggle with or need help on, and how likely are they to finish unaided? Return ONLY JSON: "
            '{"struggle_steps": [ints], "completion_likelihood": "high"|"medium"|"low", "why": "short"}')
def pj(s):
    m = re.search(r"\{.*\}", s or "", re.S)
    try: return json.loads(m.group(0))
    except Exception: return None
def score_id(j, truth):
    try: r = [int(x) for x in j["top5"]][:5]
    except Exception: return None, None
    return float(r[:1] == [truth]), float(truth in r)
def score_ab(j, t):
    try: p = {int(x) for x in j["struggle_steps"]}; cl = str(j["completion_likelihood"]).lower()
    except Exception: return None
    g = set(t["gold_struggle_steps"])
    f1 = 1.0 if not p and not g else (2 * len(p & g) / (len(p) + len(g)))
    L = ["low", "medium", "high"]; cs = 1.0 if cl == t["gold_completion_bucket"] else (.5 if cl in L and abs(L.index(cl) - L.index(t["gold_completion_bucket"])) == 1 else 0.)
    return (f1 + cs) / 2
def candidates(t, tasks):
    rng = random.Random("cand" + t["task_id"]); same = [x["title_hidden_from_model"] for x in tasks if x["domain"] == t["domain"] and x is not t]
    other = [x["title_hidden_from_model"] for x in tasks if x["domain"] != t["domain"]]
    c = rng.sample(same, min(9, len(same))) + rng.sample(other, N_CAND - 1 - min(9, len(same))) + [t["title_hidden_from_model"]]
    rng.shuffle(c); return c, c.index(t["title_hidden_from_model"]) + 1
def summarize(rows):
    out = {}
    for key in sorted({(r["subject"], r["metric"]) for r in rows}):
        by = collections.defaultdict(dict)
        for r in rows:
            if (r["subject"], r["metric"]) == key and r["score"] is not None: by[r["task_id"]][r["cond"]] = r["score"]
        ids = [i for i in by if all(c in by[i] for c in "ABC")]; res = {"n": len(ids)}
        for c in "ABC": res[f"mean_{c}"] = sum(by[i][c] for i in ids) / max(1, len(ids))
        for a, b in (("B", "C"), ("B", "A"), ("C", "A")):
            d = [by[i][a] - by[i][b] for i in ids]; res[f"{a}-{b}"] = {"mean": sum(d) / max(1, len(d)), "ci95": list(E.boot_ci(d)) if d else [0, 0]}
        res["loop_helps (B-C CI lower bound > 0)"] = res["B-C"]["ci95"][0] > 0
        out[" | ".join(key)] = res
    return out
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--gemini-free", action="store_true")
    ap.add_argument("--only-subject"); ap.add_argument("--analyze-only", action="store_true"); ap.add_argument("--limit", type=int)
    a = ap.parse_args(); out = D / ("results_dryrun" if a.dry_run else "results_prelim"); out.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in open(D / "tasks.jsonl")][: a.limit]; lib = json.load(open(D / "loop_library.json")); ret = Retriever(lib)
    rng = random.Random(31); assign = {}
    for t in tasks:
        b = ret.top(t); held = set(t["own_loops_heldout"]); pool = [i for i in range(len(lib)) if lib[i]["loop_id"] not in held]
        cc = []
        for i in rng.sample(pool, 40):
            g = next((x for x in lib[i]["grounding"] if x["sentence"] not in set(t["gold_steps"])), None)
            if g and len(cc) < max(1, len(b)): cc.append((i, 0.0, g))
        assign[t["task_id"]] = {"B": [(lib[i]["loop_id"], round(v, 2), g["sent_key"]) for i, v, g in b],
                                "C": [(lib[i]["loop_id"], 0.0, g["sent_key"]) for i, v, g in cc],
                                "B_score": round(sum(v for _, v, _ in b), 2), "_B": b, "_C": cc}
    (out / "loop_assignment.json").write_text(json.dumps({k: {x: v[x] for x in ("B", "C", "B_score")} for k, v in assign.items()}, indent=1))
    if a.dry_run: subjects = ["mock"]
    else:
        E.PRICE.update(E.FREE_TIER_PRICE)
        if not a.analyze_only and not os.environ.get("GEMINI_API_KEY"): raise SystemExit("Need GEMINI_API_KEY")
        subjects = [m for _, m in E.FREE_SUBJECTS if not a.only_subject or m == a.only_subject]
    if a.analyze_only: subjects = []
    raw = out / "raw.jsonl"; done = {(r["subject"], r["metric"], r["task_id"], r["cond"]) for r in map(json.loads, open(raw))} if raw.exists() else set()
    f = open(raw, "a"); stop = None
    try:
        for metric in ("identify", "ability"):
            for t in tasks:
                cands, truth = candidates(t, tasks)
                for m in subjects:
                    assert m == "mock" or m in E.FREE_ALLOW
                    for cnd in random.Random(t["task_id"] + m + metric).sample("ABC", 3):
                        if E.FORBIDDEN.search(t["title_hidden_from_model"]): continue
                        if (m, metric, t["task_id"], cnd) in done: continue
                        ctx = "" if cnd == "A" else ("\n\nReference TOTE loops from the system's library (may or may not be relevant):\n" +
                                                     "\n".join(render(lib[i], g) for i, _, g in assign[t["task_id"]]["_" + cnd]))
                        up = id_prompt(t, cands, ctx) if metric == "identify" else ab_prompt(t, ctx)
                        if m == "mock": ans = json.dumps({"top5": random.Random(up).sample(range(1, 21), 5), "struggle_steps": [1], "completion_likelihood": "medium"}); ti = to = 0
                        else: ans, ti, to = E.call("gemini", m, SYS, up, 400)
                        j = pj(ans)
                        if metric == "identify": s1, s5 = score_id(j, truth) if j else (None, None)
                        else: s1 = score_ab(j, t) if j else None; s5 = None
                        base = {"subject": m, "task_id": t["task_id"], "cond": cnd, "answer": ans, "tokens": [ti, to], "usd": 0.0,
                                "B_score": assign[t["task_id"]]["B_score"], "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "label": "PRELIMINARY"}
                        f.write(json.dumps({**base, "metric": metric if metric == "ability" else "identify_top1", "score": s1}) + "\n")
                        if metric == "identify": f.write(json.dumps({**base, "metric": "identify_top5", "score": s5}) + "\n")
                        f.flush(); done.add((m, metric, t["task_id"], cnd))
    except E.Stop as e:
        stop = str(e); print("STOPPED:", stop, flush=True)
    f.close()
    if not a.dry_run and LEDGER.exists():   # must still be $0
        assert json.loads(LEDGER.read_text())["total_usd"] == 0.0
    rows = [json.loads(l) for l in open(raw)] if raw.exists() else []
    rows = [dict(r, metric="identify_top1") if r["metric"] == "identify" else r for r in rows]
    s = {"label": "PRELIMINARY - not a confirmatory result", "summary": summarize(rows),
         "retrieval_coverage": {"tasks_with_>=1_B_loop": sum(bool(v["B"]) for v in assign.values()), "tasks": len(assign)},
         "_stop_reason": stop, "_records": len(rows), "_usd_this_run": 0.0}
    (out / "summary.json").write_text(json.dumps(s, indent=1)); print(json.dumps(s, indent=1)[:2500])
    if stop: raise SystemExit(4 if "DAILY" in stop else 3)
if __name__ == "__main__": main()
