"""Canonical signal-layer vocabulary — below-research shared home.

Single source of truth for the signal-layer controlled vocabulary and the
per-signal semantic mapping. Lives in ``domain/`` (alongside ``fpl_scoring``)
so that both research characterization (``research.foundation``) and registry
construction (``model.governance.semantics``) can depend on it without either
importing the other — this is the edge that removes the foundation→model cycle.

No FPL scoring logic, no pandas, no governance imports.
"""

from __future__ import annotations

from typing import Any

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

# Leakage classification (ADR-010 ruling d): the ontology owns *which* layer_role values
# constitute target leakage / outcome-component. Serve enforces these at scoring time but
# does not re-list them — it imports these sets so the classification has one home.
#
# LEAKAGE_LAYER_ROLES        — signal IS or directly encodes the scoring target (e.g. bonus).
# OUTCOME_COMPONENT_LAYER_ROLES — signal is mechanistically tautological with FPL points
#                                 (e.g. bps, a descriptive contribution index).
LEAKAGE_LAYER_ROLES: frozenset[str] = frozenset({"points_component"})
OUTCOME_COMPONENT_LAYER_ROLES: frozenset[str] = frozenset({"contribution_index"})

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
