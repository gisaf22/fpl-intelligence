"""Unit tests for kernels/metrics.py and kernels/distribution.py.

metrics.py: evaluation metrics for operational usefulness (mean_return, top1_return,
hit_rate, regret, rank_correlation, return_variance, downside_rate).

distribution.py: two functions — compute_distribution_stats (primitive) and
compare_cohorts (composition). Domain-specific helpers (analyze_tail_frequency,
cohort splitting by column) live in research/foundation/target/haul_analysis.py.
"""

import numpy as np
import pandas as pd
import pytest

from tests.helpers.metrics import (
    downside_rate,
    hit_rate,
    mean_return,
    rank_correlation,
    regret,
    return_variance,
    top1_return,
)
from research.kernels.descriptive.distribution import (
    compute_distribution_stats,
    compare_cohorts,
)
from research.foundation.target.haul_analysis import analyze_tail_frequency


# ===========================================================================
# metrics.py
# ===========================================================================

class TestMeanReturn:

    def setup_method(self):
        self.outcomes = pd.DataFrame({
            "player_id": [1, 2, 3, 4],
            "total_points": [12.0, 6.0, 8.0, 4.0],
        })

    def test_basic_mean(self):
        result = mean_return([1, 2], self.outcomes)
        assert result == pytest.approx(9.0)

    def test_single_player(self):
        result = mean_return([3], self.outcomes)
        assert result == pytest.approx(8.0)

    def test_no_matching_players_returns_none(self):
        result = mean_return([99], self.outcomes)
        assert result is None

    def test_empty_player_ids_returns_none(self):
        result = mean_return([], self.outcomes)
        assert result is None

    def test_all_nan_returns_none(self):
        df = pd.DataFrame({"player_id": [1], "total_points": [float("nan")]})
        result = mean_return([1], df)
        assert result is None


class TestTop1Return:

    def setup_method(self):
        self.outcomes = pd.DataFrame({
            "player_id": [1, 2, 3],
            "total_points": [10.0, 7.0, float("nan")],
        })

    def test_returns_correct_points(self):
        assert top1_return(1, self.outcomes) == pytest.approx(10.0)
        assert top1_return(2, self.outcomes) == pytest.approx(7.0)

    def test_missing_player_returns_none(self):
        assert top1_return(99, self.outcomes) is None

    def test_nan_value_returns_none(self):
        assert top1_return(3, self.outcomes) is None


class TestHitRate:

    def test_hit_when_in_ranked_ids(self):
        assert hit_rate([1, 2, 3], 2) == 1

    def test_miss_when_not_in_ranked_ids(self):
        assert hit_rate([1, 2, 3], 4) == 0

    def test_single_id_hit(self):
        assert hit_rate([5], 5) == 1

    def test_empty_ranked_ids_is_miss(self):
        assert hit_rate([], 1) == 0


class TestRegret:

    def test_zero_regret_when_optimal(self):
        assert regret(12.0, 12.0) == pytest.approx(0.0)

    def test_positive_regret_when_suboptimal(self):
        assert regret(12.0, 6.0) == pytest.approx(6.0)

    def test_none_picked_returns_none(self):
        assert regret(12.0, None) is None

    def test_negative_regret_possible(self):
        # Should not happen in FPL but function allows it
        assert regret(6.0, 12.0) == pytest.approx(-6.0)


class TestRankCorrelation:

    def test_perfect_positive_correlation(self):
        predicted = pd.Series([1, 2, 3, 4, 5], index=[1, 2, 3, 4, 5])
        actual = pd.Series([10, 20, 30, 40, 50], index=[1, 2, 3, 4, 5])
        result = rank_correlation(predicted, actual)
        assert result == pytest.approx(1.0)

    def test_perfect_negative_correlation(self):
        predicted = pd.Series([5, 4, 3, 2, 1], index=[1, 2, 3, 4, 5])
        actual = pd.Series([10, 20, 30, 40, 50], index=[1, 2, 3, 4, 5])
        result = rank_correlation(predicted, actual)
        assert result == pytest.approx(-1.0)

    def test_no_overlap_returns_none(self):
        predicted = pd.Series([1, 2], index=[1, 2])
        actual = pd.Series([3, 4], index=[3, 4])
        result = rank_correlation(predicted, actual)
        assert result is None

    def test_single_overlap_returns_none(self):
        predicted = pd.Series([1, 2], index=[1, 2])
        actual = pd.Series([10, 20], index=[1, 99])
        result = rank_correlation(predicted, actual)
        assert result is None

    def test_constant_predicted_returns_a_value(self):
        # Constant predicted series produces tied ranks. The Spearman formula is
        # defined even with ties (returns a value, not None). The result is not
        # meaningful but the function does not special-case this.
        predicted = pd.Series([5, 5, 5], index=[1, 2, 3])
        actual = pd.Series([10, 20, 30], index=[1, 2, 3])
        result = rank_correlation(predicted, actual)
        assert result is not None
        assert isinstance(result, float)

    def test_partial_overlap_uses_common_index(self):
        predicted = pd.Series([1, 2, 3], index=[1, 2, 3])
        actual = pd.Series([10, 20], index=[1, 2])
        result = rank_correlation(predicted, actual)
        assert result is not None
        assert result == pytest.approx(1.0)


