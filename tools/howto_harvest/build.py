"""Cached HTML -> compact export shared/data/howto/{howto_actions.jsonl.gz, summary.json}.
Reuses the tech_ui pipeline's extractor (steps_from), imperative parser (actions) and mapping (canon).
Stores NO article text: per action only verb, object, types, modifiers, URL, retrieval date, section/step and a quote of
<= 25 source tokens (plus '…' markers when truncated)."""
import gzip, hashlib, json, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "REVIEW", "tech_ui_pipeline", "src")); sys.path.insert(0, HERE)
import extract
from extract import steps_from
def _main_node(s):
    """Pick the content container with the most list/paragraph text (blog pages have card <article>s before the real one)."""
    cands = [n for sel in ["#sections", "div.cc", "article", "main", "[role=main]", "#ocArticleContent", ".article-body", ".entry-content", ".post-content"] for n in s.select(sel)]
    score = lambda n: sum(len(x.get_text(" ", strip=True)) for x in n.find_all(["li", "p"]))
    best = max(cands, key=score, default=None)
    return best if best is not None and score(best) > 400 else s.body or s
extract.main_node = _main_node
from parse import actions, OBJ
from canon import canon, NONACT
from sources import SOURCES, classify
RAW = os.environ.get("HOWTO_RAW", "/workspace/howto_raw"); OUT = os.path.join(REPO, "shared", "data", "howto")
from rules import *   # noqa: F401,F403  (ranges, modality, PLATS, BOILER, CTA, STOPV, quote)
def is_step_line(x, acts):
    if x["kind"] in ("ol",): return True
    t = re.sub(r"^(\d+[.)]\s*|step \d+:?\s*|first,?\s*|then,?\s*|next,?\s*|finally,?\s*|also,?\s*)", "", x["text"], flags=re.I)
    return bool(acts) and t[:len(acts[0]["surface"])].lower() == acts[0]["surface"].lower()
def main():
    os.makedirs(OUT, exist_ok=True)
    # pass 0: lines repeated on >= max(5, 3% of pages) of one site are site chrome/promos (e.g. "Follow ... on Google News"), not steps
    rep = {}
    for src in SOURCES:
        pd = os.path.join(RAW, "_parsed", src["name"])
        if not os.path.isdir(pd): continue
        files = os.listdir(pd); cnt = collections.Counter()
        for fn in files:
            try: cnt.update({x["text"] for x in json.load(open(os.path.join(pd, fn)))[1]})
            except Exception: pass
        rep[src["name"]] = {t for t, k in cnt.items() if k >= max(5, 0.03 * len(files))}
    rows = []; pages = collections.Counter(); pages_dom = collections.Counter(); stats = collections.Counter()
    for src in SOURCES:
        ix = os.path.join(RAW, src["name"], "_index.jsonl")
        if not os.path.exists(ix): continue
        for line in open(ix):
            e = json.loads(line); f = os.path.join(RAW, src["name"], e["file"])
            if not os.path.exists(f): continue
            cf = os.path.join(RAW, "_parsed", src["name"], e["file"] + ".json")
            if os.path.exists(cf): title, st = json.load(open(cf))
            else:
                try: title, st = steps_from(open(f, encoding="utf-8").read())
                except Exception: stats["parse_error"] += 1; continue
                for x in st: x["acts"] = actions(x["text"]) if not BOILER.search(x["text"]) else []
                os.makedirs(os.path.dirname(cf), exist_ok=True); json.dump([title, st], open(cf, "w"))
            if src["name"] in ("bitwarden", "onepassword") and ENTERPRISE.search(e["url"]): stats["enterprise_admin_page"] += 1; continue
            dom = classify(e["url"], title, src["domain"]) if src.get("classify") else e["domain"]
            pages[src["name"]] += 1; pages_dom[dom] += 1
            for li, x in enumerate(st):
                if BOILER.search(x["text"]): stats["boiler"] += 1; continue
                if x["text"] in rep.get(src["name"], ()): stats["site_repeated_line"] += 1; continue
                acts = x["acts"]
                if not acts or not is_step_line(x, acts): stats["non_step_line"] += 1; continue
                if CTA.search(x["text"]) or (x["kind"] != "ol" and len(x["text"].split()) < 5) or x["text"].rstrip().endswith("?"):
                    stats["cta_or_feature_list"] += 1; continue
                rng = ranges(x["text"])
                plats = [p for p, rx in PLATS if re.search(rx, x["text"] + " " + title, re.I)]
                for k, a in enumerate(acts):
                    c = canon({**a, "text": x["text"], "direction": "", "count": "", "duration": ""})
                    if c == "NON_ACTION" or a["verb"].split()[0] in NONACT or a["verb"].split()[0] in STOPV: stats["non_action"] += 1; continue
                    if not a["object"].strip() or re.match(r"^(simply|it all|the no\b|’s|'s)", a["object"]): stats["bare_verb_or_junk_object"] += 1; continue
                    md, why = modality(a["verb"], x["text"], c, a["object"])
                    rid = hashlib.sha1(f"{e['url']}|{li}|{k}".encode()).hexdigest()[:16]
                    rows.append({"id": rid, "domain": dom, "platform": src["platform"], "platform_hints": "|".join(plats), "site": src["name"],
                                 "canonical": "" if c.startswith("UNMAPPED") else c, "verb": a["verb"], "object": a["object"], "obj_type": a["obj_type"],
                                 "modality": md, "modality_rule": why, "amount_ranges": rng,
                                 "condition_cues": ";".join(sorted({m.group(0).lower() for m in re.finditer(r"\b(until|when prompted|if prompted|after|once|before|wait for|if you see|as soon as|appears|unless)\b", x["text"], re.I)})),
                                 "url": e["url"], "retrieved": e["retrieved"], "title": title[:120], "section": x["section"], "step_no": x["step_no"], "kind": x["kind"],
                                 "quote": quote(x["text"], a["surface"])})
                    stats["actions"] += 1
    with gzip.open(os.path.join(OUT, "howto_actions.jsonl.gz"), "wt", encoding="utf-8") as w:
        for r in rows: w.write(json.dumps(r, ensure_ascii=False) + "\n")
    summ = {"pages_by_source": dict(pages), "pages_by_domain": dict(pages_dom), "actions_by_domain": dict(collections.Counter(r["domain"] for r in rows)),
            "actions": len(rows), "mapped_to_ui_canonical": sum(1 for r in rows if r["canonical"]), "filters": dict(stats),
            "modality": dict(collections.Counter(r["modality"] for r in rows)), "with_amount_range": sum(1 for r in rows if r["amount_ranges"])}
    json.dump(summ, open(os.path.join(OUT, "summary.json"), "w"), indent=1, ensure_ascii=False); print(json.dumps(summ, indent=1, ensure_ascii=False))
if __name__ == "__main__": main()
