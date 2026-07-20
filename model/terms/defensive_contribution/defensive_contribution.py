"""The defensive-contribution Model + Term (spec §2) — strangled from ``points_model.walk_forward_dc``.

DC scores +2 when a player clears their position's action threshold (DEF >= 10 CBIT; MID/FWD >= 12 CBIRT;
GK exempt). Per D-A, DC is conditionally independent of conceding/CS given minutes, so it is a
**standalone** component: a **logistic** GLM of the derived binary ``dc_hit`` on lagged DC-action form +
minutes + fixture context, fit **per position**, then ``E[DC points] = DC_POINTS * P(hit)``.

Shares the per-position-logistic machinery with ``minutes`` via
:class:`~model.terms._binary_component.BinaryPerPositionComponent`; this module declares only what
differs — the derived ``dc_hit`` target (built in :meth:`population`) and the pool. ``selected`` (the full
pool) reproduces ``walk_forward_dc`` to the bit; the x DC_POINTS conversion is a compose-layer step, so
the term emits the raw ``P(hit)``.
"""

from __future__ import annotations

import pandas as pd

from domain.fpl_scoring import DC_CBIRT_THRESHOLD_MID_FWD, DC_CBIT_THRESHOLD_DEF
from model.terms._base import Hypothesis
from model.terms._binary_component import BinaryComponentTerm, BinaryPerPositionComponent
from model.terms.defensive_contribution.spec import DC_POOL

# Per-position DC-action thresholds (GK exempt — no DC term). Carried from the god-file verbatim.
_DC_THRESHOLD = {"DEF": DC_CBIT_THRESHOLD_DEF, "MID": DC_CBIRT_THRESHOLD_MID_FWD, "FWD": DC_CBIRT_THRESHOLD_MID_FWD}
_DC_POSITIONS = ("DEF", "MID", "FWD")


def _lag_roll(df: pd.DataFrame, src: str, window: int) -> pd.Series:
    """Strictly-prior rolling mean per player (shift(1) before rolling -> excludes current row)."""
    return df.groupby("player_id")[src].transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())


class DefensiveContributionModel(BinaryPerPositionComponent):
    """Per-position logistic GLM of ``dc_hit`` on lagged DC form + context (the fittable unit)."""

    name = "defensive_contribution"
    target = "dc_hit"                        # DERIVED binary target (built in population)
    term = "defensive_contribution"
    pool = DC_POOL
    logit_positions = _DC_POSITIONS          # GK exempt
    hypotheses = (
        Hypothesis(
            claim="modelled P(DC hit) ranks realized DC hits better than the lagged DC-action count",
            test="within-position Spearman of p_dc_hit vs dc_hit beside dc_roll3, GW>3, DEF/MID/FWD",
            success_threshold="Δ Spearman > 0 at DEF (where DC is most material)",
            status="supported (phase3 DC component)",
        ),
    )

    @staticmethod
    def population(mart: pd.DataFrame, keep_all: bool = False) -> pd.DataFrame:
        """DEF/MID/FWD rows (minutes>0, DGW excluded) with lagged DC form + the derived ``dc_hit`` target.

        Mirrors ``points_model._add_dc_columns`` exactly so the selected draw reproduces its output. GK are
        excluded (no DC term); the per-player rolls are unaffected by that filter. ``keep_all=True`` widens
        to potential-blank rows (``dc_roll{3,5}`` then include those rows, by design); train stays ``minutes>0``.
        The ``keep_all`` universe is fixtures-only (NaN-minutes no-fixture rows excluded — not appearances).
        """
        outfield = (~mart["is_dgw"].astype(bool)) & (mart["position"].isin(_DC_POSITIONS))
        keep = outfield & mart["minutes"].notna() if keep_all else outfield & (mart["minutes"] > 0)
        df = mart[keep].copy()
        df = df.sort_values(["player_id", "gw"]).reset_index(drop=True)
        for c in ["defensive_contribution", "minutes_roll3", "fdr_avg"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["was_home"] = df["was_home"].astype(float)
        for w in (3, 5):
            df[f"dc_roll{w}"] = _lag_roll(df, "defensive_contribution", w)
        df["dc_threshold"] = df["position"].map(_DC_THRESHOLD)
        df["dc_hit"] = (df["defensive_contribution"] >= df["dc_threshold"]).astype(float)
        return df


class DefensiveContributionTerm(BinaryComponentTerm):
    """The DC term — P(hit) scored vs the lagged DC-action count baseline (spec §5, DEF/MID/FWD)."""

    name = "defensive_contribution"
    baseline_col = "dc_roll3"
    view_col = "p_dc_hit"
    _model_cls = DefensiveContributionModel
    positions = _DC_POSITIONS
