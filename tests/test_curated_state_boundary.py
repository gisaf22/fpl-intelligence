"""CURATED → STATE boundary contract tests — synthetic spine, no live DB required.

Verifies every implicit assumption STATE makes about CURATED output:

1. Ordering contract   — STATE sorts on entry; unsorted CURATED output produces identical results.
                         Extends test_state_stabilization coverage to include DGW rows.
2. Grain uniqueness    — STATE rejects duplicate (player_id, gw) before any rolling computation.
3. BGW NULL semantics  — STATE rejects zero-substituted BGW performance values at entry.
4. BGW NULL divergence — Demonstrates WHY the NULL contract is semantic: zeros inflate averages.
5. Schema completeness — STATE raises on missing required CURATED columns (before opaque errors).
6. Schema passthrough  — Extra CURATED columns pass through STATE output unchanged.
7. DGW aggregation     — DGW-summed performance is stable and deterministic in STATE rolling.
"""

import pandas as pd
import pytest

from dal.state.player_gameweek_state import (
    build_player_gameweek_state,
    _ROLL_COLS,
    _REQUIRED_INPUT_COLS,
)


# ---------------------------------------------------------------------------
# Synthetic spine factory
# ---------------------------------------------------------------------------

def _make_spine(players: dict, *, extra_col: str | None = None) -> pd.DataFrame:
    """Build a minimal synthetic spine covering all columns STATE reads.

    players: {player_id: [(gw, pts, is_bgw, is_dgw), ...]}

    BGW rows: is_bgw=True, all performance columns set to pd.NA (correct contract semantics).
    DGW rows: is_dgw=True, fixture_count=2, performance columns are non-NULL (aggregated sums).
    SGW rows: is_bgw=False, is_dgw=False, fixture_count=1.

    extra_col: if provided, adds a constant-value pass-through column to simulate CURATED
    adding a new column before STATE is updated.
    """
    rows = []
    for pid, gw_specs in players.items():
        for gw, pts, is_bgw, is_dgw in gw_specs:
            row = {
                "player_id":       pid,
                "gw":              gw,
                "is_bgw":          is_bgw,
                "is_dgw":          is_dgw,
                "fixture_count":   0 if is_bgw else (2 if is_dgw else 1),
                "total_points":    pd.NA if is_bgw else pts,
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
            }
            if extra_col is not None:
                row[extra_col] = "extra_value"
            rows.append(row)

    df = pd.DataFrame(rows)
    for col in ["total_points", "minutes", "goals_scored", "assists", "clean_sheets",
                "goals_conceded", "saves", "penalties_saved", "bonus", "bps"]:
        df[col] = df[col].astype("Int64")
    for col in ["xg", "xa", "xgi", "xgc"]:
        df[col] = df[col].astype("Float64")
    return df


def _sgw_spine(n_gws: int = 7, pts_fn=None) -> pd.DataFrame:
    """Single player, n_gws of SGW. pts_fn(gw) → points; defaults to gw."""
    if pts_fn is None:
        pts_fn = lambda gw: gw
    return _make_spine({1: [(gw, pts_fn(gw), False, False) for gw in range(1, n_gws + 1)]})


# ---------------------------------------------------------------------------
# Contract 1 — Ordering
# ---------------------------------------------------------------------------

