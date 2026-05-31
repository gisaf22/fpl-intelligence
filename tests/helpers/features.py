"""Stateful feature lift evaluation.

Tests the core claim of the state layer: that rolling-window aggregations
(xgi_roll3, points_roll3, minutes_roll5) produce more useful predictors of
future performance than raw single-game observations.

The state layer constructs features on the hypothesis that:
- Smoothed signals filter out single-game noise
- Multi-GW windows capture form trajectories, not one-off events
- Rolling aggregation provides more stable decision inputs

This module evaluates that hypothesis empirically by comparing Spearman rank
correlations: does ranking players by xgi_roll3 predict future total_points
better than ranking by last single-game xGI?

Important distinction
---------------------
A validated spine observation (e.g. xgi = 0.72 in GW 14) means the raw
measurement is trustworthy. It does NOT mean that xgi_roll3 (a derived state
construct) is a useful predictor of GW 15 performance. This module tests the
second claim, which the spine validation does not address.

Interpretation guide
--------------------
- rho > 0.3: meaningfully useful predictor for operational decisions
- rho 0.1-0.3: weak signal, use cautiously
- rho < 0.1: not reliably useful — raw single-game may be equally noisy
- rolling rho > lag1 rho: state construction adds lift over raw single-game
- rolling rho < lag1 rho: state construction may be smoothing signal away
"""

from __future__ import annotations

import pandas as pd

from tests.helpers.metrics import rank_correlation
from tests.helpers.windows import assert_no_future_leakage

_COMPARISONS: dict[str, tuple[str, str]] = {
    "points": ("points_roll3", "points_lag1"),
    "xgi": ("xgi_roll3", "xgi_lag1"),
    "minutes": ("minutes_roll5", "minutes_lag1"),
}


def _compute_lag1_columns(features: pd.DataFrame) -> pd.DataFrame:
    """Add lag-1 single-game columns for raw signal comparison.

    At GW N: lag1 = value at GW N-1 (last observed game).
    This is the raw alternative to the rolling average for that same window.

    Returns a copy of features with three additional columns:
    points_lag1, xgi_lag1, minutes_lag1.
    """
    df = features.sort_values(["player_id", "gw"]).copy()
    for raw_col, lag_col in [
        ("total_points", "points_lag1"),
        ("xgi", "xgi_lag1"),
        ("minutes", "minutes_lag1"),
    ]:
        if raw_col in df.columns:
            df[lag_col] = df.groupby("player_id")[raw_col].shift(1)
        else:
            df[lag_col] = float("nan")
    return df


def evaluate_feature_lift(
    features: pd.DataFrame,
    gameweeks: list[int],
) -> dict:
    """Compare rolling window features vs single-game observations as predictors.

    For each eval GW, computes Spearman rank correlation between each candidate
    predictor column and the actual total_points at that GW. Higher correlation
    means the predictor better identifies players who will score more.

    Three paired comparisons:
    - points_roll3 vs points_lag1  → does 3-GW form beat last-game points?
    - xgi_roll3    vs xgi_lag1     → does 3-GW xGI beat last-game xGI?
    - minutes_roll5 vs minutes_lag1 → does 5-GW minutes beat last-game minutes?

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain. Must include total_points,
        xgi, minutes (spine columns) and rolling state columns.
    gameweeks:
        Historical gameweeks to evaluate over.

    Returns
    -------
    Dict containing:
    - gw_count: number of evaluated gameweeks
    - predictors: dict mapping predictor_name -> {label, mean_rho, n_gws}
    - lift: dict mapping comparison_name -> rolling_rho - lag1_rho (positive = lift)
    - detail: per-GW DataFrame with per-predictor rho values
    """
    features = _compute_lag1_columns(features)

    predictor_labels = {
        "points_roll3": "3-GW rolling form",
        "points_lag1": "last single-game points",
        "xgi_roll3": "3-GW rolling xGI",
        "xgi_lag1": "last single-game xGI",
        "minutes_roll5": "5-GW rolling minutes",
        "minutes_lag1": "last single-game minutes",
    }

    gw_rows: list[dict] = []
    for gw in gameweeks:
        if features[features["gw"] == gw].empty:
            continue
        assert_no_future_leakage(features, gw)

        gw_df = features[features["gw"] == gw].copy()
        if gw_df.empty:
            continue
        actuals = gw_df.set_index("player_id")["total_points"].dropna()
        if actuals.empty:
            continue

        row: dict = {"gw": gw}
        for pred_col in predictor_labels:
            if pred_col not in gw_df.columns:
                row[f"rho_{pred_col}"] = None
                continue
            pred = gw_df.set_index("player_id")[pred_col]
            row[f"rho_{pred_col}"] = rank_correlation(pred, actuals)
        gw_rows.append(row)

    if not gw_rows:
        return {"gw_count": 0}

    df = pd.DataFrame(gw_rows)

    predictor_summary: dict = {}
    for pred_col, label in predictor_labels.items():
        col = f"rho_{pred_col}"
        vals = df[col].dropna() if col in df.columns else pd.Series(dtype=float)
        predictor_summary[pred_col] = {
            "label": label,
            "mean_rho": float(vals.mean()) if not vals.empty else None,
            "n_gws": int(vals.notna().sum()),
        }

    lift: dict = {}
    for name, (rolling_col, lag1_col) in _COMPARISONS.items():
        r_rho = predictor_summary.get(rolling_col, {}).get("mean_rho")
        l_rho = predictor_summary.get(lag1_col, {}).get("mean_rho")
        if r_rho is not None and l_rho is not None:
            lift[name] = round(r_rho - l_rho, 4)
        else:
            lift[name] = None

    return {
        "gw_count": len(df),
        "predictors": predictor_summary,
        "lift": lift,
        "detail": df,
    }
