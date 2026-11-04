"""Store totals (node/rel counts, loops by domain/status, tech.ui breakdown). usage: store_totals.py DB [--check expected.json] [--out f] [--write f]"""
import json, sys, kuzu
a = sys.argv; db = kuzu.Database(a[1], read_only=True); c = kuzu.Connection(db)
def one(q): r = c.execute(q); return r.get_next()[0]
tables = [r for r in c.execute("CALL show_tables() RETURN name, type").get_all()]
t = {"nodes": {n: one(f"MATCH (x:{n}) RETURN count(x)") for n, k in tables if k == "NODE"},
     "rels": {n: one(f"MATCH ()-[x:{n}]->() RETURN count(x)") for n, k in tables if k == "REL"}}
t["loops_by_status"] = {s: one(f"MATCH (l:TOTELoop) WHERE l.status='{s}' RETURN count(l)") for s in ("candidate", "canonical", "")}
t["loops_by_domain"] = dict(sorted(c.execute("MATCH (l:TOTELoop) RETURN l.domain, count(l)").get_all()))
t["tech_ui"] = {"canonical_action_loops": one("MATCH (l:TOTELoop) WHERE l.domain='tech.ui' AND NOT l.loop_id STARTS WITH 'TL-UI-I-' RETURN count(l)"),
                "instance_loops": one("MATCH (l:TOTELoop) WHERE l.loop_id STARTS WITH 'TL-UI-I-' RETURN count(l)"),
                "web_sourcerefs": one("MATCH (s:SourceRef) WHERE s.ref_id STARTS WITH 'UI:' RETURN count(s)"),
                "non_provisional_rows": one("MATCH (l:TOTELoop) WHERE l.domain='tech.ui' AND (l.status<>'candidate' OR l.epistemic_status<>'PROVISIONAL') RETURN count(l)")}
t["domain_links"] = sorted(map(list, c.execute("MATCH (a:Domain)-[r:DOMAIN_LINK]->(b:Domain) RETURN a.domain_id, b.domain_id, r.shared_loops").get_all()))
s = json.dumps(t, indent=1, sort_keys=True)
if "--out" in a: open(a[a.index("--out") + 1], "w").write(s)
if "--write" in a: open(a[a.index("--write") + 1], "w").write(s); print(s)
if "--check" in a:
    want = json.load(open(a[a.index("--check") + 1])); got = json.loads(s)
    diff = [k for k in want if want[k] != got.get(k)]
    print("diff keys:", diff or "none"); sys.exit(1 if diff else 0)
