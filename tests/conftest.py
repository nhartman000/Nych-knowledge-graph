import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'stages' / '04-poc-run'))
import poc  # noqa: E402


@pytest.fixture(scope='session')
def conn(tmp_path_factory):
    return poc.open_db(tmp_path_factory.mktemp('kg') / 'kg.kuzu', rebuild=True)
