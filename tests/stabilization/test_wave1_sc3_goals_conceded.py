"""Wave 1 SC-3 — goals_conceded must sum across DGW fixtures, not average.

FAILING TEST committed before any fix.

Bug: _build_team_defensive_records uses ("goals_conceded", "mean") instead of "sum".
For a team with two DGW fixtures each conceding 1 goal, the current code returns
goals_conceded=1.0 (mean), when the correct value is 2 (sum).

Rationale: Goals conceded is additive. A team that conceded 1 goal in each of two
DGW fixtures conceded 2 goals in that gameweek. Averaging underestimates defensive
weakness and creates systematic bias in rolling opponent defensive metrics.

Tests use:
  - Synthetic player_fixture_base matching golden DB DGW scenario
  - Golden DB (P2 at T2, GW4: F5 concedes 1 + F6 concedes 1 = 2 total)
"""

from pathlib import Path

import pandas as pd

from dal.intermediate.int_opponent_context import _build_team_defensive_records

TEST_DB_PATH = Path(__file__).parent.parent / "fixtures" / "test.db"


def _make_dgw_analytics() -> pd.DataFrame:
    """Minimal analytics frame: T2 has two GW4 fixtures each conceding 1 goal.

    After correct fix: goals_conceded for T2/GW4 = 2 (sum).
    With bug:          goals_conceded for T2/GW4 = 1.0 (mean).
    """
    rows = [
        # GK row: team_id=2, GW4, fixture_id=5 — T2 concedes 1
        {"player_id": 102, "team_id": 2, "gw": 4, "fixture_id": 5,
         "position_code": 1, "minutes": 90, "goals_conceded": 1, "xgc": 1.0},
        # GK row: team_id=2, GW4, fixture_id=6 — T2 concedes 1
        {"player_id": 102, "team_id": 2, "gw": 4, "fixture_id": 6,
         "position_code": 1, "minutes": 90, "goals_conceded": 1, "xgc": 1.0},
        # SGW row for baseline comparison: team_id=2, GW3, fixture_id=4 — T2 concedes 1
        {"player_id": 102, "team_id": 2, "gw": 3, "fixture_id": 4,
         "position_code": 1, "minutes": 90, "goals_conceded": 1, "xgc": 0.9},
    ]
    df = pd.DataFrame(rows)
    return df


def test_goals_conceded_sums_across_dgw_fixtures():
    """SC-3 FAILING TEST: goals_conceded for a DGW team must be sum, not mean.

    T2 concedes 1 in each of 2 GW4 fixtures → total = 2.
    Bug: current code uses mean → returns 1.0.
    Fixed code: uses sum → returns 2.

    FAILS before fix (returns 1.0). PASSES after fix (returns 2).
    """
    analytics = _make_dgw_analytics()
    analytics_90 = analytics[analytics["minutes"] == 90]
    team_def = _build_team_defensive_records(analytics, analytics_90)

    t2_gw4 = team_def[(team_def["team_id"] == 2) & (team_def["gw"] == 4)]
    assert len(t2_gw4) == 1, f"Expected 1 row for T2/GW4, got {len(t2_gw4)}"

    actual = t2_gw4.iloc[0]["goals_conceded"]
    assert actual == 2, (
        f"Expected goals_conceded=2 for T2 in GW4 (sum of 1+1 across two fixtures), "
        f"got {actual}. Bug: mean({1},{1})={1.0} used instead of sum."
    )


def test_goals_conceded_sgw_unchanged():
    """SGW goals_conceded must equal the single fixture value (sum of 1 = 1).

    This test passes both before and after the fix for SGW rows.
    Confirms the fix does not regress SGW behaviour.
    """
    analytics = _make_dgw_analytics()
    analytics_90 = analytics[analytics["minutes"] == 90]
    team_def = _build_team_defensive_records(analytics, analytics_90)

    t2_gw3 = team_def[(team_def["team_id"] == 2) & (team_def["gw"] == 3)]
    assert len(t2_gw3) == 1
    assert t2_gw3.iloc[0]["goals_conceded"] == 1, (
        "SGW goals_conceded should be 1 (sum of single fixture)"
    )
