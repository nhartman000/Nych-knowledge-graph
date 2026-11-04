"""Review r2 (finding 5): permit issued before the transition; consumed single-use, atomically with state + ledger."""
import pytest
import qson_ledger
import kg_run as poc

TEXT = 'repair the failing unit test bug'


def one(c, q, **p):
    return c.execute(q, p).get_next()[0]


def _state(c, run, d):
    return dict(permit=one(c, 'MATCH (p:Permit{permit_id:$p}) RETURN p.status', p=run['permit_id']),
                out=one(c, 'MATCH (s:GSTState{state_id:$s}) RETURN count(s)', s=run['output_state_id']),
                trans=one(c, 'MATCH (:GSTState{state_id:$s})-[:TRANSITIONS_TO]->() RETURN count(*)', s=run['input_state_id']),
                traces=one(c, 'MATCH (t:QSONTrace{run_id:$r}) RETURN count(t)', r=run['run_id']),
                files=sorted(x.name for x in d.iterdir()) if d.exists() else [])


@pytest.fixture
def fresh(tmp_path):
    c = poc.open_db(tmp_path / 'kg.kuzu', rebuild=True)
    yield c
    poc._FAULT = None


def test_permit_issued_before_transition(fresh):
    run = poc.run_sentence(fresh, TEXT)
    assert run['result'] == 'PASS'
    assert one(fresh, 'MATCH (p:Permit{permit_id:$p}) RETURN p.status', p=run['permit_id']) == 'ISSUED'
    assert one(fresh, 'MATCH (s:GSTState{state_id:$s}) RETURN count(s)', s=run['output_state_id']) == 0   # no transition yet


@pytest.mark.parametrize('stage', ['permit_consumed', 'state_written', 'ledger_event', 'before_commit'])
def test_crash_rolls_back_everything_then_retry_succeeds(fresh, tmp_path, stage):
    run = poc.run_sentence(fresh, TEXT); d = tmp_path / 'tr'

    def boom(s):
        if s == stage:
            raise RuntimeError('simulated crash at ' + s)
    poc._FAULT = boom
    with pytest.raises(RuntimeError, match='simulated crash'):
        poc.record_trace(fresh, run, d)
    assert _state(fresh, run, d) == dict(permit='ISSUED', out=0, trans=0, traces=0, files=[])
    poc._FAULT = None
    path = poc.record_trace(fresh, run, d)
    assert qson_ledger.verify(path) == []
    assert _state(fresh, run, d) == dict(permit='CONSUMED', out=1, trans=1, traces=4, files=[path.name])


def test_reused_permit_rejected_and_writes_nothing(fresh, tmp_path):
    run = poc.run_sentence(fresh, TEXT); d = tmp_path / 'tr'
    path = poc.record_trace(fresh, run, d)
    before = _state(fresh, run, d)
    with pytest.raises(poc.PermitError, match='single-use'):
        poc.record_trace(fresh, dict(run, run_id=run['run_id']), d)
    assert _state(fresh, run, d) == before and before['permit'] == 'CONSUMED' and before['files'] == [path.name]


def test_permit_for_other_evaluation_rejected(fresh, tmp_path):
    run = poc.run_sentence(fresh, TEXT)
    bad = dict(run, evaluation=dict(run['evaluation'], in_loop=99))
    with pytest.raises(poc.PermitError, match='does not match'):
        poc.record_trace(fresh, bad, tmp_path / 'tr')
    assert one(fresh, 'MATCH (p:Permit{permit_id:$p}) RETURN p.status', p=run['permit_id']) == 'ISSUED'
