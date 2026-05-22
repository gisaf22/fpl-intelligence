"""Tests for scorer.signals — signal selection and manifest construction."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from signals.lifecycle.loader import load_registry
from intelligence.scoring.signals import load_manifest, load_manifest_from_path

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
    confirmed_signals = {(s.signal, s.position) for s in manifest.confirmed}
    caveated_signals = {(s.signal, s.position) for s in manifest.caveated}

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


def test_confirmed_signals_meet_rho_threshold(manifest):
    """Every confirmed signal has abs(rho_pooled) >= MIN_RHO."""
    from intelligence.scoring.signals import MIN_RHO

    for sig in manifest.confirmed:
        assert sig.rho_pooled == sig.rho_pooled, (  # NaN check
            f"{sig.signal}/{sig.position} has rho_pooled=NaN"
        )
        assert abs(sig.rho_pooled) >= MIN_RHO, (
            f"{sig.signal}/{sig.position} has |rho|={abs(sig.rho_pooled):.3f} "
            f"below threshold {MIN_RHO}"
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
