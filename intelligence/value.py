"""Value player identification.

Surfaces players delivering high point returns relative to their FPL cost.
Deterministic and price-static — does not forecast price changes.

Weights are loaded from the governance registry (signals/characterisation/weight_registry.yaml).

Scope constraint: xgi_roll3 and xgi_roll5 excluded at FWD (FORM-001/002 G2-FAIL).
FWD players receive neutral 0.5 on efficiency_score, form_score, and consistency_score —
xgi signals zeroed before scoring computations. xgi_per_cost output column retains
original values for informational display.
"""

from __future__ import annotations

import pandas as pd

from intelligence.intelligence_contracts import (
    IntelligenceInputError,
    normalize_within_position,
    validate_intelligence_inputs,
    weighted_composite,
)
from intelligence.weight_registry import get_module_weights

# Weights loaded from governance registry — fails hard if entry missing.
_WEIGHTS: dict[str, float] = get_module_weights("value")

# Minimum price to avoid division edge cases and very unpriced placeholders.
_MIN_PRICE = 3.5

# threshold not evaluation-derived — see threshold-registry.md §VAL-T-01
_MIN_MINUTES_ROLL5 = 30.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "purchase_price",
    "xgi_roll3",
    "xgi_roll5",
    "minutes_roll5",
    "xgi_per_cost",
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

    Scoring components (registry weights):
    - efficiency_score  50%: xgi_roll5 / purchase_price, normalized within position
                             FWD scope guard: xgi_roll5 zeroed at FWD → neutral 0.5
    - form_score        30%: xgi_roll3, normalized within position
                             FWD scope guard: zeroed at FWD → neutral 0.5
    - consistency_score 20%: alignment between xgi_roll3 and xgi_roll5
                             FWD scope guard: both zeroed → perfect consistency → 0.5

    xgi_per_cost output column shows original (un-guarded) values for display.
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

    # xgi_per_cost for display: uses original xgi values (informational output).
    eligible["xgi_per_cost"] = (
        eligible["xgi_roll5"].fillna(0) / eligible["purchase_price"]
    )

    # xgi_roll3 and xgi_roll5 excluded at FWD: FORM-001/002 G2-FAIL.
    # Zero out xgi signals for FWD players; scoring uses these guarded values.
    fwd_mask = eligible["position_label"] == "FWD"
    xgi_roll5_scored = eligible["xgi_roll5"].fillna(0).where(~fwd_mask, 0.0)
    xgi_roll3_scored = eligible["xgi_roll3"].fillna(0).where(~fwd_mask, 0.0)
    eligible["_xgi_per_cost_scored"] = xgi_roll5_scored / eligible["purchase_price"]

    # Consistency: how close are xgi_roll3 and xgi_roll5?
    # High score = roll3 ≈ roll5 (stable contributor, not one-week wonder).
    # Uses scope-guarded values; FWD players: both zero → perfect consistency → 0.5
    max_roll5_scored = xgi_roll5_scored.replace(0, 1)  # avoid division by zero
    eligible["_consistency_raw"] = 1.0 - (
        (xgi_roll3_scored - xgi_roll5_scored).abs() / max_roll5_scored.abs()
    )
    eligible["_consistency_raw"] = eligible["_consistency_raw"].clip(lower=0.0)

    eligible["_xgi_roll3_scored"] = xgi_roll3_scored

    eligible["efficiency_score"] = normalize_within_position(
        eligible, "_xgi_per_cost_scored"
    )
    eligible["form_score"] = normalize_within_position(eligible, "_xgi_roll3_scored")
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
