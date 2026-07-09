"""Tests for the Phase 3.0 Track-3 points model - team goals-against layer (part 3.1)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.forecast.points_model import (
    _conceded_penalty_expectation,
    build_team_ga_panel,
    dc_validation,
    team_ga_cs_validation,
    walk_forward_dc,
    walk_forward_team_ga,
)

pytestmark = pytest.mark.unit


def _panel(n_teams: int = 20, n_gw: int = 16, seed: int = 0) -> pd.DataFrame:
    """Synthetic player-GW panel: per-team defensive strength drives goals-against, and each player
    has a stable defensive-action propensity driving ``defensive_contribution`` (so lags predict)."""
    rng = np.random.default_rng(seed)
    rows = []
    for tm in range(n_teams):
        strength = rng.uniform(0.3, 2.2)  # team's mean goals-against
        dc_prop = {slot: rng.uniform(3, 13) for slot in range(5)}  # per-player DC-action mean
        for gw in range(1, n_gw + 1):
            ga = rng.poisson(strength)
            home = int(rng.random() < 0.5)
            for slot, pos in enumerate(["GK", "DEF", "DEF", "MID", "FWD"]):
                rows.append({
                    "player_id": tm * 5 + slot, "team_id": tm, "gw": gw, "position": pos,
                    "minutes": 90, "is_dgw": False,
                    "goals_conceded": ga, "xgc": strength + rng.normal(0, 0.1),
                    "clean_sheets": int(ga == 0) if pos != "FWD" else 0,
                    "clean_sheets_roll3": rng.uniform(0, 1),
                    "defensive_contribution": rng.poisson(dc_prop[slot]),
                    "minutes_roll3": 90.0,
                    "was_home": home, "fdr_avg": rng.uniform(2, 4),
                })
    return pd.DataFrame(rows)


def test_conceded_penalty_expectation_is_nonpositive_and_monotone() -> None:
    lam = np.array([0.2, 1.0, 2.0, 3.5])
    exp = _conceded_penalty_expectation(lam)
    assert (exp <= 0).all()                       # a penalty term never adds points
    assert np.all(np.diff(exp) < 0)               # more expected goals-against -> more negative
    assert np.isnan(_conceded_penalty_expectation(np.array([np.nan]))[0])


def test_team_panel_is_one_row_per_team_gw_and_lag_safe() -> None:
    df = _panel(n_teams=6, n_gw=6, seed=1)
    team = build_team_ga_panel(df)
    assert (team.groupby(["team_id", "gw"]).size() == 1).all()
    # a team's first gameweek has no prior rows -> lagged features are NaN (no leakage)
    first = team.sort_values("gw").groupby("team_id").head(1)
    assert first[["ga_roll3", "xgc_roll3"]].isna().all().all()


def test_walk_forward_pcs_is_a_probability_and_tracks_lambda() -> None:
    team = walk_forward_team_ga(_panel(seed=2))
    fit = team.dropna(subset=["lambda_ga"])
    assert (fit["lambda_ga"] > 0).all()
    assert fit["p_cs"].between(0, 1).all()        # proper probability, no impossible states
    # p_cs = exp(-lambda) is strictly decreasing: sorting by lambda gives non-increasing p_cs
    p_by_lambda = fit.sort_values("lambda_ga")["p_cs"].to_numpy()
    assert np.all(np.diff(p_by_lambda) <= 1e-12)


def test_validation_table_shape_and_bounds() -> None:
    res = team_ga_cs_validation(_panel(seed=3))
    assert set(res.index.get_level_values("model")) == {"team-GA P(CS)", "clean_sheets_roll3 (incumbent)"}
    assert res["spearman"].dropna().between(-1, 1).all()
    assert "FWD" not in set(res.index.get_level_values("position"))  # FWD get no CS points


def test_dc_hit_target_and_probability_bounds() -> None:
    df = walk_forward_dc(_panel(seed=4))
    # target is the threshold indicator; GK are exempt (no DC term -> NaN prediction)
    assert set(df["dc_hit"].dropna().unique()) <= {0.0, 1.0}
    assert df.loc[df["position"] == "GK", "p_dc_hit"].isna().all()
    fit = df.dropna(subset=["p_dc_hit"])
    assert fit["p_dc_hit"].between(0, 1).all()
    # e_dc_pts = DC_POINTS (2) * p_hit
    assert np.allclose(fit["e_dc_pts"], 2.0 * fit["p_dc_hit"])


def test_dc_leakage_safe_and_validation_shape() -> None:
    df = walk_forward_dc(_panel(seed=5))
    first = df.sort_values("gw").groupby("player_id").head(1)
    assert first["dc_roll3"].isna().all()          # first appearance has no prior DC actions
    res = dc_validation(_panel(seed=5))
    assert set(res.index.get_level_values("model")) == {"DC logistic P(hit)", "dc_roll3 (baseline)"}
    assert set(res.index.get_level_values("position")) <= {"DEF", "MID", "FWD"}  # GK exempt
    assert res["spearman"].dropna().between(-1, 1).all()
