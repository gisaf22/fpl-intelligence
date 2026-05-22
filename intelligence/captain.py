"""Captain candidate ranking.

Produces a ranked list of captain options for a target gameweek based on
recent form, attacking involvement, fixture difficulty, and minutes stability.

All weights are explicit and static. No learned weighting, no ML.
"""

from __future__ import annotations

import pandas as pd

from intelligence._base import (
    IntelligenceInputError,
    normalize_within_position,
    validate_intelligence_inputs,
    weighted_composite,
)

# Explicit static weights — document any change here with rationale.
# form + involvement = 65% (output-focused)
# fixture + minutes = 35% (opportunity/availability filter)
_WEIGHTS: dict[str, float] = {
    "form_score": 0.35,
    "involvement_score": 0.30,
    "fixture_score": 0.20,
    "minutes_score": 0.15,
}

# Minimum 3-GW rolling minutes to be considered a captain candidate.
# Players below this threshold are not starting reliably enough.
_MIN_MINUTES_ROLL3 = 45.0

# FDR neutral value used when fdr_avg is missing (e.g. BGW rows).
_FDR_NEUTRAL = 3.0
# FDR scale upper bound + 1, used to invert: easy fixture → high score.
_FDR_CEILING = 6.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "points_roll3",
    "xgi_roll3",
    "fdr_avg",
    "minutes_roll3",
    "form_score",
    "involvement_score",
    "fixture_score",
    "minutes_score",
    "captain_score",
    "captain_rank",
]


def rank_captain_candidates(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
) -> pd.DataFrame:
    """Rank captain candidates for a target gameweek.

    Parameters
    ----------
    features:
        Full DAL state output — spine + state columns at (player_id, gw) grain.
        Produced by get_state_features(get_curated_spine(db_path)).
    target_gw:
        The gameweek being prepared for. State at target_gw reflects rolling
        windows through the prior gameweek (lag-1 convention).
    n:
        Maximum number of candidates to return across all positions.

    Returns
    -------
    DataFrame ranked by captain_score descending, with explicit component
    columns (form_score, involvement_score, fixture_score, minutes_score)
    for full explainability.

    Scoring components (static weights):
    - form_score      35%: points_roll3, normalized within position
    - involvement_score 30%: xgi_roll3, normalized within position
    - fixture_score   20%: inverted fdr_avg, normalized within position
    - minutes_score   15%: minutes_roll3, normalized within position

    Only players with minutes_roll3 >= 45 are eligible (must be starting).
    """
    validate_intelligence_inputs(features, "rank_captain_candidates")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(
            f"rank_captain_candidates: no data for gw={target_gw}"
        )

    # Filter to players starting reliably — captaincy requires regular minutes.
    eligible = gw_df[gw_df["minutes_roll3"].fillna(0) >= _MIN_MINUTES_ROLL3].copy()
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Invert FDR so that easy fixtures (low FDR) produce high scores.
    eligible["_fdr_inv"] = _FDR_CEILING - eligible["fdr_avg"].fillna(_FDR_NEUTRAL)

    eligible["form_score"] = normalize_within_position(eligible, "points_roll3")
    eligible["involvement_score"] = normalize_within_position(eligible, "xgi_roll3")
    eligible["fixture_score"] = normalize_within_position(eligible, "_fdr_inv")
    eligible["minutes_score"] = normalize_within_position(eligible, "minutes_roll3")

    eligible["captain_score"] = weighted_composite(
        eligible, list(_WEIGHTS.keys()), _WEIGHTS
    )

    # Rank within each position (not globally) then present top-n overall.
    eligible["captain_rank"] = (
        eligible.groupby("position_label")["captain_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    return (
        eligible[_OUTPUT_COLS]
        .sort_values("captain_score", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
