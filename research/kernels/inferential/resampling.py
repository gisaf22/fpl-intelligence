"""Resampling-based uncertainty quantification.

Bootstrap confidence intervals for rank correlation. Used to decide whether an
observed signal→target association is distinguishable from zero, rather than
reporting a point estimate alone.

Deterministic by construction: results depend only on the inputs and the seed, so
the same study run twice produces the same interval (a reproducibility contract of
the research layer).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.stats import rankdata, spearmanr

# Defaults centralised here so all studies quote comparable intervals.
N_BOOTSTRAP = 1000
BOOTSTRAP_SEED = 0
CI_LEVEL = 0.95

# Minimum paired observations to attempt a bootstrap.
MIN_N = 10


def bootstrap_spearman_ci(
    x: np.ndarray,
    y: np.ndarray,
    n_samples: int = N_BOOTSTRAP,
    ci_level: float = CI_LEVEL,
    seed: int = BOOTSTRAP_SEED,
) -> dict | None:
    """Bootstrap percentile CI for the Spearman correlation between x and y.

    Args:
        x, y:      Paired observation arrays of equal length.
        n_samples: Number of bootstrap resamples.
        ci_level:  Two-sided coverage (e.g. 0.95 for a 95% interval).
        seed:      RNG seed; fixing it makes the interval reproducible.

    Returns:
        Dict {rho, ci_lower, ci_upper, n}, all rounded to 4 dp, or
        None when there are fewer than MIN_N pairs or either array is constant.

    Raises:
        ValueError: if x and y differ in length.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape:
        raise ValueError(f"x and y must have the same shape: {x.shape} vs {y.shape}")

    n = x.size
    if n < MIN_N:
        return None
    if np.unique(x).size <= 1 or np.unique(y).size <= 1:
        return None

    rho_obs = float(spearmanr(x, y).statistic)

    rng = np.random.default_rng(seed)
    boot = np.empty(n_samples)
    for i in range(n_samples):
        idx = rng.integers(0, n, size=n)
        boot[i] = float(spearmanr(x[idx], y[idx]).statistic)

    alpha = 1.0 - ci_level
    ci_lower = float(np.nanpercentile(boot, 100 * alpha / 2))
    ci_upper = float(np.nanpercentile(boot, 100 * (1 - alpha / 2)))

    return {
        "rho": round(rho_obs, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "n": int(n),
    }


# Default permutations for a null-baseline estimate; smaller than N_BOOTSTRAP since
# only a mean (not a tail percentile) is read off the null distribution.
N_PERMUTATIONS = 500
PERMUTATION_SEED = 99


def estimate_chance_correlation(
    x: np.ndarray,
    y: np.ndarray,
    n_perm: int = N_PERMUTATIONS,
    seed: int = PERMUTATION_SEED,
) -> float:
    """Estimate the rank correlation expected by chance for this sample size.

    Repeatedly shuffles ``y`` relative to ``x`` and measures |rho| each time,
    producing the null-distribution mean. An observed association must clear
    this value to be meaningful beyond sampling noise. Deterministic given ``seed``.

    Args:
        x, y:   Paired observation arrays of equal length.
        n_perm: Number of target permutations.
        seed:   RNG seed; fixing it makes the baseline reproducible.

    Returns:
        Mean |rho| across permutations, or 0.0 when there are fewer than MIN_N pairs.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < MIN_N:
        return 0.0
    rng = np.random.default_rng(seed)
    rhos = [abs(float(spearmanr(x, rng.permutation(y)).statistic)) for _ in range(n_perm)]
    return float(np.mean(rhos))


def partial_spearman(X: np.ndarray, y: np.ndarray, signal_idx: int) -> float:
    """Partial Spearman rho of X[:, signal_idx] vs y controlling for all other columns.

    Rank-OLS residualisation: rank every column and the target, regress the
    signal and target on the remaining ranked signals via least squares, then
    take the Pearson correlation of the two residual series. Reduces to bivariate
    Spearman rho when X has a single column.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n, p = X.shape

    X_r = np.apply_along_axis(rankdata, 0, X).astype(float)
    y_r = rankdata(y).astype(float)

    if p == 1:
        return float(spearmanr(X_r[:, 0], y_r).statistic)

    others = np.delete(X_r, signal_idx, axis=1)
    A = np.column_stack([np.ones(n), others])
    coef_x = np.linalg.lstsq(A, X_r[:, signal_idx], rcond=None)[0]
    coef_y = np.linalg.lstsq(A, y_r, rcond=None)[0]
    resid_x = X_r[:, signal_idx] - A @ coef_x
    resid_y = y_r - A @ coef_y

    if not (np.isfinite(resid_x).all() and np.isfinite(resid_y).all()):
        return 0.0
    if np.std(resid_x) * np.std(resid_y) < 1e-12:
        return 0.0
    return float(np.corrcoef(resid_x, resid_y)[0, 1])


def bootstrap_partial_rho(
    X: np.ndarray,
    y: np.ndarray,
    signal_idx: int,
    partial_fn: Callable[[np.ndarray, np.ndarray, int], float],
    n_samples: int = 2000,
    ci_level: float = CI_LEVEL,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Bootstrap percentile CI for a partial Spearman estimator.

    Resamples observation rows with replacement and recomputes the partial rho
    each time. Deterministic given ``seed``. The estimator is injected as
    ``partial_fn`` so this function has no dependency on any specific partial
    correlation implementation.

    Args:
        X:          (n, p) signal matrix, one row per observation.
        y:          (n,) target array.
        signal_idx: Column in X whose partial association is bootstrapped.
        partial_fn: Callable (X, y, signal_idx) → float — the partial estimator.
        n_samples:  Number of bootstrap resamples.
        ci_level:   Two-sided coverage (e.g. 0.95).
        seed:       RNG seed for reproducibility.

    Returns:
        (partial_rho, ci_lower, ci_upper) — observed value and bootstrap interval.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    rho_obs = partial_fn(X, y, signal_idx)
    rng = np.random.default_rng(seed)
    boot = np.empty(n_samples)
    for i in range(n_samples):
        idx = rng.integers(0, len(y), size=len(y))
        boot[i] = partial_fn(X[idx], y[idx], signal_idx)
    alpha = 1.0 - ci_level
    return (
        rho_obs,
        float(np.percentile(boot, 100 * alpha / 2)),
        float(np.percentile(boot, 100 * (1.0 - alpha / 2))),
    )


def _spearman_or_nan(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho, NaN when either side is constant (correlation undefined)."""
    if np.unique(a).size <= 1 or np.unique(b).size <= 1:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def _percentile_ci(draws: np.ndarray, ci_level: float) -> tuple[float, float]:
    """Two-sided percentile CI over the non-NaN draws, rounded to 4 dp."""
    arr = draws[~np.isnan(draws)]
    if arr.size == 0:
        return (float("nan"), float("nan"))
    alpha = 1.0 - ci_level
    lo = float(np.percentile(arr, 100 * alpha / 2))
    hi = float(np.percentile(arr, 100 * (1 - alpha / 2)))
    return (round(lo, 4), round(hi, 4))


def _two_sided_p(draws: np.ndarray) -> float:
    """Two-sided bootstrap p-value for H0: statistic = 0, over the non-NaN draws.

    Uses the ``(1 + k) / (1 + n)`` plug-in so the p-value is never exactly 0. Mirrors the
    player-clustered p in ``diagnostic/panel.py`` so the two decomposition notebooks quote
    comparable, cluster-respecting significance.
    """
    arr = draws[~np.isnan(draws)]
    if arr.size == 0:
        return float("nan")
    tail = min(int(np.sum(arr <= 0.0)), int(np.sum(arr >= 0.0)))
    return round(min(1.0, 2.0 * (1 + tail) / (1 + arr.size)), 4)


def cluster_bootstrap_minutes_adjusted_rho(
    signal: np.ndarray,
    control: np.ndarray,
    target: np.ndarray,
    cluster_ids: np.ndarray,
    n_samples: int = N_BOOTSTRAP,
    ci_level: float = CI_LEVEL,
    seed: int = BOOTSTRAP_SEED,
) -> dict | None:
    """Player-clustered bootstrap of a signal→target association before and after controlling.

    Answers Q2: does ``signal``'s rank association with ``target`` survive once ``control``
    (playing time) is held equal? Reports three quantities from **one shared set of cluster
    resamples**, so the shrinkage interval is properly paired:

      * ``rho_raw``   — bivariate Spearman(signal, target).
      * ``rho_adj``   — partial Spearman(signal, target) controlling for ``control``.
      * ``shrinkage`` — ``rho_raw - rho_adj`` (how much of the raw link was playing time).

    Resampling is clustered by **player, not row** (``cluster_ids``): rows within a player are
    not independent (the same player recurs every gameweek), so a row bootstrap understates the
    uncertainty. A player drawn twice contributes all their rows twice — matching the clustering
    contract of ``diagnostic/panel.py``.

    Args:
        signal, control, target: Paired observation arrays of equal length (no NaNs).
        cluster_ids: Player id per row; distinct values define the resampled clusters.
        n_samples:   Number of cluster resamples.
        ci_level:    Two-sided coverage (e.g. 0.95).
        seed:        RNG seed for reproducibility.

    Returns:
        Dict ``{rho_raw, raw_ci, rho_adj, adj_ci, shrinkage, shrinkage_ci, adj_p, n, n_players}``
        where each ``*_ci`` is a ``(lo, hi)`` tuple and ``adj_p`` is the clustered two-sided
        p-value for ``rho_adj != 0`` (feeds a BH-FDR screen). ``None`` when there are fewer than
        ``MIN_N`` pairs, fewer than 2 clusters, or a constant signal/target.
    """
    signal = np.asarray(signal, dtype=float)
    control = np.asarray(control, dtype=float)
    target = np.asarray(target, dtype=float)
    cluster_ids = np.asarray(cluster_ids)
    n = signal.size
    if not (control.size == target.size == cluster_ids.size == n):
        raise ValueError("signal, control, target, cluster_ids must share length")
    if n < MIN_N or np.unique(signal).size <= 1 or np.unique(target).size <= 1:
        return None

    _, inv = np.unique(cluster_ids, return_inverse=True)
    n_players = int(inv.max()) + 1
    if n_players < 2:
        return None
    rows_by_cluster = [np.flatnonzero(inv == k) for k in range(n_players)]

    def _adj(sig: np.ndarray, ctrl: np.ndarray, tgt: np.ndarray) -> float:
        return partial_spearman(np.column_stack([sig, ctrl]), tgt, 0)

    rho_raw = _spearman_or_nan(signal, target)
    rho_adj = _adj(signal, control, target)

    rng = np.random.default_rng(seed)
    raw_draws = np.empty(n_samples)
    adj_draws = np.empty(n_samples)
    shr_draws = np.empty(n_samples)
    for i in range(n_samples):
        drawn = rng.integers(0, n_players, size=n_players)
        rows = np.concatenate([rows_by_cluster[d] for d in drawn])
        r = _spearman_or_nan(signal[rows], target[rows])
        a = _adj(signal[rows], control[rows], target[rows])
        raw_draws[i] = r
        adj_draws[i] = a
        shr_draws[i] = r - a

    return {
        "rho_raw": round(rho_raw, 4),
        "raw_ci": _percentile_ci(raw_draws, ci_level),
        "rho_adj": round(rho_adj, 4),
        "adj_ci": _percentile_ci(adj_draws, ci_level),
        "shrinkage": round(rho_raw - rho_adj, 4),
        "shrinkage_ci": _percentile_ci(shr_draws, ci_level),
        "adj_p": _two_sided_p(adj_draws),
        "n": int(n),
        "n_players": n_players,
    }
