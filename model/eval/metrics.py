"""Shared evaluation metrics - the single home for the scoring primitives every phase reuses.

Extracted from the Phase-0 harness so no module re-implements or cross-imports a private symbol.
Pure functions: they take/return arrays or DataFrames and do no I/O. Ranking is within-position
(FPL squads fill under position quotas), so the headline is a *grouped* Spearman - the mean rank
correlation over (gameweek[, position]) cells - and its uncertainty is a **block bootstrap over the
per-gameweek series** (consecutive GWs autocorrelate; one season is thin), matching the decision layer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# Two-sided coverage for the block-bootstrap interval; block length in gameweeks.
CI_LEVEL = 0.95
BLOCK_GWS = 4
N_BOOTSTRAP = 3000


def has_rank_signal(g: pd.DataFrame, pred_col: str, target_col: str, min_n: int) -> bool:
    """Whether a (gameweek[, position]) cell has enough signal to yield a meaningful rank metric.

    Requires enough rows and variance on *both* sides: a constant prediction makes any ranking an
    argsort artifact; a constant target makes precision/NDCG trivially 1.0 and Spearman undefined.
    The single home for this predicate so every metric family (grouped Spearman, the per-GW
    precision/NDCG loop, the pre-Phase-2 checks) scores the *same* qualifying cells and cannot drift.
    """
    return len(g) >= min_n and g[pred_col].nunique() > 1 and g[target_col].nunique() > 1


def cell_spearman(pred: np.ndarray, actual: np.ndarray) -> float:
    """Spearman rank correlation for a single (gameweek[, position]) cell (caller guards rankability)."""
    return float(spearmanr(pred, actual).statistic)


def grouped_spearman_series(df: pd.DataFrame, pred_col: str, target_col: str,
                            by: list[str], min_n: int) -> np.ndarray:
    """Per-cell within-group rank correlations over cells of ``by`` (>= min_n rows, non-constant)."""
    rhos = []
    for _, g in df.groupby(by):
        if has_rank_signal(g, pred_col, target_col, min_n):
            rhos.append(cell_spearman(g[pred_col].to_numpy(), g[target_col].to_numpy()))
    return np.asarray(rhos, dtype=float)


def grouped_spearman(df: pd.DataFrame, pred_col: str, target_col: str,
                     by: list[str], min_n: int) -> float:
    """Mean rank correlation over cells of ``by`` (the within-position ranking benchmark)."""
    rhos = grouped_spearman_series(df, pred_col, target_col, by, min_n)
    return float(np.mean(rhos)) if len(rhos) else np.nan


def block_bootstrap_ci(values: np.ndarray, block: int = BLOCK_GWS, n: int = N_BOOTSTRAP,
                       ci_level: float = CI_LEVEL, seed: int = 0) -> tuple[float, float]:
    """Percentile CI of the mean of a per-gameweek series, resampling blocks of consecutive GWs.

    Consecutive gameweeks autocorrelate (form runs), so resampling *blocks* (not individual GWs) gives
    an honest interval on a per-GW metric. Degenerate (constant) series return a point interval.
    """
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < block:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    k = int(np.ceil(len(values) / block))
    draws = np.empty(n)
    for i in range(n):
        starts = rng.integers(0, len(values) - block + 1, size=k)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:len(values)]
        draws[i] = values[idx].mean()
    a = (1.0 - ci_level) / 2.0
    return (float(np.percentile(draws, 100 * a)), float(np.percentile(draws, 100 * (1 - a))))


def spearman_with_ci(df: pd.DataFrame, pred_col: str, target_col: str, by: list[str],
                     min_n: int, seed: int = 0) -> tuple[float, tuple[float, float]]:
    """Grouped Spearman point estimate + a block-bootstrap CI over its per-gameweek series.

    ``by`` should include ``gw`` (the bootstrap unit). Returns ``(estimate, (lo, hi))``.
    """
    series = grouped_spearman_series(df, pred_col, target_col, by, min_n)
    est = float(np.mean(series)) if len(series) else np.nan
    return est, block_bootstrap_ci(series, seed=seed)


def precision_at_k(pred: np.ndarray, actual: np.ndarray, k: int) -> float:
    """Share of the predicted top-K that fall in the (tie-inclusive) actual top-K.

    Question: *how many* of my top-K picks were real hits? (count/membership — order within K and
    magnitude are ignored; contrast :func:`ndcg_at_k`.) 
    
    Tie-aware on the actual side: the target is
    heavily tied, so the actual top-K is everyone at or above the k-th largest actual value (else
    which tied player counts is an argsort artifact).
    """
    k = min(k, len(pred))
    thresh = np.sort(actual)[::-1][k - 1]
    relevant = actual >= thresh
    top_pred = np.argsort(-pred)[:k]
    return float(relevant[top_pred].sum()) / k


def ndcg_at_k(pred: np.ndarray, actual: np.ndarray, k: int) -> float:
    """NDCG@K with points (clipped at 0) as gains, players ordered by prediction.

    Question: *how well* did I rank the top — did I put the biggest scorers highest? (graded by
    points, position-weighted; contrast :func:`precision_at_k`, which only counts membership.)
    """
    k = min(k, len(pred))
    gains = np.clip(actual, 0, None)
    disc = 1.0 / np.log2(np.arange(2, k + 2))
    
    # Prediction ties broken arbitrarily by argsort (deterministic, not tie-averaged) — adds slight
    # noise for integer-valued baselines like base_last; negligible once averaged over gameweeks.
    dcg = (gains[np.argsort(-pred)][:k] * disc).sum()
    idcg = (np.sort(gains)[::-1][:k] * disc).sum()
    return float(dcg / idcg) if idcg > 0 else np.nan
