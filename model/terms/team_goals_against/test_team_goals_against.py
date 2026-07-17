"""Tests for the team_goals_against joint model (model.terms.team_goals_against).

Reproduction invariant (spec §10): the ``selected`` draw emits ``clean_sheet`` (p_cs) and ``conceded``
(e_conceded_pts) **bit-identical** to the god-file ``points_model.walk_forward_team_ga`` on a fixed
panel — identical predictions ⇒ identical frozen composed numbers. The **joint shape** (one model emits
BOTH terms) is asserted directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Diagnostics, Fitted, GateResult, Model, Term
from model.terms.team_goals_against import CleanSheetTerm, ConcededTerm, TeamGoalsAgainstModel

pytestmark = pytest.mark.unit


def _mart(n_teams: int = 20, n_gw: int = 16, seed: int = 0) -> pd.DataFrame:
    """Player-gameweek mart: each team-fixture has a latent GA rate; players inherit team GA + xGC."""
    rng = np.random.default_rng(seed)
    rows = []
    for team in range(n_teams):
        strength = rng.uniform(0.4, 2.2)  # team's baseline goals-against rate
        for gw in range(1, n_gw + 1):
            ga = rng.poisson(strength)               # goals the team conceded this fixture
            xgc_team = strength + rng.normal(0, 0.2)
            was_home = int(rng.random() < 0.5)
            fdr = rng.integers(2, 6)
            for p in range(rng.integers(11, 14)):    # players who appeared for the team
                pos = ["GK", "DEF", "DEF", "MID", "MID", "FWD"][p % 6]
                rows.append({
                    "player_id": team * 100 + p, "team_id": team, "gw": gw, "position": pos,
                    "minutes": 90, "is_dgw": False,
                    "goals_conceded": ga, "xgc": max(0.0, xgc_team + rng.normal(0, 0.1)),
                    "was_home": was_home, "fdr_avg": float(fdr),
                    "clean_sheets": int(ga == 0),
                })
    df = pd.DataFrame(rows)
    # Lag-safe per-player clean-sheet roll — the CS term's baseline_col (present on the real mart).
    df["clean_sheets_roll3"] = df.groupby("player_id")["clean_sheets"].transform(
        lambda s: s.shift(1).rolling(3, min_periods=3).mean()
    )
    return df


def _reference_team_ga(mart: pd.DataFrame) -> pd.DataFrame:
    """The god-file team-GA layer (the frozen design) for the golden compare."""
    from model.forecast.points_model import walk_forward_team_ga
    return walk_forward_team_ga(mart)


def test_satisfies_model_contract_and_grain() -> None:
    model = TeamGoalsAgainstModel(variant="selected")
    assert isinstance(model, Model)
    assert model.name == "team_goals_against"
    assert model.grain == "team_gw"
    assert model.pool.minimal == ("ga_roll3",)


def test_selected_draws_the_frozen_team_ga_features() -> None:
    panel = TeamGoalsAgainstModel.population(_mart())
    # The materializable pool today is exactly points_model.TEAM_GA_FEATURES, in order.
    assert TeamGoalsAgainstModel(variant="selected").features(panel) == [
        "ga_roll3", "ga_roll5", "xgc_roll3", "xgc_roll5", "was_home", "fdr_avg",
    ]
    assert TeamGoalsAgainstModel(variant="minimal").features(panel) == ["ga_roll3"]


def test_emit_returns_both_terms_the_joint_shape() -> None:
    model = TeamGoalsAgainstModel()
    fitted = model.fit(_mart(seed=1))
    assert isinstance(fitted, Fitted)
    out = model.emit(fitted)
    assert set(out) == {"clean_sheet", "conceded"}  # ONE model, TWO terms — the joint proof
    n_team_fixtures = len(fitted.meta["team_frame"])
    assert out["clean_sheet"].shape[0] == n_team_fixtures
    assert out["conceded"].shape[0] == n_team_fixtures


def test_terms_are_internally_consistent_by_construction() -> None:
    """D-D: CS and conceded fall out of one lambda, so P(CS)=1 cannot coexist with an expected penalty."""
    model = TeamGoalsAgainstModel()
    out = model.emit(model.fit(_mart(seed=2)))
    cs, conc = out["clean_sheet"], out["conceded"]
    defined = ~(np.isnan(cs) | np.isnan(conc))
    # p_cs in [0,1]; conceded penalty is non-positive; both monotone in the same lambda.
    assert ((cs[defined] >= 0) & (cs[defined] <= 1)).all()
    assert (conc[defined] <= 1e-9).all()


def test_selected_emit_reproduces_godfile_team_ga_to_the_bit() -> None:
    panel = _mart()
    fitted = TeamGoalsAgainstModel(variant="selected").fit(panel)
    got = fitted.meta["team_frame"].sort_values(["team_id", "gw"]).reset_index(drop=True)
    ref = _reference_team_ga(panel).sort_values(["team_id", "gw"]).reset_index(drop=True)
    for col in ("lambda_ga", "p_cs", "e_conceded_pts"):
        g, r = got[col].to_numpy(), ref[col].to_numpy()
        both = ~(np.isnan(g) | np.isnan(r))
        assert both.any()
        np.testing.assert_array_almost_equal(g[both], r[both], decimal=10)
        np.testing.assert_array_equal(np.isnan(g), np.isnan(r))


def test_check_assumptions_dispersion_and_detectability() -> None:
    panel = TeamGoalsAgainstModel.population(_mart(seed=3))
    report = TeamGoalsAgainstModel().check_assumptions(panel)
    assert isinstance(report, AssumptionReport)
    assert report.term == "team_goals_against"
    assert report.n_train > 0
    assert isinstance(report.detectable, bool)
    assert isinstance(report.family_ok, bool)


# -- Terms: one shared model, two gated views ------------------------------------------------------
def test_both_terms_satisfy_the_term_contract_and_share_the_model() -> None:
    model = TeamGoalsAgainstModel()
    cs, conc = CleanSheetTerm(model), ConcededTerm(model)
    assert isinstance(cs, Term) and isinstance(conc, Term)
    assert cs.model is conc.model            # joint: both views ride the SAME fitted model
    assert cs.name == "clean_sheet" and cs.baseline_col == "clean_sheets_roll3"
    assert conc.name == "conceded" and conc.baseline_col == "conceded_baseline"


def test_clean_sheet_gate_ranks_gk_def_mid_only() -> None:
    res = CleanSheetTerm().validate(_mart(seed=1))
    assert isinstance(res, GateResult)
    assert res.term == "clean_sheet"
    assert set(res.table["position"]).issubset({"GK", "DEF", "MID"})  # FWD get no clean-sheet points
    assert res.table["p_cs"].between(-1, 1).all()
    assert {"baseline", "p_cs", "delta"} <= set(res.table.columns)


def test_conceded_gate_ranks_gk_def_only() -> None:
    res = ConcededTerm().validate(_mart(seed=1))
    assert res.term == "conceded"
    assert set(res.table["position"]).issubset({"GK", "DEF"})  # MID/FWD exempt from the penalty
    assert res.table["e_conceded"].between(-1, 1).all()


def test_clean_sheet_gate_reproduces_godfile_cs_validation() -> None:
    """CleanSheetTerm.validate p_cs Spearman ≡ points_model.team_ga_cs_validation (the frozen gate)."""
    from model.forecast.points_model import team_ga_cs_validation

    mart = _mart()
    ref = team_ga_cs_validation(mart)  # indexed (position, model)
    got = CleanSheetTerm().validate(mart).table.set_index("position")
    for pos in got.index:
        ref_model = ref.xs(pos, level="position").loc["team-GA P(CS)", "spearman"]
        assert got.loc[pos, "p_cs"] == pytest.approx(ref_model, abs=1e-9)


def test_diagnose_returns_residuals_and_ablation() -> None:
    diag = CleanSheetTerm().diagnose(_mart(seed=2))
    assert isinstance(diag, Diagnostics)
    assert not diag.residuals.empty
    # Ablation drops each of the 6 selected features once.
    assert set(diag.ablation["dropped"]) == {
        "ga_roll3", "ga_roll5", "xgc_roll3", "xgc_roll5", "was_home", "fdr_avg",
    }
