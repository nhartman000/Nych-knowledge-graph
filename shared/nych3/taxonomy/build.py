"""Stage 06: load the domain taxonomy and vernacular into the shared Kùzu store.

Owner, 2026-11-23, verbatim: "I need to build a private knowledge graph that handles the domain subdomain function
technique tote loop that can connect to the tote loop database. it should be the extensive word associations between
professions domains and vernaculars", "top top top level domains are university areas of study like liberal arts
medical law science math government military sports religion etc..", "this has to mergwe into the nych knowledge graph
and serve as the ultimate tool for the model to do its shortcutting".

Hierarchy (edges point child -> parent):
  StudyArea  CIP 2020 family (2 digits) > series (4) > program (6)          STUDY_PARENT
  Domain     NAICS 2022 sector > subsector > ... > industry (6 digits)     DOMAIN_PARENT
  WorkFunction  O*NET GWA > IWA                                            FUNCTION_PARENT
  Technique  O*NET DWA                                                     TECHNIQUE_OF -> IWA
  Task       O*NET task statement                                          TASK_TECHNIQUE -> DWA
  TOTELoop   existing loops, linked only by exact action/object lemma      TASK_LOOP (never nearest)
Professions (O*NET occupations) join StudyArea (CIP->SOC crosswalk), Task (PERFORMS) and Domain (WORKS_IN, BLS OEWS
May 2025 national industry-by-occupation employment and share at every industry level). Terms join Domain and Profession with their tier.

Term tiers: expert / intermediate / novice by everyday-English Zipf frequency from wordfreq 3.1.1 (pinned),
recomputed here for every term; the upstream vocabulary's own tier column is not used.
Deterministic, no LLM. Inputs are files pinned by SHA-256 in _config/registries/taxonomy_sources.json.
"""
from __future__ import annotations

import csv
import io
import json

import zipfile
from collections import defaultdict
from pathlib import Path
import gzip

from nych3.taxonomy.xlsx import rows as xlsx_rows

BATCH = 5000


def _onet(zip_path: Path, name: str) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        member = next(m for m in z.namelist() if m.endswith("/" + name))
        return list(csv.DictReader(io.StringIO(z.read(member).decode("utf-8")), delimiter="\t"))


# ---------------------------------------------------------------- parsers (pure; unit-tested)

def naics_nodes(codes_xlsx: Path, descriptions_xlsx: Path | None) -> list[dict]:
    nodes = {}
    for r in xlsx_rows(codes_xlsx)[1:]:
        if len(r) >= 3 and r[1].strip():
            nodes[r[1].strip()] = {"code": r[1].strip(), "title": r[2].strip(), "parent": None, "description": ""}
    sector_of = {}
    for code in nodes:
        if "-" in code:
            lo, hi = code.split("-")
            for n in range(int(lo), int(hi) + 1):
                sector_of[str(n)] = code
    for code, node in nodes.items():
        node["level"] = len(code.split("-")[0])
        if "-" in code or len(code) == 2:
            continue
        parent = next((code[:cut] for cut in range(len(code) - 1, 1, -1) if code[:cut] in nodes), None)
        node["parent"] = parent or sector_of.get(code[:2])
    if descriptions_xlsx:
        for r in xlsx_rows(descriptions_xlsx)[1:]:
            if len(r) >= 3 and r[0].strip() in nodes:
                nodes[r[0].strip()]["description"] = r[2].split("Cross-References")[0].strip()
    return list(nodes.values())


