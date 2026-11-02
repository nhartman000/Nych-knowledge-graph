"""Kuzu TOTE store (knowledge-graph style). Lookup is EXACT on structured keys:
(action_lemma, object_lemma), then a row that explicitly declares object_lemma='*'.
Nothing else. No word overlap, no nearest match: otherwise NO_MATCH + a harvest
candidate row (status=candidate, with provenance). Canonical rows are only written
with a named authority; nothing is auto-promoted."""
from __future__ import annotations
import json, re, shutil
from pathlib import Path
import kuzu
from ..config import SCHEMAS, SHARED

SCHEMA = SCHEMAS / "tote_kuzu.cypher"
SEED = SHARED / "data" / "tote_seed.json"
DEFAULT_DB = SHARED / "data" / "tote.kuzu"
COLS = ["loop_id", "name", "domain", "objective", "initial_test", "exit_predicate", "max_iterations", "epistemic_status",
        "modality_cell", "actor_cell", "action_cell", "object_cell", "perspective_cell", "exit_gate_id", "action_lemma",
        "object_lemma", "termination_triggers", "techniques", "status", "provenance", "version"]
JSON_COLS = {"termination_triggers", "techniques", "provenance"}
STATUSES = ("candidate", "canonical")


def schema_statements(path: Path = SCHEMA):
    s = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    s = re.sub(r"//[^\n]*", "", s)
    return [x.strip() for x in s.split(";") if x.strip()]


class ToteDB:
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
