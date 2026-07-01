"""Shared rank-correlation helper for diagnostic kernels.

Single canonical implementation of the Spearman / Kendall tau-b rank correlation
used across ``panel.py`` and ``serial.py`` (previously duplicated in both).
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
from scipy.stats import kendalltau, spearmanr

# Supported rank-correlation methods. Spearman is the project default (ADR-001) so the read is
# comparable with every other kernel; Kendall's tau-b is the tie-corrected sensitivity check for
# heavily tied (zero-inflated) signals.
_METHODS = ("spearman", "kendall")


def rank_corr(a: Any, b: Any, method: str) -> float:
    """Rank correlation under the named method: 'spearman' (rank-Pearson) or 'kendall' (tau-b).

    Returns NaN when either side is constant (the correlation is undefined) — short-circuited
    before scipy so a degenerate bootstrap draw costs nothing and never relies on warning
    suppression. Accepts pandas Series or numpy arrays.
    """
    if method not in _METHODS:
        raise ValueError(f"method must be one of {_METHODS}, got {method!r}")
    if np.unique(a).size <= 1 or np.unique(b).size <= 1:
        return float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # scipy's default kendalltau variant is tau-b (tie-corrected).
        stat = spearmanr(a, b).statistic if method == "spearman" else kendalltau(a, b).statistic
    return float(stat)
