"""Tests for the empirical-Bayes shrinkage ranker (model.eval.shrinkage) — Phase 1 D2."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.shrinkage import (
    SHRINK_ESTIMATORS,
    _variance_ratio_mom,
    build_shrunk_features,
    score_shrinkage_by_position,
)

pytestmark = pytest.mark.unit


def _panel(n_players: int = 60, n_gw: int = 16, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        skill = rng.uniform(2, 8)
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": ["GK", "DEF", "MID", "FWD"][p % 4],
                "minutes": 90, "is_dgw": False, "total_points": max(0.0, skill + rng.normal(0, 1.5)),
            })
    return pd.DataFrame(rows)


def test_shrunk_features_leakage_safe_on_first_appearance() -> None:
    feats = build_shrunk_features(_panel())
    first = feats.groupby("player_id").head(1)
    assert not first[list(SHRINK_ESTIMATORS)].notna().any(axis=1).any()


def test_shrunk_pulls_toward_position_mean_for_few_games() -> None:
    # A player's earliest post-warmup shrunk estimate sits strictly between his own
    # prior mean and the position mean (proper partial pooling).
    feats = build_shrunk_features(_panel())
    defined = feats[feats[["lvl_shrunk", "lvl_mean", "mu_pos"]].notna().all(axis=1)]
    early = defined.sort_values("prior_n").iloc[0]
    lo, hi = sorted([early["lvl_mean"], early["mu_pos"]])
    assert lo - 1e-9 <= early["lvl_shrunk"] <= hi + 1e-9


def test_lambda_grows_with_history() -> None:
    # More prior games ⇒ lvl_shrunk closer to lvl_mean than to mu_pos.
    feats = build_shrunk_features(_panel())
    d = feats[feats[["lvl_shrunk", "lvl_mean", "mu_pos"]].notna().all(axis=1)].copy()
    d["closeness"] = 1 - (d["lvl_shrunk"] - d["lvl_mean"]).abs() / (
        (d["mu_pos"] - d["lvl_mean"]).abs() + 1e-9
    )
    corr = d[["prior_n", "closeness"]].corr().iloc[0, 1]
    assert corr > 0.3


def test_variance_ratio_infinite_when_no_between_signal() -> None:
    # All players identical level ⇒ no between-variance ⇒ ratio inf ⇒ full shrink.
    rng = np.random.default_rng(1)
    rows = [
        {"player_id": p, "total_points": 5.0 + rng.normal(0, 2.0)}
        for p in range(20) for _ in range(10)
    ]
    prior = pd.DataFrame(rows)
    assert np.isinf(_variance_ratio_mom(prior, "total_points", "player_id"))


def test_score_structure() -> None:
    res = score_shrinkage_by_position(_panel(n_players=80, n_gw=18))
    assert res.index.names == ["position", "estimator"]
    assert set(res.index.get_level_values("estimator")) == set(SHRINK_ESTIMATORS.values())
