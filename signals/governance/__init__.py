"""Governance layer: promotion and exclusion decisions, lifecycle state, and registry loading."""

from signals.governance.lifecycle import (
    LeakageViolationError,
    LifecycleViolationError,
    assert_operational_safe,
)
from signals.governance.registry_loader import load_registry
from signals.governance.signal_layer_classifier import (
    SIGNAL_LAYER_MAPPING,
    SIGNAL_LAYER_VALUES,
    assign_downstream_status,
    enrich_signal_layers,
)
from signals.governance.validation import RegistryValidationError, validate_registry_contract

__all__ = [
    "LeakageViolationError",
    "LifecycleViolationError",
    "RegistryValidationError",
    "SIGNAL_LAYER_MAPPING",
    "SIGNAL_LAYER_VALUES",
    "assert_operational_safe",
    "assign_downstream_status",
    "enrich_signal_layers",
    "load_registry",
    "validate_registry_contract",
]
