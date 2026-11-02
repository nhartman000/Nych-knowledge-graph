"""nych3-eval: accuracy of the TOTE harvester against the graded gold set.

    nych3-eval [--gold tests/nych3/gold/gold_v1.jsonl] [--json out.json] [--code-root other/shared]

The gold set is AGENT-GRADED PENDING HUMAN REVIEW (see tests/nych3/gold/README.md).
Loops are matched per sentence by action lemma (in order). Per-field micro P/R over the matched
pairs; each loop and each sentence is graded correct / partial / wrong.
"""
from __future__ import annotations
import argparse, importlib.util, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEFAULT_GOLD = next((p for p in (REPO / "tests" / "nych3" / "gold" / "gold_v1.jsonl", REPO / "tests" / "gold" / "gold_v1.jsonl") if p.exists()), REPO / "tests" / "nych3" / "gold" / "gold_v1.jsonl")
_spec = importlib.util.spec_from_file_location("nych3_eval_compact", HERE / "compact.py")
compact = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(compact)

NUMW = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
        "twenty-four": "24", "one-third": "1/3", "three-fourths": "3/4", "one-half": "1/2"}
STOP = {"the", "a", "an", "of", "is", "are", "on", "in", "to", "until", "for", "as", "be", "you", "have"}
FIELDS = ("objects", "locations", "modality", "amount")


def toks(s):
    out = set()
    for w in re.findall(r"[\w/-]+", (s or "").lower()):
        w = NUMW.get(w, w)
        if w not in STOP:
            out.add(compact.norm(w))
    return out


def actor_kind(a):
    a = (a or "").lower()
    return "you" if a.startswith("you") else "passive" if "passive" in a else "agent"


def predict(text, domain, extract, MR, LV):
    """Same sentence gates as Harvester.extract, then the spaCy extractor."""
    t = text.strip()
    if any(q in t for q in ('"', "“", "”")) or t.endswith("?") or not t or t[-1] not in ".!;:…":
        return []
    o, loops, _ = extract(t, MR, LV, domain)
    return [compact.from_extracted(lp) for lp in loops] if o == "action" else []


def setpr(g, p):
    g, p = set(g), set(p)
    return len(g & p), len(p), len(g)


