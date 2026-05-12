"""Tests for pipeline/dal/state/player_gameweek_state.py — live DB."""

from pathlib import Path

import pandas as pd
import pytest

from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.curated.contracts import SPINE_COLS
from dal.state.player_gameweek_state import build_player_gameweek_state
from dal.exceptions import DALContractViolation
from dal.validation import validate_grain_uniqueness

DB_PATH = Path.home() / ".fpl" / "fpl.db"

_STATE_COLS = [
    "points_roll3", "points_roll5",
    "minutes_roll3", "minutes_roll5",
    "xg_roll3", "xg_roll5",
    "xa_roll3", "xa_roll5",
    "xgi_roll3", "xgi_roll5",
    "xgc_roll3", "xgc_roll5",
    "goals_scored_roll3", "goals_scored_roll5",
    "assists_roll3", "assists_roll5",
    "clean_sheets_roll3", "clean_sheets_roll5",
    "goals_conceded_roll3", "goals_conceded_roll5",
    "saves_roll3", "saves_roll5",
    "penalties_saved_roll3", "penalties_saved_roll5",
    "bonus_roll3", "bonus_roll5",
    "bps_roll3", "bps_roll5",
    "fixture_context",
    "minutes_trend",
]

_EXPECTED_COLS = set(SPINE_COLS) | set(_STATE_COLS)


@pytest.fixture(scope="module")
def state():
    spine = build_player_gameweek_spine(DB_PATH)
    return build_player_gameweek_state(spine)


def test_column_presence(state):
    """Output contains all spine columns plus all state-derived columns."""
    assert set(state.columns) == _EXPECTED_COLS, (
        f"Extra: {set(state.columns) - _EXPECTED_COLS}. "
        f"Missing: {_EXPECTED_COLS - set(state.columns)}"
    )
    assert len(state.columns) == len(_EXPECTED_COLS)


def test_grain_preserved(state):
    """(player_id, gw) is unique in output. Row count matches input spine."""
    spine = build_player_gameweek_spine(DB_PATH)
    assert not state.duplicated(subset=["player_id", "gw"]).any()
    assert len(state) == len(spine)


def test_rolling_correctness(state):
    """points_roll3 at the 4th GW position for a player matches manual calculation.

    With shift(1).rolling(3, min_periods=1), the value at index 3 is the mean of
    total_points at indices 0, 1, 2 (the prior 3 GWs).
    """
    player_counts = state.groupby("player_id")["gw"].count()
    candidates = player_counts[player_counts >= 5].index
    assert len(candidates) > 0, "Need at least one player with 5+ GWs"

    pid = candidates[0]
    player_rows = state[state["player_id"] == pid].sort_values("gw").reset_index(drop=True)

    # 4th row (index 3) — shift(1).rolling(3) at index 3 looks at indices 0, 1, 2
    expected = player_rows.loc[0:2, "total_points"].mean()
    actual = player_rows.loc[3, "points_roll3"]
    assert abs(actual - expected) < 1e-9, f"Expected {expected}, got {actual}"


def test_min_periods_gw2(state):
    """GW2 rows for players who played GW1 have non-null points_roll3."""
    # Only players who also played GW1 (non-BGW at GW1) can have a non-null roll at GW2
    played_gw1 = set(state[(state["gw"] == 1) & state["total_points"].notna()]["player_id"])
    gw2 = state[(state["gw"] == 2) & state["player_id"].isin(played_gw1)]
    gw2_with_data = gw2[gw2["total_points"].notna()]
    assert gw2_with_data["points_roll3"].notna().all()


def test_fixture_context_values(state):
    """fixture_context is a three-way label: BGW / SGW / DGW (SC-13 fix)."""
    assert set(state["fixture_context"].unique()).issubset({"BGW", "SGW", "DGW"})
    assert (state[state["is_dgw"] == True]["fixture_context"] == "DGW").all()
    assert (state[state["is_bgw"] == True]["fixture_context"] == "BGW").all()
    sgw_mask = (state["is_dgw"] == False) & (state["is_bgw"] == False)
    assert (state[sgw_mask]["fixture_context"] == "SGW").all()


def test_minutes_trend_nulls(state):
    """Players with fewer than 6 GW rows have null minutes_trend for all their rows."""
    row_counts = state.groupby("player_id")["gw"].count()
    sparse_players = row_counts[row_counts < 6].index
    if len(sparse_players) == 0:
        pytest.skip("No players with fewer than 6 GW rows in dataset")
    sparse_rows = state[state["player_id"].isin(sparse_players)]
    assert sparse_rows["minutes_trend"].isna().all(), (
        "Expected all minutes_trend to be null for players with < 6 GW rows"
    )


def test_minutes_trend_values(state):
    """minutes_trend contains only 'rising', 'stable', 'falling', and null."""
    valid = {"rising", "stable", "falling"}
    non_null = state["minutes_trend"].dropna()
    unexpected = set(non_null.unique()) - valid
    assert not unexpected, f"Unexpected minutes_trend values: {unexpected}"


def test_grain_assert_fires():
    """State layer validates grain uniqueness of its generated spine."""
    spine = build_player_gameweek_spine(DB_PATH)
    state = build_player_gameweek_state(spine)
    validate_grain_uniqueness(state, ["player_id", "gw"], "state")
