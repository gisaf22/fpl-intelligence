import pandas as pd
import pytest

from domain.registry.operational import load_registry
from research.registry.assembler import assemble_registry_from_sections

pytestmark = pytest.mark.unit

# Columns applied by governance enrichment at promotion time (model.governance),
# not by the research build. The assembler emits a raw evidence finding without them.
_GOVERNANCE_ENRICHED_COLUMNS = (
    "signal_layer",
    "layer_role",
    "feature_candidate_eligible",
    "downstream_status",
    "interpretation_caveat",
    "promotion_class",
)


def _split_current_registry(registry: pd.DataFrame):
    geometry_columns = [
        "signal",
        "position",
        "population_scope",
        "population_robustness",
        "variable_level",
        "preferred_population",
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
    ]
    stability_columns = ["signal", "position", "temporal_stability"]
    decomposition_columns = [
        "signal",
        "position",
        "rho_pooled",
        "rho_between",
        "rho_within",
        "within_share",
        "panel_class",
        "decomposition_flag",
        "n_players",
    ]
    haul_columns = [
        "signal",
        "position",
        "rho_full",
        "rho_no_haul",
        "rho_drop",
        "haul_pct",
        "n_haul",
        "tail_sensitive",
    ]

    return (
        registry[geometry_columns],
        registry[stability_columns],
        registry[decomposition_columns].assign(support_flag=""),
        registry[haul_columns].assign(support_flag=""),
    )


def test_assemble_registry_from_sections_emits_raw_evidence_finding():
    """The build assembles raw evidence only — governance enrichment is applied at
    promotion time (model.governance), so the assembled finding must NOT carry the
    governance-enriched columns and must carry the computed evidence."""
    current = load_registry()
    geometry, stability, decomposition, haul = _split_current_registry(current)

    assembled = assemble_registry_from_sections(
        geometry=geometry,
        stability=stability,
        decomposition=decomposition,
        haul=haul,
        expected_n=len(current),
    )

    assert len(assembled) == len(current)
    # Governance enrichment has not run yet.
    for column in _GOVERNANCE_ENRICHED_COLUMNS:
        assert column not in assembled.columns, f"{column} should be added at promotion, not build"
    # Raw evidence the build is responsible for is present.
    assert "association_class" in assembled.columns
    assert "rho_pooled" in assembled.columns
    assert "support_flags" in assembled.columns
    pd.testing.assert_series_equal(
        assembled["association_class"].reset_index(drop=True),
        current["association_class"].reset_index(drop=True),
        check_names=False,
    )


def test_assemble_registry_from_sections_rejects_duplicate_section_keys():
    current = load_registry()
    geometry, stability, decomposition, haul = _split_current_registry(current)
    bad_stability = pd.concat([stability, stability.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate signal-position keys"):
        assemble_registry_from_sections(
            geometry=geometry,
            stability=bad_stability,
            decomposition=decomposition,
            haul=haul,
            expected_n=len(current),
        )
