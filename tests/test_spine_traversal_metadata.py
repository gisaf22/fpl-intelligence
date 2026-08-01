"""Baseline traversal metadata checks for the analytical object spine.

Phase 0 guardrail for the spine traversal refactor plan: existing explicit
metadata links must remain resolvable before adding new routing fields.
"""

from pathlib import Path

import pytest
import yaml

from dal.feat.feat_schema import FEATURE_REGISTRY
from domain.registry.governance_lookup import get_signal_governance_by_key
from domain.registry.governance_types import GovernanceMetadata

pytestmark = pytest.mark.unit

_TRACEABILITY_PATH = Path("model/governance/signal_traceability.yaml")


def _load_traceability() -> dict:
    with _TRACEABILITY_PATH.open() as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


def _finding_key(entry: dict) -> str:
    lens = entry["evaluation_lens"].lower().replace("-", "_")
    return f"{entry['signal']}@{lens}:{entry['evaluation_target']}"


def test_feature_registry_gate_values_are_non_empty():
    """Every governed feature record keeps a non-empty gate reference."""
    violations = [feature for feature, record in FEATURE_REGISTRY.items() if not record.gate]
    assert not violations, "FEATURE_REGISTRY entries with empty gate:\n" + "\n".join(sorted(violations))


def test_traceability_declares_analysis_paths_for_evaluation_lenses():
    """Every evaluated traceability lens has a single analysis implementation path."""
    traceability = _load_traceability()
    analysis_paths = traceability.get("analysis_paths", {})
    failures = []

    for entry in traceability.get("entries", []):
        lens = entry.get("evaluation_lens")
        if lens == "STATE-ONLY":
            continue
        analysis_path = analysis_paths.get(lens)
        if not analysis_path:
            failures.append(f"{entry.get('signal')} {entry.get('position')}: no analysis_path for lens {lens}")
        elif not Path(analysis_path).exists():
            failures.append(f"{lens}: analysis_path does not exist: {analysis_path}")

    assert not failures, "Traceability entries without valid analysis paths:\n" + "\n".join(failures)


def test_approved_feature_positions_route_to_resolvable_findings_via_traceability():
    """Approved FEATURE_REGISTRY signal-position pairs route to findings without DAL owning findings."""
    traceability = _load_traceability()
    entries = traceability.get("entries", [])
    by_signal_position = {(entry["signal"], entry["position"]): entry for entry in entries}
    failures = []

    for feature, record in FEATURE_REGISTRY.items():
        if record.status != "APPROVED":
            continue
        for position in record.positions:
            entry = by_signal_position.get((feature, position))
            if entry is None:
                failures.append(f"{feature}#{position}: no traceability entry")
                continue
            if entry.get("evaluation_lens") == "STATE-ONLY":
                continue
            if entry.get("evaluation_target") is None:
                failures.append(f"{feature}#{position}: traceability entry has no evaluated finding route")
                continue
            key = f"{_finding_key(entry)}#{position}"
            try:
                governance = get_signal_governance_by_key(key)
                assert isinstance(governance, GovernanceMetadata)
            except Exception as exc:
                failures.append(f"{feature}#{position}: {key}: {type(exc).__name__}: {exc}")

    assert not failures, "Approved features without deterministic traceability route:\n" + "\n".join(failures)
