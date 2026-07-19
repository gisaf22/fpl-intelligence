"""The assists Model + Term (spec §2) — strangled from ``component_forecast.py``, no behaviour change.

``AssistsModel`` fits ``assists`` one gameweek ahead with a Poisson GLM on lagged process stats,
expanding walk-forward — the same Poisson-player shape as goals, so all the machinery is inherited from
:class:`~model.terms._poisson_component.PoissonPlayerComponentModel`; only the target column and pool
differ. The golden test pins ``minimal`` ``emit`` bit-identical to ``component_forecast``'s assists GLM.
``AssistsTerm`` scores E[assists] against the term's own lagged-assists baseline (spec §5).
"""

from __future__ import annotations

import pandas as pd

from model.features.build import add_lagged_rolls
from model.terms._base import Hypothesis
from model.terms._poisson_component import PlayerComponentTerm, PoissonPlayerComponentModel
from model.terms.assists.spec import ASSISTS_POOL


class AssistsModel(PoissonPlayerComponentModel):
    """Poisson GLM of next-GW ``assists`` on lagged process stats (the fittable unit)."""

    name = "assists"
    target = "assists"
    term = "assists"
    pool = ASSISTS_POOL
    hypotheses = (
        Hypothesis(
            claim="lagged xGI ranks next-GW assists better than a player's lagged assists mean",
            test="within-position Spearman of emitted E[assists] vs assists_prior, GW>3, common eval set",
            success_threshold="Δ Spearman > 0 at MID (the primary creative position)",
            status="supported (phase2 component model: assists ~ xgi_roll3 + minutes_roll3)",
        ),
    )

    @staticmethod
    def population(mart: pd.DataFrame) -> pd.DataFrame:
        """Base player population + materialized lag-safe ``xa_roll3/5`` (the shipped ASSIST_FEATURES).

        ``minimal`` still draws only ``xgi_roll3 + minutes_roll3`` (unchanged, golden-pinned); building the
        extra rolls only widens what ``selected`` can draw. On a mart without ``xa`` the build is a no-op.
        """
        df = PoissonPlayerComponentModel.population(mart)
        return add_lagged_rolls(df, ["xa"], (3, 5))


class AssistsTerm(PlayerComponentTerm):
    """The ``assists`` term — E[assists] scored vs its own lagged-assists baseline (spec §5, per-term)."""

    name = "assists"
    baseline_col = "assists_prior"
    view_col = "e_assists"
    _model_cls = AssistsModel
