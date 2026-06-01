"""DAL integrity tests — spine completeness. Contract: Section 2, Section 7, Section 9."""

import pytest

from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.fct.validation import validate_row_count_invariant, validate_time_continuity
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.staging import load_staged_entities

pytestmark = pytest.mark.unit


def _load_spine(db_path):
    staged = load_staged_entities(db_path)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)


def test_spine_row_count_invariant(db_path):
    """Spine has exactly n_players x n_gws rows — BGW rows must be present. Contract Section 2."""
    spine = _load_spine(db_path)
    n_players = spine["player_id"].nunique()
    n_gws = spine["gw"].nunique()
    validate_row_count_invariant(spine, n_players, n_gws)


def test_spine_time_continuity(db_path):
    """Every player has a contiguous GW sequence with no gaps — BGW rows fill blanks. Contract Section 7."""
    spine = _load_spine(db_path)
    validate_time_continuity(spine)