def evaluate(gold_path=DEFAULT_GOLD, code_root=None):
    if code_root:
        sys.path.insert(0, str(code_root))
    from nych3.config import registry
    from nych3.harvest.spacy_extract import extract
    MR, LV = registry("modality"), set(registry("lexicon")["verbs"])
    rows = [json.loads(l) for l in open(gold_path, encoding="utf-8") if l.strip()]
    tally = defaultdict(lambda: defaultdict(Counter))   # scope -> field -> tp/np/ng
    verdict = defaultdict(Counter)
    lverdict = defaultdict(Counter)
    errors = Counter(); examples = defaultdict(list)
    details = []
    for r in rows:
        dom = r["domain"]
        gold = compact.parse_sentence(r["gold"])
        for gl in gold:
            gl["actor"] = actor_kind(gl["actor"])
        pred = predict(r["sentence"], dom, extract, MR, LV)
        for pl in pred:
            pl["actor"] = actor_kind(pl["actor"])
        used, pairs = set(), []
        for gl in gold:
            j = next((j for j, pl in enumerate(pred) if j not in used and pl["action"] == gl["action"]), None)
            if j is not None:
                used.add(j); pairs.append((gl, pred[j]))
            else:
                errors["missed_loop"] += 1; examples["missed_loop"].append(f"{r['id']} {gl['action']}")
                if not gl["objects"] and gl["exit_tier"] == "inferred" and not gl["locations"]:
                    errors["missed_loop:bare_verb"] += 1
        for j, pl in enumerate(pred):
            if j not in used:
                errors["spurious_loop"] += 1; examples["spurious_loop"].append(f"{r['id']} {pl['action']}")
        for scope in ("all", dom):
            T = tally[scope]
            T["action"]["tp"] += len(pairs); T["action"]["np"] += len(pred); T["action"]["ng"] += len(gold)
            T["instruction_sentence"]["tp"] += int(bool(gold) and bool(pred))
            T["instruction_sentence"]["np"] += int(bool(pred)); T["instruction_sentence"]["ng"] += int(bool(gold))
        ok_loops = 0
        for gl, pl in pairs:
            bad = []
            for f in FIELDS:
                tp, np_, ng = setpr(gl[f], pl[f])
                for scope in ("all", dom):
                    tally[scope][f]["tp"] += tp; tally[scope][f]["np"] += np_; tally[scope][f]["ng"] += ng
                if set(gl[f]) != set(pl[f]):
                    bad.append(f)
            tier_ok = gl["exit_tier"] == pl["exit_tier"]
            ex_ok = tier_ok and (gl["exit_tier"] == "inferred" or
                                 len(toks(gl["exit"]) & toks(pl["exit"])) >= max(1, 0.5 * len(toks(gl["exit"]))))
            act_ok = gl["actor"] == pl["actor"]
            for scope in ("all", dom):
                for f, okv in (("exit_tier", tier_ok), ("exit", ex_ok), ("actor", act_ok)):
                    tally[scope][f]["tp"] += okv; tally[scope][f]["np"] += 1; tally[scope][f]["ng"] += 1
            bad += [f for f, okv in (("exit_tier", tier_ok), ("exit", ex_ok and tier_ok), ("actor", act_ok)) if not okv]
            if "exit" in bad and "exit_tier" in bad:
                bad.remove("exit")
            for b in bad:
                errors[f"{b}_wrong"] += 1
                if len(examples[f"{b}_wrong"]) < 400:
                    examples[f"{b}_wrong"].append(f"{r['id']} {gl['action']}: gold {gl[b] if b in gl else ''} | pred {pl.get(b)}")
            v = "correct" if not bad else "partial"
            ok_loops += v == "correct"
            for scope in ("all", dom):
                lverdict[scope][v] += 1
        for scope in ("all", dom):
            lverdict[scope]["wrong"] += (len(gold) - len(pairs)) + (len(pred) - len(pairs))
        if not gold and not pred:
            sv = "correct"
        elif not pairs:
            sv = "wrong"
            errors["gate_false_positive" if not gold else "gate_false_negative" if not pred else "no_loop_matched"] += 1
        elif ok_loops == len(pairs) == len(gold) == len(pred):
            sv = "correct"
        else:
            sv = "partial"
        for scope in ("all", dom):
            verdict[scope][sv] += 1
        details.append({"id": r["id"], "verdict": sv, "gold": r["gold"], "pred": " || ".join(compact.to_compact(p) for p in pred) or "-"})

    def pr(c):
        p = c["tp"] / c["np"] if c["np"] else None
        rc = c["tp"] / c["ng"] if c["ng"] else None
        f = 2 * p * rc / (p + rc) if p and rc else 0.0 if p is not None and rc is not None else None
        return {"precision": p, "recall": rc, "f1": f, **c}
    report = {"gold": str(gold_path), "n_sentences": len(rows), "grading": "agent-graded, pending human review",
              "fields": {s: {f: pr(c) for f, c in T.items()} for s, T in tally.items()},
              "sentence_verdicts": {s: dict(v) for s, v in verdict.items()},
              "loop_verdicts": {s: dict(v) for s, v in lverdict.items()},
              "errors": dict(errors.most_common()), "examples": {k: v[:15] for k, v in examples.items()}, "details": details}
    return report


def fmt(rep):
    L = [f"gold: {rep['n_sentences']} sentences ({rep['grading']})"]
    order = ["instruction_sentence", "action", "objects", "locations", "modality", "exit_tier", "exit", "amount", "actor"]
    for scope in ["all"] + sorted(k for k in rep["fields"] if k != "all"):
        F = rep["fields"][scope]
        sv, lv = rep["sentence_verdicts"][scope], rep["loop_verdicts"][scope]
        L.append(f"\n[{scope}] sentences correct/partial/wrong = {sv.get('correct',0)}/{sv.get('partial',0)}/{sv.get('wrong',0)}"
                 f"   loops correct/partial/wrong = {lv.get('correct',0)}/{lv.get('partial',0)}/{lv.get('wrong',0)}")
        for f in order:
            if f in F:
                c = F[f]
                g = lambda x: "  -  " if x is None else f"{x:.3f}"
                L.append(f"  {f:22s} P {g(c['precision'])}  R {g(c['recall'])}  F1 {g(c['f1'])}   (tp {c['tp']}, pred {c['np']}, gold {c['ng']})")
    L.append("\nerrors: " + ", ".join(f"{k}={v}" for k, v in rep["errors"].items()))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nych3-eval")
    ap.add_argument("--gold", default=str(DEFAULT_GOLD)); ap.add_argument("--json"); ap.add_argument("--code-root")
    a = ap.parse_args(argv)
    rep = evaluate(Path(a.gold), a.code_root)
    print(fmt(rep))
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
