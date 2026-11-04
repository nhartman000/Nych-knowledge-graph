import pytest

spacy = pytest.importorskip("spacy")


def test_spacy_parser_peter(encode):
    try:
        st = encode(parser="spacy")[0]
    except OSError:
        pytest.skip("en_core_web_sm not installed")
    assert st["manifest"]["parser"]["name"] == "spacy"
    lemmas = [e["lemma"] for e in st["temporal"]["events"]]
    assert lemmas[:2] == ["love", "look"]
    assert st["temporal"]["time_anchors"][0]["scoped_to_events"] == [st["temporal"]["events"][-1]["event_id"]]
