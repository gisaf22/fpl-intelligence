"""Captain candidate ranking — model-driven.

Ranks captain options for a target gameweek by the forecaster's **haul probability** (``p_haul``) — the
distribution read the mean cannot give. Captaincy is a *ceiling* bet (you want the chance of a big
score, not the expected score), so we rank by ``p_haul`` and tie-break on the 90th-percentile ceiling
``p90``. Because ``p_haul`` is an absolute probability, it is comparable **across** positions — unlike
the retired within-position signal composite, whose normalised score made a DEF's 0.9 and a MID's 0.9
meaningless to compare.

This replaces the former composite (xgi form/involvement + fixture + minutes, statically weighted from
a serve weight registry — since retired, see ADR-011). Head-to-head over 2025-26 GW6-38: the model
captain returned **+1.9 pts/GW** vs the composite (5.09 vs 3.22; paired 95% CI [-0.03, +3.9]) — better on
the point estimate, never significantly worse. Per-position validity is enforced upstream by the term
gates, so the old xgi scope-guards (excluded at FWD/MID) are gone with the composite.

Structure: this module declares a :class:`domain.decision.DecisionSpec` and delegates the shared
lifecycle to :func:`serve.decision_engine.run_decision` (ADR-012). The forecast columns (``p_haul``,
``p90``, ``e_points_uncond``) arrive as data, merged onto the mart by the operational runner —
``serve`` does not import ``model`` (import-linter ``no_serve_to_research_or_model``).
"""

from __future__ import annotations

import pandas as pd

from domain.decision import DecisionSpec
from serve.decision_engine import run_decision

# threshold not evaluation-derived — see threshold-registry.md §CAPT-T-01
_MIN_MINUTES_ROLL3 = 45.0


def _eligible(features: pd.DataFrame, **_: object) -> pd.Series:
    """Captaincy needs a reliable starter."""
    return (~features["is_warmup_gw"]) & (features["minutes_roll3"] >= _MIN_MINUTES_ROLL3)


def _objective(features: pd.DataFrame) -> pd.Series:
    """Ceiling bet: rank by the probability of a haul."""
    return features["p_haul"]


CAPTAIN = DecisionSpec(
    name="rank_captain_candidates",
    required_forecast_cols=("p_haul", "p90", "e_points_uncond"),
    eligibility=_eligible,
    objective=_objective,
    score_col="captain_score",
    rank_col="captain_rank",
    output_cols=(
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
    ),
    tie_break=("p90",),  # same haul probability → prefer the higher 90th-percentile ceiling
)


def rank_captain_candidates(features: pd.DataFrame, target_gw: int, n: int = 20) -> pd.DataFrame:
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
    return run_decision(CAPTAIN, features, target_gw, n=n)
