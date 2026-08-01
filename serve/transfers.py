"""Transfer target ranking — model-driven.

Ranks incoming transfer candidates by the forecaster's ex-ante expected points for the upcoming
gameweek: ``transfer_score = e_points_uncond`` (= ``P(play) x E[points | played]``, so appearance risk
is already priced in). A transfer is a squad-in decision — you want the highest expected return, and
price is a separate budget constraint (carried in the output for the manager, not in the score).

This replaces the former composite (xgi form + momentum + fixture + involvement + minutes, statically
weighted from ``weight_registry.yaml``). Head-to-head over 2025-26 GW6-35 (3-GW forward hold): the model
ranker returned **+1.73 cumulative pts/decision** vs the composite (10.87 vs 9.14; paired 95% CI
[+0.76, +2.70], wins 24/30 GWs) — **significantly better**. Per-position validity is enforced upstream
by the term gates, so the old xgi scope-guards (excluded at FWD/MID) are gone with the composite.

The ranker scores the **upcoming** GW only (``e_points_uncond`` at ``target_gw``), which is strictly
lag-safe (the terms fit on ``gw < target_gw``). A multi-week forward hold would need per-decision
multi-step forecasts frozen at the deadline; summing the precomputed forecast column across future GWs
would leak post-decision state, so it is deliberately not done here.

Input: the DAL mart **enriched** with the model forecast column ``e_points_uncond`` from
:func:`model.predictions.assemble_forecast`, merged on ``(player_id, gw)`` by the operational runner —
``serve`` does not import ``model`` (import-linter ``no_serve_to_research_or_model``), so the forecast
arrives as data, not a call.
"""

from __future__ import annotations

import pandas as pd

from serve.input_contracts import IntelligenceInputError, validate_intelligence_inputs

# threshold not evaluation-derived — see threshold-registry.md §TRANS-T-01
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
    "transfer_score",
    "transfer_rank",
]


def rank_transfer_targets(
    features: pd.DataFrame,
    target_gw: int,
    n: int = 20,
    position: str | None = None,
) -> pd.DataFrame:
    """Rank transfer-in candidates for a target gameweek by model expected points.

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
    position:
        Optional position filter: 'GK', 'DEF', 'MID', or 'FWD'.
        When None, returns top-n across all positions.

    Returns
    -------
    DataFrame ranked by ``transfer_score`` (= ``e_points_uncond``) descending, with the expected-points
    read carried for explainability. ``transfer_rank`` is the within-position rank.

    Only players with ``minutes_roll5 >= 30`` (and a scored forecast row) are eligible.
    """
    validate_intelligence_inputs(features, "rank_transfer_targets")
    missing = [c for c in _FORECAST_COLS if c not in features.columns]
    if missing:
        raise IntelligenceInputError(
            f"rank_transfer_targets: missing model forecast columns {missing}. Enrich the mart with "
            "model.predictions.assemble_forecast before ranking (serve does not import model; the "
            "operational runner merges the forecast on (player_id, gw))."
        )

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"rank_transfer_targets: no data for gw={target_gw}")

    if position is not None:
        gw_df = gw_df[gw_df["position_label"] == position]
        if gw_df.empty:
            return pd.DataFrame(columns=_OUTPUT_COLS)

    eligible = gw_df[~gw_df["is_warmup_gw"] & (gw_df["minutes_roll5"] >= _MIN_MINUTES_ROLL5)].copy()
    # A scored forecast row (e_points_uncond defined) is required to rank.
    eligible = eligible.dropna(subset=["e_points_uncond"])
    if eligible.empty:
        return pd.DataFrame(columns=_OUTPUT_COLS)

    # Best incoming pick = highest ex-ante expected points for the upcoming GW.
    eligible["transfer_score"] = eligible["e_points_uncond"].astype(float)
    eligible = eligible.sort_values("transfer_score", ascending=False)
    eligible["transfer_rank"] = (
        eligible.groupby("position_label")["transfer_score"].rank(ascending=False, method="min").astype(int)
    )

    return eligible[_OUTPUT_COLS].head(n).reset_index(drop=True)
