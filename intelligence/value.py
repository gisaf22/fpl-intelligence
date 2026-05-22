"""Value player identification.

Surfaces players delivering high point returns relative to their FPL cost.
Deterministic and price-static — does not forecast price changes.
"""

from __future__ import annotations

import pandas as pd

from intelligence._base import (
    IntelligenceInputError,
    normalize_within_position,
    validate_intelligence_inputs,
    weighted_composite,
)

# Explicit static weights.
# Value efficiency = 50%, form = 30%, consistency = 20%.
_WEIGHTS: dict[str, float] = {
    "efficiency_score": 0.50,
    "form_score": 0.30,
    "consistency_score": 0.20,
}

# Minimum price to avoid division edge cases and very unpriced placeholders.
_MIN_PRICE = 3.5

# Minimum rolling minutes to include — bench-warmers inflate value artificially.
_MIN_MINUTES_ROLL5 = 30.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "purchase_price",
    "points_roll3",
    "points_roll5",
    "minutes_roll5",
    "points_per_cost",
    "efficiency_score",
    "form_score",
    "consistency_score",
    "value_score",
    "value_rank",
]


def rank_value_players(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    max_price: float | None = None,
) -> pd.DataFrame:
    """Rank players by value (return per unit cost) for a target gameweek.

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain.
    target_gw:
        Gameweek being prepared for.
    n:
        Maximum candidates to return.
    max_price:
        Optional price ceiling (FPL £m). When set, only players at or below
        this price are considered.

    Returns
    -------
    DataFrame ranked by value_score descending with explainability columns.

    Scoring components (static weights):
    - efficiency_score  50%: points_roll5 / purchase_price, normalized within position
    - form_score        30%: points_roll3, normalized within position
    - consistency_score 20%: alignment between roll3 and roll5 (low divergence = consistent)

    Only players with minutes_roll5 >= 30 and purchase_price >= 3.5 are eligible.
    """
    validate_intelligence_inputs(features, "rank_value_players")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(
            f"rank_value_players: no data for gw={target_gw}"
        )

    eligible = gw_df[
        (gw_df["purchase_price"].fillna(0) >= _MIN_PRICE)
        & (gw_df["minutes_roll5"].fillna(0) >= _MIN_MINUTES_ROLL5)
    ].copy()

    if max_price is not None:
        eligible = eligible[eligible["purchase_price"] <= max_price]

    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Points per cost: primary value signal.
    eligible["points_per_cost"] = (
        eligible["points_roll5"].fillna(0) / eligible["purchase_price"]
    )

    # Consistency: how close are roll3 and roll5?
    # High score = roll3 ≈ roll5 (stable contributor, not one-week wonder).
    roll3 = eligible["points_roll3"].fillna(0)
    roll5 = eligible["points_roll5"].fillna(0)
    # Normalised absolute divergence, inverted so 0 divergence = score 1.
    max_roll5 = roll5.replace(0, 1)  # avoid division by zero
    eligible["_consistency_raw"] = 1.0 - (roll3 - roll5).abs() / max_roll5.abs()
    eligible["_consistency_raw"] = eligible["_consistency_raw"].clip(lower=0.0)

    eligible["efficiency_score"] = normalize_within_position(
        eligible, "points_per_cost"
    )
    eligible["form_score"] = normalize_within_position(eligible, "points_roll3")
    eligible["consistency_score"] = normalize_within_position(
        eligible, "_consistency_raw"
    )

    eligible["value_score"] = weighted_composite(
        eligible, list(_WEIGHTS.keys()), _WEIGHTS
    )
    eligible["value_rank"] = (
        eligible.groupby("position_label")["value_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    return (
        eligible[_OUTPUT_COLS]
        .sort_values("value_score", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
