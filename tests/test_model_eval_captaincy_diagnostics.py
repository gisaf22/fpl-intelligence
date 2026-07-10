"""Tests for the Door-1 captaincy diagnostic (model.eval.captaincy_diagnostics)."""

from __future__ import annotations

import pytest

from model.eval.captaincy_diagnostics import (
    build_diagnostic_pool,
    divergence_winrate,
    oracle_discrimination,
    oracle_rank_hits,
    reducible_regret,
)
from tests.test_model_eval_decisions import _capt_panel

pytestmark = pytest.mark.unit


def test_pool_has_one_oracle_per_gw() -> None:
    pool = build_diagnostic_pool(_capt_panel(seed=1), n_sims=200, seed=0)
    assert (pool.groupby("gw")["is_oracle"].sum() == 1).all()      # exactly one oracle per GW
    assert set(pool["is_oracle"].unique()) <= {0, 1}


def test_reducible_regret_nonnegative_with_concentration_attrs() -> None:
    pool = build_diagnostic_pool(_capt_panel(seed=2), n_sims=200, seed=0)
    reg = reducible_regret(pool)
    assert (reg["oracle"] >= reg["base"] - 1e-9).all()             # oracle is the best possible
    assert (reg["reducible"] >= -1e-9).all()
    assert "top20_share" in reg.attrs and "gini" in reg.attrs


def test_oracle_rank_hits_bounds() -> None:
    pool = build_diagnostic_pool(_capt_panel(seed=3), n_sims=200, seed=0)
    hits = oracle_rank_hits(pool)
    assert hits[["hit_at_1", "hit_at_3"]].apply(lambda s: s.between(0, 1)).all().all()
    assert (hits["hit_at_3"] >= hits["hit_at_1"] - 1e-9).all()     # top-3 hit >= top-1 hit


def test_divergence_and_discrimination_shapes() -> None:
    pool = build_diagnostic_pool(_capt_panel(seed=4), n_sims=200, seed=0)
    div = divergence_winrate(pool)
    assert {"n_divergent", "winrate", "winrate_ci", "mean_pts_diff"} <= set(div)
    disc = oracle_discrimination(pool, n_null=50, seed=0)
    assert 0 <= disc["combined_logo_auc"] <= 1
    assert 0 <= disc["min_detectable_auc"] <= 1
    assert isinstance(disc["signal_detected"], bool)
    assert all(0 <= v <= 1 for v in disc["single_auc"].values())
