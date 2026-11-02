"""Unified store: NYCH 3.0 encoder as the KG runner's encoder, plus the schema additions."""
import json
import pytest
import kg_run as poc
import qson_ledger
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from nych3.store.tote_db import ToteDB


def one(c, q, **p):
    return c.execute(q, p).get_next()[0]


def test_nych3_encoder_selects_canonical_loop_and_passes_gate(conn, tmp_path):
    run = poc.run_sentence(conn, 'Peter looked at the stars.')
    assert run['loop_id'] == 'TL-LOOK-AT-STARS-001' and run['match_method'].startswith('nych3:')
    assert run['result'] == 'PASS' and run['permit_id']
    assert qson_ledger.verify(poc.record_trace(conn, run, tmp_path)) == []
    assert one(conn, 'MATCH (:Gate)-[:ISSUES]->(:Permit{permit_id:$p})-[:AUTHORIZES]->(l:TOTELoop) RETURN l.loop_id', p=run['permit_id']) == run['loop_id']


def test_nych3_candidate_row_is_intermediate(tmp_path):
    c = poc.open_db(tmp_path / 'kg.kuzu', rebuild=True)
    ToteDB.on_connection(c).c.execute("MATCH (l:TOTELoop{loop_id:'TL-LOOK-AT-STARS-001'}) SET l.status='candidate'")
    run = poc.run_sentence(c, 'Peter looked at the stars.')
    assert run['result'] == 'INTERMEDIATE' and run['permit_id'] is None
    assert run['evaluation']['epistemic_status'] == 'CANDIDATE'


def test_legacy_sentences_still_route_via_legacy_adapter(conn):
    assert poc.run_sentence(conn, 'repair the failing unit test bug')['match_method'].startswith('legacy:')


def test_schema_additions_present(conn):
    tables = {r[1] for r in _rows(conn, 'CALL show_tables() RETURN *')}
    for t in ['Domain', 'IN_DOMAIN', 'DOMAIN_LINK', 'Measure', 'MeasureRule', 'MEASURE_WEIGHT_IN', 'SourceRef', 'SOURCED_FROM',
              'HarvestSentence', 'SymbolPattern', 'INSTANTIATES', 'PATTERN_OPERATOR', 'PATTERN_GESTALT', 'USES_MODALITY',
              'CELL_GESTALT', 'CELL_SENSE', 'LexicalEntry', 'MAPPED_TO']:
        assert t in tables, t
    props = {r[1] for r in _rows(conn, "CALL table_info('SourceRef') RETURN *")}
    assert {'isbn', 'page', 'fallback_gutenberg_id', 'sentence_text', 'flags'} <= props
    props = {r[1] for r in _rows(conn, "CALL table_info('TOTELoop') RETURN *")}
    assert {'modality_cell', 'actor_cell', 'action_cell', 'object_cell', 'perspective_cell', 'status', 'provenance'} <= props
    # no duplicate gestalt / gate tables were introduced
    assert not tables & {'Modality', 'NychGestalt', 'ToteGate'}
    assert poc.count(conn, 'SymbolPattern') == 0          # schema only


def test_measures_loaded_as_assumed_priors(conn):
    m = json.loads((ROOT / '_config/invariants/measures.json').read_text())
    assert poc.count(conn, 'Measure') == len(m['entries']) and poc.count(conn, 'MeasureRule') == len(m['context_rules'])
    assert one(conn, "MATCH (x:Measure) WHERE x.weight_source <> 'assumed_prior' RETURN count(x)") == 0
    assert one(conn, "MATCH (r:MeasureRule) WHERE r.rank = 0 RETURN r.rule_id") == 'MEAS-WORTH'
    assert one(conn, "MATCH (:Measure{word:'stitch'})-[w:MEASURE_WEIGHT_IN]->(:Domain{domain_id:'craft.knitting'}) RETURN w.sense_weight") == 'high'


def test_domain_links_derived(tmp_path):
    c = poc.open_db(tmp_path / 'kg.kuzu', rebuild=True)
    t = ToteDB.on_connection(c)
    c.execute("MATCH (l:TOTELoop{loop_id:'TL-APPROACH-LOCATION-001'}),(d:Domain{domain_id:'astronomy.observation'}) CREATE (l)-[:IN_DOMAIN{role:'cross_link',evidence:'t',provenance:'t'}]->(d)")
    pairs = t.refresh_domain_links()
    assert any(p['n'] >= 1 for p in pairs)
    assert one(c, 'MATCH (:Domain)-[r:DOMAIN_LINK]->(:Domain) RETURN count(r)') == len(pairs)


def _rows(c, q):
    r = c.execute(q); out = []
    while r.has_next(): out.append(r.get_next())
    return out
