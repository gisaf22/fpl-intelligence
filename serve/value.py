"""Value player identification.

Surfaces players delivering high point returns relative to their FPL cost.
Deterministic and price-static — does not forecast price changes.

Weights are loaded from the module weight registry (serve/weight_registry.yaml).

Scope constraints:
- xgi_roll3 and xgi_roll5 excluded at FWD (xgi_roll3@form:total_points / xgi_roll5@form:total_points G2-FAIL).
- xgi_roll3 excluded at MID (xgi_roll3@form:total_points#MID EXCLUDED-REDUNDANT vs xgi_roll5 (set-synth-weights)).
FWD and MID players receive neutral 0.5 on form_score and consistency_score.
FWD players also receive neutral 0.5 on efficiency_score (xgi_roll5 zeroed at FWD only).
xgi_per_cost output column retains original values for informational display.
"""

from __future__ import annotations

import pandas as pd

from serve.intelligence_contracts import (
    IntelligenceInputError,
    normalize_within_position,
    validate_intelligence_inputs,
    weighted_composite,
)
from serve.weight_registry import get_module_weights

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
                             FWD+MID scope guard: zeroed at FWD and MID → neutral 0.5
    - consistency_score 20%: alignment between xgi_roll3 and xgi_roll5
                             FWD: both zeroed → 0.5. MID: comparison neutralised → 0.5

    xgi_per_cost output column shows original (un-guarded) values for display.
    Only players with minutes_roll5 >= 30 and purchase_price >= 3.5 are eligible.
    """
    validate_intelligence_inputs(features, "rank_value_players")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"rank_value_players: no data for gw={target_gw}")

    eligible = gw_df[
        (gw_df["purchase_price"].fillna(0) >= _MIN_PRICE) & (gw_df["minutes_roll5"].fillna(0) >= _MIN_MINUTES_ROLL5)
    ].copy()

    if max_price is not None:
        eligible = eligible[eligible["purchase_price"] <= max_price]

    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # xgi_per_cost for display: uses original xgi values (informational output).
    eligible["xgi_per_cost"] = eligible["xgi_roll5"].fillna(0) / eligible["purchase_price"]

    # xgi_roll5 excluded at FWD: xgi_roll5@form:total_points G2-FAIL.
    # xgi_roll3 excluded at FWD (xgi_roll3@form:total_points G2-FAIL) and MID (xgi_roll3@form:total_points#MID:
    # EXCLUDED-REDUNDANT vs xgi_roll5). Zeroed groups return 0.5 from
    # normalize_within_position (neutral, not removed).
    fwd_mask = eligible["position_label"] == "FWD"
    mid_mask = eligible["position_label"] == "MID"
    xgi_roll5_scored = eligible["xgi_roll5"].fillna(0).where(~fwd_mask, 0.0)
    xgi_roll3_scored = eligible["xgi_roll3"].fillna(0).where(~(fwd_mask | mid_mask), 0.0)
    eligible["_xgi_per_cost_scored"] = xgi_roll5_scored / eligible["purchase_price"]

    # Consistency: how close are xgi_roll3 and xgi_roll5?
    # High score = roll3 ≈ roll5 (stable contributor, not one-week wonder).
    # FWD: both zeroed → 0.5. MID: xgi_roll3 zeroed but xgi_roll5 live — comparison
    # is invalid (zeroed operand vs non-zero produces wrong ranking). Neutralise by
    # setting _consistency_raw to 0 for all MID; all-same → normalize → 0.5.
    max_roll5_scored = xgi_roll5_scored.replace(0, 1)  # avoid division by zero
    eligible["_consistency_raw"] = 1.0 - ((xgi_roll3_scored - xgi_roll5_scored).abs() / max_roll5_scored.abs())
    eligible["_consistency_raw"] = eligible["_consistency_raw"].clip(lower=0.0)
    eligible.loc[mid_mask, "_consistency_raw"] = 0.0

    eligible["_xgi_roll3_scored"] = xgi_roll3_scored

    eligible["efficiency_score"] = normalize_within_position(eligible, "_xgi_per_cost_scored")
    eligible["form_score"] = normalize_within_position(eligible, "_xgi_roll3_scored")
    eligible["consistency_score"] = normalize_within_position(eligible, "_consistency_raw")

    eligible["value_score"] = weighted_composite(eligible, list(_WEIGHTS.keys()), _WEIGHTS)
    eligible["value_rank"] = (
        eligible.groupby("position_label")["value_score"].rank(ascending=False, method="min").astype(int)
    )

    return eligible[_OUTPUT_COLS].sort_values("value_score", ascending=False).head(n).reset_index(drop=True)
