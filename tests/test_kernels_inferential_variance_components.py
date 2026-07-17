"""Tests for the random-intercept ICC kernel (research.kernels.inferential.variance_components)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.kernels.descriptive.variance_components import decompose_variance
from research.kernels.inferential.variance_components import (
    between_share_bootstrap,
    mixed_effects_icc,
)

pytestmark = pytest.mark.unit

# Small bootstrap for test speed; the kernel default (300) is for real one-shot fits.
_NB = 60


def _panel(
    sigma_between: float, sigma_within: float, n_players: int = 40, n_gw: int = 12, seed: int = 0
) -> pd.DataFrame:
    """Balanced panel with a known between/within split."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        level = rng.normal(5.0, sigma_between)
        for gw in range(1, n_gw + 1):
            rows.append({"player_id": p, "total_points": level + rng.normal(0, sigma_within)})
    return pd.DataFrame(rows)


def test_recovers_high_icc_when_between_dominates() -> None:
    df = _panel(sigma_between=4.0, sigma_within=1.0, seed=1)
    res = mixed_effects_icc(df, n_bootstrap=_NB)
    assert res["icc"] > 0.7
    assert res["sigma2_between"] > res["sigma2_within"]
    # Signal is real: LRT rejects the pooled null, and the ICC CI sits well above 0.
    assert res["lrt_p"] < 0.05
    assert res["icc_ci_lo"] > 0.0


def test_low_icc_when_within_dominates() -> None:
    df = _panel(sigma_between=0.3, sigma_within=4.0, seed=2)
    res = mixed_effects_icc(df, n_bootstrap=_NB)
    assert res["icc"] < 0.3


def test_icc_agrees_with_ss_share_on_balanced_panel() -> None:
    # For a balanced panel ICC and the descriptive SS-share should agree in magnitude.
    df = _panel(sigma_between=3.0, sigma_within=2.0, seed=3)
    icc = mixed_effects_icc(df, n_bootstrap=_NB)["icc"]
    ss_share = decompose_variance(df)["pct_between"] / 100.0
    assert icc == pytest.approx(ss_share, abs=0.1)


def test_returns_nan_when_too_few_players() -> None:
    df = _panel(sigma_between=3.0, sigma_within=2.0, n_players=1, seed=4)
    res = mixed_effects_icc(df, n_bootstrap=_NB)
    assert np.isnan(res["icc"])
    assert res["n_players"] <= 1


def test_ci_bounds_bracket_point_estimate() -> None:
    df = _panel(sigma_between=3.0, sigma_within=2.0, seed=5)
    res = mixed_effects_icc(df, n_bootstrap=_NB)
    assert res["icc_ci_lo"] <= res["icc"] <= res["icc_ci_hi"]


def test_between_share_bootstrap_orders_and_is_deterministic() -> None:
    # Between-variance dominates -> a large, ordered between-share; deterministic given the seed.
    df = _panel(sigma_between=4.0, sigma_within=1.0, seed=1)
    lo, med, hi = between_share_bootstrap(df, n_boot=200)
    assert lo <= med <= hi
    assert med > 0.5
    assert tuple(between_share_bootstrap(df, n_boot=200)) == (lo, med, hi)


def test_between_share_bootstrap_small_when_within_dominates() -> None:
    df = _panel(sigma_between=0.3, sigma_within=4.0, seed=2)
    _, med, _ = between_share_bootstrap(df, n_boot=200)
    assert med < 0.3
