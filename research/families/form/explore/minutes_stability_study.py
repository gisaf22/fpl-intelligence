"""Minutes stability × rolling xGI conditional robustness study — STUDY-MINSTAB-01.

Mode: predictive/conditioning · Stage: validate · Status: REJECTED — FRINGE > STABLE
Population: FWD only; GW 6-33; lag-1 respected
ADLC §4 audit row D (the 31-test template).

Research question: Does minutes stability condition the usefulness of rolling xGI
signals for forwards?

Hypothesis: Rolling xGI signals show materially stronger rank correlation with
next-GW total_points for minutes-stable forwards (minutes_roll5 >= 60) than for
rotation (30–59) or fringe (< 30) forwards.

Population: FWD only, GW 6–33 inclusive.
Signals evaluated: xgi_lag1, xgi_roll3, xgi_roll8.
Segmentation: three cohorts via minutes_roll5 (fixed thresholds, a priori).
Temporal integrity: all features produced by DAL state layer with lag-1 shift.

Design doc: docs/studies/minutes-stability-xgi-study.md
"""

from __future__ import annotations

import pandas as pd

from research.kernels.metrics import downside_rate, rank_correlation
from research.kernels.windows import assert_no_future_leakage, evaluation_gameweeks

_POSITION_FWD = "FWD"
_MIN_GW = 6
_MAX_GW = 33
_MIN_POPULATION = 5  # players per cohort per GW to compute metrics

# Stability cohort thresholds — fixed a priori, not optimized
_STABLE_THRESHOLD = 60.0    # minutes_roll5 >= 60 → STABLE
_ROTATION_THRESHOLD = 30.0  # minutes_roll5 >= 30 → ROTATION; < 30 → FRINGE

_COHORT_STABLE = "STABLE"
_COHORT_ROTATION = "ROTATION"
_COHORT_FRINGE = "FRINGE"
_COHORT_UNKNOWN = "UNKNOWN"

_SIGNALS: list[tuple[str, str]] = [
    ("xgi_lag1", "lag-1 raw xGI (baseline)"),
    ("xgi_roll3", "3-GW rolling mean xGI"),
    ("xgi_roll8", "8-GW rolling mean xGI"),
]

_DOWNSIDE_THRESHOLD = 4.0  # < 4 pts is a damaging captain outcome

# Pre-committed success thresholds — locked before execution
_THRESHOLDS = {
    "cohort_min_gws": 15,            # STABLE viable in >= 15 GWs
    "primary_differential": 0.04,    # delta_stable_fringe (roll3) > 0.04
    "horizon_interaction": 0.02,     # |delta_roll8 - delta_roll3| > 0.02
    "downside_improvement": 0.10,    # downside[STABLE, roll3] < full_fwd - 0.10
}


def _add_xgi_lag1(features: pd.DataFrame) -> pd.DataFrame:
    """Add xgi_lag1 column — shift-1 of raw xgi per player.

    At GW N: xgi_lag1 = xgi observed at GW N-1. This is the raw single-game
    baseline the rolling windows are compared against.
    """
    df = features.sort_values(["player_id", "gw"]).copy()
    if "xgi" in df.columns:
        df["xgi_lag1"] = df.groupby("player_id")["xgi"].shift(1)
    else:
        df["xgi_lag1"] = float("nan")
    return df


def _assign_stability_cohort(minutes_roll5: float | None) -> str:
    """Assign a stability cohort label based on minutes_roll5.

    Thresholds are fixed a priori — not optimized. NULL input → UNKNOWN.
    """
    if minutes_roll5 is None or (isinstance(minutes_roll5, float) and minutes_roll5 != minutes_roll5):
        return _COHORT_UNKNOWN
    if minutes_roll5 >= _STABLE_THRESHOLD:
        return _COHORT_STABLE
    if minutes_roll5 >= _ROTATION_THRESHOLD:
        return _COHORT_ROTATION
    return _COHORT_FRINGE


def _filter_fwd_gw(features: pd.DataFrame, gw: int) -> pd.DataFrame:
    """Return all FWD rows for a given GW with stability cohort already assigned."""
    gw_df = features[features["gw"] == gw].copy()
    return gw_df[gw_df["position_label"] == _POSITION_FWD]


def _evaluate_cohort_signals(
    pop: pd.DataFrame,
    actuals: pd.Series,
) -> dict:
    """Compute per-signal metrics for a single cohort in a single GW.

    Returns dict: n_players, and per signal: rho_{name}, top1_return_{name}.
    """
    row: dict = {"n_players": len(pop)}
    for signal_col, _ in _SIGNALS:
        rho_key = f"rho_{signal_col}"
        top1_key = f"top1_return_{signal_col}"

        if signal_col not in pop.columns:
            row[rho_key] = None
            row[top1_key] = None
            continue

        pred = pop.set_index("player_id")[signal_col].dropna()
        common = pred.index.intersection(actuals.index)
        if len(common) < 2:
            row[rho_key] = None
            row[top1_key] = None
            continue

        row[rho_key] = rank_correlation(pred.loc[common], actuals.loc[common])

        top1_id = int(pred.loc[common].idxmax())
        top1_pts = actuals.get(top1_id)
        row[top1_key] = float(top1_pts) if top1_pts is not None else None

    return row


