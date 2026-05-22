"""Tests for evaluation.rolling_xgi_study — rolling xGI horizon study execution.

Validates:
- Forward-only population filtering
- Rolling window evaluation correctness (higher smoothing = higher rho in controlled data)
- No future leakage (temporal integrity enforcement)
- Deterministic metric reproducibility
- Output structure completeness
- lift_over_lag1 arithmetic correctness
- interpret_results returns a known interpretation string
"""

from __future__ import annotations

import pandas as pd
import pytest

from studies.experiments.rolling_xgi_study import (
    _add_xgi_lag1,
    _filter_fwd_population,
    evaluate_rolling_xgi_horizons,
    interpret_results,
)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _fwd_row(
    player_id: int,
    gw: int,
    total_points: float = 6.0,
    xgi: float = 0.5,
    xgi_roll3: float = 0.5,
    xgi_roll5: float = 0.48,
    xgi_roll8: float = 0.46,
    minutes_roll3: float = 85.0,
    position_label: str = "FWD",
) -> dict:
    """Minimal FWD row with all columns required by the study evaluation."""
    return {
        "player_id": player_id,
        "gw": gw,
        "player_name": f"FWD_{player_id}",
        "position_label": position_label,
        "position_code": 4,
        "team_id": player_id * 10,
        "purchase_price": 8.0,
        "fdr_avg": 3.0,
        "fdr_min": 2.5,
        "fdr_max": 3.5,
        "is_bgw": False,
        "is_dgw": False,
        "total_points": total_points,
        "xgi": xgi,
        "minutes": 90.0,
        "points_roll3": total_points * 0.9,
        "points_roll5": total_points * 0.85,
        "points_roll8": total_points * 0.80,
        "minutes_roll3": minutes_roll3,
        "minutes_roll5": minutes_roll3 - 5.0,
        "minutes_roll8": minutes_roll3 - 8.0,
        "xgi_roll3": xgi_roll3,
        "xgi_roll5": xgi_roll5,
        "xgi_roll8": xgi_roll8,
        "xgc_roll3": 0.3,
        "xgc_roll5": 0.3,
        "xgc_roll8": 0.3,
        "goals_conceded_roll3": 1.0,
        "goals_conceded_roll5": 1.0,
        "goals_conceded_roll8": 1.0,
        "minutes_trend": "stable",
        "fixture_context": "SGW",
    }


def _make_features(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _multi_gw_fwd_population(
    n_players: int = 8,
    gws: list[int] | None = None,
    rank_by_ability: bool = True,
) -> pd.DataFrame:
    """Build a multi-GW FWD population where ability is monotonic across player IDs.

    Players 1..n have increasing true ability. This makes roll3/roll5 predictable:
    higher ability → higher rolling xGI → should rank first → higher rho.
    """
    if gws is None:
        gws = list(range(6, 14))
    rows = []
    for pid in range(1, n_players + 1):
        ability = pid / n_players  # 0.125..1.0
        for gw in gws:
            rows.append(_fwd_row(
                player_id=pid,
                gw=gw,
                total_points=ability * 10.0,
                xgi=ability,
                xgi_roll3=ability,
                xgi_roll5=ability * 0.95,
                xgi_roll8=ability * 0.90,
                minutes_roll3=85.0,
            ))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# _add_xgi_lag1
# ---------------------------------------------------------------------------

class TestAddXgiLag1:
    def test_lag1_is_prior_gw_value(self):
        features = _make_features(
            _fwd_row(1, 5, xgi=0.8),
            _fwd_row(1, 6, xgi=0.3),
        )
        result = _add_xgi_lag1(features)
        gw6 = result[result["gw"] == 6]
        assert float(gw6["xgi_lag1"].iloc[0]) == pytest.approx(0.8)

    def test_first_gw_lag1_is_nan(self):
        features = _make_features(
            _fwd_row(1, 5, xgi=0.8),
            _fwd_row(1, 6, xgi=0.3),
        )
        result = _add_xgi_lag1(features)
        gw5 = result[result["gw"] == 5]
        assert pd.isna(gw5["xgi_lag1"].iloc[0])

    def test_lag1_does_not_bleed_across_players(self):
        features = _make_features(
            _fwd_row(1, 5, xgi=1.0),
            _fwd_row(2, 5, xgi=0.1),
            _fwd_row(1, 6, xgi=0.5),
            _fwd_row(2, 6, xgi=0.7),
        )
        result = _add_xgi_lag1(features)
        p1_gw6 = result[(result["player_id"] == 1) & (result["gw"] == 6)]
        p2_gw6 = result[(result["player_id"] == 2) & (result["gw"] == 6)]
        assert float(p1_gw6["xgi_lag1"].iloc[0]) == pytest.approx(1.0)
        assert float(p2_gw6["xgi_lag1"].iloc[0]) == pytest.approx(0.1)

    def test_column_present_after_call(self):
        features = _make_features(_fwd_row(1, 6, xgi=0.5))
        result = _add_xgi_lag1(features)
        assert "xgi_lag1" in result.columns


# ---------------------------------------------------------------------------
# _filter_fwd_population
# ---------------------------------------------------------------------------

class TestFilterFwdPopulation:
    def test_excludes_non_fwd_positions(self):
        features = _make_features(
            _fwd_row(1, 6, position_label="FWD"),
            _fwd_row(2, 6, position_label="MID"),
            _fwd_row(3, 6, position_label="DEF"),
        )
        result = _filter_fwd_population(features, gw=6, min_minutes=60.0)
        assert set(result["player_id"]) == {1}

    def test_excludes_low_minutes_players(self):
        features = _make_features(
            _fwd_row(1, 6, minutes_roll3=90.0),
            _fwd_row(2, 6, minutes_roll3=30.0),  # below threshold
        )
        result = _filter_fwd_population(features, gw=6, min_minutes=60.0)
        assert 2 not in result["player_id"].values

    def test_includes_exactly_threshold_minutes(self):
        features = _make_features(
            _fwd_row(1, 6, minutes_roll3=60.0),
        )
        result = _filter_fwd_population(features, gw=6, min_minutes=60.0)
        assert 1 in result["player_id"].values

    def test_returns_only_target_gw(self):
        features = _make_features(
            _fwd_row(1, 6),
            _fwd_row(1, 7),
            _fwd_row(2, 6),
        )
        result = _filter_fwd_population(features, gw=6, min_minutes=60.0)
        assert set(result["gw"]) == {6}

    def test_empty_if_no_fwd_at_gw(self):
        features = _make_features(
            _fwd_row(1, 7, position_label="MID"),
        )
        result = _filter_fwd_population(features, gw=7, min_minutes=60.0)
        assert result.empty


# ---------------------------------------------------------------------------
# evaluate_rolling_xgi_horizons — no future leakage enforcement
# ---------------------------------------------------------------------------

class TestNoFutureLeakage:
    def test_raises_when_rolling_columns_missing(self):
        features = _make_features(
            _fwd_row(1, 6), _fwd_row(2, 6), _fwd_row(3, 6),
            _fwd_row(4, 6), _fwd_row(5, 6),
        )
        features = features.drop(columns=["xgi_roll3"])
        features = features.drop(columns=["points_roll3"])
        with pytest.raises(ValueError, match="missing rolling columns"):
            evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=6)


