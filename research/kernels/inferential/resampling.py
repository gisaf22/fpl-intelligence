"""Resampling-based uncertainty quantification.

Bootstrap confidence intervals for rank correlation. Used to decide whether an
observed signal→target association is distinguishable from zero, rather than
reporting a point estimate alone.

Deterministic by construction: results depend only on the inputs and the seed, so
the same study run twice produces the same interval (a reproducibility contract of
the research layer).
"""

from __future__ import annotations

from typing import Callable

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
    partial_fn: "Callable[[np.ndarray, np.ndarray, int], float]",
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
