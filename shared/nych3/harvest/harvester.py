"""Long-running, resumable batch TOTE harvester.

For every sentence of a public-domain instructional book: skip dialogue/questions,
skip non-action sentences, extract (modalities, actor, action, object/tool, perspective/
location, exit condition) per action clause, dedupe by normalized structure, and save as
`candidate` TOTE rows with repeat_count and ISBN+page SourceRefs.

At-most-once: each paragraph's ledger rows (HarvestSentence) and loop writes commit in ONE
Kuzu transaction; any sentence already in the ledger is never processed again. The JSON
checkpoint (book, next sentence offset) is only a fast-forward hint; the ledger is the
authority. Deterministic: no LLM, no network except the polite cached book fetch."""
from __future__ import annotations
import hashlib, json, signal, time
from datetime import datetime
from pathlib import Path
from ..config import SHARED, registry
from ..nlp import segmenter, analysis
from ..nlp.parser_adapter import get_parser
from ..store.tote_db import ToteDB, DEFAULT_DB
from .source import sources, fetch, paragraphs

HARVEST_DIR = SHARED / "data" / "harvest"
NON_ACTION = {"be", "have", "seem", "appear", "become", "know", "will", "would", "could", "should", "might", "may", "must",
              "can", "do", "mean", "contain", "consist", "belong", "need", "require", "cost", "weigh", "remain", "say"}
MAX_TOKENS = 80
MAX_EXITS = 10


def structure_key(action, obj, tool, actor_kind, channels, exit_kind):
    return json.dumps([action, obj or "", tool or "", actor_kind, sorted(set(channels)), exit_kind], ensure_ascii=False)


def loop_id_for(key: str) -> str:
    return "TL-H-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


