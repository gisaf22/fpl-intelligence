"""Tests for scorer.signals — signal selection and manifest construction."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from domain.registry.governance_types import GovernanceMetadataError
from domain.registry.lifecycle import LifecycleViolationError
from domain.registry.operational import load_registry
from serve.scoring.signal_selector import load_manifest

pytestmark = pytest.mark.unit

REGISTRY_PATH = Path("research/findings/records/eda_03_joint_registry.csv")

_SCORING_CLASSES = frozenset({"core_signal", "review_signal"})
_LEAKAGE_SIGNALS = {"bonus"}  # points_component layer_role
_OUTCOME_COMPONENT_SIGNALS = {"bps"}  # contribution_index layer_role

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry():
    return load_registry(REGISTRY_PATH)


@pytest.fixture(scope="module")
def manifest(registry):
    return load_manifest(registry)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_manifest_confirmed_only_scoring_classes(manifest):
    """All confirmed signals have promotion_class in (core_signal, review_signal)."""
    for sig in manifest.confirmed:
        assert sig.promotion_class in _SCORING_CLASSES, (
            f"{sig.signal}/{sig.position} in confirmed with class '{sig.promotion_class}'"
        )


def test_manifest_caveated_only_scoring_classes(manifest):
    """All caveated signals also come from scoring promotion classes."""
    for sig in manifest.caveated:
        assert sig.promotion_class in _SCORING_CLASSES, (
            f"{sig.signal}/{sig.position} in caveated with class '{sig.promotion_class}'"
        )


def test_leakage_signals_in_caveated_not_confirmed(manifest):
    """bonus must be in caveated, not confirmed, due to leakage."""
    _confirmed_signals = {(s.signal, s.position) for s in manifest.confirmed}
    _caveated_signals = {(s.signal, s.position) for s in manifest.caveated}

    for leakage_signal in _LEAKAGE_SIGNALS:
        caveated_entries = [s for s in manifest.caveated if s.signal == leakage_signal]
        confirmed_entries = [s for s in manifest.confirmed if s.signal == leakage_signal]
        assert len(caveated_entries) > 0, f"'{leakage_signal}' should appear in caveated (leakage) but is absent"
        assert len(confirmed_entries) == 0, f"'{leakage_signal}' should not appear in confirmed but does"


def test_outcome_component_signals_in_caveated_not_confirmed(manifest):
    """bps must be in caveated, not confirmed, as an outcome-component."""
    for oc_signal in _OUTCOME_COMPONENT_SIGNALS:
        confirmed_entries = [s for s in manifest.confirmed if s.signal == oc_signal]
        caveated_entries = [s for s in manifest.caveated if s.signal == oc_signal]
        assert len(confirmed_entries) == 0, f"'{oc_signal}' should not appear in confirmed but does"
        assert len(caveated_entries) > 0, f"'{oc_signal}' should appear in caveated but is absent"


def test_confirmed_signals_respect_governance_decision(manifest):
    """No confirmed signal is governance-excluded/blocked (registry↔governance drift guard).

    A registry may promote a signal that the decision-of-record has since
    excluded; load_manifest must route such signals to caveated, not confirmed.
    Regression guard for the gw36 purchase_price@{GK,MID} drift.
    """
    from domain.registry.governance_lookup import get_signal_governance

    violations = []
    for sig in manifest.confirmed:
        try:
            gov = get_signal_governance(sig.signal, sig.position)
        except GovernanceMetadataError:
            continue  # ungoverned/allowlist handled by _assert_governance_compliance
        if gov.lifecycle_state == "excluded" or gov.downstream_status == "blocked":
            violations.append(
                f"{sig.signal}/{sig.position}: confirmed but governance "
                f"lifecycle_state={gov.lifecycle_state}, downstream_status={gov.downstream_status}"
            )
    assert not violations, "Governance-excluded signals leaked into confirmed:\n" + "\n".join(violations)


def test_confirmed_signals_have_non_null_rho(manifest):
    """Every confirmed signal has a non-null rho_pooled (CI gate, Phase 8 resolution of G-OPS-02)."""
    for sig in manifest.confirmed:
        assert sig.rho_pooled == sig.rho_pooled, (  # NaN check via self-inequality
            f"{sig.signal}/{sig.position} has rho_pooled=NaN — should be caveated, not confirmed"
        )


def test_confirmed_directions_match_rho_sign(manifest):
    """direction is +1 for positive rho, -1 for negative rho."""
    for sig in manifest.confirmed:
        expected = 1 if sig.rho_pooled > 0 else -1
        assert sig.direction == expected, (
            f"{sig.signal}/{sig.position}: rho={sig.rho_pooled}, direction={sig.direction}, expected {expected}"
        )


def test_positions_covered_matches_confirmed(manifest):
    """positions_covered is derived exclusively from confirmed signals."""
    from collections import defaultdict

    expected: dict[str, list[str]] = defaultdict(list)
    for sig in manifest.confirmed:
        expected[sig.position].append(sig.signal)

    assert set(manifest.positions_covered.keys()) == set(expected.keys()), (
        f"positions_covered keys {set(manifest.positions_covered.keys())} "
        f"don't match confirmed positions {set(expected.keys())}"
    )
    for pos, signals in expected.items():
        assert sorted(manifest.positions_covered[pos]) == sorted(signals), f"positions_covered[{pos}] mismatch"


def test_no_confirmed_signal_has_null_rho(registry, manifest):
    """Cross-check: no registry row that is confirmed has a null rho_pooled."""
    confirmed_keys = {(s.signal, s.position) for s in manifest.confirmed}
    eligible = registry[registry["promotion_class"].isin(_SCORING_CLASSES)]
    for _, row in eligible.iterrows():
        key = (row["signal"], row["position"])
        if key in confirmed_keys:
            assert pd.notna(row["rho_pooled"]), f"Confirmed signal {key} has null rho_pooled in registry"


def test_no_lens_record_with_excluding_foundation_status_raises(registry):
    """A confirmed signal with no lens record whose foundation status derives to excluded
    must hard-fail (ADR-009 §1 replaces the former allowlist with a derived verdict)."""
    from serve.scoring.contracts import ConfirmedSignal, SignalManifest
    from serve.scoring.signal_selector import _assert_governance_compliance

    fake_signal = ConfirmedSignal(
        signal="ungoverned_synthetic_signal",
        position="DEF",
        rho_pooled=0.15,
        direction=1,
        promotion_class="core_signal",
        downstream_status="blocked",  # derives to excluded
    )
    fake_manifest = SignalManifest(
        confirmed=[fake_signal],
        caveated=[],
        positions_covered={"DEF": ["ungoverned_synthetic_signal"]},
    )
    with pytest.raises(LifecycleViolationError):
        _assert_governance_compliance(fake_manifest)


def test_pre_lens_signals_pass_via_derived_foundation_verdict(registry):
    """Pre-lens signals (no evaluation_metadata.yaml record) pass compliance when their
    foundation status derives to candidate (ADR-009 §1, eligible/caveated → candidate)."""
    from serve.scoring.contracts import ConfirmedSignal, SignalManifest
    from serve.scoring.signal_selector import _assert_governance_compliance

    for signal_name in ("goals_scored", "xgi", "clean_sheets"):
        test_signal = ConfirmedSignal(
            signal=signal_name,
            position="DEF",
            rho_pooled=0.10,
            direction=1,
            promotion_class="core_signal",
            downstream_status="caveated",  # derives to candidate
        )
        manifest = SignalManifest(
            confirmed=[test_signal],
            caveated=[],
            positions_covered={"DEF": [signal_name]},
        )
        # Must not raise
        _assert_governance_compliance(manifest)
