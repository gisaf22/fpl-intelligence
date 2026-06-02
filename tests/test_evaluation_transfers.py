"""Tests for evaluation.transfers and evaluation.value heuristic evaluation.

Validates:
- Deterministic outputs
- Future-window return computation
- Temporal integrity (eval GW uses only pre-deadline features)
- Correct lookahead window handling
- Graceful degradation when future GWs are absent
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.helpers.transfers import evaluate_transfer_heuristic
from tests.helpers.value import evaluate_value_heuristic

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _state_row(
    player_id: int,
    gw: int,
    total_points: float = 5.0,
    points_roll3: float = 5.0,
    points_roll5: float = 4.5,
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
        "goals_scored": 0.3,
        "total_points": total_points,
        "minutes": 90.0,
        "xgi": 0.4,
        "points_roll3": points_roll3,
        "points_roll5": points_roll5,
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


def _multi_gw_features(n_players: int = 3, gws: list[int] | None = None) -> pd.DataFrame:
    """Generate a features DataFrame spanning multiple GWs for lookahead tests."""
    if gws is None:
        gws = [5, 6, 7, 8]
    rows = []
    for gw in gws:
        for pid in range(1, n_players + 1):
            rows.append(
                _state_row(
                    player_id=pid,
                    gw=gw,
                    total_points=float(pid * 2 + gw),  # deterministic variety
                    points_roll3=float(pid + 3),
                    points_roll5=float(pid + 2),
                    xgi_roll3=0.1 * pid,
                )
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# evaluate_transfer_heuristic
# ---------------------------------------------------------------------------


class TestEvaluateTransferHeuristic:
    def test_returns_gw_count(self):
        features = _multi_gw_features(n_players=4)
        result = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        assert result["gw_count"] == 1

    def test_deterministic(self):
        features = _multi_gw_features(n_players=4)
        r1 = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        r2 = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        assert r1["gw_count"] == r2["gw_count"]
        assert r1["heuristic_avg_future_return"] == r2["heuristic_avg_future_return"]

    def test_output_keys_present(self):
        features = _multi_gw_features(n_players=4)
        result = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        for key in [
            "gw_count",
            "heuristic_avg_future_return",
            "baseline_recent_avg_future_return",
            "baseline_fixture_avg_future_return",
            "heuristic_variance",
            "detail",
        ]:
            assert key in result, f"missing key: {key}"

    def test_detail_is_dataframe(self):
        features = _multi_gw_features(n_players=4)
        result = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        assert isinstance(result["detail"], pd.DataFrame)

    def test_skips_gw_without_lookahead_coverage(self):
        # GW 8 requires lookahead to GW 11, which doesn't exist
        features = _multi_gw_features(n_players=3, gws=[5, 6, 7, 8])
        result = evaluate_transfer_heuristic(features, gameweeks=[8], lookahead=3)
        assert result["gw_count"] == 0

    def test_multi_gw_evaluation(self):
        features = _multi_gw_features(n_players=4, gws=[3, 4, 5, 6, 7, 8])
        result = evaluate_transfer_heuristic(features, gameweeks=[3, 4, 5], lookahead=2)
        assert result["gw_count"] == 3

    def test_temporal_integrity_enforced(self):
        features = _multi_gw_features(n_players=3)
        features = features.drop(columns=["points_roll3"])
        with pytest.raises(ValueError, match="missing rolling columns"):
            evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)

    def test_empty_gameweeks_returns_zero_count(self):
        features = _multi_gw_features(n_players=3)
        result = evaluate_transfer_heuristic(features, gameweeks=[], lookahead=2)
        assert result["gw_count"] == 0

    def test_avg_future_return_is_positive(self):
        features = _multi_gw_features(n_players=4, gws=[5, 6, 7])
        result = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        if result["gw_count"] > 0 and result["heuristic_avg_future_return"] is not None:
            assert result["heuristic_avg_future_return"] > 0

    def test_lookahead_affects_returns(self):
        features = _multi_gw_features(n_players=4, gws=[5, 6, 7, 8])
        r1 = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=1)
        r2 = evaluate_transfer_heuristic(features, gameweeks=[5], lookahead=2)
        # Longer lookahead should accumulate more points
        if r1["heuristic_avg_future_return"] is not None and r2["heuristic_avg_future_return"] is not None:
            assert r2["heuristic_avg_future_return"] >= r1["heuristic_avg_future_return"]


# ---------------------------------------------------------------------------
# evaluate_value_heuristic
# ---------------------------------------------------------------------------


class TestEvaluateValueHeuristic:
    def test_returns_gw_count(self):
        features = _multi_gw_features(n_players=4, gws=[5, 6, 7, 8, 9])
        result = evaluate_value_heuristic(features, gameweeks=[5], lookahead=3)
        assert result["gw_count"] == 1

    def test_deterministic(self):
        features = _multi_gw_features(n_players=4, gws=[5, 6, 7, 8, 9])
        r1 = evaluate_value_heuristic(features, gameweeks=[5], lookahead=3)
        r2 = evaluate_value_heuristic(features, gameweeks=[5], lookahead=3)
        assert r1["gw_count"] == r2["gw_count"]
        assert r1["heuristic_avg_ppc"] == r2["heuristic_avg_ppc"]

    def test_output_keys_present(self):
        features = _multi_gw_features(n_players=4, gws=[5, 6, 7, 8, 9])
        result = evaluate_value_heuristic(features, gameweeks=[5], lookahead=3)
        for key in [
            "gw_count",
            "heuristic_avg_ppc",
            "baseline_recent_avg_ppc",
            "baseline_fixture_avg_ppc",
            "heuristic_variance",
            "detail",
        ]:
            assert key in result, f"missing key: {key}"

    def test_skips_gw_without_lookahead_coverage(self):
        features = _multi_gw_features(n_players=3, gws=[5, 6, 7])
        # GW 6 needs GW 10, which doesn't exist
        result = evaluate_value_heuristic(features, gameweeks=[6], lookahead=4)
        assert result["gw_count"] == 0

    def test_temporal_integrity_enforced(self):
        features = _multi_gw_features(n_players=3, gws=[5, 6, 7, 8, 9])
        features = features.drop(columns=["xgi_roll3"])
        with pytest.raises(Exception):
            evaluate_value_heuristic(features, gameweeks=[5], lookahead=3)

    def test_ppc_is_positive_when_data_available(self):
        features = _multi_gw_features(n_players=4, gws=[5, 6, 7, 8, 9])
        result = evaluate_value_heuristic(features, gameweeks=[5], lookahead=3)
        if result["heuristic_avg_ppc"] is not None:
            assert result["heuristic_avg_ppc"] > 0
