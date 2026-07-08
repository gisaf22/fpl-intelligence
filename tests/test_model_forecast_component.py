"""Tests for the Phase 2.1 component forecast (model.forecast.component_forecast)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.forecast.component_forecast import walk_forward_component_points

pytestmark = pytest.mark.unit


def _panel(n_players: int = 120, n_gw: int = 14, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        skill = rng.uniform(0.02, 0.4)
        for gw in range(1, n_gw + 1):
            goals = rng.poisson(skill)
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xgi_roll3": skill + rng.normal(0, 0.05), "minutes_roll3": 90.0,
                "goals_conceded_roll3": rng.uniform(0, 2), "xgc_roll3": rng.uniform(0, 2),
                "goals_scored": goals, "assists": rng.poisson(0.1),
                "clean_sheets": int(rng.random() < 0.3),
                "total_points": 2 + goals * 5 + rng.normal(0, 1),
            })
    return pd.DataFrame(rows)


def test_returns_both_models_per_position() -> None:
    res = walk_forward_component_points(_panel())
    assert res.index.names == ["position", "model"]
    models = set(res.index.get_level_values("model"))
    assert models == {"base_season (incumbent)", "component model"}
    assert res["spearman"].notna().any()


def test_component_model_is_leakage_safe_shape() -> None:
    # Composed E[points] is only defined post-warmup; the frame carries a Spearman per cell.
    res = walk_forward_component_points(_panel(seed=1))
    assert (res["n_gw"] > 0).all()
    assert res["spearman"].between(-1, 1).all()
