"""Transfer target ranking.

Identifies strong incoming transfer candidates based on rising form, fixture
context, involvement, and minutes stability. Does not model price movements,
ownership shifts, or market dynamics.

Weights are loaded from the governance registry (signals/characterisation/weight_registry.yaml).

Scope constraint: xgi_roll3 and xgi_roll5 excluded at FWD (FORM-001/002 G2-FAIL).
FWD players receive neutral 0.5 on recent_form_score, form_momentum_score, and
involvement_score — xgi signals zeroed before normalization.

fixture_score uses binary DGW indicator from STATE fixture_context column.
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
_WEIGHTS: dict[str, float] = get_module_weights("transfers")

# threshold not evaluation-derived — see threshold-registry.md §TRANS-T-01
_MIN_MINUTES_ROLL5 = 30.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "purchase_price",
    "xgi_roll3",
    "xgi_roll5",
    "fixture_context",
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

    Scoring components (registry weights):
    - recent_form_score    30%: xgi_roll3; excluded at FWD (FORM-001/002 G2-FAIL) → neutral 0.5
    - form_momentum_score  25%: xgi_roll3 − xgi_roll5; FWD scope guard applied
    - fixture_score        20%: binary DGW flag from STATE fixture_context
    - involvement_score    15%: xgi_roll3; excluded at FWD (FORM-001/002 G2-FAIL) → neutral 0.5
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

    # xgi_roll3 and xgi_roll5 excluded at FWD: FORM-001/002 G2-FAIL.
    # Zero out both for FWD players; all-zero FWD group returns 0.5 from normalization.
    fwd_mask = eligible["position_label"] == "FWD"
    xgi_roll3_scored = eligible["xgi_roll3"].fillna(0).where(~fwd_mask, 0.0)
    xgi_roll5_scored = eligible["xgi_roll5"].fillna(0).where(~fwd_mask, 0.0)

    eligible["_xgi_roll3_scored"] = xgi_roll3_scored
    eligible["_xgi_roll5_scored"] = xgi_roll5_scored

    # Form momentum: positive when recent xgi (roll3) exceeds medium-term (roll5).
    # FWD guard: both operands zeroed → momentum = 0 for all FWD → neutral 0.5.
    eligible["_momentum"] = xgi_roll3_scored - xgi_roll5_scored

    # Binary DGW flag from STATE fixture_context column.
    eligible["_fixture_context_dgw"] = (
        eligible["fixture_context"].fillna("SGW") == "DGW"
    ).astype(float)

    eligible["recent_form_score"] = normalize_within_position(
        eligible, "_xgi_roll3_scored"
    )
    eligible["form_momentum_score"] = normalize_within_position(
        eligible, "_momentum"
    )
    eligible["fixture_score"] = normalize_within_position(
        eligible, "_fixture_context_dgw"
    )
    eligible["involvement_score"] = normalize_within_position(
        eligible, "_xgi_roll3_scored"
    )
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
