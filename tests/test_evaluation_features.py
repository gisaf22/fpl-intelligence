"""Tests for evaluation.features — stateful feature lift evaluation.

Validates:
- Lag-1 column computation is correct (no leakage)
- Rank correlation computation
- Lift comparison: rolling vs single-game predictors
- Deterministic outputs across calls
- Output structure and key presence
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.helpers.features import _compute_lag1_columns, evaluate_feature_lift

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _spine_row(
    player_id: int,
    gw: int,
    total_points: float,
    xgi: float,
    minutes: float = 90.0,
    points_roll3: float = 5.0,
    xgi_roll3: float = 0.5,
    minutes_roll5: float = 80.0,
) -> dict:
    """Row with both spine raw columns and state rolling columns."""
    return {
        "player_id": player_id,
        "gw": gw,
        "player_name": f"P{player_id}",
        "position_label": "MID",
        "position_code": 3,
        "team_id": player_id * 10,
        "purchase_price": 7.0,
        "fdr_avg": 3.0,
        "fdr_min": 2.5,
        "fdr_max": 3.5,
        "is_bgw": False,
        "is_dgw": False,
        "goals_scored": 0.2,
        "total_points": total_points,
        "xgi": xgi,
        "minutes": minutes,
        "points_roll3": points_roll3,
        "points_roll5": points_roll3 - 0.5,
        "minutes_roll3": minutes,
        "minutes_roll5": minutes_roll5,
        "xgi_roll3": xgi_roll3,
        "xgi_roll5": xgi_roll3 - 0.05,
        "xgc_roll3": 0.2,
        "xgc_roll5": 0.25,
        "goals_conceded_roll3": 0.3,
        "goals_conceded_roll5": 0.4,
        "minutes_trend": "stable",
    }


def _make_features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _sequential_player(player_id: int, gws_and_points: list[tuple[int, float, float]]) -> list[dict]:
    """Create sequential rows for a player across GWs: (gw, total_points, xgi) tuples."""
    rows = []
    for i, (gw, pts, xgi) in enumerate(gws_and_points):
        roll3 = sum(p for _, p, _ in gws_and_points[max(0, i-3):i]) / max(1, min(3, i))
        rows.append(_spine_row(player_id, gw, pts, xgi, points_roll3=roll3))
    return rows


# ---------------------------------------------------------------------------
# _compute_lag1_columns
# ---------------------------------------------------------------------------

class TestComputeLag1Columns:
    def test_lag1_is_prior_gw_value(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(1, 6, total_points=4.0, xgi=0.3),
        )
        result = _compute_lag1_columns(features)
        gw6_row = result[result["gw"] == 6]
        # GW 6 lag1 should be GW 5 value
        assert float(gw6_row["points_lag1"].iloc[0]) == pytest.approx(8.0)
        assert float(gw6_row["xgi_lag1"].iloc[0]) == pytest.approx(0.9)

    def test_first_gw_lag1_is_nan(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(1, 6, total_points=4.0, xgi=0.3),
        )
        result = _compute_lag1_columns(features)
        gw5_row = result[result["gw"] == 5]
        assert pd.isna(gw5_row["points_lag1"].iloc[0])

    def test_does_not_bleed_across_players(self):
        features = _make_features(
            _spine_row(1, 5, total_points=10.0, xgi=1.0),
            _spine_row(2, 5, total_points=2.0, xgi=0.1),
            _spine_row(1, 6, total_points=4.0, xgi=0.3),
            _spine_row(2, 6, total_points=8.0, xgi=0.7),
        )
        result = _compute_lag1_columns(features)
        p1_gw6 = result[(result["player_id"] == 1) & (result["gw"] == 6)]
        p2_gw6 = result[(result["player_id"] == 2) & (result["gw"] == 6)]
        # P1 lag1 should be P1's GW5, not P2's
        assert float(p1_gw6["points_lag1"].iloc[0]) == pytest.approx(10.0)
        assert float(p2_gw6["points_lag1"].iloc[0]) == pytest.approx(2.0)

    def test_minutes_lag1_column_created(self):
        features = _make_features(
            _spine_row(1, 5, total_points=6.0, xgi=0.5),
            _spine_row(1, 6, total_points=4.0, xgi=0.3),
        )
        result = _compute_lag1_columns(features)
        assert "minutes_lag1" in result.columns


# ---------------------------------------------------------------------------
# evaluate_feature_lift
# ---------------------------------------------------------------------------

class TestEvaluateFeatureLift:
    def test_returns_gw_count(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
            _spine_row(3, 5, total_points=6.0, xgi=0.5),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        assert result["gw_count"] == 1

    def test_deterministic(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
            _spine_row(3, 5, total_points=6.0, xgi=0.5),
        )
        r1 = evaluate_feature_lift(features, gameweeks=[5])
        r2 = evaluate_feature_lift(features, gameweeks=[5])
        assert r1["gw_count"] == r2["gw_count"]
        assert r1["predictors"] == r2["predictors"]

    def test_output_keys_present(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        assert "gw_count" in result
        assert "predictors" in result
        assert "lift" in result
        assert "detail" in result

    def test_predictor_dict_contains_all_signals(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
            _spine_row(3, 5, total_points=6.0, xgi=0.5),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        expected = {"points_roll3", "points_lag1", "xgi_roll3", "xgi_lag1",
                    "minutes_roll5", "minutes_lag1"}
        assert expected.issubset(set(result["predictors"].keys()))

    def test_predictor_has_label_and_mean_rho(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
            _spine_row(3, 5, total_points=6.0, xgi=0.5),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        for pred_name, pred_info in result["predictors"].items():
            assert "label" in pred_info
            assert "mean_rho" in pred_info
            assert "n_gws" in pred_info

    def test_lift_keys_match_comparison_pairs(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        assert "points" in result["lift"]
        assert "xgi" in result["lift"]
        assert "minutes" in result["lift"]

    def test_detail_is_dataframe(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        assert isinstance(result["detail"], pd.DataFrame)

    def test_empty_gameweeks_returns_zero_count(self):
        features = _make_features(_spine_row(1, 5, total_points=6.0, xgi=0.5))
        result = evaluate_feature_lift(features, gameweeks=[])
        assert result["gw_count"] == 0

    def test_temporal_integrity_enforced(self):
        features = _make_features(
            _spine_row(1, 5, total_points=8.0, xgi=0.9),
            _spine_row(2, 5, total_points=4.0, xgi=0.3),
        )
        features = features.drop(columns=["points_roll3"])
        with pytest.raises(ValueError, match="missing rolling columns"):
            evaluate_feature_lift(features, gameweeks=[5])

    def test_rho_range_is_valid(self):
        # Build a case where rolling signal aligns with outcome
        features = _make_features(
            _spine_row(1, 5, total_points=10.0, xgi=0.9, points_roll3=8.0, xgi_roll3=0.8),
            _spine_row(2, 5, total_points=6.0, xgi=0.5, points_roll3=5.0, xgi_roll3=0.5),
            _spine_row(3, 5, total_points=2.0, xgi=0.1, points_roll3=2.0, xgi_roll3=0.1),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        for pred_name, pred_info in result["predictors"].items():
            rho = pred_info["mean_rho"]
            if rho is not None:
                assert -1.0 <= rho <= 1.0, f"{pred_name} rho={rho} out of [-1, 1]"

    def test_lift_is_difference_of_rhos(self):
        features = _make_features(
            _spine_row(1, 5, total_points=10.0, xgi=0.9, points_roll3=8.0, xgi_roll3=0.8),
            _spine_row(2, 5, total_points=6.0, xgi=0.5, points_roll3=5.0, xgi_roll3=0.5),
            _spine_row(3, 5, total_points=2.0, xgi=0.1, points_roll3=2.0, xgi_roll3=0.1),
        )
        result = evaluate_feature_lift(features, gameweeks=[5])
        p = result["predictors"]
        r_rho = p.get("points_roll3", {}).get("mean_rho")
        l_rho = p.get("points_lag1", {}).get("mean_rho")
        lift = result["lift"].get("points")
        if r_rho is not None and l_rho is not None and lift is not None:
            assert abs(lift - (r_rho - l_rho)) < 1e-4
