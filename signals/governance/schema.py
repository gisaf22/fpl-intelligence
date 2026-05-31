"""Schema contract for governed EDA signal registries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
RESEARCH_REGISTRY_PATH = Path("studies/eda/findings/eda_03_joint_registry.csv")

# Operational: canonical destination for lifecycle-promoted registry artifacts.
OPERATIONAL_REGISTRY_DIR = Path("outputs/registry")

REQUIRED_COLUMNS: tuple[str, ...] = (
    # identity / primary key
    "signal",
    "position",
    "population_scope",
    # characterization synthesis — EDA-7 ownership (assembled from EDA-4/5 outputs)
    "population_robustness",
    "preferred_population",
    "temporal_stability",
    # registry_build metadata — analytics.registry.semantics.enrich_signal_layers()
    "signal_layer",
    "layer_role",
    "feature_candidate_eligible",
    "downstream_status",
    "interpretation_caveat",
    "variable_level",
    # registry_build computed — geometry section (sections._geometry_row)
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
    # registry_build computed — decomposition section (analytics.relationships.decompose_rho)
    "rho_pooled",
    "rho_between",
    "rho_within",
    "within_share",
    "panel_class",
    "decomposition_flag",
    "n_players",
    # registry_build computed — haul section (analytics.relationships.haul_concentration)
    "rho_full",
    "rho_no_haul",
    "rho_drop",
    "haul_pct",
    "n_haul",
    "tail_sensitive",
    # registry_build computed — assembly (analytics.relationships.assign_association_class)
    "association_class",
    # EDA-7 synthesis + registry_build computed — analytics.registry.promotion
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
POPULATION_ROBUSTNESS_VALUES: frozenset[str] = frozenset(
    {"stable", "scope_sensitive", "untested"}
)
VARIABLE_LEVEL_VALUES: frozenset[str] = frozenset({"player_level", "match_level"})
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
DOWNSTREAM_STATUS_VALUES: frozenset[str] = frozenset(
    {"eligible", "caveated", "blocked", "approved"}
)
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
PANEL_CLASS_VALUES: frozenset[str] = frozenset(
    {"state_sensitive", "mixed", "identity_dominant", "indeterminate"}
)
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

NON_FEATURE_SIGNAL_LAYERS: frozenset[str] = frozenset(
    {"context", "market_behavior", "valuation", "exposure"}
)

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
# structural exclusions — position-role mismatches (goals_scored×GK) or >99% zero mass
# (red_cards×GK). These are not data quality issues and are not recoverable from the registry.

# Columns where null/empty is a valid governed state (not a data error).
# support_type is empty when no support failure exists.
# promotion_class is null for blocked rows.
NULLABLE_CONTROLLED_COLUMNS: frozenset[str] = frozenset({"support_type", "promotion_class"})

# ---------------------------------------------------------------------------
# Runtime governance metadata
# ---------------------------------------------------------------------------

LIFECYCLE_STATE_VALUES: frozenset[str] = frozenset(
    {"candidate", "excluded", "not_applicable", "approved"}
)
LEAKAGE_RISK_VALUES: frozenset[str] = frozenset(
    {"none", "evaluation_circularity", "direct"}
)


@dataclass(frozen=True)
class GovernanceMetadata:
    """Runtime governance container for a single signal-position pair.

    Populated from evaluation_metadata.yaml via get_signal_governance().
    When a signal appears in multiple lens studies, the most favorable
    lifecycle_state is returned (candidate > excluded > not_applicable).
    """

    signal: str
    position: str
    signal_id: str           # e.g. "FORM-001"
    lens: str                # e.g. "FORM"
    lifecycle_state: str     # candidate | excluded | not_applicable
    downstream_status: str   # eligible | caveated | blocked
    leakage_risk: str        # none | evaluation_circularity | direct
    behavioral_reason: str
    source_gate_decisions: tuple[str, ...]
    rho_pooled: float | None
    ci_lower: float | None
    ci_upper: float | None


class GovernanceMetadataError(ValueError):
    """Raised when evaluation governance metadata is missing or unresolvable."""


# Signals that predate the lens-study methodology and have no evaluation_metadata.yaml record.
# Any confirmed signal absent from both this set and evaluation_metadata.yaml is ungoverned
# and must not enter the scoring manifest.
PRE_LENS_SIGNAL_ALLOWLIST: frozenset[str] = frozenset({
    "assists",
    "clean_sheets",
    "creativity",
    "goals_conceded",
    "goals_scored",
    "ict_index",
    "influence",
    "saves",
    "threat",
    "xa",
    "xg",
    "xgc",
    "xgi",
    "yellow_cards",
})
