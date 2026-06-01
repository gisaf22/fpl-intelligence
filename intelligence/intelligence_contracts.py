"""Shared utilities for the operational intelligence layer.

All intelligence outputs consume only:
- DAL mart (via dal.pipeline.load().mart)

Research artifacts (studies/eda/, exploratory registries) must not enter here.
"""

from __future__ import annotations

import pandas as pd

from dal.feat.feat_schema import FEATURE_REGISTRY

# Derived from FEATURE_REGISTRY — single source of truth for governed state columns.
# Any column added to FEATURE_REGISTRY is automatically required here.
_REQUIRED_STATE_COLS: frozenset[str] = frozenset(FEATURE_REGISTRY.keys())

# Spine columns required by intelligence functions.
_REQUIRED_SPINE_COLS: frozenset[str] = frozenset([
    "player_id",
    "gw",
    "player_name",
    "position_label",
    "position_code",
    "team_id",
    "purchase_price",
    "fdr_avg",
    "is_bgw",
    "goals_scored",
])

REQUIRED_INTELLIGENCE_COLS: frozenset[str] = _REQUIRED_STATE_COLS | _REQUIRED_SPINE_COLS


class IntelligenceInputError(ValueError):
    """Raised when intelligence input contracts are violated."""


def validate_intelligence_inputs(features: pd.DataFrame, caller: str) -> None:
    """Assert required columns are present. Raises IntelligenceInputError if not."""
    missing = REQUIRED_INTELLIGENCE_COLS - set(features.columns)
    if missing:
        raise IntelligenceInputError(
            f"{caller}: missing required columns: {sorted(missing)}. "
            "Intelligence outputs must consume DAL mart from dal.pipeline.load().mart."
        )


def normalize_within_position(
    df: pd.DataFrame,
    col: str,
    fill_value: float = 0.0,
    position_col: str = "position_label",
) -> pd.Series:
    """Min-max normalize col to [0, 1] within each position group.

    NaN values are filled with fill_value before normalization.
    When all values in a group are equal, returns 0.5 (neutral score).
    """
    filled = df[col].fillna(fill_value)

    def _norm(s: pd.Series) -> pd.Series:
        lo, hi = s.min(), s.max()
        if hi == lo:
            return pd.Series(0.5, index=s.index)
        return (s - lo) / (hi - lo)

    result = filled.groupby(df[position_col]).transform(_norm)
    return result.fillna(0.5)


def weighted_composite(
    df: pd.DataFrame,
    component_cols: list[str],
    weights: dict[str, float],
) -> pd.Series:
    """Compute weighted composite score from normalized [0, 1] component columns.

    Weights are normalized to sum to 1.0 internally so callers can use
    intuitive proportions (e.g. 0.35 + 0.30 + 0.20 + 0.15 = 1.0).
    """
    total = sum(weights[c] for c in component_cols)
    composite = sum(df[c] * (weights[c] / total) for c in component_cols)
    return composite
