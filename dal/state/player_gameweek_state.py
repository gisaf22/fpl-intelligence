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
    # Step 1 — sort
    df = spine.sort_values(["player_id", "gw"]).reset_index(drop=True)

    # Step 2 — rolling windows (lag-1: prior GWs only, not including current)
    # NULLs (BGW, pre-transfer) are skipped; rolling computes with available non-NULL values
    for col in _ROLL_COLS:
        col_short = "points" if col == "total_points" else col
        roll3_col = f"{col_short}_roll3"
        roll5_col = f"{col_short}_roll5"

        df[roll3_col] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        )
        df[roll5_col] = (
            df.groupby("player_id")[col]
            .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
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

    # Step 5 — assert grain
    validate_grain_uniqueness(df, ["player_id", "gw"], "build_player_gameweek_state")

    return df
