import copy, json, subprocess, sys
import pytest
import kuzu
import poc, qson_ledger
from conftest import ROOT


def one(c, q, **p):
    return c.execute(q, p).get_next()[0]


def test_schema_is_single_source_and_loads(conn):
    stmts = poc.schema_statements()
    assert len(stmts) >= 25
    assert 'CREATE NODE TABLE' not in (ROOT / 'stages/04-poc-run/poc.py').read_text().replace("'CREATE NODE TABLE'", '')
    for t, n in {'Gestalt': 32, 'Sense': 14, 'Span': 11, 'Operator': 4, 'TOTELoop': 22, 'Step': 132, 'Gate': 1}.items():
        assert poc.count(conn, t) == n, t


def test_every_sense_and_span_linked_to_gestalt(conn):
    assert one(conn, 'MATCH (s:Sense) WHERE NOT (s)-[:SENSE_OF]->(:Gestalt) RETURN count(s)') == 0
    assert one(conn, 'MATCH (s:Span) WHERE NOT (s)-[:SPANS]->(:Gestalt) RETURN count(s)') == 0


@pytest.mark.parametrize('text,loop,result', [
    ('repair the failing unit test bug', 'code.unit_test_repair', 'PASS'),
    ('the test passes', 'ai.model_evaluation', 'PASS'),
    ('check model output provenance', 'ai.output_gate', 'INTERMEDIATE'),
    ('the cat sat on the mat', None, 'INTERMEDIATE'),
])
def test_sentences(conn, tmp_path, text, loop, result):
    run = poc.run_sentence(conn, text)
    assert (run['loop_id'], run['result']) == (loop, result)
    path = poc.record_trace(conn, run, tmp_path)
    assert qson_ledger.verify(path) == []
    if result == 'PASS':
        assert one(conn, 'MATCH (:Gate)-[:ISSUES]->(p:Permit{permit_id:$p})-[:AUTHORIZES]->(l:TOTELoop) RETURN l.loop_id', p=run['permit_id']) == loop
        assert one(conn, 'MATCH (a:GSTState{state_id:$a})-[:TRANSITIONS_TO]->(b) RETURN b.state_id', a=run['input_state_id']) == run['output_state_id']
    else:
        assert run['permit_id'] is None


@pytest.mark.parametrize('args,expected', [(('CANONICAL', 3, 3), 'PASS'), (('CANONICAL', 3, 2), 'FAIL'),
                                           (('DRAFT', 2, 2), 'INTERMEDIATE'), ((None, 0, 0), 'INTERMEDIATE'), (('CANONICAL', 0, 0), 'INTERMEDIATE')])
def test_gate_logic(args, expected):
    assert poc.evaluate_gate(*args) == expected


def test_gate_fail_in_graph(tmp_path):
    c = poc.open_db(tmp_path / 'kg.kuzu', rebuild=True)
    c.execute("MATCH (:TOTELoop{loop_id:'code.unit_test_repair'})-[r:USES_GESTALT]->(:Gestalt{gestalt_id:'bug'}) DELETE r")
    run = poc.run_sentence(c, 'repair the failing unit test bug')
    assert run['result'] == 'FAIL' and run['permit_id'] is None
    led = qson_ledger.build_ledger(run, poc.GATE_ID, poc.GATE_FILE_ID, '2026-11-01T00:00:00Z')
    assert [e['event_type'] for e in led['events']] == ['external_input', 'gate_attempt']
    assert led['events'][1]['action'] == 'stop'


@pytest.fixture
def ledger(conn):
    return qson_ledger.build_ledger(poc.run_sentence(conn, 'repair the failing unit test bug'), poc.GATE_ID, poc.GATE_FILE_ID, '2026-11-01T00:00:00Z')


def test_hash_chain_valid(ledger):
    ev = ledger['events']
    assert qson_ledger.verify(ledger) == []
    assert ev[0]['previous_event_hash'] == qson_ledger.GENESIS
    for a, b in zip(ev, ev[1:]):
        assert b['previous_event_hash'] == qson_ledger.event_hash(a) == a['event_hash']


@pytest.mark.parametrize('tamper', ['edit', 'edit_and_rehash', 'delete', 'reorder'])
def test_tamper_detected(ledger, tamper):
    t = copy.deepcopy(ledger); ev = t['events']
    if tamper == 'edit':
        ev[1]['result'] = 'FAIL'
    elif tamper == 'edit_and_rehash':
        ev[1]['result'] = 'FAIL'; ev[1]['event_hash'] = qson_ledger.event_hash(ev[1])
    elif tamper == 'delete':
        del ev[1]
    else:
        ev[1], ev[2] = ev[2], ev[1]
    assert qson_ledger.verify(t)


def test_verify_cli_detects_tamper(ledger, tmp_path):
    good = qson_ledger.write(ledger, tmp_path / 'g.qson')
    bad = tmp_path / 'b.qson'; bad.write_text(good.read_text().replace('"PASS"', '"FAIL"'))
    py = [sys.executable, str(ROOT / 'stages/04-poc-run/poc.py'), 'verify']
    assert subprocess.run(py + [str(good)]).returncode == 0
    assert subprocess.run(py + [str(bad)]).returncode == 1


def test_persistence_default(tmp_path):
    db = tmp_path / 'kg.kuzu'
    c = poc.open_db(db, rebuild=True); poc.run_sentence(c, 'the test passes'); del c
    c2 = poc.open_db(db)
    assert poc.count(c2, 'Utterance') == 1 and poc.count(c2, 'Gestalt') == 32
    del c2
    assert poc.count(poc.open_db(db, rebuild=True), 'Utterance') == 0


def test_stage_gate_enforced(tmp_path):
    g = tmp_path / 'GATE.md'
    g.write_text('status: PENDING\n')
    with pytest.raises(poc.StageGateError):
        poc.check_stage_gate(g)
    assert poc.check_stage_gate(g, force_demo=True) == 'PENDING'
    g.write_text('status: APPROVED\n')
    assert poc.check_stage_gate(g) == 'APPROVED'


def test_cli_refuses_then_force_demo_stdin(tmp_path):
    g = tmp_path / 'GATE.md'; g.write_text('status: PENDING\n')
    py = [sys.executable, str(ROOT / 'stages/04-poc-run/poc.py')]
    r = subprocess.run(py + ['x', '--gate-file', str(g)], capture_output=True, text=True)
    assert r.returncode == 2 and 'REFUSED' in r.stderr
    r = subprocess.run(py + ['-', '--force-demo', '--gate-file', str(g), '--db', str(tmp_path / 'kg.kuzu'), '--trace-dir', str(tmp_path / 'tr')],
                       input='repair the failing unit test bug\nthe cat sat on the mat\n', capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert 'PRE-APPROVAL DEMO' in r.stderr
    assert len(list((tmp_path / 'tr').glob('*.qson'))) == 2
