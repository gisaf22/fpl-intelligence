"""Tests for the Phase 2.2 regularized signal combination (model.forecast.signal_combination)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from model.forecast.signal_combination import (
    _GOAL_FEATURES,
    _L1_WT_DEFAULT,
    ALPHA_GRID,
    L1_WT_GRID,
    _add_lagged_process,
    _select_penalty,
    _standardize,
    gradient_boosting_ceiling,
    selection_stability,
    walk_forward_signal_combination,
)

pytestmark = pytest.mark.unit


def _panel(n_players: int = 160, n_gw: int = 16, seed: int = 0) -> pd.DataFrame:
    """Synthetic player-GW panel where goals track a lagged xG signal (so features should rank)."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        skill = rng.uniform(0.02, 0.5)
        for gw in range(1, n_gw + 1):
            goals = rng.poisson(skill)
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xg": skill + rng.normal(0, 0.05), "xa": 0.1 + rng.normal(0, 0.03),
                "xgi_roll3": skill + rng.normal(0, 0.05), "xgi_roll5": skill + rng.normal(0, 0.05),
                "minutes_roll3": 90.0, "minutes_roll8": 88.0, "minutes_trend": 0.0,
                "goals_conceded_roll3": rng.uniform(0, 2), "goals_conceded_roll5": rng.uniform(0, 2),
                "xgc_roll3": rng.uniform(0, 2), "xgc_roll5": rng.uniform(0, 2),
                "clean_sheets_roll3": rng.uniform(0, 1), "clean_sheets_roll5": rng.uniform(0, 1),
                "transfers_in": rng.uniform(0, 1e5), "ownership_count": rng.uniform(0, 1e6),
                "purchase_price": rng.uniform(40, 130), "fdr_avg": rng.uniform(2, 4),
                "goals_scored": goals, "assists": rng.poisson(0.1),
                "clean_sheets": int(rng.random() < 0.3), "saves": rng.poisson(1.5),
                "was_home": int(rng.random() < 0.5), "total_points": 2 + goals * 5 + rng.normal(0, 1),
            })
    return pd.DataFrame(rows)


def test_returns_three_bars_per_position() -> None:
    res = walk_forward_signal_combination(_panel())
    models = set(res.index.get_level_values("model"))
    assert models == {"base_season (incumbent)", "best single signal", "regularized combination"}
    assert res["spearman"].notna().any()


def test_leakage_safe_shape() -> None:
    res = walk_forward_signal_combination(_panel(seed=1))
    assert (res["n_gw"] > 0).all()
    assert res["spearman"].dropna().between(-1, 1).all()


def test_best_single_signal_reports_winner() -> None:
    res = walk_forward_signal_combination(_panel(seed=2))
    single = res.xs("best single signal", level="model")
    # every position's best-single row names a candidate column
    assert (single["note"].str.len() > 0).all()


def test_lagged_process_columns_are_prior() -> None:
    df = _panel(n_players=4, n_gw=6, seed=3).sort_values(["player_id", "gw"]).reset_index(drop=True)
    out = _add_lagged_process(df.copy())
    for col in ("xg_roll3", "xg_roll5", "xa_roll3", "xa_roll5"):
        assert col in out.columns
    # a player's FIRST appearance has no prior rows -> lagged roll is NaN (no leakage of current GW)
    first = out.groupby("player_id").head(1)
    assert first["xg_roll3"].isna().all()


def test_standardize_zeros_constant_column() -> None:
    tr = np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
    te = np.array([[2.0, 5.0]])
    tr_z, te_z = _standardize(tr, te)
    assert np.allclose(tr_z[:, 1], 0.0)          # constant column -> all zeros (penalty will drop it)
    assert abs(te_z[0, 0]) < 1e-9                 # test row at train mean -> 0


def test_select_penalty_returns_grid_members() -> None:
    df = _add_lagged_process(_panel(seed=4).sort_values(["player_id", "gw"]).reset_index(drop=True))
    alpha, l1_wt = _select_penalty(df[df["gw"] < 12], "goals_scored", _GOAL_FEATURES, sm.families.Poisson())
    assert alpha in ALPHA_GRID
    assert l1_wt in (*L1_WT_GRID, _L1_WT_DEFAULT)


def test_selection_stability_reports_kept_signals() -> None:
    res = selection_stability(_panel(seed=6))
    assert res.index.names == ["component", "feature"]
    # every logged (component, feature) has a selection frequency in [0, 1] and non-negative coef
    assert res["selection_freq"].between(0, 1).all()
    assert (res["mean_abs_coef"] >= 0).all()
    # goals must have logged at least its own process signal as a candidate
    goals_feats = set(res.xs("goals_scored", level="component").index)
    assert "xg_roll3" in goals_feats


def test_gradient_boosting_ceiling_runs() -> None:
    res = gradient_boosting_ceiling(_panel(seed=5))
    assert set(res.index.get_level_values("model")) == {"gradient boosting (ceiling)"}
    assert res["spearman"].dropna().between(-1, 1).all()