def cip_nodes(cip_csv: Path) -> list[dict]:
    out = []
    with open(cip_csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = r["CIPCode"].strip('="')
            title = r["CIPTitle"].strip().rstrip(".")
            action = (r.get("Action") or "").lower()
            if title.lower().startswith("reserved") or action.startswith(("moved", "deleted")):
                continue
            digits = len(code.replace(".", ""))
            parent = None if digits == 2 else code[:2] if digits == 4 else code[:5]
            out.append({"code": code, "level": digits, "title": title, "definition": r["CIPDefinition"].strip(),
                        "parent": parent})
    return out


def cip_soc(crosswalk_xlsx: Path) -> list[tuple[str, str]]:
    rows = xlsx_rows(crosswalk_xlsx, "CIP-SOC")
    head = rows[0]
    ci, si = head.index("CIP2020Code"), head.index("SOC2018Code")
    return [(r[ci].strip(), r[si].strip()) for r in rows[1:] if len(r) > si and r[si].strip() and r[si] != "99-9999"]


_SKIP_OBJ = {"it", "them", "this", "that", "which", "what", "something"}


def task_lemmas(texts: list[str], nlp=None) -> list[tuple[str, str]]:
    """(action lemma, object lemma) per task: the sentence root verb and its direct object; '' when absent."""
    if nlp is None:
        return [("", "")] * len(texts)
    out = []
    for doc in nlp.pipe(texts, batch_size=256):
        root = next((t for t in doc if t.dep_ == "ROOT"), None)
        if root is None or root.pos_ != "VERB":
            out.append(("", ""))
            continue
        obj = next((c for c in root.children if c.dep_ in ("dobj", "obj")), None)
        o = obj.lemma_.lower() if obj is not None and obj.lemma_.lower() not in _SKIP_OBJ else ""
        out.append((root.lemma_.lower(), o))
    return out


EXPERT_BELOW, NOVICE_FROM = 3.0, 4.0  # van Heuven et al. (2014) Zipf bands: 1-3 low, 4-7 high frequency


def everyday_zipf(term: str) -> float:
    """General-English Zipf frequency from wordfreq (subtitles, Wikipedia, web, books; data CC BY-SA 4.0).
    Replaces the Common Corpus count used upstream, which over-counts legal and government words."""
    from wordfreq import zipf_frequency

    return round(zipf_frequency(term, "en"), 3)


def tier(z: float) -> str:
    if z < EXPERT_BELOW:
        return "expert"
    return "novice" if z >= NOVICE_FROM else "intermediate"


def read_terms(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# ---------------------------------------------------------------- writer

class Loader:
    def __init__(self, conn):
        self.c = conn
        self.counts = defaultdict(int)

    def nodes(self, table: str, rows: list[dict]):
        if not rows:
            return
        key, *rest = list(rows[0])
        q = f"UNWIND $rows AS r MERGE (n:{table} {{{key}: r.{key}}})"
        if rest:
            q += " SET " + ", ".join(f"n.{k} = r.{k}" for k in rest)
        for i in range(0, len(rows), BATCH):
            self.c.execute(q, {"rows": rows[i:i + BATCH]})
        self.counts[table] += len(rows)

    def rels(self, rel: str, a: tuple[str, str], b: tuple[str, str], rows: list[dict]):
        """rows: {'a': key, 'b': key, ...props}. a/b = (table, key property)."""
        if not rows:
            return
        props = [k for k in rows[0] if k not in ("a", "b")]
        body = ("{" + ", ".join(f"{k}: r.{k}" for k in props) + "}") if props else ""
        q = (f"UNWIND $rows AS r MATCH (x:{a[0]} {{{a[1]}: r.a}}), (y:{b[0]} {{{b[1]}: r.b}}) "
             f"CREATE (x)-[:{rel} {body}]->(y)")
        for i in range(0, len(rows), BATCH):
            self.c.execute(q, {"rows": rows[i:i + BATCH]})
        self.counts[rel] += len(rows)


def build(conn, src: dict, nlp=None) -> dict:
    """src keys: naics_codes, naics_descriptions, onet_zip, cip_csv, cip_soc_xlsx, vocab_tsv, glossary_tsv, tld_tsv,
    oews_tsv (BLS OEWS profession x industry, from nych3.taxonomy.oews)."""
    L = Loader(conn)
    # Domains (NAICS)
    naics = naics_nodes(Path(src["naics_codes"]), Path(src["naics_descriptions"]))
    L.nodes("Domain", [{"domain_id": f"naics:{n['code']}", "name": n["title"], "kind": "naics", "code": n["code"],
                        "level": n["level"], "description": n["description"]} for n in naics])
    L.rels("DOMAIN_PARENT", ("Domain", "domain_id"), ("Domain", "domain_id"),
           [{"a": f"naics:{n['code']}", "b": f"naics:{n['parent']}"} for n in naics if n["parent"]])
    # Study areas (CIP)
    cip = cip_nodes(Path(src["cip_csv"]))
    have = {c["code"] for c in cip}
    L.nodes("StudyArea", [{"study_id": f"cip:{c['code']}", "code": c["code"], "level": c["level"], "title": c["title"],
                           "definition": c["definition"]} for c in cip])
    L.rels("STUDY_PARENT", ("StudyArea", "study_id"), ("StudyArea", "study_id"),
           [{"a": f"cip:{c['code']}", "b": f"cip:{c['parent']}"} for c in cip if c["parent"] in have])
    # Professions (O*NET)
    occ = _onet(Path(src["onet_zip"]), "Occupation Data.txt")
    L.nodes("Profession", [{"profession_id": f"onet:{o['O*NET-SOC Code']}", "soc_code": o["O*NET-SOC Code"][:7],
                            "title": o["Title"].strip(), "description": o["Description"].strip()} for o in occ])
    by_soc = defaultdict(list)
    for o in occ:
        by_soc[o["O*NET-SOC Code"][:7]].append(f"onet:{o['O*NET-SOC Code']}")
    pairs = {(f"cip:{c}", p) for c, s in cip_soc(Path(src["cip_soc_xlsx"])) if c in have for p in by_soc.get(s, [])}
    L.rels("STUDY_LEADS_TO", ("StudyArea", "study_id"), ("Profession", "profession_id"),
           [{"a": a, "b": b, "source": "NCES CIP2020-SOC2018 crosswalk"} for a, b in sorted(pairs)])
    # Functions and techniques (O*NET work activities)
    names = {r["Element ID"]: r["Element Name"] for r in _onet(Path(src["onet_zip"]), "Content Model Reference.txt")}
    g2i = _onet(Path(src["onet_zip"]), "GWAs to IWAs.txt")
    gwas = sorted({r["GWA Element ID"] for r in g2i})
    L.nodes("WorkFunction", [{"function_id": f"gwa:{g}", "level": "GWA", "title": names.get(g, g)} for g in gwas]
            + [{"function_id": f"iwa:{r['IWA Element ID']}", "level": "IWA", "title": r["IWA Element Name"]} for r in g2i])
    L.rels("FUNCTION_PARENT", ("WorkFunction", "function_id"), ("WorkFunction", "function_id"),
           [{"a": f"iwa:{r['IWA Element ID']}", "b": f"gwa:{r['GWA Element ID']}"} for r in g2i])
    dwa = {r["DWA Element ID"]: r for r in _onet(Path(src["onet_zip"]), "GWAs to IWAs to DWAs.txt")}
    L.nodes("Technique", [{"technique_id": f"dwa:{k}", "title": r["DWA Element Name"]} for k, r in dwa.items()])
    L.rels("TECHNIQUE_OF", ("Technique", "technique_id"), ("WorkFunction", "function_id"),
           [{"a": f"dwa:{k}", "b": f"iwa:{r['IWA Element ID']}"} for k, r in dwa.items()])
    # Tasks
    tasks = _onet(Path(src["onet_zip"]), "Task Statements.txt")
    lem = task_lemmas([t["Task"] for t in tasks], nlp)
    L.nodes("Task", [{"task_id": f"task:{t['Task ID']}", "text": t["Task"].strip(), "task_type": t["Task Type"],
                      "action_lemma": a, "object_lemma": o} for t, (a, o) in zip(tasks, lem)])
    L.rels("PERFORMS", ("Profession", "profession_id"), ("Task", "task_id"),
           [{"a": f"onet:{t['O*NET-SOC Code']}", "b": f"task:{t['Task ID']}"} for t in tasks])
    known_tasks = {t["Task ID"] for t in tasks}
    L.rels("TASK_TECHNIQUE", ("Task", "task_id"), ("Technique", "technique_id"),
           [{"a": f"task:{r['Task ID']}", "b": f"dwa:{r['DWA Element ID']}"}
            for r in _onet(Path(src["onet_zip"]), "Tasks to DWAs.txt") if r["Task ID"] in known_tasks and r["DWA Element ID"] in dwa])
    # Task -> existing TOTE loops: exact action+object, then action + declared wildcard object. Never nearest.
    loops = conn.execute("MATCH (l:TOTELoop) RETURN l.loop_id, l.action_lemma, l.object_lemma")
    exact, wild = defaultdict(list), defaultdict(list)
    while loops.has_next():
        lid, a, o = loops.get_next()
        if a:
            (wild[a] if o == "*" else exact[(a, o)]).append(lid)
    links = []
    for t, (a, o) in zip(tasks, lem):
        if a and o and exact.get((a, o)):
            links += [{"a": f"task:{t['Task ID']}", "b": l, "match_method": "exact_action_object"} for l in exact[(a, o)]]
        elif a and wild.get(a):
            links += [{"a": f"task:{t['Task ID']}", "b": l, "match_method": "exact_action_declared_wildcard_object"}
                      for l in wild[a]]
    L.rels("TASK_LOOP", ("Task", "task_id"), ("TOTELoop", "loop_id"), links)
    # Subject TLDs
    with open(src["tld_tsv"], encoding="utf-8") as f:
        tld = [r for r in csv.DictReader(f, delimiter="\t") if r.get("naics_codes")]
    L.nodes("SubjectTLD", [{"tld": r["tld"].strip().lower()} for r in tld])
    codes = {n["code"] for n in naics}
    L.rels("TLD_OF", ("SubjectTLD", "tld"), ("Domain", "domain_id"),
           [{"a": r["tld"].strip().lower(), "b": f"naics:{c}", "source": "b4-subject-tlds-naics.v1"}
            for r in tld for c in r["naics_codes"].split(";") if c in codes])
    # Vernacular terms
    vocab, gloss = read_terms(Path(src["vocab_tsv"])), read_terms(Path(src["glossary_tsv"]))
    terms = {}
    for r in vocab + gloss:
        if r["term"] not in terms:
            z = everyday_zipf(r["term"])
            terms[r["term"]] = {"term": r["term"], "zipf": z, "tier": tier(z)}
    L.nodes("Term", list(terms.values()))
    profs = {f"onet:{o['O*NET-SOC Code']}" for o in occ}
    domains = {f"naics:{c}" for c in codes}
    td, tp = {}, {}
    for r in vocab:
        key = (r["term"], r["domain"])
        row = {"a": r["term"], "b": r["domain"], "tier": terms[r["term"]]["tier"], "weight": float(r["tfidf"]), "source": "d4-vocabulary.v1"}
        if r["domain"] in profs:
            tp.setdefault(key, row)
        elif r["domain"] in domains:
            td.setdefault(key, row)
    for r in gloss:
        key = (r["term"], r["domain"])
        if r["domain"] in domains and key not in td:
            td[key] = {"a": r["term"], "b": r["domain"], "tier": terms[r["term"]]["tier"], "weight": 1.0,
                       "source": "d4-glossary.v1 " + r["sources"].split(" ")[0]}
    L.rels("TERM_DOMAIN", ("Term", "term"), ("Domain", "domain_id"), list(td.values()))
    L.rels("TERM_PROFESSION", ("Term", "term"), ("Profession", "profession_id"), list(tp.values()))
    # Profession -> industry: BLS OEWS May 2025 national industry-by-occupation estimates (all industry levels)
    if src.get("oews_tsv"):
        rows, missing = [], set()
        for r in read_terms(Path(src["oews_tsv"])):
            if f"naics:{r['naics_code']}" not in domains:
                missing.add(r["naics_code"])
                continue
            emp = float(r["tot_emp"]) if r["tot_emp"] else None
            share = float(r["pct_total"]) if r["pct_total"] else None
            rows += [{"a": p, "b": f"naics:{r['naics_code']}", "employment": emp, "share": share,
                      "source": "BLS OEWS May 2025 national"} for p in by_soc.get(r["soc_code"], [])]
        L.rels("WORKS_IN", ("Profession", "profession_id"), ("Domain", "domain_id"), rows)
        L.counts["oews_industry_codes_not_in_naics_2022"] = len(missing)
    return dict(L.counts)


def load_sources(registry: Path, data_dir: Path) -> dict:
    """Paths of the pinned inputs, after checking each SHA-256 against the registry."""
    import hashlib

    reg = json.loads(Path(registry).read_text())
    out = {}
    for key, item in reg["inputs"].items():
        p = Path(data_dir) / item["file"]
        if not p.exists():
            if item.get("optional"):
                continue
            raise FileNotFoundError(f"{p} missing (fetch with: python -m nych3.taxonomy.cli fetch)")
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"{p.name}: sha256 {digest} != pinned {item['sha256']}")
        out[key] = p
    return out



