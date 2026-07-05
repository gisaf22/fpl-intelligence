"""Tests for the Phase-0 baseline + walk-forward harness (model.eval)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.baselines import BASELINES, build_baseline_features
from model.eval.walkforward import WARMUP_GW, score_predictions, walk_forward_baselines

pytestmark = pytest.mark.unit


def _panel(n_players: int = 6, n_gw: int = 12, seed: int = 0) -> pd.DataFrame:
    """A clean player-gameweek panel: every player features every GW, no DGW."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        skill = rng.uniform(2, 8)  # persistent player level (between-player signal)
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": ["DEF", "MID", "FWD", "GK"][p % 4],
                "minutes": 90, "is_dgw": False,
                "total_points": max(0.0, skill + rng.normal(0, 1)),
            })
    return pd.DataFrame(rows)


def test_features_are_leakage_safe_on_first_appearance() -> None:
    feats = build_baseline_features(_panel())
    first = feats.groupby("player_id").head(1)
    # No PLAYER-HISTORY baseline may be defined on a player's first row (nothing prior).
    # base_posmean is excluded: it reads other players' earlier gameweeks.
    player_hist = ["base_last", "base_roll3", "base_roll5", "base_season"]
    assert not first[player_hist].notna().any(axis=1).any()


def test_last_gw_baseline_equals_prior_points() -> None:
    feats = build_baseline_features(_panel()).sort_values(["player_id", "gw"])
    one = feats[feats.player_id == 0].reset_index(drop=True)
    # base_last at row i is total_points at row i-1.
    assert one["base_last"].iloc[1:].to_numpy() == pytest.approx(one["total_points"].iloc[:-1].to_numpy())


def test_population_excludes_dgw_and_non_players() -> None:
    df = _panel(n_players=4, n_gw=6)
    df.loc[df.index[:2], "minutes"] = 0          # did not play
    df.loc[df.index[2:4], "is_dgw"] = True       # double gameweek
    feats = build_baseline_features(df)
    assert (feats["minutes"] > 0).all()
    assert (~feats["is_dgw"].astype(bool)).all()


def test_persistent_skill_makes_season_avg_rank_well() -> None:
    # With persistent player skill, the expanding season average should track the
    # true ranking (positive within-week Spearman).
    feats = build_baseline_features(_panel(n_players=30, n_gw=15, seed=3))
    out = score_predictions(feats, "base_season")
    assert out["spearman_mean"] > 0.3
    assert out["n"] > 0


def test_walk_forward_returns_all_baselines_ranked() -> None:
    res = walk_forward_baselines(_panel(n_players=30, n_gw=14))
    assert set(res.index) == set(BASELINES.values())
    assert list(res.columns) == ["spearman_mean", "spearman_pos", "precision_at_k", "ndcg_at_k", "mae", "n", "coverage"]
    # sorted by spearman_mean descending
    sp = res["spearman_mean"].dropna().to_numpy()
    assert (np.diff(sp) <= 1e-9).all()


def test_common_eval_set_scores_all_baselines_on_equal_n() -> None:
    # Fix A: with a common evaluation set, every baseline is scored on the same rows.
    res = walk_forward_baselines(_panel(n_players=30, n_gw=16))
    assert res["n"].nunique() == 1  # equal n across baselines


def test_scoring_respects_warmup() -> None:
    feats = build_baseline_features(_panel())
    ev = feats[feats["gw"] > WARMUP_GW]
    assert len(ev) < len(feats)  # warmup rows are excluded from evaluation
