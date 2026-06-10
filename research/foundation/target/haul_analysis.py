"""Haul / tail analysis — exceedance frequency by threshold and position.

Answers: how often do players exceed a score threshold (a "haul"), and does
that rate differ by position? Used in target EDA to characterise upper-tail
behaviour before deciding whether haul events need special treatment in
signal evaluation.
"""

from __future__ import annotations

import pandas as pd


def analyze_tail_frequency(
    df: pd.DataFrame,
    value_col: str = "total_points",
    thresholds: list[float] | None = None,
) -> pd.DataFrame:
    """Percentage of GWs where a player exceeded each score threshold, by position.

    Thresholds default to [8, 10, 12, 15, 20] points — the range that captures
    meaningful haul events across positions.
    """
    if thresholds is None:
        thresholds = [8, 10, 12, 15, 20]

    positions = sorted(df["position"].dropna().unique())
    results = {}
    for threshold in thresholds:
        row = {"threshold": threshold}
        for pos in positions:
            pos_data = df[df["position"] == pos][value_col]
            row[pos] = (pos_data > threshold).mean() * 100
        results[threshold] = row
    return pd.DataFrame(results).T


def compare_tail_frequency_across_cohorts(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
    threshold: float = 15.0,
) -> pd.DataFrame:
    """Haul-event rate at a single threshold across multiple cohorts, by position."""
    results = []
    for cohort_name, cohort_df in cohorts.items():
        positions = sorted(cohort_df["position"].dropna().unique())
        row = {"cohort": cohort_name}
        for pos in positions:
            pos_data = cohort_df[cohort_df["position"] == pos][value_col]
            row[pos] = (pos_data > threshold).mean() * 100
        results.append(row)
    return pd.DataFrame(results).set_index("cohort")
