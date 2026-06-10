"""Tests for evaluation.captain — captain heuristic historical evaluation.

Validates:
- Deterministic evaluation outputs
- Correct summary statistics (avg return, hit rate, regret)
- Temporal integrity enforcement
- Graceful handling of edge cases (empty GWs, no eligible players)
- Baseline comparison presence in output
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.helpers.captain import evaluate_captain_heuristic

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Shared fixture helpers (mirrored from test_evaluation_core for isolation)
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
) -> dict:
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
        "is_bgw": False,
        "is_dgw": False,
        "is_warmup_gw": False,
        "goals_scored": 0.3,
        "total_points": total_points,
        "minutes": 90.0,
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
# Tests
# ---------------------------------------------------------------------------


class TestEvaluateCaptainHeuristic:
    def test_returns_gw_count(self):
        features = _make_features(
            _state_row(1, 5, total_points=10.0, points_roll3=8.0, xgi_roll3=0.9),
            _state_row(2, 5, total_points=4.0, points_roll3=4.0, xgi_roll3=0.3),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        assert result["gw_count"] == 1

    def test_deterministic(self):
        features = _make_features(
            _state_row(1, 5, total_points=10.0, points_roll3=8.0, xgi_roll3=0.9),
            _state_row(2, 5, total_points=4.0, points_roll3=4.0, xgi_roll3=0.3),
        )
        r1 = evaluate_captain_heuristic(features, gameweeks=[5])
        r2 = evaluate_captain_heuristic(features, gameweeks=[5])
        assert r1["gw_count"] == r2["gw_count"]
        assert r1["top1_hit_rate"] == r2["top1_hit_rate"]
        assert r1["heuristic_avg_return"] == r2["heuristic_avg_return"]

    def test_output_keys_present(self):
        features = _make_features(
            _state_row(1, 5, total_points=8.0, points_roll3=7.0, xgi_roll3=0.8),
            _state_row(2, 5, total_points=4.0, points_roll3=3.0, xgi_roll3=0.3),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        for key in [
            "gw_count",
            "heuristic_avg_return",
            "baseline_recent_avg_return",
            "baseline_xgi_avg_return",
            "top1_hit_rate",
            "top3_hit_rate",
            "mean_regret",
            "heuristic_variance",
            "heuristic_downside_rate",
            "detail",
        ]:
            assert key in result, f"missing key: {key}"

    def test_detail_is_dataframe(self):
        features = _make_features(
            _state_row(1, 5, total_points=8.0, points_roll3=7.0),
            _state_row(2, 5, total_points=4.0, points_roll3=3.0),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        assert isinstance(result["detail"], pd.DataFrame)
        assert len(result["detail"]) == 1

    def test_detail_columns_present(self):
        features = _make_features(
            _state_row(1, 5, total_points=8.0, points_roll3=7.0),
            _state_row(2, 5, total_points=4.0, points_roll3=3.0),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        for col in ["gw", "heuristic_top1_id", "heuristic_top1_return", "top1_hit", "top3_hit", "regret"]:
            assert col in result["detail"].columns, f"missing detail column: {col}"

    def test_hit_rate_in_0_1_range(self):
        features = _make_features(
            _state_row(1, 5, total_points=10.0, points_roll3=8.0),
            _state_row(2, 5, total_points=4.0, points_roll3=3.0),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        assert 0.0 <= result["top1_hit_rate"] <= 1.0
        assert 0.0 <= result["top3_hit_rate"] <= 1.0

    def test_top1_hit_when_best_player_selected(self):
        # Player 1 has high form and will be picked as top captain
        # Player 1 also scores the most → top1_hit_rate should be 1.0
        features = _make_features(
            _state_row(1, 5, total_points=18.0, points_roll3=9.0, xgi_roll3=1.0, fdr_avg=2.0, minutes_roll3=90.0),
            _state_row(2, 5, total_points=2.0, points_roll3=2.0, xgi_roll3=0.1, fdr_avg=4.0, minutes_roll3=85.0),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        assert result["top1_hit_rate"] == 1.0

    def test_regret_is_non_negative_when_heuristic_is_suboptimal(self):
        # Player 2 scores more but player 1 is picked by heuristic (higher roll3)
        features = _make_features(
            _state_row(1, 5, total_points=6.0, points_roll3=9.0, xgi_roll3=1.0, fdr_avg=2.0),
            _state_row(2, 5, total_points=20.0, points_roll3=2.0, xgi_roll3=0.1, fdr_avg=4.5),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5])
        if result["mean_regret"] is not None:
            assert result["mean_regret"] >= 0

    def test_multi_gw_aggregates_correctly(self):
        features = _make_features(
            _state_row(1, 5, total_points=10.0, points_roll3=8.0),
            _state_row(2, 5, total_points=4.0, points_roll3=4.0),
            _state_row(1, 6, total_points=8.0, points_roll3=8.0),
            _state_row(2, 6, total_points=2.0, points_roll3=4.0),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[5, 6])
        assert result["gw_count"] == 2

    def test_empty_gameweeks_returns_zero_count(self):
        features = _make_features(
            _state_row(1, 5, total_points=6.0),
            _state_row(2, 5, total_points=4.0),
        )
        result = evaluate_captain_heuristic(features, gameweeks=[])
        assert result["gw_count"] == 0

    def test_gw_absent_from_features_is_skipped(self):
        features = _make_features(
            _state_row(1, 5, total_points=8.0, points_roll3=7.0),
            _state_row(2, 5, total_points=4.0, points_roll3=3.0),
        )
        # GW 99 doesn't exist → should be skipped without error
        result = evaluate_captain_heuristic(features, gameweeks=[5, 99])
        assert result["gw_count"] == 1

    def test_temporal_integrity_enforced(self):
        features = _make_features(
            _state_row(1, 5, total_points=6.0),
        )
        # Remove rolling columns to simulate bypassed state layer
        features = features.drop(columns=["points_roll3"])
        with pytest.raises(ValueError, match="missing rolling columns"):
            evaluate_captain_heuristic(features, gameweeks=[5])
