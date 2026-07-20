"""Base-contract tests for the ``keep_all`` blank-tail flag on both term bases (spec X1; P(play) slice).

``keep_all=True`` widens a term's population to potential-blank (``minutes==0``) rows so the ex-ante
universe can be scored, while TRAIN stays filtered to ``minutes>0`` (the fit is unchanged; only the
prediction set grows). These tests pin the two halves of that contract on **both** bases:

* the extra ``minutes==0`` rows get scored (non-NaN) — the universe genuinely widens; and
* on the shared ``minutes>0`` rows, a model whose design features are pre-existing mart columns (so the
  widening does not perturb any recomputed roll) predicts **bit-identically** to ``keep_all=False`` —
  i.e. it trains on the same played rows.

The reproducibility invariant only protects the ``keep_all=False`` default path (verified across the
existing per-term goldens); ``keep_all=True`` is a *distinct universe* wherever a term rebuilds rolls
after the ``minutes>0`` filter (goals xg_roll, dc dc_roll, minutes starts_roll) — that shared-row
divergence is **by design** (it matches the DAL rolls + the god-file ``predict_all``) and is not asserted
here. The probes below deliberately use only mart-column features to isolate the base contract.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from model.terms._binary_component import BinaryPerPositionComponent
from model.terms.goals import GoalsModel

pytestmark = pytest.mark.unit

_POS = ("GK", "DEF", "MID", "FWD")


def _blank_panel(n_players: int = 120, n_gw: int = 14, seed: int = 0) -> pd.DataFrame:
    """A player-GW panel carrying real ``minutes==0`` (potential-blank) rows.

    Every 4th player sits out GW 8-9 (minutes 0); the rest play. Features are pre-existing mart columns
    (``xgi_roll3``/``minutes_roll3``) — no ``xg``/``xa`` source column, so ``add_lagged_rolls`` is a no-op
    and the widening cannot perturb any recomputed roll (isolating the base contract).
    """
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = _POS[p % 4]
        skill = rng.uniform(0.02, 0.4)
        for gw in range(1, n_gw + 1):
            blank = (p % 4 == 0) and gw in (8, 9)
            minutes = 0 if blank else int(rng.choice([30, 90], p=[0.2, 0.8]))
            rows.append({
                "player_id": p, "gw": gw, "position": pos, "minutes": minutes, "is_dgw": False,
                "xgi_roll3": skill + rng.normal(0, 0.05),
                "minutes_roll3": rng.uniform(20, 90),
                "goals_scored": 0 if blank else rng.poisson(skill),
            })
    return pd.DataFrame(rows)


def _keyed_predictions(pop: pd.DataFrame, pred: pd.Series) -> pd.DataFrame:
    """Align a fit's predictions back to (player_id, gw, minutes) so True/False panels can be joined."""
    out = pop[["player_id", "gw", "minutes"]].copy()
    out["pred"] = pred.to_numpy()
    return out


# --- Poisson base (via GoalsModel, minimal — mart-column features) --------------------------------
def test_poisson_keep_all_scores_blanks_and_matches_played_rows() -> None:
    panel = _blank_panel()
    model = GoalsModel(variant="minimal")
    off = _keyed_predictions(model.population(panel, keep_all=False), model.fit(panel, keep_all=False).predictions)
    on = _keyed_predictions(model.population(panel, keep_all=True), model.fit(panel, keep_all=True).predictions)

    # (1) blank rows exist only in the widened universe and get scored there (post-warmup ones non-NaN).
    assert (off["minutes"] == 0).sum() == 0                      # default path drops blanks entirely
    scored_blanks = on[(on["minutes"] == 0) & on["pred"].notna()]
    assert len(scored_blanks) > 0

    # (2) shared minutes>0 rows: identical fit ⇒ bit-identical predictions (trains on the same played set).
    merged = off.merge(on, on=["player_id", "gw"], suffixes=("_off", "_on"))
    both = merged[merged["pred_off"].notna() & merged["pred_on"].notna()]
    assert len(both) > 0
    np.testing.assert_array_equal(both["pred_off"].to_numpy(), both["pred_on"].to_numpy())


# --- Binary base (via a mart-column probe subclass) -----------------------------------------------
class _BinaryProbe(BinaryPerPositionComponent):
    """Minimal per-position logistic on a mart column — isolates the base ``keep_all`` contract.

    Feature is the pre-existing ``minutes_roll3`` (never recomputed from the panel), target is the derived
    ``play60`` = 1{minutes>=60}; all four positions fit by logistic. Because the design column is untouched
    by the widening, the shared-row predictions must match across ``keep_all``.
    """

    name = "keepall_probe"
    target = "play60"
    term = "p_probe"
    logit_positions = _POS

    def __init__(self) -> None:
        super().__init__(feature_override=["minutes_roll3"])

    @staticmethod
    def population(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
        keep = ~mart["is_dgw"].astype(bool) if keep_all else (mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))
        df = mart[keep].copy().sort_values(["player_id", "gw"]).reset_index(drop=True)
        df["minutes_roll3"] = pd.to_numeric(df["minutes_roll3"], errors="coerce")
        df["play60"] = (df["minutes"] >= 60).astype(float)
        return df


def test_binary_keep_all_scores_blanks_and_matches_played_rows() -> None:
    panel = _blank_panel(seed=1)
    model = _BinaryProbe()
    off = _keyed_predictions(model.population(panel, keep_all=False), model.fit(panel, keep_all=False).predictions)
    on = _keyed_predictions(model.population(panel, keep_all=True), model.fit(panel, keep_all=True).predictions)

    assert (off["minutes"] == 0).sum() == 0
    scored_blanks = on[(on["minutes"] == 0) & on["pred"].notna()]
    assert len(scored_blanks) > 0

    merged = off.merge(on, on=["player_id", "gw"], suffixes=("_off", "_on"))
    both = merged[merged["pred_off"].notna() & merged["pred_on"].notna()]
    assert len(both) > 0
    np.testing.assert_array_equal(both["pred_off"].to_numpy(), both["pred_on"].to_numpy())
