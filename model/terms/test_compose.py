"""Tests for model.compose + the term registry — the assembler over all extracted terms.

No god-file golden here (compose is a NEW assembler — the shipped ``full_pts`` reconciliation is a tracked
follow-up). Instead: the registry covers every term, and the decomposition is **internally exact** (the
parts sum to ``e_points``) with each contribution in its valid range.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.compose import DECOMP_COLUMNS, _collect_views, _master_panel, compose_points
from model.terms.registry import BONUS_MODEL, REGISTERED_TERMS, TERM_MODELS

pytestmark = pytest.mark.unit


def _mart(seed: int = 0, n_teams: int = 16, n_gw: int = 16) -> pd.DataFrame:
    """A full mart-like panel carrying every column the eight terms need."""
    rng = np.random.default_rng(seed)
    roster = [("GK", 1), ("DEF", 3), ("MID", 3), ("FWD", 2)]
    rows = []
    pid = 0
    for team in range(n_teams):
        ga_rate = rng.uniform(0.6, 2.0)
        players = []
        for pos, k in roster:
            for _ in range(k):
                players.append((pid, pos, rng.uniform(0.05, 0.5), rng.uniform(0.5, 0.95),
                                rng.uniform(6.0, 14.0)))
                pid += 1
        for gw in range(1, n_gw + 1):
            team_ga = int(rng.poisson(ga_rate))
            was_home = int(rng.random() < 0.5)
            fdr = float(rng.integers(2, 6))
            for pl, pos, skill, p_start, dc_lam in players:
                started = rng.random() < p_start
                minutes = 90 if started else int(rng.choice([20, 45]))
                goals = int(rng.poisson(skill if pos != "GK" else 0.01))
                assists = int(rng.poisson(skill * 0.6))
                saves = int(rng.poisson(2.5)) if pos == "GK" else 0
                dc = int(rng.poisson(dc_lam))
                base = goals * 2 + assists + int(team_ga == 0)
                bonus = int(np.clip(round(base * 0.4 + rng.normal(0, 0.5)), 0, 3))
                rows.append({
                    "player_id": pl, "team_id": team, "gw": gw, "position": pos,
                    "minutes": minutes, "is_dgw": False,
                    "goals_scored": goals, "assists": assists, "saves": saves,
                    "clean_sheets": int(team_ga == 0 and minutes >= 60), "goals_conceded": team_ga,
                    "defensive_contribution": dc, "bonus": bonus, "starts": int(started),
                    "xgi_roll3": skill + rng.normal(0, 0.05), "xgc_roll3": ga_rate + rng.normal(0, 0.1),
                    "xgc": max(0.0, ga_rate + rng.normal(0, 0.1)),
                    "minutes_roll3": 80.0, "minutes_roll5": 80.0, "minutes_roll8": 80.0,
                    "fdr_avg": fdr, "was_home": was_home, "total_points": 2.0,
                })
    return pd.DataFrame(rows)


def test_registry_covers_every_scored_view() -> None:
    n_models = len(TERM_MODELS) + 1  # + bonus
    assert n_models == 7
    emitted = set()
    for m in TERM_MODELS:
        emitted |= set(_emit_names(m))
    emitted |= {BONUS_MODEL.term}
    assert emitted == set(REGISTERED_TERMS)


def _emit_names(model) -> tuple[str, ...]:
    """The term names a model emits (team_goals_against emits two)."""
    if model.name == "team_goals_against":
        return ("clean_sheet", "conceded")
    return (model.term,)


def test_collect_views_maps_all_terms_onto_the_master_panel() -> None:
    mart = _mart()
    master = _master_panel(mart)
    views = _collect_views(master, mart)
    for term in ("goals", "assists", "saves", "clean_sheet", "conceded", "defensive_contribution", "p60"):
        assert term in views
        assert len(views[term]) == len(master)


def test_decomposition_sums_to_e_points_exactly() -> None:
    out = compose_points(_mart())
    recomposed = out[list(DECOMP_COLUMNS)].sum(axis=1)
    np.testing.assert_array_almost_equal(out["e_points"].to_numpy(), recomposed.to_numpy(), decimal=12)


def test_contributions_are_in_valid_ranges() -> None:
    out = compose_points(_mart())
    post = out[out["gw"] > 3]
    assert (post["appearance"].between(1.0, 2.0)).all()          # 1 (played) .. 2 (>=60')
    assert (post["goals"] >= -1e-9).all()
    assert (post["assists"] >= -1e-9).all()
    assert (post["bonus"].between(-1e-9, 3.0 + 1e-9)).all()
    # position eligibility: FWD get no clean sheet; MID/FWD get no conceded penalty
    fwd = post[post["position"] == "FWD"]
    assert (fwd["clean_sheets"].abs() < 1e-9).all()
    assert (post.loc[post["position"].isin(["MID", "FWD"]), "goals_conceded"].abs() < 1e-9).all()
    assert (post.loc[post["position"].isin(["GK", "DEF"]), "goals_conceded"] <= 1e-9).all()  # penalty <= 0


def test_e_points_is_finite_post_warmup() -> None:
    out = compose_points(_mart(seed=2))
    post = out[out["gw"] > 3]
    assert np.isfinite(post["e_points"].to_numpy()).all()
    assert (post["e_points"] > 0).mean() > 0.9  # appearance alone keeps E[points] positive for players
