"""Transfer target ranking — model-driven.

Ranks incoming transfer candidates by the forecaster's ex-ante expected points for the upcoming
gameweek: ``transfer_score = e_points_uncond`` (= ``P(play) x E[points | played]``, so appearance risk
is already priced in). A transfer is a squad-in decision — you want the highest expected return, and
price is a separate budget constraint (carried in the output for the manager, not in the score).

This replaces the former composite (xgi form + momentum + fixture + involvement + minutes, statically
weighted from a serve weight registry — since retired, see ADR-011). Head-to-head over 2025-26 GW6-35
(3-GW forward hold): the model
ranker returned **+1.73 cumulative pts/decision** vs the composite (10.87 vs 9.14; paired 95% CI
[+0.76, +2.70], wins 24/30 GWs) — **significantly better**. Per-position validity is enforced upstream
by the term gates, so the old xgi scope-guards (excluded at FWD/MID) are gone with the composite.

The ranker scores the **upcoming** GW only (``e_points_uncond`` at ``target_gw``), which is strictly
lag-safe (the terms fit on ``gw < target_gw``). A multi-week forward hold would need per-decision
multi-step forecasts frozen at the deadline; summing the precomputed forecast column across future GWs
would leak post-decision state, so it is deliberately not done here.

Structure: this module declares a :class:`domain.decision.DecisionSpec` and delegates the shared
lifecycle to :func:`serve.decision_engine.run_decision` (ADR-012). The forecast column
``e_points_uncond`` arrives as data, merged onto the mart by the operational runner — ``serve`` does
not import ``model`` (import-linter ``no_serve_to_research_or_model``).
"""

from __future__ import annotations

import pandas as pd

from domain.decision import DecisionSpec
from serve.decision_engine import run_decision

# threshold not evaluation-derived — see threshold-registry.md §TRANS-T-01
_MIN_MINUTES_ROLL5 = 30.0


def _eligible(features: pd.DataFrame, *, position: str | None = None, **_: object) -> pd.Series:
    """A reliable starter; optionally restricted to one position."""
    mask = (~features["is_warmup_gw"]) & (features["minutes_roll5"] >= _MIN_MINUTES_ROLL5)
    if position is not None:
        mask &= features["position_label"] == position
    return mask


def _objective(features: pd.DataFrame) -> pd.Series:
    """Best incoming pick = highest ex-ante expected points for the upcoming GW."""
    return features["e_points_uncond"]


TRANSFERS = DecisionSpec(
    name="rank_transfer_targets",
    required_forecast_cols=("e_points_uncond",),
    eligibility=_eligible,
    objective=_objective,
    score_col="transfer_score",
    rank_col="transfer_rank",
    output_cols=(
        "player_id",
        "player_name",
        "position_label",
        "team_id",
        "purchase_price",
        "minutes_roll5",
        "e_points_uncond",
        "transfer_score",
        "transfer_rank",
    ),
)


def rank_transfer_targets(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    position: str | None = None,
) -> pd.DataFrame:
    """Rank transfer-in candidates for a target gameweek by model expected points.

    Parameters
    ----------
    features:
        DAL mart at (player_id, gw) grain, **enriched** with the model forecast column
        ``e_points_uncond`` via :func:`model.predictions.assemble_forecast`.
    target_gw:
        Gameweek being prepared for. The forecast at ``target_gw`` is lag-safe (the terms fit on
        ``gw < target_gw``).
    n:
        Maximum candidates to return.
    position:
        Optional position filter: 'GK', 'DEF', 'MID', or 'FWD'.
        When None, returns top-n across all positions.

    Returns
    -------
    DataFrame ranked by ``transfer_score`` (= ``e_points_uncond``) descending, with the expected-points
    read carried for explainability. ``transfer_rank`` is the within-position rank.

    Only players with ``minutes_roll5 >= 30`` (and a scored forecast row) are eligible.
    """
    return run_decision(TRANSFERS, features, target_gw, n=n, position=position)
