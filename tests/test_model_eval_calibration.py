"""Tests for the Phase 4 calibration suite (model.eval.calibration)."""

from __future__ import annotations

import numpy as np
import pytest

from model.eval.calibration import (
    RETURN_THRESHOLD,
    calibration_report,
    crps_table,
    expected_calibration_error,
    recalibration_table,
    simulate_eval,
)
from tests.test_model_forecast_points_model import _panel

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
    assert (ev["crps_sim"] >= 0).all()
    assert RETURN_THRESHOLD == 6


def test_recalibration_table_shape() -> None:
    ev = simulate_eval(_panel(seed=2), n_sims=300, seed=0)
    tbl = recalibration_table(ev, "p_return", "return_")
    assert set(tbl.index) == {"raw", "isotonic", "platt"}
    assert (tbl["ece"] >= 0).all()


def test_crps_table_and_report() -> None:
    r = calibration_report(_panel(seed=3), n_sims=300, seed=0)
    assert set(r["crps"].columns) == {"crps_sim", "crps_point", "crps_pois", "crps_clim"}
    assert "haul_ece" in r and "coverage" in r and len(r["pit_deciles"]) == 10
    # the simulator distribution should beat the degenerate point forecast on CRPS (adds spread)
    crps = crps_table(simulate_eval(_panel(seed=3), n_sims=300, seed=0))
    valid = crps.dropna(subset=["crps_sim", "crps_point"])
    assert (valid["crps_sim"] <= valid["crps_point"] + 1e-9).all()
