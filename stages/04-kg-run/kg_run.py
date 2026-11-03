"""knowledge-graph runner (replaces the retired POC runner poc.py):
NYCH 3.0 encoder (shared/nych3, stages/05-nych3-encoder) -> TOTE loop in the shared KG store -> KG gate
-> Permit/GST/QSON hash-chain trace (Kuzu embedded). If the nych3 encoder finds no TOTE row, the legacy
vendored-nych grounding adapter is tried for the legacy loop set (match_method says which one fired).

Usage:
  python kg_run.py "repair the failing unit test bug"
  python kg_run.py --file sentences.txt        # one sentence per line
  echo "sentence" | python kg_run.py -         # stdin
  python kg_run.py ... --rebuild               # drop and reload the persistent store
  python kg_run.py ... --force-demo            # run before stage 03 is APPROVED; writes to demo_pre_approval/
  python kg_run.py verify path/to/run.qson [...] # check QSON hash chain / tampering
DDL is loaded from stages/02-schema/output/schema.cypher (single source).
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, re, shutil, sqlite3, sys, uuid
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
sys.path.insert(0, str(HERE))
import qson_ledger  # noqa: E402
sys.path.insert(0, str(SH))
from nych3.store.tote_db import ToteDB  # noqa: E402
from nych3.pipeline import run as nych3_run  # noqa: E402
import tempfile  # noqa: E402

_DB_PATH: dict = {}   # id(connection) -> store path (lets nych3 stages reuse the open connection)

STAGE03_GATE = ROOT / 'stages' / '03-ontology' / 'output' / 'GATE.md'
DEMO_DIR = HERE / 'demo_pre_approval'
GATE_ID = 'kg.grounding.consistent'
GATE_FILE_ID = 'knowledge-graph.kg-gates.001'  # NEW local g8son file_id


def canon(o) -> str:
    return json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class StageGateError(RuntimeError):
    pass


def stage_gate_status(path: Path = STAGE03_GATE) -> str:
    m = re.search(r'^status:\s*(\S+)', path.read_text(), re.M) if path.exists() else None
    return m.group(1).upper() if m else 'MISSING'


def check_stage_gate(path: Path = STAGE03_GATE, force_demo: bool = False) -> str:
    """ICM discipline: stage 04 may run only when stage 03 GATE.md says status: APPROVED."""
    st = stage_gate_status(path)
    if st != 'APPROVED' and not force_demo:
        raise StageGateError(f'stage 03 gate is {st} ({path}); approve it or pass --force-demo')
    return st


def schema_statements(path: Path = SCHEMA):
    s = re.sub(r'/\*.*?\*/', '', path.read_text(), flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return [x.strip() for x in s.split(';') if x.strip()]


def open_db(db_path: Path, rebuild: bool = False):
    """Persistent by default; rebuild=True deletes and reloads the store."""
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
        ToteDB.on_connection(c).load_seed()   # nych3 operators, domains, gates, seed loops, measures
    ToteDB.on_connection(c, db_path)
    _DB_PATH[id(c)] = str(db_path)
    return c


def nych3_encode(c, text: str):
    """Run the NYCH 3.0 encoder (stages 01-09) against the shared store. Returns the first bound TOTE
    instance as (loop_id, method, grounded_words, status) or None."""
    path = _DB_PATH.get(id(c))
    if not path:
        return None
    with tempfile.TemporaryDirectory() as td:
        _, g, _, _ = nych3_run('Encode this sentence with NYCH.', text, name='kg', root=Path(td), write_stage_outputs=False, db_path=path)
    for inst in g['nych3']['tote']['instances']:
        if inst.get('template_id') and inst['template_id'] != 'NO_MATCH':
            key = [k for k in inst['retrieval']['key'] if k and k != '*']
            st = c.execute('MATCH (l:TOTELoop{loop_id:$l}) RETURN l.status', dict(l=inst['template_id'])).get_next()[0]
            return inst['template_id'], 'nych3:' + inst['retrieval']['method'], key, st
    return None


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
    n3 = nych3_encode(c, text)
    if n3:
        return _run_nych3(c, text, *n3)
    h = build_handoff(text, db_path=str(TOTE)); t = h.get('tote') or {}
    if t.get('match_method'):
        t['match_method'] = 'legacy:' + t['match_method']
    loop_id = (t.get('loop') or {}).get('loop_id')
    uid = 'UTT-' + sha(text)[:12]
    run_id = 'RUN-' + uid + '-' + uuid.uuid4().hex[:12]  # unique per execution (QSON §2)
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
    return _finish(c, text, uid, run_id, loop_id, t.get('match_method'), t.get('matched_words'), status, [g for g, _ in grounded], in_loop)


def _run_nych3(c, text, loop_id, method, words, status):
    """nych3 path: grounding = the structured lookup key (action_lemma, object_lemma); in_loop = key parts equal to
    the loop's own lemmas. CANONICAL only for status=canonical rows (authority metadata, not authenticated), else CANDIDATE -> INTERMEDIATE."""
    uid = 'UTT-' + sha(text)[:12]
    run_id = 'RUN-' + uid + '-' + uuid.uuid4().hex[:12]
    c.execute('MERGE (:Utterance{utt_id:$u,text:$t})', dict(u=uid, t=text))
    c.execute('MATCH (u:Utterance{utt_id:$u}),(l:TOTELoop{loop_id:$l}) MERGE (u)-[:SELECTED_LOOP{match_method:$m}]->(l)', dict(u=uid, l=loop_id, m=method))
    c.execute('MATCH (g:Gate{gate_id:$g}),(l:TOTELoop{loop_id:$l}) MERGE (g)-[:GUARDS]->(l)', dict(g=GATE_ID, l=loop_id))
    a, o = c.execute('MATCH (l:TOTELoop{loop_id:$l}) RETURN l.action_lemma, l.object_lemma', dict(l=loop_id)).get_next()
    in_loop = sum(1 for w in words if w in (a, o))
    return _finish(c, text, uid, run_id, loop_id, method, words, 'CANONICAL' if status == 'canonical' else 'CANDIDATE', words, in_loop)


