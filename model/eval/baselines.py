"""Naive baselines for next-gameweek FPL points — Phase 0.1 of the predictive-layer plan.

These are the floor every signal and model must beat. Each baseline predicts a
player-gameweek's ``total_points`` from **strictly-prior** rows only, so the
features are leakage-safe by construction (all use ``shift(1)`` within a player).

Population contract (v1): ``minutes > 0``, DGW excluded — the project base
population. Warmup gameweeks (too little history for a window) yield NaN features
and are dropped by the harness.
"""

from __future__ import annotations

import pandas as pd

# Rolling-window lengths (in appearances) for the rolling-average baselines.
ROLL_WINDOWS = (3, 5)

# Baseline column -> human label. The harness ranks exactly these columns.
# (A position-mean column was dropped: constant within a (gw, position) group, it
# carries no within-position rank signal, and absolute-error (MAE) is too haul-noisy
# in FPL to compare models by — ranking per position is the decision-relevant metric.)
BASELINES: dict[str, str] = {
    "base_last": "last-GW points",
    "base_roll3": "rolling avg (3)",
    "base_roll5": "rolling avg (5)",
    "base_season": "expanding season avg",
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
    df["base_season"] = expanding_prior_mean(df)          # single source of the expanding-prior-mean stat
    return df


def expanding_prior_mean(mart: pd.DataFrame) -> pd.Series:
    """A player's expanding prior-mean points, as a standalone Series.

    This one statistic underlies the ``base_season`` baseline column, the Phase-1 ``lvl_mean``, and the
    Phase-2/3 incumbent bar - which is *why* they are numerically equal. Leakage-safe: ``shift(1)``
    before the expanding mean excludes the current gameweek. Aligned to ``mart``'s index.

    Population-agnostic - the result's *meaning* follows the rows you pass: on the **canonical**
    population (``minutes > 0``, DGW excluded) it is the ``base_season`` column / ``lvl_mean``; on a
    blanks-included frame it is the "incl-blanks" variant for ex-ante blank scoring (Phase 5,
    ``points_model`` ``keep_all``). To reproduce the ``base_season`` column, pass the canonical
    population - the full mart would silently fold in 0-minute blanks.

    Input contract: ``mart`` carries the mart's ``total_points`` column - numeric
    (``Int64``, nullable on BGW per ``MART_SCHEMA``). Every caller derives its frame
    from the schema-validated mart (filter/sort/merge preserve the dtype), so no
    numeric coercion is needed here.
    """
    return mart.groupby("player_id")["total_points"].transform(
        lambda s: s.shift(1).expanding().mean()
    )