def _aggregate_signal_results(gw_rows: list[dict]) -> dict:
    """Aggregate per-GW rows into cohort-level signal summaries."""
    if not gw_rows:
        return {}

    detail = pd.DataFrame(gw_rows)
    results: dict = {}

    for signal_col, label in _SIGNALS:
        rho_col = f"rho_{signal_col}"
        top1_col = f"top1_return_{signal_col}"

        rho_vals = detail[rho_col].dropna() if rho_col in detail.columns else pd.Series(dtype=float)
        top1_vals = detail[top1_col].dropna() if top1_col in detail.columns else pd.Series(dtype=float)

        results[signal_col] = {
            "label": label,
            "mean_rho": round(float(rho_vals.mean()), 4) if not rho_vals.empty else None,
            "std_rho": round(float(rho_vals.std()), 4) if len(rho_vals) >= 2 else None,
            "n_gws": int(rho_vals.notna().sum()),
            "mean_top1_return": round(float(top1_vals.mean()), 2) if not top1_vals.empty else None,
            "downside_rate": downside_rate(top1_vals, threshold=_DOWNSIDE_THRESHOLD),
        }

    return results


def evaluate_minutes_stability_conditioning(
    features: pd.DataFrame,
    min_gw: int = _MIN_GW,
    max_gw: int = _MAX_GW,
) -> dict:
    """Execute the minutes stability × rolling xGI conditional robustness study.

    Evaluates xgi_lag1, xgi_roll3, xgi_roll8 for forwards within three stability
    cohorts defined by minutes_roll5. Compares signal usefulness across cohorts
    and against the unfiltered FWD baseline.

    Parameters
    ----------
    features:
        DAL state output at (player_id, gw) grain. Must include xgi, xgi_roll3,
        xgi_roll8, minutes_roll5, minutes_roll3, points_roll3, total_points,
        position_label. All rolling columns must be lag-1 shifted (state layer).
    min_gw:
        First evaluation GW (inclusive). Default 6.
    max_gw:
        Last evaluation GW (inclusive). Default 33.

    Returns
    -------
    dict with keys:
    - eval_gws: list of GWs evaluated
    - gw_count: GWs with viable full-FWD population
    - cohort_gw_counts: {STABLE, ROTATION, FRINGE} → GWs with >= 5 players
    - cohorts: {STABLE, ROTATION, FRINGE} → signal results dict
    - full_fwd: signal results for the unfiltered FWD population
    - differential: cross-cohort rho delta per signal
    - threshold_assessment: pre-committed criteria evaluation
    - detail: per-GW population accounting DataFrame
    """
    features = _add_xgi_lag1(features)

    features = features.copy()
    features["stability_cohort"] = features["minutes_roll5"].apply(_assign_stability_cohort)

    eval_gws = evaluation_gameweeks(features, min_gw=min_gw, max_gw=max_gw)

    cohort_gw_rows: dict[str, list[dict]] = {
        _COHORT_STABLE: [],
        _COHORT_ROTATION: [],
        _COHORT_FRINGE: [],
    }
    full_fwd_gw_rows: list[dict] = []
    population_rows: list[dict] = []

    for gw in eval_gws:
        assert_no_future_leakage(features, gw)
        all_fwd = _filter_fwd_gw(features, gw)
        if all_fwd.empty:
            continue

        actuals = all_fwd.set_index("player_id")["total_points"].dropna()
        if actuals.empty:
            continue

        # Full FWD population — unfiltered baseline
        if len(all_fwd) >= _MIN_POPULATION:
            row = _evaluate_cohort_signals(all_fwd, actuals)
            row["gw"] = gw
            full_fwd_gw_rows.append(row)

        # Per-cohort evaluation
        pop_row: dict = {"gw": gw, "n_all_fwd": len(all_fwd)}
        for cohort in (_COHORT_STABLE, _COHORT_ROTATION, _COHORT_FRINGE, _COHORT_UNKNOWN):
            cohort_pop = all_fwd[all_fwd["stability_cohort"] == cohort]
            pop_row[f"n_{cohort.lower()}"] = len(cohort_pop)

            if cohort == _COHORT_UNKNOWN:
                continue
            if len(cohort_pop) < _MIN_POPULATION:
                continue

            row = _evaluate_cohort_signals(cohort_pop, actuals)
            row["gw"] = gw
            cohort_gw_rows[cohort].append(row)

        population_rows.append(pop_row)

    if not full_fwd_gw_rows:
        return {"eval_gws": eval_gws, "gw_count": 0}

    # Aggregate per cohort
    cohort_results: dict = {}
    cohort_gw_counts: dict[str, int] = {}
    for cohort in (_COHORT_STABLE, _COHORT_ROTATION, _COHORT_FRINGE):
        rows = cohort_gw_rows[cohort]
        cohort_gw_counts[cohort] = len(rows)
        cohort_results[cohort] = _aggregate_signal_results(rows) if rows else {}

    full_fwd_results = _aggregate_signal_results(full_fwd_gw_rows)

    # Cross-cohort differential: STABLE rho − FRINGE rho per signal
    differential: dict = {}
    for signal_col, _ in _SIGNALS:
        stable_rho = cohort_results.get(_COHORT_STABLE, {}).get(signal_col, {}).get("mean_rho")
        rotation_rho = cohort_results.get(_COHORT_ROTATION, {}).get(signal_col, {}).get("mean_rho")
        fringe_rho = cohort_results.get(_COHORT_FRINGE, {}).get(signal_col, {}).get("mean_rho")

        delta = None
        if stable_rho is not None and fringe_rho is not None:
            delta = round(stable_rho - fringe_rho, 4)

        differential[signal_col] = {
            "stable_rho": stable_rho,
            "rotation_rho": rotation_rho,
            "fringe_rho": fringe_rho,
            "delta_stable_fringe": delta,
        }

    # Pre-committed threshold assessment
    roll3_delta = differential.get("xgi_roll3", {}).get("delta_stable_fringe")
    roll8_delta = differential.get("xgi_roll8", {}).get("delta_stable_fringe")
    stable_gws = cohort_gw_counts.get(_COHORT_STABLE, 0)

    stable_downside = (
        cohort_results.get(_COHORT_STABLE, {}).get("xgi_roll3", {}).get("downside_rate")
    )
    full_downside = full_fwd_results.get("xgi_roll3", {}).get("downside_rate")

    horizon_interaction = None
    if roll3_delta is not None and roll8_delta is not None:
        horizon_interaction = round(abs(roll8_delta - roll3_delta), 4)

    downside_improvement = None
    if stable_downside is not None and full_downside is not None:
        downside_improvement = round(full_downside - stable_downside, 4)

    threshold_assessment = {
        "cohort_viability": {
            "criterion": f"STABLE cohort >= {_MIN_POPULATION} players in >= {_THRESHOLDS['cohort_min_gws']} GWs",
            "threshold": _THRESHOLDS["cohort_min_gws"],
            "value": stable_gws,
            "met": stable_gws >= _THRESHOLDS["cohort_min_gws"],
        },
        "primary_differential": {
            "criterion": "delta_stable_fringe (xgi_roll3) > 0.04",
            "threshold": _THRESHOLDS["primary_differential"],
            "value": roll3_delta,
            "met": roll3_delta is not None and roll3_delta > _THRESHOLDS["primary_differential"],
        },
        "horizon_stability_interaction": {
            "criterion": "|delta_roll8 - delta_roll3| > 0.02",
            "threshold": _THRESHOLDS["horizon_interaction"],
            "value": horizon_interaction,
            "met": (
                horizon_interaction is not None
                and horizon_interaction > _THRESHOLDS["horizon_interaction"]
            ),
        },
        "downside_improvement": {
            "criterion": "downside_rate[STABLE, roll3] < full_fwd_downside - 0.10",
            "threshold": _THRESHOLDS["downside_improvement"],
            "value": downside_improvement,
            "met": (
                downside_improvement is not None
                and downside_improvement > _THRESHOLDS["downside_improvement"]
            ),
        },
    }

    detail = pd.DataFrame(population_rows) if population_rows else pd.DataFrame()

    return {
        "eval_gws": eval_gws,
        "gw_count": len(full_fwd_gw_rows),
        "cohort_gw_counts": cohort_gw_counts,
        "cohorts": cohort_results,
        "full_fwd": full_fwd_results,
        "differential": differential,
        "threshold_assessment": threshold_assessment,
        "detail": detail,
    }


def interpret_results(results: dict) -> str:
    """Produce a canonical interpretation string from study results.

    Interpretation strings map to the guidance in the study design document
    (docs/studies/minutes-stability-xgi-study.md, Section 11).
    """
    if results.get("gw_count", 0) == 0:
        return "insufficient_data"

    ta = results.get("threshold_assessment", {})
    viable = ta.get("cohort_viability", {}).get("met", False)
    if not viable:
        return "cohort_size_failure"

    primary_met = ta.get("primary_differential", {}).get("met", False)
    interaction_met = ta.get("horizon_stability_interaction", {}).get("met", False)
    downside_met = ta.get("downside_improvement", {}).get("met", False)

    if not primary_met:
        return "stability_does_not_condition_signal"
    if primary_met and interaction_met and downside_met:
        return "stability_conditions_signal_strongly"
    if primary_met and downside_met:
        return "stability_conditions_downside_not_horizon"
    if primary_met and interaction_met:
        return "stability_conditions_horizon_not_downside"
    return "stability_conditions_rho_only"
