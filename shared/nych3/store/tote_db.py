"""Kuzu TOTE store (knowledge-graph style). Lookup is EXACT on structured keys:
(action_lemma, object_lemma), then a row that explicitly declares object_lemma='*'.
Nothing else. No word overlap, no nearest match: otherwise NO_MATCH + a harvest
candidate row (status=candidate, with provenance). Canonical rows are only written
with a named authority; nothing is auto-promoted."""
from __future__ import annotations
import json, re, shutil
from pathlib import Path
import kuzu
from ..config import CONFIG, KG_SCHEMA, SHARED

SCHEMA = KG_SCHEMA
SEED = SHARED / "data" / "tote_seed.json"
DEFAULT_DB = SHARED / "data" / "tote.kuzu"
COLS = ["loop_id", "name", "domain", "objective", "initial_test", "exit_predicate", "max_iterations", "epistemic_status",
        "modality_cell", "actor_cell", "action_cell", "object_cell", "perspective_cell", "exit_gate_id", "action_lemma",
        "object_lemma", "termination_triggers", "techniques", "status", "provenance", "version", "repeat_count", "structure_key"]
JSON_COLS = {"termination_triggers", "techniques", "provenance"}
STATUSES = ("candidate", "canonical")


def schema_statements(path: Path = SCHEMA):
    s = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    s = re.sub(r"//[^\n]*", "", s)
    return [x.strip() for x in s.split(";") if x.strip()]


_ATTACHED: dict = {}


