"""Tests for the Phase 3.1 Monte-Carlo simulator (model.forecast.simulator)."""

from __future__ import annotations

import numpy as np
import pytest

from model.forecast.points_model import walk_forward_points
from model.forecast.simulator import (
    HAUL_THRESHOLD,
    _draw_team_ga,
    simulate_points,
)
from tests.test_model_forecast_points_model import _panel

pytestmark = pytest.mark.unit


def test_simulate_shape_and_bounds() -> None:
    sim = simulate_points(walk_forward_points(_panel(seed=1)), n_sims=500, seed=0)
    assert not sim.empty
    for c in ["sim_mean", "sim_sd", "p10", "p50", "p90", "p_haul"]:
        assert c in sim.columns
    assert sim["p_haul"].between(0, 1).all()
    assert (sim["p90"] >= sim["p10"] - 1e-9).all()          # quantiles ordered
    assert np.isfinite(sim["sim_mean"]).all()


def test_reproducible_under_seed() -> None:
    points = walk_forward_points(_panel(seed=2))
    a = simulate_points(points, n_sims=500, seed=7)
    b = simulate_points(points, n_sims=500, seed=7)
    assert np.allclose(a["sim_mean"], b["sim_mean"])
    assert np.allclose(a["p_haul"], b["p_haul"])


def test_team_ga_drawn_once_per_team_fixture() -> None:
    # the shared team-GA draw is (n_team_fixtures, n_sims); rows of the same team-fixture map to it
    points = walk_forward_points(_panel(seed=3)).dropna(subset=["p_cs"]).reset_index(drop=True)
    rng = np.random.default_rng(0)
    tf_index, ga_by_tf = _draw_team_ga(points, 200, rng)
    assert ga_by_tf.shape[1] == 200
    assert tf_index.max() + 1 == ga_by_tf.shape[0]
    # every row maps to a valid team-fixture row of the shared draw
    assert tf_index.min() >= 0 and tf_index.max() < ga_by_tf.shape[0]


def test_sim_mean_tracks_analytic_full_pts() -> None:
    # internal consistency: the sim mean reproduces the composition's mean (not a predictive claim)
    sim = simulate_points(walk_forward_points(_panel(seed=4)), n_sims=3000, seed=0)
    sim = sim.dropna(subset=["full_pts", "sim_mean"])
    assert np.corrcoef(sim["sim_mean"], sim["full_pts"])[0, 1] > 0.95


def test_haul_probability_is_sane() -> None:
    sim = simulate_points(walk_forward_points(_panel(seed=5)), n_sims=1000, seed=0)
    # haul prob is small and bounded; p90 never below the median
    assert (sim["p_haul"] <= 1).all()
    assert (sim["p90"] >= sim["p50"] - 1e-9).all()
    assert HAUL_THRESHOLD == 10
