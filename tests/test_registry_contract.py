import pytest

from core.governance import (
    RegistryValidationError,
    load_registry,
    validate_registry_contract,
)


def test_current_registry_loads_and_validates():
    registry = load_registry()

    validate_registry_contract(registry)

    assert len(registry) == 116
    assert registry["feature_candidate_eligible"].map(type).eq(bool).all()
    assert registry["low_confidence"].map(type).eq(bool).all()
    assert registry["tail_sensitive"].map(type).eq(bool).all()


def test_missing_signal_layer_fails_validation():
    registry = load_registry().drop(columns=["signal_layer"])

    with pytest.raises(RegistryValidationError, match="missing required columns"):
        validate_registry_contract(registry)


def test_low_confidence_row_cannot_be_eligible():
    registry = load_registry()
    registry.loc[registry.index[0], "low_confidence"] = True
    registry.loc[registry.index[0], "downstream_status"] = "eligible"

    with pytest.raises(RegistryValidationError, match="low-confidence rows"):
        validate_registry_contract(registry)


def test_insufficient_support_row_must_be_blocked():
    registry = load_registry()
    idx = registry[
        registry["support_flags"].str.contains("insufficient_support", na=False)
    ].index[0]
    registry.loc[idx, "downstream_status"] = "caveated"

    with pytest.raises(RegistryValidationError, match="insufficient_support"):
        validate_registry_contract(registry)

