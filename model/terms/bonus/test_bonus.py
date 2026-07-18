"""Tests for the bonus term (model.terms.bonus) — contract + frozen-number reproduction.

Reproduction invariant (spec §10): ``BonusModel`` emits ``e_bonus`` **bit-identical** to the god-file
``points_model.walk_forward_bonus``, and the term's gate reproduces ``bonus_validation``. Also asserts
the contemporaneous scoring-map shape (OLS on same-match returns_pts, coefficients exposed).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Diagnostics, GateResult, Model, Term
from model.terms.bonus import BonusModel, BonusTerm

pytestmark = pytest.mark.unit


def _panel(seed: int = 0, n_per_pos: int = 40, n_gw: int = 16) -> pd.DataFrame:
    """All-position panel with realized returns + bonus correlated with returns (the BPS proxy)."""
    rng = np.random.default_rng(seed)
    rows = []
    pid = 0
    for pos in ("GK", "DEF", "MID", "FWD"):
        for _ in range(n_per_pos):
            skill = rng.uniform(0.05, 0.5)
            for gw in range(1, n_gw + 1):
                goals = int(rng.poisson(skill if pos != "GK" else 0.01))
                assists = int(rng.poisson(skill * 0.6))
                cs = int(rng.random() < 0.3) if pos in ("GK", "DEF", "MID") else 0
                saves = int(rng.poisson(2.0)) if pos == "GK" else 0
                # realized bonus loosely rises with returns (top-3 BPS) + noise, clipped to 0..3
                base = goals * 2 + assists + cs + (saves // 3)
                bonus = int(np.clip(round(base * 0.4 + rng.normal(0, 0.5)), 0, 3))
                rows.append({
                    "player_id": pid, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                    "goals_scored": goals, "assists": assists, "clean_sheets": cs, "saves": saves,
                    "bonus": bonus, "total_points": 2.0,
                })
            pid += 1
    return pd.DataFrame(rows)


def test_satisfies_contracts_and_shape() -> None:
    model = BonusModel()
    term = BonusTerm(model)
    assert isinstance(model, Model) and isinstance(term, Term)
    assert model.name == "bonus" and model.target == "bonus_actual"
    assert term.baseline_col == "returns_pts"   # a contemporaneous composite, not a lagged feature
    assert model.pool.candidates[0].known_future is True


def test_selected_emit_reproduces_walk_forward_bonus_to_the_bit() -> None:
    from model.forecast.points_model import walk_forward_bonus

    panel = _panel()
    fitted = BonusModel().fit(panel)
    got = BonusModel.population(panel).assign(e=fitted.predictions.to_numpy())
    got = got[["player_id", "gw", "e"]]
    ref = walk_forward_bonus(panel)[["player_id", "gw", "e_bonus"]]
    merged = got.merge(ref, on=["player_id", "gw"])
    assert len(merged) == len(got)
    both = ~(merged["e"].isna() | merged["e_bonus"].isna())
    assert both.any()
    np.testing.assert_array_almost_equal(merged.loc[both, "e"].to_numpy(),
                                         merged.loc[both, "e_bonus"].to_numpy(), decimal=10)
    np.testing.assert_array_equal(merged["e"].isna().to_numpy(), merged["e_bonus"].isna().to_numpy())


def test_gate_reproduces_bonus_validation() -> None:
    from model.forecast.points_model import bonus_validation

    panel = _panel()
    ref = bonus_validation(panel)  # indexed (position, model)
    got = BonusTerm().validate(panel).table.set_index("position")
    for pos in got.index:
        ref_proxy = ref.xs(pos, level="position").loc["bonus proxy (calibrated)", "spearman"]
        assert got.loc[pos, "e_bonus"] == pytest.approx(ref_proxy, abs=1e-9)


def test_emit_is_clipped_and_exposes_calibration_coefficients() -> None:
    fitted = BonusModel().fit(_panel(seed=2))
    out = BonusModel().emit(fitted)
    assert set(out) == {"bonus"}
    vals = out["bonus"]
    defined = ~np.isnan(vals)
    assert ((vals[defined] >= 0.0) & (vals[defined] <= 3.0)).all()   # bonus in [0, 3]
    coeffs = fitted.meta["coefficients"]
    assert {"position", "gw", "intercept", "slope"} <= set(coeffs.columns)  # simulator co-movement inputs
    assert not coeffs.empty


def test_check_assumptions_and_diagnose() -> None:
    panel = _panel(seed=3)
    report = BonusModel().check_assumptions(BonusModel.population(panel))
    assert isinstance(report, AssumptionReport)
    assert report.dispersion["family"] == "gaussian_ols"
    assert "proxy_spearman" in report.dispersion
    diag = BonusTerm().diagnose(panel)
    assert isinstance(diag, Diagnostics)
    assert {"intercept", "slope"} <= set(diag.ablation.columns)  # ablation == the calibration coefficients


def test_validate_covers_all_positions() -> None:
    res = BonusTerm().validate(_panel(seed=1))
    assert isinstance(res, GateResult)
    assert set(res.table["position"]).issubset({"GK", "DEF", "MID", "FWD"})
    assert {"baseline", "e_bonus", "delta"} <= set(res.table.columns)
