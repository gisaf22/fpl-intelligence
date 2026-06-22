"""Tests for domain.fpl_signals — algebraic composite/component registry.

These are definitional FPL identities, not empirical findings; the registry is
relied on to narrow signal sets to one representation per composite family
(e.g. research/foundation/temporal/signal_stability.ipynb).
"""

from __future__ import annotations

import pytest

from domain import fpl_signals as sig

pytestmark = pytest.mark.unit


def test_composite_registry_covers_known_composites():
    assert set(sig.COMPOSITE_SIGNALS) == {"xgi", "ict_index", "defensive_contribution"}


def test_composite_components_match_named_tuples():
    assert sig.COMPOSITE_SIGNALS["xgi"] == sig.XGI_COMPONENTS == ("xg", "xa")
    assert sig.COMPOSITE_SIGNALS["ict_index"] == sig.ICT_COMPONENTS
    assert sig.COMPOSITE_SIGNALS["defensive_contribution"] == sig.DC_COMPONENTS


def test_no_composite_is_its_own_component():
    """A parent must not appear among its own components (would self-cancel)."""
    for parent, components in sig.COMPOSITE_SIGNALS.items():
        assert parent not in components


def test_components_and_parents_are_disjoint():
    """No signal is both a parent and a component of another (no chain ambiguity)."""
    parents = set(sig.COMPOSITE_SIGNALS)
    components = {c for comps in sig.COMPOSITE_SIGNALS.values() for c in comps}
    assert parents.isdisjoint(components)


def test_dc_components_are_the_raw_defensive_actions():
    assert sig.DC_COMPONENTS == (
        "clearances_blocks_interceptions",
        "tackles",
        "recoveries",
    )
