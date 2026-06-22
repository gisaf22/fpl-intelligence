"""Tests for research.kernels.resampling (bootstrap CI)."""

from __future__ import annotations

import numpy as np
import pytest

from research.kernels.inferential.resampling import MIN_N, bootstrap_spearman_ci, estimate_chance_correlation

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
    assert (out["ci_lower"] > 0 or out["ci_upper"] < 0) is True


def test_independent_arrays_do_not_exclude_zero() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=300)
    y = rng.normal(size=300)
    out = bootstrap_spearman_ci(x, y, seed=5)
    assert out is not None
    assert (out["ci_lower"] > 0 or out["ci_upper"] < 0) is False


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


# ---------------------------------------------------------------------------
# estimate_chance_correlation
# ---------------------------------------------------------------------------


def test_permutation_baseline_is_seed_deterministic() -> None:
    x, y = _correlated()
    assert estimate_chance_correlation(x, y, seed=99) == estimate_chance_correlation(x, y, seed=99)


def test_permutation_baseline_near_zero_for_strong_signal() -> None:
    """Under permuted target the chance baseline is small even when x,y are correlated."""
    x, y = _correlated()
    assert estimate_chance_correlation(x, y, n_perm=200, seed=99) < 0.1


def test_permutation_baseline_too_few_observations_returns_zero() -> None:
    assert estimate_chance_correlation(np.arange(MIN_N - 1.0), np.arange(MIN_N - 1.0)) == 0.0
