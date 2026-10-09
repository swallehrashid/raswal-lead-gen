import json
from pathlib import Path

import pytest

from pipeline.settings import FIXTURES_DIR, load_config


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES_DIR


def load_json(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