def test_ordering_shuffled_spine_with_dgw_identical_output():
    """STATE output is identical for sorted vs. shuffled input when DGW rows are present.

    Extends test_state_stabilization.test_shuffled_input_produces_identical_output by
    including DGW rows, which affect fixture_context derivation. Confirms STATE's
    unconditional entry sort covers the full range of CURATED output patterns.
    """
    spine = _make_spine({
        1: [(gw, gw * 3, False, False) for gw in range(1, 8)],
        2: [(1, 5, False, False), (2, pd.NA, True, False), (3, 8, False, False),
            (4, 15, False, True), (5, 6, False, False), (6, 7, False, False)],
        3: [(1, 10, False, False), (2, 22, False, True), (3, 5, False, False),
            (4, 9, False, False), (5, 4, False, False)],
    })
    shuffled = spine.sample(frac=1, random_state=42).reset_index(drop=True)

    result_sorted   = build_player_gameweek_state(spine)
    result_shuffled = build_player_gameweek_state(shuffled)

    key = ["player_id", "gw"]
    pd.testing.assert_frame_equal(
        result_sorted.sort_values(key).reset_index(drop=True),
        result_shuffled.sort_values(key).reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# Contract 2 — Grain uniqueness at entry
# ---------------------------------------------------------------------------

def test_grain_duplicate_input_rejected_at_state_entry():
    """STATE rejects duplicate (player_id, gw) rows before any rolling computation.

    Without the entry guard, a duplicate row silently participates in rolling windows,
    distorting averages for all subsequent GWs of that player. The exit grain check
    in build_player_gameweek_state fires only after that corruption has occurred.
    """
    spine = _sgw_spine(5)
    dup_row = spine[spine["gw"] == 3].copy()
    spine_with_dup = pd.concat([spine, dup_row], ignore_index=True)

    with pytest.raises(ValueError, match="grain"):
        build_player_gameweek_state(spine_with_dup)


# ---------------------------------------------------------------------------
# Contract 3 — BGW NULL semantics at entry
# ---------------------------------------------------------------------------

def test_bgw_zero_substitution_rejected_at_state_entry():
    """STATE rejects BGW rows where performance columns contain 0 instead of NULL.

    CURATED guarantees BGW performance columns are pd.NA. If a caller (e.g., a test
    helper or non-CURATED source) substitutes zeros, rolling averages are silently wrong.
    The entry guard closes this gap by failing before any computation runs.
    """
    spine = _sgw_spine(5)
    # Inject a BGW row with zero-substituted total_points (semantic violation)
    spine = spine.copy()
    spine.loc[spine["gw"] == 3, "is_bgw"] = True
    spine.loc[spine["gw"] == 3, "total_points"] = pd.array([0], dtype="Int64")

    with pytest.raises(ValueError, match="BGW"):
        build_player_gameweek_state(spine)


# ---------------------------------------------------------------------------
# Contract 4 — BGW NULL vs. zero divergence (demonstrates the semantic risk)
# ---------------------------------------------------------------------------

def test_bgw_null_vs_zero_rolling_divergence():
    """BGW NULL and zero-substituted BGW produce different rolling averages.

    This is a direct demonstration of why the NULL contract is semantically significant.
    Rolling mean skips NA values; substituting 0 includes them, inflating the average.

    Sequence at GWs 1–5: [10, 20, BGW, 30, 40]
    At GW5, roll3 window covers GWs 2–4 (lag-1 shift):
      NULL version:  mean(20, NA, 30)  = mean([20, 30])       = 25.0
      Zero version:  mean(20,  0, 30)  = mean([20, 0,  30])   = 16.67
    """
    points_null = pd.array([10, 20, pd.NA, 30, 40], dtype="Int64")
    points_zero = pd.array([10, 20, 0,     30, 40], dtype="Int64")

    def _roll3_at_gw5(arr: pd.array) -> float:
        return float(
            pd.Series(arr, dtype="Float64")
            .shift(1)
            .rolling(3, min_periods=1)
            .mean()
            .iloc[4]
        )

    roll3_null = _roll3_at_gw5(points_null)
    roll3_zero = _roll3_at_gw5(points_zero)

    assert abs(roll3_null - 25.0) < 1e-9, (
        f"NULL BGW roll3 expected 25.0, got {roll3_null}"
    )
    assert abs(roll3_zero - (50.0 / 3)) < 1e-9, (
        f"Zero BGW roll3 expected {50.0/3:.4f}, got {roll3_zero}"
    )
    assert roll3_null != roll3_zero, (
        "BGW NULL and BGW zero produce identical rolling averages — "
        "the test logic is wrong or pandas behavior has changed"
    )


# ---------------------------------------------------------------------------
# Contract 5 — Schema completeness at entry
# ---------------------------------------------------------------------------

def test_required_input_cols_constant_is_superset_of_roll_cols():
    """_REQUIRED_INPUT_COLS covers all _ROLL_COLS plus identity columns.

    This is a static contract check: ensures the published constant is internally
    consistent and cannot drift out of sync with _ROLL_COLS.
    """
    assert set(_ROLL_COLS).issubset(_REQUIRED_INPUT_COLS), (
        f"_REQUIRED_INPUT_COLS is missing _ROLL_COLS entries: "
        f"{set(_ROLL_COLS) - _REQUIRED_INPUT_COLS}"
    )
    assert {"player_id", "gw", "is_bgw", "is_dgw"}.issubset(_REQUIRED_INPUT_COLS)


def test_missing_required_column_raises_at_state_entry():
    """STATE raises ValueError when a required CURATED column is absent from input.

    Without the entry guard, a missing column produces an opaque KeyError deep inside
    the grouped rolling transform. The entry guard surfaces the contract violation
    immediately with a clear error message identifying the missing column.
    """
    spine = _sgw_spine(5)
    spine_missing = spine.drop(columns=["total_points"])

    with pytest.raises(ValueError, match="missing"):
        build_player_gameweek_state(spine_missing)


# ---------------------------------------------------------------------------
# Contract 6 — Schema passthrough stability
# ---------------------------------------------------------------------------

def test_extra_curated_column_passes_through_state_unchanged():
    """Columns CURATED adds beyond STATE's declared dependencies pass through unchanged.

    When CURATED adds a new column before STATE is updated, STATE must not silently
    strip it. The STATE exit schema guard permits pass-through columns (it only flags
    columns that appear in output but not in spine and not in declared derivations).
    """
    spine = _make_spine(
        {1: [(gw, gw, False, False) for gw in range(1, 6)]},
        extra_col="deadline_time",
    )
    assert "deadline_time" in spine.columns

    state = build_player_gameweek_state(spine)

    assert "deadline_time" in state.columns, (
        "Pass-through column 'deadline_time' was stripped by STATE — "
        "extra CURATED columns must survive the boundary unchanged"
    )
    # The exit schema guard must not have fired (it checks output - spine - derived == {})
    # If this test passes without RuntimeError, the guard correctly permits pass-through columns.


# ---------------------------------------------------------------------------
# Contract 7 — DGW aggregation stability in STATE rolling
# ---------------------------------------------------------------------------

def test_dgw_aggregated_points_used_correctly_in_rolling():
    """DGW summed performance is correctly consumed by STATE rolling windows.

    CURATED guarantees DGW performance is the sum across 2 fixtures. STATE treats DGW
    rows identically to SGW rows for rolling purposes — it does not re-aggregate.
    This verifies the rolling value at GW5 correctly reflects the DGW total (not half of it).

    Sequence: GW1=5, GW2=7, GW3=12(DGW), GW4=8, GW5=6
    At GW5, roll3 covers GWs 2–4 (lag-1 shift): mean(7, 12, 8) = 9.0
    """
    spine = _make_spine({
        1: [(1, 5, False, False), (2, 7, False, False), (3, 12, False, True),
            (4, 8, False, False), (5, 6, False, False)],
    })
    state = build_player_gameweek_state(spine)

    gw5_roll3 = float(state[state["gw"] == 5]["points_roll3"].iloc[0])
    assert abs(gw5_roll3 - 9.0) < 1e-9, (
        f"DGW points not correctly reflected in roll3: expected 9.0, got {gw5_roll3}. "
        "STATE may be re-aggregating DGW values instead of using CURATED sums as-is."
    )


def test_dgw_aggregation_deterministic_regardless_of_input_order():
    """DGW rolling results are identical whether the DGW row arrives first or last in input.

    Complements Contract 1 specifically for DGW rows — ensures the sort at STATE entry
    produces the same groupby order for DGW players regardless of CURATED output ordering.
    """
    spine = _make_spine({
        1: [(1, 5, False, False), (2, 7, False, False), (3, 12, False, True),
            (4, 8, False, False), (5, 6, False, False), (6, 9, False, False)],
    })
    shuffled = spine.sample(frac=1, random_state=99).reset_index(drop=True)

    state_ordered  = build_player_gameweek_state(spine)
    state_shuffled = build_player_gameweek_state(shuffled)

    key = ["player_id", "gw"]
    pd.testing.assert_frame_equal(
        state_ordered.sort_values(key).reset_index(drop=True),
        state_shuffled.sort_values(key).reset_index(drop=True),
    )
