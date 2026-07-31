"""Captain candidate ranking — model-driven.

Ranks captain options for a target gameweek by the forecaster's **haul probability** (``p_haul``) — the
distribution read the mean cannot give. Captaincy is a *ceiling* bet (you want the chance of a big
score, not the expected score), so we rank by ``p_haul`` and tie-break on the 90th-percentile ceiling
``p90``. Because ``p_haul`` is an absolute probability, it is comparable **across** positions — unlike
the retired within-position signal composite, whose normalised score made a DEF's 0.9 and a MID's 0.9
meaningless to compare.

This replaces the former composite (xgi form/involvement + fixture + minutes, statically weighted from
``weight_registry.yaml``). Head-to-head over 2025-26 GW6-38: the model captain returned **+1.9 pts/GW**
vs the composite (5.09 vs 3.22; paired 95% CI [-0.03, +3.9]) — better on the point estimate, never
significantly worse. Per-position validity is enforced upstream by the term gates, so the old xgi
scope-guards (excluded at FWD/MID) are gone with the composite.

Input: the DAL mart **enriched** with the model forecast columns (``p_haul``, ``p90``,
``e_points_uncond``) from :func:`model.predictions.assemble_forecast`, merged on ``(player_id, gw)`` by
the operational runner — ``serve`` does not import ``model`` (import-linter ``no_serve_to_research_or_model``),
so the forecast arrives as data, not a call.
"""

from __future__ import annotations

import pandas as pd

from serve.input_contracts import IntelligenceInputError, validate_intelligence_inputs

# threshold not evaluation-derived — see threshold-registry.md §CAPT-T-01
_MIN_MINUTES_ROLL3 = 45.0

# The model forecast columns the runner must have merged onto the mart (see model.predictions).
_FORECAST_COLS = ("p_haul", "p90", "e_points_uncond")

_OUTPUT_COLS = [
    "player_id",
    "player_name",
    "position_label",
    "team_id",
    "minutes_roll3",
    "e_points_uncond",
    "p90",
    "p_haul",
    "captain_score",
    "captain_rank",
]


def rank_captain_candidates(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
) -> pd.DataFrame:
    """Rank captain candidates for a target gameweek by model haul probability.

    Parameters
    ----------
    features:
        DAL mart at (player_id, gw) grain, **enriched** with the model forecast columns
        (``p_haul``, ``p90``, ``e_points_uncond``) via :func:`model.predictions.assemble_forecast`.
    target_gw:
        The gameweek being prepared for. The forecast at ``target_gw`` is lag-safe (the terms fit on
        ``gw < target_gw``).
    n:
        Maximum number of candidates to return across all positions.

    Returns
    -------
    DataFrame ranked by ``captain_score`` (= ``p_haul``) descending, tie-broken by ``p90``, with the
    ceiling reads carried for explainability. ``captain_rank`` is the within-position rank.

    Only players with ``minutes_roll3 >= 45`` (reliable starters) are eligible.
    """
    validate_intelligence_inputs(features, "rank_captain_candidates")
    missing = [c for c in _FORECAST_COLS if c not in features.columns]
    if missing:
        raise IntelligenceInputError(
            f"rank_captain_candidates: missing model forecast columns {missing}. Enrich the mart with "
            "model.predictions.assemble_forecast before ranking (serve does not import model; the "
            "operational runner merges the forecast on (player_id, gw))."
        )

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"rank_captain_candidates: no data for gw={target_gw}")

    # Captaincy needs a reliable starter; a scored forecast row (p_haul defined) is required to rank.
    eligible = gw_df[~gw_df["is_warmup_gw"] & (gw_df["minutes_roll3"] >= _MIN_MINUTES_ROLL3)].copy()
    eligible = eligible.dropna(subset=["p_haul"])
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Ceiling bet: rank by the probability of a haul, tie-break on the 90th-percentile ceiling.
    eligible["captain_score"] = eligible["p_haul"].astype(float)
    eligible = eligible.sort_values(["captain_score", "p90"], ascending=False)
    eligible["captain_rank"] = (
        eligible.groupby("position_label")["captain_score"].rank(ascending=False, method="min").astype(int)
    )

    return eligible[_OUTPUT_COLS].head(n).reset_index(drop=True)
