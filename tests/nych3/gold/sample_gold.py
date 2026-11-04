"""Draw the stratified gold sample (deterministic, seed 20261102) from the round-3 shard outcomes.
Writes candidates.jsonl (sentence + provenance + stratum). Grading lives in gold_v1.jsonl."""
import glob, json, random, re, sys
from pathlib import Path
from nych3.harvest.harvester import Harvester, HARVEST_DIR
from nych3.harvest.source import fetch, paragraphs, sources

QUOTA = {"action": 58, "rejected": 17}
rng = random.Random(20261102)
books = {b["book_id"]: b for b in sources()["books"]}
by = {}
for f in sorted(glob.glob(str(HARVEST_DIR / "shards" / "*.jsonl"))):
    for line in open(f, encoding="utf-8"):
        r = json.loads(line)
        if "_meta" in r:
            continue
        o = r["outcome"]
        st = "action" if o == "action" else "rejected" if o in ("non_action", "no_match", "skipped_apparatus") else None
        if st:
            by.setdefault((r["sent_key"].split(":")[0], st), []).append(r)
h = Harvester.__new__(Harvester)
from nych3.nlp.parser_adapter import get_parser
h.parser = get_parser("rule")
out = []
for bid, b in books.items():
    if bid not in {k[0] for k in by}:
        continue
    paras = {p["para_idx"]: p for p in paragraphs(fetch(b), b)}
    for st, q in QUOTA.items():
        if b["domain"] == "craft.ropework" and st == "rejected":
            q = 75 - n_act   # ropework has fewer action sentences: top up with rejected ones (tests recall of the gate)
        pool = by.get((bid, st), [])
        rng.shuffle(pool)
        n = 0
        for r in pool:
            if n >= q:
                break
            pi, si = re.match(r".*:p(\d+):s(\d+)", r["sent_key"]).groups()
            p = paras[int(pi)]
            stt, tagged, temp, sem = Harvester.analyse_paragraph(h, p["text"])
            from nych3.nlp import analysis
            sents = list(analysis.iter_sentences(stt))
            text = sents[int(si)]["text"]
            if len(text) > 230 or len(text) < 8:
                continue
            out.append({"id": f"G{len(out)+1:03d}", "domain": b["domain"], "stratum": st, "sent_key": r["sent_key"],
                        "page": p["page"], "page_kind": p["page_kind"], "sentence": text, "round3_outcome": r["outcome"]})
            n += 1
        if st == "action":
            n_act = n
Path(__file__).with_name("candidates.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
print(len(out), {d: sum(1 for x in out if x["domain"] == d) for d in {x["domain"] for x in out}})
