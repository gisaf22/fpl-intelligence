"""Wave 1 SC-11 — missing GW context must raise DALContractViolation immediately.

FAILING TEST committed before any fix.

Bug: when get_gameweek_context returns fewer GWs than are present in fixture history,
build_player_gameweek_spine logs a WARNING and continues. The spine build will always
fail later at null semantics validation (deadline_time is never_null). This is a silent
failure mode — the error message at null semantics validation is cryptic compared to
an explicit error at the missing-context detection point.

Fix: replace the warning block with an immediate DALContractViolation raise.

The failing test:
  - Patches get_gameweek_context to return only GW1-4
  - Patches get_player_fixture_base to include data for GW1-5
  - Asserts DALContractViolation is raised (not just logged)
  - FAILS before fix (no exception raised). PASSES after fix (exception raised).
"""

import pandas as pd
import pytest

from dal.exceptions import DALContractViolation
from dal.fct.fct_player_gameweek import build_player_gameweek_spine

pytestmark = pytest.mark.unit

def _make_minimal_player_fixture_base() -> pd.DataFrame:
    """Return a minimal player_fixture_base covering GWs 1-5 for one player."""
    rows = []
    for gw in range(1, 6):
        rows.append({
            "player_id": 1,
            "gw": gw,
            "fixture_id": gw * 10,
            "was_home": 1,
            "home_team_id": 1,
            "away_team_id": 2,
            "team_id": 1,
            "opponent_team_id": 2,
            "player_name": "Test",
            "position_code": 1,
            "position_label": "GKP",
            "purchase_price": 5.5,
            "ownership_count": 1000,
            "minutes": 90,
            "total_points": 6,
            "goals_scored": 0,
            "assists": 0,
            "clean_sheets": 1,
            "goals_conceded": 0,
            "own_goals": 0,
            "penalties_saved": 0,
            "penalties_missed": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "saves": 2,
            "bonus": 1,
            "bps": 20,
            "xg": 0.0,
            "xa": 0.0,
            "xgi": 0.0,
            "xgc": 0.5,
            "starts": 1,
            "in_dreamteam": 0,
            "influence": 20.0,
            "creativity": 10.0,
            "threat": 15.0,
            "ict_index": 4.5,
            "fixture_difficulty": 3,
            "transfers_in": 100,
            "transfers_out": 80,
            "transfers_balance": 20,
            "kickoff_time": "2025-08-16T12:30:00Z",
            "home_team_score": 1,
            "away_team_score": 0,
            "home_team_name": "T1",
            "away_team_name": "T2",
            "home_team_strength_overall": 1200,
            "home_team_strength_attack": 1250,
            "home_team_strength_defence": 1150,
            "away_team_strength_overall": 1100,
            "away_team_strength_attack": 1150,
            "away_team_strength_defence": 1050,
        })
    df = pd.DataFrame(rows)
    return df

def _make_gw_context_missing_gw5() -> pd.DataFrame:
    """Return events covering GWs 1-4 only (GW5 is missing)."""
    rows = []
    for gw in range(1, 5):
        rows.append({
            "gw": gw,
            "deadline_time": f"2025-08-{14 + gw * 7:02d}T18:00:00Z",
            "finished": 1,
            "is_previous": 0,
            "is_live": 0,
            "is_next": 0,
            "average_entry_score": 52,
            "highest_score": 120,
            "transfers_made": 500000,
        })
    return pd.DataFrame(rows)

def test_missing_gw_context_raises_immediately():
    """SC-11 FAILING TEST: missing GW context must raise DALContractViolation.

    Patches get_player_fixture_base to return data for GWs 1-5.
    Patches get_gameweek_context to return only GWs 1-4.

    Assert DALContractViolation raised during spine build, naming GW5 as missing.
    FAILS before fix (warning logged but no exception). PASSES after fix (exception raised).
    """
    player_fixture_base = _make_minimal_player_fixture_base()
    gw_context = _make_gw_context_missing_gw5()

    with pytest.raises(DALContractViolation) as exc_info:
        build_player_gameweek_spine(player_fixture_base, gw_context)

    assert "5" in str(exc_info.value), (
        f"Exception message should name GW 5 as missing. Got: {exc_info.value}"
    )

def test_missing_gw_context_does_not_return_partial_result():
    """SC-11: no partial DataFrame should be returned when GW context is missing."""
    player_fixture_base = _make_minimal_player_fixture_base()
    gw_context = _make_gw_context_missing_gw5()

    result = None
    try:
        result = build_player_gameweek_spine(player_fixture_base, gw_context)
    except (DALContractViolation, Exception):
        pass  # exception is expected

    assert result is None, (
        "build_player_gameweek_spine must not return a partial DataFrame when GW context is missing"
    )
