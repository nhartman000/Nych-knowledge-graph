"""NYCH + MG8 + KG proof of concept (Kuzu embedded). Nodes marked NEW are proposed."""
import json, sqlite3, sys, hashlib, shutil
from pathlib import Path
import kuzu
W = Path('/workspace'); sys.path.insert(0, str(W/'nych'))
from nych.gestalt_handoff import build_handoff
TOTE = W/'T.O.T.E-loops/data/tote_loops.sqlite3'
REG = json.load(open(W/'nych/nych/data/sense_registry.json'))
DB = Path(__file__).parent/'kg.kuzu'; shutil.rmtree(DB, ignore_errors=True); DB.unlink(missing_ok=True)
c = kuzu.Connection(kuzu.Database(str(DB)))
for q in [
 "CREATE NODE TABLE Gestalt(gestalt_id STRING, glyph STRING, lexical_form STRING, sense STRING, route STRING, recoverability_note STRING, PRIMARY KEY(gestalt_id))",
 "CREATE NODE TABLE Sense(sense_id STRING, gestalt STRING, surface_forms STRING[], cue_words STRING[], PRIMARY KEY(sense_id))",
 "CREATE NODE TABLE Span(span_id STRING, phrases STRING[], gestalt STRING, canonical_expression STRING, protected_invariants STRING[], PRIMARY KEY(span_id))",
 "CREATE NODE TABLE Operator(operator_id STRING, symbol STRING, canonical_name STRING, evidence_channel STRING, may_assert_action BOOLEAN, PRIMARY KEY(operator_id))",
 "CREATE NODE TABLE TOTELoop(loop_id STRING, name STRING, domain STRING, objective STRING, initial_test STRING, exit_predicate STRING, max_iterations INT64, epistemic_status STRING, PRIMARY KEY(loop_id))",
 "CREATE NODE TABLE Step(step_key STRING, step_index INT64, phase STRING, plain_text STRING, nych_text STRING, proposition_kind STRING, provenance STRING, PRIMARY KEY(step_key))",
 "CREATE NODE TABLE Utterance(utt_id STRING, text STRING, PRIMARY KEY(utt_id))",
 "CREATE NODE TABLE TraceEvent(trace_id STRING, run_id STRING, sequence INT64, event_type STRING, gate_id STRING, result STRING, previous_event_hash STRING, PRIMARY KEY(trace_id))",
 "CREATE REL TABLE USES_GESTALT(FROM TOTELoop TO Gestalt, role STRING)",
 "CREATE REL TABLE HAS_STEP(FROM TOTELoop TO Step)",
 "CREATE REL TABLE NEXT_ON_MATCH(FROM Step TO Step)",
 "CREATE REL TABLE NEXT_ON_MISMATCH(FROM Step TO Step)",
 "CREATE REL TABLE USES_OPERATOR(FROM Step TO Operator)",
 "CREATE REL TABLE GROUNDED_TO(FROM Utterance TO Gestalt, word STRING)",
 "CREATE REL TABLE SELECTED_LOOP(FROM Utterance TO TOTELoop, match_method STRING)",
 "CREATE REL TABLE TRACE_OF(FROM TraceEvent TO Utterance)",
 "CREATE REL TABLE PRECEDES(FROM TraceEvent TO TraceEvent)",
]: c.execute(q)
s = sqlite3.connect(TOTE); s.row_factory = sqlite3.Row
for r in s.execute("select * from gestalts"): c.execute("CREATE (:Gestalt $p)" .replace("$p","{gestalt_id:$a,glyph:$b,lexical_form:$c,sense:$d,route:$e,recoverability_note:$f}"), dict(a=r[0],b=r[1] or '',c=r[2],d=r[3],e=r[4],f=r[5]))
for r in s.execute("select * from modality_operators"): c.execute("CREATE (:Operator {operator_id:$a,symbol:$b,canonical_name:$c,evidence_channel:$d,may_assert_action:$e})", dict(a=r['operator_id'],b=r['symbol'],c=r['canonical_name'],d=r['evidence_channel'],e=bool(r['may_assert_action'])))
for r in s.execute("select * from tote_loops"): c.execute("CREATE (:TOTELoop {loop_id:$a,name:$b,domain:$c,objective:$d,initial_test:$e,exit_predicate:$f,max_iterations:$g,epistemic_status:$h})", dict(zip('abcdefgh', tuple(r))))
for r in s.execute("select * from loop_gestalts"): c.execute("MATCH (l:TOTELoop{loop_id:$l}),(g:Gestalt{gestalt_id:$g}) CREATE (l)-[:USES_GESTALT{role:$r}]->(g)", dict(l=r[0],g=r[1],r=r[2]))
steps = list(s.execute("select * from tote_steps"))
for r in steps:
    k=f"{r['loop_id']}#{r['step_index']}"
    c.execute("MATCH (l:TOTELoop{loop_id:$l}) CREATE (l)-[:HAS_STEP]->(:Step {step_key:$k,step_index:$i,phase:$p,plain_text:$t,nych_text:$n,proposition_kind:$pk,provenance:$pv})", dict(l=r['loop_id'],k=k,i=r['step_index'],p=r['phase'],t=r['plain_text'],n=r['nych_text'],pk=r['proposition_kind'],pv=r['provenance']))
    if r['operator_id']: c.execute("MATCH (s:Step{step_key:$k}),(o:Operator{operator_id:$o}) CREATE (s)-[:USES_OPERATOR]->(o)", dict(k=k,o=r['operator_id']))
