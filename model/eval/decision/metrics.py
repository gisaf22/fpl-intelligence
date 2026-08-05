"""Decision-outcome metrics (promoted from tests/helpers; ADR-012 §5).

Operationally interpretable, deterministic, None-safe. These grade a *decision's outcome* (did the pick
return well) — distinct from ``model/eval``'s forecast-ranking metrics (spearman, precision@k), which
grade the forecast.
"""

from __future__ import annotations

from collections.abc import Collection

import pandas as pd


def hit_rate(ranked_ids: Collection[int], actual_best_id: int) -> int:
    """1 if the actual best scorer is among ``ranked_ids``, else 0."""
    return int(actual_best_id in set(ranked_ids))


def regret(actual_best_points: float, picked_points: float | None) -> float | None:
    """Opportunity cost: best minus picked. 0 = optimal pick; None if the pick has no outcome."""
    if picked_points is None:
        return None
    return float(actual_best_points - picked_points)


def return_variance(returns: pd.Series) -> float | None:
    """Std dev of returns (consistency). None if fewer than 2 observations."""
    clean = returns.dropna()
    if len(clean) < 2:
        return None
    return float(clean.std())
