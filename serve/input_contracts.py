"""Shared utilities for the operational intelligence layer.

All intelligence outputs consume only:
- DAL mart (via dal.pipeline.load().mart)

Research artifacts (research/findings/, exploratory registries) must not enter here.
"""

from __future__ import annotations

import pandas as pd

from dal.mart import GOVERNED_SIGNAL_COLUMNS

# Derived from the mart public API — governed state columns available after pipeline.load().
_REQUIRED_STATE_COLS: frozenset[str] = frozenset(GOVERNED_SIGNAL_COLUMNS)

# Spine columns required by intelligence functions.
_REQUIRED_SPINE_COLS: frozenset[str] = frozenset(
    [
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
    ]
)

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
