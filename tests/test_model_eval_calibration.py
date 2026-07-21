"""Tests for the Phase 4 calibration suite (model.eval.calibration)."""

from __future__ import annotations

import numpy as np
import pytest

from model.eval.calibration import (
    COVERAGE_ALPHA,
    RETURN_THRESHOLD,
    calibration_report,
    crps_table,
    event_counts,
    expected_calibration_error,
    recalibration_table,
    simulate_eval,
)
from model.eval.walkforward import POSITIONS
from tests._synthetic_mart import points_panel as _panel

pytestmark = pytest.mark.unit


def test_ece_zero_for_perfect_calibration() -> None:
    rng = np.random.default_rng(0)
    prob = rng.uniform(0, 1, 5000)
    event = (rng.uniform(0, 1, 5000) < prob).astype(int)   # events occur at exactly the stated prob
    assert expected_calibration_error(prob, event) < 0.03
    # a constant wrong probability is clearly miscalibrated
    assert expected_calibration_error(np.full(5000, 0.9), np.zeros(5000)) > 0.5


def test_simulate_eval_columns_and_bounds() -> None:
    ev = simulate_eval(_panel(seed=1), n_sims=300, seed=0)
    assert not ev.empty
    assert ev["pit"].between(0, 1).all()
    assert ev["p_haul"].between(0, 1).all()
    assert set(ev["cover"].unique()) <= {0, 1}
    assert set(ev["cover_pit"].unique()) <= {0, 1}
    assert (ev["crps_sim"] >= 0).all()
    assert RETURN_THRESHOLD == 6


def test_cover_pit_is_a_pure_function_of_pit() -> None:
    """`cover_pit` must add NO randomness of its own (coverage-metric slice, Fork B): it is exactly
    the indicator that the already-drawn randomized PIT lies in the central 80%."""
    ev = simulate_eval(_panel(seed=1), n_sims=300, seed=0)
    expected = ((ev["pit"] >= COVERAGE_ALPHA) & (ev["pit"] <= 1 - COVERAGE_ALPHA)).astype(int)
    assert (ev["cover_pit"] == expected).all()


def test_cover_pit_is_discreteness_correct_on_an_atomic_distribution() -> None:
    """The property that motivates the slice: on a lumpy distribution the `[p10,p90]` rule mis-measures
    an 80% interval, while the randomized-PIT rule hits 80% on the nose.

    Ground truth: draws and realizations from the SAME heavily-atomic law, so a correct 80% coverage
    metric must return ~0.80. `np.percentile` lands inside an atom and cannot.
    """
    rng = np.random.default_rng(0)
    n, n_sims = 4000, 2000
    # ~60% of the mass sits on the single value 1 — the FPL "played, returned nothing" atom.
    draws = np.where(rng.random((n, n_sims)) < 0.6, 1.0, rng.poisson(4.0, size=(n, n_sims)) + 1.0)
    y = np.where(rng.random(n) < 0.6, 1.0, rng.poisson(4.0, size=n) + 1.0)

    p10, p90 = np.percentile(draws, [10, 90], axis=1)
    cover_interval = ((p10 <= y) & (y <= p90)).mean()

    below = (draws < y[:, None]).mean(axis=1)
    eq = (draws == y[:, None]).mean(axis=1)
    pit = below + rng.random(n) * eq
    cover_pit = ((pit >= COVERAGE_ALPHA) & (pit <= 1 - COVERAGE_ALPHA)).mean()

    assert abs(cover_pit - 0.80) < 0.02, f"PIT coverage should be ~0.80, got {cover_pit:.3f}"
    assert abs(cover_interval - 0.80) > 0.05, (
        f"the [p10,p90] rule should visibly mis-measure on an atomic law, got {cover_interval:.3f}")


def test_recalibration_table_shape() -> None:
    ev = simulate_eval(_panel(seed=2), n_sims=300, seed=0)
    tbl = recalibration_table(ev, "p_return", "return_")
    assert set(tbl.index) == {"raw", "isotonic", "platt"}
    assert (tbl["ece"] >= 0).all()


