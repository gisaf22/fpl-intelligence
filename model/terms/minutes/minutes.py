"""The minutes Model + Term (spec §2) — strangled from ``points_model.walk_forward_minutes_hurdle``.

Minutes is a **gate**, not a smooth covariate: appearance scores 1 (1-59') / 2 (>=60'), and the
clean-sheet term is only awarded at >=60'. Within the conditional-on-appearance population (minutes>0),
this models **P(>=60' | played)** = ``p60``. Outfield uses a per-position logistic on lagged minutes form
(shared base); **GK are overridden** with a robust lagged expanding rate of ``play60`` — GK play >=60'
~99% of the time, so the logistic is degenerate there.

``selected`` (the full pool) reproduces ``walk_forward_minutes_hurdle`` to the bit. The emitted ``p60``
maps to appearance points (``1 + p60``) and gates clean_sheet — both compose-layer concerns, so the term
emits the raw probability.
"""

from __future__ import annotations

import pandas as pd

from model.terms._base import Hypothesis
from model.terms._binary_component import BinaryComponentTerm, BinaryPerPositionComponent
from model.terms.minutes.spec import MINUTES_POOL

# GK fallback when a keeper has no prior history at all (matches the god-file's backfill constant).
_GK_PRIOR_PLAY60 = 0.98


def _lag_roll(df: pd.DataFrame, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean per player (shift(1) before rolling -> excludes current row)."""
    return df.groupby("player_id")[src].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


class MinutesHurdleModel(BinaryPerPositionComponent):
    """Per-position logistic P(>=60' | played), with a robust-rate GK override (the fittable unit)."""

    name = "minutes"
    target = "play60"                        # DERIVED binary: 1{minutes >= 60}
    term = "p60"                             # the emitted view: P(>=60' | played)
    pool = MINUTES_POOL
    logit_positions = ("DEF", "MID", "FWD")  # GK handled by _fill_special
    hypotheses = (
        Hypothesis(
            claim="the P(>=60') hurdle calibrates the appearance/CS gate better than a raw lagged minutes level",
            test="within-position Spearman of p60 vs play60 beside minutes_roll3, GW>3",
            success_threshold="calibrated probability (outfield ranking ~parity; GK near-constant)",
            status="supported-as-calibration (phase3 minutes hurdle; ranking parity is expected, not a miss)",
        ),
    )

    @staticmethod
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """All-position rows (minutes>0, DGW excluded) with lagged starts + the derived ``play60`` target.

        Mirrors ``walk_forward_minutes_hurdle`` exactly (``minutes_roll{3,5,8}`` come from the mart; only
        ``starts_roll3`` is built here) so the selected draw reproduces its output. GK rows are retained —
        the override needs them.
        """
        df = mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))].copy()
        df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
        for c in ["minutes_roll3", "minutes_roll5", "minutes_roll8", "minutes", "starts"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["starts_roll3"] = _lag_roll(df, "starts", 3)
        df["play60"] = (df["minutes"] >= 60).astype(float)
        return df

    def _fill_special(self, df: pd.DataFrame, pred: pd.Series) -> None:
        """GK override: a robust prior-only expanding rate of play60, backfilled with the global GK rate.

        GK play >=60' ~99% of the time (near-constant), so a logistic is degenerate; a shrinkage-style
        lagged rate is the honest estimator. Reproduces the god-file's GK branch exactly.
        """
        gk = df["position"] == "GK"
        prior_rate = df.groupby("player_id")["play60"].transform(lambda s: s.shift(1).expanding().mean())
        global_prior = df.loc[gk, "play60"].shift(1).expanding().mean()
        pred.loc[gk] = prior_rate[gk].fillna(global_prior).fillna(_GK_PRIOR_PLAY60)


class MinutesTerm(BinaryComponentTerm):
    """The minutes term — p60 = P(>=60') scored vs the lagged ``minutes_roll3`` baseline (spec §5)."""

    name = "minutes"
    baseline_col = "minutes_roll3"
    view_col = "p60"
    _model_cls = MinutesHurdleModel
    # All four positions are scored (GK near-constant — ranking is near-meaningless but reported honestly).