def _finish(c, text, uid, run_id, loop_id, match_method, matched_words, status, grounded_ids, in_loop):
    result = evaluate_gate(status, len(grounded_ids), in_loop)
    evaluation = {'gate_id': GATE_ID, 'loop_id': loop_id, 'epistemic_status': status, 'grounded': grounded_ids, 'in_loop': in_loop, 'result': result}
    in_state = {'state_id': f'gst:{run_id}:in', 'gst_version': '1.0', 'internal': canon({'current': {'mode': 'utterance_received'}}),
                'external': canon({'current': {'utterance': text}}), 'continuity': canon({}), 'intent': text,
                'outcome_expectation': 'select one CANONICAL TOTE loop consistent with grounding', 'constraints': canon({'gate': GATE_ID})}
    c.execute('CREATE (:GSTState $p)'.replace('$p', '{' + ','.join(f'{k}:${k}' for k in in_state) + '}'), in_state)
    out_state_id = None
    permit_id = None
    if result == 'PASS':
        # Step 1 (before any transition): issue a single-use permit. The GST transition is NOT written here; it is
        # committed by commit_run() in one Kuzu transaction that also consumes the permit and writes the ledger mirror.
        out_state_id = f'gst:{run_id}:out'
        permit_id = issue_permit(c, run_id, uid, loop_id, evaluation)
    return dict(text=text, utt_id=uid, run_id=run_id, loop_id=loop_id, match_method=match_method, matched_words=matched_words,
                evaluation=evaluation, result=result, input_state_id=in_state['state_id'], output_state_id=out_state_id, permit_id=permit_id,
                _in_state=in_state)


class PermitError(RuntimeError):
    pass


_FAULT = None   # test hook: callable(stage:str) invoked inside the commit transaction (crash/rollback tests)


def _fault(stage):
    if _FAULT:
        _FAULT(stage)


