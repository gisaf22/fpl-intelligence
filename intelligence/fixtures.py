"""Fixture opportunity indicators.

Surfaces players and teams with favorable near-term fixture windows. Uses
team-level attacking output and DGW presence as observable inputs — no predictive
modeling. Opponent defensive weakness is proxied through recent team-level
concession rates derived from the curated spine.

Weights are loaded from the governance registry (signals/registry/weight_registry.yaml).
All weights are PROVISIONAL-EDITORIAL — no analytical derivation exists.

## Phase 6 governance changes (2026-05-27)

GAP-TRACE-02 (GOVERNANCE INCONSISTENCY fixed): fdr_avg removed from scoring weights.
  fdr_opportunity_score component removed entirely (fdr_avg excluded at all positions;
  FIXTURE-001 G2-FAIL). Remaining two components (team_attack_score, dgw_bonus_score)
  retained at original values; weighted_composite normalises to an effective 0.58:0.42
  split. fdr_window_avg kept as an informational output column only.

GAP-TRACE-06 (GOVERNED BUT NOT WIRED fixed): DGW detection migrated from spine
  is_dgw flag to STATE fixture_context column (DGW/BGW/SGW classification).

Known remaining governance notes (do not resolve until SYNTH-01):
- team_attack_score: no lens evaluation — goals_scored is a team-level proxy
- _MIN_MINUTES_ROLL5 = 30.0: UNJUSTIFIED (threshold-registry.md §FIX-T-01)
"""

from __future__ import annotations

import pandas as pd

from intelligence._base import (
    IntelligenceInputError,
    normalize_within_position,
    validate_intelligence_inputs,
    weighted_composite,
)
from intelligence.weight_registry import get_module_weights

# Weights loaded from governance registry — fails hard if entry missing.
# Note: fdr_opportunity_score removed in Phase 6 (GAP-TRACE-02).
_WEIGHTS: dict[str, float] = get_module_weights("fixtures")

_FDR_NEUTRAL = 3.0

# UNJUSTIFIED (threshold-registry.md §FIX-T-01): no lens study establishes 30.0
# as a participation minimum for fixture opportunity.
_MIN_MINUTES_ROLL5 = 30.0

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "fdr_window_avg",
    "dgw_in_window",
    "team_goals_roll5",
    "team_attack_score",
    "dgw_bonus_score",
    "fixture_opportunity_score",
    "fixture_opportunity_rank",
]


def _build_team_attack_strength(
    features: pd.DataFrame,
    target_gw: int,
    horizon: int,
) -> pd.Series:
    """Return team-level attacking strength indexed by team_id.

    Computed as the mean of each team's goals_roll5 across the window GWs,
    then normalized to [0, 1] across teams.

    Uses the window [target_gw - horizon, target_gw) to avoid look-ahead.
    """
    lookback_start = max(1, target_gw - horizon)
    window_df = features[
        (features["gw"] >= lookback_start) & (features["gw"] < target_gw)
    ].copy()

    if window_df.empty:
        return pd.Series(dtype=float)

    team_attack = (
        window_df.groupby(["team_id", "gw"])["goals_scored"]
        .sum()
        .reset_index()
        .groupby("team_id")["goals_scored"]
        .mean()
    )

    lo, hi = team_attack.min(), team_attack.max()
    if hi == lo:
        return pd.Series(0.5, index=team_attack.index)
    return (team_attack - lo) / (hi - lo)


def rank_fixture_opportunities(
    features: pd.DataFrame,
    target_gw: int,
    horizon: int = 3,
    n: int = 20,
) -> pd.DataFrame:
    """Rank players by near-term fixture opportunity.

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain. Must span the
        target_gw window (and ideally prior GWs for team attack strength).
    target_gw:
        First gameweek of the fixture window being evaluated.
    horizon:
        Number of gameweeks ahead to include in the fixture window.
        Window: [target_gw, target_gw + horizon).
    n:
        Maximum candidates to return.

    Returns
    -------
    DataFrame ranked by fixture_opportunity_score descending with explainability
    columns.

    Scoring components (registry weights; PROVISIONAL-EDITORIAL):
    - team_attack_score  (58% effective): team's rolling goals scored
    - dgw_bonus_score    (42% effective): DGW presence in window from fixture_context

    fdr_window_avg is computed and retained as an informational output only —
    it no longer contributes to fixture_opportunity_score (GAP-TRACE-02).

    Only players with minutes_roll5 >= 30 at target_gw are included.
    """
    validate_intelligence_inputs(features, "rank_fixture_opportunities")

    # Reference row: player state at target_gw for eligibility and rolling signals.
    ref_df = features[features["gw"] == target_gw].copy()
    if ref_df.empty:
        raise IntelligenceInputError(
            f"rank_fixture_opportunities: no data for gw={target_gw}"
        )

    eligible = ref_df[ref_df["minutes_roll5"].fillna(0) >= _MIN_MINUTES_ROLL5].copy()
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Fixture window: compute per-player DGW presence (from fixture_context, GAP-TRACE-06)
    # and mean FDR (informational only, not scored).
    window_gws = list(range(target_gw, target_gw + horizon))
    window_df = features[features["gw"].isin(window_gws)][
        ["player_id", "gw", "fdr_avg", "fixture_context"]
    ]

    if window_df.empty:
        # No forward GW data available — return neutral scores.
        eligible["fdr_window_avg"] = _FDR_NEUTRAL
        eligible["dgw_in_window"] = 0
    else:
        fdr_summary = window_df.groupby("player_id").agg(
            fdr_window_avg=("fdr_avg", "mean"),
            dgw_in_window=("fixture_context", lambda s: int((s == "DGW").any())),
        )
        fdr_summary["fdr_window_avg"] = fdr_summary["fdr_window_avg"].fillna(
            _FDR_NEUTRAL
        )
        eligible = eligible.merge(
            fdr_summary, on="player_id", how="left"
        )
        eligible["fdr_window_avg"] = eligible["fdr_window_avg"].fillna(_FDR_NEUTRAL)
        eligible["dgw_in_window"] = eligible["dgw_in_window"].fillna(0).astype(int)

    # Team attack strength derived from prior gameweeks (no look-ahead).
    team_attack = _build_team_attack_strength(features, target_gw, horizon)
    eligible["team_goals_roll5"] = eligible["team_id"].map(team_attack).fillna(0.5)

    eligible["team_attack_score"] = normalize_within_position(
        eligible, "team_goals_roll5"
    )
    # DGW bonus: binary flag normalized to [0, 1] within position.
    eligible["dgw_bonus_score"] = normalize_within_position(
        eligible, "dgw_in_window"
    )

    eligible["fixture_opportunity_score"] = weighted_composite(
        eligible, list(_WEIGHTS.keys()), _WEIGHTS
    )
    eligible["fixture_opportunity_rank"] = (
        eligible.groupby("position_label")["fixture_opportunity_score"]
        .rank(ascending=False, method="min")
        .astype(int)
    )

    return (
        eligible[_OUTPUT_COLS]
        .sort_values("fixture_opportunity_score", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )
