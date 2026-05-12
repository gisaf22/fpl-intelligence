"""Block-distribution stability utilities for EDA-5.

Classifies whether a signal's distribution is stable across GW blocks,
and assigns a pooling decision based on that classification.

Vocabulary:
  homogeneity: stable | moderate_shift | unstable
  pooling:     pool_confirmed | pool_with_caveat | restrict_to_midseason

Heuristic: normalized median shift between blocks.
  normalized_shift = |median_b1 - median_b2| / (pooled_iqr + EPSILON)
  stable:         normalized_shift < STABLE_THRESHOLD
  moderate_shift: STABLE_THRESHOLD <= normalized_shift < UNSTABLE_THRESHOLD
  unstable:       normalized_shift >= UNSTABLE_THRESHOLD

All-zero signals have IQR = 0 and median = 0 across all blocks, producing
normalized_shift = 0 → classified as stable. This is correct: a signal
that is consistently zero is structurally constant, not unstable.

Thresholds are operational heuristics. Treat classifications as analytical
guidance, not statistical claims.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from itertools import combinations


BLOCK_HOMOGENEITY_VALUES: frozenset[str] = frozenset(
    {"stable", "moderate_shift", "unstable"}
)

POOLING_DECISION_VALUES: frozenset[str] = frozenset(
    {"pool_confirmed", "pool_with_caveat", "restrict_to_midseason"}
)

# Default GW split: first half GW1-17, second half GW18-38.
# Parameterizable via gw_blocks argument.
DEFAULT_GW_BLOCKS: dict[str, tuple[int, int]] = {
    "first_half": (1, 17),
    "second_half": (18, 38),
}

# Thresholds for normalized median shift classification.
STABLE_THRESHOLD: float = 0.5
UNSTABLE_THRESHOLD: float = 1.5

# Added to pooled IQR in denominator to avoid division by zero.
EPSILON: float = 1e-6

# Minimum observations required in a block to compute meaningful statistics.
MIN_N_FOR_BLOCK_STATS: int = 10

_HOMOGENEITY_TO_POOLING: dict[str, str] = {
    "stable": "pool_confirmed",
    "moderate_shift": "pool_with_caveat",
    "unstable": "restrict_to_midseason",
}


def compute_signal_block_distributions(
    df: pd.DataFrame,
    signals: list[str],
    positions: list[str],
    gw_column: str = "gw",
    gw_blocks: dict[str, tuple[int, int]] | None = None,
) -> pd.DataFrame:
    """Compute per-block distribution statistics for each signal-position pair.

    Args:
        df:         DataFrame containing gw, position, and signal columns.
        signals:    Signal column names to evaluate.
        positions:  Position values to iterate over.
        gw_column:  Name of the gameweek column.
        gw_blocks:  Mapping of block name → (min_gw, max_gw) inclusive.
                    Defaults to DEFAULT_GW_BLOCKS.

    Returns:
        DataFrame with one row per (signal, position, block) and columns:
        signal, position, block, n, median, q1, q3, iqr, min_gw, max_gw.
        Rows with n < MIN_N_FOR_BLOCK_STATS have NaN for distribution columns.
    """
    blocks = gw_blocks if gw_blocks is not None else DEFAULT_GW_BLOCKS

    required = {gw_column, "position"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    rows: list[dict] = []
    for signal in signals:
        if signal not in df.columns:
            continue
        for position in positions:
            pos_mask = df["position"] == position
            pos_df = df.loc[pos_mask]

            for block_name, (min_gw, max_gw) in blocks.items():
                block_mask = pos_df[gw_column].between(min_gw, max_gw)
                block_df = pos_df.loc[block_mask, signal].dropna()
                n = len(block_df)

                if n < MIN_N_FOR_BLOCK_STATS:
                    rows.append({
                        "signal": signal,
                        "position": position,
                        "block": block_name,
                        "n": n,
                        "median": float("nan"),
                        "q1": float("nan"),
                        "q3": float("nan"),
                        "iqr": float("nan"),
                        "min_gw": min_gw,
                        "max_gw": max_gw,
                    })
                    continue

                q1 = float(np.percentile(block_df, 25))
                q3 = float(np.percentile(block_df, 75))
                rows.append({
                    "signal": signal,
                    "position": position,
                    "block": block_name,
                    "n": n,
                    "median": float(np.median(block_df)),
                    "q1": q1,
                    "q3": q3,
                    "iqr": q3 - q1,
                    "min_gw": min_gw,
                    "max_gw": max_gw,
                })

    return pd.DataFrame(rows)


def classify_block_homogeneity(block_stats: pd.DataFrame) -> str:
    """Classify distribution homogeneity across blocks for one (signal, position).

    Args:
        block_stats: Rows from compute_signal_block_distributions for a single
                     (signal, position). Must have columns: block, median, iqr.
                     Must contain at least two blocks.

    Returns:
        One of {stable, moderate_shift, unstable}.

    Rows with NaN median (insufficient observations) produce "unstable" when
    paired with any row that has a non-NaN median, because the missing block
    prevents a pooling decision. If ALL blocks have NaN median, returns "stable"
    — treated equivalently to an all-zero signal (consistently unobservable).
    """
    required = {"block", "median", "iqr"}
    missing = required - set(block_stats.columns)
    if missing:
        raise ValueError(f"block_stats missing required columns: {sorted(missing)}")

    valid = block_stats.dropna(subset=["median", "iqr"])

    if len(valid) < 2:
        # Fewer than 2 valid blocks — insufficient data to compare.
        # Return stable only when no valid blocks exist (all unobservable).
        if len(valid) == 0:
            return "stable"
        return "unstable"

    medians = valid["median"].to_numpy(dtype=float)
    iqrs = valid["iqr"].to_numpy(dtype=float)

    max_shift = 0.0
    for (i, j) in combinations(range(len(medians)), 2):
        pooled_iqr = (iqrs[i] + iqrs[j]) / 2.0
        normalized_shift = abs(medians[i] - medians[j]) / (pooled_iqr + EPSILON)
        if normalized_shift > max_shift:
            max_shift = normalized_shift

    if max_shift < STABLE_THRESHOLD:
        return "stable"
    if max_shift < UNSTABLE_THRESHOLD:
        return "moderate_shift"
    return "unstable"


def flag_pooling_decision(homogeneity: str) -> str:
    """Map a homogeneity classification to a pooling decision.

    Args:
        homogeneity: One of {stable, moderate_shift, unstable}.

    Returns:
        One of {pool_confirmed, pool_with_caveat, restrict_to_midseason}.

    Raises:
        ValueError: if homogeneity is not a recognized vocabulary value.
    """
    if homogeneity not in BLOCK_HOMOGENEITY_VALUES:
        raise ValueError(
            f"unrecognized homogeneity value {homogeneity!r}; "
            f"expected one of {sorted(BLOCK_HOMOGENEITY_VALUES)}"
        )
    return _HOMOGENEITY_TO_POOLING[homogeneity]
