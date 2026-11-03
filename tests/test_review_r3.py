"""r3 third-opinion review regressions (REVIEW/RESPONSE_TO_REVIEW_r3.md)."""
import copy
import pytest
import qson_ledger
import kg_run as poc

NEG_CONTROLS = [  # reviewer's controls (tote-graph-review.md finding 1) + extra negation forms
    'repair the failing medical test bug', 'repair the failing pregnancy test', 'repair the failing statistical test',
    'test the patient', 'do not repair the failing unit test bug', "don't repair the failing unit test bug",
    'never repair the failing unit test bug', 'repair the failing unit test bug without touching anything',
]


@pytest.mark.parametrize('text', NEG_CONTROLS)
def test_r3_05_negated_or_wrong_domain_not_pass(conn, text):
    run = poc.run_sentence(conn, text)
    assert run['result'] == 'INTERMEDIATE' and run['permit_id'] is None, run['evaluation']
    ev = run['evaluation']
    assert ev['negated'] or ev['unaccounted_words']


@pytest.mark.parametrize('text', ['repair the failing unit test bug', 'the test passes'])
def test_r3_05_positive_controls_still_pass(conn, text):
    run = poc.run_sentence(conn, text)
    assert run['result'] == 'PASS' and not run['evaluation']['negated'] and run['evaluation']['unaccounted_words'] == []


def test_r3_05_guard_unit():
    g = poc.context_guard('do not repair the pregnancy test', {'repair', 'test'})
    assert g == {'negated': True, 'unaccounted_words': ['pregnancy']}
    assert poc.evaluate_gate('CANONICAL', 2, 2, g) == 'INTERMEDIATE'
    assert poc.evaluate_gate('CANONICAL', 2, 2, {'negated': False, 'unaccounted_words': []}) == 'PASS'
    assert poc.evaluate_gate('CANONICAL', 2, 1, g) == 'FAIL'   # inconsistency still FAILs first


def test_r3_06_previous_hash_binds_prior_content(conn):
    """Reviewer finding: on main@c4d3a14 previous_event_hash = sha256(trace_id). On this branch it is the prior event's
    content hash; changing the prior event's content must be detected."""
    run = poc.run_sentence(conn, 'repair the failing unit test bug')
    led = qson_ledger.build_ledger(run, poc.GATE_ID, poc.GATE_FILE_ID, '2026-11-03T00:00:00Z')
    assert led['events'][1]['previous_event_hash'] == qson_ledger.event_hash(led['events'][0])
    bad = copy.deepcopy(led); bad['events'][0]['action'] = 'TAMPERED'
    assert any('event_hash mismatch' in e for e in qson_ledger.verify(bad))