def issue_permit(c, run_id, uid, loop_id, evaluation) -> str:
    """Issue a single-use commit permit (status ISSUED). Issued BEFORE the GST transition exists."""
    permit_id = 'PERMIT-' + sha(run_id)[:16]
    exp = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ')
    c.execute('BEGIN TRANSACTION')
    try:
        c.execute('CREATE (:Permit {permit_id:$p,run_id:$r,proposal_id:$u,status:"ISSUED",purpose:"commit",expires_at:$e,version:0,epoch:0,evaluation_digest:$d,actor:"kg-runner",operation:$l})',
                  dict(p=permit_id, r=run_id, u=uid, e=exp, d=sha(canon(evaluation)), l=loop_id))
        c.execute('MATCH (g:Gate{gate_id:$g}),(p:Permit{permit_id:$p}) CREATE (g)-[:ISSUES]->(p)', dict(g=GATE_ID, p=permit_id))
        c.execute('MATCH (p:Permit{permit_id:$p}),(l:TOTELoop{loop_id:$l}) CREATE (p)-[:AUTHORIZES]->(l)', dict(p=permit_id, l=loop_id))
        c.execute('COMMIT')
    except Exception:
        c.execute('ROLLBACK'); raise
    return permit_id


def _consume_permit(c, run):
    """Inside the open transaction: ISSUED -> CONSUMED exactly once; reject reuse, expiry, digest or operation mismatch."""
    r = c.execute('MATCH (p:Permit{permit_id:$p}) RETURN p.status, p.expires_at, p.evaluation_digest, p.operation, p.run_id', dict(p=run['permit_id']))
    if not r.has_next():
        raise PermitError(f"unknown permit {run['permit_id']}")
    st, exp, dig, op, rid = r.get_next()
    if st != 'ISSUED':
        raise PermitError(f"permit {run['permit_id']} is {st}; permits are single-use")
    if exp < now_iso():
        raise PermitError(f"permit {run['permit_id']} expired at {exp}")
    if dig != sha(canon(run['evaluation'])) or op != run['loop_id'] or rid != run['run_id']:
        raise PermitError(f"permit {run['permit_id']} does not match this run/evaluation")
    n = c.execute("MATCH (p:Permit{permit_id:$p}) WHERE p.status='ISSUED' SET p.status='CONSUMED', p.version=p.version+1 RETURN count(p)",
                  dict(p=run['permit_id'])).get_next()[0]
    if n != 1:
        raise PermitError(f"permit {run['permit_id']} could not be consumed")


def _mirror_ledger(c, run, led):
    prevtid = None
    for ev in led['events']:
        c.execute('CREATE (:QSONTrace{trace_id:$t,run_id:$r,sequence:$s,event_type:$e,file_id:$f,gate_id:$g,input_state_id:$i,result:$x,action:$a,output_state_id:$o,actor_type:$at,actor_id:$ai,timestamp:$ts,previous_event_hash:$p,event_hash:$h})',
                  dict(t=ev['trace_id'], r=ev['run_id'], s=ev['sequence'], e=ev['event_type'], f=ev.get('file_id', ''), g=ev.get('gate_id', ''),
                       i=ev.get('input_state_id', ''), x=ev.get('result', ''), a=ev['action'] if isinstance(ev.get('action'), str) else canon(ev.get('action')),
                       o=ev.get('output_state_id') or '', at=ev['actor']['type'], ai=ev['actor']['id'], ts=ev['timestamp'], p=ev['previous_event_hash'], h=ev['event_hash']))
        c.execute('MATCH (e:QSONTrace{trace_id:$t}),(u:Utterance{utt_id:$u}) CREATE (e)-[:TRACE_OF]->(u)', dict(t=ev['trace_id'], u=run['utt_id']))
        if ev.get('gate_id'): c.execute('MATCH (e:QSONTrace{trace_id:$t}),(g:Gate{gate_id:$g}) CREATE (e)-[:RECORDS]->(g)', dict(t=ev['trace_id'], g=ev['gate_id']))
        for rel, key in (('INPUT_STATE', 'input_state_id'), ('OUTPUT_STATE', 'output_state_id')):
            if ev.get(key): c.execute(f'MATCH (e:QSONTrace{{trace_id:$t}}),(s:GSTState{{state_id:$s}}) CREATE (e)-[:{rel}]->(s)', dict(t=ev['trace_id'], s=ev[key]))
        if prevtid: c.execute('MATCH (a:QSONTrace{trace_id:$a}),(b:QSONTrace{trace_id:$b}) CREATE (a)-[:PRECEDES]->(b)', dict(a=prevtid, b=ev['trace_id']))
        prevtid = ev['trace_id']
        _fault('ledger_event')


