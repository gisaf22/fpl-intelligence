"""ADR-010 ruling (d) — leakage classification owned by the domain ontology.

Domain owns *which* layer_role values constitute target leakage / outcome-component
(``domain.signal_layers.{LEAKAGE_LAYER_ROLES, OUTCOME_COMPONENT_LAYER_ROLES}``). Serve
enforces them at scoring time but does not re-list them — its enforcement sets must BE
the domain sets (a derived, explicit cross-layer mapping, not an independent copy).

This catches the drift mode where serve quietly maintains its own divergent notion of
which roles leak.
"""

from __future__ import annotations

import pytest

from domain.signal_layers import LEAKAGE_LAYER_ROLES, OUTCOME_COMPONENT_LAYER_ROLES
from serve.scoring import signal_selector

pytestmark = pytest.mark.unit


def test_serve_leakage_roles_reference_the_domain_classification() -> None:
    """Serve's leakage enforcement set is the domain-owned classification, not a copy."""
    assert signal_selector._LEAKAGE_ROLES is LEAKAGE_LAYER_ROLES, (
        "serve/scoring/signal_selector._LEAKAGE_ROLES must reference "
        "domain.signal_layers.LEAKAGE_LAYER_ROLES (ADR-010 ruling d), not re-list role strings."
    )


def test_serve_outcome_component_roles_reference_the_domain_classification() -> None:
    """Serve's outcome-component enforcement set is the domain-owned classification."""
    assert signal_selector._OUTCOME_COMPONENT_ROLES is OUTCOME_COMPONENT_LAYER_ROLES, (
        "serve/scoring/signal_selector._OUTCOME_COMPONENT_ROLES must reference "
        "domain.signal_layers.OUTCOME_COMPONENT_LAYER_ROLES (ADR-010 ruling d)."
    )