for r in steps:
    for col,rel in (('next_on_match','NEXT_ON_MATCH'),('next_on_mismatch','NEXT_ON_MISMATCH')):
        if r[col] is not None: c.execute(f"MATCH (a:Step{{step_key:$a}}),(b:Step{{step_key:$b}}) CREATE (a)-[:{rel}]->(b)", dict(a=f"{r['loop_id']}#{r['step_index']}", b=f"{r['loop_id']}#{r[col]}"))
for x in REG['senses']: c.execute("CREATE (:Sense {sense_id:$a,gestalt:$b,surface_forms:$c,cue_words:$d})", dict(a=x['sense_id'],b=x['gestalt'],c=x['surface_forms'],d=x['cue_words']))
for x in REG['gestalt_spans']: c.execute("CREATE (:Span {span_id:$a,phrases:$b,gestalt:$c,canonical_expression:$d,protected_invariants:$e})", dict(a=x['span_id'],b=x['phrases'],c=x['gestalt'],d=x['canonical_expression'],e=x['protected_invariants']))
def cnt(t): return c.execute(f"MATCH (n:{t}) RETURN count(n)").get_next()[0]
print("LOADED", {t:cnt(t) for t in "Gestalt Sense Span Operator TOTELoop Step".split()})
# --- end-to-end one sentence
text = "repair the failing unit test bug"
h = build_handoff(text, db_path=str(TOTE)); t = h['tote']
uid = "UTT-"+hashlib.sha256(text.encode()).hexdigest()[:12]
c.execute("CREATE (:Utterance{utt_id:$u,text:$t})", dict(u=uid,t=text))
for w in t['matched_words']:
    c.execute("MATCH (u:Utterance{utt_id:$u}),(g:Gestalt{lexical_form:$w}) CREATE (u)-[:GROUNDED_TO{word:$w}]->(g)", dict(u=uid,w=w))
c.execute("MATCH (u:Utterance{utt_id:$u}),(l:TOTELoop{loop_id:$l}) CREATE (u)-[:SELECTED_LOOP{match_method:$m}]->(l)", dict(u=uid,l=t['loop']['loop_id'],m=t['match_method']))
print("NYCH lookup_loop:", t['match_method'], t['matched_words'], "->", t['loop']['loop_id'])
# KG gate (NEW): every grounded gestalt must belong to the selected loop, loop must be CANONICAL
r = c.execute("""MATCH (u:Utterance{utt_id:$u})-[:SELECTED_LOOP]->(l:TOTELoop) OPTIONAL MATCH (u)-[:GROUNDED_TO]->(g:Gestalt)
 OPTIONAL MATCH (l)-[ug:USES_GESTALT]->(g) RETURN l.epistemic_status, count(g), count(ug)""", dict(u=uid)).get_next()
result = "PASS" if r[0]=="CANONICAL" and r[1]>0 and r[1]==r[2] else ("FAIL" if r[1]!=r[2] else "INTERMEDIATE")
print("KG gate kg.grounding.consistent:", result, "(status, grounded, in-loop) =", r)
prev=""
for i,(et,gid,res) in enumerate([("grounding",None,None),("gate_evaluated","kg.grounding.consistent",result)],1):
    tid=f"TRACE-{uid}-{i}"
    c.execute("CREATE (:TraceEvent{trace_id:$t,run_id:$r,sequence:$s,event_type:$e,gate_id:$g,result:$x,previous_event_hash:$p})", dict(t=tid,r="RUN-"+uid,s=i,e=et,g=gid or "",x=res or "",p=prev))
    c.execute("MATCH (e:TraceEvent{trace_id:$t}),(u:Utterance{utt_id:$u}) CREATE (e)-[:TRACE_OF]->(u)", dict(t=tid,u=uid))
    if prev: c.execute("MATCH (a:TraceEvent{trace_id:$a}),(b:TraceEvent{trace_id:$b}) CREATE (a)-[:PRECEDES]->(b)", dict(a=prevtid,b=tid))
    prev=hashlib.sha256(tid.encode()).hexdigest(); prevtid=tid
q = c.execute("MATCH (l:TOTELoop{loop_id:'code.unit_test_repair'})-[:HAS_STEP]->(s:Step)-[:USES_OPERATOR]->(o:Operator) RETURN s.step_index,s.phase,o.symbol,s.plain_text ORDER BY s.step_index")
print("Loop steps:"); 
while q.has_next(): print("  ", q.get_next())
q = c.execute("MATCH (e:TraceEvent)-[:TRACE_OF]->(u:Utterance)-[:SELECTED_LOOP]->(l) RETURN e.sequence,e.event_type,e.result,l.loop_id ORDER BY e.sequence")
print("Provenance:");
while q.has_next(): print("  ", q.get_next())
