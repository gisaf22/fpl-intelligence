"""Tests for the defensive_contribution term — contract + frozen-number reproduction.

Reproduction invariant (spec §10): ``DefensiveContributionModel(selected)`` emits P(DC hit)
**bit-identical** to the god-file ``points_model.walk_forward_dc``, and the term's gate reproduces
``dc_validation``. Also asserts the new shape (logistic, derived binary target, per-position fit).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
from model.terms.defensive_contribution import (
    DefensiveContributionModel,
    DefensiveContributionTerm,
)

pytestmark = pytest.mark.unit


def _panel(seed: int = 0, n_per_pos: int = 50, n_gw: int = 16) -> pd.DataFrame:
    """DEF/MID/FWD panel with DC-action counts that straddle the thresholds (both classes present)."""
    rng = np.random.default_rng(seed)
    rows = []
    pid = 0
    for pos in ("DEF", "MID", "FWD"):
        for _ in range(n_per_pos):
            lam = rng.uniform(5.0, 15.0)  # some players clear DEF>=10 / MID-FWD>=12, some don't
            for gw in range(1, n_gw + 1):
                rows.append({
                    "player_id": pid, "gw": gw, "position": pos, "minutes": 90, "is_dgw": False,
                    "defensive_contribution": int(rng.poisson(lam)), "minutes_roll3": 90.0,
                    "fdr_avg": float(rng.integers(2, 6)), "was_home": int(rng.random() < 0.5),
                    "total_points": 2.0,
                })
            pid += 1
    return pd.DataFrame(rows)


def test_satisfies_contracts_and_shape() -> None:
    model = DefensiveContributionModel(variant="selected")
    term = DefensiveContributionTerm(model)
    assert isinstance(model, Model) and isinstance(term, Term)
    assert model.name == "defensive_contribution" and model.target == "dc_hit"
    assert term.baseline_col == "dc_roll3"
    assert model.family is __import__("statsmodels.api", fromlist=["families"]).families.Binomial


def test_population_builds_the_derived_binary_target() -> None:
    pop = DefensiveContributionModel.population(_panel())
    assert set(pop["position"].unique()) <= {"DEF", "MID", "FWD"}   # GK exempt
    assert set(pop["dc_hit"].dropna().unique()) <= {0.0, 1.0}       # binary
    assert pop["dc_hit"].nunique() == 2                             # both classes present
    # threshold is position-specific: DEF at 10, MID/FWD at 12
    assert (pop.loc[pop["position"] == "DEF", "dc_threshold"] == 10).all()
    assert (pop.loc[pop["position"] == "MID", "dc_threshold"] == 12).all()


def test_selected_emit_reproduces_walk_forward_dc_to_the_bit() -> None:
    from model.forecast.points_model import walk_forward_dc

    panel = _panel()
    fitted = DefensiveContributionModel(variant="selected").fit(panel)
    got = DefensiveContributionModel.population(panel).assign(p=fitted.predictions.to_numpy())
    got = got[["player_id", "gw", "p"]]
    ref = walk_forward_dc(panel)[["player_id", "gw", "p_dc_hit"]]
    merged = got.merge(ref, on=["player_id", "gw"])
    assert len(merged) == len(got)
    both = ~(merged["p"].isna() | merged["p_dc_hit"].isna())
    assert both.any()
    np.testing.assert_array_almost_equal(merged.loc[both, "p"].to_numpy(),
                                         merged.loc[both, "p_dc_hit"].to_numpy(), decimal=10)
    np.testing.assert_array_equal(merged["p"].isna().to_numpy(), merged["p_dc_hit"].isna().to_numpy())


def test_gate_reproduces_dc_validation() -> None:
    from model.forecast.points_model import dc_validation

    panel = _panel()
    ref = dc_validation(panel)  # indexed (position, model)
    got = DefensiveContributionTerm().validate(panel).table.set_index("position")
    for pos in got.index:
        ref_model = ref.xs(pos, level="position").loc["DC logistic P(hit)", "spearman"]
        assert got.loc[pos, "p_dc_hit"] == pytest.approx(ref_model, abs=1e-9)


def test_emit_returns_single_term_and_check_assumptions() -> None:
    model = DefensiveContributionModel()
    fitted = model.fit(_panel(seed=2))
    assert isinstance(fitted, Fitted)
    assert set(model.emit(fitted)) == {"defensive_contribution"}
    report = model.check_assumptions(DefensiveContributionModel.population(_panel(seed=2)))
    assert isinstance(report, AssumptionReport)
    assert report.dispersion["family"] == "binomial"
    assert isinstance(report.detectable, bool)


def test_validate_scores_def_mid_fwd_only() -> None:
    res = DefensiveContributionTerm().validate(_panel(seed=1))
    assert isinstance(res, GateResult)
    assert set(res.table["position"]).issubset({"DEF", "MID", "FWD"})  # GK exempt
    assert {"baseline", "p_dc_hit", "delta"} <= set(res.table.columns)
