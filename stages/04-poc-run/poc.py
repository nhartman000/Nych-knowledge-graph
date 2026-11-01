"""knowledge-graph runner: NYCH grounding -> TOTE loop -> KG gate -> Permit/GST/trace (Kuzu embedded).

Usage:
  python poc.py "repair the failing unit test bug"
  python poc.py --file sentences.txt        # one sentence per line
  echo "sentence" | python poc.py -         # stdin
DDL is loaded from stages/02-schema/output/schema.cypher (single source).
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, re, shutil, sqlite3, sys
from pathlib import Path
import kuzu

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SH = ROOT / 'shared'
SCHEMA = ROOT / 'stages' / '02-schema' / 'output' / 'schema.cypher'
TOTE = SH / 'data' / 'tote_loops.sqlite3'
REGISTRY = SH / 'data' / 'sense_registry.json'
sys.path.insert(0, str(SH / 'vendor' / 'nych'))
from nych.gestalt_handoff import build_handoff  # noqa: E402

GATE_ID = 'kg.grounding.consistent'
GATE_FILE_ID = 'knowledge-graph.kg-gates.001'  # NEW local g8son file_id


def canon(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def schema_statements(path: Path = SCHEMA):
    s = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return [x.strip() for x in s.split(';') if x.strip()]


def open_db(db_path: Path, rebuild: bool = True):
    if rebuild:
        shutil.rmtree(db_path, ignore_errors=True)
        if db_path.exists():
            db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not db_path.exists()
    c = kuzu.Connection(kuzu.Database(str(db_path)))
    if fresh:
        for q in schema_statements():
            c.execute(q)
        load_base(c)
    return c


def load_base(c):
    s = sqlite3.connect(TOTE); s.row_factory = sqlite3.Row
    reg = json.loads(REGISTRY.read_text())
    glyphs = {}
    for r in s.execute('select * from gestalts'):
        c.execute('CREATE (:Gestalt {gestalt_id:$a,glyph:$b,lexical_form:$c,sense:$d,route:$e,recoverability_note:$f,origin:"tote_db"})',
                  dict(a=r[0], b=r[1] or '', c=r[2], d=r[3], e=r[4], f=r[5]))
        if r[1]: glyphs[r[1]] = r[0]
    for g in sorted({x['gestalt'] for x in reg['senses'] + reg['gestalt_spans']} - set(glyphs)):
        gid = 'glyph:' + g
        c.execute('CREATE (:Gestalt {gestalt_id:$a,glyph:$b,lexical_form:"",sense:"",route:"",recoverability_note:"",origin:"registry_glyph"})', dict(a=gid, b=g))
        glyphs[g] = gid
    for r in s.execute('select * from modality_operators'):
        c.execute('CREATE (:Operator {operator_id:$a,symbol:$b,canonical_name:$c,evidence_channel:$d,may_assert_action:$e})',
                  dict(a=r['operator_id'], b=r['symbol'], c=r['canonical_name'], d=r['evidence_channel'], e=bool(r['may_assert_action'])))
    for r in s.execute('select * from tote_loops'):
        c.execute('CREATE (:TOTELoop {loop_id:$a,name:$b,domain:$c,objective:$d,initial_test:$e,exit_predicate:$f,max_iterations:$g,epistemic_status:$h})', dict(zip('abcdefgh', tuple(r))))
    for r in s.execute('select * from loop_gestalts'):
        c.execute('MATCH (l:TOTELoop{loop_id:$l}),(g:Gestalt{gestalt_id:$g}) CREATE (l)-[:USES_GESTALT{role:$r}]->(g)', dict(l=r[0], g=r[1], r=r[2]))
    rows = list(s.execute('select * from tote_steps'))
    for r in rows:
        k = f"{r['loop_id']}#{r['step_index']}"
        c.execute('MATCH (l:TOTELoop{loop_id:$l}) CREATE (l)-[:HAS_STEP]->(:Step {step_key:$k,step_index:$i,phase:$p,plain_text:$t,nych_text:$n,proposition_kind:$pk,provenance:$pv})',
                  dict(l=r['loop_id'], k=k, i=r['step_index'], p=r['phase'], t=r['plain_text'], n=r['nych_text'], pk=r['proposition_kind'], pv=r['provenance']))
        if r['operator_id']:
            c.execute('MATCH (s:Step{step_key:$k}),(o:Operator{operator_id:$o}) CREATE (s)-[:USES_OPERATOR]->(o)', dict(k=k, o=r['operator_id']))
    for r in rows:
        for col, rel in (('next_on_match', 'NEXT_ON_MATCH'), ('next_on_mismatch', 'NEXT_ON_MISMATCH')):
            if r[col] is not None:
                c.execute(f'MATCH (a:Step{{step_key:$a}}),(b:Step{{step_key:$b}}) CREATE (a)-[:{rel}]->(b)',
                          dict(a=f"{r['loop_id']}#{r['step_index']}", b=f"{r['loop_id']}#{r[col]}"))
    for x in reg['senses']:
        c.execute('CREATE (:Sense {sense_id:$a,gestalt:$b,surface_forms:$c,cue_words:$d})', dict(a=x['sense_id'], b=x['gestalt'], c=x['surface_forms'], d=x['cue_words']))
        c.execute('MATCH (s:Sense{sense_id:$a}),(g:Gestalt{gestalt_id:$g}) CREATE (s)-[:SENSE_OF]->(g)', dict(a=x['sense_id'], g=glyphs[x['gestalt']]))
    for x in reg['gestalt_spans']:
        c.execute('CREATE (:Span {span_id:$a,phrases:$b,gestalt:$c,canonical_expression:$d,protected_invariants:$e})', dict(a=x['span_id'], b=x['phrases'], c=x['gestalt'], d=x['canonical_expression'], e=x['protected_invariants']))
        c.execute('MATCH (s:Span{span_id:$a}),(g:Gestalt{gestalt_id:$g}) CREATE (s)-[:SPANS]->(g)', dict(a=x['span_id'], g=glyphs[x['gestalt']]))
    c.execute('CREATE (:Gate {gate_id:$g,file_id:$f,`order`:1,type:"AND",conditions:$c,outcomes:$o})',
              dict(g=GATE_ID, f=GATE_FILE_ID,
                   c=['selected loop epistemic_status == CANONICAL', 'grounded gestalt count > 0', 'every grounded gestalt is USES_GESTALT of selected loop'],
                   o=canon({'PASS': 'continue', 'FAIL': 'stop', 'INTERMEDIATE': 'review'})))


def count(c, t):
    return c.execute(f'MATCH (n:{t}) RETURN count(n)').get_next()[0]


def evaluate_gate(status, grounded, in_loop) -> str:
    """g8son result space: PASS / FAIL / INTERMEDIATE."""
    if status is None or grounded == 0:
        return 'INTERMEDIATE'
    if grounded != in_loop:
        return 'FAIL'
    return 'PASS' if status == 'CANONICAL' else 'INTERMEDIATE'


def gestalt_ids_for(c, words):
    ids = set()
    rows = c.execute('MATCH (g:Gestalt) WHERE g.origin="tote_db" RETURN g.gestalt_id, g.lexical_form')
    forms = []
    while rows.has_next(): forms.append(rows.get_next())
    ws = set(words)
    for gid, lf in forms:
        toks = lf.split()
        if gid in ws or (toks and set(toks) <= ws):
            ids.add((gid, lf))
    return sorted(ids)


def run_sentence(c, text: str) -> dict:
    h = build_handoff(text, db_path=str(TOTE)); t = h.get('tote') or {}
    loop_id = (t.get('loop') or {}).get('loop_id')
    uid = 'UTT-' + sha(text)[:12]
    run_id = 'RUN-' + uid + '-' + sha(now_iso() + text)[:8]
    c.execute('MERGE (:Utterance{utt_id:$u,text:$t})', dict(u=uid, t=text))
    grounded = gestalt_ids_for(c, t.get('matched_words') or [])
    for gid, lf in grounded:
        c.execute('MATCH (u:Utterance{utt_id:$u}),(g:Gestalt{gestalt_id:$g}) MERGE (u)-[:GROUNDED_TO{word:$w}]->(g)', dict(u=uid, g=gid, w=lf))
    status, in_loop = None, 0
    if loop_id:
        c.execute('MATCH (u:Utterance{utt_id:$u}),(l:TOTELoop{loop_id:$l}) MERGE (u)-[:SELECTED_LOOP{match_method:$m}]->(l)', dict(u=uid, l=loop_id, m=t.get('match_method') or ''))
        c.execute('MATCH (g:Gate{gate_id:$g}),(l:TOTELoop{loop_id:$l}) MERGE (g)-[:GUARDS]->(l)', dict(g=GATE_ID, l=loop_id))
        status = c.execute('MATCH (l:TOTELoop{loop_id:$l}) RETURN l.epistemic_status', dict(l=loop_id)).get_next()[0]
        ids = [g for g, _ in grounded]
        in_loop = c.execute('MATCH (l:TOTELoop{loop_id:$l})-[:USES_GESTALT]->(g:Gestalt) WHERE g.gestalt_id IN $ids RETURN count(DISTINCT g)', dict(l=loop_id, ids=ids)).get_next()[0]
    result = evaluate_gate(status, len(grounded), in_loop)
    evaluation = {'gate_id': GATE_ID, 'loop_id': loop_id, 'epistemic_status': status, 'grounded': [g for g, _ in grounded], 'in_loop': in_loop, 'result': result}
    in_state = {'state_id': f'gst:{run_id}:in', 'gst_version': '1.0', 'internal': canon({'current': {'mode': 'utterance_received'}}),
                'external': canon({'current': {'utterance': text}}), 'continuity': canon({}), 'intent': text,
                'outcome_expectation': 'select one CANONICAL TOTE loop consistent with grounding', 'constraints': canon({'gate': GATE_ID})}
    c.execute('CREATE (:GSTState $p)'.replace('$p', '{' + ','.join(f'{k}:${k}' for k in in_state) + '}'), in_state)
    out_state_id = None
    permit_id = None
    if result == 'PASS':
        out_state_id = f'gst:{run_id}:out'
        out = dict(in_state, state_id=out_state_id, internal=canon({'prior': {'mode': 'utterance_received'}, 'current': {'mode': 'loop_authorized', 'loop_id': loop_id}}))
        c.execute('CREATE (:GSTState $p)'.replace('$p', '{' + ','.join(f'{k}:${k}' for k in out) + '}'), out)
        c.execute('MATCH (a:GSTState{state_id:$a}),(b:GSTState{state_id:$b}) CREATE (a)-[:TRANSITIONS_TO]->(b)', dict(a=in_state['state_id'], b=out_state_id))
        permit_id = 'PERMIT-' + sha(run_id)[:16]
        exp = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ')
        c.execute('CREATE (:Permit {permit_id:$p,run_id:$r,proposal_id:$u,status:"ISSUED",purpose:"commit",expires_at:$e,version:0,epoch:0,evaluation_digest:$d,actor:"kg-runner",operation:$l})',
                  dict(p=permit_id, r=run_id, u=uid, e=exp, d=sha(canon(evaluation)), l=loop_id))
        c.execute('MATCH (g:Gate{gate_id:$g}),(p:Permit{permit_id:$p}) CREATE (g)-[:ISSUES]->(p)', dict(g=GATE_ID, p=permit_id))
        c.execute('MATCH (p:Permit{permit_id:$p}),(l:TOTELoop{loop_id:$l}) CREATE (p)-[:AUTHORIZES]->(l)', dict(p=permit_id, l=loop_id))
    return dict(text=text, utt_id=uid, run_id=run_id, loop_id=loop_id, match_method=t.get('match_method'), matched_words=t.get('matched_words'),
                evaluation=evaluation, result=result, input_state_id=in_state['state_id'], output_state_id=out_state_id, permit_id=permit_id)


def record_trace(c, run: dict):
    """Step-2 in-graph trace (replaced by QSON ledger in step 3)."""
    prev = ''; prevtid = None
    for i, (et, res) in enumerate([('external_input', None), ('gate_attempt', run['result'])], 1):
        tid = f"trace-{run['run_id']}-{i:06d}"
        c.execute('CREATE (:QSONTrace{trace_id:$t,run_id:$r,sequence:$s,event_type:$e,gate_id:$g,result:$x,previous_event_hash:$p})',
                  dict(t=tid, r=run['run_id'], s=i, e=et, g=GATE_ID if res else '', x=res or '', p=prev))
        c.execute('MATCH (e:QSONTrace{trace_id:$t}),(u:Utterance{utt_id:$u}) CREATE (e)-[:TRACE_OF]->(u)', dict(t=tid, u=run['utt_id']))
        if prevtid: c.execute('MATCH (a:QSONTrace{trace_id:$a}),(b:QSONTrace{trace_id:$b}) CREATE (a)-[:PRECEDES]->(b)', dict(a=prevtid, b=tid))
        prev = sha(tid); prevtid = tid


def read_sentences(args):
    if args.file:
        return [l.strip() for l in Path(args.file).read_text().splitlines() if l.strip()]
    if args.sentence in (None, '-'):
        return [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
    return [args.sentence]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('sentence', nargs='?', help='sentence to run, or - for stdin')
    ap.add_argument('--file', help='file with one sentence per line')
    ap.add_argument('--db', default=str(HERE / 'output' / 'kg.kuzu'))
    args = ap.parse_args(argv)
    sentences = read_sentences(args)
    if not sentences: ap.error('no input sentence')
    c = open_db(Path(args.db), rebuild=True)
    print('LOADED', {t: count(c, t) for t in 'Gestalt Sense Span Operator TOTELoop Step Gate'.split()})
    for text in sentences:
        run = run_sentence(c, text); record_trace(c, run)
        print(json.dumps({k: run[k] for k in ('text', 'loop_id', 'matched_words', 'result', 'permit_id')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
