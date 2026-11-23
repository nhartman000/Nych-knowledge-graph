"""The shortcut: text in -> ranked study areas, domains, professions, techniques and TOTE loops, plus competency.

Owner, 2026-11-23: the graph must "serve as the ultimate tool for the model to do its shortcutting". This is the
lookup the inverse transform reads: what the words point to, so everything else can be pruned.

Method (deterministic, no LLM; interpretations flagged R1-R4):
1. Words of the text are matched to Term nodes, longest phrase first (3, 2, 1 words), no overlaps.
2. R1 Each matched term spreads one unit of evidence evenly over the domains (and, separately, the professions) it
   is linked to, so a word tied to one domain counts fully and a word tied to fifty barely counts.
3. Domains roll up their evidence to every ancestor (industry -> subsector -> sector). R2 Rank = summed evidence.
4. Study areas come from the ranked professions through the CIP-SOC crosswalk, rolled up to CIP families.
5. Techniques and TOTE loops come from the top professions' tasks (PERFORMS -> TASK_TECHNIQUE / TASK_LOOP).
   R5 A single word with everyday-English Zipf >= 5.0 (wordfreq) (very common words such as "for", "under") is not evidence;
   proposal, not owner-approved. R2 Items are ranked by the number of distinct matched terms supporting them, then
   by summed evidence, so a domain backed by several words beats one backed by a single word sense.
   Study-area evidence: each profession's score is split evenly over the CIP families it leads to.
6. R3 Competency (owner: experts use expert terminology, novices novice terms) = share of matched terms per tier;
   the label is the tier with the largest share. R4 Ties keep every tied item (D4 tie policy).
7. Plurals (owner, 2026-11-23: "yes add plurals"): when a phrase as written is not a Term, its last word is tried in
   singular form (-ies -> -y, -es -> drop, -s -> drop; not -ss, words of 4+ letters), e.g. "dentists" -> "dentist",
   "summary judgments" -> "summary judgment". The written form is kept as `as_written`. R6 these exact endings and the
   full weight of a plural match are my interpretation.
No match at all returns "unresolved domain".
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

COMMON_WORD_ZIPF = 5.0  # R5 proposal
_WORD = re.compile(r"[a-z0-9]+(?:['\-][a-z0-9]+)*")


def _q(conn, cypher, params=None):
    res = conn.execute(cypher, params or {})
    cols = res.get_column_names()
    out = []
    while res.has_next():
        out.append(dict(zip(cols, res.get_next())))
    return out


def singulars(word: str) -> list[str]:
    """Regular English singular candidates for a plural word (R6), most specific first."""
    if len(word) < 4 or word.endswith("ss") or not word.endswith("s"):
        return []
    out = [word[:-3] + "y"] if word.endswith("ies") else []
    if word.endswith("es"):
        out.append(word[:-2])
    out.append(word[:-1])
    return out


def _forms(gram: str) -> list[str]:
    head, _, last = gram.rpartition(" ")
    return [gram] + [(head + " " + s if head else s) for s in singulars(last)]


def match_terms(conn, text: str) -> list[dict]:
    ws = _WORD.findall(text.lower())
    grams = sorted({f for n in (1, 2, 3) for i in range(len(ws) - n + 1) for f in _forms(" ".join(ws[i:i + n]))})
    known = {r["term"]: r for r in _q(conn, "UNWIND $g AS g MATCH (t:Term {term: g}) RETURN t.term AS term, t.tier AS tier, t.zipf AS zipf", {"g": grams})
             if " " in r["term"] or r["zipf"] is None or r["zipf"] < COMMON_WORD_ZIPF}
    out, i = [], 0
    while i < len(ws):
        for n in (3, 2, 1):
            g = " ".join(ws[i:i + n])
            hit = next((f for f in _forms(g) if f in known), None) if len(ws[i:i + n]) == n else None
            if hit:
                out.append(known[hit] if hit == g else {**known[hit], "as_written": g})
                i += n
                break
        else:
            i += 1
    return out


def _top(scores: dict, k: int, support: dict | None = None) -> list[dict]:
    support = support or {}
    key = lambda i: (len(support.get(i, ())), round(scores[i], 9))  # noqa: E731  (R2)
    ranked = sorted(scores, key=lambda i: (tuple(-x for x in key(i)), i))
    if not ranked:
        return []
    cut = key(ranked[min(k, len(ranked)) - 1])
    return [{"id": i, "score": round(scores[i], 4), "terms": len(support.get(i, ()))} for i in ranked if key(i) >= cut]  # R4


def resolve(conn, text: str, k: int = 5) -> dict:
    terms = match_terms(conn, text)
    if not terms:
        return {"domains": ["unresolved domain"], "terms": [], "competency": None}
    names = [t["term"] for t in terms]
    td = _q(conn, "UNWIND $t AS t MATCH (x:Term {term: t})-[r:TERM_DOMAIN]->(d:Domain) RETURN x.term AS term, d.domain_id AS d", {"t": names})
    tp = _q(conn, "UNWIND $t AS t MATCH (x:Term {term: t})-[r:TERM_PROFESSION]->(p:Profession) RETURN x.term AS term, p.profession_id AS p", {"t": names})
    dom, prof = defaultdict(float), defaultdict(float)
    dsup, psup = defaultdict(set), defaultdict(set)
    links_d, links_p = Counter(r["term"] for r in td), Counter(r["term"] for r in tp)
    for r in td:
        dom[r["d"]] += 1.0 / links_d[r["term"]]
        dsup[r["d"]].add(r["term"])
    for r in tp:
        prof[r["p"]] += 1.0 / links_p[r["term"]]
        psup[r["p"]].add(r["term"])
    # roll up to ancestors
    rolled = defaultdict(float, dom)
    rsup = defaultdict(set, {d: set(v) for d, v in dsup.items()})
    if dom:
        for r in _q(conn, "UNWIND $d AS d MATCH (x:Domain {domain_id: d})-[:DOMAIN_PARENT*1..5]->(a:Domain) "
                          "RETURN x.domain_id AS d, a.domain_id AS a", {"d": list(dom)}):
            rolled[r["a"]] += dom[r["d"]]
            rsup[r["a"]] |= dsup[r["d"]]
    sectors = {r["id"]: r for r in _q(conn, "UNWIND $d AS d MATCH (x:Domain {domain_id: d}) RETURN x.domain_id AS id, x.name AS name, x.level AS level", {"d": list(rolled)})}
    by_level = defaultdict(dict)
    for d, s in rolled.items():
        by_level[sectors[d]["level"]][d] = s
    top_prof = _top(prof, k, psup)
    pids = [p["id"] for p in top_prof]
    study, fams = defaultdict(float), defaultdict(set)
    for r in _q(conn, "UNWIND $p AS p MATCH (s:StudyArea)-[:STUDY_LEADS_TO]->(x:Profession {profession_id: p}) "
                      "OPTIONAL MATCH (s)-[:STUDY_PARENT*1..2]->(f:StudyArea {level: 2}) "
                      "RETURN DISTINCT p, coalesce(f.study_id, s.study_id) AS f", {"p": pids}):
        fams[r["p"]].add(r["f"])
    for p, fs in fams.items():
        for f in fs:
            study[f] += prof[p] / len(fs)
    tech = _q(conn, "UNWIND $p AS p MATCH (:Profession {profession_id: p})-[:PERFORMS]->(:Task)-[:TASK_TECHNIQUE]->(t:Technique) "
                    "RETURN t.technique_id AS id, t.title AS title, count(*) AS n ORDER BY n DESC, id LIMIT $k", {"p": pids, "k": k})
    loops = _q(conn, "UNWIND $p AS p MATCH (:Profession {profession_id: p})-[:PERFORMS]->(:Task)-[r:TASK_LOOP]->(l:TOTELoop) "
                     "RETURN DISTINCT l.loop_id AS id, l.name AS name, r.match_method AS method LIMIT $k", {"p": pids, "k": k})
    tiers = Counter(t["tier"] for t in terms)
    share = {t: round(tiers[t] / len(terms), 3) for t in ("expert", "intermediate", "novice")}
    best = max(share.values())

    def label(items, kind):
        ids = [i["id"] for i in items]
        if not ids:
            return items
        title = {"domain": "MATCH (x:Domain) WHERE x.domain_id IN $i RETURN x.domain_id AS id, x.name AS t",
                 "prof": "MATCH (x:Profession) WHERE x.profession_id IN $i RETURN x.profession_id AS id, x.title AS t",
                 "study": "MATCH (x:StudyArea) WHERE x.study_id IN $i RETURN x.study_id AS id, x.title AS t"}[kind]
        t = {r["id"]: r["t"] for r in _q(conn, title, {"i": ids})}
        return [{**i, "title": t.get(i["id"])} for i in items]
    return {
        "terms": terms,
        "competency": {"shares": share, "label": [t for t, v in share.items() if v == best]},
        "study_areas": label(_top(study, k), "study"),
        "sectors": label(_top(by_level.get(2, {}), k, rsup), "domain"),
        "subsectors": label(_top(by_level.get(3, {}), k, rsup), "domain"),
        "industries": label(_top(by_level.get(6, {}), k, rsup), "domain"),
        "professions": label(top_prof, "prof"),
        "techniques": tech,
        "tote_loops": loops,
        "interpretations": ["R1 evidence spread evenly over a term's links", "R2 rank by distinct supporting terms, then summed evidence",
                            "R3 competency = largest tier share", "R4 ties at the cut kept", "R5 single words with Zipf >= 5.0 ignored",
                            "R6 plurals: last word tried as singular (-ies/-es/-s), full weight"],
    }
