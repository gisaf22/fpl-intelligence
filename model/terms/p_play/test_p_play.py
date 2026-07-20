"""Tests for the P(play) term (model.terms.p_play) — structural + seed (Fork D: no god-file golden).

Captaincy's old inline ``_p_play`` was a *pooled*, crude logistic, so this per-position term is a
deliberate replacement, not a bit-identical reproduction. It is therefore pinned as a normal gated term:
the contract, that it scores the blank (``minutes==0``) rows and trains on them, that it *learns* the
availability signal (nailed starters out-score rotation risks), and that the fit is deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import AssumptionReport, Fitted, GateResult, Model, Term
from model.terms.p_play import PlayModel, PlayTerm

pytestmark = pytest.mark.unit

_POS = ("GK", "DEF", "MID", "FWD")


def _panel(n_players: int = 80, n_gw: int = 14, seed: int = 0) -> pd.DataFrame:
    """A player-GW panel with real blanks: even players are *nailed* (~0.92 appearance), odd players
    *rotation risks* (~0.5). Lagged minutes/start form tracks the archetype, so the model has signal."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = _POS[p % 4]
        nailed = p % 2 == 0
        p_appear = 0.92 if nailed else 0.5
        for gw in range(1, n_gw + 1):
            played = rng.random() < p_appear
            minutes = int(rng.choice([30, 90], p=[0.15, 0.85])) if played else 0
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": minutes, "is_dgw": False,
                "starts": int(minutes >= 60),
                "minutes_roll3": (75.0 if nailed else 40.0) + rng.normal(0, 5),
                "minutes_roll5": (75.0 if nailed else 40.0) + rng.normal(0, 5),
            })
    return pd.DataFrame(rows)


def test_satisfies_model_and_term_contracts() -> None:
    model = PlayModel(variant="selected")
    term = PlayTerm(model)
    assert isinstance(model, Model)
    assert isinstance(term, Term)
    assert model.name == "p_play" and term.name == "p_play"
    assert model.target == "played"
    assert model.term == "p_play"
    assert term.baseline_col == "minutes_roll3"
    assert model.grain == "player_gw"
    # P(play) is a genuine split at every position (no GK override) and trains on the blank rows.
    assert model.logit_positions == _POS
    assert model.trains_on_appearances_only is False
    assert model.pool.minimal == ("minutes_roll3", "starts_roll3")


def test_population_is_the_whole_universe_with_the_played_target() -> None:
    panel = _panel()
    pop = PlayModel.population(panel)
    # blanks are retained (unlike every conditional-on-appearance term) ...
    assert (pop["minutes"] == 0).sum() > 0
    # ... and the derived target is exactly 1{minutes>0}.
    np.testing.assert_array_equal(pop["played"].to_numpy(), (pop["minutes"] > 0).astype(float).to_numpy())
    assert set(np.unique(pop["played"])) == {0.0, 1.0}


def test_population_excludes_no_fixture_rows_and_keeps_played_clean() -> None:
    """No-fixture rows (nullable-Int64 ``minutes`` == NA: blank GW / unregistered) are not appearance
    decisions — dropping them keeps ``played`` a clean 0/1 (else ``(NA>0).astype(float)`` leaks NaN and
    poisons the gate). Regression for the real-mart bug where blank-GW rows made per-cell Spearman NaN."""
    panel = _panel()
    panel["minutes"] = panel["minutes"].astype("Int64")
    panel.loc[panel["gw"].isin([8, 9]) & (panel["player_id"] % 3 == 0), "minutes"] = pd.NA  # no-fixture rows
    pop = PlayModel.population(panel)
    assert pop["minutes"].notna().all()                     # no-fixture rows dropped
    assert pop["played"].notna().all()                      # target is clean 0/1, never NaN
    assert set(np.unique(pop["played"])) == {0.0, 1.0}


def test_fit_scores_the_blank_rows_as_probabilities() -> None:
    panel = _panel(seed=1)
    model = PlayModel(variant="selected")
    pop = model.population(panel)
    pred = model.fit(panel).predictions
    scored = pop.assign(p=pred.to_numpy())
    scored = scored[scored["gw"] > 3]
    # every position is scored (GK included — no override leaves it NaN), on blanks and appearances alike.
    blanks = scored[(scored["minutes"] == 0) & scored["p"].notna()]
    assert len(blanks) > 0
    assert set(scored.dropna(subset=["p"])["position"].unique()) == set(_POS)
    valid = scored["p"].dropna().to_numpy()
    assert ((valid >= 0.0) & (valid <= 1.0)).all()


def test_learns_the_availability_signal_nailed_above_rotation() -> None:
    """The point of the term: a nailed starter gets a higher P(play) than a rotation risk."""
    panel = _panel(seed=2)
    model = PlayModel(variant="selected")
    pop = model.population(panel).assign(p=model.fit(panel).predictions.to_numpy())
    ev = pop[(pop["gw"] > 3) & pop["p"].notna()]
    nailed = ev[ev["player_id"] % 2 == 0]["p"].mean()
    rotation = ev[ev["player_id"] % 2 == 1]["p"].mean()
    assert nailed > rotation + 0.1


def test_validate_scores_model_vs_lagged_minutes_baseline() -> None:
    res = PlayTerm().validate(_panel(seed=3))
    assert isinstance(res, GateResult)
    assert res.term == "p_play"
    assert {"position", "baseline", "p_play", "delta"} <= set(res.table.columns)
    # the view column in the gate table holds the within-position Spearman (a correlation, not a prob).
    assert res.table["p_play"].between(-1, 1).all()
    assert set(res.passed).issubset(set(_POS))


def test_check_assumptions_reports_class_balance() -> None:
    report = PlayModel().check_assumptions(PlayModel.population(_panel(seed=4)))
    assert isinstance(report, AssumptionReport)
    assert report.term == "p_play"
    assert report.n_train > 0
    assert report.dispersion["family"] == "binomial"
    assert isinstance(report.detectable, bool)


def test_fit_is_deterministic() -> None:
    panel = _panel(seed=5)
    a = PlayModel(variant="selected").fit(panel).predictions.to_numpy()
    b = PlayModel(variant="selected").fit(panel).predictions.to_numpy()
    assert isinstance(PlayModel().fit(panel), Fitted)
    np.testing.assert_array_equal(a, b)
