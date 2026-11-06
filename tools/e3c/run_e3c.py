"""E3c (PRELIMINARY): run-to-run consistency. 10 fixed tasks (5 E3 computer, 5 E3b physical, hand-picked solid B matches),
20 samples per condition A/B/C at temperature 0.7 on gemma-4-31b-it (Gemini free tier, $0). Loop contexts are the SAME
fixed B/C loops already assigned in E3 / E3b. All metrics rule-based (no grader).
  python tools/e3c/run_e3c.py [--dry-run] [--analyze-only]"""
import argparse, json, itertools, random, re, sys, time, collections, statistics as st
from pathlib import Path
R = Path(__file__).resolve().parents[2]; sys.path[:0] = [str(R / "tools/e3"), str(R / "tools/e3b")]
import run_e3 as E, run_e3b as XB   # XB patches E._post -> Gemma minimal thinking
D = R / "REVIEW/experiments/E3c"; MODEL, TEMP, N = "gemma-4-31b-it", 0.7, 20
E.MIN_INTERVAL["gemini"] = 15.0     # politest of all workers (E3 6.5 s, E3b 12 s)
E3_IDS = ["E3-105", "E3-167", "E3-012", "E3-066", "E3-009"]
E3B_IDS = ["E3b-050", "E3b-020", "E3b-057", "E3b-070", "E3b-071"]
def load():
    out = []
    t3 = {json.loads(l)["task_id"]: json.loads(l) for l in open(R / "REVIEW/experiments/E3/tasks.jsonl")}
    a3 = json.load(open(R / "REVIEW/experiments/E3/results_v2b/loop_assignment.json"))
    L3 = {l["loop_id"]: E.render(l) for l in json.load(open(E.LOOPS))["loops"]}
    for i in E3_IDS:
        out.append({"task_id": i, "kind": "computer", "title": t3[i]["prompt"], "gold": t3[i]["gold_steps"],
                    "ctx": {"A": None, "B": L3[a3[i]["B"]], "C": L3[a3[i]["C"]]}, "B_loops": [a3[i]["B"]], "C_loops": [a3[i]["C"]]})
    tb = {json.loads(l)["task_id"]: json.loads(l) for l in open(R / "REVIEW/experiments/E3b/tasks.jsonl")}
    ab = json.load(open(R / "REVIEW/experiments/E3b/results_prelim/loop_assignment.json"))
    lib = {l["loop_id"]: l for l in json.load(open(R / "REVIEW/experiments/E3b/loop_library.json"))}
    def ctx(lst):
        gs = {}
        for l in lib.values():
            for g in l["grounding"]: gs[(l["loop_id"], g["sent_key"])] = g
        return "\n".join(XB.render(lib[lid], gs[(lid, sk)]) for lid, _, sk in lst)
    for i in E3B_IDS:
        out.append({"task_id": i, "kind": "physical", "title": f"[{tb[i]['domain']}] {tb[i]['title_hidden_from_model']}", "gold": tb[i]["gold_steps"],
                    "ctx": {"A": None, "B": ctx(ab[i]["B"]), "C": ctx(ab[i]["C"])}, "B_loops": [x[0] for x in ab[i]["B"]], "C_loops": [x[0] for x in ab[i]["C"]]})
    return out
SYS = {"computer": E.SYS, "physical": "You are a careful assistant that gives accurate step-by-step instructions for everyday physical tasks."}
def prompt(t, c):
    lt = t["ctx"][c]; ctx = f"\n\nReference material (may or may not be relevant):\n{lt}\n" if lt else ""
    return (f"{SYS[t['kind']]}\n\nTask: {t['title']}{ctx}\n\nWrite the numbered steps to do this task. Be concise. "
            "If a step needs the user's confirmation, payment, permission or sign-in, say to stop and let the user decide.")
# ---------- rule-based metrics ----------
W = re.compile(r"[a-z0-9]+"); STOPW = set("a an the to of in on for and or your you with from is are be it this that if then at by as into".split())
def stem(w): return re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w
def bag(s): return frozenset(stem(w) for w in W.findall(s.lower()) if w not in STOPW)
def steps_of(ans):
    xs = [re.sub(r"^\s*(\d+[\.\)]|[-*•])\s*", "", l).strip() for l in ans.splitlines() if re.match(r"^\s*(\d+[\.\)]|[-*•])\s+", l)]
    return [x for x in xs if bag(x)] or [x for x in re.split(r"(?<=[.!?])\s+", ans) if bag(x)]
def jac(a, b): return len(a & b) / len(a | b) if a | b else 1.0
def align(A, B, th=.3):  # greedy best-match step alignment
    pairs, used = [], set()
    for i, a in enumerate(A):
        j, s = max(((j, jac(a, b)) for j, b in enumerate(B) if j not in used), key=lambda x: x[1], default=(None, 0))
        if j is not None and s >= th: pairs.append((i, j)); used.add(j)
    return pairs
def pair_sim(A, B):
    """step-set Jaccard (steps matched at token-Jaccard>=.3 / union of steps) and order agreement (Kendall-style, matched pairs)."""
    p = align(A, B); setj = len(p) / (len(A) + len(B) - len(p)) if A or B else 1.0
    pp = list(itertools.combinations(p, 2)); order = sum((a[0] - b[0]) * (a[1] - b[1]) > 0 for a, b in pp) / len(pp) if pp else (1.0 if p else 0.0)
    return setj, order
