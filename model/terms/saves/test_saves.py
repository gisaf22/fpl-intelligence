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
import statsmodels.api as sm

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
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


def _reference_e_saves(mart: pd.DataFrame) -> pd.DataFrame:
    """The god-file GK-saves component (frozen design): GK e_saves keyed by (player_id, gw)."""
    from model.eval.walkforward import WARMUP_GW
    from model.forecast.component_forecast import _SAVES_FEATURES, _fit_predict

    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    df["e_saves"] = np.nan
    for t in sorted(g for g in df["gw"].unique() if g > WARMUP_GW):
        train, test = df[df["gw"] < t], df[df["gw"] == t]
        if test.empty or len(train) < 100:
            continue
        gk_tr, gk_te = train[train["position"] == "GK"], test[test["position"] == "GK"]
        if not gk_te.empty and len(gk_tr.dropna(subset=_SAVES_FEATURES)) >= 30:
            df.loc[gk_te.index, "e_saves"] = _fit_predict(gk_tr, gk_te, "saves", _SAVES_FEATURES,
                                                           sm.families.Poisson())
    gk = df[df["position"] == "GK"]
    return gk[["player_id", "gw", "e_saves"]].reset_index(drop=True)


def test_satisfies_contracts_and_is_gk_only() -> None:
    model = SavesModel(variant="minimal")
    term = SavesTerm(model)
    assert isinstance(model, Model) and isinstance(term, Term)
    assert model.name == "saves" and model.target == "saves"
    assert term.baseline_col == "saves_prior"
    assert issubclass(SavesModel, PoissonPlayerComponentModel)
    pop = SavesModel.population(_panel())
    assert (pop["position"] == "GK").all()  # population override restricts to keepers


def test_emit_reproduces_godfile_gk_saves_to_the_bit() -> None:
    panel = _panel()
    fitted = SavesModel(variant="minimal").fit(panel)
    got = SavesModel.population(panel).assign(e_saves=fitted.predictions.to_numpy())
    got = got[["player_id", "gw", "e_saves"]].reset_index(drop=True)
    ref = _reference_e_saves(panel)
    merged = got.merge(ref, on=["player_id", "gw"], suffixes=("_got", "_ref"))
    assert len(merged) == len(got)  # same GK rows on both sides
    both = ~(merged["e_saves_got"].isna() | merged["e_saves_ref"].isna())
    assert both.any()
    np.testing.assert_array_almost_equal(
        merged.loc[both, "e_saves_got"].to_numpy(), merged.loc[both, "e_saves_ref"].to_numpy(), decimal=10
    )
    np.testing.assert_array_equal(merged["e_saves_got"].isna().to_numpy(),
                                  merged["e_saves_ref"].isna().to_numpy())


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