class TestReturnVariance:

    def test_zero_variance_constant_series(self):
        s = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = return_variance(s)
        assert result == pytest.approx(0.0)

    def test_known_std(self):
        s = pd.Series([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        result = return_variance(s)
        assert result is not None
        assert result > 0.0

    def test_single_element_returns_none(self):
        assert return_variance(pd.Series([5.0])) is None

    def test_all_nan_returns_none(self):
        s = pd.Series([float("nan"), float("nan")])
        assert return_variance(s) is None

    def test_drops_nan_before_computing(self):
        s = pd.Series([1.0, 2.0, float("nan"), 3.0])
        result = return_variance(s)
        assert result is not None


class TestDownsideRate:

    def test_all_above_threshold(self):
        s = pd.Series([8.0, 10.0, 12.0])
        assert downside_rate(s, threshold=4.0) == pytest.approx(0.0)

    def test_all_below_threshold(self):
        s = pd.Series([1.0, 2.0, 3.0])
        assert downside_rate(s, threshold=4.0) == pytest.approx(1.0)

    def test_half_below(self):
        s = pd.Series([1.0, 3.0, 5.0, 7.0])
        assert downside_rate(s, threshold=4.0) == pytest.approx(0.5)

    def test_empty_returns_none(self):
        assert downside_rate(pd.Series([], dtype=float)) is None

    def test_drops_nan(self):
        s = pd.Series([1.0, float("nan"), 10.0])
        result = downside_rate(s, threshold=4.0)
        assert result == pytest.approx(0.5)

    def test_custom_threshold(self):
        s = pd.Series([5.0, 10.0, 15.0])
        assert downside_rate(s, threshold=8.0) == pytest.approx(1.0 / 3.0)


# ===========================================================================
# distribution.py
# ===========================================================================

class TestComputeDistributionStats:

    def test_returns_all_expected_keys(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = compute_distribution_stats(s)
        expected_keys = {"count", "mean", "median", "std", "min", "max",
                         "p25", "p75", "p90", "p99", "skew", "kurtosis", "variance"}
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
        df = pd.DataFrame({
            "position": ["GK", "GK", "DEF", "DEF"],
            "total_points": [5.0, 7.0, 3.0, 4.0],
        })
        cohorts = {pos: grp for pos, grp in df.groupby("position")}
        result = compare_cohorts(cohorts, value_col="total_points")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    def test_mean_correct_per_group(self):
        df = pd.DataFrame({
            "pos": ["A", "A", "B", "B"],
            "pts": [10.0, 20.0, 5.0, 15.0],
        })
        cohorts = {pos: grp for pos, grp in df.groupby("pos")}
        result = compare_cohorts(cohorts, value_col="pts")
        assert result.loc["A", "mean"] == pytest.approx(15.0)


class TestAnalyzeTailFrequency:

    def test_returns_dataframe(self):
        df = pd.DataFrame({
            "position_code": ["DEF", "DEF", "MID", "MID", "FWD"],
            "total_points": [5.0, 15.0, 3.0, 13.0, 20.0],
        })
        result = analyze_tail_frequency(df, thresholds=[10, 12])
        assert isinstance(result, pd.DataFrame)

    def test_threshold_zero_means_all_qualify(self):
        df = pd.DataFrame({
            "position_code": ["DEF"] * 4,
            "total_points": [1.0, 2.0, 3.0, 4.0],
        })
        result = analyze_tail_frequency(df, thresholds=[0])
        assert result.loc[0, "DEF"] == pytest.approx(100.0)

    def test_threshold_above_max_means_none_qualify(self):
        df = pd.DataFrame({
            "position_code": ["DEF"] * 3,
            "total_points": [1.0, 2.0, 3.0],
        })
        result = analyze_tail_frequency(df, thresholds=[100])
        assert result.loc[100, "DEF"] == pytest.approx(0.0)
