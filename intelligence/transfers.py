"""Transfer target ranking.

Identifies strong incoming transfer candidates based on rising form, fixture
opportunity, involvement, and minutes stability. Does not model price
movements, ownership shifts, or market dynamics.
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
# Recent form + momentum = 55% (directional signal)
# Fixture + involvement + minutes = 45% (opportunity/reliability)
_WEIGHTS: dict[str, float] = {
    "recent_form_score": 0.30,
    "form_momentum_score": 0.25,
    "fixture_score": 0.20,
    "involvement_score": 0.15,
    "minutes_stability_score": 0.10,
}

# Minimum 5-GW rolling minutes to qualify — transfers need sustained involvement.
_MIN_MINUTES_ROLL5 = 30.0

_FDR_NEUTRAL = 3.0
_FDR_CEILING = 6.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "purchase_price",
    "points_roll3",
    "points_roll5",
    "xgi_roll3",
    "fdr_avg",
    "minutes_roll5",
    "recent_form_score",
    "form_momentum_score",
    "fixture_score",
    "involvement_score",
    "minutes_stability_score",
    "transfer_score",
    "transfer_rank",
]


def rank_transfer_targets(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    position: str | None = None,
) -> pd.DataFrame:
    """Rank transfer-in candidates for a target gameweek.

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain.
    target_gw:
        Gameweek being prepared for.
    n:
        Maximum candidates to return.
    position:
        Optional position filter: 'GK', 'DEF', 'MID', or 'FWD'.
        When None, returns top-n across all positions.

    Returns
    -------
    DataFrame ranked by transfer_score descending with explicit component
    columns for explainability.

    Scoring components (static weights):
    - recent_form_score    30%: points_roll3, normalized within position
    - form_momentum_score  25%: points_roll3 − points_roll5 (rising = positive)
    - fixture_score        20%: inverted fdr_avg, normalized within position
    - involvement_score    15%: xgi_roll3, normalized within position
    - minutes_stability    10%: minutes_roll5, normalized within position

    Only players with minutes_roll5 >= 30 are eligible.
    """
    validate_intelligence_inputs(features, "rank_transfer_targets")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(
            f"rank_transfer_targets: no data for gw={target_gw}"
        )

    if position is not None:
        gw_df = gw_df[gw_df["position_label"] == position]
        if gw_df.empty:
            return pd.DataFrame(columns=_OUTPUT_COLS)

    eligible = gw_df[gw_df["minutes_roll5"].fillna(0) >= _MIN_MINUTES_ROLL5].copy()
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Form momentum: positive when recent form (roll3) exceeds medium-term (roll5).
    eligible["_momentum"] = (
        eligible["points_roll3"].fillna(0) - eligible["points_roll5"].fillna(0)
    )
    eligible["_fdr_inv"] = _FDR_CEILING - eligible["fdr_avg"].fillna(_FDR_NEUTRAL)

    eligible["recent_form_score"] = normalize_within_position(
        eligible, "points_roll3"
    )
    eligible["form_momentum_score"] = normalize_within_position(
        eligible, "_momentum"
    )
    eligible["fixture_score"] = normalize_within_position(eligible, "_fdr_inv")
    eligible["involvement_score"] = normalize_within_position(eligible, "xgi_roll3")
    eligible["minutes_stability_score"] = normalize_within_position(
        eligible, "minutes_roll5"
    )

    eligible["transfer_score"] = weighted_composite(
        eligible, list(_WEIGHTS.keys()), _WEIGHTS
    )
    eligible["transfer_rank"] = (
        eligible.groupby("position_label")["transfer_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    return (
        eligible[_OUTPUT_COLS]
        .sort_values("transfer_score", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