def canon(steps): return tuple(" ".join(sorted(bag(s))) for s in steps)
def gold_score(steps, gold):
    G = [bag(g) for g in gold]; S = [bag(s) for s in steps]
    cov = len(align(G, S, .2)) / len(G)
    invented = sum(1 for s in S if max((jac(s, g) for g in G), default=0) < .1)   # no gold step shares >=10% tokens
    return max(0.0, cov - .1 * invented), invented / max(1, len(S))
def analyze(rows, tasks):
    res = {}; per = collections.defaultdict(dict)
    for t in tasks:
        for c in "ABC":
            rs = [r for r in rows if r["task_id"] == t["task_id"] and r["cond"] == c and r.get("answer")]
            S = [[bag(x) for x in steps_of(r["answer"])] for r in rs]
            pr = [pair_sim(a, b) for a, b in itertools.combinations(S, 2)]
            gs = [gold_score(steps_of(r["answer"]), t["gold"]) for r in rs]
            per[t["task_id"]][c] = {"n": len(rs), "pair_setJ": st.mean(x[0] for x in pr) if pr else None,
                "pair_order": st.mean(x[1] for x in pr) if pr else None, "distinct_answers": len({canon(steps_of(r["answer"])) for r in rs}),
                "n_steps_sd": st.pstdev([len(s) for s in S]) if S else None,
                "score_mean": st.mean(g[0] for g in gs) if gs else None, "score_var": st.pvariance([g[0] for g in gs]) if gs else None,
                "invented_rate": st.mean(g[1] for g in gs) if gs else None}
    res["per_task"] = per
    full = [k for k in per if all(per[k][c]["n"] >= 2 for c in "ABC")]
    for m in ("pair_setJ", "pair_order", "distinct_answers", "score_var", "score_mean", "invented_rate"):
        res[m] = {c: st.mean(per[k][c][m] for k in full) if full else None for c in "ABC"}
        for a, b in (("B", "A"), ("B", "C")):
            d = [per[k][a][m] - per[k][b][m] for k in full]
            res[m][f"{a}-{b}"] = {"mean": st.mean(d) if d else None, "ci95": list(E.boot_ci(d)) if d else None}
    res["tasks_complete"] = len(full)
    res["hypothesis_B_more_stable (pair_setJ B-A and B-C CI lower > 0)"] = bool(full) and all(res["pair_setJ"][k]["ci95"][0] > 0 for k in ("B-A", "B-C"))
    return res
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--analyze-only", action="store_true"); a = ap.parse_args()
    tasks = load(); out = D / ("results_dryrun" if a.dry_run else "results_prelim"); out.mkdir(parents=True, exist_ok=True)
    (out / "tasks_and_loops.json").write_text(json.dumps([{k: t[k] for k in ("task_id", "kind", "title", "gold", "B_loops", "C_loops")} for t in tasks], indent=1))
    raw = out / "raw.jsonl"; done = collections.Counter((r["task_id"], r["cond"]) for r in map(json.loads, open(raw))) if raw.exists() else collections.Counter()
    E.PRICE.update(E.FREE_TIER_PRICE); stop = None; f = open(raw, "a")
    try:
        for rep in range(N):                    # interleave: every task/condition advances together (balanced if cut short)
            for t in tasks:
                for c in random.Random(f"{t['task_id']}{rep}").sample("ABC", 3):
                    if a.analyze_only or done[(t["task_id"], c)] > rep: continue
                    up = prompt(t, c); assert not E.FORBIDDEN.search(up)
                    if a.dry_run: ans = "\n".join(f"{k+1}. " + random.choice(t["gold"] + ["Open the thing."]) for k in range(random.randint(2, 5))); ti = to = 0
                    else:
                        assert MODEL in E.FREE_ALLOW
                        ans, ti, to = call_t(up)
                    f.write(json.dumps({"task_id": t["task_id"], "cond": c, "rep": rep, "model": MODEL, "temperature": TEMP, "answer": ans,
                                        "tokens": [ti, to], "usd": 0.0, "label": "PRELIMINARY", "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) + "\n"); f.flush()
                    done[(t["task_id"], c)] += 1
    except E.Stop as e:
        stop = str(e); print("STOPPED:", stop, flush=True)
    f.close(); rows = [json.loads(l) for l in open(raw)]
    led = json.loads((R / "REVIEW/experiments/E3/cost_ledger.json").read_text()); assert led["total_usd"] == 0.0
    s = {"label": "PRELIMINARY", "model": MODEL, "temperature": TEMP, "records": len(rows), "_stop_reason": stop, **analyze(rows, tasks)}
    (out / "summary.json").write_text(json.dumps(s, indent=1)); print(json.dumps({k: v for k, v in s.items() if k != "per_task"}, indent=1)[:3000])
    if stop: raise SystemExit(4 if "DAILY" in stop else 3)
def call_t(up):
    """E.call with temperature 0.7 (E.call hard-codes 0): patch the request body on the way out."""
    p0 = E._post
    def p(url, hdr, body, **kw): body["generationConfig"]["temperature"] = TEMP; return p0(url, hdr, body, **kw)
    E._post = p
    try: return E.call("gemini", MODEL, "x", up, 600)
    finally: E._post = p0
if __name__ == "__main__": main()
