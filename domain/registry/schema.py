"""Schema contract for governed EDA signal registries."""

from __future__ import annotations

from pathlib import Path

from domain.signal_layers import SIGNAL_LAYER_VALUES

# Promotion class vocabulary is defined here to avoid circular imports
# (promotion.py imports pandas; schema.py must remain import-light).
PROMOTION_CLASS_VALUES: frozenset[str] = frozenset(
    {
        "core_signal",
        "review_signal",
        "context_control",
        "exposure_control",
        "market_context",
    }
)


# Research-only: the authoritative system EDA output. Not for operational consumers.
# Operational consumers (scorer, report runner) must use registries from OPERATIONAL_REGISTRY_DIR.
RESEARCH_REGISTRY_PATH = Path("research/findings/records/eda_03_joint_registry.csv")

# Operational: canonical destination for lifecycle-promoted registry artifacts.
OPERATIONAL_REGISTRY_DIR = Path("outputs/registry")

REQUIRED_COLUMNS: tuple[str, ...] = (
    # identity / primary key
    "signal",
    "position",
    "population_scope",
    # characterization synthesis — composition/synthesis (model/assemble)
    "population_robustness",
    "preferred_population",
    "temporal_stability",
    # semantic enrichment — model.governance.semantics.enrich_signal_layers()
    "signal_layer",
    "layer_role",
    "feature_candidate_eligible",
    "downstream_status",
    "interpretation_caveat",
    "variable_level",
    # registry-build computed — geometry section (research/registry build via research.kernels)
    "bucketing_scheme",
    "n_records",
    "zero_fraction",
    "active_bin_count",
    "effective_n_per_bin",
    "q1_q5_mean_gap",
    "relationship_geometry",
    "monotonicity_confidence",
    "low_confidence",
    "support_flags",
    "support_type",
    # registry-build computed — decomposition section (research.kernels.correlation.panel)
    "rho_pooled",
    "rho_between",
    "rho_within",
    "within_share",
    "panel_class",
    "decomposition_flag",
    "n_players",
    # registry-build computed — haul section (research.kernels.correlation.tail)
    "rho_full",
    "rho_no_haul",
    "rho_drop",
    "haul_pct",
    "n_haul",
    "tail_sensitive",
    # registry-build computed — research.kernels.association.assign_association_class
    "association_class",
    # promotion class — model.governance.promotion.assign_promotion_class
    "promotion_class",
)

PRIMARY_KEY_COLUMNS: tuple[str, ...] = (
    "signal",
    "position",
    "population_scope",
)

BOOLEAN_COLUMNS: tuple[str, ...] = (
    "feature_candidate_eligible",
    "low_confidence",
    "tail_sensitive",
)

INTEGER_COLUMNS: tuple[str, ...] = (
    "n_records",
    "n_players",
    "n_haul",
)

NUMERIC_COLUMNS: tuple[str, ...] = (
    "zero_fraction",
    "active_bin_count",
    "effective_n_per_bin",
    "q1_q5_mean_gap",
    "monotonicity_confidence",
    "rho_pooled",
    "rho_between",
    "rho_within",
    "within_share",
    "rho_full",
    "rho_no_haul",
    "rho_drop",
    "haul_pct",
)

NON_EMPTY_COLUMNS: tuple[str, ...] = (
    "signal",
    "position",
    "population_scope",
    "population_robustness",
    "signal_layer",
    "layer_role",
    "downstream_status",
    "interpretation_caveat",
    "variable_level",
    "preferred_population",
    "bucketing_scheme",
    "relationship_geometry",
    "temporal_stability",
    "panel_class",
    "association_class",
)

POSITION_VALUES: frozenset[str] = frozenset({"GK", "DEF", "MID", "FWD"})
POPULATION_SCOPE_VALUES: frozenset[str] = frozenset({"primary", "secondary"})
POPULATION_ROBUSTNESS_VALUES: frozenset[str] = frozenset({"stable", "scope_sensitive", "untested"})
VARIABLE_LEVEL_VALUES: frozenset[str] = frozenset({"player_level", "match_level"})
DOWNSTREAM_STATUS_VALUES: frozenset[str] = frozenset({"eligible", "caveated", "blocked", "approved"})
GEOMETRY_VALUES: frozenset[str] = frozenset(
    {
        "monotonic_positive",
        "monotonic_negative",
        "threshold_positive",
        "threshold_negative",
        "saturation",
        "non_monotonic",
        "asymmetric_tail",
        "indeterminate",
        "unassessable",
    }
)
ASSOCIATION_CLASS_VALUES: frozenset[str] = frozenset(
    {
        "continuous_monotonic",
        "upper_tail_concentrated",
        "tail_dependent",
        "temporally_unstable",
        "weak_association",
        "unassessable",
    }
)
SUPPORT_TYPE_VALUES: frozenset[str] = frozenset(
    {
        "sparse_event_process",
        "structural_binary",
        "near_constant_position",
        "ordinal_scheme_mismatch",
        "insufficient_n",
    }
)
PANEL_CLASS_VALUES: frozenset[str] = frozenset({"state_sensitive", "mixed", "identity_dominant", "indeterminate"})
TEMPORAL_STABILITY_VALUES: frozenset[str] = frozenset(
    {"stable", "moderate_shift", "unstable", "unassessable", "insufficient_data"}
)

MATCH_LEVEL_SIGNALS: frozenset[str] = frozenset(
    {
        "was_home",
        "goals_conceded",
        "fixture_count",
        "fdr_avg",
        "is_dgw",
    }
)

NON_FEATURE_SIGNAL_LAYERS: frozenset[str] = frozenset({"context", "market_behavior", "valuation", "exposure"})

CONTROLLED_VALUE_COLUMNS: dict[str, frozenset[str]] = {
    "position": POSITION_VALUES,
    "population_scope": POPULATION_SCOPE_VALUES,
    "population_robustness": POPULATION_ROBUSTNESS_VALUES,
    "variable_level": VARIABLE_LEVEL_VALUES,
    "signal_layer": SIGNAL_LAYER_VALUES,
    "downstream_status": DOWNSTREAM_STATUS_VALUES,
    "relationship_geometry": GEOMETRY_VALUES,
    "association_class": ASSOCIATION_CLASS_VALUES,
    "support_type": SUPPORT_TYPE_VALUES,
    "panel_class": PANEL_CLASS_VALUES,
    "temporal_stability": TEMPORAL_STABILITY_VALUES,
    "promotion_class": PROMOTION_CLASS_VALUES,
}

# downstream_status="blocked" with relationship_geometry="unassessable" marks permanent
# structural exclusions — position-role mismatches (goals_scored x GK) or >99% zero mass
# (red_cards x GK). These are not data quality issues and are not recoverable from the registry.

# Columns where null/empty is a valid governed state (not a data error).
# support_type is empty when no support failure exists.
# promotion_class is null for blocked rows.
NULLABLE_CONTROLLED_COLUMNS: frozenset[str] = frozenset({"support_type", "promotion_class"})

# ---------------------------------------------------------------------------
# Runtime governance metadata
# ---------------------------------------------------------------------------
# The runtime governance verdict contract (GovernanceMetadata, its error type,
# the lifecycle/leakage vocabularies, and the pre-lens allowlist) lives in
# domain.registry.governance_types — it is the contract for evaluation_metadata.yaml
# lookups, not for the registry CSV. Kept separate so this module stays the
# single concern "what is a valid registry row".
