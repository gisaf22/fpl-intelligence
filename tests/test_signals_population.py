"""Unit tests for population validity utilities."""

import numpy as np
import pandas as pd
import pytest

from studies.eda.population import (
    MIN_N_FOR_RHO,
    POPULATION_ROBUSTNESS_VALUES,
    RHO_SHIFT_STABLE_THRESHOLD,
    classify_population_robustness,
    compute_dual_scope_rho,
)

pytestmark = pytest.mark.unit

# --- vocabulary ---

def test_population_robustness_values_are_complete():
    assert POPULATION_ROBUSTNESS_VALUES == {"stable", "scope_sensitive", "untested"}

# --- classify_population_robustness ---

def test_stable_when_shift_below_threshold_and_same_geometry():
    result = classify_population_robustness(
        rho_filtered=0.50,
        rho_minimal=0.45,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "stable"

def test_stable_at_shift_just_below_threshold():
    shift = RHO_SHIFT_STABLE_THRESHOLD - 0.001
    result = classify_population_robustness(
        rho_filtered=0.50,
        rho_minimal=0.50 - shift,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "stable"

def test_scope_sensitive_at_shift_above_threshold():
    # Use 0.50 and 0.39 for a shift of 0.11, clearly above the 0.10 boundary.
    result = classify_population_robustness(
        rho_filtered=0.50,
        rho_minimal=0.39,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "scope_sensitive"

def test_scope_sensitive_when_geometry_changes_even_with_small_rho_shift():
    result = classify_population_robustness(
        rho_filtered=0.50,
        rho_minimal=0.49,
        geometry_filtered="monotonic_positive",
        geometry_minimal="threshold_positive",
    )
    assert result == "scope_sensitive"

def test_scope_sensitive_when_shift_exceeds_threshold():
    result = classify_population_robustness(
        rho_filtered=0.50,
        rho_minimal=0.25,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "scope_sensitive"

def test_scope_sensitive_when_shift_exceeds_025():
    # Large shifts (>0.25) still return scope_sensitive — no unstable tier in schema.
    result = classify_population_robustness(
        rho_filtered=0.80,
        rho_minimal=0.40,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "scope_sensitive"

def test_untested_when_rho_filtered_is_none():
    result = classify_population_robustness(
        rho_filtered=None,
        rho_minimal=0.45,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "untested"

def test_untested_when_rho_minimal_is_none():
    result = classify_population_robustness(
        rho_filtered=0.50,
        rho_minimal=None,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "untested"

def test_untested_when_rho_filtered_is_nan():
    result = classify_population_robustness(
        rho_filtered=float("nan"),
        rho_minimal=0.45,
        geometry_filtered="monotonic_positive",
        geometry_minimal="monotonic_positive",
    )
    assert result == "untested"

def test_untested_when_both_rho_are_none():
    result = classify_population_robustness(
        rho_filtered=None,
        rho_minimal=None,
        geometry_filtered="indeterminate",
        geometry_minimal="indeterminate",
    )
    assert result == "untested"

def test_output_is_always_governed_vocabulary():
    cases = [
        (0.50, 0.45, "monotonic_positive", "monotonic_positive"),
        (0.50, 0.35, "monotonic_positive", "monotonic_positive"),
        (None, 0.45, "monotonic_positive", "monotonic_positive"),
        (float("nan"), 0.45, "monotonic_positive", "monotonic_positive"),
    ]
    for rho_f, rho_m, g_f, g_m in cases:
        result = classify_population_robustness(rho_f, rho_m, g_f, g_m)
        assert result in POPULATION_ROBUSTNESS_VALUES

# --- compute_dual_scope_rho ---

def _make_df(n_filtered: int = 100, n_extra: int = 50, seed: int = 42) -> pd.DataFrame:
    """Synthetic dataset with two populations: filtered (minutes>=60) and minimal (minutes>0)."""
    rng = np.random.default_rng(seed)
    signal = rng.normal(5, 2, n_filtered + n_extra)
    target = signal * 0.5 + rng.normal(0, 1, n_filtered + n_extra)
    minutes = np.concatenate([
        np.full(n_filtered, 90),   # filtered population
        np.full(n_extra, 30),      # minimal-only population
    ])
    return pd.DataFrame({
        "position": ["MID"] * (n_filtered + n_extra),
        "signal_a": signal,
        "total_points": target,
        "minutes": minutes,
    })

def test_compute_dual_scope_rho_returns_one_row_per_signal_position():
    df = _make_df()
    result = compute_dual_scope_rho(df, signals=["signal_a"], positions=["MID"])
    assert len(result) == 1
    assert result.iloc[0]["signal"] == "signal_a"
    assert result.iloc[0]["position"] == "MID"

def test_compute_dual_scope_rho_columns_present():
    df = _make_df()
    result = compute_dual_scope_rho(df, signals=["signal_a"], positions=["MID"])
    expected_cols = {"signal", "position", "n_filtered", "n_minimal", "rho_filtered", "rho_minimal", "rho_shift"}
    assert expected_cols.issubset(result.columns)

def test_compute_dual_scope_rho_n_filtered_less_than_n_minimal():
    df = _make_df(n_filtered=100, n_extra=50)
    result = compute_dual_scope_rho(df, signals=["signal_a"], positions=["MID"])
    row = result.iloc[0]
    assert row["n_filtered"] == 100
    assert row["n_minimal"] == 150

def test_compute_dual_scope_rho_rho_shift_is_abs_difference():
    df = _make_df()
    result = compute_dual_scope_rho(df, signals=["signal_a"], positions=["MID"])
    row = result.iloc[0]
    if row["rho_filtered"] is not None and row["rho_minimal"] is not None:
        expected_shift = round(abs(row["rho_filtered"] - row["rho_minimal"]), 4)
        assert abs(row["rho_shift"] - expected_shift) < 1e-6

def test_compute_dual_scope_rho_returns_none_when_insufficient_n():
    rng = np.random.default_rng(0)
    # Only 20 rows in filtered population — below MIN_N_FOR_RHO
    df = pd.DataFrame({
        "position": ["GK"] * (MIN_N_FOR_RHO - 10),
        "signal_a": rng.normal(0, 1, MIN_N_FOR_RHO - 10),
        "total_points": rng.normal(0, 1, MIN_N_FOR_RHO - 10),
        "minutes": np.full(MIN_N_FOR_RHO - 10, 90),
    })
    result = compute_dual_scope_rho(df, signals=["signal_a"], positions=["GK"])
    assert result.iloc[0]["rho_filtered"] is None

def test_compute_dual_scope_rho_skips_missing_signal_column():
    df = _make_df()
    result = compute_dual_scope_rho(df, signals=["signal_a", "not_in_df"], positions=["MID"])
    assert len(result) == 1
    assert "not_in_df" not in result["signal"].values

def test_compute_dual_scope_rho_raises_on_missing_required_columns():
    df = pd.DataFrame({"signal_a": [1, 2, 3]})
    with pytest.raises(ValueError, match="missing required columns"):
        compute_dual_scope_rho(df, signals=["signal_a"], positions=["MID"])
