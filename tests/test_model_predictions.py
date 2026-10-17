"""Tests for the operational forecast surface (model.predictions.assemble_forecast).

The single mean+distribution join a downstream layer consumes. Structural + seed-pinned, on the shared
synthetic panel (the real mart is non-deterministic across refreshes).
"""

from __future__ import annotations

import numpy as np
import pytest

from model.compose import compose_points
from model.predictions import assemble_forecast
from tests._synthetic_mart import points_panel

pytestmark = pytest.mark.unit


def test_carries_mean_uncond_and_distribution() -> None:
    panel = points_panel(seed=0)
    fc = assemble_forecast(panel, n_sims=500, seed=0)
    # mean side (from compose) — including the ex-ante unconditional expectation value/transfers need.
    assert {"e_points", "e_points_uncond", "p_play", "base_season"} <= set(fc.columns)
    # distribution side (from simulate) — the ceiling/downside/haul the mean cannot express.
    assert {"sim_mean", "p10", "p50", "p90", "p_haul"} <= set(fc.columns)
    # one row per composed player-GW; the join does not multiply rows.
    assert len(fc) == len(compose_points(panel, keep_all=True))
    assert not fc[["player_id", "gw"]].duplicated().any()


def test_unconditional_is_bounded_and_distribution_ordered() -> None:
    fc = assemble_forecast(points_panel(seed=1), n_sims=500, seed=0)
    scored = fc.dropna(subset=["p90", "p_play"])
    # E[pts]_uncond = P(play) x E[pts | played] <= E[pts | played], and P(play), p_haul are probabilities.
    assert (scored["e_points_uncond"] <= scored["e_points"] + 1e-9).all()
    assert scored["p_play"].between(0, 1).all()
    assert scored["p_haul"].between(0, 1).all()
    # percentiles are ordered.
    assert (scored["p10"] <= scored["p50"] + 1e-9).all()
    assert (scored["p50"] <= scored["p90"] + 1e-9).all()


def test_seed_pinned_reproducible() -> None:
    panel = points_panel(seed=0)
    a = assemble_forecast(panel, n_sims=500, seed=0)
    b = assemble_forecast(panel, n_sims=500, seed=0)
    # e_points is deterministic; the seed-pinned MC reproduces p90/p_haul exactly.
    for col in ("e_points", "p90", "p_haul"):
        np.testing.assert_array_equal(a[col].to_numpy(), b[col].to_numpy())
