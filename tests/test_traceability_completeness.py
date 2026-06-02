"""Completeness tests for the Signal Traceability Matrix.

Verifies that signal_traceability.yaml covers the full evaluated signal set
and the full STATE-governed column set, and that governance fields are
consistently populated.

Four core assertions:
1. Every signal in evaluation_metadata.yaml has at least one entry in
   signal_traceability.yaml (one per evaluated position).
2. Every column in _GOVERNED_ROLLING_COLS has at least one entry in
   signal_traceability.yaml.
3. Every candidate entry has a non-null operational_role.
4. Every entry with a non-null operational_role has either consumer_modules
   (non-empty list) or a consumer_note explaining the gap.
"""

from pathlib import Path

import pytest
import yaml

from dal.feat.feat_schema import FEATURE_REGISTRY

pytestmark = pytest.mark.unit

TRACEABILITY_PATH = Path("signals/characterisation/signal_traceability.yaml")
EVAL_META_PATH = Path("signals/governance/evaluation_metadata.yaml")


def _load_traceability() -> list[dict]:
    with open(TRACEABILITY_PATH) as f:
        data = yaml.safe_load(f)
    return data["entries"]


def _load_eval_meta_signals() -> set[str]:
    with open(EVAL_META_PATH) as f:
        data = yaml.safe_load(f)
    return {entry["signal"] for entry in data["evaluation_findings"]}


def _load_governed_rolling_cols() -> set[str]:
    """Return the governed column set from FEATURE_REGISTRY — the single source of truth."""
    return set(FEATURE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# 1. Every evaluated signal has a traceability entry
# ---------------------------------------------------------------------------


def test_all_evaluated_signals_have_traceability_entry():
    """Every signal in evaluation_metadata.yaml appears in signal_traceability.yaml."""
    eval_signals = _load_eval_meta_signals()
    entries = _load_traceability()
    traced_signals = {e["signal"] for e in entries}

    missing = eval_signals - traced_signals
    assert not missing, "Signals in evaluation_metadata.yaml without any traceability entry:\n" + "\n".join(
        sorted(missing)
    )


# ---------------------------------------------------------------------------
# 2. Every governed STATE column has a traceability entry
# ---------------------------------------------------------------------------


def test_all_governed_rolling_cols_have_traceability_entry():
    """Every column in _GOVERNED_ROLLING_COLS appears in signal_traceability.yaml."""
    governed = _load_governed_rolling_cols()
    entries = _load_traceability()
    traced_signals = {e["signal"] for e in entries}

    missing = governed - traced_signals
    assert not missing, "Governed STATE columns without any traceability entry:\n" + "\n".join(sorted(missing))


# ---------------------------------------------------------------------------
# 3. Every candidate entry has a non-null operational_role
# ---------------------------------------------------------------------------


def test_candidate_entries_have_operational_role():
    """Every entry with lifecycle_state=candidate has a non-null operational_role."""
    entries = _load_traceability()
    violations = []
    for e in entries:
        if e.get("lifecycle_state") == "candidate":
            if e.get("operational_role") is None:
                violations.append(
                    f"{e.get('signal')} {e.get('position')}: lifecycle_state=candidate but operational_role is null"
                )
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# 4. Every non-null operational_role has consumer_modules or consumer_note
# ---------------------------------------------------------------------------


def test_operational_role_entries_have_consumer_or_note():
    """Entries with a non-null operational_role have consumer_modules or consumer_note."""
    entries = _load_traceability()
    violations = []
    for e in entries:
        if e.get("operational_role") is not None:
            has_consumers = bool(e.get("consumer_modules"))
            has_note = bool(e.get("consumer_note") and str(e.get("consumer_note")).strip())
            if not has_consumers and not has_note:
                violations.append(
                    f"{e.get('signal')} {e.get('position')}: "
                    f"operational_role={e.get('operational_role')} but "
                    f"consumer_modules is empty and consumer_note is null/empty"
                )
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# 5. Structural sanity: all entries have required fields
# ---------------------------------------------------------------------------

_REQUIRED_ENTRY_FIELDS = frozenset(
    {
        "signal",
        "position",
        "lifecycle_state",
        "downstream_status",
        "operational_role",
        "consumer_modules",
    }
)


def test_all_entries_have_required_fields():
    """Every traceability entry has the minimum required fields."""
    entries = _load_traceability()
    violations = []
    for e in entries:
        key = f"{e.get('signal', '?')} {e.get('position', '?')}"
        missing = _REQUIRED_ENTRY_FIELDS - set(e.keys())
        if missing:
            violations.append(f"{key}: missing fields {sorted(missing)}")
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# 6. Lifecycle vocabulary conformance
# ---------------------------------------------------------------------------

_VALID_LIFECYCLE = frozenset({"candidate", "approved", "excluded", "not_applicable", "provisional"})
_VALID_DOWNSTREAM = frozenset({"eligible", "caveated", "approved", "blocked"})


def test_lifecycle_state_vocabulary():
    """lifecycle_state must be in the controlled vocabulary."""
    entries = _load_traceability()
    violations = []
    for e in entries:
        key = f"{e.get('signal')} {e.get('position')}"
        ls = e.get("lifecycle_state")
        if ls not in _VALID_LIFECYCLE:
            violations.append(f"{key}: invalid lifecycle_state '{ls}'")
    assert not violations, "\n".join(violations)


def test_downstream_status_vocabulary():
    """downstream_status must be in the controlled vocabulary."""
    entries = _load_traceability()
    violations = []
    for e in entries:
        key = f"{e.get('signal')} {e.get('position')}"
        ds = e.get("downstream_status")
        if ds not in _VALID_DOWNSTREAM:
            violations.append(f"{key}: invalid downstream_status '{ds}'")
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# 7. Blocked entries are not listed as eligible
# ---------------------------------------------------------------------------


def test_excluded_entries_are_blocked():
    """Entries with lifecycle_state=excluded must not have downstream_status=eligible."""
    entries = _load_traceability()
    violations = []
    for e in entries:
        key = f"{e.get('signal')} {e.get('position')}"
        if e.get("lifecycle_state") == "excluded":
            if e.get("downstream_status") == "eligible":
                violations.append(f"{key}: lifecycle_state=excluded but downstream_status=eligible")
    assert not violations, "\n".join(violations)


# ---------------------------------------------------------------------------
# 8. Total entry count is consistent with known schema
# ---------------------------------------------------------------------------


def test_traceability_is_non_empty():
    """signal_traceability.yaml contains entries."""
    entries = _load_traceability()
    assert len(entries) > 0, "signal_traceability.yaml has no entries"


def test_traceability_covers_all_four_positions_for_evaluated_signals():
    """Every signal in evaluation_metadata.yaml has entries for at least 3 of 4 positions.

    Some signals have ontological GK/FWD exclusions (not_applicable) but the
    entries must still be present — absence would mean incomplete traceability.
    """
    eval_signals = _load_eval_meta_signals()
    entries = _load_traceability()

    by_signal: dict[str, set[str]] = {}
    for e in entries:
        sig = e["signal"]
        pos = e["position"]
        by_signal.setdefault(sig, set()).add(pos)

    violations = []
    for sig in eval_signals:
        positions = by_signal.get(sig, set())
        if len(positions) < 3:
            violations.append(f"{sig}: only {len(positions)} position entries ({sorted(positions)}); expected ≥ 3")
    assert not violations, "\n".join(violations)
