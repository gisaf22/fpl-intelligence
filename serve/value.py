"""Value player identification — model-driven.

Ranks players by **return per unit cost** using the forecaster's ex-ante expected points:
``value_score = e_points_uncond / purchase_price`` — the unconditional expectation
(``P(play) x E[points | played]``) divided by the price the manager pays now. Because
``e_points_uncond`` already prices in appearance risk, a rotation-doubtful cheap punt is not
flattered by a high per-cost score the way a raw form/cost composite would flatter it.

This replaces the former composite (xgi efficiency + form + consistency, statically weighted from
a serve weight registry — since retired, see ADR-011). Head-to-head over 2025-26 GW6-34: the model value ranker returned
**+0.14 points-per-£m/GW** vs the composite (2.35 vs 2.21; paired 95% CI [-0.17, +0.44]) — better on
the point estimate, never significantly worse. Per-position validity is enforced upstream by the term
gates, so the old xgi scope-guards (xgi excluded at FWD/MID) are gone with the composite.

Deterministic and price-static — does not forecast price changes.

Structure: this module declares a :class:`domain.decision.DecisionSpec` and delegates the shared
lifecycle to :func:`serve.decision_engine.run_decision` (ADR-012). The forecast column
``e_points_uncond`` arrives as data, merged onto the mart by the operational runner — ``serve`` does
not import ``model`` (import-linter ``no_serve_to_research_or_model``).
"""

from __future__ import annotations

import pandas as pd

from domain.decision import DecisionSpec
from serve.decision_engine import run_decision

# Minimum price to avoid division edge cases and very unpriced placeholders.
_MIN_PRICE = 3.5

# threshold not evaluation-derived — see threshold-registry.md §VAL-T-01
_MIN_MINUTES_ROLL5 = 30.0


def _eligible(features: pd.DataFrame, *, max_price: float | None = None, **_: object) -> pd.Series:
    """Priced, reliable, and (optionally) at or below a budget ceiling."""
    mask = (
        (features["purchase_price"] >= _MIN_PRICE)
        & (~features["is_warmup_gw"])
        & (features["minutes_roll5"] >= _MIN_MINUTES_ROLL5)
    )
    if max_price is not None:
        mask &= features["purchase_price"] <= max_price
    return mask


def _objective(features: pd.DataFrame) -> pd.Series:
    """Ex-ante expected points per £m paid. ``e_points_uncond`` already prices appearance risk."""
    return features["e_points_uncond"] / features["purchase_price"]


VALUE = DecisionSpec(
    name="rank_value_players",
    required_forecast_cols=("e_points_uncond",),
    eligibility=_eligible,
    objective=_objective,
    score_col="value_score",
    rank_col="value_rank",
    output_cols=(
        "player_id",
        "player_name",
        "position_label",
        "team_id",
        "purchase_price",
        "minutes_roll5",
        "e_points_uncond",
        "value_score",
        "value_rank",
    ),
)


def rank_value_players(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    max_price: float | None = None,
) -> pd.DataFrame:
    """Rank players by value (expected return per unit cost) for a target gameweek.

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
    max_price:
        Optional price ceiling (FPL £m). When set, only players at or below this price are considered.

    Returns
    -------
    DataFrame ranked by ``value_score`` (= ``e_points_uncond / purchase_price``) descending, with the
    expected-points read carried for explainability. ``value_rank`` is the within-position rank.

    Only players with ``minutes_roll5 >= 30`` and ``purchase_price >= 3.5`` (and a scored forecast row)
    are eligible.
    """
    return run_decision(VALUE, features, target_gw, n=n, max_price=max_price)