def record_trace(c, run: dict, trace_dir: Path) -> Path:
    """Commit the run atomically and serialize it to a QSON v1 ledger file.

    Write-ahead protocol: (1) the ledger is written to <run>.qson.pending; (2) ONE Kuzu transaction consumes the
    permit (single-use, ISSUED -> CONSUMED), creates the output GSTState + TRANSITIONS_TO edge and mirrors every
    ledger event into the graph; (3) only after COMMIT is the pending file renamed to <run>.qson. Any failure in (2)
    rolls the transaction back and deletes the pending file, so state, permit and ledger stay consistent and the
    permit remains ISSUED (retryable). A reused permit raises PermitError and writes nothing."""
    import os
    led = qson_ledger.build_ledger(run, GATE_ID, GATE_FILE_ID, now_iso())
    path = Path(trace_dir) / f"{run['run_id']}.qson"
    pending = qson_ledger.write(led, path.with_name(path.name + '.pending'))
    c.execute('BEGIN TRANSACTION')
    try:
        if run.get('permit_id'):
            _consume_permit(c, run)
            _fault('permit_consumed')
            ins = run['_in_state']
            out = dict(ins, state_id=run['output_state_id'], internal=canon({'prior': {'mode': 'utterance_received'}, 'current': {'mode': 'loop_authorized', 'loop_id': run['loop_id']}}))
            c.execute('CREATE (:GSTState $p)'.replace('$p', '{' + ','.join(f'{k}:${k}' for k in out) + '}'), out)
            c.execute('MATCH (a:GSTState{state_id:$a}),(b:GSTState{state_id:$b}) CREATE (a)-[:TRANSITIONS_TO]->(b)', dict(a=ins['state_id'], b=run['output_state_id']))
            _fault('state_written')
        _mirror_ledger(c, run, led)
        _fault('before_commit')
        c.execute('COMMIT')
    except BaseException:
        c.execute('ROLLBACK')
        pending.unlink(missing_ok=True)
        raise
    os.replace(pending, path)
    return path


def verify_main(paths) -> int:
    bad = 0
    for p in paths:
        errs = qson_ledger.verify(p)
        print(('OK      ' if not errs else 'TAMPERED') + f' {p}')
        for e in errs: print('   -', e)
        bad += bool(errs)
    return 1 if bad else 0


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
    ap.add_argument('--db', help='Kuzu store path (default output/kg.kuzu, or demo_pre_approval/kg.kuzu with --force-demo)')
    ap.add_argument('--trace-dir', help='QSON output dir (default output/traces, or demo_pre_approval/traces)')
    ap.add_argument('--rebuild', action='store_true', help='delete and reload the store before running')
    ap.add_argument('--force-demo', action='store_true', help='override the stage 03 gate; outputs are labelled pre-approval demo')
    ap.add_argument('--gate-file', default=str(STAGE03_GATE), help=argparse.SUPPRESS)
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['verify']:
        return verify_main(argv[1:])
    args = ap.parse_args(argv)
    sentences = read_sentences(args)
    if not sentences: ap.error('no input sentence')
    try:
        st = check_stage_gate(Path(args.gate_file), args.force_demo)
    except StageGateError as e:
        print('REFUSED:', e, file=sys.stderr); return 2
    base = HERE / 'output' if st == 'APPROVED' else DEMO_DIR
    if st != 'APPROVED': print(f'WARNING: stage 03 gate is {st}; PRE-APPROVAL DEMO run -> {base}', file=sys.stderr)
    args.db = args.db or str(base / 'kg.kuzu'); args.trace_dir = args.trace_dir or str(base / 'traces')
    c = open_db(Path(args.db), rebuild=args.rebuild)
    print('LOADED', {t: count(c, t) for t in 'Gestalt Sense Span Operator TOTELoop Step Gate Domain Measure MeasureRule'.split()})
    for text in sentences:
        run = run_sentence(c, text); qp = record_trace(c, run, Path(args.trace_dir))
        print(json.dumps({**{k: run[k] for k in ('text', 'loop_id', 'matched_words', 'result', 'permit_id')}, 'qson': str(qp)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
