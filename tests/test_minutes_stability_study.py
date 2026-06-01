"""Validation tests for STUDY-MINSTAB-01: minutes stability x rolling xGI.

Validates the five requirements from the study design (Section 9):
1. No temporal leakage — structural check passes for every GW
2. Cohort assignment determinism — same input always produces same cohort
3. Population accounting closure — cohort sums equal n_all_fwd every GW
4. Result structure — all required keys present
5. Reproducibility — identical results on two consecutive calls

Design doc: docs/studies/minutes-stability-xgi-study.md
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from studies.experiments.minutes_stability_study import (
    _COHORT_FRINGE,
    _COHORT_ROTATION,
    _COHORT_STABLE,
    _COHORT_UNKNOWN,
    _assign_stability_cohort,
    evaluate_minutes_stability_conditioning,
    interpret_results,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Synthetic feature builder
# ---------------------------------------------------------------------------

def _make_fwd_features(
    n_players: int = 30,
    n_gws: int = 35,
    seed: int = 42,
    minutes_profile: str = "mixed",
) -> pd.DataFrame:
    """Build a minimal synthetic FWD dataset for study testing.

    All state-layer columns are present (points_roll3, minutes_roll3, xgi_roll3
    are required by assert_no_future_leakage). Rolling values are synthetic but
    structurally correct: NULLed out for early GWs to mimic lag-1 warm-up.

    Parameters
    ----------
    minutes_profile:
        "mixed" — players distributed across STABLE/ROTATION/FRINGE.
        "all_stable" — all players have minutes_roll5 >= 60.
        "all_fringe" — all players have minutes_roll5 < 30.
    """
    rng = np.random.default_rng(seed)
    records = []
    player_ids = list(range(1, n_players + 1))

    for pid in player_ids:
        if minutes_profile == "all_stable":
            base_minutes = 80.0
        elif minutes_profile == "all_fringe":
            base_minutes = 15.0
        else:
            # distribute: 40% STABLE, 35% ROTATION, 25% FRINGE
            base_minutes = float(rng.choice([80, 45, 15], p=[0.4, 0.35, 0.25]))

        for gw in range(1, n_gws + 1):
            minutes = float(np.clip(base_minutes + rng.normal(0, 8), 0, 90))
            xgi = float(max(0.0, rng.normal(0.3, 0.2)))
            # minutes_roll5 tracks the base profile with small noise
            minutes_roll5 = float(
                np.clip(base_minutes + rng.normal(0, 5), 0, 90)
            ) if gw > 5 else None

            records.append({
                "player_id": pid,
                "gw": gw,
                "position_label": "FWD",
                "minutes": minutes,
                "xgi": xgi,
                "total_points": float(max(0.0, rng.normal(4, 3))),
                # State-layer rolling columns (lag-1 warm-up applied below)
                "minutes_roll3": float(np.clip(base_minutes + rng.normal(0, 5), 0, 90)),
                "minutes_roll5": minutes_roll5,
                "points_roll3": float(max(0.0, rng.normal(4, 2))),
                "xgi_roll3": float(max(0.0, rng.normal(0.3, 0.1))),
                "xgi_roll5": float(max(0.0, rng.normal(0.28, 0.1))),
                "xgi_roll8": float(max(0.0, rng.normal(0.28, 0.08))),
            })

    df = pd.DataFrame(records)

    # Null out early GWs to mimic state-layer lag-1 warm-up
    df.loc[df["gw"] <= 3, ["xgi_roll3", "minutes_roll3", "points_roll3"]] = None
    df.loc[df["gw"] <= 5, ["xgi_roll5", "minutes_roll5"]] = None
    df.loc[df["gw"] <= 8, "xgi_roll8"] = None

    return df

# ---------------------------------------------------------------------------
# Cohort assignment correctness
# ---------------------------------------------------------------------------

class TestCohortAssignment:
    def test_stable_at_exactly_60(self):
        assert _assign_stability_cohort(60.0) == _COHORT_STABLE

    def test_stable_above_60(self):
        assert _assign_stability_cohort(90.0) == _COHORT_STABLE
        assert _assign_stability_cohort(60.1) == _COHORT_STABLE

    def test_rotation_at_exactly_30(self):
        assert _assign_stability_cohort(30.0) == _COHORT_ROTATION

    def test_rotation_between_30_and_60(self):
        assert _assign_stability_cohort(45.0) == _COHORT_ROTATION
        assert _assign_stability_cohort(59.9) == _COHORT_ROTATION

    def test_fringe_below_30(self):
        assert _assign_stability_cohort(0.0) == _COHORT_FRINGE
        assert _assign_stability_cohort(15.0) == _COHORT_FRINGE
        assert _assign_stability_cohort(29.9) == _COHORT_FRINGE

    def test_unknown_for_none(self):
        assert _assign_stability_cohort(None) == _COHORT_UNKNOWN

    def test_unknown_for_nan(self):
        assert _assign_stability_cohort(float("nan")) == _COHORT_UNKNOWN

    def test_deterministic_across_calls(self):
        values = [0.0, 15.0, 29.9, 30.0, 45.0, 59.9, 60.0, 75.0, 90.0, None]
        first = [_assign_stability_cohort(v) for v in values]
        second = [_assign_stability_cohort(v) for v in values]
        assert first == second

    def test_boundary_not_straddling_wrong_cohort(self):
        # 29.9 must be FRINGE, never ROTATION
        assert _assign_stability_cohort(29.9) == _COHORT_FRINGE
        # 59.9 must be ROTATION, never STABLE
        assert _assign_stability_cohort(59.9) == _COHORT_ROTATION

# ---------------------------------------------------------------------------
# Population accounting closure
# ---------------------------------------------------------------------------

class TestPopulationAccounting:
    def test_cohort_counts_sum_to_all_fwd(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        assert "detail" in results
        detail = results["detail"]
        assert not detail.empty, "detail DataFrame is empty — no evaluation GWs produced rows"

        for _, row in detail.iterrows():
            total = int(row["n_all_fwd"])
            cohort_sum = int(
                row.get("n_stable", 0)
                + row.get("n_rotation", 0)
                + row.get("n_fringe", 0)
                + row.get("n_unknown", 0)
            )
            assert cohort_sum == total, (
                f"GW {row['gw']}: cohort sum {cohort_sum} != n_all_fwd {total}"
            )

    def test_no_negative_counts(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)
        detail = results["detail"]

        count_cols = [c for c in detail.columns if c.startswith("n_")]
        for col in count_cols:
            assert (detail[col] >= 0).all(), f"Column {col} has negative values"

# ---------------------------------------------------------------------------
# Result structure completeness
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_top_level_keys_present(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        required = {
            "eval_gws", "gw_count", "cohort_gw_counts", "cohorts",
            "full_fwd", "differential", "threshold_assessment", "detail",
        }
        for key in required:
            assert key in results, f"Missing top-level key: '{key}'"

    def test_all_cohort_keys_present(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        cohorts = results["cohorts"]
        for cohort in (_COHORT_STABLE, _COHORT_ROTATION, _COHORT_FRINGE):
            assert cohort in cohorts, f"Cohort '{cohort}' missing from results['cohorts']"

    def test_threshold_assessment_keys_present(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        ta = results["threshold_assessment"]
        required = {
            "cohort_viability",
            "primary_differential",
            "horizon_stability_interaction",
            "downside_improvement",
        }
        for key in required:
            assert key in ta, f"Missing threshold key: '{key}'"

    def test_each_threshold_has_met_bool(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        for criterion, entry in results["threshold_assessment"].items():
            assert "met" in entry, f"Threshold '{criterion}' missing 'met' key"
            assert isinstance(entry["met"], bool), (
                f"Threshold '{criterion}' 'met' is not bool — got {type(entry['met'])}"
            )

    def test_differential_contains_all_signals(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        diff = results["differential"]
        for signal in ("xgi_lag1", "xgi_roll3", "xgi_roll8"):
            assert signal in diff, f"Signal '{signal}' missing from differential"
            assert "delta_stable_fringe" in diff[signal], (
                f"Signal '{signal}' missing 'delta_stable_fringe'"
            )

    def test_cohort_signal_results_have_expected_keys(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        for cohort in (_COHORT_STABLE, _COHORT_ROTATION, _COHORT_FRINGE):
            cohort_result = results["cohorts"].get(cohort, {})
            if not cohort_result:
                continue  # too few players in this cohort — acceptable
            for signal in ("xgi_lag1", "xgi_roll3", "xgi_roll8"):
                sig_result = cohort_result.get(signal, {})
                if not sig_result:
                    continue
                for key in ("label", "mean_rho", "std_rho", "n_gws", "mean_top1_return", "downside_rate"):
                    assert key in sig_result, (
                        f"Cohort '{cohort}', signal '{signal}' missing key '{key}'"
                    )

    def test_gw_count_matches_eval_gws(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        assert results["gw_count"] <= len(results["eval_gws"])

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

class TestReproducibility:
    def test_identical_output_on_two_calls(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        r1 = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)
        r2 = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        assert r1["gw_count"] == r2["gw_count"]
        assert r1["eval_gws"] == r2["eval_gws"]

        for cohort in (_COHORT_STABLE, _COHORT_ROTATION, _COHORT_FRINGE):
            for signal in ("xgi_lag1", "xgi_roll3", "xgi_roll8"):
                rho1 = r1["cohorts"].get(cohort, {}).get(signal, {}).get("mean_rho")
                rho2 = r2["cohorts"].get(cohort, {}).get(signal, {}).get("mean_rho")
                assert rho1 == rho2, f"Non-reproducible: {cohort}/{signal} mean_rho"

        for signal in ("xgi_lag1", "xgi_roll3", "xgi_roll8"):
            d1 = r1["differential"][signal]["delta_stable_fringe"]
            d2 = r2["differential"][signal]["delta_stable_fringe"]
            assert d1 == d2, f"Non-reproducible differential: {signal}"

    def test_threshold_met_flags_reproducible(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        r1 = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)
        r2 = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        for criterion in r1["threshold_assessment"]:
            assert r1["threshold_assessment"][criterion]["met"] == r2["threshold_assessment"][criterion]["met"]

# ---------------------------------------------------------------------------
# Interpretation correctness
# ---------------------------------------------------------------------------

class TestInterpretResults:
    def test_insufficient_data_on_zero_gw_count(self):
        assert interpret_results({"gw_count": 0}) == "insufficient_data"

    def test_cohort_size_failure_when_not_viable(self):
        ta = {
            "cohort_viability": {"met": False},
            "primary_differential": {"met": False},
            "horizon_stability_interaction": {"met": False},
            "downside_improvement": {"met": False},
        }
        result = interpret_results({"gw_count": 5, "threshold_assessment": ta})
        assert result == "cohort_size_failure"

    def test_no_conditioning_when_primary_not_met(self):
        ta = {
            "cohort_viability": {"met": True},
            "primary_differential": {"met": False},
            "horizon_stability_interaction": {"met": True},
            "downside_improvement": {"met": True},
        }
        result = interpret_results({"gw_count": 20, "threshold_assessment": ta})
        assert result == "stability_does_not_condition_signal"

    def test_strong_conditioning_when_all_met(self):
        ta = {
            "cohort_viability": {"met": True},
            "primary_differential": {"met": True},
            "horizon_stability_interaction": {"met": True},
            "downside_improvement": {"met": True},
        }
        result = interpret_results({"gw_count": 20, "threshold_assessment": ta})
        assert result == "stability_conditions_signal_strongly"

    def test_returns_non_empty_string_on_real_data(self):
        features = _make_fwd_features(n_players=30, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)
        interp = interpret_results(results)
        assert isinstance(interp, str)
        assert len(interp) > 0

    def test_all_interpretation_strings_are_known(self):
        known = {
            "insufficient_data",
            "cohort_size_failure",
            "stability_does_not_condition_signal",
            "stability_conditions_signal_strongly",
            "stability_conditions_downside_not_horizon",
            "stability_conditions_horizon_not_downside",
            "stability_conditions_rho_only",
        }
        # Test each threshold combination that produces a distinct path
        scenarios = [
            ({"cohort_viability": {"met": True}, "primary_differential": {"met": True},
              "horizon_stability_interaction": {"met": False}, "downside_improvement": {"met": True}},
             "stability_conditions_downside_not_horizon"),
            ({"cohort_viability": {"met": True}, "primary_differential": {"met": True},
              "horizon_stability_interaction": {"met": True}, "downside_improvement": {"met": False}},
             "stability_conditions_horizon_not_downside"),
            ({"cohort_viability": {"met": True}, "primary_differential": {"met": True},
              "horizon_stability_interaction": {"met": False}, "downside_improvement": {"met": False}},
             "stability_conditions_rho_only"),
        ]
        for ta, expected in scenarios:
            result = interpret_results({"gw_count": 20, "threshold_assessment": ta})
            assert result == expected, f"Expected '{expected}', got '{result}'"
            assert result in known, f"Unknown interpretation string: '{result}'"

# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_dataframe_returns_zero_gw_count(self):
        empty = pd.DataFrame(columns=[
            "player_id", "gw", "position_label", "minutes", "xgi", "total_points",
            "minutes_roll3", "minutes_roll5", "points_roll3",
            "xgi_roll3", "xgi_roll5", "xgi_roll8",
        ])
        results = evaluate_minutes_stability_conditioning(empty, min_gw=6, max_gw=33)
        assert results["gw_count"] == 0

    def test_non_fwd_rows_excluded(self):
        features = _make_fwd_features(n_players=20, n_gws=35, seed=42)
        # Relabel half as MID
        features.loc[features["player_id"] <= 10, "position_label"] = "MID"
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        detail = results["detail"]
        if not detail.empty:
            assert (detail["n_all_fwd"] <= 10).all(), (
                "MID rows should be excluded from n_all_fwd"
            )

    def test_all_stable_population_produces_empty_fringe(self):
        features = _make_fwd_features(n_players=20, n_gws=35, seed=42, minutes_profile="all_stable")
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        detail = results["detail"]
        if not detail.empty:
            # FRINGE count should be zero when all minutes >= 60
            assert (detail.get("n_fringe", pd.Series([0])) == 0).all()

    def test_gw_range_respected(self):
        features = _make_fwd_features(n_players=20, n_gws=35, seed=42)
        results = evaluate_minutes_stability_conditioning(features, min_gw=10, max_gw=20)

        for gw in results["eval_gws"]:
            assert 10 <= gw <= 20, f"GW {gw} is outside [10, 20] range"

    def test_differential_none_when_fringe_insufficient(self):
        # Use all_stable so FRINGE cohort is always empty → delta should be None
        features = _make_fwd_features(n_players=20, n_gws=35, seed=42, minutes_profile="all_stable")
        results = evaluate_minutes_stability_conditioning(features, min_gw=6, max_gw=33)

        diff = results["differential"]
        for signal in ("xgi_lag1", "xgi_roll3", "xgi_roll8"):
            delta = diff.get(signal, {}).get("delta_stable_fringe")
            assert delta is None, (
                f"Expected None delta for {signal} when FRINGE is empty, got {delta}"
            )
