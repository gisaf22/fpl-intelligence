"""Resampling-based uncertainty quantification.

Bootstrap confidence intervals for rank correlation. Used to decide whether an
observed signal→target association is distinguishable from zero, rather than
reporting a point estimate alone.

Deterministic by construction: results depend only on the inputs and the seed, so
the same study run twice produces the same interval (a reproducibility contract of
the research layer).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

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
        Dict {rho, ci_lower, ci_upper, n, excludes_zero}, all rounded to 4 dp, or
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
        "excludes_zero": bool(ci_lower > 0 or ci_upper < 0),
    }
