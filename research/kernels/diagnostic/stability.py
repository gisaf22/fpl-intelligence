"""Distribution and relationship stability classification — Rung Dg (Diagnostic).

Vocabulary:
  homogeneity: stable | moderate_shift | unstable
  pooling:     pool_confirmed | pool_with_caveat | restrict_to_midseason

Heuristic: normalized median shift between blocks.
  normalized_shift = |median_b1 - median_b2| / (pooled_iqr + EPSILON)
  stable:         normalized_shift < STABLE_THRESHOLD
  moderate_shift: STABLE_THRESHOLD <= normalized_shift < UNSTABLE_THRESHOLD
  unstable:       normalized_shift >= UNSTABLE_THRESHOLD

Thresholds are operational heuristics. Treat classifications as analytical
guidance, not statistical claims.

Block distribution computation lives in research.kernels.descriptive.block_distributions.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

BLOCK_HOMOGENEITY_VALUES: frozenset[str] = frozenset({"stable", "moderate_shift", "unstable"})

POOLING_DECISION_VALUES: frozenset[str] = frozenset({"pool_confirmed", "pool_with_caveat", "restrict_to_midseason"})

STABLE_THRESHOLD: float = 0.5
UNSTABLE_THRESHOLD: float = 1.5
EPSILON: float = 1e-6

_HOMOGENEITY_TO_POOLING: dict[str, str] = {
    "stable": "pool_confirmed",
    "moderate_shift": "pool_with_caveat",
    "unstable": "restrict_to_midseason",
}


def assess_distribution_stability(block_stats: pd.DataFrame) -> str:
    """Assess whether a signal's distribution is stable across GW blocks.

    Args:
        block_stats: Output of compute_signal_block_distributions for a single
                     (signal, position). Must have columns: block, median, iqr.

    Returns:
        One of {stable, moderate_shift, unstable}.
    """
    required = {"block", "median", "iqr"}
    missing = required - set(block_stats.columns)
    if missing:
        raise ValueError(f"block_stats missing required columns: {sorted(missing)}")

    valid = block_stats.dropna(subset=["median", "iqr"])

    if len(valid) < 2:
        if len(valid) == 0:
            return "stable"
        return "unstable"

    medians = valid["median"].to_numpy(dtype=float)
    iqrs = valid["iqr"].to_numpy(dtype=float)

    max_shift = 0.0
    for i, j in combinations(range(len(medians)), 2):
        pooled_iqr = (iqrs[i] + iqrs[j]) / 2.0
        normalized_shift = abs(medians[i] - medians[j]) / (pooled_iqr + EPSILON)
        if normalized_shift > max_shift:
            max_shift = normalized_shift

    if max_shift < STABLE_THRESHOLD:
        return "stable"
    if max_shift < UNSTABLE_THRESHOLD:
        return "moderate_shift"
    return "unstable"


def resolve_pooling_strategy(stability_verdict: str) -> str:
    """Map a distribution stability verdict to a season-pooling decision."""
    if stability_verdict not in BLOCK_HOMOGENEITY_VALUES:
        raise ValueError(
            f"unrecognized stability verdict {stability_verdict!r}; expected one of {sorted(BLOCK_HOMOGENEITY_VALUES)}"
        )
    return _HOMOGENEITY_TO_POOLING[stability_verdict]


def stability_classify(
    pooled_gap: float,
    block_gaps: dict[str, float | None],
) -> str:
    """Classify temporal stability of a signal's bin gap across GW blocks.

    Different from assess_distribution_stability which classifies signal
    distribution shift — this classifies relationship strength consistency.

    Returns one of: stable | moderate_shift | unstable | insufficient_data
    """
    valid_gaps = [v for v in block_gaps.values() if v is not None and not np.isnan(v)]

    if len(valid_gaps) < 2 or np.isnan(pooled_gap):
        return "insufficient_data"

    all_pos = all(gap > 0 for gap in valid_gaps)
    all_neg = all(gap < 0 for gap in valid_gaps)
    if not (all_pos or all_neg):
        return "unstable"

    abs_gaps = [abs(gap) for gap in valid_gaps]
    min_gap, max_gap = min(abs_gaps), max(abs_gaps)
    gap_ratio = min_gap / max_gap if max_gap > 0 else 1.0

    if gap_ratio < 0.50:
        return "moderate_shift"
    return "stable"
