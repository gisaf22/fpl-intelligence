"""Ontology consistency tests.

Checks that signal-ontology.yaml is structurally valid and consistent with
the signals used by the STATE layer.

The scope cross-check against STATE_CONTRACT.md is stubbed — enable it in
Phase 4 once STATE_CONTRACT.md has machine-readable scope annotations.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ONTOLOGY_YAML = _REPO_ROOT / "docs" / "foundations" / "signal-ontology.yaml"

_REQUIRED_FIELDS = {"family", "scope", "temporal_type", "semantic_constraint"}
_VALID_TEMPORAL_TYPES = {"count", "rate", "stock", "indicator", "estimate"}
_VALID_SCOPES = {"Individual", "Team", "Population", "Match"}
_VALID_FAMILIES = {
    "Outcome",
    "Allocation",
    "Event",
    "Process",
    "Participation",
    "Market",
    "Structural Tier",
    "Context",
}

# Base signals referenced by STATE rolling windows (total_points aliased to points in column names)
_STATE_BASE_SIGNALS = {
    "total_points",
    "minutes",
    "xg",
    "xgi",
    "xgc",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "saves",
    "penalties_saved",
    "bonus",
    "bps",
}


@pytest.fixture(scope="module")
def ontology() -> dict:
    data = yaml.safe_load(_ONTOLOGY_YAML.read_text())
    return data["signals"]


def test_yaml_loads(ontology):
    assert len(ontology) == 23, f"Expected 23 signals, got {len(ontology)}"


def test_all_required_fields_present(ontology):
    missing = {
        signal: _REQUIRED_FIELDS - set(attrs) for signal, attrs in ontology.items() if _REQUIRED_FIELDS - set(attrs)
    }
    assert not missing, f"Signals missing fields: {missing}"


def test_temporal_types_are_valid(ontology):
    invalid = {
        signal: attrs["temporal_type"]
        for signal, attrs in ontology.items()
        if attrs.get("temporal_type") not in _VALID_TEMPORAL_TYPES
    }
    assert not invalid, f"Invalid temporal_type values: {invalid}"


def test_scopes_are_valid(ontology):
    invalid = {signal: attrs["scope"] for signal, attrs in ontology.items() if attrs.get("scope") not in _VALID_SCOPES}
    assert not invalid, f"Invalid scope values: {invalid}"


def test_families_are_valid(ontology):
    invalid = {
        signal: attrs["family"] for signal, attrs in ontology.items() if attrs.get("family") not in _VALID_FAMILIES
    }
    assert not invalid, f"Invalid family values: {invalid}"


def test_state_base_signals_present_in_ontology(ontology):
    """Every signal STATE derives rolling columns from must exist in the ontology."""
    missing = _STATE_BASE_SIGNALS - set(ontology)
    assert not missing, f"STATE base signals missing from ontology: {sorted(missing)}"


def test_state_base_signals_have_rollable_temporal_type(ontology):
    """Signals used for rolling averages in STATE should not be stocks or indicators.

    Rolling a stock (ownership_count) or indicator (clean_sheets) produces a proportion
    or a meaningless level average. If any STATE base signal has these types it signals
    a representation design issue that should be resolved before it reaches scoring.
    """
    non_rollable = {"stock", "indicator"}
    violations = {
        signal: ontology[signal]["temporal_type"]
        for signal in _STATE_BASE_SIGNALS
        if signal in ontology and ontology[signal]["temporal_type"] in non_rollable
    }
    assert not violations, (
        f"STATE base signals with non-rollable temporal_type: {violations}\n"
        "Rolling averages of stock or indicator signals are semantically invalid — "
        "remove from _ROLL_COLS or reclassify the temporal_type with justification."
    )


@pytest.mark.skip(reason="Enable in Phase 4 once STATE_CONTRACT.md has machine-readable scope annotations")
def test_scope_consistency_yaml_vs_state_contract():
    """For every signal in both ontology YAML and STATE_CONTRACT.md, scope must match.

    To enable: parse scope annotations from STATE_CONTRACT.md and compare against
    ontology[signal]['scope'] for each STATE derived column's base signal.
    """
    pass
