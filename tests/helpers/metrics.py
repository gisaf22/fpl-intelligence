"""Reusable evaluation metrics for operational usefulness assessment.

All metrics are operationally interpretable: a football manager should
understand what each metric means without statistical background.

Design philosophy:
- Deterministic: same inputs always produce same outputs
- Transparent: no black-box statistical machinery
- Bounded: most metrics have natural [0, 1] or absolute-points interpretation
- None-safe: functions return None when data is insufficient
"""

from __future__ import annotations

from collections.abc import Collection

import pandas as pd


def mean_return(
    player_ids: Collection[int],
    outcomes: pd.DataFrame,
    points_col: str = "total_points",
) -> float | None:
    """Mean actual points of the given players in outcomes.

    Returns None if no matching players found.
    """
    subset = outcomes[outcomes["player_id"].isin(player_ids)]
    if subset.empty or subset[points_col].isna().all():
        return None
    return float(subset[points_col].mean())


def top1_return(
    player_id: int,
    outcomes: pd.DataFrame,
    points_col: str = "total_points",
) -> float | None:
    """Actual points of a single player in outcomes.

    Returns None if the player is not in outcomes.
    """
    row = outcomes[outcomes["player_id"] == player_id]
    if row.empty:
        return None
    val = row[points_col].iloc[0]
    return None if pd.isna(val) else float(val)


def hit_rate(ranked_ids: Collection[int], actual_best_id: int) -> int:
    """1 if actual_best_id is in ranked_ids, else 0.

    Measures whether the evaluation population contains the optimal pick.
    """
    return int(actual_best_id in set(ranked_ids))


def regret(actual_best_points: float, picked_points: float | None) -> float | None:
    """Opportunity cost: actual_best_points minus picked_points.

    0 means the optimal pick was made. Higher regret = worse decision quality.
    Returns None when picked_points is unavailable.

    FPL context: a captain regret of 6 means the captained player scored 6
    fewer points than the highest-scoring eligible player that GW.
    """
    if picked_points is None:
        return None
    return float(actual_best_points - picked_points)


def rank_correlation(
    predicted_values: pd.Series,
    actual_returns: pd.Series,
) -> float | None:
    """Spearman rank correlation between predicted values and actual returns.

    Both series must share the same index (player_id). Returns None if fewer
    than 2 overlapping observations.

    Interpretation: positive = higher-ranked players tended to score more.
    A value above 0.1 suggests mild directional usefulness; above 0.3 is
    operationally meaningful for FPL decision support.
    """
    common = predicted_values.index.intersection(actual_returns.index)
    if len(common) < 2:
        return None
    pred = predicted_values.loc[common].dropna()
    actual = actual_returns.loc[common].dropna()
    common2 = pred.index.intersection(actual.index)
    if len(common2) < 2:
        return None
    pred, actual = pred.loc[common2], actual.loc[common2]

    n = len(pred)
    pred_ranks = pred.rank()
    actual_ranks = actual.rank()
    d_sq = float(((pred_ranks - actual_ranks) ** 2).sum())
    denominator = n * (n ** 2 - 1)
    if denominator == 0:
        return None
    return float(1.0 - (6.0 * d_sq) / denominator)


def return_variance(returns: pd.Series) -> float | None:
    """Standard deviation of returns.

    Measures consistency: a low-variance strategy produces predictable outcomes.
    Returns None if fewer than 2 observations.
    """
    clean = returns.dropna()
    if len(clean) < 2:
        return None
    return float(clean.std())


def downside_rate(returns: pd.Series, threshold: float = 4.0) -> float | None:
    """Fraction of returns below threshold (catastrophic miss rate).

    FPL context: a captain returning < 4 points is typically a damaging
    outcome. Downside rate answers: how often does this strategy produce
    such outcomes?

    Returns None if returns is empty.
    """
    clean = returns.dropna()
    if clean.empty:
        return None
    return float((clean < threshold).mean())
