"""Tests for studies.kernels.resampling (bootstrap CI)."""

from __future__ import annotations

import numpy as np
import pytest

from studies.kernels.resampling import MIN_N, bootstrap_spearman_ci

pytestmark = pytest.mark.unit


def _correlated(n: int = 200, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = x * 0.5 + rng.normal(size=n)
    return x, y


def test_seed_makes_interval_deterministic() -> None:
    x, y = _correlated()
    assert bootstrap_spearman_ci(x, y, seed=42) == bootstrap_spearman_ci(x, y, seed=42)


def test_positive_relationship_excludes_zero() -> None:
    x, y = _correlated()
    out = bootstrap_spearman_ci(x, y, seed=1)
    assert out is not None
    assert out["rho"] > 0
    assert out["ci_lower"] <= out["rho"] <= out["ci_upper"]
    assert out["excludes_zero"] is True


def test_independent_arrays_do_not_exclude_zero() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=300)
    y = rng.normal(size=300)
    out = bootstrap_spearman_ci(x, y, seed=5)
    assert out is not None
    assert out["excludes_zero"] is False


def test_too_few_observations_returns_none() -> None:
    assert bootstrap_spearman_ci(np.arange(MIN_N - 1.0), np.arange(MIN_N - 1.0)) is None


def test_constant_array_returns_none() -> None:
    assert bootstrap_spearman_ci(np.ones(50), np.arange(50.0)) is None


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError, match="same shape"):
        bootstrap_spearman_ci(np.arange(10.0), np.arange(11.0))


def test_metamorphic_monotonic_transform_preserves_estimate() -> None:
    """Rank correlation is invariant under a strictly increasing transform of x."""
    x, y = _correlated()
    base = bootstrap_spearman_ci(x, y, seed=9)
    transformed = bootstrap_spearman_ci(np.exp(x), y, seed=9)
    assert base is not None and transformed is not None
    assert base["rho"] == pytest.approx(transformed["rho"], abs=1e-9)
