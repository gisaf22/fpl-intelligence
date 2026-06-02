"""Validation tests for signals/governance/evaluation_metadata.yaml.

Verifies schema completeness and vocabulary conformance for the structured
evaluation findings. Does not test rho values — those are sourced from lens
study run artifacts and tracked in SIGNAL_REGISTRY.md.

Phase 4 additions (Governance Consolidation):
- Every entry has behavioral_reason, source_gate_decisions, leakage_risk populated
- Every candidate entry has rho_pooled not null
- Every candidate entry has a matching entry in synth01_candidates.yaml
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

EVAL_META_PATH = Path("signals/governance/evaluation_metadata.yaml")

_REQUIRED_POSITION_KEYS = frozenset(
    {"rho_pooled", "rho_ci_lower", "rho_ci_upper", "block_stability_count", "decision_class", "lifecycle_state"}
)
_VALID_DECISION_CLASS = frozenset({"informative", "uninformative", "conditional", "excluded"})
_VALID_LIFECYCLE_STATE = frozenset({"candidate", "excluded", "not_applicable", "approved"})


def _load() -> dict:
    with open(EVAL_META_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


def test_evaluation_metadata_loads():
    """YAML parses without error and is non-empty."""
    data = _load()
    assert data is not None
    assert "evaluation_findings" in data


def test_required_top_level_sections():
    """YAML has the three required top-level sections."""
    data = _load()
    assert "evaluation_findings" in data
    assert "decision_class_vocab" in data
    assert "lifecycle_state_vocab" in data


def test_evaluation_findings_is_non_empty_list():
    """evaluation_findings is a non-empty list."""
    data = _load()
    findings = data["evaluation_findings"]
    assert isinstance(findings, list)
    assert len(findings) > 0


def test_each_entry_has_signal_and_lens():
    """Every entry has signal_id, signal, lens, target, and per_position fields."""
    data = _load()
    required_entry_keys = {"signal_id", "signal", "lens", "target", "per_position"}
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        missing = required_entry_keys - set(entry.keys())
        assert not missing, f"{signal_id}: missing entry keys {sorted(missing)}"


# ---------------------------------------------------------------------------
# Per-position field completeness
# ---------------------------------------------------------------------------


def test_all_positions_have_required_keys():
    """Every signal-position entry carries all six required governance fields."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            missing = _REQUIRED_POSITION_KEYS - set(pos_data.keys())
            if missing:
                violations.append(f"{signal_id} {pos}: missing {sorted(missing)}")
    assert not violations, "Missing position-level keys:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Vocabulary conformance
# ---------------------------------------------------------------------------


def test_decision_class_values_are_valid():
    """decision_class must be in the controlled vocabulary."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            dc = pos_data.get("decision_class")
            if dc not in _VALID_DECISION_CLASS:
                violations.append(f"{signal_id} {pos}: invalid decision_class '{dc}'")
    assert not violations, "\n".join(violations)


def test_lifecycle_state_values_are_valid():
    """lifecycle_state must be in the controlled vocabulary."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            ls = pos_data.get("lifecycle_state")
            if ls not in _VALID_LIFECYCLE_STATE:
                violations.append(f"{signal_id} {pos}: invalid lifecycle_state '{ls}'")
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# Internal consistency
# ---------------------------------------------------------------------------


def test_informative_entries_have_ci():
    """Entries with decision_class=informative must have rho_ci_lower and rho_ci_upper."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            if pos_data.get("decision_class") == "informative":
                if pos_data.get("rho_ci_lower") is None:
                    violations.append(f"{signal_id} {pos}: informative but rho_ci_lower is null")
                if pos_data.get("rho_ci_upper") is None:
                    violations.append(f"{signal_id} {pos}: informative but rho_ci_upper is null")
    assert not violations, "\n".join(violations)


def test_informative_entries_have_block_stability():
    """Entries with decision_class=informative must have block_stability_count."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            if pos_data.get("decision_class") == "informative":
                if pos_data.get("block_stability_count") is None:
                    violations.append(f"{signal_id} {pos}: informative but block_stability_count is null")
    assert not violations, "\n".join(violations)


