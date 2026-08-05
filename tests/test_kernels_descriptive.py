"""Unit tests for research/kernels/descriptive/distribution.py.

Two functions: compute_distribution_stats (primitive) and compare_cohorts (composition).
"""

import numpy as np
import pandas as pd
import pytest

from research.kernels.descriptive.distribution import (
    compare_cohorts,
    compute_distribution_stats,
)


class TestComputeDistributionStats:
    def test_returns_all_expected_keys(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_distribution_stats(s)
        expected_keys = {
            "count",
            "mean",
            "median",
            "std",
            "min",
            "max",
            "p25",
            "p75",
            "p90",
            "p99",
            "skew",
            "kurtosis",
            "variance",
        }
        assert expected_keys <= set(result.keys())

    def test_known_values(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_distribution_stats(s)
        assert result["count"] == 5
        assert result["mean"] == pytest.approx(3.0)
        assert result["min"] == pytest.approx(1.0)
        assert result["max"] == pytest.approx(5.0)

    def test_empty_series_returns_nan_dict(self):
        result = compute_distribution_stats(pd.Series([], dtype=float))
        assert all(np.isnan(v) for v in result.values())

    def test_drops_nan_before_stats(self):
        s = pd.Series([1.0, 2.0, float("nan"), 4.0, 5.0])
        result = compute_distribution_stats(s)
        assert result["count"] == 4

    def test_single_value(self):
        result = compute_distribution_stats(pd.Series([42.0]))
        assert result["mean"] == pytest.approx(42.0)
        assert result["min"] == pytest.approx(42.0)


class TestCompareCohorts:
    def test_returns_dataframe_indexed_by_cohort(self):
        cohorts = {
            "gkp": pd.DataFrame({"total_points": [5.0, 6.0, 7.0]}),
            "def": pd.DataFrame({"total_points": [3.0, 4.0, 5.0]}),
        }
        result = compare_cohorts(cohorts)
        assert isinstance(result, pd.DataFrame)
        assert set(result.index) == {"gkp", "def"}

    def test_custom_value_col(self):
        cohorts = {"a": pd.DataFrame({"score": [1.0, 2.0, 3.0]})}
        result = compare_cohorts(cohorts, value_col="score")
        assert "mean" in result.columns
        assert result.loc["a", "mean"] == pytest.approx(2.0)


class TestCompareCohortsByColumn:
    """compare_cohorts with a caller-owned groupby split — replaces the deleted analyze_by_group."""

    def test_groups_correctly(self):
        df = pd.DataFrame(
            {
                "position": ["GK", "GK", "DEF", "DEF"],
                "total_points": [5.0, 7.0, 3.0, 4.0],
            }
        )
        cohorts = {pos: grp for pos, grp in df.groupby("position")}
        result = compare_cohorts(cohorts, value_col="total_points")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_mean_correct_per_group(self):
        df = pd.DataFrame(
            {
                "pos": ["A", "A", "B", "B"],
                "pts": [10.0, 20.0, 5.0, 15.0],
            }
        )
        cohorts = {pos: grp for pos, grp in df.groupby("pos")}
        result = compare_cohorts(cohorts, value_col="pts")
        assert result.loc["A", "mean"] == pytest.approx(15.0)
