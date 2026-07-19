"""Tests for the goals term (model.terms.goals) — contract + frozen-number reproduction.

The reproduction guarantee (spec §10 invariant): the strangled ``GoalsModel`` emits E[goals] identical to
the god-file ``component_forecast``/``points_model`` goals GLM. Those references have now been **frozen**
(the god-files are being deleted, spec §10.5): each golden below asserts the emit against a checked-in
regression vector — a scored-row count, the 6dp prediction sum (a drift-sensitive checksum), and a handful
of 4dp spot values — captured while the god-file references were still live and green.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
from model.terms._freeze import assert_frozen
from model.terms.goals import GoalsModel, GoalsTerm

pytestmark = pytest.mark.unit


def _panel(n_players: int = 120, n_gw: int = 14, seed: int = 0) -> pd.DataFrame:
    """Same shape as the god-file's component test panel (so predictions are comparable)."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        skill = rng.uniform(0.02, 0.4)
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xgi_roll3": skill + rng.normal(0, 0.05), "minutes_roll3": 90.0,
                "goals_scored": rng.poisson(skill), "assists": rng.poisson(0.1),
                "total_points": 2.0,
            })
    return pd.DataFrame(rows)


def test_satisfies_model_and_term_contracts() -> None:
    model = GoalsModel(variant="minimal")
    term = GoalsTerm(model)
    assert isinstance(model, Model)
    assert isinstance(term, Term)
    assert model.name == "goals" and term.name == "goals"
    assert term.baseline_col == "goals_prior"
    assert model.grain == "player_gw"
    assert model.pool.minimal == ("xgi_roll3", "minutes_roll3")


def test_emit_reproduces_godfile_goals_frozen() -> None:
    """The strangler invariant, frozen: minimal emit ≡ the (deleted) component_forecast goals GLM."""
    got = GoalsModel(variant="minimal").fit(_panel()).predictions.to_numpy()
    assert_frozen(got, n_scored=1320, sum6=287.867666,
                  spot_idx=[3, 339, 675, 1011, 1347],
                  spot_vals=[0.1284, 0.0869, 0.335, 0.2783, 0.2843])


def test_emit_returns_single_goals_term() -> None:
    model = GoalsModel()
    fitted = model.fit(_panel(seed=2))
    assert isinstance(fitted, Fitted)  # fit produces the bundle; emit (on the model) reads views off it
    out = model.emit(fitted)
    assert set(out) == {"goals"}  # a non-joint model emits exactly one term
    assert out["goals"].shape[0] == len(fitted.predictions)


def test_check_assumptions_dispersion_and_detectability() -> None:
    panel = _panel(seed=3)
    train = GoalsModel.population(panel)
    report = GoalsModel().check_assumptions(train)
    assert isinstance(report, AssumptionReport)
    assert report.term == "goals"
    assert report.n_train > 0
    assert report.family_ok  # near-Poisson counts ⇒ Poisson justified (matches count_models diagnosis)
    assert isinstance(report.detectable, bool)


def test_detectability_floor_fails_on_a_thin_zero_slice() -> None:
    """A slice with too few positive events is under-powered ⇒ not detectable (inconclusive, not null)."""
    panel = _panel(n_players=8, n_gw=6, seed=9).copy()
    panel["goals_scored"] = 0  # no events at all
    report = GoalsModel().check_assumptions(GoalsModel.population(panel))
    assert report.detectable is False
    assert "detectability floor" in report.notes


def test_validate_scores_model_vs_own_baseline() -> None:
    res = GoalsTerm().validate(_panel(seed=1))
    assert isinstance(res, GateResult)
    assert res.term == "goals"
    assert {"position", "baseline", "e_goals", "delta"} <= set(res.table.columns)
    assert res.table["e_goals"].between(-1, 1).all()
    assert set(res.passed).issubset({"GK", "DEF", "MID", "FWD"})


def test_selected_falls_back_to_minimal_without_process_rolls() -> None:
    """On a mart lacking xg/xgi_roll5, selected can only draw the two mechanistic columns."""
    panel = _panel(seed=4)   # no xg / xgi_roll5 columns
    assert GoalsModel(variant="selected").features(panel) == ["xgi_roll3", "minutes_roll3"]


def _process_panel(n_players: int = 120, n_gw: int = 16, seed: int = 7) -> pd.DataFrame:
    """Panel carrying the shipped GOAL_FEATURES inputs: xg, xgi_roll3/5, minutes_roll3."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        skill = rng.uniform(0.02, 0.5)
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xg": max(0.0, skill + rng.normal(0, 0.08)), "xa": max(0.0, skill * 0.5 + rng.normal(0, 0.05)),
                "xgi_roll3": skill + rng.normal(0, 0.05), "xgi_roll5": skill + rng.normal(0, 0.04),
                "minutes_roll3": 90.0, "goals_scored": rng.poisson(skill),
            })
    return pd.DataFrame(rows)


def test_selected_reproduces_full_pts_goals_frozen() -> None:
    """full_pts reconciliation, frozen: selected (5-feature GOAL_FEATURES) ≡ points_model's inline goals fit."""
    panel = _process_panel()
    # selected must draw exactly the shipped 5-feature GOAL_FEATURES set (frozen expected set).
    assert set(GoalsModel(variant="selected").features(GoalsModel.population(panel))) == {
        "xg_roll3", "xg_roll5", "xgi_roll3", "xgi_roll5", "minutes_roll3"}
    got = GoalsModel(variant="selected").fit(panel).predictions.to_numpy()
    assert_frozen(got, n_scored=1560, sum6=378.949036,
                  spot_idx=[3, 387, 771, 1155, 1539],
                  spot_vals=[0.2613, 0.0966, 0.1392, 0.1013, 0.1596])


def _lagsafe_mart(n_players: int = 6, n_gw: int = 6) -> pd.DataFrame:
    """A mart where the pool's strictly-prior features are NaN on each player's first appearance."""
    rows = []
    for p in range(n_players):
        for gw in range(1, n_gw + 1):
            first = gw == 1
            rows.append({
                "player_id": p, "gw": gw,
                "xgi_roll3": np.nan if first else 0.2,
                "minutes_roll3": np.nan if first else 90.0,
            })
    return pd.DataFrame(rows)


def test_leakage_property_passes_on_lagsafe_mart() -> None:
    from model.features.build import assert_lag_safe
    from model.terms.goals.spec import GOALS_POOL

    assert_lag_safe(_lagsafe_mart(), GOALS_POOL)  # must not raise


def test_leakage_property_catches_a_leaked_feature() -> None:
    from model.features.build import assert_lag_safe
    from model.terms.goals.spec import GOALS_POOL

    leaky = _lagsafe_mart()
    leaky.loc[leaky["gw"] == 1, "xgi_roll3"] = 0.5  # defined on first appearance ⇒ leak
    with pytest.raises(AssertionError, match="xgi_roll3"):
        assert_lag_safe(leaky, GOALS_POOL)
