"""Tests for the assists term (model.terms.assists) — contract + frozen-number reproduction.

Reproduction invariant (spec §10): ``AssistsModel(minimal)`` emits E[assists] **bit-identical** to the
god-file ``component_forecast``'s assists GLM on a fixed panel. Also asserts the shared base is truly
shared — goals and assists differ only in target/pool, not logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
from model.terms._freeze import assert_frozen
from model.terms._poisson_component import PoissonPlayerComponentModel
from model.terms.assists import AssistsModel, AssistsTerm

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
                "assists": rng.poisson(skill), "goals_scored": rng.poisson(skill),
                "total_points": 2.0,
            })
    return pd.DataFrame(rows)


def test_satisfies_model_and_term_contracts() -> None:
    model = AssistsModel(variant="minimal")
    term = AssistsTerm(model)
    assert isinstance(model, Model)
    assert isinstance(term, Term)
    assert model.name == "assists" and term.name == "assists"
    assert model.target == "assists" and model.term == "assists"
    assert term.baseline_col == "assists_prior"
    assert model.grain == "player_gw"
    assert model.pool.minimal == ("xgi_roll3", "minutes_roll3")


def test_reuses_the_shared_poisson_base() -> None:
    """DRY proof: assists is the shared shape, not a copy — it subclasses the base, adds no fit logic."""
    assert issubclass(AssistsModel, PoissonPlayerComponentModel)
    assert "fit" not in AssistsModel.__dict__      # inherited, not reimplemented
    assert "_fit_predict" not in AssistsModel.__dict__


def test_emit_reproduces_godfile_assists_frozen() -> None:
    got = AssistsModel(variant="minimal").fit(_panel()).predictions.to_numpy()
    assert_frozen(got, n_scored=1320, sum6=268.346591,
                  spot_idx=[3, 339, 675, 1011, 1347],
                  spot_vals=[0.127, 0.351, 0.2166, 0.3701, 0.2658])


def test_emit_returns_single_assists_term() -> None:
    model = AssistsModel()
    fitted = model.fit(_panel(seed=2))
    assert isinstance(fitted, Fitted)
    out = model.emit(fitted)
    assert set(out) == {"assists"}
    assert out["assists"].shape[0] == len(fitted.predictions)


def test_check_assumptions_dispersion_and_detectability() -> None:
    report = AssistsModel().check_assumptions(AssistsModel.population(_panel(seed=3)))
    assert isinstance(report, AssumptionReport)
    assert report.term == "assists"
    assert report.n_train > 0
    assert report.family_ok  # near-Poisson counts ⇒ Poisson justified
    assert isinstance(report.detectable, bool)


def test_validate_scores_model_vs_own_baseline() -> None:
    res = AssistsTerm().validate(_panel(seed=1))
    assert isinstance(res, GateResult)
    assert res.term == "assists"
    assert {"position", "baseline", "e_assists", "delta"} <= set(res.table.columns)
    assert res.table["e_assists"].between(-1, 1).all()
    assert set(res.passed).issubset({"GK", "DEF", "MID", "FWD"})


def _process_panel(n_players: int = 120, n_gw: int = 16, seed: int = 7) -> pd.DataFrame:
    """Panel carrying the shipped ASSIST_FEATURES inputs: xa, xgi_roll3/5, minutes_roll3."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        skill = rng.uniform(0.02, 0.5)
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xg": max(0.0, skill + rng.normal(0, 0.08)), "xa": max(0.0, skill * 0.6 + rng.normal(0, 0.05)),
                "xgi_roll3": skill + rng.normal(0, 0.05), "xgi_roll5": skill + rng.normal(0, 0.04),
                "minutes_roll3": 90.0, "assists": rng.poisson(skill * 0.6),
            })
    return pd.DataFrame(rows)


def test_selected_reproduces_full_pts_assists_frozen() -> None:
    """full_pts reconciliation, frozen: selected (5-feature ASSIST_FEATURES) ≡ points_model's inline fit."""
    panel = _process_panel()
    assert set(AssistsModel(variant="selected").features(AssistsModel.population(panel))) == {
        "xa_roll3", "xa_roll5", "xgi_roll3", "xgi_roll5", "minutes_roll3"}
    got = AssistsModel(variant="selected").fit(panel).predictions.to_numpy()
    assert_frozen(got, n_scored=1560, sum6=244.991438,
                  spot_idx=[3, 387, 771, 1155, 1539],
                  spot_vals=[0.1542, 0.0515, 0.1967, 0.1269, 0.2568])
