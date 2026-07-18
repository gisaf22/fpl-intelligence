"""The assists Model + Term (spec §2) — strangled from ``component_forecast.py``, no behaviour change.

``AssistsModel`` fits ``assists`` one gameweek ahead with a Poisson GLM on lagged process stats,
expanding walk-forward — the same Poisson-player shape as goals, so all the machinery is inherited from
:class:`~model.terms._poisson_component.PoissonPlayerComponentModel`; only the target column and pool
differ. The golden test pins ``minimal`` ``emit`` bit-identical to ``component_forecast``'s assists GLM.
``AssistsTerm`` scores E[assists] against the term's own lagged-assists baseline (spec §5).
"""

from __future__ import annotations

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


class AssistsTerm(PlayerComponentTerm):
    """The ``assists`` term — E[assists] scored vs its own lagged-assists baseline (spec §5, per-term)."""

    name = "assists"
    baseline_col = "assists_prior"
    view_col = "e_assists"
    _model_cls = AssistsModel
