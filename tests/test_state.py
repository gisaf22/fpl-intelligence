"""Smoke tests for the feat layer (build_player_gameweek_state) — live DB."""

from pathlib import Path

import pytest

from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.staging import load_staged_entities
from dal.intermediate.int_player_fixture import get_player_fixture_base

pytestmark = pytest.mark.integration

DB_PATH = Path.home() / ".fpl" / "fpl.db"


def _load_spine():
    staged = load_staged_entities(DB_PATH)
    return build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)


@pytest.fixture(scope="module")
def state():
    spine = _load_spine()
    return build_player_gameweek_state(spine)


def test_grain_preserved(state):
    """(player_id, gw) is unique in feat output. Row count matches input spine."""
    spine = _load_spine()
    assert not state.duplicated(subset=["player_id", "gw"]).any()
    assert len(state) == len(spine)


def test_rolling_correctness(state):
    """xgi_roll3 at the 4th GW for a player matches manual mean of the prior 3 GW xgi values."""
    player_counts = state.groupby("player_id")["gw"].count()
    candidates = player_counts[player_counts >= 5].index
    assert len(candidates) > 0, "Need at least one player with 5+ GWs"

    pid = candidates[0]
    player_rows = state[state["player_id"] == pid].sort_values("gw").reset_index(drop=True)

    # shift(1).rolling(3) at index 3 looks at indices 0, 1, 2
    expected = player_rows.loc[0:2, "xgi"].mean()
    actual = player_rows.loc[3, "xgi_roll3"]
    assert abs(actual - expected) < 1e-9, f"Expected {expected}, got {actual}"


def test_fixture_context_values(state):
    """fixture_context is a three-way label: BGW / SGW / DGW."""
    assert set(state["fixture_context"].unique()).issubset({"BGW", "SGW", "DGW"})
    assert (state[state["is_dgw"] == True]["fixture_context"] == "DGW").all()
    assert (state[state["is_bgw"] == True]["fixture_context"] == "BGW").all()
    sgw_mask = (state["is_dgw"] == False) & (state["is_bgw"] == False)
    assert (state[sgw_mask]["fixture_context"] == "SGW").all()
