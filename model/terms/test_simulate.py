"""Tests for model.simulate — the Monte-Carlo points distribution over the term registry.

This is a STOCHASTIC step, so there is no bit-identical god-file golden (a Monte-Carlo mean cannot equal
an analytic reference to the bit). The reproducibility gate is instead a **seed-pinned regression vector**
(fixed seed -> summaries reproduce to 4dp) plus a **tolerance consistency check** that ``sim_mean`` tracks
compose ``e_points`` on non-GK rows. See docs/model-redesign-simulate-slice.md (Fork B).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.compose import compose_parameters
from model.simulate import (
    _SUMMARY_COLUMNS,
    _draw_team_ga,
    iter_sample_blocks,
    simulate_from_mart,
    simulate_points,
    simulator_consistency,
)
from model.terms.test_compose import _mart

pytestmark = pytest.mark.unit


def test_summary_contract() -> None:
    sim = simulate_points(compose_parameters(_mart()), n_sims=1000, seed=0)
    assert list(sim.columns) == _SUMMARY_COLUMNS
    assert (sim["p10"] <= sim["p50"]).all() and (sim["p50"] <= sim["p90"]).all()
    assert sim["p_haul"].between(0.0, 1.0).all()


def test_seed_pinned_regression_vector() -> None:
    """Fixed seed -> a frozen row reproduces to 4dp (the repro gate for stochastic code, Fork B.1)."""
    sim = simulate_points(compose_parameters(_mart(seed=0)), n_sims=3000, seed=7)
    row = sim.sort_values(["player_id", "gw"]).iloc[100]
    assert (int(row["player_id"]), int(row["gw"]), row["position"]) == (8, 9, "FWD")
    frozen = {"sim_mean": 3.8376, "sim_sd": 2.6993, "p10": 1.1975,
              "p50": 2.1975, "p90": 6.8481, "p_haul": 0.0413}
    for col, want in frozen.items():
        assert round(float(row[col]), 4) == want, f"{col}: {row[col]!r} != {want}"


def test_iter_sample_blocks_covers_scored_rows_and_matches_simulate_points() -> None:
    """The shared draw primitive yields the same scored rows simulate_points reduces, in order, with an
    (n_rows, n_sims) draw matrix per block — and simulate_points is a pure reduction over it."""
    params = compose_parameters(_mart(seed=0))
    blocks = list(iter_sample_blocks(params, n_sims=500, seed=7, batch_rows=128))
    assert blocks and all(d.shape == (len(b), 500) for b, d in blocks)
    # concatenated block keys == simulate_points output keys, same order (a pure reduction).
    keys = pd.concat([b[["player_id", "gw"]] for b, _ in blocks], ignore_index=True)
    sim = simulate_points(params, n_sims=500, seed=7, batch_rows=128)
    np.testing.assert_array_equal(keys.to_numpy(), sim[["player_id", "gw"]].to_numpy())
    # per-block mean equals simulate_points' sim_mean (same rng stream, no double-draw).
    means = np.concatenate([d.mean(axis=1) for _, d in blocks])
    np.testing.assert_array_almost_equal(means, sim["sim_mean"].to_numpy(), decimal=12)


def test_empty_params_yields_no_blocks() -> None:
    empty = compose_parameters(_mart()).iloc[:0]
    assert list(iter_sample_blocks(empty, n_sims=10, seed=0)) == []
    assert simulate_points(empty, n_sims=10, seed=0).empty


def test_determinism_same_seed() -> None:
    params = compose_parameters(_mart())
    a = simulate_points(params, n_sims=1500, seed=3)
    b = simulate_points(params, n_sims=1500, seed=3)
    np.testing.assert_array_equal(a["sim_mean"].to_numpy(), b["sim_mean"].to_numpy())


def test_consistency_with_compose_non_gk() -> None:
    """sim_mean tracks compose e_points on non-GK rows within tolerance (Fork B.2)."""
    c = simulator_consistency(_mart(), n_sims=4000, seed=0)
    assert c["corr"] > 0.98
    assert c["mean_abs_diff"] < 0.25
    assert c["n"] > 0


def test_team_ga_drawn_once_per_team_fixture() -> None:
    """Rows sharing (team_id, gw) map to one shared GA draw (D-D co-movement)."""
    params = compose_parameters(_mart())
    df = params[params["gw"] > 4].dropna(subset=["p_cs"]).reset_index(drop=True)
    rng = np.random.default_rng(0)
    tf_index, ga_by_tf = _draw_team_ga(df, n_sims=50, rng=rng)
    key = df["team_id"].astype(str) + "_" + df["gw"].astype(str)
    # every row of a team-fixture indexes the same GA vector
    assert len(np.unique(tf_index)) == key.nunique()
    assert ga_by_tf.shape[0] == key.nunique()


def test_warmup_rows_absent() -> None:
    from model.eval.walkforward import WARMUP_GW
    sim = simulate_points(compose_parameters(_mart()), n_sims=500, seed=0)
    assert (sim["gw"] > WARMUP_GW).all()


def test_dgw_rows_absent() -> None:
    """compose drops is_dgw rows, so the simulator never scores a double-gameweek fixture (Fork D)."""
    mart = _mart()
    dgw = mart[(mart["gw"] == 10)].copy()
    dgw["is_dgw"] = True
    dgw["gw"] = 10  # a flagged double fixture
    marked = pd.concat([mart[mart["gw"] != 10], dgw], ignore_index=True)
    sim = simulate_from_mart(marked, n_sims=300, seed=0)
    assert (sim["gw"] != 10).all()
