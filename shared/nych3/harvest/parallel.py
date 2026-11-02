"""Parallel harvest: N extraction workers + ONE Kuzu writer (fix 7).

Kuzu allows a single writer, so workers never touch the DB. The work is sharded by
(book, paragraph range). Each worker runs the same pure `Harvester.extract` and writes
`<out>/shards/<book>@<lo>-<hi>.jsonl` via tmp-file + atomic rename, so a shard file that
exists is complete. Afterwards `merge` (single process) replays the shard files into Kuzu,
one transaction per shard, skipping any sentence key already in the HarvestSentence
ledger (at-most-once), and records merged shards in checkpoint.json.

Resumable at both stages: re-running skips finished shard files and merged shards; a
killed worker leaves only a .tmp that is redone. Sentence keys are `<book>:p<para>:s<n>`
(position-stable, independent of how the work was split)."""
from __future__ import annotations
import json, os, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from ..nlp import analysis
from .harvester import Harvester, HARVEST_DIR
from .source import sources, fetch, paragraphs

SHARD_PARAS = 60
COUNTERS = ("sentences_seen", "skipped_dialogue", "skipped_question", "skipped_too_long", "skipped_apparatus", "non_action",
            "action_sentences", "action_clauses", "no_match", "modality_unresolved", "errors", "sense_attached", "sense_unattached")


def plan(books, shard_paras=SHARD_PARAS, fetcher=fetch):
    out = []
    for b in books:
        n = len(paragraphs(fetcher(b), b))
        out += [(b, lo, min(lo + shard_paras, n)) for lo in range(0, n, shard_paras)]
    return out


def shard_name(book, lo, hi):
    return f"{book['book_id']}@{lo:05d}-{hi:05d}"


def work_shard(book, lo, hi, out_dir, fetcher=fetch):
    out_dir = Path(out_dir); sd = out_dir / "shards"; sd.mkdir(parents=True, exist_ok=True)
    final = sd / f"{shard_name(book, lo, hi)}.jsonl"
    if final.exists():
        return final.name, "cached"
    h = Harvester(None, out_dir, fetcher=fetcher)
    paras = paragraphs(fetcher(book), book)[lo:hi]
    recs = []
    for para in paras:
        try:
            st, tagged, temp, sem = h.analyse_paragraph(para["text"])
            sents = list(analysis.iter_sentences(st))
        except Exception as e:
            h.stats["errors"] += 1; continue
        for n, s in enumerate(sents):
            key = f"{book['book_id']}:p{para['para_idx']}:s{n}"
            h.stats["sentences_seen"] += 1
            try:
                outcome, loops, reason = h.extract(dict(s, tokens=tagged[s["sent_id"]]), temp, sem, book.get("domain"))
            except Exception as e:
                outcome, loops, reason = "error", [], repr(e)[:200]; h.stats["errors"] += 1
            if outcome in h.stats and isinstance(h.stats[outcome], int):
                h.stats[outcome] += 1
            if outcome in ("action", "no_match"):
                h.stats["action_sentences"] += 1
            for lp in loops:
                h.stats["action_clauses"] += 1; h.stats["modality_unresolved"] += lp["modality_unresolved"]
            recs.append({"sent_key": key, "offset": para["para_idx"] * 1000 + n, "outcome": outcome, "reason": reason,
                         "para": {k: para[k] for k in ("para_idx", "page", "page_kind", "page_method")}, "loops": loops})
    tmp = final.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": {"book_id": book["book_id"], "lo": lo, "hi": hi, "pid": os.getpid(),
                                      "stats": {k: h.stats[k] for k in COUNTERS}}}, ensure_ascii=False) + "\n")
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(final)
    return final.name, "done"


def run_parallel(workers=4, book_ids=None, out_dir=HARVEST_DIR, shard_paras=SHARD_PARAS, books=None, fetcher=fetch):
    books = [b for b in (books or sources()["books"]) if not book_ids or b["book_id"] in book_ids]
    for b in books:   # polite: fetch serially, once, in the parent
        fetcher(b)
    shards = plan(books, shard_paras, fetcher)
    t0 = time.time(); res = {"done": 0, "cached": 0}
    if workers <= 1:
        for b, lo, hi in shards:
            res[work_shard(b, lo, hi, out_dir, fetcher)[1]] += 1
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(work_shard, b, lo, hi, str(out_dir), fetcher) for b, lo, hi in shards]
            for f in as_completed(futs):
                res[f.result()[1]] += 1
    return {"workers": workers, "shards": len(shards), **res, "extract_seconds": round(time.time() - t0, 1)}


def merge(db_path, out_dir=HARVEST_DIR, books=None):
    """Single writer: replay shard JSONL into Kuzu. Idempotent and resumable."""
    books = {b["book_id"]: b for b in (books or sources()["books"])}
    h = Harvester(db_path, out_dir)
    merged = set(h.ckpt.get("_merged_shards", []))
    for f in sorted((Path(out_dir) / "shards").glob("*.jsonl")):
        if f.name in merged:
            continue
        lines = f.read_text(encoding="utf-8").splitlines()
        meta = json.loads(lines[0])["_meta"]; book = books[meta["book_id"]]
        pb = h.stats["per_book"].setdefault(book["book_id"], {"sentences_seen": 0, "loops_new": 0, "loops_repeat": 0, "action_sentences": 0})
        for k in COUNTERS:
            h.stats[k] += meta["stats"].get(k, 0)
        pb["sentences_seen"] += meta["stats"]["sentences_seen"]; pb["action_sentences"] += meta["stats"]["action_sentences"]
        h.db.c.execute("BEGIN TRANSACTION")
        try:
            for ln in lines[1:]:
                r = json.loads(ln)
                if h._seen(r["sent_key"]):
                    h.stats["skipped_already_processed"] += 1; continue
                if r["outcome"] == "no_match":
                    h.stats["no_match_reasons"][r["reason"]] = h.stats["no_match_reasons"].get(r["reason"], 0) + 1
                elif r["outcome"] == "non_action" and r["reason"]:
                    h.stats["non_action_reasons"][r["reason"]] = h.stats["non_action_reasons"].get(r["reason"], 0) + 1
                for n, lp in enumerate(r["loops"]):
                    new = h._write_loop(lp, book, r["para"], f"{r['sent_key']}#{n}", r["sent_key"], lp["sentence"])
                    k = "loops_new" if new else "loops_repeat"; h.stats[k] += 1; pb[k] += 1
                    if new and len(h.stats["samples_new"]) < 40:
                        h.stats["samples_new"].append({"loop_id": lp["loop_id"], "row": lp["row"], "sentence": lp["sentence"]})
                h.db.c.execute("CREATE (:HarvestSentence {sent_key:$k,book_id:$b,sent_offset:$o,outcome:$u})",
                               dict(k=r["sent_key"], b=book["book_id"], o=r["offset"], u=r["outcome"]))
            h.db.c.execute("COMMIT")
        except Exception:
            h.db.c.execute("ROLLBACK"); raise
        merged.add(f.name); h.ckpt["_merged_shards"] = sorted(merged); h._save_ckpt()
    h.stats["finished"] = datetime.now().isoformat(timespec="seconds"); h.stats["stopped_by"] = "merge_complete"
    h.stats["mode"] = "parallel-merge"
    if hasattr(h.db, "refresh_domain_links"):   # knowledge-graph store: derive DOMAIN_LINK edges after the merge
        h.stats["domain_links"] = h.db.refresh_domain_links()
    h.save_stats(); st = h.stats; h.close()
    return st
