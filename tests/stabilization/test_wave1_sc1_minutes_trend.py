"""Wave 1 SC-1 — minutes_trend look-ahead leak.

FAILING TEST committed before any fix.

Bug: _compute_minutes_trend uses rolling(3).mean() without shift(1) for last3.
At GW N, last3 includes minutes from GW N itself — temporal look-ahead.

Proof: player with 7 GWs minutes=[90,90,90,0,0,0,90].
At GW 7:
  - Buggy (no shift): last3 = mean(minutes[4],minutes[5],minutes[6]) = mean(0,0,90) = 30
    diff = 30 - 60 = -30 → "stable"
  - Fixed (shift(1)): last3 = mean(minutes[3],minutes[4],minutes[5]) = mean(0,0,0) = 0
    diff = 0 - 60 = -60 → "falling"

The test asserts "falling" — this FAILS before the fix and PASSES after.
"""

import pandas as pd
import pytest

from dal.feat.feat_player_gameweek import build_player_gameweek_state

pytestmark = pytest.mark.unit


def _make_synthetic_spine(minutes_by_gw: list[int | None]) -> pd.DataFrame:
    """Build a minimal spine DataFrame for a single player with given minutes per GW.

    None entries represent BGW rows (fixture_count=0, is_bgw=True, minutes=pd.NA).
    Non-None entries are SGW rows (fixture_count=1, is_bgw=False).
    """
    rows = []
    for i, m in enumerate(minutes_by_gw):
        gw = i + 1
        is_bgw = m is None
        rows.append(
            {
                "player_id": 1,
                "gw": gw,
                "is_bgw": is_bgw,
                "is_dgw": False,
                "fixture_count": 0 if is_bgw else 1,
                "minutes": pd.NA if is_bgw else m,
                "total_points": pd.NA if is_bgw else 2,
                "xg": pd.NA if is_bgw else 0.0,
                "xa": pd.NA if is_bgw else 0.0,
                "xgi": pd.NA if is_bgw else 0.0,
                "xgc": pd.NA if is_bgw else 0.5,
                "goals_scored": pd.NA if is_bgw else 0,
                "assists": pd.NA if is_bgw else 0,
                "clean_sheets": pd.NA if is_bgw else (1 if not is_bgw else pd.NA),
                "goals_conceded": pd.NA if is_bgw else 0,
                "saves": pd.NA if is_bgw else 0,
                "penalties_saved": pd.NA if is_bgw else 0,
                "bonus": pd.NA if is_bgw else 0,
                "bps": pd.NA if is_bgw else 0,
            }
        )
    df = pd.DataFrame(rows)
    df["minutes"] = df["minutes"].astype("Int64")
    df["total_points"] = df["total_points"].astype("Int64")
    df["goals_scored"] = df["goals_scored"].astype("Int64")
    df["assists"] = df["assists"].astype("Int64")
    df["clean_sheets"] = df["clean_sheets"].astype("Int64")
    df["goals_conceded"] = df["goals_conceded"].astype("Int64")
    df["saves"] = df["saves"].astype("Int64")
    df["penalties_saved"] = df["penalties_saved"].astype("Int64")
    df["bonus"] = df["bonus"].astype("Int64")
    df["bps"] = df["bps"].astype("Int64")
    df["xg"] = df["xg"].astype("Float64")
    df["xa"] = df["xa"].astype("Float64")
    df["xgi"] = df["xgi"].astype("Float64")
    df["xgc"] = df["xgc"].astype("Float64")
    return df


def test_minutes_trend_lag1_convention():
    """SC-1 FAILING TEST: minutes_trend at GW N must not use GW N minutes.

    Player: 7 GWs, minutes=[90,90,90,0,0,0,90].
    At GW 7:
      - prior3 (GWs 1-3) = mean(90,90,90) = 90
      - With correct lag-1: last3 = mean(GWs 4,5,6) = mean(0,0,0) = 0 → falling
      - With bug (no shift): last3 = mean(GWs 5,6,7) = mean(0,0,90) = 30 → stable

    Asserts "falling". FAILS before fix (returns "stable"). PASSES after fix.
    """
    spine = _make_synthetic_spine([90, 90, 90, 0, 0, 0, 90])
    state = build_player_gameweek_state(spine)
    gw7 = state[state["gw"] == 7].iloc[0]
    assert gw7["minutes_trend"] == "falling", (
        f"Expected 'falling' at GW 7 (lag-1 convention: last3 uses GWs 4,5,6 = [0,0,0]), "
        f"got {gw7['minutes_trend']!r}. "
        f"Bug: no shift(1) on last3 causes look-ahead — last3 sees GW7's 90 min."
    )


def test_minutes_trend_null_at_gw1():
    """minutes_trend must be null at GW 1 for all players — no prior data.

    This test passes both before and after the fix (documents expected behaviour).
    Included here as a golden-value regression guard for Wave 1 exit criteria.
    """
    spine = _make_synthetic_spine([90, 90, 90, 0, 0, 0, 90])
    state = build_player_gameweek_state(spine)
    gw1_trend = state[state["gw"] == 1].iloc[0]["minutes_trend"]
    assert gw1_trend is None or (isinstance(gw1_trend, float) and pd.isna(gw1_trend)), (
        f"minutes_trend at GW 1 must be null, got {gw1_trend!r}"
    )
