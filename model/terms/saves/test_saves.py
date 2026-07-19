"""Tests for the saves term (model.terms.saves) — contract + frozen-number reproduction.

Reproduction invariant (spec §10): ``SavesModel(minimal)`` emits E[saves] **bit-identical** to the
god-file ``component_forecast``'s GK-saves GLM on a fixed panel. Because saves lives inside the
all-position walk-forward there (outer guard = all-position train ≥ 100, non-binding for GW>3) while the
strangled model uses a GK-only population, the panel carries all positions so the reference's outer guard
is non-binding — proving the ``min_train_rows_total=30`` override reproduces the effective GK gate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
from model.terms._freeze import assert_frozen
from model.terms._poisson_component import PoissonPlayerComponentModel
from model.terms.saves import SavesModel, SavesTerm

pytestmark = pytest.mark.unit


def _panel(n_players: int = 120, n_gw: int = 14, seed: int = 0) -> pd.DataFrame:
    """All-position panel (30 GK) so the reference's all-position train >= 100 guard is non-binding."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = ["GK", "DEF", "MID", "FWD"][p % 4]
        shot_rate = rng.uniform(0.5, 2.5)  # a keeper's fixture shots-faced level
        for gw in range(1, n_gw + 1):
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                "xgc_roll3": shot_rate + rng.normal(0, 0.1), "minutes_roll3": 90.0,
                "saves": rng.poisson(shot_rate) if pos == "GK" else 0,
                "total_points": 2.0,
            })
    return pd.DataFrame(rows)


def test_satisfies_contracts_and_is_gk_only() -> None:
    model = SavesModel(variant="minimal")
    term = SavesTerm(model)
    assert isinstance(model, Model) and isinstance(term, Term)
    assert model.name == "saves" and model.target == "saves"
    assert term.baseline_col == "saves_prior"
    assert issubclass(SavesModel, PoissonPlayerComponentModel)
    pop = SavesModel.population(_panel())
    assert (pop["position"] == "GK").all()  # population override restricts to keepers


def test_emit_reproduces_godfile_gk_saves_frozen() -> None:
    """Frozen: minimal GK e_saves ≡ the (deleted) component_forecast GK-saves GLM (GK-only population)."""
    got = SavesModel(variant="minimal").fit(_panel()).predictions.to_numpy()
    assert_frozen(got, n_scored=330, sum6=471.100411,
                  spot_idx=[3, 87, 171, 255, 339],
                  spot_vals=[1.4013, 1.1705, 2.3551, 0.9902, 1.71])


def test_emit_returns_single_saves_term() -> None:
    model = SavesModel()
    fitted = model.fit(_panel(seed=2))
    assert isinstance(fitted, Fitted)
    out = model.emit(fitted)
    assert set(out) == {"saves"}


def test_validate_scores_gk_only() -> None:
    res = SavesTerm().validate(_panel(seed=1))
    assert isinstance(res, GateResult)
    assert res.term == "saves"
    assert set(res.table["position"]).issubset({"GK"})  # GK-only population -> GK-only gate
    assert {"baseline", "e_saves", "delta"} <= set(res.table.columns)


def test_check_assumptions_reports_dispersion_and_detectability() -> None:
    report = SavesModel().check_assumptions(SavesModel.population(_panel(seed=3)))
    assert isinstance(report, AssumptionReport)
    assert report.term == "saves"
    assert report.n_train > 0
    assert isinstance(report.detectable, bool)
    assert isinstance(report.family_ok, bool)  # saves may be over-dispersed — reported, not blocked
