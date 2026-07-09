"""Tests for the Phase 5 decision evaluation - captaincy backtest (model.eval.decisions)."""

from __future__ import annotations

import numpy as np
import pytest

from model.eval.decisions import (
    _STRATEGIES,
    _block_bootstrap_ci,
    build_captaincy_panel,
    captaincy_backtest,
)
from tests.test_model_forecast_points_model import _panel

pytestmark = pytest.mark.unit


def _capt_panel(seed: int = 1):
    # add ownership (varying) so the template strategy has a signal to rank on
    return _panel(seed=seed).assign(ownership_count=lambda d: 1_000_000 - d["player_id"] * 1000)


def test_block_bootstrap_ci_brackets_constant() -> None:
    lo, hi = _block_bootstrap_ci(np.full(20, 5.0))
    assert lo == hi == 5.0                              # a constant series has a degenerate CI
    lo2, hi2 = _block_bootstrap_ci(np.arange(20.0))
    assert lo2 <= np.arange(20.0).mean() <= hi2         # CI brackets the mean


def test_build_captaincy_panel_has_pplay_and_multiplier() -> None:
    df = build_captaincy_panel(_capt_panel(seed=1), n_sims=200, seed=0)
    fit = df.dropna(subset=["p_play"])
    assert fit["p_play"].between(0, 1).all()
    prod = df.dropna(subset=["full_pts", "p_play"])
    assert np.allclose(prod["model_pplay"], prod["full_pts"] * prod["p_play"])


def test_captaincy_backtest_shape_and_bounds() -> None:
    tbl = captaincy_backtest(_capt_panel(seed=2), pool="free", n_sims=200, seed=0)
    assert set(tbl.index) == set(_STRATEGIES)
    assert tbl["winrate_vs_template"].between(0, 1).all()
    assert tbl.attrs["n_gw"] > 0 and tbl.attrs["oracle_mean"] > 0
    # core strategies are always defined (model_mean_x_pplay needs blanks to fit P(play) -> may be NaN)
    scored = tbl.dropna(subset=["mean_pts_gw"])
    assert {"template", "base_season", "model_mean", "ceiling_p90"} <= set(scored.index)
    assert (scored["regret"] >= -1e-9).all()            # no strategy beats the oracle
    assert (scored["ci_lo"] <= scored["mean_pts_gw"] + 1e-9).all()
    assert (scored["ci_hi"] >= scored["mean_pts_gw"] - 1e-9).all()


def test_ownership_pool_runs() -> None:
    tbl = captaincy_backtest(_capt_panel(seed=3), pool="ownership", n_top=10, n_sims=200, seed=0)
    assert set(tbl.index) == set(_STRATEGIES)
    assert tbl.loc["template", "mean_pts_gw"] > 0       # core strategies produce picks
