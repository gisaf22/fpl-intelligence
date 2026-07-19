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
from model.terms._freeze import assert_frozen
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


def test_selected_emit_reproduces_walk_forward_minutes_hurdle_frozen() -> None:
    """Frozen: selected p60 ≡ the (deleted) walk_forward_minutes_hurdle, including the GK override."""
    got = MinutesHurdleModel(variant="selected").fit(_panel()).predictions.to_numpy()
    assert_frozen(got, n_scored=2200, sum6=1720.667671,
                  spot_idx=[0, 440, 937, 1479, 2021],
                  spot_vals=[0.98, 1.0, 0.6539, 0.7013, 0.7949])


def test_gk_override_is_the_robust_rate_not_a_logistic() -> None:
    """GK p60 must match the prior-only expanding play60 rate (the special-cased branch), not a GLM."""
    panel = _panel(seed=5)
    pop = MinutesHurdleModel.population(panel)
    fitted = MinutesHurdleModel(variant="selected").fit(panel)
    pop = pop.assign(p=fitted.predictions.to_numpy())
    gk = pop[pop["position"] == "GK"]
    assert gk["p"].notna().all()                 # every GK row filled (backfilled), no NaN gaps
    assert (gk["p"].between(0.0, 1.0)).all()


def test_gate_reproduces_minutes_hurdle_validation_frozen() -> None:
    """Frozen: the term gate's per-position Spearman ≡ the (deleted) minutes_hurdle_validation."""
    got = MinutesTerm().validate(_panel()).table.set_index("position")
    frozen = {"GK": -0.0343, "DEF": 0.2452, "MID": 0.127, "FWD": 0.1727}
    for pos, want in frozen.items():
        assert round(float(got.loc[pos, "p60"]), 4) == want


def test_validate_covers_all_positions_and_emit_single_view() -> None:
    model = MinutesHurdleModel()
    fitted = model.fit(_panel(seed=2))
    assert isinstance(fitted, Fitted)
    assert set(model.emit(fitted)) == {"p60"}
    res = MinutesTerm().validate(_panel(seed=2))
    assert isinstance(res, GateResult)
    assert set(res.table["position"]).issubset({"GK", "DEF", "MID", "FWD"})
