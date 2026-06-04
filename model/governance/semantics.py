"""Semantic enrichment — model-governance concern (exited research).

Signal-layer vocabulary is sourced from ``domain.signal_layers`` (the shared,
below-research canonical home), so this module carries no upward dependency.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from domain.signal_layers import SIGNAL_LAYER_MAPPING, SIGNAL_LAYER_VALUES

__all__ = [
    "SIGNAL_LAYER_MAPPING",
    "SIGNAL_LAYER_VALUES",
    "assign_downstream_status",
    "enrich_signal_layers",
]


def _has_value(value: Any) -> bool:
    """Return True when a registry scalar is present after CSV/NaN coercions."""
    if value is None:
        return False
    if pd.isna(value):
        return False
    return str(value).strip() != ""


def assign_downstream_status(row: dict[str, Any]) -> str:
    """Assign row-level downstream governance status."""
    support_flags = str(row.get("support_flags", ""))
    support_type = row.get("support_type", "")
    geom = row.get("relationship_geometry", "")

    if (
        "insufficient_support" in support_flags
        or support_type in {"insufficient_n", "near_constant_position"}
        or geom == "unassessable"
    ):
        return "blocked"

    caveated_layers = {"context", "market_behavior", "valuation"}
    if (
        row.get("low_confidence", False) == True  # noqa: E712
        or geom == "indeterminate"
        or row.get("panel_class", "") == "indeterminate"
        or _has_value(support_type)
        or row.get("signal_layer") in caveated_layers
    ):
        return "caveated"

    if row.get("feature_candidate_eligible", False) == True:  # noqa: E712
        return "eligible"

    return "caveated"


def enrich_signal_layers(registry: pd.DataFrame) -> pd.DataFrame:
    """Merge semantic signal-layer metadata and downstream status into registry."""
    missing = sorted(set(registry["signal"]) - set(SIGNAL_LAYER_MAPPING))
    if missing:
        raise ValueError(
            "Signal-layer mapping missing entries for signals: "
            + ", ".join(missing)
        )

    layer_df = pd.DataFrame.from_dict(SIGNAL_LAYER_MAPPING, orient="index")
    layer_df.index.name = "signal"
    layer_df = layer_df.reset_index()

    semantic_cols = [
        "signal_layer",
        "layer_role",
        "feature_candidate_eligible",
        "interpretation_caveat",
        "downstream_status",
    ]
    enriched = registry.drop(
        columns=[column for column in semantic_cols if column in registry.columns]
    ).merge(layer_df, on="signal", how="left")
    enriched["feature_candidate_eligible"] = (
        enriched["feature_candidate_eligible"].astype(bool)
    )
    enriched["downstream_status"] = [
        assign_downstream_status(row)
        for row in enriched.to_dict(orient="records")
    ]
    return enriched
