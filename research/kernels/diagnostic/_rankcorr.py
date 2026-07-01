"""Shared rank-correlation helper for diagnostic kernels.

Single canonical implementation of the Spearman / Kendall tau-b rank correlation
used across ``panel.py`` and ``serial.py`` (previously duplicated in both).
"""

from __future__ import annotations

import warnings

import pandas as pd
from scipy.stats import kendalltau, spearmanr

# Supported rank-correlation methods. Spearman is the project default (ADR-001) so the read is
# comparable with every other kernel; Kendall's tau-b is the tie-corrected sensitivity check for
# heavily tied (zero-inflated) signals.
_METHODS = ("spearman", "kendall")


def rank_corr(a: pd.Series, b: pd.Series, method: str) -> float:
    """Rank correlation under the named method: 'spearman' (rank-Pearson) or 'kendall' (tau-b)."""
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # scipy's default kendalltau variant is tau-b (tie-corrected).
        stat = spearmanr(a, b).statistic if method == "spearman" else kendalltau(a, b).statistic
    return float(stat)
