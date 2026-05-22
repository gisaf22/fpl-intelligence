"""State layer — player gameweek analytical state variables."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dal.validation.grain import validate_grain_uniqueness

_ROLL_COLS = [
    "total_points",
    "minutes",
    "xg",
    "xa",
    "xgi",
    "xgc",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "saves",
    "penalties_saved",
    "bonus",
    "bps",
]

# Columns that CURATED must provide for STATE to function correctly.
# Used by the entry contract guard — any caller (test or production) that omits
# these columns will get a clear error before any computation runs.
_REQUIRED_INPUT_COLS: frozenset[str] = frozenset(
    ["player_id", "gw", "is_bgw", "is_dgw"] + _ROLL_COLS
)


def _validate_spine_entry_contract(spine: pd.DataFrame) -> None:
    """Assert CURATED → STATE boundary preconditions before any computation.

    Three invariants that STATE relies on but previously assumed without checking:
    1. Required columns present — avoids opaque KeyError deep in rolling transform.
    2. Grain uniqueness — a duplicate (player_id, gw) pair corrupts every rolling window
       for that player; the exit grain check fires too late to prevent that corruption.
    3. BGW performance columns are NULL — zero-substituted BGW values are semantically
       wrong and silently inflate rolling averages (mean([20, 0, 30]) ≠ mean([20, 30])).
    """
    missing = _REQUIRED_INPUT_COLS - set(spine.columns)
    if missing:
        raise ValueError(
            f"build_player_gameweek_state: required input columns missing: {sorted(missing)}"
        )

    dupes = spine.duplicated(subset=["player_id", "gw"])
    if dupes.any():
        n = int(dupes.sum())
        raise ValueError(
            f"build_player_gameweek_state: {n} duplicate (player_id, gw) rows in input — "
            "grain must be unique before STATE computation"
        )

    bgw = spine[spine["is_bgw"] == True]
    if not bgw.empty:
        for col in _ROLL_COLS:
            if col not in spine.columns:
                continue
            bad = bgw[bgw[col].notna()]
            if not bad.empty:
                raise ValueError(
                    f"build_player_gameweek_state: BGW rows have non-NULL '{col}' "
                    f"({len(bad)} rows) — zero-substituted BGW values corrupt rolling averages"
                )


def _compute_minutes_trend(minutes_series: pd.Series) -> pd.Series:
    # shift(1): lag-1 convention — GW N trend uses only GW 1..N-1 data, never GW N itself
    last3 = minutes_series.shift(1).rolling(3, min_periods=3).mean()
    prior3 = minutes_series.shift(3).rolling(3, min_periods=3).mean()
    diff = last3 - prior3
    trend = pd.Series(index=minutes_series.index, dtype="object")
    trend[diff > 30] = "rising"
    trend[diff < -30] = "falling"
    trend[diff.abs() <= 30] = "stable"
    trend[last3.isna() | prior3.isna()] = None
    return trend


def build_player_gameweek_state(spine: pd.DataFrame) -> pd.DataFrame:
    """Derive analytical state variables from the player GW spine.

    Grain: (player_id, gw) unique on exit — same as input spine.
    """
    _validate_spine_entry_contract(spine)

    # Step 1 — sort
    df = spine.sort_values(["player_id", "gw"]).reset_index(drop=True)

    # Step 2 — rolling windows (lag-1: prior GWs only, not including current)
    # NULLs (BGW, pre-transfer) are skipped; rolling computes with available non-NULL values
    for col in _ROLL_COLS:
        col_short = "points" if col == "total_points" else col
        roll3_col = f"{col_short}_roll3"
        roll5_col = f"{col_short}_roll5"
        roll8_col = f"{col_short}_roll8"

        df[roll3_col] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        )
        df[roll5_col] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
        )
        df[roll8_col] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(8, min_periods=1).mean())
        )

    # Step 3 — fixture_context: three-way label (BGW rows were previously mapped to "SGW")
    df["fixture_context"] = np.select(
        [df["is_bgw"], df["is_dgw"]],
        ["BGW", "DGW"],
        default="SGW",
    )

    # Step 4 — minutes_trend
    df["minutes_trend"] = (
        df.groupby("player_id")["minutes"]
        .transform(_compute_minutes_trend)
    )

    # Step 5 — schema guard: assert no columns leaked beyond the declared derivations
    _state_derived = (
        {f"{'points' if c == 'total_points' else c}_roll{w}" for c in _ROLL_COLS for w in (3, 5, 8)}
        | {"fixture_context", "minutes_trend"}
    )
    _leaked = set(df.columns) - set(spine.columns) - _state_derived
    if _leaked:
        raise RuntimeError(
            f"build_player_gameweek_state: unexpected columns in output: {sorted(_leaked)}"
        )

    # Step 6 — assert grain
    validate_grain_uniqueness(df, "player_gameweek_state")

    return df
