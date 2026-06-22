"""Tests for multivariate partial-rho functions."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import spearmanr

from research.kernels.inferential.resampling import bootstrap_partial_rho, partial_spearman

pytestmark = pytest.mark.unit


def _design(n: int = 300, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    y = x[:, 0] * 0.6 + x[:, 1] * 0.2 + rng.normal(size=n)
    return x, y


def test_singleton_reduces_to_bivariate_spearman() -> None:
    x, y = _design()
    col = x[:, [0]]
    assert partial_spearman(col, y, 0) == pytest.approx(float(spearmanr(col[:, 0], y).statistic))


def test_controlling_for_collinear_signal_shrinks_partial() -> None:
    rng = np.random.default_rng(11)
    n = 400
    s = rng.normal(size=n)
    y = s * 0.7 + rng.normal(size=n)
    X = np.column_stack([s, s + rng.normal(scale=1e-3, size=n)])
    partial = abs(partial_spearman(X, y, 0))
    bivariate = abs(float(spearmanr(s, y).statistic))
    assert partial < bivariate


def test_constant_residual_returns_zero() -> None:
    rng = np.random.default_rng(3)
    n = 200
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    y = rng.normal(size=n)
    assert partial_spearman(X, y, 0) == 0.0


def test_bootstrap_partial_rho_is_seed_deterministic() -> None:
    x, y = _design()
    assert bootstrap_partial_rho(x, y, 0, partial_spearman, n_samples=300, seed=42) == bootstrap_partial_rho(
        x, y, 0, partial_spearman, n_samples=300, seed=42
    )


def test_bootstrap_partial_rho_interval_brackets_estimate() -> None:
    x, y = _design()
    rho, lo, hi = bootstrap_partial_rho(x, y, 0, partial_spearman, n_samples=500, seed=1)
    assert lo <= rho <= hi
    assert lo > 0
