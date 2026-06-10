import pandas as pd
import pytest

from domain.registry.validation import validate_registry_contract
from domain.registry.association import assign_association_class, consolidate_flags
from research.kernels.diagnostic.panel import split_between_within_player_rho
from research.kernels.diagnostic.tail import measure_tail_event_dependence
from research.registry.assembler import assemble_registry_from_sections
from research.registry.sections import SectionBuildConfig, compute_relationship_sections

pytestmark = pytest.mark.unit


def test_split_between_within_player_rho_returns_panel_metrics_for_supported_slice():
    rows = []
    for player_id in range(20):
        for gw in range(5):
            rows.append(
                {
                    "player_id": player_id,
                    "position": "MID",
                    "signal": player_id + gw * 0.1,
                    "target": player_id * 0.8 + gw * 0.2,
                }
            )
    df = pd.DataFrame(rows)

    result = split_between_within_player_rho(df, "signal", "target", "MID")

    assert result["support_flag"] == ""
    assert result["n_records"] == 100
    assert result["n_players"] == 20
    assert result["panel_class"] in {
        "state_sensitive",
        "mixed",
        "identity_dominant",
        "indeterminate",
    }
    assert pd.notna(result["rho_pooled"])


def test_measure_tail_event_dependence_uses_fixed_haul_threshold():
    df = pd.DataFrame(
        {
            "position": ["FWD"] * 100,
            "signal": list(range(100)),
            "target": [2] * 60 + [8] * 20 + [14] * 20,
        }
    )

    result = measure_tail_event_dependence(df, "signal", "target", "FWD")

    assert result["support_flag"] == ""
    assert result["n_haul"] == 20
    assert result["haul_pct"] == 20.0
    assert isinstance(result["tail_sensitive"], (bool, type(None)))


def test_association_class_precedence_and_flag_consolidation():
    assert (
        assign_association_class(
            {
                "support_flags": "insufficient_support:bin_density",
                "relationship_geometry": "monotonic_positive",
            }
        )
        == "unassessable"
    )
    assert (
        assign_association_class(
            {
                "support_flags": "",
                "relationship_geometry": "monotonic_positive",
                "temporal_stability": "stable",
                "rho_drop": 0.1,
                "low_confidence": False,
                "panel_class": "mixed",
            }
        )
        == "continuous_monotonic"
    )
    assert (
        assign_association_class(
            {
                "support_flags": "",
                "relationship_geometry": "monotonic_positive",
                "temporal_stability": "stable",
                "rho_drop": 0.1,
                "low_confidence": True,
                "panel_class": "mixed",
            }
        )
        == "weak_association"
    )
    assert (
        consolidate_flags(
            "insufficient_support:bin_density",
            "degenerate",
            "insufficient_support:bin_density",
            "",
        )
        == "insufficient_support:bin_density,degenerate"
    )


def test_compute_relationship_sections_iterates_signal_position_pairs():
    rows = []
    for position_index, position in enumerate(["GK", "DEF", "MID", "FWD"]):
        for player_id in range(20):
            for gw in range(5):
                value = player_id + gw + position_index
                rows.append(
                    {
                        "player_id": f"{position}-{player_id}",
                        "position": position,
                        "gw_block": "early" if gw < 2 else "mid" if gw < 4 else "late",
                        "bps": value,
                        "total_points": value * 0.5 + position_index,
                    }
                )
    data = pd.DataFrame(rows)

    sections = compute_relationship_sections(
        data,
        signals=["bps"],
        config=SectionBuildConfig(n_bootstrap=0),
    )

    assert len(sections.geometry) == 4
    assert len(sections.stability) == 4
    assert len(sections.decomposition) == 4
    assert len(sections.haul) == 4
    assert set(sections.geometry["position"]) == {"GK", "DEF", "MID", "FWD"}
    assert sections.geometry["signal"].eq("bps").all()
    assert sections.geometry["population_scope"].eq("primary").all()
    assert sections.geometry["variable_level"].eq("player_level").all()
    assert sections.geometry["n_records"].eq(100).all()


def test_compute_relationship_sections_can_feed_registry_assembly():
    rows = []
    for player_id in range(20):
        for gw in range(5):
            value = player_id + gw
            rows.append(
                {
                    "player_id": player_id,
                    "position": "MID",
                    "gw_block": "early" if gw < 2 else "mid" if gw < 4 else "late",
                    "bps": value,
                    "total_points": value,
                }
            )
    data = pd.DataFrame(rows)

    sections = compute_relationship_sections(
        data,
        signals=["bps"],
        config=SectionBuildConfig(positions=("MID",), n_bootstrap=0),
    )
    # The build assembles raw evidence; governance enriches at promotion. Mirror
    # that pipeline to obtain a contract-valid governed registry.
    from model.governance.promotion import enrich_promotion_class
    from model.governance.semantics import enrich_signal_layers

    registry = assemble_registry_from_sections(
        geometry=sections.geometry,
        stability=sections.stability,
        decomposition=sections.decomposition,
        haul=sections.haul,
        expected_n=1,
    )
    assert "downstream_status" not in registry.columns  # raw evidence finding
    registry = enrich_promotion_class(enrich_signal_layers(registry))

    validate_registry_contract(registry)
    assert registry.loc[0, "signal"] == "bps"
    assert registry.loc[0, "position"] == "MID"
    assert registry.loc[0, "downstream_status"] in {
        "eligible",
        "caveated",
        "blocked",
    }