class ToteDB:
    @classmethod
    def on_connection(cls, conn, path=None):
        """Wrap an already-open Kuzu connection (the shared knowledge-graph store). Registered by path so
        encoder stages reuse it instead of opening a second Database on the same file (Kuzu forbids that)."""
        self = cls.__new__(cls)
        self.path, self.db, self.c = (Path(path) if path else None), None, conn
        if path:
            _ATTACHED[str(Path(path))] = self
        return self

    @classmethod
    def open(cls, path):
        return _ATTACHED.get(str(Path(path))) or cls(path)

    @staticmethod
    def detach(path):
        _ATTACHED.pop(str(Path(path)), None)

    def __init__(self, path: str | Path = DEFAULT_DB, rebuild: bool = False, seed: bool = True, read_only: bool = False):
        self.path = Path(path)
        if rebuild:
            shutil.rmtree(self.path, ignore_errors=True)
            if self.path.exists():
                self.path.unlink()
        fresh = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.path), read_only=read_only and not fresh)
        self.c = kuzu.Connection(self.db)
        if fresh:
            for q in schema_statements():
                self.c.execute(q)
            if seed:
                self.load_seed()

    def close(self):
        """Release the Kuzu handle (required before reopening the same path in-process)."""
        if self.db is None:      # borrowed connection: owner closes it
            return
        try:
            self.c.close(); self.db.close()
        except Exception:
            pass

    def q(self, cypher, params=None):
        r = self.c.execute(cypher, params or {})
        cols = r.get_column_names()
        out = []
        while r.has_next():
            out.append(dict(zip(cols, r.get_next())))
        return out

    # ------------------------------------------------------------- writes
    def load_seed(self, seed_path: Path = SEED):
        d = json.loads(seed_path.read_text(encoding="utf-8"))
        for op in d["operators"]:
            self.c.execute("CREATE (:Operator {operator_id:$a,symbol:$b,canonical_name:$c,evidence_channel:$d,may_assert_action:$e})",
                           dict(zip("abcde", op)))
        for dom in d["domains"]:
            self.c.execute("CREATE (:Domain {domain_id:$a,name:$a})", {"a": dom})
        for g in d["gates"]:
            self.add_gate(g)
        for row in d["loops"]:
            self.add_loop(row, status=row["status"], provenance=row["provenance"])
        self.load_measures()

    def load_measures(self, path: Path = CONFIG / "invariants" / "measures.json"):
        """Master measures list -> Measure / MeasureRule / MEASURE_WEIGHT_IN(Domain). Weights stay ordered classes (assumed_prior)."""
        m = json.loads(path.read_text(encoding="utf-8"))
        src = m["weight_source"]
        for rank, r in enumerate(m["context_rules"]):
            self.c.execute("CREATE (:MeasureRule {rule_id:$i,rank:$r,pattern:$p,effect:$e})", dict(i=r["rule_id"], r=rank, p=r["pattern"], e=r["effect"]))
        rev = {v: k for k, v in m.get("domain_aliases", {}).items()}
        for w, e in m["entries"].items():
            self.c.execute("CREATE (:Measure {word:$w,kind:$k,sense_weight:$s,weight_source:$src})", dict(w=w, k=e["kind"], s=e["sense_weight"], src=src))
            for alias, wt in (e.get("domains") or {}).items():
                dom = rev.get(alias, alias)
                if not self.q("MATCH (d:Domain {domain_id:$d}) RETURN d.domain_id AS d", {"d": dom}):
                    self.c.execute("CREATE (:Domain {domain_id:$a,name:$a})", {"a": dom})
                self.c.execute("MATCH (x:Measure {word:$w}),(d:Domain {domain_id:$d}) CREATE (x)-[:MEASURE_WEIGHT_IN {sense_weight:$s,weight_source:$src}]->(d)",
                               dict(w=w, d=dom, s=wt, src=src))

    def refresh_domain_links(self):
        """Derive DOMAIN_LINK edges from loops that sit in >1 domain (cross-domain commonality). Idempotent."""
        self.c.execute("MATCH (:Domain)-[r:DOMAIN_LINK]->(:Domain) DELETE r")
        pairs = self.q("MATCH (a:Domain)<-[:IN_DOMAIN]-(l:TOTELoop)-[:IN_DOMAIN]->(b:Domain) WHERE a.domain_id < b.domain_id "
                       "RETURN a.domain_id AS a, b.domain_id AS b, count(DISTINCT l) AS n")
        for p in pairs:
            self.c.execute("MATCH (a:Domain {domain_id:$a}),(b:Domain {domain_id:$b}) CREATE (a)-[:DOMAIN_LINK {kind:'shared_loops',shared_loops:$n,evidence:'loops IN_DOMAIN of both',provenance:'derived'}]->(b)", p)
        return pairs

    def add_gate(self, g):
        self.c.execute("CREATE (:Gate {gate_id:$i,file_id:$f,`order`:$o,type:$t,conditions:$c,outcomes:$u})",
                       dict(i=g["gate_id"], f=g["file_id"], o=g["order"], t=g["type"], c=g["conditions"], u=json.dumps(g["outcomes"])))

    def add_loop(self, row, *, status: str, provenance: dict):
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if status == "canonical" and not (provenance or {}).get("authority"):
            raise ValueError("canonical TOTE rows need a named authority in provenance (no auto-promotion)")
        if not provenance or not provenance.get("source"):
            raise ValueError("every TOTE row needs provenance.source")
        rec = {k: row.get(k) for k in COLS}
        rec.update(status=status, provenance=provenance)
        rec["max_iterations"] = int(rec.get("max_iterations") or -1)
        rec["repeat_count"] = int(rec.get("repeat_count") or 0)
        for k in JSON_COLS:
            rec[k] = json.dumps(rec[k] if rec[k] is not None else [], ensure_ascii=False)
        rec = {k: ("" if v is None else v) for k, v in rec.items()}
        self.c.execute("CREATE (:TOTELoop {" + ",".join(f"{k}:${k}" for k in COLS) + "})", rec)
        for dom, role, ev in row.get("in_domain", [[row["domain"], "primary", ""]]):
            if not self.q("MATCH (d:Domain {domain_id:$d}) RETURN d.domain_id AS d", {"d": dom}):
                self.c.execute("CREATE (:Domain {domain_id:$a,name:$a})", {"a": dom})
            self.c.execute("MATCH (l:TOTELoop {loop_id:$l}),(d:Domain {domain_id:$d}) CREATE (l)-[:IN_DOMAIN {role:$r,evidence:$e,provenance:$p}]->(d)",
                           dict(l=row["loop_id"], d=dom, r=role, e=ev, p=rec["provenance"]))
        if row.get("exit_gate_id"):
            self.c.execute("MATCH (g:Gate {gate_id:$g}),(l:TOTELoop {loop_id:$l}) CREATE (g)-[:GUARDS]->(l)",
                           dict(g=row["exit_gate_id"], l=row["loop_id"]))

    def promote(self, loop_id: str, authority: str, note: str = ""):
        """Candidate -> canonical. Requires a named authority. Never called automatically."""
        if not authority or not authority.strip():
            raise ValueError("promotion requires a named authority")
        row = self.get(loop_id)
        if row is None:
            raise KeyError(loop_id)
        prov_ = dict(row["provenance"] or {})
        prov_.setdefault("promotions", []).append({"to": "canonical", "authority": authority, "note": note})
        prov_["authority"] = authority
        self.c.execute("MATCH (l:TOTELoop {loop_id:$l}) SET l.status='canonical', l.provenance=$p",
                       {"l": loop_id, "p": json.dumps(prov_, ensure_ascii=False)})

    def suggest_promotions(self, min_repeats: int = 5, min_sources: int = 2):
        """SUGGESTION ONLY (not applied): candidates seen >= min_repeats times from >= min_sources distinct books."""
        return self.q("MATCH (l:TOTELoop)-[:SOURCED_FROM]->(s:SourceRef) WHERE l.status='candidate' "
                      "WITH l, count(DISTINCT s.fallback_gutenberg_id) AS books "
                      "WHERE l.repeat_count >= $r AND books >= $b "
                      "RETURN l.loop_id AS loop_id, l.name AS name, l.repeat_count AS repeats, books ORDER BY repeats DESC",
                      {"r": min_repeats, "b": min_sources})

    def harvest(self, candidate: dict):
        """Persist a harvested candidate row (from natural language). Always status=candidate."""
        if candidate.get("status") not in (None, "candidate"):
            raise ValueError("harvested rows are always candidates")
        if self.q("MATCH (l:TOTELoop {loop_id:$l}) RETURN l.loop_id AS l", {"l": candidate["loop_id"]}):
            return False
        if candidate.get("exit_gate") and not self.q("MATCH (g:Gate {gate_id:$g}) RETURN g.gate_id AS g", {"g": candidate["exit_gate"]["gate_id"]}):
            self.add_gate(candidate["exit_gate"])
        self.add_loop(candidate, status="candidate", provenance=candidate["provenance"])
        return True

    # ------------------------------------------------------------- reads
    def _row(self, r):
        out = {k: r[f"l.{k}"] for k in COLS}
        for k in JSON_COLS:
            out[k] = json.loads(out[k]) if out[k] else None
        return out

    def get(self, loop_id):
        rows = self.q("MATCH (l:TOTELoop {loop_id:$l}) RETURN " + ",".join(f"l.{k}" for k in COLS), {"l": loop_id})
        return self._row(rows[0]) if rows else None

    def gate(self, gate_id):
        r = self.q("MATCH (g:Gate {gate_id:$g}) RETURN g.gate_id AS gate_id, g.file_id AS file_id, g.`order` AS `order`, g.type AS type, g.conditions AS conditions, g.outcomes AS outcomes", {"g": gate_id})
        if not r:
            return None
        r = r[0]; r["outcomes"] = json.loads(r["outcomes"]); return r

    def lookup(self, action_lemma: str, object_lemma: str | None):
        """Exact structured lookup. Returns {'match': row|None, 'method': ..., 'key': ...}."""
        ret = ",".join(f"l.{k}" for k in COLS)
        order = "ORDER BY CASE l.status WHEN 'canonical' THEN 0 ELSE 1 END, l.loop_id"
        if object_lemma:
            r = self.q(f"MATCH (l:TOTELoop) WHERE l.action_lemma=$a AND l.object_lemma=$o RETURN {ret} {order}",
                       {"a": action_lemma, "o": object_lemma})
            if r:
                return {"match": self._row(r[0]), "method": "exact_action_object", "key": [action_lemma, object_lemma],
                        "alternatives": [x["l.loop_id"] for x in r[1:]]}
        r = self.q(f"MATCH (l:TOTELoop) WHERE l.action_lemma=$a AND l.object_lemma='*' RETURN {ret} {order}", {"a": action_lemma})
        if r:
            return {"match": self._row(r[0]), "method": "exact_action_declared_wildcard_object", "key": [action_lemma, "*"],
                    "alternatives": [x["l.loop_id"] for x in r[1:]]}
        return {"match": None, "method": "NO_MATCH", "key": [action_lemma, object_lemma], "alternatives": []}

    def domains_of(self, loop_id):
        return self.q("MATCH (l:TOTELoop {loop_id:$l})-[r:IN_DOMAIN]->(d:Domain) RETURN d.domain_id AS domain, r.role AS role ORDER BY d.domain_id", {"l": loop_id})

    def commonality(self):
        """Loops shared across >1 domain = cross-links (the 5th dimension)."""
        return self.q("MATCH (l:TOTELoop)-[:IN_DOMAIN]->(d:Domain) WITH l, collect(d.domain_id) AS ds WHERE size(ds) > 1 "
                      "RETURN l.loop_id AS loop_id, ds AS domains ORDER BY loop_id")

    def count(self, status=None):
        if status:
            return self.q("MATCH (l:TOTELoop) WHERE l.status=$s RETURN count(l) AS n", {"s": status})[0]["n"]
        return self.q("MATCH (l:TOTELoop) RETURN count(l) AS n")[0]["n"]


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build the seed TOTE Kuzu DB")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    a = ap.parse_args()
    db = ToteDB(a.db, rebuild=True)
    print(f"built {a.db}: {db.count()} loops ({db.count('canonical')} canonical, {db.count('candidate')} candidate); commonality={db.commonality()}")


if __name__ == "__main__":
    main()
