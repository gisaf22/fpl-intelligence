"""Tests for the relocated forecast diagnostics (model.eval.forecast_diagnostics).

Moved verbatim from the deleted god-file tests (test_model_forecast_component /
test_model_forecast_points_model) so the two surviving diagnostics keep their coverage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.eval.forecast_diagnostics import unmodeled_points_share, xg_vs_goals_forecast_skill

pytestmark = pytest.mark.unit


def _xg_panel(n_players: int = 90, n_gw: int = 14, seed: int = 0) -> pd.DataFrame:
    """Panel where xg = a player's true scoring rate + small noise; goals ~ Poisson(rate)."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["DEF", "MID", "FWD"][p % 3]
        rate = rng.uniform(0.05, 0.6)
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xg": rate + rng.normal(0, 0.05), "goals_scored": rng.poisson(rate),
            })
    return pd.DataFrame(rows)


def _deferred_panel() -> pd.DataFrame:
    """Small canonical panel: every player scores 6 pts with 1 bonus; GK also make 3 saves."""
    rows = []
    for p in range(8):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        for gw in range(1, 6):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "total_points": 6, "bonus": 1, "saves": 3 if pos == "GK" else 0,
            })
    return pd.DataFrame(rows)


def test_xg_vs_goals_structure_and_winner_consistency() -> None:
    out = xg_vs_goals_forecast_skill(_xg_panel())
    assert list(out.index) == ["DEF", "MID", "FWD"]
    assert {"xg_prior", "goals_prior", "delta", "winner"} <= set(out.columns)
    for _, row in out.iterrows():
        assert row["winner"] == ("xG" if row["xg_prior"] > row["goals_prior"] else "goals")
        assert -1.0 <= row["xg_prior"] <= 1.0
        assert row["delta"] == pytest.approx(row["xg_prior"] - row["goals_prior"], abs=1e-9)


def test_unmodeled_points_share_isolates_gk_saves_and_bonus() -> None:
    out = unmodeled_points_share(_deferred_panel())
    assert list(out.index) == ["GK", "DEF", "MID", "FWD"]
    assert {"total_points", "bonus_pct", "gk_saves_pct"} <= set(out.columns)
    assert out.loc["GK", "gk_saves_pct"] > 0                       # only GK carry a saves share
    assert (out.loc[["DEF", "MID", "FWD"], "gk_saves_pct"] == 0).all()
    assert (out["bonus_pct"] > 0).all()                           # bonus scored for every position
