"""The generic decision engine — the shared lifecycle every DecisionSpec runs through (ADR-012 §5).

One place holds what captain/value/transfers used to each hand-roll: validate the mart, guard the
required forecast columns, slice to the target gameweek, apply the spec's eligibility, score by the
spec's objective, rank within position, and project the spec's output columns. A decision module is
then just a :class:`domain.decision.DecisionSpec` plus a thin public wrapper.

``serve`` reads the model forecast as data (columns merged onto the mart by the operational runner);
it does not import ``model`` (import-linter ``no_serve_to_research_or_model``).
"""

from __future__ import annotations

import pandas as pd

from domain.decision import DecisionSpec
from serve.input_contracts import IntelligenceInputError, validate_intelligence_inputs


def run_decision(
    spec: DecisionSpec,
    features: pd.DataFrame,
    target_gw: int,
    *,
    n: int = 20,
    **params: object,
) -> pd.DataFrame:
    """Rank candidates for ``target_gw`` under ``spec``.

    The lifecycle is identical across decisions; only the spec's slots differ. ``params`` are the
    decision's optional filters (e.g. ``max_price``, ``position``), forwarded to ``spec.eligibility``.

    Returns a DataFrame at ``spec.output_cols`` ranked by ``spec.score_col`` (descending, tie-broken by
    ``spec.tie_break``), with ``spec.rank_col`` the within-position rank. Returns an empty frame at the
    same columns when no candidate is eligible; raises :class:`IntelligenceInputError` when the mart is
    unenriched or ``target_gw`` is absent.
    """
    validate_intelligence_inputs(features, spec.name)

    missing = [c for c in spec.required_forecast_cols if c not in features.columns]
    if missing:
        raise IntelligenceInputError(
            f"{spec.name}: missing model forecast columns {missing}. Enrich the mart with "
            "model.predictions.assemble_forecast before ranking (serve does not import model; the "
            "operational runner merges the forecast on (player_id, gw))."
        )

    gw_df = features[features["gw"] == target_gw].copy()
    if gw_df.empty:
        raise IntelligenceInputError(f"{spec.name}: no data for gw={target_gw}")

    eligible = gw_df[spec.eligibility(gw_df, **params)].copy()
    # Score first, then drop rows the forecast did not score — equivalent to each module's former
    # dropna on its score-input column, but expressed once (a NaN objective becomes a NaN score).
    eligible[spec.score_col] = spec.objective(eligible).astype(float)
    eligible = eligible.dropna(subset=[spec.score_col])
    if eligible.empty:
        return pd.DataFrame(columns=list(spec.output_cols))

    eligible = eligible.sort_values([spec.score_col, *spec.tie_break], ascending=False)
    eligible[spec.rank_col] = (
        eligible.groupby("position_label")[spec.score_col].rank(ascending=False, method="min").astype(int)
    )
    return eligible.loc[:, list(spec.output_cols)].head(n).reset_index(drop=True)
