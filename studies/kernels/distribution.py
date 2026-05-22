"""Y distribution stats — completeness, atomic statistics, cohort aggregation, tail analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def analyze_data_completeness(
    df: pd.DataFrame,
    player_id_col: str = "player_id",
    gw_col: str = "gw",
    started_col: str = "starts",
    study_gw_min: int = 6,
) -> dict:
    total = len(df)
    null_count = df[started_col].isna().sum()
    first_gw = df[df[started_col].notna()].groupby(player_id_col)[gw_col].min()
    late_joiners = (first_gw > study_gw_min).sum()
    return {
        "total_rows": total,
        "null_rows": null_count,
        "null_pct": (null_count / total * 100),
        "late_joiners": late_joiners,
        "first_appearances": first_gw,
    }


def compute_distribution_stats(series: pd.Series) -> dict[str, float]:
    s = series.dropna()
    if len(s) == 0:
        return {k: np.nan for k in [
            "count", "mean", "median", "std", "min", "max",
            "p25", "p75", "p90", "p99", "skew", "kurtosis", "variance",
        ]}
    return {
        "count": len(s),
        "mean": s.mean(),
        "median": s.median(),
        "std": s.std(),
        "variance": s.var(),
        "min": s.min(),
        "max": s.max(),
        "p25": s.quantile(0.25),
        "p75": s.quantile(0.75),
        "p90": s.quantile(0.90),
        "p99": s.quantile(0.99),
        "skew": stats.skew(s),
        "kurtosis": stats.kurtosis(s),
    }


def compare_cohorts(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
) -> pd.DataFrame:
    results = []
    for cohort_name, cohort_df in cohorts.items():
        stats_dict = compute_distribution_stats(cohort_df[value_col])
        stats_dict["cohort"] = cohort_name
        results.append(stats_dict)
    return pd.DataFrame(results).set_index("cohort")


def analyze_by_group(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
) -> pd.DataFrame:
    results = []
    for group_val, group_df in df.groupby(group_col, observed=True):
        stats_dict = compute_distribution_stats(group_df[value_col])
        stats_dict[group_col] = group_val
        results.append(stats_dict)
    return pd.DataFrame(results)


def analyze_dgw_vs_sgw(
    df: pd.DataFrame,
    value_col: str = "total_points",
) -> dict:
    return {
        "dgw": compute_distribution_stats(df[df["is_dgw"]][value_col]),
        "sgw": compute_distribution_stats(df[~df["is_dgw"]][value_col]),
    }


def compare_dgw_vs_sgw_across_cohorts(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
) -> pd.DataFrame:
    flat_results = []
    for cohort_name, cohort_df in cohorts.items():
        dgw_sgw = analyze_dgw_vs_sgw(cohort_df, value_col)
        for fixture_type, stats_dict in dgw_sgw.items():
            row = {"cohort": cohort_name, "fixture_type": fixture_type}
            row.update(stats_dict)
            flat_results.append(row)
    df = pd.DataFrame(flat_results)
    return df.set_index(["cohort", "fixture_type"])


def analyze_tail_frequency(
    df: pd.DataFrame,
    value_col: str = "total_points",
    thresholds: list[float] | None = None,
    position_map: dict | None = None,
) -> pd.DataFrame:
    if thresholds is None:
        thresholds = [8, 10, 12, 15, 20]

    df_for_analysis = df.copy()
    if position_map:
        df_for_analysis["position_code"] = df_for_analysis["position_code"].map(position_map)

    positions = sorted(df_for_analysis["position_code"].dropna().unique())
    results = {}
    for threshold in thresholds:
        row = {"threshold": threshold}
        for pos in positions:
            pos_data = df_for_analysis[df_for_analysis["position_code"] == pos][value_col]
            row[pos] = (pos_data > threshold).mean() * 100
        results[threshold] = row
    return pd.DataFrame(results).T


def compare_tail_frequency_across_cohorts(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
    threshold: float = 15.0,
    position_map: dict | None = None,
) -> pd.DataFrame:
    results = []
    for cohort_name, cohort_df in cohorts.items():
        cohort_for_analysis = cohort_df.copy()
        if position_map:
            cohort_for_analysis["position_code"] = cohort_for_analysis["position_code"].map(position_map)

        positions = sorted(cohort_for_analysis["position_code"].dropna().unique())
        row = {"cohort": cohort_name}
        for pos in positions:
            pos_data = cohort_for_analysis[cohort_for_analysis["position_code"] == pos][value_col]
            row[pos] = (pos_data > threshold).mean() * 100
        results.append(row)
    return pd.DataFrame(results).set_index("cohort")
