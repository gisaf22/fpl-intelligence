"""Semantic enrichment helpers — study-layer copy.

SIGNAL_LAYER_VALUES inlined; no signals.* imports.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# inlined from signals.governance.schema
SIGNAL_LAYER_VALUES: frozenset[str] = frozenset(
    {
        "exposure",
        "performance",
        "context",
        "market_behavior",
        "valuation",
        "discipline",
        "defensive_context",
    }
)

SIGNAL_LAYER_MAPPING: dict[str, dict[str, Any]] = {
    "minutes": {
        "signal_layer": "exposure",
        "layer_role": "outcome_access",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "eligibility/access signal, not quality",
    },
    "starts": {
        "signal_layer": "exposure",
        "layer_role": "selection_access",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "selection proxy, not quality",
    },
    "bps": {
        "signal_layer": "performance",
        "layer_role": "contribution_index",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "descriptive contribution index, not causal",
    },
    "bonus": {
        "signal_layer": "performance",
        "layer_role": "points_component",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "scoring outcome component; avoid target leakage in modeling",
    },
    "ict_index": {
        "signal_layer": "performance",
        "layer_role": "composite_contribution",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "descriptive composite index",
    },
    "influence": {
        "signal_layer": "performance",
        "layer_role": "contribution_component",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "descriptive component",
    },
    "creativity": {
        "signal_layer": "performance",
        "layer_role": "chance_creation",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "position-sensitive support required",
    },
    "threat": {
        "signal_layer": "performance",
        "layer_role": "attacking_threat",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "position-sensitive support required",
    },
    "xg": {
        "signal_layer": "performance",
        "layer_role": "chance_quality",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "position-sensitive support required",
    },
    "xa": {
        "signal_layer": "performance",
        "layer_role": "chance_creation_quality",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "position-sensitive support required",
    },
    "xgi": {
        "signal_layer": "performance",
        "layer_role": "attacking_chance_quality",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "position-sensitive support required",
    },
    "goals_scored": {
        "signal_layer": "performance",
        "layer_role": "scoring_event",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "sparse event caveats apply",
    },
    "assists": {
        "signal_layer": "performance",
        "layer_role": "creation_event",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "sparse event caveats apply",
    },
    "clean_sheets": {
        "signal_layer": "defensive_context",
        "layer_role": "defensive_points_context",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "team/role dependent scoring context",
    },
    "saves": {
        "signal_layer": "defensive_context",
        "layer_role": "goalkeeper_action",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "GK-specific; not comparable across positions",
    },
    "xgc": {
        "signal_layer": "defensive_context",
        "layer_role": "defensive_environment",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "team/fixture defensive context, not attacking performance",
    },
    "fdr_avg": {
        "signal_layer": "context",
        "layer_role": "fixture_difficulty",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "match-level schedule context",
    },
    "fdr_min": {
        "signal_layer": "context",
        "layer_role": "fixture_difficulty",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "per-fixture minimum FDR; removed from spine — superseded by fdr_avg",
    },
    "fdr_max": {
        "signal_layer": "context",
        "layer_role": "fixture_difficulty",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "per-fixture maximum FDR; removed from spine — superseded by fdr_avg",
    },
    "was_home": {
        "signal_layer": "context",
        "layer_role": "match_environment",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "match-level context, not player intrinsic",
    },
    "fixture_count": {
        "signal_layer": "context",
        "layer_role": "schedule_volume",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "schedule/exposure multiplier",
    },
    "goals_conceded": {
        "signal_layer": "defensive_context",
        "layer_role": "defensive_outcome_context",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "team defensive outcome, not player quality",
    },
    "ownership_count": {
        "signal_layer": "market_behavior",
        "layer_role": "popularity_proxy",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "popularity/demand, not quality",
    },
    "transfers_balance": {
        "signal_layer": "market_behavior",
        "layer_role": "demand_net_flow",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "net transfer flow (transfers_in − transfers_out); removed from spine — uninformative all positions",
    },
    "transfers_in": {
        "signal_layer": "market_behavior",
        "layer_role": "demand_inflow",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "behavioral demand signal",
    },
    "transfers_out": {
        "signal_layer": "market_behavior",
        "layer_role": "demand_outflow",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "behavioral demand signal",
    },
    "purchase_price": {
        "signal_layer": "valuation",
        "layer_role": "market_pricing",
        "feature_candidate_eligible": False,
        "interpretation_caveat": "price embeds historical, role, and market effects",
    },
    "yellow_cards": {
        "signal_layer": "discipline",
        "layer_role": "negative_event",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "sparse/low-frequency caveats apply",
    },
    "red_cards": {
        "signal_layer": "discipline",
        "layer_role": "negative_event",
        "feature_candidate_eligible": True,
        "interpretation_caveat": "sparse/low-frequency caveats apply",
    },
}


def _has_value(value: Any) -> bool:
    """Return True when a registry scalar is present after CSV/NaN coercions."""
    if value is None:
        return False
    if pd.isna(value):
        return False
    return str(value).strip() != ""


def assign_downstream_status(row: dict[str, Any]) -> str:
    """Assign row-level downstream governance status."""
    support_flags = str(row.get("support_flags", ""))
    support_type = row.get("support_type", "")
    geom = row.get("relationship_geometry", "")

    if (
        "insufficient_support" in support_flags
        or support_type in {"insufficient_n", "near_constant_position"}
        or geom == "unassessable"
    ):
        return "blocked"

    caveated_layers = {"context", "market_behavior", "valuation"}
    if (
        row.get("low_confidence", False) == True  # noqa: E712
        or geom == "indeterminate"
        or row.get("panel_class", "") == "indeterminate"
        or _has_value(support_type)
        or row.get("signal_layer") in caveated_layers
    ):
        return "caveated"

    if row.get("feature_candidate_eligible", False) == True:  # noqa: E712
        return "eligible"

    return "caveated"


def enrich_signal_layers(registry: pd.DataFrame) -> pd.DataFrame:
    """Merge semantic signal-layer metadata and downstream status into registry."""
    missing = sorted(set(registry["signal"]) - set(SIGNAL_LAYER_MAPPING))
    if missing:
        raise ValueError(
            "Signal-layer mapping missing entries for signals: "
            + ", ".join(missing)
        )

    layer_df = pd.DataFrame.from_dict(SIGNAL_LAYER_MAPPING, orient="index")
    layer_df.index.name = "signal"
    layer_df = layer_df.reset_index()

    semantic_cols = [
        "signal_layer",
        "layer_role",
        "feature_candidate_eligible",
        "interpretation_caveat",
        "downstream_status",
    ]
    enriched = registry.drop(
        columns=[column for column in semantic_cols if column in registry.columns]
    ).merge(layer_df, on="signal", how="left")
    enriched["feature_candidate_eligible"] = (
        enriched["feature_candidate_eligible"].astype(bool)
    )
    enriched["downstream_status"] = [
        assign_downstream_status(row)
        for row in enriched.to_dict(orient="records")
    ]
    return enriched
