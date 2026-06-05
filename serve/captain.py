"""Captain candidate ranking.

Produces a ranked list of captain options for a target gameweek based on
recent form, attacking involvement, fixture context, and minutes stability.

Weights are loaded from the module weight registry (serve/weight_registry.yaml).

Scope constraints (validate-stage lens findings + the model-stage synthesis verdict
set-synth-weights; see docs/decisions/):
- xgi_roll5 excluded at FWD (xgi_roll5@form:total_points, G2-FAIL). FWD → neutral 0.5 on form_score.
- xgi_roll3 excluded at FWD (xgi_roll3@form:total_points, G2-FAIL) and MID
  (xgi_roll3@form:total_points#MID: EXCLUDED-REDUNDANT vs xgi_roll5). FWD and MID →
  neutral 0.5 on involvement_score.

fixture_score uses binary DGW indicator from STATE fixture_context column.
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
_WEIGHTS: dict[str, float] = get_module_weights("captain")

# threshold not evaluation-derived — see threshold-registry.md §CAPT-T-01
_MIN_MINUTES_ROLL3 = 45.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "xgi_roll5",
    "xgi_roll3",
    "fixture_context",
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
        Produced by dal.pipeline.load().mart.
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

    Scoring components (registry weights):
    - form_score        35%: xgi_roll5; excluded at FWD (xgi_roll5@form:total_points G2-FAIL) → neutral 0.5
    - involvement_score 30%: xgi_roll3; excluded at FWD (xgi_roll3@form:total_points G2-FAIL) and MID
                             (xgi_roll3@form:total_points#MID EXCLUDED-REDUNDANT) → neutral 0.5
    - fixture_score     20%: binary DGW flag from STATE fixture_context
    - minutes_score     15%: minutes_roll3, normalized within position

    Only players with minutes_roll3 >= 45 are eligible (must be starting).
    """
    validate_intelligence_inputs(features, "rank_captain_candidates")

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"rank_captain_candidates: no data for gw={target_gw}")

    # Filter to players starting reliably — captaincy requires regular minutes.
    eligible = gw_df[gw_df["minutes_roll3"].fillna(0) >= _MIN_MINUTES_ROLL3].copy()
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # xgi_roll5 excluded at FWD: xgi_roll5@form:total_points G2-FAIL.
    # xgi_roll3 excluded at FWD (xgi_roll3@form:total_points G2-FAIL) and MID
    # (xgi_roll3@form:total_points#MID: EXCLUDED-REDUNDANT vs xgi_roll5 at MID). Zeroed groups return 0.5 from
    # normalize_within_position (neutral, no xgi contribution at excluded positions).
    fwd_mask = eligible["position_label"] == "FWD"
    mid_mask = eligible["position_label"] == "MID"
    eligible["_xgi_roll5_scored"] = eligible["xgi_roll5"].where(~fwd_mask, 0.0)
    eligible["_xgi_roll3_scored"] = eligible["xgi_roll3"].where(~(fwd_mask | mid_mask), 0.0)

    # Binary DGW flag from STATE fixture_context column.
    eligible["_fixture_context_dgw"] = (eligible["fixture_context"].fillna("SGW") == "DGW").astype(float)

    eligible["form_score"] = normalize_within_position(eligible, "_xgi_roll5_scored")
    eligible["involvement_score"] = normalize_within_position(eligible, "_xgi_roll3_scored")
    eligible["fixture_score"] = normalize_within_position(eligible, "_fixture_context_dgw")
    eligible["minutes_score"] = normalize_within_position(eligible, "minutes_roll3")

    eligible["captain_score"] = weighted_composite(eligible, list(_WEIGHTS.keys()), _WEIGHTS)

    eligible["captain_rank"] = (
        eligible.groupby("position_label")["captain_score"].rank(ascending=False, method="min").astype(int)
    )

    return eligible[_OUTPUT_COLS].sort_values("captain_score", ascending=False).head(n).reset_index(drop=True)
