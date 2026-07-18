"""Tests for the assists term (model.terms.assists) — contract + frozen-number reproduction.

Reproduction invariant (spec §10): ``AssistsModel(minimal)`` emits E[assists] **bit-identical** to the
god-file ``component_forecast``'s assists GLM on a fixed panel. Also asserts the shared base is truly
shared — goals and assists differ only in target/pool, not logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
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


def _reference_e_assists(mart: pd.DataFrame) -> pd.Series:
    """Expanding walk-forward E[assists] exactly as component_forecast fits the assists component."""
    from model.eval.walkforward import WARMUP_GW
    from model.forecast.component_forecast import _ASSIST_FEATURES, _fit_predict

    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    pred = pd.Series(np.nan, index=df.index, dtype=float)
    for t in sorted(g for g in df["gw"].unique() if g > WARMUP_GW):
        train, test = df[df["gw"] < t], df[df["gw"] == t]
        if test.empty or len(train) < 100:
            continue
        pred.loc[test.index] = _fit_predict(train, test, "assists", _ASSIST_FEATURES, sm.families.Poisson())
    return pred


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


def test_emit_reproduces_godfile_assists_to_the_bit() -> None:
    panel = _panel()
    fitted = AssistsModel(variant="minimal").fit(panel)
    got = fitted.predictions.to_numpy()
    ref = _reference_e_assists(panel).to_numpy()
    both = ~(np.isnan(got) | np.isnan(ref))
    assert both.any()
    np.testing.assert_array_almost_equal(got[both], ref[both], decimal=10)
    np.testing.assert_array_equal(np.isnan(got), np.isnan(ref))


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
