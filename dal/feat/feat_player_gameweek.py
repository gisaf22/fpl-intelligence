"""Feature layer — derives analytical state variables from the fct spine.

Appends rolling windows, fixture context label, and minutes trend to the (player_id, gw)
spine produced by fct. Does not aggregate, filter, or change grain — all output rows
correspond 1:1 with input rows. BGW rows are skipped in rolling windows (NULL-aware).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dal.feat.feat_schema import FEATURE_REGISTRY
from dal.validation.grain import validate_grain_uniqueness

_ROLL_COLS = [
    "minutes",
    "xgi",
    "xgc",
    "clean_sheets",
    "goals_conceded",
]

# Columns that FCT must provide for FEAT to function correctly.
# Used by the entry contract guard — any caller (test or production) that omits
# these columns will get a clear error before any computation runs.
_REQUIRED_INPUT_COLS: frozenset[str] = frozenset(["player_id", "gw", "is_bgw", "is_dgw", *_ROLL_COLS])

# Derived from FEATURE_REGISTRY — the single source of truth for governed output columns.
# Add a column by registering it in FEATURE_REGISTRY (feat_schema.py), not here.
_GOVERNED_ROLLING_COLS: frozenset[str] = frozenset(FEATURE_REGISTRY.keys())


def _validate_spine_entry_contract(spine: pd.DataFrame) -> None:
    """Assert FCT → FEAT boundary preconditions before any computation.

    Three invariants that FEAT relies on but previously assumed without checking:
    1. Required columns present — avoids opaque KeyError deep in rolling transform.
    2. Grain uniqueness — a duplicate (player_id, gw) pair corrupts every rolling window
       for that player; the exit grain check fires too late to prevent that corruption.
    3. BGW performance columns are NULL — zero-substituted BGW values are semantically
       wrong and silently inflate rolling averages (mean([20, 0, 30]) ≠ mean([20, 30])).
    """
    missing = _REQUIRED_INPUT_COLS - set(spine.columns)
    if missing:
        raise ValueError(f"build_player_gameweek_state: required input columns missing: {sorted(missing)}")

    dupes = spine.duplicated(subset=["player_id", "gw"])
    if dupes.any():
        n = int(dupes.sum())
        raise ValueError(
            f"build_player_gameweek_state: {n} duplicate (player_id, gw) rows in input — "
            "grain must be unique before FEAT computation"
        )

    bgw = spine[spine["is_bgw"].astype(bool)]
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
    # PROVISIONAL-EDITORIAL threshold — STATE-T-01: 30-minute divergence boundary has no
    # empirical calibration; availability domain only (see _AVAILABILITY_DOMAIN_ONLY).
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

    df = spine.sort_values(["player_id", "gw"]).reset_index(drop=True)

    # Lag-1: prior GWs only. NULLs (BGW, pre-transfer) are skipped by rolling.
    # xa excluded: absorbed by xgi (G-EDA6-02). roll8 for minutes only (LENS-AVAIL AVAIL-003).
    # Excluded cols (total_points, xg, goals_scored, assists, saves, penalties_saved, bonus, bps):
    # removed by lens evaluation (evaluation_circularity or G2-FAIL).
    for col in _ROLL_COLS:
        df[f"{col}_roll3"] = df.groupby("player_id")[col].transform(
            lambda x: x.shift(1).rolling(3, min_periods=1).mean()
        )
        df[f"{col}_roll5"] = df.groupby("player_id")[col].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).mean()
        )
        if col == "minutes":
            df["minutes_roll8"] = df.groupby("player_id")[col].transform(
                lambda x: x.shift(1).rolling(8, min_periods=1).mean()
            )

    # BGW rows were previously mapped to "SGW" — three-way label introduced to fix that
    df["fixture_context"] = np.select(
        [df["is_bgw"], df["is_dgw"]],
        ["BGW", "DGW"],
        default="SGW",
    )

    # Availability domain only — CONDITIONAL, no empirical threshold calibration
    df["minutes_trend"] = df.groupby("player_id")["minutes"].transform(_compute_minutes_trend)

    # Governance assertion: derived columns must exactly equal _GOVERNED_ROLLING_COLS
    _produced = set(df.columns) - set(spine.columns)
    if _produced != _GOVERNED_ROLLING_COLS:
        _extra = _produced - _GOVERNED_ROLLING_COLS
        _missing = _GOVERNED_ROLLING_COLS - _produced
        raise RuntimeError(
            f"build_player_gameweek_state: FEAT column set diverged from governed set.\n"
            f"Extra (unapproved): {sorted(_extra)}\n"
            f"Missing (approved but absent): {sorted(_missing)}"
        )

    validate_grain_uniqueness(df, "player_gameweek_state")

    return df
