import pytest
from nych3.store.tote_db import ToteDB


def test_seed_and_commonality(db_path):
    db = ToteDB(db_path)
    assert db.count() == 2 and db.count("canonical") == 1 and db.count("candidate") == 1
    assert db.commonality() == [{"loop_id": "TL-LOOK-AT-STARS-001", "domains": ["astronomy.observation", "human_action.perception"]}] or \
        db.commonality()[0]["loop_id"] == "TL-LOOK-AT-STARS-001"
    g = db.gate("G-EXIT-LOOK-AT-STARS-001")
    assert g["outcomes"] == {"PASS": "exit", "FAIL": "repeat"}


def test_canonical_needs_authority(db_path):
    db = ToteDB(db_path)
    with pytest.raises(ValueError, match="authority"):
        db.add_loop({"loop_id": "X", "domain": "d", "action_lemma": "a", "object_lemma": "b"}, status="canonical",
                    provenance={"source": "inferred story path", "authority": None})


def test_harvest_then_lookup(encode, db_path):
    st = encode(harvest=True)[0]
    assert st["tote"]["harvest_persisted"] == [st["tote"]["harvest_candidates"][0]["loop_id"]]
    db = ToteDB(db_path)
    row = db.get(st["tote"]["harvest_candidates"][0]["loop_id"])
    assert row["status"] == "candidate" and row["provenance"]["method"] == "HARVEST-NL-1"
    del db
    st2 = encode(name="t2")[0]
    inst = st2["tote"]["instances"][2]
    assert inst["template_id"].startswith("TL-H-NOTICE-WOLF-") and inst["template_status"] == "candidate"
    assert inst["retrieval"]["method"] == "exact_action_object"
