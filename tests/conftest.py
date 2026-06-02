from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def db_path() -> Path:
    """Return the path to the golden test fixture database.

    Tests that need the SQLite DB should declare ``db_path`` as a parameter
    rather than hard-coding the path themselves.
    """
    return Path(__file__).parent / "fixtures" / "test.db"


@pytest.fixture
def minimal_spine_df() -> pd.DataFrame:
    """Minimal valid (player_id, gw) fct spine for unit tests. No live DB required.

    2 players x 3 GWs, all SGW. Contains every column required by
    build_player_gameweek_state plus position_code for mart position mapping.
    """
    rows = [
        {
            "player_id": 1,
            "gw": 1,
            "is_bgw": False,
            "is_dgw": False,
            "minutes": 90.0,
            "xgi": 0.4,
            "xgc": 0.2,
            "clean_sheets": 1.0,
            "goals_conceded": 0.0,
            "position_code": 3,
        },
        {
            "player_id": 1,
            "gw": 2,
            "is_bgw": False,
            "is_dgw": False,
            "minutes": 60.0,
            "xgi": 0.1,
            "xgc": 0.5,
            "clean_sheets": 0.0,
            "goals_conceded": 1.0,
            "position_code": 3,
        },
        {
            "player_id": 1,
            "gw": 3,
            "is_bgw": False,
            "is_dgw": False,
            "minutes": 90.0,
            "xgi": 0.6,
            "xgc": 0.1,
            "clean_sheets": 1.0,
            "goals_conceded": 0.0,
            "position_code": 3,
        },
        {
            "player_id": 2,
            "gw": 1,
            "is_bgw": False,
            "is_dgw": False,
            "minutes": 90.0,
            "xgi": 0.2,
            "xgc": 0.3,
            "clean_sheets": 0.0,
            "goals_conceded": 2.0,
            "position_code": 2,
        },
        {
            "player_id": 2,
            "gw": 2,
            "is_bgw": False,
            "is_dgw": False,
            "minutes": 0.0,
            "xgi": 0.0,
            "xgc": 0.4,
            "clean_sheets": 0.0,
            "goals_conceded": 1.0,
            "position_code": 2,
        },
        {
            "player_id": 2,
            "gw": 3,
            "is_bgw": False,
            "is_dgw": False,
            "minutes": 45.0,
            "xgi": 0.3,
            "xgc": 0.2,
            "clean_sheets": 1.0,
            "goals_conceded": 0.0,
            "position_code": 2,
        },
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def minimal_feat_df(minimal_spine_df: pd.DataFrame) -> pd.DataFrame:
    """minimal_spine_df + all 13 governed feat columns. No live DB required.

    Built by running build_player_gameweek_state on minimal_spine_df so it
    is always in sync with the actual feat layer implementation.
    """
    from dal.feat.feat_player_gameweek import build_player_gameweek_state

    return build_player_gameweek_state(minimal_spine_df)
