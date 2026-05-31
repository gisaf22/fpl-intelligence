"""Tests for rolling xGI real-data validation execution path.

Covers:
- Real-data-shaped execution path correctness
- Deterministic replication behavior
- Metric reproducibility
- Temporal integrity preservation
- Study output stability

These tests do NOT use the live database — they use realistic synthetic data
that mirrors real-data characteristics (small FWD pool, high GW variance,
28 evaluation GWs). They verify evaluation correctness, not football outcomes.
"""

from __future__ import annotations

import random

import numpy as np
import pandas as pd
import pytest

from studies.experiments.rolling_xgi_study import (
    evaluate_rolling_xgi_horizons,
    interpret_results,
)
from studies.kernels.windows import assert_no_future_leakage

# ---------------------------------------------------------------------------
# Realistic data builder — mirrors real-data characteristics
# ---------------------------------------------------------------------------

def _realistic_fwd_dataset(
    n_players: int = 18,
    gws: list[int] | None = None,
    seed: int = 99,
) -> pd.DataFrame:
    """Build a dataset with realistic real-data characteristics.

    Mimics the 2024-25 real execution:
    - Small FWD pool (15-21 per GW)
    - High per-GW rho variance (real football is noisy)
    - All four xgi signal columns present
    - minutes_roll3 >= 60 for all included players
    - position_label == FWD

    Includes GW5 so that xgi_lag1 can be computed for GW6 (lag1 needs a prior GW).
    """
    if gws is None:
        # Include GW5 so GW6's xgi_lag1 is non-NaN — matches real DAL usage
        gws = list(range(5, 34))  # GW5-33; evaluation window is GW6-33

    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    rows = []
    for pid in range(1, n_players + 1):
        true_ability = pid / n_players  # stable latent ability
        for gw in gws:
            # Add per-GW noise — high variance mirrors real football
            noise = np_rng.normal(0, 0.3)
            xgi_base = max(0.0, true_ability * 0.8 + noise)

            rows.append({
                "player_id": pid,
                "gw": gw,
                "player_name": f"FWD_{pid}",
                "position_label": "FWD",
                "position_code": 4,
                "team_id": (pid % 10) + 1,
                "purchase_price": 7.5 + true_ability * 2,
                "fdr_avg": 3.0,
                "fdr_min": 2.0,
                "fdr_max": 4.0,
                "is_bgw": False,
                "is_dgw": False,
                # Target: noisy relationship with ability
                "total_points": max(0.0, true_ability * 8 + np_rng.normal(0, 3)),
                "xgi": xgi_base,
                "minutes": 90.0,
                "points_roll3": max(0.0, true_ability * 7 + np_rng.normal(0, 2)),
                "points_roll5": max(0.0, true_ability * 7 + np_rng.normal(0, 1.5)),
                "points_roll8": max(0.0, true_ability * 7 + np_rng.normal(0, 1.2)),
                # Rolling signals: smoother versions of xgi
                "xgi_roll3": max(0.0, true_ability * 0.8 + np_rng.normal(0, 0.2)),
                "xgi_roll5": max(0.0, true_ability * 0.8 + np_rng.normal(0, 0.15)),
                "xgi_roll8": max(0.0, true_ability * 0.8 + np_rng.normal(0, 0.1)),
                "xgc_roll3": 0.4,
                "xgc_roll5": 0.4,
                "xgc_roll8": 0.4,
                "goals_conceded_roll3": 1.2,
                "goals_conceded_roll5": 1.2,
                "goals_conceded_roll8": 1.2,
                "minutes_roll3": 82.0 + rng.uniform(-10, 5),
                "minutes_roll5": 80.0,
                "minutes_roll8": 78.0,
                "minutes_trend": "stable",
                "fixture_context": "SGW",
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Execution path correctness
# ---------------------------------------------------------------------------

class TestRealDataShapeCompatibility:
    """Study executes correctly on data shaped like real 2024-25 FWD population."""

    def test_executes_on_realistic_population_size(self):
        """Study runs without error on realistic FWD pool (15-21 per GW, 28 GWs)."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert result["gw_count"] > 0

    def test_evaluates_all_28_study_gws(self):
        """All 28 GWs in the GW6-33 window are evaluated when data is present."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert result["gw_count"] == 28

    def test_all_four_signals_evaluated(self):
        """All four study signals are evaluated and return non-None rho values."""
        # Include GW5 so xgi_lag1 is non-NaN for GW6 (lag1 requires a prior GW)
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(5, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig in ("xgi_lag1", "xgi_roll3", "xgi_roll5", "xgi_roll8"):
            assert result["signals"][sig]["mean_rho"] is not None, f"{sig} rho is None"
            assert result["signals"][sig]["n_gws"] == 28

    def test_lift_values_present_for_all_rolling_signals(self):
        """lift_over_lag1 is populated for all rolling windows."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig in ("xgi_roll3", "xgi_roll5", "xgi_roll8"):
            assert result["lift_over_lag1"][sig] is not None

    def test_top1_metrics_present_for_all_signals(self):
        """top1_metrics are computed for all signals across 28 GWs."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig in ("xgi_lag1", "xgi_roll3", "xgi_roll5", "xgi_roll8"):
            assert result["top1_metrics"][sig]["mean_top1_return"] is not None
            dr = result["top1_metrics"][sig]["downside_rate"]
            assert dr is not None and 0.0 <= dr <= 1.0

    def test_minimum_population_guard_skips_sparse_gws(self):
        """GWs with fewer than 5 FWDs are skipped without error."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        # Remove most players from GW10 to create a sparse GW
        features = features[~((features["gw"] == 10) & (features["player_id"] > 3))]
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        # GW10 has 3 players — below minimum of 5, should be skipped
        assert result["gw_count"] == 27


# ---------------------------------------------------------------------------
# Deterministic replication behavior
# ---------------------------------------------------------------------------

class TestDeterministicReplication:
    """Same input data always produces identical outputs."""

    def test_full_28gw_run_is_deterministic(self):
        """Two sequential runs on the same data produce byte-identical results."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        r1 = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        r2 = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert r1["signals"] == r2["signals"]
        assert r1["lift_over_lag1"] == r2["lift_over_lag1"]
        assert r1["gw_count"] == r2["gw_count"]
        assert r1["best_signal"] == r2["best_signal"]

    def test_detail_dataframe_is_deterministic(self):
        """Per-GW detail DataFrame is row-identical across repeated runs."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        r1 = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        r2 = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        pd.testing.assert_frame_equal(r1["detail"], r2["detail"])

    def test_interpretation_is_deterministic(self):
        """interpret_results returns the same string on repeated calls."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert interpret_results(result) == interpret_results(result)

    def test_different_seeds_produce_different_results(self):
        """Different data seeds produce different rho values (not a constant output)."""
        f1 = _realistic_fwd_dataset(seed=1)
        f2 = _realistic_fwd_dataset(seed=42)
        r1 = evaluate_rolling_xgi_horizons(f1)
        r2 = evaluate_rolling_xgi_horizons(f2)
        # At least one signal rho should differ between datasets
        assert r1["signals"]["xgi_roll3"]["mean_rho"] != r2["signals"]["xgi_roll3"]["mean_rho"]


# ---------------------------------------------------------------------------
# Metric reproducibility
# ---------------------------------------------------------------------------

class TestMetricReproducibility:
    """Metric computations are consistent and arithmetically correct."""

    def test_rho_values_in_valid_range(self):
        """All rho values lie in [-1, 1]."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig, info in result["signals"].items():
            rho = info["mean_rho"]
            if rho is not None:
                assert -1.0 <= rho <= 1.0, f"{sig} mean_rho={rho} outside [-1, 1]"

    def test_std_rho_non_negative(self):
        """Standard deviation of rho is non-negative for all signals."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig, info in result["signals"].items():
            std = info["std_rho"]
            if std is not None:
                assert std >= 0.0, f"{sig} std_rho={std} is negative"

    def test_lift_arithmetic_correct(self):
        """lift_over_lag1 equals the difference of mean rho values."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        lag1_rho = result["signals"]["xgi_lag1"]["mean_rho"]
        for sig in ("xgi_roll3", "xgi_roll5", "xgi_roll8"):
            sig_rho = result["signals"][sig]["mean_rho"]
            lift = result["lift_over_lag1"][sig]
            if sig_rho is not None and lag1_rho is not None and lift is not None:
                expected = round(sig_rho - lag1_rho, 4)
                assert abs(lift - expected) < 1e-3, (
                    f"{sig} lift={lift} != expected {expected}"
                )

    def test_lag1_lift_is_zero(self):
        """xgi_lag1 lift over itself is always 0.0."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert result["lift_over_lag1"]["xgi_lag1"] == 0.0

    def test_n_gws_matches_gw_count(self):
        """n_gws in each signal entry matches the overall gw_count."""
        # Include GW5 so xgi_lag1 has a valid prior-GW value at GW6
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(5, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig, info in result["signals"].items():
            assert info["n_gws"] == result["gw_count"], (
                f"{sig} n_gws={info['n_gws']} != gw_count={result['gw_count']}"
            )

    def test_downside_rates_in_valid_range(self):
        """All downside rates are in [0, 1]."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for sig, m in result["top1_metrics"].items():
            dr = m["downside_rate"]
            if dr is not None:
                assert 0.0 <= dr <= 1.0, f"{sig} downside_rate={dr} out of range"


# ---------------------------------------------------------------------------
# Temporal integrity preservation
# ---------------------------------------------------------------------------

class TestTemporalIntegrity:
    """assert_no_future_leakage is enforced throughout the evaluation window."""

    def test_temporal_guard_passes_on_valid_lag1_features(self):
        """assert_no_future_leakage does not raise on properly lagged features."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(5, 14)))
        for gw in range(6, 14):
            assert_no_future_leakage(features, gw)  # should not raise

    def test_temporal_guard_raises_on_missing_rolling_columns(self):
        """Evaluation raises ValueError when required rolling columns are absent."""
        features = _realistic_fwd_dataset(n_players=8, gws=list(range(6, 10)))
        features = features.drop(columns=["xgi_roll3", "points_roll3"])
        with pytest.raises(ValueError, match="missing rolling columns"):
            evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=9)

    def test_evaluation_skips_gws_outside_window(self):
        """GWs outside min_gw/max_gw are not included in evaluation."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(1, 38)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        evaluated_gws = result["detail"]["gw"].tolist()
        assert all(6 <= gw <= 33 for gw in evaluated_gws)
        assert 1 not in evaluated_gws
        assert 37 not in evaluated_gws

    def test_detail_gws_are_strictly_within_eval_window(self):
        """Detail DataFrame contains only rows within the evaluation GW window."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        min_gw = result["detail"]["gw"].min()
        max_gw = result["detail"]["gw"].max()
        assert min_gw >= 6
        assert max_gw <= 33


# ---------------------------------------------------------------------------
# Study output stability — structural invariants
# ---------------------------------------------------------------------------

class TestStudyOutputStability:
    """Study output structure is stable and complete regardless of data characteristics."""

    _REQUIRED_KEYS = (
        "eval_gws", "gw_count", "signals", "lift_over_lag1",
        "top1_metrics", "threshold_assessment", "best_signal", "detail",
    )
    _REQUIRED_SIGNALS = ("xgi_lag1", "xgi_roll3", "xgi_roll5", "xgi_roll8")
    _REQUIRED_THRESHOLD_KEYS = ("positive_lift", "operational_usefulness", "stability")

    def test_output_keys_stable_across_seeds(self):
        """All required output keys are present regardless of dataset seed."""
        for seed in (1, 42, 99, 123):
            features = _realistic_fwd_dataset(n_players=18, seed=seed)
            result = evaluate_rolling_xgi_horizons(features)
            for key in self._REQUIRED_KEYS:
                assert key in result, f"seed={seed}: missing key {key}"

    def test_signal_entries_stable_across_seeds(self):
        """All four signal entries are present in every run."""
        for seed in (1, 42, 99):
            features = _realistic_fwd_dataset(n_players=18, seed=seed)
            result = evaluate_rolling_xgi_horizons(features)
            for sig in self._REQUIRED_SIGNALS:
                assert sig in result["signals"], f"seed={seed}: missing signal {sig}"

    def test_threshold_assessment_keys_stable(self):
        """Threshold assessment always contains all three criteria."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for key in self._REQUIRED_THRESHOLD_KEYS:
            assert key in result["threshold_assessment"], f"missing threshold key: {key}"

    def test_interpretation_returns_known_string(self):
        """interpret_results always returns a string from the known set."""
        known = {
            "insufficient_data",
            "no_rolling_horizon_beats_lag1",
            "signal_remains_investigational_unstable",
            "signal_remains_investigational_below_threshold",
            "roll5_materially_improves_over_roll3",
            "roll3_supported_no_change_warranted",
            "signal_remains_investigational",
        }
        for seed in (1, 42, 99, 123):
            features = _realistic_fwd_dataset(n_players=18, seed=seed)
            result = evaluate_rolling_xgi_horizons(features)
            interp = interpret_results(result)
            assert interp in known, f"seed={seed}: unknown interpretation '{interp}'"

    def test_detail_has_expected_columns(self):
        """Detail DataFrame always contains gw, n_fwd, and per-signal rho columns."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        detail = result["detail"]
        assert "gw" in detail.columns
        assert "n_fwd" in detail.columns
        for sig in self._REQUIRED_SIGNALS:
            assert f"rho_{sig}" in detail.columns, f"detail missing rho_{sig}"

    def test_detail_gw_count_matches_gw_count_key(self):
        """Number of rows in detail equals gw_count."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert len(result["detail"]) == result["gw_count"]

    def test_best_signal_is_one_of_the_four_signals(self):
        """best_signal is always one of the four defined study signals."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert result["best_signal"] in self._REQUIRED_SIGNALS

    def test_threshold_assessment_values_are_booleans(self):
        """Each threshold criterion has a boolean 'met' field."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        for criterion, entry in result["threshold_assessment"].items():
            assert isinstance(entry["met"], bool), (
                f"{criterion}: 'met' is not bool (got {type(entry['met'])})"
            )

    def test_empty_result_on_all_non_fwd_data(self):
        """gw_count=0 is returned when no FWDs are in the population."""
        features = _realistic_fwd_dataset(n_players=18, gws=list(range(6, 34)))
        features["position_label"] = "MID"
        result = evaluate_rolling_xgi_horizons(features, min_gw=6, max_gw=33)
        assert result["gw_count"] == 0
