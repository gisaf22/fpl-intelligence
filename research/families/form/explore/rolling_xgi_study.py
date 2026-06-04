"""Rolling xGI horizon study — study-specific evaluation module.

Mode: predictive · Stage: validate · Status: window selection (xGI horizon choice)
Population: FWD only; GW 6-33; minutes_roll3>=60; lag-1 respected
ADLC §4 audit (unlettered rolling-xGI window-choice row).

Executes the evaluation defined in docs/studies/rolling-xgi-horizon-study.md.

Research question: Does rolling xGI outperform raw (lag-1) xGI for forwards
across 3-, 5-, and 8-game horizons when predicting the following GW's total points?

Population: FWD only, GW 6–33 inclusive, minutes_roll3 >= 60.
Signals evaluated: xgi_lag1, xgi_roll3, xgi_roll5, xgi_roll8.
Evaluation target: total_points at GW N.
Temporal integrity: all rolling features produced by state layer with lag-1 shift.
"""

from __future__ import annotations

import pandas as pd

from research.kernels.metrics import downside_rate, rank_correlation
from research.kernels.windows import assert_no_future_leakage, evaluation_gameweeks

_POSITION_FWD = "FWD"
_MIN_GW = 6
_MAX_GW = 33
_MIN_MINUTES = 60.0
_DOWNSIDE_THRESHOLD = 4.0

_SIGNALS: list[tuple[str, str]] = [
    ("xgi_lag1", "lag-1 raw xGI (baseline)"),
    ("xgi_roll3", "3-GW rolling mean xGI"),
    ("xgi_roll5", "5-GW rolling mean xGI"),
    ("xgi_roll8", "8-GW rolling mean xGI"),
]

_SUCCESS_THRESHOLDS = {
    "min_lift": 0.02,
    "min_mean_rho": 0.25,
    "max_rho_std": 0.15,
}


def _add_xgi_lag1(features: pd.DataFrame) -> pd.DataFrame:
    """Add xgi_lag1 column (shift-1 of raw xgi per player).

    At GW N: xgi_lag1 = xgi observed at GW N-1.
    This is the raw single-game baseline the rolling windows are compared against.
    """
    df = features.sort_values(["player_id", "gw"]).copy()
    if "xgi" in df.columns:
        df["xgi_lag1"] = df.groupby("player_id")["xgi"].shift(1)
    else:
        df["xgi_lag1"] = float("nan")
    return df


def _filter_fwd_population(
    features: pd.DataFrame,
    gw: int,
    min_minutes: float,
) -> pd.DataFrame:
    """Filter to FWD-only rows for a given GW with sufficient minutes.

    Applies the study's population constraint: position_label == FWD
    and minutes_roll3 >= min_minutes.
    """
    gw_df = features[features["gw"] == gw].copy()
    fwd_df = gw_df[gw_df["position_label"] == _POSITION_FWD]
    return fwd_df[fwd_df["minutes_roll3"].fillna(0) >= min_minutes]


