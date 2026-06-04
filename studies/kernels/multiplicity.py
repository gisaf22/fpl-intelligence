"""Multiple-comparison control.

When a study tests a family of hypotheses (e.g. several signals by positions by
windows), raw p-values overstate significance: at alpha = 0.05, one in twenty true
nulls is expected to "pass" by chance. This kernel adjusts a declared family of
p-values so the confirmatory tier reports honest significance.

Two methods, both deterministic and order-preserving on the inputs:
  benjamini_hochberg — controls the false discovery rate (expected proportion of
                       false positives among rejections); the default for screening
                       many candidate signals.
  holm_bonferroni    — controls the family-wise error rate (probability of any false
                       positive); stricter, for confirmatory go/no-go decisions.

NOTE: "FDR" in this kernel means **False Discovery Rate**. Elsewhere in this repository
"FDR" means *Fixture Difficulty Rating* (a conditioning variable). They are unrelated.
"""

from __future__ import annotations

import numpy as np


def _validate(p_values: list[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(p_values, dtype=float)
    if arr.ndim != 1:
        raise ValueError("p_values must be one-dimensional")
    if arr.size == 0:
        return arr
    if np.isnan(arr).any():
        raise ValueError("p_values must not contain NaN")
    if ((arr < 0.0) | (arr > 1.0)).any():
        raise ValueError("p_values must lie in [0, 1]")
    return arr


def benjamini_hochberg(
    p_values: list[float] | np.ndarray,
    alpha: float = 0.05,
) -> dict[str, np.ndarray]:
    """Benjamini-Hochberg FDR adjustment, preserving input order.

    Args:
        p_values: The declared family of raw p-values.
        alpha:    Target false discovery rate.

    Returns:
        Dict with two arrays aligned to the input order:
          'reject'   — bool, True where the hypothesis is rejected at FDR <= alpha.
          'q_value'  — the BH-adjusted p-value (monotone, clipped to [0, 1]).
        An empty input yields empty arrays.
    """
    p = _validate(p_values)
    m = p.size
    if m == 0:
        return {"reject": np.array([], dtype=bool), "q_value": np.array([], dtype=float)}

    order = np.argsort(p, kind="stable")
    ranked = p[order]
    ranks = np.arange(1, m + 1)

    # Step-up adjusted p-values, enforced monotone non-decreasing from the largest.
    raw_q = ranked * m / ranks
    q_sorted = np.minimum.accumulate(raw_q[::-1])[::-1]
    q_sorted = np.clip(q_sorted, 0.0, 1.0)

    q_value = np.empty(m, dtype=float)
    q_value[order] = q_sorted

    reject = q_value <= alpha
    return {"reject": reject, "q_value": np.round(q_value, 6)}


def holm_bonferroni(
    p_values: list[float] | np.ndarray,
    alpha: float = 0.05,
) -> dict[str, np.ndarray]:
    """Holm-Bonferroni family-wise error adjustment, preserving input order.

    Args:
        p_values: The declared family of raw p-values.
        alpha:    Target family-wise error rate.

    Returns:
        Dict with two arrays aligned to the input order:
          'reject'   — bool, True where the hypothesis is rejected.
          'p_adj'    — the Holm-adjusted p-value (monotone, clipped to [0, 1]).
        An empty input yields empty arrays.
    """
    p = _validate(p_values)
    m = p.size
    if m == 0:
        return {"reject": np.array([], dtype=bool), "p_adj": np.array([], dtype=float)}

    order = np.argsort(p, kind="stable")
    ranked = p[order]
    multipliers = np.arange(m, 0, -1)

    raw_adj = ranked * multipliers
    adj_sorted = np.maximum.accumulate(raw_adj)
    adj_sorted = np.clip(adj_sorted, 0.0, 1.0)

    p_adj = np.empty(m, dtype=float)
    p_adj[order] = adj_sorted

    reject = p_adj <= alpha
    return {"reject": reject, "p_adj": np.round(p_adj, 6)}
