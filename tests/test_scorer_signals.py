"""Tests for scorer.signals — signal selection and manifest construction."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from intelligence.scoring.signal_selector import _PRE_LENS_SIGNAL_ALLOWLIST, load_manifest
from signals.governance.registry_loader import load_registry
from signals.governance.schema import GovernanceMetadataError

pytestmark = pytest.mark.unit

REGISTRY_PATH = Path("studies/eda/findings/eda_03_joint_registry.csv")

_SCORING_CLASSES = frozenset({"core_signal", "review_signal"})
_LEAKAGE_SIGNALS = {"bonus"}          # points_component layer_role
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
        caveated_entries = [
            s for s in manifest.caveated if s.signal == leakage_signal
        ]
        confirmed_entries = [
            s for s in manifest.confirmed if s.signal == leakage_signal
        ]
        assert len(caveated_entries) > 0, (
            f"'{leakage_signal}' should appear in caveated (leakage) but is absent"
        )
        assert len(confirmed_entries) == 0, (
            f"'{leakage_signal}' should not appear in confirmed but does"
        )

def test_outcome_component_signals_in_caveated_not_confirmed(manifest):
    """bps must be in caveated, not confirmed, as an outcome-component."""
    for oc_signal in _OUTCOME_COMPONENT_SIGNALS:
        confirmed_entries = [s for s in manifest.confirmed if s.signal == oc_signal]
        caveated_entries = [s for s in manifest.caveated if s.signal == oc_signal]
        assert len(confirmed_entries) == 0, (
            f"'{oc_signal}' should not appear in confirmed but does"
        )
        assert len(caveated_entries) > 0, (
            f"'{oc_signal}' should appear in caveated but is absent"
        )

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
            f"{sig.signal}/{sig.position}: rho={sig.rho_pooled}, "
            f"direction={sig.direction}, expected {expected}"
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
        assert sorted(manifest.positions_covered[pos]) == sorted(signals), (
            f"positions_covered[{pos}] mismatch"
        )

def test_no_confirmed_signal_has_null_rho(registry, manifest):
    """Cross-check: no registry row that is confirmed has a null rho_pooled."""
    confirmed_keys = {(s.signal, s.position) for s in manifest.confirmed}
    eligible = registry[registry["promotion_class"].isin(_SCORING_CLASSES)]
    for _, row in eligible.iterrows():
        key = (row["signal"], row["position"])
        if key in confirmed_keys:
            assert pd.notna(row["rho_pooled"]), (
                f"Confirmed signal {key} has null rho_pooled in registry"
            )

def test_ungoverned_signal_raises_governance_error(registry):
    """Signal absent from both evaluation_metadata.yaml and the allowlist must raise GovernanceMetadataError.

    Injects a synthetic confirmed signal with a made-up name to verify the allowlist
    check fires rather than silently continuing.
    """
    from intelligence.scoring.contracts import ConfirmedSignal, SignalManifest
    from intelligence.scoring.signal_selector import _assert_governance_compliance

    fake_signal = ConfirmedSignal(
        signal="ungoverned_synthetic_signal",
        position="DEF",
        rho_pooled=0.15,
        direction=1,
        promotion_class="core_signal",
    )
    fake_manifest = SignalManifest(
        confirmed=[fake_signal],
        caveated=[],
        positions_covered={"DEF": ["ungoverned_synthetic_signal"]},
    )
    with pytest.raises(GovernanceMetadataError):
        _assert_governance_compliance(fake_manifest)

def test_allowlist_signals_pass_governance_without_evaluation_record(registry):
    """Pre-lens signals on _PRE_LENS_SIGNAL_ALLOWLIST pass governance compliance without an evaluation record."""
    from intelligence.scoring.contracts import ConfirmedSignal, SignalManifest
    from intelligence.scoring.signal_selector import _assert_governance_compliance

    # pick one allowlist signal per position to exercise the bypass
    for signal_name in list(_PRE_LENS_SIGNAL_ALLOWLIST)[:3]:
        test_signal = ConfirmedSignal(
            signal=signal_name,
            position="DEF",
            rho_pooled=0.10,
            direction=1,
            promotion_class="core_signal",
        )
        manifest = SignalManifest(
            confirmed=[test_signal],
            caveated=[],
            positions_covered={"DEF": [signal_name]},
        )
        # Must not raise
        _assert_governance_compliance(manifest)
