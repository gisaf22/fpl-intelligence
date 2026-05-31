"""Promotion class assignment for governed signal registries.

promotion_class is a downstream interpretation layer, not a prediction layer.
It classifies non-blocked registry rows into one of five controlled values
that describe how a signal should be used in weekly analytical outputs.

Vocabulary decision: schema uses {stable, scope_sensitive, untested} for
population_robustness. The EDA_DESIGN.md alternative {robust, moderate_shift,
unstable} was never committed to the schema and is not used here.

Blocked rows (downstream_status == "blocked") are excluded from this domain.
assign_promotion_class raises for blocked rows; enrich_promotion_class
handles them by writing NaN.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from signals.governance.schema import PROMOTION_CLASS_VALUES

_LAYER_TO_CLASS: dict[str, str] = {
    "exposure": "exposure_control",
    "context": "context_control",
    "market_behavior": "market_context",
}

_CORE_SIGNAL_TEMPORAL: frozenset[str] = frozenset({"stable"})
_CORE_SIGNAL_ASSOCIATION: frozenset[str] = frozenset({"continuous_monotonic"})


def enrich_promotion_class(registry: pd.DataFrame) -> pd.DataFrame:
    """Add promotion_class column to a registry DataFrame.

    Non-blocked rows receive a governed promotion_class value.
    Blocked rows receive NaN — they are excluded from the promotion domain.

    Must be called after enrich_signal_layers() so downstream_status is set.
    Does not mutate the input.
    """
    classes: list[Any] = []
    for row in registry.to_dict(orient="records"):
        if row.get("downstream_status") == "blocked":
            classes.append(float("nan"))
        else:
            classes.append(assign_promotion_class(row))
    result = registry.copy()
    result["promotion_class"] = classes
    return result


def assign_promotion_class(row: dict[str, Any]) -> str:
    """Assign a promotion class to a non-blocked registry row.

    Assignment is fully derived from governed registry fields. No analytical
    judgment is applied here — that judgment is encoded in the source fields.

    Raises:
        ValueError: if the row has downstream_status == "blocked". Blocked
            rows are not in the promotion class domain.
    """
    if row.get("downstream_status") == "blocked":
        raise ValueError(
            f"blocked rows are excluded from promotion class domain: "
            f"signal={row.get('signal')!r} position={row.get('position')!r}"
        )

    layer = row.get("signal_layer", "")
    if layer in _LAYER_TO_CLASS:
        return _LAYER_TO_CLASS[layer]

    # Remaining layers: performance, defensive_context, discipline, valuation.
    # core_signal requires eligible status, stable temporal classification,
    # and continuous_monotonic association class. Everything else is review_signal.
    if (
        row.get("downstream_status") == "eligible"
        and row.get("temporal_stability") in _CORE_SIGNAL_TEMPORAL
        and row.get("association_class") in _CORE_SIGNAL_ASSOCIATION
    ):
        return "core_signal"

    return "review_signal"
