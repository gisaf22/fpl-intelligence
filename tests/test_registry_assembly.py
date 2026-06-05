import pandas as pd
import pytest

from domain.registry.operational import load_registry
from domain.registry.validation import validate_registry_contract
from research.registry.assembler import assemble_registry_from_sections

pytestmark = pytest.mark.unit


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


def test_assemble_registry_from_sections_preserves_current_registry_contract():
    current = load_registry()
    geometry, stability, decomposition, haul = _split_current_registry(current)

    assembled = assemble_registry_from_sections(
        geometry=geometry,
        stability=stability,
        decomposition=decomposition,
        haul=haul,
        expected_n=len(current),
    )

    validate_registry_contract(assembled)
    assert list(assembled.columns) == list(current.columns)
    assert len(assembled) == len(current)
    pd.testing.assert_series_equal(
        assembled["association_class"],
        current["association_class"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        assembled["downstream_status"],
        current["downstream_status"],
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
