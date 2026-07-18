"""The goals Model + Term (spec §2) — strangled from ``component_forecast.py``, no behaviour change.

``GoalsModel`` fits ``goals_scored`` one gameweek ahead with a Poisson GLM on lagged process stats,
expanding walk-forward (fit on ``gw < t``). Two draws from ``GOALS_POOL`` (spec §3):

* **minimal** — ``xgi_roll3 + minutes_roll3``, unregularized ``statsmodels`` GLM. This *is* the
  god-file's goals design; it is both the fast smoke-test and the comparison **bar**. The golden test
  pins its ``emit`` bit-identical to ``component_forecast`` on a fixed panel (the 4dp reproduction).
* **selected** — regularized over the full materializable pool; the shipped model once the §3
  opponent-forward / team-context features exist. Today only the two mechanistic columns are on the
  mart, so *selected draws the same design as minimal* and the frozen composed numbers are untouched.

All the machinery lives in the shared :class:`~model.terms._poisson_component.PoissonPlayerComponentModel`
(``goals`` / ``assists`` / ``saves`` are the same Poisson-player shape); these subclasses declare only
what differs. ``GoalsTerm`` scores E[goals] against the term's **own** lagged-goals baseline (spec §5).
"""

from __future__ import annotations

from model.terms._base import Hypothesis
from model.terms._poisson_component import PlayerComponentTerm, PoissonPlayerComponentModel
from model.terms.goals.spec import GOALS_POOL


class GoalsModel(PoissonPlayerComponentModel):
    """Poisson GLM of next-GW ``goals_scored`` on lagged process stats (the fittable unit)."""

    name = "goals"
    target = "goals_scored"
    term = "goals"
    pool = GOALS_POOL
    hypotheses = (
        Hypothesis(
            claim="lagged xG+xA ranks next-GW goals better than a player's lagged goals mean",
            test="within-position Spearman of emitted E[goals] vs goals_prior, GW>3, common eval set",
            success_threshold="Δ Spearman > 0 at DEF and MID (the rankable attacking positions)",
            status="supported (phase2: DEF +0.026, MID +0.043, FWD +0.013)",
        ),
    )


class GoalsTerm(PlayerComponentTerm):
    """The ``goals`` term — E[goals] scored vs its own lagged-goals baseline (spec §5, per-term)."""

    name = "goals"
    baseline_col = "goals_prior"
    view_col = "e_goals"
    _model_cls = GoalsModel
