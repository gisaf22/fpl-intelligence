"""Guardrail on governed feature metadata in the analytical object spine.

The traceability-routing checks that once lived here were retired with
``model/governance/signal_traceability.yaml``; what remains is the FEATURE_REGISTRY
invariant, which does not depend on that file.
"""

import pytest

from dal.feat.feat_schema import FEATURE_REGISTRY

pytestmark = pytest.mark.unit


def test_feature_registry_gate_values_are_non_empty():
    """Every governed feature record keeps a non-empty gate reference."""
    violations = [feature for feature, record in FEATURE_REGISTRY.items() if not record.gate]
    assert not violations, "FEATURE_REGISTRY entries with empty gate:\n" + "\n".join(sorted(violations))
