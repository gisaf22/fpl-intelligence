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

Input: the DAL mart **enriched** with the model forecast column ``e_points_uncond`` from
:func:`model.predictions.assemble_forecast`, merged on ``(player_id, gw)`` by the operational runner —
``serve`` does not import ``model`` (import-linter ``no_serve_to_research_or_model``), so the forecast
arrives as data, not a call.
"""

from __future__ import annotations

import pandas as pd

from serve.input_contracts import IntelligenceInputError, validate_intelligence_inputs

# Minimum price to avoid division edge cases and very unpriced placeholders.
_MIN_PRICE = 3.5

# threshold not evaluation-derived — see threshold-registry.md §VAL-T-01
_MIN_MINUTES_ROLL5 = 30.0

# The model forecast column the runner must have merged onto the mart (see model.predictions).
_FORECAST_COLS = ("e_points_uncond",)

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "purchase_price",
    "minutes_roll5",
    "e_points_uncond",
    "value_score",
    "value_rank",
]


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
    validate_intelligence_inputs(features, "rank_value_players")
    missing = [c for c in _FORECAST_COLS if c not in features.columns]
    if missing:
        raise IntelligenceInputError(
            f"rank_value_players: missing model forecast columns {missing}. Enrich the mart with "
            "model.predictions.assemble_forecast before ranking (serve does not import model; the "
            "operational runner merges the forecast on (player_id, gw))."
        )

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"rank_value_players: no data for gw={target_gw}")

    eligible = gw_df[
        (gw_df["purchase_price"] >= _MIN_PRICE)
        & (~gw_df["is_warmup_gw"])
        & (gw_df["minutes_roll5"] >= _MIN_MINUTES_ROLL5)
    ].copy()

    if max_price is not None:
        eligible = eligible[eligible["purchase_price"] <= max_price]

    # A scored forecast row (e_points_uncond defined) is required to rank.
    eligible = eligible.dropna(subset=["e_points_uncond"])
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Value = ex-ante expected points per £m paid. e_points_uncond already prices appearance risk.
    eligible["value_score"] = eligible["e_points_uncond"].astype(float) / eligible["purchase_price"].astype(float)
    eligible = eligible.sort_values("value_score", ascending=False)
    eligible["value_rank"] = (
        eligible.groupby("position_label")["value_score"].rank(ascending=False, method="min").astype(int)
    )

    return eligible[_OUTPUT_COLS].head(n).reset_index(drop=True)
