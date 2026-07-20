"""The P(play) Model + Term (spec §2, X1 blank-tail) — the appearance gate that unconditions compose.

**P(play)** = P(minutes>0): the probability a player features at all, *before* the ``minutes`` term's
P(>=60' | played). The unconditional points identity is one clean factor out front::

    E[points]_unconditional = P(play) * E[points | played]

where ``E[points | played]`` is today's compose output. ``compose`` (keep_all mode) owns that multiply;
this module owns only the appearance probability.

P(play) rides the shared :class:`~model.terms._binary_component.BinaryPerPositionComponent` (a
per-position logistic of a derived binary target) but differs from every other binary term in **two**
ways, both because it *is* the appearance model rather than a conditional-on-appearance one:

* its **population is the whole universe** (blanks included) — the target ``played`` needs the 0-minute
  rows; and
* it **trains on those blank rows** (``trains_on_appearances_only = False``) — filtering to ``minutes>0``
  would leave ``played`` all-ones (one class) and collapse the logistic.

All four positions are fit by logistic (``logit_positions`` = every position): unlike the p60 hurdle
(GK play >=60' ~always → near-constant → the GK ``_fill_special`` override), P(play) is a genuine
starters-vs-backups split for GK too, so **no override**. There is no god-file golden (captaincy's old
inline ``_p_play`` was pooled + crude); P(play) is validated as a normal gated term (see ``ASSUMPTIONS.md``).
"""

from __future__ import annotations

import pandas as pd

from model.terms._base import Hypothesis
from model.terms._binary_component import BinaryComponentTerm, BinaryPerPositionComponent
from model.terms.p_play.spec import PLAY_POOL


def _lag_roll(df: pd.DataFrame, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean per player (shift(1) before rolling -> excludes current row)."""
    return df.groupby("player_id")[src].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


class PlayModel(BinaryPerPositionComponent):
    """Per-position logistic P(play) = P(minutes>0) on lagged availability form (the fittable unit)."""

    name = "p_play"
    target = "played"                        # DERIVED binary: 1{minutes > 0}
    term = "p_play"                          # the emitted view: P(play)
    pool = PLAY_POOL
    logit_positions = ("GK", "DEF", "MID", "FWD")  # all four — a real split for GK too (no override)
    trains_on_appearances_only = False       # P(play) must learn from the blank (played==0) rows
    hypotheses = (
        Hypothesis(
            claim="lagged minutes + start form rank who features next GW better than a lagged minutes level alone",
            test="within-position Spearman of P(play) vs played beside minutes_roll3, GW>3, all positions",
            success_threshold="calibrated appearance probability; ranking >= the lagged-minutes baseline",
            status="new term (X1 blank tail) — replaces captaincy's pooled inline _p_play (per-position upgrade)",
        ),
    )

    @staticmethod
    def population(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
        """The **whole** universe (DGW excluded): all rows incl. ``minutes==0``, with lagged starts + target.

        P(play) is the appearance model itself, so — unlike every conditional-on-appearance term — the
        population is *always* the widest one (the target ``played`` is defined by the blank rows). The
        ``keep_all`` flag is accepted for base-signature parity but does not change this: the population is
        already the full universe. ``minutes_roll{3,5}`` come from the mart; only ``starts_roll3`` is built.
        """
        df = mart[~mart["is_dgw"].astype(bool)].copy()
        df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
        for c in ["minutes_roll3", "minutes_roll5", "minutes", "starts"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["starts_roll3"] = _lag_roll(df, "starts", 3)
        df["played"] = (df["minutes"] > 0).astype(float)
        return df


class PlayTerm(BinaryComponentTerm):
    """The P(play) term — P(play) scored vs the lagged ``minutes_roll3`` availability baseline (spec §5)."""

    name = "p_play"
    baseline_col = "minutes_roll3"
    view_col = "p_play"
    _model_cls = PlayModel
    # All four positions are scored (P(play) is a real split at every position, GK included).
