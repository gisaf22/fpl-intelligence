"""Baseline traversal metadata checks for the analytical object spine.

Phase 0 guardrail for the spine traversal refactor plan: existing explicit
metadata links must remain resolvable before adding new routing fields.
"""

from pathlib import Path

import pytest
import yaml

from dal.feat.feat_schema import FEATURE_REGISTRY
from signals.governance.governance import get_signal_governance_by_key
from signals.governance.schema import GovernanceMetadata

pytestmark = pytest.mark.unit

_WEIGHT_REGISTRY_PATH = Path("signals/governance/weight_registry.yaml")
_TRACEABILITY_PATH = Path("signals/characterisation/signal_traceability.yaml")


def _load_weight_registry() -> dict:
    with _WEIGHT_REGISTRY_PATH.open() as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


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


def test_weight_registry_signal_ids_resolve_when_present():
    """Every explicit decision signal_id resolves through governance metadata."""
    registry = _load_weight_registry()
    failures = []

    for module_name, module in registry.get("modules", {}).items():
        for weight_name, entry in module.get("weights", {}).items():
            signal_id = entry.get("signal_id")
            if signal_id is None:
                continue
            try:
                governance = get_signal_governance_by_key(signal_id)
                assert isinstance(governance, GovernanceMetadata)
            except Exception as exc:
                failures.append(f"{module_name}.{weight_name}: {signal_id}: {type(exc).__name__}: {exc}")

    assert not failures, "Weight registry signal_id values that failed to resolve:\n" + "\n".join(failures)


def test_weight_registry_entries_have_signal_id_or_structured_derivation():
    """Every decision weight has either a governed finding id or explicit derivation metadata."""
    registry = _load_weight_registry()
    failures = []

    for module_name, module in registry.get("modules", {}).items():
        for weight_name, entry in module.get("weights", {}).items():
            if entry.get("signal_id") is not None:
                continue
            derived_from = entry.get("derived_from")
            if not isinstance(derived_from, dict):
                failures.append(f"{module_name}.{weight_name}: missing structured derived_from")
                continue
            features = derived_from.get("features")
            findings = derived_from.get("findings")
            if not isinstance(features, list) or not isinstance(findings, list):
                failures.append(f"{module_name}.{weight_name}: derived_from must contain features and findings lists")
            elif not features and not findings:
                failures.append(f"{module_name}.{weight_name}: derived_from cannot be empty")

    assert not failures, "Weight entries without deterministic derivation metadata:\n" + "\n".join(failures)


def test_weight_registry_derived_findings_resolve_when_present():
    """Every derived_from.findings key resolves through governance metadata."""
    registry = _load_weight_registry()
    failures = []

    for module_name, module in registry.get("modules", {}).items():
        for weight_name, entry in module.get("weights", {}).items():
            derived_from = entry.get("derived_from")
            if not isinstance(derived_from, dict):
                continue
            for finding_key in derived_from.get("findings", []):
                try:
                    governance = get_signal_governance_by_key(finding_key)
                    assert isinstance(governance, GovernanceMetadata)
                except Exception as exc:
                    failures.append(f"{module_name}.{weight_name}: {finding_key}: {type(exc).__name__}: {exc}")

    assert not failures, "Weight registry derived findings that failed to resolve:\n" + "\n".join(failures)


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