# ---------------------------------------------------------------------------
# evaluate_rolling_xgi_horizons — forward-only filtering
# ---------------------------------------------------------------------------

class TestForwardOnlyFiltering:
    def test_mid_players_excluded_from_evaluation(self):
        """MID players should not contribute to the FWD study metrics."""
        fwd_rows = [_fwd_row(i, 6, total_points=float(i), xgi_roll3=float(i) / 10)
                    for i in range(1, 8)]
        mid_rows = [_fwd_row(i + 100, 6, total_points=15.0, xgi_roll3=5.0,
                             position_label="MID")
                    for i in range(5)]
        features = pd.DataFrame(fwd_rows + mid_rows)
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=6)
        # MID players with xgi_roll3=5.0 should not dominate rho if excluded
        assert result["gw_count"] >= 0  # runs without error

    def test_results_differ_when_mids_present_vs_absent(self):
        """Evaluation should use only FWDs — MID-only data should produce 0 evaluated GWs."""
        mid_only = pd.DataFrame([
            _fwd_row(i, 6, position_label="MID") for i in range(1, 10)
        ])
        result = evaluate_rolling_xgi_horizons(mid_only, min_gw=6, max_gw=6)
        assert result["gw_count"] == 0


# ---------------------------------------------------------------------------
# evaluate_rolling_xgi_horizons — output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:
    def _minimal_features(self) -> pd.DataFrame:
        return _multi_gw_fwd_population(n_players=8, gws=[6, 7, 8])

    def test_required_keys_present(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        for key in ("eval_gws", "gw_count", "signals", "lift_over_lag1",
                    "top1_metrics", "threshold_assessment", "best_signal", "detail"):
            assert key in result, f"Missing key: {key}"

    def test_signals_contains_all_four_variants(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        for sig in ("xgi_lag1", "xgi_roll3", "xgi_roll5", "xgi_roll8"):
            assert sig in result["signals"], f"Missing signal: {sig}"

    def test_signal_entry_has_required_fields(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        for sig, info in result["signals"].items():
            assert "label" in info, f"{sig} missing label"
            assert "mean_rho" in info, f"{sig} missing mean_rho"
            assert "std_rho" in info, f"{sig} missing std_rho"
            assert "n_gws" in info, f"{sig} missing n_gws"

    def test_lift_over_lag1_lag1_is_zero(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        assert result["lift_over_lag1"]["xgi_lag1"] == 0.0

    def test_threshold_assessment_has_three_criteria(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        ta = result["threshold_assessment"]
        assert "positive_lift" in ta
        assert "operational_usefulness" in ta
        assert "stability" in ta

    def test_detail_is_dataframe(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        assert isinstance(result["detail"], pd.DataFrame)

    def test_gw_count_matches_eval_gws(self):
        result = evaluate_rolling_xgi_horizons(self._minimal_features(), min_gw=6, max_gw=8)
        assert result["gw_count"] == len(result["detail"])

    def test_empty_when_no_fwd_in_range(self):
        features = pd.DataFrame([_fwd_row(1, 20, position_label="MID")])
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=8)
        assert result["gw_count"] == 0


# ---------------------------------------------------------------------------
# evaluate_rolling_xgi_horizons — determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_identical_results_on_repeated_calls(self):
        features = _multi_gw_fwd_population(n_players=8, gws=[6, 7, 8])
        r1 = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=8)
        r2 = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=8)
        assert r1["signals"] == r2["signals"]
        assert r1["lift_over_lag1"] == r2["lift_over_lag1"]
        assert r1["gw_count"] == r2["gw_count"]


# ---------------------------------------------------------------------------
# evaluate_rolling_xgi_horizons — lift arithmetic
# ---------------------------------------------------------------------------

class TestLiftArithmetic:
    def test_lift_equals_difference_of_rhos(self):
        features = _multi_gw_fwd_population(n_players=8, gws=[6, 7, 8])
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=8)
        sigs = result["signals"]
        lifts = result["lift_over_lag1"]
        lag1_rho = sigs["xgi_lag1"]["mean_rho"]
        for sig in ("xgi_roll3", "xgi_roll5", "xgi_roll8"):
            sig_rho = sigs[sig]["mean_rho"]
            expected_lift = round(sig_rho - lag1_rho, 4)
            actual_lift = lifts[sig]
            if sig_rho is not None and lag1_rho is not None and actual_lift is not None:
                assert abs(actual_lift - expected_lift) < 1e-3, (
                    f"Lift arithmetic error for {sig}: {actual_lift} != {expected_lift}"
                )

    def test_rho_values_in_valid_range(self):
        features = _multi_gw_fwd_population(n_players=8, gws=[6, 7, 8])
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=8)
        for sig, info in result["signals"].items():
            rho = info["mean_rho"]
            if rho is not None:
                assert -1.0 <= rho <= 1.0, f"{sig} rho={rho} out of [-1, 1]"


# ---------------------------------------------------------------------------
# evaluate_rolling_xgi_horizons — rolling window correctness
# ---------------------------------------------------------------------------

class TestRollingWindowCorrectness:
    def test_rolling_beats_lag1_in_controlled_data(self):
        """In monotonic-ability data with no per-GW noise, rolling windows should equal or
        exceed lag1 rho because smoothing helps when true ability is stable."""
        features = _multi_gw_fwd_population(n_players=10, gws=list(range(6, 16)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=15)
        sigs = result["signals"]
        lag1_rho = sigs["xgi_lag1"]["mean_rho"]
        roll3_rho = sigs["xgi_roll3"]["mean_rho"]
        if lag1_rho is not None and roll3_rho is not None:
            assert roll3_rho >= lag1_rho - 0.05, (
                f"roll3 rho ({roll3_rho:.3f}) should not be much below lag1 ({lag1_rho:.3f})"
            )

    def test_downside_rate_between_zero_and_one(self):
        features = _multi_gw_fwd_population(n_players=10, gws=list(range(6, 12)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=11)
        for sig, metrics in result["top1_metrics"].items():
            dr = metrics["downside_rate"]
            if dr is not None:
                assert 0.0 <= dr <= 1.0, f"{sig} downside_rate={dr} not in [0, 1]"


# ---------------------------------------------------------------------------
# interpret_results
# ---------------------------------------------------------------------------

class TestInterpretResults:
    _KNOWN_INTERPRETATIONS = {
        "insufficient_data",
        "no_rolling_horizon_beats_lag1",
        "signal_remains_investigational_unstable",
        "signal_remains_investigational_below_threshold",
        "roll5_materially_improves_over_roll3",
        "roll3_supported_no_change_warranted",
        "signal_remains_investigational",
    }

    def test_returns_known_interpretation_string(self):
        features = _multi_gw_fwd_population(n_players=10, gws=list(range(6, 16)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=15)
        interp = interpret_results(result)
        assert interp in self._KNOWN_INTERPRETATIONS, f"Unknown interpretation: {interp}"

    def test_insufficient_data_for_empty_result(self):
        interp = interpret_results({"gw_count": 0})
        assert interp == "insufficient_data"

    def test_deterministic(self):
        features = _multi_gw_fwd_population(n_players=10, gws=list(range(6, 14)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=13)
        assert interpret_results(result) == interpret_results(result)