def evaluate_rolling_xgi_horizons(
    features: pd.DataFrame,
    min_gw: int = _MIN_GW,
    max_gw: int = _MAX_GW,
    min_minutes: float = _MIN_MINUTES,
) -> dict:
    """Execute the rolling xGI horizon study evaluation.

    Compares xgi_lag1, xgi_roll3, xgi_roll5, xgi_roll8 as predictors of
    next-GW total_points for forwards.

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain. Must include
        xgi, xgi_roll3, xgi_roll5, xgi_roll8, minutes_roll3, total_points,
        and position_label columns.
    min_gw:
        First evaluation GW (inclusive). Early-season GWs excluded by default.
    max_gw:
        Last evaluation GW (inclusive).
    min_minutes:
        Minimum minutes_roll3 threshold for eligibility.

    Returns
    -------
    Dict containing:
    - eval_gws: list of GWs evaluated
    - gw_count: number of GWs with sufficient FWD population
    - signals: dict mapping signal_name -> {label, mean_rho, std_rho, n_gws}
    - lift_over_lag1: dict mapping signal_name -> rolling_rho - lag1_rho
    - top1_metrics: dict mapping signal_name -> {mean_top1_return, downside_rate}
    - threshold_assessment: dict mapping criterion -> {threshold, value, met}
    - detail: per-GW DataFrame with per-signal rho values
    """
    features = _add_xgi_lag1(features)

    eval_gws = evaluation_gameweeks(features, min_gw=min_gw, max_gw=max_gw)

    gw_rows: list[dict] = []
    for gw in eval_gws:
        assert_no_future_leakage(features, gw)
        pop = _filter_fwd_population(features, gw, min_minutes)
        if len(pop) < 5:
            continue

        actuals = pop.set_index("player_id")["total_points"].dropna()
        if actuals.empty:
            continue

        row: dict = {"gw": gw, "n_fwd": len(pop)}
        for signal_col, _ in _SIGNALS:
            if signal_col not in pop.columns:
                row[f"rho_{signal_col}"] = None
                row[f"top1_return_{signal_col}"] = None
                continue
            pred = pop.set_index("player_id")[signal_col].dropna()
            common = pred.index.intersection(actuals.index)
            if len(common) < 2:
                row[f"rho_{signal_col}"] = None
                row[f"top1_return_{signal_col}"] = None
                continue

            rho = rank_correlation(pred.loc[common], actuals.loc[common])
            row[f"rho_{signal_col}"] = rho

            top1_id = int(pred.loc[common].idxmax())
            top1_pts = actuals.get(top1_id)
            row[f"top1_return_{signal_col}"] = float(top1_pts) if top1_pts is not None else None

        gw_rows.append(row)

    if not gw_rows:
        return {"eval_gws": eval_gws, "gw_count": 0}

    detail = pd.DataFrame(gw_rows)

    signals: dict = {}
    for signal_col, label in _SIGNALS:
        rho_col = f"rho_{signal_col}"
        if rho_col not in detail.columns:
            signals[signal_col] = {"label": label, "mean_rho": None, "std_rho": None, "n_gws": 0}
            continue
        rho_vals = detail[rho_col].dropna()
        signals[signal_col] = {
            "label": label,
            "mean_rho": round(float(rho_vals.mean()), 4) if not rho_vals.empty else None,
            "std_rho": round(float(rho_vals.std()), 4) if len(rho_vals) >= 2 else None,
            "n_gws": int(rho_vals.notna().sum()),
        }

    lag1_rho = signals.get("xgi_lag1", {}).get("mean_rho")
    lift_over_lag1: dict = {}
    for signal_col, _ in _SIGNALS:
        if signal_col == "xgi_lag1":
            lift_over_lag1[signal_col] = 0.0
            continue
        sig_rho = signals.get(signal_col, {}).get("mean_rho")
        if sig_rho is not None and lag1_rho is not None:
            lift_over_lag1[signal_col] = round(sig_rho - lag1_rho, 4)
        else:
            lift_over_lag1[signal_col] = None

    top1_metrics: dict = {}
    for signal_col, _ in _SIGNALS:
        col = f"top1_return_{signal_col}"
        if col not in detail.columns:
            top1_metrics[signal_col] = {"mean_top1_return": None, "downside_rate": None}
            continue
        returns = detail[col].dropna()
        top1_metrics[signal_col] = {
            "mean_top1_return": round(float(returns.mean()), 2) if not returns.empty else None,
            "downside_rate": downside_rate(returns, threshold=_DOWNSIDE_THRESHOLD),
        }

    best_signal = max(
        (s for s in _SIGNALS if s[0] != "xgi_lag1"),
        key=lambda s: signals.get(s[0], {}).get("mean_rho") or -999,
    )[0]
    best_rho = signals.get(best_signal, {}).get("mean_rho")
    best_std = signals.get(best_signal, {}).get("std_rho")
    best_lift = lift_over_lag1.get(best_signal)

    threshold_assessment = {
        "positive_lift": {
            "criterion": "lift > 0.02 for at least one rolling window",
            "threshold": _SUCCESS_THRESHOLDS["min_lift"],
            "value": best_lift,
            "met": best_lift is not None and best_lift > _SUCCESS_THRESHOLDS["min_lift"],
        },
        "operational_usefulness": {
            "criterion": f"mean rho > 0.25 for best window ({best_signal})",
            "threshold": _SUCCESS_THRESHOLDS["min_mean_rho"],
            "value": best_rho,
            "met": best_rho is not None and best_rho > _SUCCESS_THRESHOLDS["min_mean_rho"],
        },
        "stability": {
            "criterion": f"std(rho) < 0.15 for best window ({best_signal})",
            "threshold": _SUCCESS_THRESHOLDS["max_rho_std"],
            "value": best_std,
            "met": best_std is not None and best_std < _SUCCESS_THRESHOLDS["max_rho_std"],
        },
    }

    return {
        "eval_gws": eval_gws,
        "gw_count": len(gw_rows),
        "signals": signals,
        "lift_over_lag1": lift_over_lag1,
        "top1_metrics": top1_metrics,
        "threshold_assessment": threshold_assessment,
        "best_signal": best_signal,
        "detail": detail,
    }


def interpret_results(results: dict) -> str:
    """Produce a plain-language interpretation of study results.

    Returns one of the canonical interpretation strings from the study design.
    """
    if results.get("gw_count", 0) == 0:
        return "insufficient_data"

    ta = results.get("threshold_assessment", {})
    lift_met = ta.get("positive_lift", {}).get("met", False)
    usefulness_met = ta.get("operational_usefulness", {}).get("met", False)
    stability_met = ta.get("stability", {}).get("met", False)

    sigs = results.get("signals", {})
    roll5_rho = sigs.get("xgi_roll5", {}).get("mean_rho") or 0.0
    roll3_rho = sigs.get("xgi_roll3", {}).get("mean_rho") or 0.0
    lag1_rho = sigs.get("xgi_lag1", {}).get("mean_rho") or 0.0
    lift_roll5_over_roll3 = roll5_rho - roll3_rho

    if not lift_met:
        return "no_rolling_horizon_beats_lag1"
    if not stability_met:
        return "signal_remains_investigational_unstable"
    if not usefulness_met:
        return "signal_remains_investigational_below_threshold"
    if lift_roll5_over_roll3 > 0.05:
        return "roll5_materially_improves_over_roll3"
    if roll3_rho > lag1_rho + 0.02:
        return "roll3_supported_no_change_warranted"
    return "signal_remains_investigational"
