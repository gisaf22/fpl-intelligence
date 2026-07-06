"""Tests for the point-estimate stress test (model.eval.level_estimators)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.level_estimators import (
    LEVEL_ESTIMATORS,
    _huber_loc,
    build_level_features,
    score_levels_by_position,
)

pytestmark = pytest.mark.unit


def _panel(n_players: int = 60, n_gw: int = 15, seed: int = 0) -> pd.DataFrame:
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


def test_huber_matches_mean_when_clean_and_resists_outlier() -> None:
    clean = np.array([3.0, 4.0, 5.0, 4.0, 3.0])
    assert _huber_loc(clean) == pytest.approx(np.mean(clean), abs=0.3)
    outlier = np.array([3.0, 4.0, 5.0, 4.0, 50.0])  # one haul
    # Huber sits below the (outlier-inflated) mean, nearer the bulk.
    assert _huber_loc(outlier) < np.mean(outlier)


def test_level_features_leakage_safe_on_first_appearance() -> None:
    feats = build_level_features(_panel())
    first = feats.groupby("player_id").head(1)
    assert not first[list(LEVEL_ESTIMATORS)].notna().any(axis=1).any()


def test_lvl_mean_matches_expanding_prior_mean() -> None:
    feats = build_level_features(_panel(n_players=4, n_gw=8)).sort_values(["player_id", "gw"])
    one = feats[feats.player_id == 0].reset_index(drop=True)
    # lvl_mean at row i is the mean of rows 0..i-1.
    for i in range(1, len(one)):
        assert one["lvl_mean"].iloc[i] == pytest.approx(one["total_points"].iloc[:i].mean())


def test_score_structure_and_all_estimators_present() -> None:
    res = score_levels_by_position(_panel(n_players=80, n_gw=16))
    assert res.index.names == ["position", "estimator"]
    assert list(res.columns) == ["spearman", "precision_at_k", "ndcg_at_k", "k", "n_gw"]
    assert set(res.index.get_level_values("estimator")) == set(LEVEL_ESTIMATORS.values())
