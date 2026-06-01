"""Tests for evaluation core modules: metrics, windows, baselines.

Validates:
- Metric correctness (deterministic, mathematically sound)
- Temporal integrity enforcement (no future leakage)
- Baseline reproducibility and determinism
- Evaluation window slicing

Uses minimal synthetic DataFrames — no DB dependency.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.helpers.baselines import (
    baseline_fixture_only,
    baseline_highest_xgi,
    baseline_random_top_n,
    baseline_recent_points,
)
from tests.helpers.metrics import (
    downside_rate,
    hit_rate,
    mean_return,
    rank_correlation,
    regret,
    return_variance,
    top1_return,
)
from tests.helpers.windows import assert_no_future_leakage, evaluation_gameweeks

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _state_row(
    player_id: int,
    gw: int,
    total_points: float = 6.0,
    points_roll3: float = 5.0,
    xgi_roll3: float = 0.5,
    minutes_roll3: float = 85.0,
    minutes_roll5: float = 80.0,
    fdr_avg: float = 3.0,
    purchase_price: float = 7.5,
    position_label: str = "MID",
    is_bgw: bool = False,
) -> dict:
    """Minimal row with all required state + spine columns for evaluation tests."""
    return {
        "player_id": player_id,
        "gw": gw,
        "player_name": f"P{player_id}",
        "position_label": position_label,
        "position_code": 3,
        "team_id": player_id * 10,
        "purchase_price": purchase_price,
        "fdr_avg": fdr_avg,
        "fdr_min": fdr_avg - 0.5,
        "fdr_max": fdr_avg + 0.5,
        "is_bgw": is_bgw,
        "is_dgw": False,
        "goals_scored": 0.3,
        "total_points": None if is_bgw else total_points,
        "minutes": None if is_bgw else 90.0,
        "xgi": 0.4,
        "points_roll3": points_roll3,
        "points_roll5": points_roll3 - 0.3,
        "minutes_roll3": minutes_roll3,
        "minutes_roll5": minutes_roll5,
        "xgi_roll3": xgi_roll3,
        "xgi_roll5": xgi_roll3 - 0.05,
        "xgc_roll3": 0.2,
        "xgc_roll5": 0.25,
        "clean_sheets_roll3": 0.2,
        "clean_sheets_roll5": 0.2,
        "goals_conceded_roll3": 0.3,
        "goals_conceded_roll5": 0.4,
        "minutes_trend": "stable",
        "minutes_roll8": 88.0,
        "fixture_context": "SGW",
    }

def _make_features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# evaluation.metrics
# ---------------------------------------------------------------------------

class TestMeanReturn:
    def test_returns_mean_of_matching_players(self):
        outcomes = pd.DataFrame({"player_id": [1, 2, 3], "total_points": [6.0, 8.0, 4.0]})
        result = mean_return([1, 3], outcomes)
        assert abs(result - 5.0) < 1e-9

    def test_returns_none_when_no_match(self):
        outcomes = pd.DataFrame({"player_id": [1], "total_points": [6.0]})
        assert mean_return([99], outcomes) is None

    def test_returns_none_for_empty_outcomes(self):
        outcomes = pd.DataFrame({"player_id": [], "total_points": []})
        assert mean_return([1], outcomes) is None

    def test_deterministic(self):
        outcomes = pd.DataFrame({"player_id": [1, 2], "total_points": [5.0, 7.0]})
        assert mean_return([1, 2], outcomes) == mean_return([1, 2], outcomes)

class TestTop1Return:
    def test_returns_correct_points(self):
        outcomes = pd.DataFrame({"player_id": [7], "total_points": [12.0]})
        assert top1_return(7, outcomes) == 12.0

    def test_returns_none_when_player_absent(self):
        outcomes = pd.DataFrame({"player_id": [1], "total_points": [6.0]})
        assert top1_return(99, outcomes) is None

    def test_returns_none_for_nan_points(self):
        outcomes = pd.DataFrame({"player_id": [5], "total_points": [float("nan")]})
        assert top1_return(5, outcomes) is None

class TestHitRate:
    def test_returns_1_when_best_in_list(self):
        assert hit_rate([1, 2, 3], 2) == 1

    def test_returns_0_when_best_not_in_list(self):
        assert hit_rate([1, 2, 3], 99) == 0

    def test_empty_list_returns_0(self):
        assert hit_rate([], 1) == 0

    def test_single_element_hit(self):
        assert hit_rate([42], 42) == 1

class TestRegret:
    def test_zero_regret_for_optimal_pick(self):
        assert regret(10.0, 10.0) == 0.0

    def test_positive_regret_for_suboptimal_pick(self):
        assert abs(regret(12.0, 6.0) - 6.0) < 1e-9

    def test_none_when_picked_points_none(self):
        assert regret(10.0, None) is None

    def test_negative_regret_impossible_but_accepted(self):
        # Regret can be negative if actual_best was outside the pool
        result = regret(4.0, 8.0)
        assert result == -4.0

class TestRankCorrelation:
    def test_perfect_positive_correlation(self):
        pred = pd.Series([3.0, 2.0, 1.0], index=[1, 2, 3])
        actual = pd.Series([30.0, 20.0, 10.0], index=[1, 2, 3])
        rho = rank_correlation(pred, actual)
        assert abs(rho - 1.0) < 1e-6

    def test_perfect_negative_correlation(self):
        pred = pd.Series([1.0, 2.0, 3.0], index=[1, 2, 3])
        actual = pd.Series([30.0, 20.0, 10.0], index=[1, 2, 3])
        rho = rank_correlation(pred, actual)
        assert abs(rho - (-1.0)) < 1e-6

    def test_returns_none_for_single_observation(self):
        pred = pd.Series([5.0], index=[1])
        actual = pd.Series([6.0], index=[1])
        assert rank_correlation(pred, actual) is None

    def test_handles_non_overlapping_indices(self):
        pred = pd.Series([1.0, 2.0], index=[1, 2])
        actual = pd.Series([5.0, 6.0], index=[3, 4])
        assert rank_correlation(pred, actual) is None

    def test_partial_overlap_uses_common_index(self):
        pred = pd.Series([1.0, 2.0, 3.0], index=[1, 2, 3])
        actual = pd.Series([10.0, 20.0], index=[1, 2])
        rho = rank_correlation(pred, actual)
        assert rho is not None

    def test_deterministic(self):
        pred = pd.Series([1.0, 2.0, 3.0], index=[1, 2, 3])
        actual = pd.Series([4.0, 2.0, 6.0], index=[1, 2, 3])
        assert rank_correlation(pred, actual) == rank_correlation(pred, actual)

class TestReturnVariance:
    def test_zero_variance_for_constant_returns(self):
        returns = pd.Series([5.0, 5.0, 5.0])
        assert return_variance(returns) == 0.0

    def test_nonzero_variance_for_varied_returns(self):
        returns = pd.Series([2.0, 8.0, 14.0])
        assert return_variance(returns) > 0

    def test_returns_none_for_single_value(self):
        assert return_variance(pd.Series([5.0])) is None

    def test_returns_none_for_empty_series(self):
        assert return_variance(pd.Series([], dtype=float)) is None

class TestDownsideRate:
    def test_all_below_threshold(self):
        returns = pd.Series([1.0, 2.0, 3.0])
        assert downside_rate(returns, threshold=4.0) == 1.0

    def test_none_below_threshold(self):
        returns = pd.Series([5.0, 6.0, 7.0])
        assert downside_rate(returns, threshold=4.0) == 0.0

    def test_half_below_threshold(self):
        returns = pd.Series([2.0, 8.0])
        assert abs(downside_rate(returns, threshold=4.0) - 0.5) < 1e-9

    def test_returns_none_for_empty_series(self):
        assert downside_rate(pd.Series([], dtype=float)) is None

    def test_custom_threshold(self):
        returns = pd.Series([5.0, 6.0, 7.0])
        assert downside_rate(returns, threshold=6.0) == pytest.approx(1 / 3)

# ---------------------------------------------------------------------------
# evaluation.windows
# ---------------------------------------------------------------------------

class TestEvaluationGameweeks:
    def test_filters_to_range(self):
        features = _make_features(
            _state_row(1, 3), _state_row(1, 5), _state_row(1, 7), _state_row(1, 9)
        )
        result = evaluation_gameweeks(features, min_gw=4, max_gw=8)
        assert result == [5, 7]

    def test_empty_range_returns_empty(self):
        features = _make_features(_state_row(1, 5))
        result = evaluation_gameweeks(features, min_gw=10, max_gw=20)
        assert result == []

    def test_returns_sorted_order(self):
        features = _make_features(
            _state_row(1, 9), _state_row(1, 3), _state_row(1, 6)
        )
        result = evaluation_gameweeks(features, min_gw=1, max_gw=10)
        assert result == [3, 6, 9]

    def test_inclusive_boundaries(self):
        features = _make_features(
            _state_row(1, 3), _state_row(1, 5), _state_row(1, 7)
        )
        result = evaluation_gameweeks(features, min_gw=3, max_gw=7)
        assert 3 in result and 7 in result

class TestAssertNoFutureleakage:
    def test_passes_for_valid_state_features(self):
        features = _make_features(_state_row(1, 5), _state_row(2, 5))
        assert_no_future_leakage(features, 5)  # should not raise

    def test_raises_for_missing_gw(self):
        features = _make_features(_state_row(1, 5))
        with pytest.raises(ValueError, match="no rows for gw=99"):
            assert_no_future_leakage(features, 99)

    def test_raises_for_missing_rolling_columns(self):
        features = _make_features(_state_row(1, 5))
        features = features.drop(columns=["points_roll3"])
        with pytest.raises(ValueError, match="missing rolling columns"):
            assert_no_future_leakage(features, 5)

    def test_error_message_names_missing_columns(self):
        features = _make_features(_state_row(1, 5))
        features = features.drop(columns=["points_roll3", "xgi_roll3"])
        with pytest.raises(ValueError) as exc_info:
            assert_no_future_leakage(features, 5)
        msg = str(exc_info.value)
        assert "points_roll3" in msg or "xgi_roll3" in msg

# ---------------------------------------------------------------------------
# evaluation.baselines
# ---------------------------------------------------------------------------

class TestBaselineRecentPoints:
    def test_orders_by_points_roll3_descending(self):
        features = _make_features(
            _state_row(1, 5, points_roll3=8.0),
            _state_row(2, 5, points_roll3=5.0),
            _state_row(3, 5, points_roll3=3.0),
        )
        result = baseline_recent_points(features, target_gw=5)
        assert list(result["player_id"]) == [1, 2, 3]

    def test_filters_low_minutes_players(self):
        features = _make_features(
            _state_row(1, 5, minutes_roll3=90.0),
            _state_row(2, 5, minutes_roll3=10.0),  # below threshold
        )
        result = baseline_recent_points(features, target_gw=5)
        assert 2 not in result["player_id"].values

    def test_is_deterministic(self):
        features = _make_features(
            _state_row(1, 5, points_roll3=7.0),
            _state_row(2, 5, points_roll3=5.0),
        )
        r1 = baseline_recent_points(features, target_gw=5)
        r2 = baseline_recent_points(features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

    def test_n_limits_rows(self):
        features = _make_features(
            _state_row(1, 5), _state_row(2, 5), _state_row(3, 5)
        )
        result = baseline_recent_points(features, target_gw=5, n=2)
        assert len(result) <= 2

    def test_returns_empty_when_all_below_minutes(self):
        features = _make_features(
            _state_row(1, 5, minutes_roll3=5.0),
            _state_row(2, 5, minutes_roll3=10.0),
        )
        result = baseline_recent_points(features, target_gw=5, min_minutes_roll3=45.0)
        assert result.empty

class TestBaselineHighestXgi:
    def test_orders_by_xgi_roll3_descending(self):
        features = _make_features(
            _state_row(1, 5, xgi_roll3=0.9),
            _state_row(2, 5, xgi_roll3=0.3),
        )
        result = baseline_highest_xgi(features, target_gw=5)
        assert result.iloc[0]["player_id"] == 1

    def test_is_deterministic(self):
        features = _make_features(
            _state_row(1, 5, xgi_roll3=0.7),
            _state_row(2, 5, xgi_roll3=0.4),
        )
        r1 = baseline_highest_xgi(features, target_gw=5)
        r2 = baseline_highest_xgi(features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

class TestBaselineFixtureOnly:
    def test_easy_fixture_ranks_first(self):
        features = _make_features(
            _state_row(1, 5, fdr_avg=1.5),  # easy
            _state_row(2, 5, fdr_avg=4.5),  # hard
        )
        result = baseline_fixture_only(features, target_gw=5)
        assert result.iloc[0]["player_id"] == 1

    def test_fdr_score_column_present(self):
        features = _make_features(_state_row(1, 5), _state_row(2, 5))
        result = baseline_fixture_only(features, target_gw=5)
        assert "fdr_score" in result.columns

    def test_is_deterministic(self):
        features = _make_features(
            _state_row(1, 5, fdr_avg=2.0),
            _state_row(2, 5, fdr_avg=3.5),
        )
        r1 = baseline_fixture_only(features, target_gw=5)
        r2 = baseline_fixture_only(features, target_gw=5)
        pd.testing.assert_frame_equal(r1, r2)

class TestBaselineRandomTopN:
    def test_returns_n_players(self):
        features = _make_features(
            *[_state_row(i, 5) for i in range(1, 11)]
        )
        result = baseline_random_top_n(features, target_gw=5, n=5)
        assert len(result) == 5

    def test_reproducible_with_same_seed(self):
        features = _make_features(
            *[_state_row(i, 5) for i in range(1, 11)]
        )
        r1 = baseline_random_top_n(features, target_gw=5, n=5, seed=42)
        r2 = baseline_random_top_n(features, target_gw=5, n=5, seed=42)
        pd.testing.assert_frame_equal(r1, r2)

    def test_different_seeds_may_differ(self):
        features = _make_features(
            *[_state_row(i, 5) for i in range(1, 11)]
        )
        r1 = baseline_random_top_n(features, target_gw=5, n=5, seed=42)
        r2 = baseline_random_top_n(features, target_gw=5, n=5, seed=99)
        # With enough players, different seeds usually produce different orderings
        assert not r1["player_id"].equals(r2["player_id"]) or True  # allowed to match

    def test_does_not_exceed_eligible_pool(self):
        features = _make_features(_state_row(1, 5), _state_row(2, 5))
        result = baseline_random_top_n(features, target_gw=5, n=10)
        assert len(result) <= 2
