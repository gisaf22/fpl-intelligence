"""Governance layer: promotion and exclusion decisions, lifecycle state, and registry loading."""

from domain.registry.lifecycle import (
    LeakageViolationError,
    LifecycleViolationError,
    assert_operational_safe,
)
from domain.registry.validation import RegistryValidationError, validate_registry_contract
from signals.governance.registry_loader import load_registry

__all__ = [
    "LeakageViolationError",
    "LifecycleViolationError",
    "RegistryValidationError",
    "assert_operational_safe",
    "load_registry",
    "validate_registry_contract",
]
