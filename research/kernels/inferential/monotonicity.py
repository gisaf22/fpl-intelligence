"""Bootstrap confidence for geometry shape — Rung I (Inferential).

Assesses how stable the observed adjacent-bin direction pattern is across
bootstrap resamples. Bridges descriptive binning (research.kernels.descriptive.binning)
and diagnostic shape classification (research.kernels.diagnostic.shape).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.kernels.descriptive.binning import MIN_N_SHAPE, bin_analysis
from research.kernels.diagnostic.shape import get_bin_direction


def monotonicity_confidence(
    df: pd.DataFrame,
    signal: str,
    target: str,
    position: str,
    original_bin_stats: pd.DataFrame,
    scheme: tuple,
    n_bootstrap: int = 200,
    seed: int = 42,
) -> float:
    """Bootstrap stability of the original adjacent-bin direction pattern.

    Returns the fraction of bootstrap resamples where the bin direction pattern
    matches the original. Higher = more confident the shape is genuine.
    Returns NaN when n_bootstrap=0 or insufficient data.
    """
    if n_bootstrap == 0:
        return np.nan

    subset = df[df["position"] == position][[signal, target]].dropna()
    if len(subset) < MIN_N_SHAPE:
        return np.nan

    original_direction = get_bin_direction(original_bin_stats)
    if not original_direction:
        return np.nan

    rng = np.random.default_rng(seed)
    agreements = 0
    attempts = 0

    for _ in range(n_bootstrap):
        sample = subset.sample(frac=1.0, replace=True, random_state=int(rng.integers(1_000_000)))
        bs_stats, _ = bin_analysis(
            sample.assign(position=position),
            signal,
            target,
            position,
            scheme,
        )
        if bs_stats is None or len(bs_stats) < 2:
            continue
        attempts += 1
        if get_bin_direction(bs_stats) == original_direction:
            agreements += 1

    if attempts == 0:
        return np.nan
    return round(agreements / attempts, 3)
