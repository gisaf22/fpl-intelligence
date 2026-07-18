"""Tests for the minutes term (model.terms.minutes) — contract + frozen-number reproduction.

Reproduction invariant (spec §10): ``MinutesHurdleModel(selected)`` emits ``p60`` **bit-identical** to
the god-file ``walk_forward_minutes_hurdle`` — including the GK robust-rate override — and the term's
gate reproduces ``minutes_hurdle_validation``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._base import Fitted, GateResult, Model, Term
from model.terms._binary_component import BinaryPerPositionComponent
from model.terms.minutes import MinutesHurdleModel, MinutesTerm

pytestmark = pytest.mark.unit


def _panel(seed: int = 0, n_per_pos: int = 40, n_gw: int = 16) -> pd.DataFrame:
    """All-position panel: outfield start-probability varies (both play60 classes); GK near-always start."""
    rng = np.random.default_rng(seed)
    rows = []
    pid = 0
    for pos in ("GK", "DEF", "MID", "FWD"):
        for _ in range(n_per_pos):
            p_start = rng.uniform(0.97, 0.99) if pos == "GK" else rng.uniform(0.45, 0.95)
            for gw in range(1, n_gw + 1):
                started = rng.random() < p_start
                minutes = 90 if started else int(rng.choice([15, 30, 45]))
                rows.append({
                    "player_id": pid, "gw": gw, "position": pos, "minutes": minutes, "is_dgw": False,
                    "starts": int(started), "total_points": 2.0,
                })
            pid += 1
    df = pd.DataFrame(rows).sort_values(["player_id", "gw"]).reset_index(drop=True)
    # minutes_roll{3,5,8} are mart columns the god-file reads as-is; build lag-safe versions here.
    for w in (3, 5, 8):
        df[f"minutes_roll{w}"] = df.groupby("player_id")["minutes"].transform(
            lambda s, w=w: s.shift(1).rolling(w, min_periods=1).mean()
        )
    return df


def test_satisfies_contracts_and_shape() -> None:
    model = MinutesHurdleModel(variant="selected")
    term = MinutesTerm(model)
    assert isinstance(model, Model) and isinstance(term, Term)
    assert issubclass(MinutesHurdleModel, BinaryPerPositionComponent)
    assert model.name == "minutes" and model.target == "play60" and model.term == "p60"
    assert term.baseline_col == "minutes_roll3" and term.view_col == "p60"
    assert model.logit_positions == ("DEF", "MID", "FWD")  # GK handled by the override


def test_selected_emit_reproduces_walk_forward_minutes_hurdle_to_the_bit() -> None:
    from model.forecast.points_model import walk_forward_minutes_hurdle

    panel = _panel()
    fitted = MinutesHurdleModel(variant="selected").fit(panel)
    got = MinutesHurdleModel.population(panel).assign(p=fitted.predictions.to_numpy())
    got = got[["player_id", "gw", "position", "p"]]
    ref = walk_forward_minutes_hurdle(panel)[["player_id", "gw", "p60"]]
    merged = got.merge(ref, on=["player_id", "gw"])
    assert len(merged) == len(got)
    both = ~(merged["p"].isna() | merged["p60"].isna())
    assert both.any()
    np.testing.assert_array_almost_equal(merged.loc[both, "p"].to_numpy(),
                                         merged.loc[both, "p60"].to_numpy(), decimal=10)
    np.testing.assert_array_equal(merged["p"].isna().to_numpy(), merged["p60"].isna().to_numpy())


def test_gk_override_is_the_robust_rate_not_a_logistic() -> None:
    """GK p60 must match the prior-only expanding play60 rate (the special-cased branch), not a GLM."""
    panel = _panel(seed=5)
    pop = MinutesHurdleModel.population(panel)
    fitted = MinutesHurdleModel(variant="selected").fit(panel)
    pop = pop.assign(p=fitted.predictions.to_numpy())
    gk = pop[pop["position"] == "GK"]
    assert gk["p"].notna().all()                 # every GK row filled (backfilled), no NaN gaps
    assert (gk["p"].between(0.0, 1.0)).all()


def test_gate_reproduces_minutes_hurdle_validation() -> None:
    from model.forecast.points_model import minutes_hurdle_validation

    panel = _panel()
    ref = minutes_hurdle_validation(panel)  # indexed (position, model)
    got = MinutesTerm().validate(panel).table.set_index("position")
    for pos in got.index:
        ref_model = ref.xs(pos, level="position").loc["P(>=60') hurdle", "spearman"]
        got_val = got.loc[pos, "p60"]
        if pd.isna(ref_model):
            assert pd.isna(got_val)
        else:
            assert got_val == pytest.approx(ref_model, abs=1e-9)


def test_validate_covers_all_positions_and_emit_single_view() -> None:
    model = MinutesHurdleModel()
    fitted = model.fit(_panel(seed=2))
    assert isinstance(fitted, Fitted)
    assert set(model.emit(fitted)) == {"p60"}
    res = MinutesTerm().validate(_panel(seed=2))
    assert isinstance(res, GateResult)
    assert set(res.table["position"]).issubset({"GK", "DEF", "MID", "FWD"})
