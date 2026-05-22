"""Redundancy detection utilities.

Computes pairwise Spearman correlation between signals, identifies redundant
pairs above a configurable threshold, and provides partial correlation to
disentangle construct overlap from algebraic identity.

Callers are responsible for supplying any domain-specific algebraic
decomposition lists (e.g. known signal identities) as parameters.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from itertools import combinations
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
            flagged.append(pair)  # type: ignore[arg-type]

    return sorted(set(flagged))


def compute_partial_rho(
    df: pd.DataFrame,
    signal_a: str,
    signal_b: str,
    target: str,
    position: str,
) -> float | None:
    """Compute partial Spearman correlation between signal_a and signal_b, controlling for target.

    Uses the correlation-matrix approach on ranked variables:
      r_ab.c = (r_ab - r_ac * r_bc) / sqrt((1 - r_ac^2)(1 - r_bc^2))

    Args:
        df:       Analytical dataset with position, signal, and target columns.
        signal_a: First signal name.
        signal_b: Second signal name.
        target:   Conditioning variable (typically 'total_points').
        position: Position label to filter on.

    Returns:
        Partial correlation in [-1, 1], or None if the matrix is singular,
        there are insufficient observations, or any variable is constant.
    """
    required = {signal_a, signal_b, target, "position"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"df missing required columns: {sorted(missing)}")

    pos_df = df[df["position"] == position][[signal_a, signal_b, target]].dropna()

    if len(pos_df) < MIN_N_FOR_RHO:
        return None

    for col in (signal_a, signal_b, target):
        if pos_df[col].nunique() <= 1:
            return None

    # Convert to ranks then compute 3×3 correlation matrix.
    ranked = pos_df.apply(stats.rankdata)
    cols = [signal_a, signal_b, target]
    corr = ranked[cols].corr(method="pearson")

    r_ab = corr.loc[signal_a, signal_b]
    r_ac = corr.loc[signal_a, target]
    r_bc = corr.loc[signal_b, target]

    denom_sq = (1.0 - r_ac**2) * (1.0 - r_bc**2)
    if denom_sq <= 0.0:
        return None

    partial = (r_ab - r_ac * r_bc) / np.sqrt(denom_sq)
    # Clamp to [-1, 1] to handle floating point edge cases.
    partial = float(np.clip(partial, -1.0, 1.0))
    return round(partial, 4)
