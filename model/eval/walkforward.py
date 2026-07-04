"""Walk-forward scoring harness — Phase 0.2 of the predictive-layer plan.

The temporal-CV substrate every later model plugs into. Because the baseline
features are built from strictly-prior gameweeks (see ``baselines.py``), scoring
each row against its own target *is* an expanding-window walk-forward: the
prediction for gameweek ``t`` uses only gameweeks ``< t``. This module verifies
that guarantee and reports per-gameweek and pooled metrics.

Metrics: MAE and RMSE (point accuracy) plus per-gameweek Spearman (ranking — the
decision-relevant read, since FPL is won by ranking players, not by hitting exact
scores).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from model.eval.baselines import BASELINES, build_baseline_features

# Gameweeks below this are warmup (too little history for rolling/expanding windows).
WARMUP_GW = 3
# Minimum rows in a gameweek to compute a stable rank correlation for that GW.
MIN_ROWS_PER_GW = 20
# Baselines built from a player's OWN prior rows — these must be undefined on the
# player's first appearance. (base_posmean is excluded: it reads other players'
# earlier gameweeks, which are legitimately available on any first appearance.)
_PLAYER_HISTORY_BASELINES = ("base_last", "base_roll3", "base_roll5", "base_season")


def _assert_no_leakage(features: pd.DataFrame) -> None:
    """Guard: no player-history baseline may derive from a player's own current/future row.

    The features are shift(1)/expanding by construction; this re-checks the
    invariant by confirming no player-history baseline is defined on a player's
    very first row (there is nothing prior to draw on).
    """
    first_rows = features.groupby("player_id").head(1)
    leaked = first_rows[list(_PLAYER_HISTORY_BASELINES)].notna().any(axis=1)
    if bool(leaked.any()):
        raise AssertionError("leakage: a player-history baseline is defined on a player's first appearance")


def score_predictions(features: pd.DataFrame, pred_col: str, target_col: str = "total_points") -> dict:
    """Pooled + per-gameweek metrics for one prediction column, evaluated post-warmup.

    Args:
        features:  output of ``build_baseline_features`` (or any frame with the
                   prediction, ``total_points``, and ``gw``).
        pred_col:  the prediction column to score.
        target_col: the realised outcome column.

    Returns:
        Dict ``{mae, rmse, spearman_mean, n}`` — ``spearman_mean`` is the mean of
        per-gameweek rank correlations (only GWs with >= MIN_ROWS_PER_GW rows), so
        it measures within-week ranking, not a pooled cross-week artifact.
    """
    ev = features[features["gw"] > WARMUP_GW].dropna(subset=[pred_col, target_col])
    if ev.empty:
        return {"mae": np.nan, "rmse": np.nan, "spearman_mean": np.nan, "n": 0}

    err = ev[pred_col] - ev[target_col]
    mae = float(err.abs().mean())
    rmse = float(np.sqrt((err**2).mean()))

    rhos = []
    for _, grp in ev.groupby("gw"):
        if len(grp) >= MIN_ROWS_PER_GW and grp[pred_col].nunique() > 1 and grp[target_col].nunique() > 1:
            rhos.append(float(spearmanr(grp[pred_col], grp[target_col]).statistic))
    spearman_mean = float(np.mean(rhos)) if rhos else np.nan

    return {"mae": round(mae, 4), "rmse": round(rmse, 4),
            "spearman_mean": round(spearman_mean, 4), "n": len(ev)}


def walk_forward_baselines(mart: pd.DataFrame) -> pd.DataFrame:
    """Score every baseline on the mart via the leakage-checked walk-forward.

    Returns a frame indexed by baseline (label) with mae / rmse / spearman_mean / n,
    sorted by spearman_mean descending — the frozen Phase-0 benchmark.
    """
    features = build_baseline_features(mart)
    _assert_no_leakage(features)
    rows = []
    for col, label in BASELINES.items():
        rows.append({"baseline": label, **score_predictions(features, col)})
    return pd.DataFrame(rows).set_index("baseline").sort_values("spearman_mean", ascending=False)
