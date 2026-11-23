"""Stage 06 taxonomy: parsers on tiny files and the resolve shortcut on a tiny graph (no downloads)."""
import sys
from pathlib import Path

import kuzu
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "shared"))

from nych3.store.tote_db import schema_statements  # noqa: E402
from nych3.taxonomy.build import Loader, cip_nodes, tier  # noqa: E402
from nych3.taxonomy.resolve import resolve, singulars  # noqa: E402


def test_cip_levels_parents_and_reserved(tmp_path):
    f = tmp_path / "cip.csv"
    f.write_text('"CIPFamily","CIPCode","Action","TextChange","CIPTitle","CIPDefinition","CrossReferences","Examples"\n'
                 '="22",="22","No substantive changes",no,"LEGAL PROFESSIONS AND STUDIES.","Law.","",\n'
                 '="22",="22.01","No substantive changes",no,"Law.","Law series.","",\n'
                 '="22",="22.0101","No substantive changes",no,"Law.","JD.","",\n'
                 '="21",="21","No substantive changes",no,"Reserved.","","",\n'
                 '="22",="22.9999","Moved to 22.0101",no,"Old.","","",\n', encoding="utf-8")
    nodes = {n["code"]: n for n in cip_nodes(f)}
    assert set(nodes) == {"22", "22.01", "22.0101"}
    assert (nodes["22"]["level"], nodes["22.01"]["parent"], nodes["22.0101"]["parent"]) == (2, "22", "22.01")


def test_tier_bands():
    assert (tier(1.2), tier(3.5), tier(4.0)) == ("expert", "intermediate", "novice")


@pytest.fixture()
def graph(tmp_path):
    db = kuzu.Database(str(tmp_path / "t.kuzu"))
    c = kuzu.Connection(db)
    for q in schema_statements():
        c.execute(q)
    L = Loader(c)
    L.nodes("Domain", [{"domain_id": "naics:54", "name": "Professional", "kind": "naics", "code": "54", "level": 2, "description": ""},
                       {"domain_id": "naics:541110", "name": "Offices of Lawyers", "kind": "naics", "code": "541110", "level": 6, "description": ""},
                       {"domain_id": "naics:23", "name": "Construction", "kind": "naics", "code": "23", "level": 2, "description": ""}])
    L.rels("DOMAIN_PARENT", ("Domain", "domain_id"), ("Domain", "domain_id"), [{"a": "naics:541110", "b": "naics:54"}])
    L.nodes("Profession", [{"profession_id": "onet:23-1011.00", "soc_code": "23-1011", "title": "Lawyers", "description": ""}])
    L.nodes("StudyArea", [{"study_id": "cip:22", "code": "22", "level": 2, "title": "Legal", "definition": ""},
                          {"study_id": "cip:22.0101", "code": "22.0101", "level": 6, "title": "Law", "definition": ""}])
    L.rels("STUDY_PARENT", ("StudyArea", "study_id"), ("StudyArea", "study_id"), [{"a": "cip:22.0101", "b": "cip:22"}])
    L.rels("STUDY_LEADS_TO", ("StudyArea", "study_id"), ("Profession", "profession_id"),
           [{"a": "cip:22.0101", "b": "onet:23-1011.00", "source": "t"}])
    L.nodes("Term", [{"term": "plaintiff", "zipf": 3.55, "tier": "intermediate"},
                     {"term": "summary judgment", "zipf": 4.02, "tier": "novice"},
                     {"term": "for", "zipf": 7.0, "tier": "novice"},
                     {"term": "concrete", "zipf": 4.5, "tier": "novice"}])
    L.rels("TERM_DOMAIN", ("Term", "term"), ("Domain", "domain_id"),
           [{"a": "plaintiff", "b": "naics:541110", "tier": "intermediate", "weight": 1.0, "source": "t"},
            {"a": "summary judgment", "b": "naics:541110", "tier": "novice", "weight": 1.0, "source": "t"},
            {"a": "for", "b": "naics:23", "tier": "novice", "weight": 1.0, "source": "t"},
            {"a": "concrete", "b": "naics:23", "tier": "novice", "weight": 1.0, "source": "t"}])
    L.rels("TERM_PROFESSION", ("Term", "term"), ("Profession", "profession_id"),
           [{"a": "plaintiff", "b": "onet:23-1011.00", "tier": "intermediate", "weight": 1.0, "source": "t"}])
    return c


def test_resolve_ranks_rolls_up_and_ignores_common_words(graph):
    r = resolve(graph, "The plaintiff asked for summary judgment.", k=3)
    assert [t["term"] for t in r["terms"]] == ["plaintiff", "summary judgment"]  # "for" is too common (R5)
    assert r["sectors"][0]["id"] == "naics:54" and r["sectors"][0]["terms"] == 2
    assert r["industries"][0]["id"] == "naics:541110"
    assert r["professions"][0]["title"] == "Lawyers"
    assert r["study_areas"][0]["id"] == "cip:22"
    assert r["competency"]["label"] == ["intermediate", "novice"]  # tie kept (R4)


def test_resolve_more_supporting_words_wins(graph):
    r = resolve(graph, "concrete plaintiff summary judgment", k=1)
    assert [s["id"] for s in r["sectors"]] == ["naics:54"]


def test_resolve_unresolved(graph):
    assert resolve(graph, "nothing here matches")["domains"] == ["unresolved domain"]


def test_singulars():
    assert singulars("dentists") == ["dentist"]
    assert singulars("liabilities")[0] == "liability"
    assert singulars("statutes") == ["statut", "statute"]
    assert singulars("glass") == [] and singulars("gas") == [] and singulars("law") == []


def test_resolve_matches_plurals(graph):
    r = resolve(graph, "Plaintiffs filed for summary judgments.", k=3)
    assert [(t["term"], t.get("as_written")) for t in r["terms"]] == [("plaintiff", "plaintiffs"), ("summary judgment", "summary judgments")]
    assert r["professions"][0]["title"] == "Lawyers"
