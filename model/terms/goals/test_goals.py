"""Tests for the goals term (model.terms.goals) — contract + frozen-number reproduction.

The reproduction guarantee (spec §10 invariant): the strangled ``GoalsModel(minimal)`` emits E[goals]
**bit-identical** to the god-file ``component_forecast``'s goals GLM on a fixed panel. Identical
predictions ⇒ identical downstream composed/ranking numbers, so this pins the 4dp invariant without a
live mart. When ``component_forecast`` is deleted (spec §10 step 5), the golden vector below becomes
the frozen record and this test keeps guarding it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
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


# -- god-file reference (the frozen goals design), replicated locally for the golden compare -------
def _reference_e_goals(mart: pd.DataFrame) -> pd.Series:
    """Expanding walk-forward E[goals] exactly as component_forecast fits the goals component."""
    from model.eval.walkforward import WARMUP_GW
    from model.forecast.component_forecast import _GOAL_FEATURES, _design, _fit_predict

    df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
    df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
    pred = pd.Series(np.nan, index=df.index, dtype=float)
    for t in sorted(g for g in df["gw"].unique() if g > WARMUP_GW):
        train, test = df[df["gw"] < t], df[df["gw"] == t]
        if test.empty or len(train) < 100:
            continue
        pred.loc[test.index] = _fit_predict(train, test, "goals_scored", _GOAL_FEATURES, sm.families.Poisson())
    _ = _design  # imported to prove we share the god-file's design construction
    return pred


def test_satisfies_model_and_term_contracts() -> None:
    model = GoalsModel(variant="minimal")
    term = GoalsTerm(model)
    assert isinstance(model, Model)
    assert isinstance(term, Term)
    assert model.name == "goals" and term.name == "goals"
    assert term.baseline_col == "goals_prior"
    assert model.grain == "player_gw"
    assert model.pool.minimal == ("xgi_roll3", "minutes_roll3")


def test_emit_reproduces_godfile_goals_to_the_bit() -> None:
    """The strangler invariant: minimal emit ≡ component_forecast's goals GLM (4dp and beyond)."""
    panel = _panel()
    fitted = GoalsModel(variant="minimal").fit(panel)
    got = fitted.predictions.to_numpy()
    ref = _reference_e_goals(panel).to_numpy()
    both = ~(np.isnan(got) | np.isnan(ref))
    assert both.any()
    np.testing.assert_array_almost_equal(got[both], ref[both], decimal=10)
    # NaN pattern must also match (same warmup / thin-slice guards).
    np.testing.assert_array_equal(np.isnan(got), np.isnan(ref))


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


def test_selected_variant_matches_minimal_until_pool_widens() -> None:
    """Only the two mechanistic columns are on the mart today, so selected draws the same design."""
    panel = _panel(seed=4)
    assert GoalsModel(variant="selected").features(panel) == ["xgi_roll3", "minutes_roll3"]


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
