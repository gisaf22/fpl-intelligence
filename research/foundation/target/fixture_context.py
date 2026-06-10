"""Fixture context analysis — DGW vs SGW distribution splits.

Answers: does the target variable (total_points) behave differently in
double gameweeks vs single gameweeks, and is that difference consistent
across cohorts?
"""

from __future__ import annotations

import pandas as pd

from research.kernels.descriptive.distribution import compute_distribution_stats


def analyze_dgw_vs_sgw(
    df: pd.DataFrame,
    value_col: str = "total_points",
) -> dict:
    """Distribution stats split between double and single gameweeks."""
    return {
        "dgw": compute_distribution_stats(df[df["is_dgw"]][value_col]),
        "sgw": compute_distribution_stats(df[~df["is_dgw"]][value_col]),
    }


def compare_dgw_vs_sgw_across_cohorts(
    cohorts: dict[str, pd.DataFrame],
    value_col: str = "total_points",
) -> pd.DataFrame:
    """DGW vs SGW distribution comparison across multiple cohorts.

    Returns a (cohort, fixture_type)-indexed DataFrame.
    """
    flat_results = []
    for cohort_name, cohort_df in cohorts.items():
        dgw_sgw = analyze_dgw_vs_sgw(cohort_df, value_col)
        for fixture_type, stats_dict in dgw_sgw.items():
            row = {"cohort": cohort_name, "fixture_type": fixture_type}
            row.update(stats_dict)
            flat_results.append(row)
    df = pd.DataFrame(flat_results)
    return df.set_index(["cohort", "fixture_type"])