def test_calibration_report_seed_pinned_regression() -> None:
    """Repro gate (Phase-4 step 3): fixed panel + seed -> the numpy/scipy metrics reproduce to the
    report's rounding. The sklearn-recalibrated ECE is checked under a **tolerance**, not bit-frozen —
    isotonic/Platt output can legitimately drift across library versions (Fork C)."""
    rep = calibration_report(_panel(seed=0), n_sims=2000, seed=0)
    assert rep["n"] == 1260
    assert rep["pit_mean"] == 0.527
    np.testing.assert_array_almost_equal(
        rep["pit_deciles"],
        [0.059, 0.072, 0.093, 0.112, 0.126, 0.141, 0.115, 0.084, 0.085, 0.113], decimal=6)
    # `cover` is the operational [p10,p90] hit rate; `cover_pit` is the discreteness-correct gate.
    # Both re-frozen in the position-intercept slice: the goals term changed, so the drawn
    # distributions moved (the earlier re-freeze was metric-only and left `cover` untouched).
    cover = {"GK": 0.869, "DEF": 0.885, "MID": 0.65, "FWD": 0.875}
    cover_pit = {"GK": 0.869, "DEF": 0.883, "MID": 0.65, "FWD": 0.846}
    crps = {"GK": 1.771, "DEF": 1.557, "MID": 1.616, "FWD": 1.348}
    for p in POSITIONS:
        np.testing.assert_almost_equal(float(rep["coverage"][p]), cover[p], decimal=6)
        np.testing.assert_almost_equal(float(rep["coverage_pit"][p]), cover_pit[p], decimal=6)
        np.testing.assert_almost_equal(float(rep["crps"].loc[p, "crps_sim"]), crps[p], decimal=6)
    # the band is pre-registered and unmoved; it now gates on the discreteness-correct number.
    assert rep["coverage_in_band"] == {p: bool(0.75 <= cover_pit[p] <= 0.85) for p in POSITIONS}
    np.testing.assert_almost_equal(float(rep["haul_ece"].loc["raw", "ece"]), 0.0241, decimal=6)
    np.testing.assert_almost_equal(float(rep["return_ece"].loc["raw", "ece"]), 0.0702, decimal=6)
    # power surface: per-position event counts reproduce exactly.
    got_events = {p: (int(rep["events"].loc[p, "n"]), int(rep["events"].loc[p, "n_haul"]),
                      int(rep["events"].loc[p, "n_return"])) for p in POSITIONS}
    assert got_events == {"GK": (260, 19, 95), "DEF": (520, 21, 190),
                          "MID": (240, 11, 71), "FWD": (240, 13, 65)}
    # sklearn recalibration (tolerance, not frozen): a walk-forward recal must not WORSEN the raw haul ECE.
    raw = float(rep["haul_ece"].loc["raw", "ece"])
    for method in ("isotonic", "platt"):
        assert float(rep["haul_ece"].loc[method, "ece"]) <= raw + 0.01


def test_event_counts_power_surface() -> None:
    ev = simulate_eval(_panel(seed=1), n_sims=300, seed=0)
    counts = event_counts(ev)
    assert list(counts.index) == list(POSITIONS)
    assert set(counts.columns) == {"n", "n_haul", "n_return"}
    assert (counts["n"] >= counts["n_return"]).all() and (counts["n_return"] >= counts["n_haul"]).all()


def test_crps_table_and_report() -> None:
    r = calibration_report(_panel(seed=3), n_sims=300, seed=0)
    assert set(r["crps"].columns) == {"crps_sim", "crps_point", "crps_pois", "crps_clim"}
    assert "haul_ece" in r and "coverage" in r and len(r["pit_deciles"]) == 10
    # the simulator distribution should beat the degenerate point forecast on CRPS (adds spread)
    crps = crps_table(simulate_eval(_panel(seed=3), n_sims=300, seed=0))
    valid = crps.dropna(subset=["crps_sim", "crps_point"])
    assert (valid["crps_sim"] <= valid["crps_point"] + 1e-9).all()
