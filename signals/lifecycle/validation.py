"""Validation for governed EDA signal registries."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from signals.lifecycle.schema import (
    BOOLEAN_COLUMNS,
    CONTROLLED_VALUE_COLUMNS,
    MATCH_LEVEL_SIGNALS,
    NULLABLE_CONTROLLED_COLUMNS,
    NON_EMPTY_COLUMNS,
    NON_FEATURE_SIGNAL_LAYERS,
    PRIMARY_KEY_COLUMNS,
    REQUIRED_COLUMNS,
)


@dataclass
class RegistryValidationError(ValueError):
    """Raised when a registry violates the downstream contract."""

    errors: list[str]

    def __str__(self) -> str:
        lines = ["Registry contract validation failed:"]
        lines.extend(f"  - {error}" for error in self.errors)
        return "\n".join(lines)


def _present(series: pd.Series) -> pd.Series:
    """Return mask for non-null, non-empty scalar values."""
    return series.notna() & (series.astype(str).str.strip() != "")


def _validate_required_columns(registry: pd.DataFrame, errors: list[str]) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in registry.columns]
    if missing:
        errors.append(f"missing required columns: {missing}")

    duplicate_count = int(registry.columns.duplicated().sum())
    if duplicate_count:
        errors.append(f"duplicate column names: {duplicate_count}")


def _validate_primary_key(registry: pd.DataFrame, errors: list[str]) -> None:
    if not set(PRIMARY_KEY_COLUMNS).issubset(registry.columns):
        return

    duplicates = registry[list(PRIMARY_KEY_COLUMNS)].duplicated().sum()
    if duplicates:
        errors.append(
            f"{int(duplicates)} duplicate primary keys on {PRIMARY_KEY_COLUMNS}"
        )


def _validate_non_empty(registry: pd.DataFrame, errors: list[str]) -> None:
    for column in NON_EMPTY_COLUMNS:
        if column not in registry.columns:
            continue
        missing = (~_present(registry[column])).sum()
        if missing:
            errors.append(f"{int(missing)} rows have empty {column}")


def _validate_controlled_values(registry: pd.DataFrame, errors: list[str]) -> None:
    for column, allowed_values in CONTROLLED_VALUE_COLUMNS.items():
        if column not in registry.columns:
            continue

        values = registry[column]
        if column in NULLABLE_CONTROLLED_COLUMNS:
            mask = values.notna() & (values.astype(str).str.strip() != "")
        else:
            mask = values.notna()

        bad = sorted(set(values[mask].astype(str)) - set(allowed_values))
        if bad:
            errors.append(f"{column} contains unknown values: {bad}")


def _validate_booleans(registry: pd.DataFrame, errors: list[str]) -> None:
    for column in BOOLEAN_COLUMNS:
        if column not in registry.columns:
            continue

        bad_mask = registry[column].map(type).ne(bool)
        if bad_mask.any():
            errors.append(f"{int(bad_mask.sum())} rows have non-bool {column}")


def _validate_layer_status_consistency(
    registry: pd.DataFrame,
    errors: list[str],
) -> None:
    required = {
        "signal",
        "variable_level",
        "signal_layer",
        "feature_candidate_eligible",
        "support_flags",
        "low_confidence",
        "downstream_status",
    }
    if not required.issubset(registry.columns):
        return

    bad_match_level = registry[
        registry["signal"].isin(MATCH_LEVEL_SIGNALS)
        & (registry["variable_level"] != "match_level")
    ]
    if not bad_match_level.empty:
        errors.append(
            f"{len(bad_match_level)} match-level signal rows are not variable_level=match_level"
        )

    bad_feature_layers = registry[
        registry["signal_layer"].isin(NON_FEATURE_SIGNAL_LAYERS)
        & (registry["feature_candidate_eligible"] == True)  # noqa: E712
    ]
    if not bad_feature_layers.empty:
        errors.append(
            f"{len(bad_feature_layers)} non-feature-layer rows are feature_candidate_eligible=True"
        )

    insuff_not_blocked = registry[
        registry["support_flags"]
        .astype(str)
        .str.contains("insufficient_support", na=False)
        & (registry["downstream_status"] != "blocked")
    ]
    if not insuff_not_blocked.empty:
        errors.append(
            f"{len(insuff_not_blocked)} insufficient_support rows are not blocked"
        )

    low_conf_eligible = registry[
        (registry["low_confidence"] == True)  # noqa: E712
        & (registry["downstream_status"] == "eligible")
    ]
    if not low_conf_eligible.empty:
        errors.append(
            f"{len(low_conf_eligible)} low-confidence rows are marked eligible"
        )


def _validate_promotion_coherence(
    registry: pd.DataFrame,
    errors: list[str],
) -> None:
    if "promotion_class" not in registry.columns or "downstream_status" not in registry.columns:
        return

    blocked = registry["downstream_status"] == "blocked"
    non_blocked = ~blocked

    # Blocked rows must have null promotion_class.
    blocked_with_class = registry[blocked & registry["promotion_class"].notna()]
    if not blocked_with_class.empty:
        errors.append(
            f"{len(blocked_with_class)} blocked rows have a non-null promotion_class"
        )

    # Non-blocked rows must have a non-null promotion_class.
    non_blocked_without_class = registry[non_blocked & registry["promotion_class"].isna()]
    if not non_blocked_without_class.empty:
        errors.append(
            f"{len(non_blocked_without_class)} non-blocked rows have null promotion_class"
        )


def validate_registry_contract(registry: pd.DataFrame) -> None:
    """Validate the registry contract used by weekly analytics code.

    Raises:
        RegistryValidationError: when any contract check fails.
    """
    errors: list[str] = []

    _validate_required_columns(registry, errors)
    if errors:
        raise RegistryValidationError(errors)

    _validate_primary_key(registry, errors)
    _validate_non_empty(registry, errors)
    _validate_controlled_values(registry, errors)
    _validate_booleans(registry, errors)
    _validate_layer_status_consistency(registry, errors)
    _validate_promotion_coherence(registry, errors)

    if errors:
        raise RegistryValidationError(errors)
