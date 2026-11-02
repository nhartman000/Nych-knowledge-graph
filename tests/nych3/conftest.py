import pytest
from nych3.pipeline import run
from nych3.store.tote_db import ToteDB

PETER = "Peter loved looking at the stars from the hill behind his house. One clear night he noticed a wolf."
PROMPT = "Encode this story with NYCH."


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "tote.kuzu"
    ToteDB(p, rebuild=True)
    return p


@pytest.fixture
def encode(tmp_path, db_path):
    def _enc(story=PETER, prompt=PROMPT, **kw):
        kw.setdefault("db_path", str(db_path))
        return run(prompt, story, name=kw.pop("name", "t"), root=tmp_path / "run", **kw)
    return _enc


@pytest.fixture
def peter(encode):
    return encode()
