"""Stateful feature-lift study (form family).

Tests the core claim of the state layer: that rolling-window aggregations (xgi_roll3, points_roll3,
minutes_roll5) predict future performance better than raw single-game observations.

The state layer constructs features on the hypothesis that:
- Smoothed signals filter out single-game noise
- Multi-GW windows capture form trajectories, not one-off events
- Rolling aggregation provides more stable decision inputs

This module evaluates that hypothesis empirically by comparing Spearman rank correlations: does ranking
players by xgi_roll3 predict future total_points better than ranking by last single-game xGI?

Important distinction
---------------------
A validated spine observation (e.g. xgi = 0.72 in GW 14) means the raw measurement is trustworthy. It
does NOT mean that xgi_roll3 (a derived state construct) is a useful predictor of GW 15 performance.
This module tests the second claim, which the spine validation does not address.
"""

from __future__ import annotations

import pandas as pd

from research.kernels.evaluation import assert_no_future_leakage, rank_correlation

_COMPARISONS: dict[str, tuple[str, str]] = {
    "points": ("points_roll3", "points_lag1"),
    "xgi": ("xgi_roll3", "xgi_lag1"),
    "minutes": ("minutes_roll5", "minutes_lag1"),
}


def _compute_lag1_columns(features: pd.DataFrame) -> pd.DataFrame:
    """Add lag-1 single-game columns for raw signal comparison.

    At GW N: lag1 = value at GW N-1 (last observed game). This is the raw alternative to the rolling
    average for that same window. Returns a copy with points_lag1, xgi_lag1, minutes_lag1.
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


def evaluate_feature_lift(features: pd.DataFrame, gameweeks: list[int]) -> dict:
    """Compare rolling window features vs single-game observations as predictors.

    For each eval GW, computes Spearman rank correlation between each candidate predictor column and the
    actual total_points at that GW. Higher correlation means the predictor better identifies players who
    will score more.

    Returns a dict with: gw_count, predictors (name -> {label, mean_rho, n_gws}), lift (comparison ->
    rolling_rho - lag1_rho), detail (per-GW DataFrame).
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
