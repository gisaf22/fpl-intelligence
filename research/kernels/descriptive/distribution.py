"""Univariate distribution primitive.

Two functions — one primitive, one composition of the primitive.
Single responsibility: summarise the shape of a numeric distribution.

Used by: research/foundation/target/, research/foundation/signals/,
         research/kernels/stability.py (via callers).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


def compute_distribution_stats(series: pd.Series) -> dict[str, float]:
    """Full distribution summary for a single numeric series.

    Returns NaN for every key when the series is empty after dropping nulls,
    so callers can safely concatenate results across positions without
    special-casing missing slices.
    """
    s = series.dropna()
    _nan_keys = [
        "count",
        "mean",
        "median",
        "std",
        "min",
        "max",
        "p25",
        "p75",
        "iqr",
        "p90",
        "p95",
        "p99",
        "skew",
        "kurtosis",
        "variance",
    ]
    if len(s) == 0:
        return {k: np.nan for k in _nan_keys}
    val = float(s.iloc[0])
    if s.std() == 0:
        return {
            "count": len(s),
            "mean": val,
            "median": val,
            "std": 0.0,
            "variance": 0.0,
            "min": val,
            "max": val,
            "p25": val,
            "p75": val,
            "p90": val,
            "p95": val,
            "p99": val,
            "iqr": 0.0,
            "skew": np.nan,
            "kurtosis": np.nan,
        }
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
        "p95": s.quantile(0.95),
        "p99": s.quantile(0.99),
        "iqr": s.quantile(0.75) - s.quantile(0.25),
        "skew": stats.skew(s),
        "kurtosis": stats.kurtosis(s),
    }


def compare_cohorts(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
) -> pd.DataFrame:
    """Distribution stats for each named cohort, returned as a cohort-indexed DataFrame.

    Callers own the split — build the cohorts dict from whatever grouping makes
    sense (position, GW block, season, etc.) then pass it in.
    """
    results: list[dict[str, Any]] = []
    for cohort_name, cohort_df in cohorts.items():
        stats_dict: dict[str, Any] = compute_distribution_stats(cohort_df[value_col])
        stats_dict["cohort"] = cohort_name
        results.append(stats_dict)
    return pd.DataFrame(results).set_index("cohort")
