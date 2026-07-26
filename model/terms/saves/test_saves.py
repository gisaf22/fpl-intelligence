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


def test_saves_points_expectation_is_exact_not_linear() -> None:
    """The scoring-rule fix: FPL pays floor(S/3), so the expected POINTS are E[floor(S/3)], NOT the
    naive E[S]/3. The gap is a concave-step Jensen effect (~0.33 pt at a typical keeper rate) — the bug
    that made compose over-count GK saves points and diverge from the simulator (which draws then floors).
    """
    from model.terms.saves.saves import saves_points_expectation

    rng = np.random.default_rng(0)
    for lam in (0.5, 2.6, 5.0, 8.0):
        exact = float(saves_points_expectation(np.array([lam]))[0])
        mc = float((rng.poisson(lam, 1_000_000) // 3).mean())     # draw-then-floor: the ground truth
        assert abs(exact - mc) < 5e-3, f"lam={lam}: exact {exact:.4f} vs MC {mc:.4f}"
        assert exact < lam / 3.0, f"lam={lam}: exact {exact:.4f} not below naive {lam/3:.4f}"
    # a typical keeper rate leaves a materially large gap — this is worth ~0.33 pt/GW
    assert (2.6 / 3.0) - float(saves_points_expectation(np.array([2.6]))[0]) > 0.3
    # NaN-safe (compose feeds nan_to_num'd values, but the primitive is honest on its own)
    assert np.isnan(saves_points_expectation(np.array([np.nan]))[0])


def test_saves_points_expectation_matches_simulator_mean() -> None:
    """compose's point estimate must now AGREE with the simulator's floored-draw mean at GK (the two
    diverged before the fix — E[S]/3 vs E[floor(S/3)]). Same construction as conceded_penalty_expectation.
    """
    from model.terms.saves.saves import saves_points_expectation

    rng = np.random.default_rng(1)
    lam = np.array([1.2, 2.6, 4.1])
    sim_mean = np.array([(rng.poisson(x, 400_000) // 3).mean() for x in lam])
    np.testing.assert_allclose(saves_points_expectation(lam), sim_mean, atol=5e-3)