class Harvester:
    def __init__(self, db_path=DEFAULT_DB, out_dir: Path = HARVEST_DIR, parser="auto", fetcher=fetch):
        self.db = ToteDB(db_path) if db_path is not None else None   # None = extraction-only worker (parallel mode)
        self.out = Path(out_dir); (self.out / "runs").mkdir(parents=True, exist_ok=True)
        self.ckpt_path = self.out / "checkpoint.json"
        self._ops = None
        self.ckpt = json.loads(self.ckpt_path.read_text()) if self.ckpt_path.exists() else {}
        self.use_spacy = False
        if parser in ("spacy", "auto"):
            try:
                from .spacy_extract import nlp as _nlp
                _nlp(); self.use_spacy = True
            except Exception:
                if parser == "spacy":
                    raise
        self.parser = get_parser("rule")
        self.lexverbs = set(registry("lexicon")["verbs"])
        self.modreg = registry("modality")
        self.fetcher = fetcher
        self.stop = False
        self.run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
        self.stats = {"run_id": self.run_id, "started": datetime.now().isoformat(timespec="seconds"), "parser": "spacy-en_core_web_sm+nych3" if self.use_spacy else self.parser.version,
                      "sentences_seen": 0, "skipped_already_processed": 0, "skipped_dialogue": 0, "skipped_question": 0,
                      "skipped_too_long": 0, "skipped_apparatus": 0, "non_action": 0, "non_action_reasons": {}, "action_sentences": 0, "action_clauses": 0, "loops_new": 0,
                      "loops_repeat": 0, "sense_attached": 0, "sense_unattached": 0, "modality_links": 0, "no_match": 0, "no_match_reasons": {}, "modality_unresolved": 0, "errors": 0,
                      "error_samples": [], "per_book": {}, "samples_new": []}

    def close(self):
        if self.db is not None:
            self.db.close()

    def _op_ids(self):
        if self._ops is None:
            self._ops = {r["c"]: r["i"] for r in self.db.q("MATCH (o:Operator) RETURN o.canonical_name AS c, o.operator_id AS i")}
        return self._ops

    def _link_modalities(self, lid, links):
        """USES_MODALITY: loop -> Operator for every action channel and every attached sense test (never a bare sense)."""
        ops = self._op_ids()
        have = {(r["o"], r["w"]) for r in self.db.q("MATCH (l:TOTELoop {loop_id:$l})-[u:USES_MODALITY]->(o:Operator) RETURN o.operator_id AS o, u.word AS w", {"l": lid})}
        n = 0
        for ln in links or []:
            oid = ops.get(ln["channel"])
            w = f"{ln['word']}|{ln.get('role', 'action')}|{ln.get('provenance', '')}"
            if oid and (oid, w) not in have:
                self.db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(o:Operator {operator_id:$o}) CREATE (l)-[:USES_MODALITY {word:$w}]->(o)",
                                  {"l": lid, "o": oid, "w": w})
                have.add((oid, w)); n += 1
        self.stats["modality_links"] += n
        return n

    # ------------------------------------------------------------ helpers
    def _seen(self, key):
        return bool(self.db.q("MATCH (h:HarvestSentence {sent_key:$k}) RETURN h.sent_key AS k", {"k": key}))

    def _save_ckpt(self):
        tmp = self.ckpt_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.ckpt, indent=1)); tmp.replace(self.ckpt_path)

    def save_stats(self):
        self.stats["updated"] = datetime.now().isoformat(timespec="seconds")
        self.stats["db_totals"] = {"loops": self.db.count(), "candidate": self.db.count("candidate"), "canonical": self.db.count("canonical")}
        (self.out / "runs" / f"{self.run_id}.json").write_text(json.dumps(self.stats, ensure_ascii=False, indent=1), encoding="utf-8")

    def _nm(self, reason):
        self.stats["no_match"] += 1
        self.stats["no_match_reasons"][reason] = self.stats["no_match_reasons"].get(reason, 0) + 1

    # ------------------------------------------------------------ extraction (pure)
    def analyse_paragraph(self, text):
        st = segmenter.structure(text)
        tagged = {s["sent_id"]: self.parser.tag(s["tokens"]) for s in analysis.iter_sentences(st)}
        scope = analysis.scope_attribution(st, tagged)
        temp = analysis.temporal(st, tagged)
        sem = analysis.semantics(st, tagged, scope, temp)
        return st, tagged, temp, sem

    def extract(self, sent, temp, sem, domain=None):
        """-> (outcome, [loop dicts], reason). Pure; no DB."""
        from .spacy_extract import is_apparatus
        app = is_apparatus(sent["text"])
        if app:
            return "skipped_apparatus", [], app
        if sent["dialogue_spans"] or any(q in sent["text"] for q in ('"', "“", "”")):
            return "skipped_dialogue", [], None
        if sent["is_question"]:
            return "skipped_question", [], None
        if sent["tokens"][-1]["text"] not in (".", "!", ";", ":", "...", "…"):
            return "non_action", [], None   # heading, ingredient or list line (no sentence terminator)
        if len(sent["tokens"]) > MAX_TOKENS:
            return "skipped_too_long", [], None
        if self.use_spacy:
            from .spacy_extract import extract as sx
            o, loops, r = sx(sent["text"], self.modreg, self.lexverbs, domain, self.stats)
            for lp in loops:
                lp["loop_id"] = loop_id_for(lp["key"])
            return o, loops, r
        evs = {e["event_id"]: e for e in temp["events"]}
        props = [p for p in sem["propositions"] if p["span"]["sent_id"] == sent["sent_id"]]
        mats = [p for p in props if p["parent_event"] is None]
        action_mats = [p for p in mats if p["lemma"] not in NON_ACTION and p["actor"]
                       and (p["mood"] == "imperative" or evs[p["event_id"]]["tense"] not in ("unresolved", None))]
        if not action_mats:
            return "non_action", [], None
        loops, reasons = [], []
        by = {p["event_id"]: p for p in props}
        for m in action_mats:
            chain = [m]
            while chain[-1]["complement_event"]:
                chain.append(by[chain[-1]["complement_event"]])
            leaf = chain[-1]
            if leaf["lemma"] in NON_ACTION:
                reasons.append("nonaction_leaf"); continue
            obj = leaf["object"]
            tool = next((l for l in leaf["locations"] if l["role"] == "instrument"), None)
            locs = [l for l in leaf["locations"] if l is not tool]
            exitc = leaf.get("exit_condition")
            if not (obj or tool or exitc):
                reasons.append("no_object_tool_or_exit"); continue
            a = m["actor"] or {}
            if a.get("rule") == "SEM-AGENTLESS-PASSIVE-IMPLIED-AGENT":
                actor_kind = "implied_agent_passive"
            elif a.get("implied"):
                actor_kind = "implied_you"
            else:
                actor_kind = "you" if a.get("head_lemma") == "you" else "agent"
            ops = [c for c in (analysis.operator_cell(x, evs[x["event_id"]], self.modreg) for x in chain) if c]
            chans = [x["channel"] for x in chain if x["channel"] and x["channel"] != "unresolved"]
            exit_kind = exitc["kind"] if exitc else "inferred_completion"
            key = structure_key(leaf["lemma"], obj["head_lemma"] if obj else None, tool["head_lemma"] if tool else None,
                                actor_kind, chans, exit_kind)
            neg = m["polarity"] == "negative"
            loops.append({
                "key": key, "loop_id": loop_id_for(key), "negated": neg,
                "row": {"modality": " ; ".join(ops) or "UNRESOLVED,",
                        "actor": {"implied_you": "you(implied),", "implied_agent_passive": "agent(implied; agentless passive),"}.get(actor_kind, f"{a.get('text') or 'UNRESOLVED'},"),
                        "action": f"{leaf['lemma']},",
                        "object": " ; ".join(x for x in [f"{obj['head']}," if obj else "", f"with {tool['head']}," if tool else ""] if x) or "UNRESOLVED,",
                        "perspective_location": " ; ".join(f"{l['prep']} {l['head']}," for l in locs) or "UNRESOLVED,",
                        "exit": (exitc["text"] + " [explicit]") if exitc else f"{leaf['lemma']}_complete == true [inferred]"},
                "lemma": leaf["lemma"], "object_lemma": obj["head_lemma"] if obj else (tool["head_lemma"] if tool else ""),
                "exit": exitc, "modality_unresolved": not ops, "mood": m["mood"], "sentence": sent["text"]})
        if not loops:
            return "no_match", [], reasons[0] if reasons else "unknown"
        return "action", loops, None

    # ------------------------------------------------------------ persistence
    def _write_loop(self, lp, book, para, ref_id, sent_key, sentence_text=""):
        lid = lp["loop_id"]
        row = self.db.get(lid)
        prov_ref = {"isbn": book["isbn"], "isbn_status": book["isbn_status"], "page": para["page"], "page_kind": para["page_kind"],
                    "fallback_gutenberg_id": book["gutenberg_id"]}
        if row is None:
            gate = {"gate_id": "G-" + lid, "file_id": "nych3.harvest.exit", "order": 1, "type": "condition",
                    "conditions": [lp["row"]["exit"]], "outcomes": {"PASS": "exit", "FAIL": "repeat"}}
            self.db.add_gate(gate)
            self.db.add_loop({
                "loop_id": lid, "name": f"{lp['lemma']} {lp['object_lemma']}".strip(), "domain": book["domain"],
                "objective": "UNRESOLVED",
                "initial_test": " ; ".join(t["step"] for t in lp.get("sense_tests", []) if t["role"] == "test") or "UNRESOLVED", "exit_predicate": gate["gate_id"], "max_iterations": -1,
                "epistemic_status": "ACT", "modality_cell": lp["row"]["modality"], "actor_cell": lp["row"]["actor"],
                "action_cell": lp["row"]["action"], "object_cell": lp["row"]["object"], "perspective_cell": lp["row"]["perspective_location"],
                "exit_gate_id": gate["gate_id"], "action_lemma": lp["lemma"], "object_lemma": lp["object_lemma"],
                "termination_triggers": ([{"trigger": lp["exit"]["text"], "condition": lp["exit"].get("condition", lp["exit"]["text"]),
                                           "provenance": lp["exit"].get("provenance", "explicit"), "rule": lp["exit"].get("rule")}] if lp["exit"] else
                                         [{"trigger": f"{lp['lemma']}_complete", "provenance": "inferred"}]),
                "techniques": [dict(t, kind="sense_test") for t in lp.get("sense_tests", [])], "version": "1", "repeat_count": 1, "structure_key": lp["key"],
                "in_domain": [[book["domain"], "primary", "harvested"]]},
                status="candidate", provenance={"source": "nych3 batch harvester", "method": "HARVEST-BATCH-1", "authority": None,
                                                "first_ref": prov_ref})
            new = True
        else:
            trig = row["termination_triggers"] or []
            if lp["exit"] and len(trig) < MAX_EXITS and all(t["trigger"] != lp["exit"]["text"] for t in trig):
                trig.append({"trigger": lp["exit"]["text"], "provenance": lp["exit"].get("provenance", "explicit")})
            self.db.c.execute("MATCH (l:TOTELoop {loop_id:$l}) SET l.repeat_count = l.repeat_count + 1, l.termination_triggers=$t",
                              {"l": lid, "t": json.dumps(trig, ensure_ascii=False)})
            if not self.db.q("MATCH (l:TOTELoop {loop_id:$l})-[:IN_DOMAIN]->(d:Domain {domain_id:$d}) RETURN d.domain_id AS d",
                             {"l": lid, "d": book["domain"]}):
                if not self.db.q("MATCH (d:Domain {domain_id:$d}) RETURN d.domain_id AS d", {"d": book["domain"]}):
                    self.db.c.execute("CREATE (:Domain {domain_id:$d,name:$d})", {"d": book["domain"]})
                self.db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(d:Domain {domain_id:$d}) CREATE (l)-[:IN_DOMAIN {role:'cross_link',evidence:'same structure harvested in another domain',provenance:'harvester'}]->(d)",
                                  {"l": lid, "d": book["domain"]})
            new = False
        self._link_modalities(lid, lp.get("modality_links"))
        self.db.c.execute("CREATE (:SourceRef {ref_id:$r,isbn:$i,isbn_status:$s,page:$p,page_kind:$k,page_method:$m,fallback_gutenberg_id:$g,sent_key:$sk,sentence_text:$t,flags:$f})",
                          dict(r=ref_id, i=book["isbn"] or "", s=book["isbn_status"], p=para["page"], k=para["page_kind"],
                               m=para["page_method"], g=str(book["gutenberg_id"]), sk=sent_key, t=sentence_text,
                               f=[x for x in (("isbn_null_gutenberg_fallback" if not book["isbn"] else ""),
                                              ("page_derived" if para["page_kind"] != "printed" else "")) if x]))
        self.db.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(s:SourceRef {ref_id:$r}) CREATE (l)-[:SOURCED_FROM]->(s)", {"l": lid, "r": ref_id})
        return new

    # ------------------------------------------------------------ main loop
    def run_book(self, book, max_sentences=None, deadline=None):
        bid = book["book_id"]
        paras = paragraphs(self.fetcher(book), book)
        start = self.ckpt.get(bid, {}).get("next_offset", 0)
        pb = self.stats["per_book"].setdefault(bid, {"sentences_seen": 0, "loops_new": 0, "loops_repeat": 0, "action_sentences": 0})
        offset = 0
        for para in paras:
            if self.stop or (deadline and time.time() > deadline) or (max_sentences and self.stats["sentences_seen"] >= max_sentences):
                return False
            try:
                st, tagged, temp, sem = self.analyse_paragraph(para["text"])
                sents = list(analysis.iter_sentences(st))
            except Exception as e:  # count, never crash the long run
                self.stats["errors"] += 1
                if len(self.stats["error_samples"]) < 10:
                    self.stats["error_samples"].append({"book": bid, "para_idx": para["para_idx"], "error": repr(e)[:200]})
                continue  # offsets for an unparseable paragraph are not assigned; deterministic on re-run
            if offset + len(sents) <= start:
                offset += len(sents); continue
            self.db.c.execute("BEGIN TRANSACTION")
            try:
                for s in sents:
                    key = f"{bid}:{offset}"
                    offset += 1
                    if self._seen(key):
                        self.stats["skipped_already_processed"] += 1; continue
                    self.stats["sentences_seen"] += 1; pb["sentences_seen"] += 1
                    try:
                        outcome, loops, reason = self.extract(dict(s, tokens=tagged[s["sent_id"]]), temp, sem, book.get("domain"))
                    except Exception as e:
                        outcome, loops, reason = "error", [], repr(e)[:200]
                        self.stats["errors"] += 1
                        if len(self.stats["error_samples"]) < 10:
                            self.stats["error_samples"].append({"sent_key": key, "error": reason})
                    if outcome in ("skipped_dialogue", "skipped_question", "skipped_too_long", "skipped_apparatus", "non_action"):
                        self.stats[outcome] += 1
                        if outcome == "non_action" and reason:
                            self.stats["non_action_reasons"][reason] = self.stats["non_action_reasons"].get(reason, 0) + 1
                    elif outcome == "no_match":
                        self.stats["action_sentences"] += 1; pb["action_sentences"] += 1; self._nm(reason)
                    elif outcome == "action":
                        self.stats["action_sentences"] += 1; pb["action_sentences"] += 1
                        for n, lp in enumerate(loops):
                            self.stats["action_clauses"] += 1
                            self.stats["modality_unresolved"] += lp["modality_unresolved"]
                            new = self._write_loop(lp, book, para, f"{key}#{n}", key, s["text"])
                            k = "loops_new" if new else "loops_repeat"
                            self.stats[k] += 1; pb[k] += 1
                            if new and len(self.stats["samples_new"]) < 40:
                                self.stats["samples_new"].append({"loop_id": lp["loop_id"], "row": lp["row"], "sentence": lp["sentence"],
                                                                  "isbn": book["isbn"], "page": para["page"], "page_kind": para["page_kind"],
                                                                  "gutenberg_id": book["gutenberg_id"]})
                    self.db.c.execute("CREATE (:HarvestSentence {sent_key:$k,book_id:$b,sent_offset:$o,outcome:$u})",
                                      dict(k=key, b=bid, o=offset - 1, u=outcome))
                self.db.c.execute("COMMIT")
            except Exception:
                self.db.c.execute("ROLLBACK")
                raise
            self.ckpt[bid] = {"next_offset": offset, "done": False}
            self._save_ckpt()
            if self.stats["sentences_seen"] % 500 < len(sents):
                self.save_stats()
        self.ckpt[bid] = {"next_offset": offset, "done": True}
        self._save_ckpt()
        return True

    def run(self, book_ids=None, max_sentences=None, max_seconds=None, books=None):
        signal.signal(signal.SIGTERM, lambda *a: setattr(self, "stop", True))
        signal.signal(signal.SIGINT, lambda *a: setattr(self, "stop", True))
        deadline = time.time() + max_seconds if max_seconds else None
        books = [b for b in (books or sources()["books"]) if not book_ids or b["book_id"] in book_ids]
        for b in books:
            if self.ckpt.get(b["book_id"], {}).get("done"):
                continue
            if not self.run_book(b, max_sentences, deadline):
                break
        self.stats["domain_links"] = self.db.refresh_domain_links()
        self.stats["finished"] = datetime.now().isoformat(timespec="seconds")
        self.stats["stopped_by"] = "signal" if self.stop else ("limit" if (max_sentences or max_seconds) else "complete")
        self.save_stats()
        return self.stats
