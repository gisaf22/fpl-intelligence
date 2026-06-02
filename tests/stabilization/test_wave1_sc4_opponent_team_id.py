"""Wave 1 SC-4 — opponent_team_id must be derived from fixture context.

FAILING TEST committed before any fix.

Status: opponent_team_id is present in staging from player_histories.opponent_team
(FPL API field). However, the intermediate layer must DERIVE and OVERRIDE it from
fixture home/away team data, which is more authoritative than the staging pass-through.

Bug: _resolve_player_side_context does not set opponent_team_id from fixture context.
It leaves the staging value unchanged. If staging has a wrong value (e.g. due to
FPL API inconsistency), the intermediate layer silently propagates the error.

Failing test: craft a DataFrame where staging's opponent_team_id is intentionally wrong
(99), but home/away teams are correct. Assert the intermediate layer overrides to the
fixture-derived value.

  - away player (was_home=0): opponent = home_team_id = 10
  - Current code: returns opponent_team_id=99 (staging pass-through) → FAILS
  - Fixed code: derives opponent_team_id=10 from home_team_id → PASSES
"""

import pandas as pd
import pytest

from dal.intermediate.int_player_fixture import _resolve_player_side_context

pytestmark = pytest.mark.unit


def _make_fixture_row(
    was_home: int, home_team_id: int, away_team_id: int, staging_opponent_team_id: int, staging_team_id: int
) -> pd.DataFrame:
    """Return a single-row DataFrame mimicking the join output before _resolve_player_side_context."""
    return pd.DataFrame(
        [
            {
                "player_id": 1,
                "gw": 1,
                "fixture_id": 100,
                "was_home": was_home,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_team_difficulty": 3,
                "away_team_difficulty": 4,
                "team_id": staging_team_id,
                "opponent_team_id": staging_opponent_team_id,  # staging value, may be wrong
                "player_name": "Test Player",
                "minutes": 90,
                "total_points": 6,
                "goals_scored": 1,
                "assists": 0,
                "clean_sheets": 0,
                "goals_conceded": 0,
                "xg": 0.5,
                "xa": 0.1,
                "xgi": 0.6,
                "xgc": 0.3,
                "position_code": 4,
                "position_label": "FWD",
                "home_team_name": "Home FC",
                "away_team_name": "Away FC",
                "home_team_strength_overall": 1200,
                "home_team_strength_attack": 1250,
                "home_team_strength_defence": 1150,
                "away_team_strength_overall": 1100,
                "away_team_strength_attack": 1150,
                "away_team_strength_defence": 1050,
                "purchase_price": 7.5,
                "ownership_count": 5000,
                "transfers_in": 100,
                "transfers_out": 80,
                "transfers_balance": 20,
                "own_goals": 0,
                "penalties_saved": 0,
                "penalties_missed": 0,
                "yellow_cards": 0,
                "red_cards": 0,
                "saves": 0,
                "bonus": 0,
                "bps": 20,
                "starts": 1,
                "in_dreamteam": 0,
                "influence": 30.0,
                "creativity": 20.0,
                "threat": 40.0,
                "ict_index": 9.0,
                "kickoff_time": "2025-08-16T12:30:00Z",
                "home_team_score": 1,
                "away_team_score": 0,
            }
        ]
    )


def test_opponent_team_id_overrides_staging_for_away_player():
    """SC-4 FAILING TEST: intermediate layer must derive opponent_team_id from fixture data.

    Away player (was_home=0): opponent is the home team (home_team_id=10).
    Staging has wrong opponent_team_id=99.

    Assert result["opponent_team_id"] == 10 (fixture-derived, not 99 from staging).
    FAILS before fix (returns 99). PASSES after fix (overrides with 10).
    """
    df = _make_fixture_row(
        was_home=0,
        home_team_id=10,
        away_team_id=20,
        staging_opponent_team_id=99,  # wrong staging value
        staging_team_id=20,  # away team is this player's team
    )
    result = _resolve_player_side_context(df)
    assert result["opponent_team_id"].iloc[0] == 10, (
        f"Expected opponent_team_id=10 (derived from home_team_id for away player), "
        f"got {result['opponent_team_id'].iloc[0]}. "
        f"Bug: _resolve_player_side_context does not override staging opponent_team_id."
    )


def test_opponent_team_id_overrides_staging_for_home_player():
    """SC-4 FAILING TEST: home player's opponent must be the away team.

    Home player (was_home=1): opponent is the away team (away_team_id=20).
    Staging has wrong opponent_team_id=99.

    Assert result["opponent_team_id"] == 20 (fixture-derived, not 99 from staging).
    FAILS before fix (returns 99). PASSES after fix (overrides with 20).
    """
    df = _make_fixture_row(
        was_home=1,
        home_team_id=10,
        away_team_id=20,
        staging_opponent_team_id=99,  # wrong staging value
        staging_team_id=10,  # home team is this player's team
    )
    result = _resolve_player_side_context(df)
    assert result["opponent_team_id"].iloc[0] == 20, (
        f"Expected opponent_team_id=20 (derived from away_team_id for home player), "
        f"got {result['opponent_team_id'].iloc[0]}. "
        f"Bug: _resolve_player_side_context does not override staging opponent_team_id."
    )


def test_opponent_team_id_never_null_after_fix():
    """Post-fix: opponent_team_id must never be null for any resolved player fixture."""
    df = _make_fixture_row(
        was_home=0,
        home_team_id=10,
        away_team_id=20,
        staging_opponent_team_id=10,
        staging_team_id=20,
    )
    result = _resolve_player_side_context(df)
    assert result["opponent_team_id"].notna().all(), "opponent_team_id must never be null"
