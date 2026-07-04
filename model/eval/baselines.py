"""Naive baselines for next-gameweek FPL points — Phase 0.1 of the predictive-layer plan.

These are the floor every signal and model must beat. Each baseline predicts a
player-gameweek's ``total_points`` from **strictly-prior** rows only, so the
features are leakage-safe by construction (all use ``shift(1)`` within a player,
or an expanding position aggregate that excludes the current gameweek).

Population contract (v1): ``minutes > 0``, DGW excluded — the project base
population. Warmup gameweeks (too little history for a window) yield NaN features
and are dropped by the harness.
"""

from __future__ import annotations

import pandas as pd

# Rolling-window lengths (in appearances) for the rolling-average baselines.
ROLL_WINDOWS = (3, 5)

# Baseline column -> human label. The harness scores exactly these columns.
BASELINES: dict[str, str] = {
    "base_last": "last-GW points",
    "base_roll3": "rolling avg (3)",
    "base_roll5": "rolling avg (5)",
    "base_season": "expanding season avg",
    "base_posmean": "position mean (identity-free)",
}


def build_baseline_features(mart: pd.DataFrame) -> pd.DataFrame:
    """Attach leakage-safe baseline predictions to each player-gameweek row.

    Args:
        mart: player-gameweek frame with columns
            ``player_id, gw, position, minutes, total_points, is_dgw``.

    Returns:
        A copy restricted to the v1 population (``minutes > 0``, DGW excluded),
        sorted by (player, gw), with one column per key in ``BASELINES`` plus the
        ``total_points`` target. Rows whose player-history is too short to fill a
        given baseline carry NaN in that column (the harness drops them per-metric).
    """
    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)

    # All windows are computed WITHIN each player via transform, so a rolling/
    # expanding window can never reach across into another player's rows. shift(1)
    # first guarantees the current gameweek never enters its own prediction.
    pts = df.groupby("player_id")["total_points"]
    df["base_last"] = pts.transform(lambda s: s.shift(1))
    for k in ROLL_WINDOWS:
        df[f"base_roll{k}"] = pts.transform(lambda s, k=k: s.shift(1).rolling(k, min_periods=k).mean())
    df["base_season"] = pts.transform(lambda s: s.shift(1).expanding().mean())

    df["base_posmean"] = _position_expanding_mean(df)
    return df


def _position_expanding_mean(df: pd.DataFrame) -> pd.Series:
    """Mean points of a player's position over all **earlier** gameweeks.

    Identity-free floor: it knows only "how do DEF/MID/FWD/GK score on average so
    far", not who the player is. Excludes the current gameweek to stay leakage-safe.
    """
    per = (
        df.groupby(["position", "gw"])["total_points"].agg(["sum", "count"]).reset_index().sort_values("gw")
    )
    cum_sum = per.groupby("position")["sum"].cumsum() - per["sum"]
    cum_cnt = per.groupby("position")["count"].cumsum() - per["count"]
    per["base_posmean"] = (cum_sum / cum_cnt).where(cum_cnt > 0)
    return df.merge(per[["position", "gw", "base_posmean"]], on=["position", "gw"], how="left")["base_posmean"]
