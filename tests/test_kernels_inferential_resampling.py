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


# --- cluster_bootstrap_minutes_adjusted_rho (Q2) -------------------------------

from research.kernels.inferential.resampling import cluster_bootstrap_minutes_adjusted_rho  # noqa: E402


def _panel(n_players: int, n_gw: int, seed: int, mediated: bool) -> dict[str, np.ndarray]:
    """Build a player panel. mediated=True: signal→target link runs entirely through
    the control (minutes), so the minutes-adjusted rho should collapse toward 0."""
    rng = np.random.default_rng(seed)
    sig, ctrl, tgt, pid = [], [], [], []
    for p in range(n_players):
        minutes = rng.uniform(0, 90, size=n_gw)
        if mediated:
            s = minutes + rng.normal(0, 1, size=n_gw)      # signal driven by minutes
            y = minutes + rng.normal(0, 1, size=n_gw)      # target driven by minutes only
        else:
            s = rng.normal(0, 1, size=n_gw)                # signal independent of minutes
            y = 2 * s + minutes * 0.1 + rng.normal(0, 1, size=n_gw)  # target tracks signal
        sig.append(s)
        ctrl.append(minutes)
        tgt.append(y)
        pid.append(np.full(n_gw, p))
    return {
        "signal": np.concatenate(sig), "control": np.concatenate(ctrl),
        "target": np.concatenate(tgt), "cluster_ids": np.concatenate(pid),
    }


def test_cluster_boot_is_deterministic() -> None:
    d = _panel(20, 10, seed=1, mediated=False)
    a = cluster_bootstrap_minutes_adjusted_rho(**d, seed=0, n_samples=300)
    b = cluster_bootstrap_minutes_adjusted_rho(**d, seed=0, n_samples=300)
    assert a == b


def test_genuine_signal_survives_adjustment() -> None:
    d = _panel(40, 12, seed=2, mediated=False)
    out = cluster_bootstrap_minutes_adjusted_rho(**d, seed=0, n_samples=400)
    assert out is not None
    assert out["adj_ci"][0] > 0                    # adjusted rho stays clear of 0
    assert out["adj_p"] < 0.05
    assert out["n_players"] == 40


def test_minutes_proxy_collapses_after_adjustment() -> None:
    d = _panel(40, 12, seed=3, mediated=True)
    out = cluster_bootstrap_minutes_adjusted_rho(**d, seed=0, n_samples=400)
    assert out is not None
    assert out["rho_raw"] > 0.3                    # raw link is real...
    assert out["adj_ci"][0] <= 0 <= out["adj_ci"][1]  # ...but vanishes once minutes held equal
    assert out["shrinkage"] > 0.2


def test_returns_none_below_floor() -> None:
    d = _panel(1, 5, seed=4, mediated=False)       # 1 cluster, too few pairs
    assert cluster_bootstrap_minutes_adjusted_rho(**d, seed=0, n_samples=50) is None