def test_candidate_entries_are_informative_or_conditional():
    """lifecycle_state=candidate must have decision_class in (informative, conditional)."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            if pos_data.get("lifecycle_state") == "candidate":
                dc = pos_data.get("decision_class")
                if dc not in {"informative", "conditional"}:
                    violations.append(f"{signal_id} {pos}: lifecycle_state=candidate but decision_class='{dc}'")
    assert not violations, "\n".join(violations)


def test_excluded_design_entries_not_candidate():
    """decision_class=excluded must not have lifecycle_state=candidate."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            if pos_data.get("decision_class") == "excluded":
                if pos_data.get("lifecycle_state") == "candidate":
                    violations.append(f"{signal_id} {pos}: decision_class=excluded but lifecycle_state=candidate")
    assert not violations, "\n".join(violations)


def test_ci_lower_less_than_ci_upper():
    """Where both CI bounds are present, lower must be strictly less than upper."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            lo = pos_data.get("rho_ci_lower")
            hi = pos_data.get("rho_ci_upper")
            if lo is not None and hi is not None:
                if lo >= hi:
                    violations.append(f"{signal_id} {pos}: rho_ci_lower={lo} >= rho_ci_upper={hi}")
    assert not violations, "\n".join(violations)


def test_block_stability_count_in_range():
    """block_stability_count, where present, must be in [0, block_stability_total]."""
    data = _load()
    total = data.get("block_stability_total", 3)
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            count = pos_data.get("block_stability_count")
            if count is not None:
                if not (0 <= count <= total):
                    violations.append(f"{signal_id} {pos}: block_stability_count={count} out of [0, {total}]")
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# Phase 4 — Governance Consolidation
# ---------------------------------------------------------------------------

_SYNTH01_CANDIDATES_PATH = Path("signals/characterisation/synth01_candidates.yaml")


def _load_synth01() -> list[dict]:
    with open(_SYNTH01_CANDIDATES_PATH) as f:
        data = yaml.safe_load(f)
    return data["candidates"]


def test_all_positions_have_behavioral_reason():
    """Every signal-position entry has a non-empty behavioral_reason (Phase 4)."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            br = pos_data.get("behavioral_reason")
            if not br or not str(br).strip():
                violations.append(f"{signal_id} {pos}: behavioral_reason is null or empty")
    assert not violations, "\n".join(violations)


def test_all_positions_have_source_gate_decisions():
    """Every signal-position entry has a non-empty source_gate_decisions list (Phase 4)."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            decisions = pos_data.get("source_gate_decisions")
            if not decisions or not isinstance(decisions, list) or len(decisions) == 0:
                violations.append(f"{signal_id} {pos}: source_gate_decisions is null, empty, or not a list")
    assert not violations, "\n".join(violations)


def test_all_positions_have_leakage_risk():
    """Every signal-position entry has leakage_risk in the controlled vocabulary (Phase 4)."""
    _VALID_LEAKAGE_RISK = frozenset({"none", "evaluation_circularity", "direct"})
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            lr = pos_data.get("leakage_risk")
            if not lr or lr not in _VALID_LEAKAGE_RISK:
                violations.append(f"{signal_id} {pos}: leakage_risk={lr!r} — null or not in vocabulary")
    assert not violations, "\n".join(violations)


def test_candidate_entries_have_rho_pooled_not_null():
    """Every entry with lifecycle_state=candidate must have rho_pooled not null (Phase 4)."""
    data = _load()
    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            if pos_data.get("lifecycle_state") == "candidate":
                if pos_data.get("rho_pooled") is None:
                    violations.append(f"{signal_id} {pos}: lifecycle_state=candidate but rho_pooled is null")
    assert not violations, "\n".join(violations)


def test_candidate_entries_have_matching_synth01_entry():
    """Every lifecycle_state=candidate entry has a matching record in synth01_candidates.yaml (Phase 4)."""
    data = _load()
    synth_candidates = _load_synth01()
    synth_set = {(c["signal"], c["position"]) for c in synth_candidates}

    violations = []
    for entry in data["evaluation_findings"]:
        signal_id = entry.get("signal_id", "?")
        signal = entry.get("signal", "?")
        for pos, pos_data in entry.get("per_position", {}).items():
            if pos_data.get("lifecycle_state") == "candidate":
                key = (signal, pos)
                if key not in synth_set:
                    violations.append(
                        f"{signal_id}: ({signal}, {pos}) is lifecycle_state=candidate "
                        f"but has no matching entry in synth01_candidates.yaml"
                    )
    assert not violations, "\n".join(violations)
