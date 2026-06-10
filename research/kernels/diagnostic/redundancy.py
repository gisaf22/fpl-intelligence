"""Pairwise signal redundancy screening.

Computes pairwise Spearman correlation between signals and identifies pairs
that are likely measuring the same construct. Used in foundation EDA and
composition pre-screening — not part of the qualification pipeline.

``DEFAULT_REDUNDANCY_THRESHOLD = 0.85`` is an operational heuristic with no
statistical derivation. Treat flagged pairs as candidates for investigation,
not confirmed redundancies.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

# Minimum observations required to compute a meaningful correlation.
MIN_N_FOR_RHO = 30

# Default threshold for flagging a pair as redundant.
DEFAULT_REDUNDANCY_THRESHOLD = 0.85


def compute_pairwise_rho(
    df: pd.DataFrame,
    signals: list[str],
    position: str,
) -> pd.DataFrame:
    """Compute Spearman rho matrix for all signal pairs within a position.

    Args:
        df:       Analytical dataset with a 'position' column and signal columns.
        signals:  Signal column names to include in the matrix.
        position: Position label to filter on (e.g. 'MID').

    Returns:
        Symmetric DataFrame with signals as both index and columns.
        Diagonal entries are 1.0. Cells where either signal has insufficient
        data or is constant are NaN.

    Raises:
        ValueError: if 'position' column is missing from df.
    """
    if "position" not in df.columns:
        raise ValueError("df missing required column: 'position'")

    missing = [s for s in signals if s not in df.columns]
    if missing:
        raise ValueError(f"df missing signal columns: {missing}")

    pos_df = df[df["position"] == position][signals].dropna()

    n = len(pos_df)
    size = len(signals)
    matrix = np.full((size, size), np.nan)
    np.fill_diagonal(matrix, 1.0)

    if n < MIN_N_FOR_RHO:
        return pd.DataFrame(matrix, index=signals, columns=signals)

    for i, j in combinations(range(size), 2):
        sig_i = signals[i]
        sig_j = signals[j]
        pair = pos_df[[sig_i, sig_j]].dropna()
        if len(pair) < MIN_N_FOR_RHO:
            continue
        if pair[sig_i].nunique() <= 1 or pair[sig_j].nunique() <= 1:
            continue
        rho, _ = stats.spearmanr(pair[sig_i], pair[sig_j])
        matrix[i, j] = round(float(rho), 4)
        matrix[j, i] = round(float(rho), 4)

    return pd.DataFrame(matrix, index=signals, columns=signals)


def identify_redundant_pairs(
    rho_matrix: pd.DataFrame,
    threshold: float = DEFAULT_REDUNDANCY_THRESHOLD,
) -> list[tuple[str, str]]:
    """Return signal pairs whose absolute rho meets or exceeds the threshold.

    Args:
        rho_matrix: Symmetric DataFrame from compute_pairwise_rho.
        threshold:  Absolute rho threshold for flagging redundancy.

    Returns:
        Sorted list of (signal_a, signal_b) tuples, lexicographically ordered
        within each pair and across the list. No duplicate pairs emitted.
    """
    signals = list(rho_matrix.columns)
    flagged: list[tuple[str, str]] = []

    for i, j in combinations(range(len(signals)), 2):
        sig_i = signals[i]
        sig_j = signals[j]
        val = rho_matrix.iloc[i, j]
        if pd.isna(val):
            continue
        if abs(val) >= threshold:
            pair = tuple(sorted((sig_i, sig_j)))
            flagged.append(pair)

    return sorted(set(flagged))
