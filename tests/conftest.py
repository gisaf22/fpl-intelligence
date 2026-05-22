from pathlib import Path

import pytest


@pytest.fixture
def db_path() -> Path:
    """Return the path to the golden test fixture database.

    Tests that need the SQLite DB should declare ``db_path`` as a parameter
    rather than hard-coding the path themselves.
    """
    return Path(__file__).parent / "fixtures" / "test.db"
