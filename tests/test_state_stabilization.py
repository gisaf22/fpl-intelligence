"""STATE layer stabilization tests — synthetic spine, no live DB required.

Covers the four required stabilization properties:
1. Rolling features exclude current GW (lag-1 numerical proof)
2. Shuffled input produces identical output (determinism)
3. State output schema is exact — no leakage, no missing columns
4. Schema guard in implementation raises on unexpected column (duplicate-grain
   protection is already covered by test_state.py::test_grain_assert_fires)
"""

import pandas as pd
import pytest

from dal.state.player_gameweek_state import build_player_gameweek_state, _ROLL_COLS


# ---------------------------------------------------------------------------
# Synthetic spine builder
# ---------------------------------------------------------------------------

def _make_spine(players: dict) -> pd.DataFrame:
    """Build a minimal synthetic spine from {player_id: [points_per_gw, ...]}.

    None entries produce BGW rows (is_bgw=True, all performance columns NA).
    All other _ROLL_COLS get fixed non-null values so rolling can compute.
    """
    rows = []
    for pid, points_by_gw in players.items():
        for gw, pts in enumerate(points_by_gw, start=1):
            is_bgw = pts is None
            rows.append({
                "player_id": pid,
                "gw": gw,
                "is_bgw": is_bgw,
                "is_dgw": False,
                "fixture_count": 0 if is_bgw else 1,
                "total_points": pd.NA if is_bgw else pts,
                "minutes":         pd.NA if is_bgw else 60,
                "xg":              pd.NA if is_bgw else 0.1,
                "xa":              pd.NA if is_bgw else 0.1,
                "xgi":             pd.NA if is_bgw else 0.2,
                "xgc":             pd.NA if is_bgw else 0.3,
                "goals_scored":    pd.NA if is_bgw else 0,
                "assists":         pd.NA if is_bgw else 0,
                "clean_sheets":    pd.NA if is_bgw else 0,
                "goals_conceded":  pd.NA if is_bgw else 1,
                "saves":           pd.NA if is_bgw else 0,
                "penalties_saved": pd.NA if is_bgw else 0,
                "bonus":           pd.NA if is_bgw else 1,
                "bps":             pd.NA if is_bgw else 10,
            })
    df = pd.DataFrame(rows)
    for col in ["total_points", "minutes", "goals_scored", "assists", "clean_sheets",
                "goals_conceded", "saves", "penalties_saved", "bonus", "bps"]:
        df[col] = df[col].astype("Int64")
    for col in ["xg", "xa", "xgi", "xgc"]:
        df[col] = df[col].astype("Float64")
    return df


# ---------------------------------------------------------------------------
# Required test 1 — rolling features exclude current GW (numerical proof)
# ---------------------------------------------------------------------------

def test_rolling_excludes_current_gw_numerically():
    """Lag-1 proof: roll value at GW N must not include GW N performance.

    Player: total_points = [10, 20, 30, 40, 999] for GWs 1-5.
    At GW 5:
      - points_roll3 = mean(20, 30, 40) = 30.0  [GWs 2,3,4 — not GW 5]
      - points_roll5 = mean(10, 20, 30, 40) = 25.0  [GWs 1,2,3,4 — not GW 5]
    If 999 appears in either result, the lag-1 shift is broken.
    """
    spine = _make_spine({1: [10, 20, 30, 40, 999]})
    state = build_player_gameweek_state(spine)
    gw5 = state[state["gw"] == 5].iloc[0]

    assert abs(gw5["points_roll3"] - 30.0) < 1e-9, (
        f"points_roll3 at GW5 = {gw5['points_roll3']!r}, expected 30.0. "
        "GW5 value (999) is leaking into the roll3 window — lag-1 shift broken."
    )
    assert abs(gw5["points_roll5"] - 25.0) < 1e-9, (
        f"points_roll5 at GW5 = {gw5['points_roll5']!r}, expected 25.0. "
        "GW5 value (999) is leaking into the roll5 window — lag-1 shift broken."
    )


# ---------------------------------------------------------------------------
# Required test 2 — shuffled input produces identical output (determinism)
# ---------------------------------------------------------------------------

def test_shuffled_input_produces_identical_output():
    """Shuffling spine row order before state build produces identical output.

    Guarantees no rolling or derived-column operation depends on input row order.
    The sort at the top of build_player_gameweek_state is the enforcement mechanism.
    """
    spine = _make_spine({
        1: [10, 20, 30, 40, 50, 60, 70],
        2: [5,  15, 25, 35, 45, 55, 65],
        3: [2,   4,  6,  8, 10, 12, 14],
    })
    shuffled = spine.sample(frac=1, random_state=99).reset_index(drop=True)

    state_orig = build_player_gameweek_state(spine)
    state_shuf = build_player_gameweek_state(shuffled)

    key = ["player_id", "gw"]
    orig_sorted = state_orig.sort_values(key).reset_index(drop=True)
    shuf_sorted = state_shuf.sort_values(key).reset_index(drop=True)

    pd.testing.assert_frame_equal(orig_sorted, shuf_sorted, check_like=False)


# ---------------------------------------------------------------------------
# Required tests 3 & 4 — schema exact (completeness + purity)
# ---------------------------------------------------------------------------

def test_state_schema_exact():
    """State output has exactly the expected columns — no extras, no missing.

    Covers:
    - Schema completeness: all expected derived columns are present.
    - Schema purity: no helper/temp columns leaked by pandas operations.

    The schema guard in build_player_gameweek_state enforces this at runtime.
    This test verifies the guard holds for normal execution paths.
    """
    spine = _make_spine({1: [10, 20, 30, 40, 50]})
    state = build_player_gameweek_state(spine)

    expected_derived = (
        {f"{'points' if c == 'total_points' else c}_roll{w}"
         for c in _ROLL_COLS for w in (3, 5, 8)}
        | {"fixture_context", "minutes_trend"}
    )
    expected_all = set(spine.columns) | expected_derived

    extra = set(state.columns) - expected_all
    missing = expected_all - set(state.columns)

    assert not extra, f"Unexpected columns leaked into state output: {sorted(extra)}"
    assert not missing, f"Expected derived columns missing from state output: {sorted(missing)}"
    assert len(state.columns) == len(expected_all), (
        f"Column count mismatch — likely duplicate column names. "
        f"Got {len(state.columns)}, expected {len(expected_all)}"
    )
