"""Typed loader for governed EDA signal registries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from signals.lifecycle.schema import (
    BOOLEAN_COLUMNS,
    INTEGER_COLUMNS,
    NUMERIC_COLUMNS,
    RESEARCH_REGISTRY_PATH,
)


TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n"}


def _coerce_bool(value: object, column: str) -> bool:
    """Coerce common CSV boolean representations to Python bool."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        raise ValueError(f"{column} contains null boolean value")

    text = str(value).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    raise ValueError(f"{column} contains invalid boolean value: {value!r}")


def load_registry(path: str | Path = RESEARCH_REGISTRY_PATH) -> pd.DataFrame:
    """Load a registry CSV and normalize dtypes for downstream use."""
    registry_path = Path(path)
    registry = pd.read_csv(registry_path, keep_default_na=True)

    for column in BOOLEAN_COLUMNS:
        if column in registry.columns:
            registry[column] = [
                _coerce_bool(value, column) for value in registry[column]
            ]

    for column in INTEGER_COLUMNS:
        if column in registry.columns:
            numeric = pd.to_numeric(registry[column], errors="raise")
            if numeric.isna().any():
                raise ValueError(f"{column} contains null integer value")
            registry[column] = numeric.astype("int64")

    for column in NUMERIC_COLUMNS:
        if column in registry.columns:
            registry[column] = pd.to_numeric(registry[column], errors="raise")

    return registry

