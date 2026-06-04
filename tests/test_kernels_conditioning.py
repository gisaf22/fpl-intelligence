"""Tests for studies.kernels.conditioning (class-5 heterogeneity kernel)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from studies.kernels.conditioning import (
    MIN_N_PER_STRATUM,
    classify_heterogeneity,
    compute_conditional_rho,
)

pytestmark = pytest.mark.unit


def _stratum(signal: np.ndarray, target: np.ndarray, label: str) -> pd.DataFrame:
    return pd.DataFrame({"s": signal, "t": target, "m": label})


def test_missing_columns_raise() -> None:
    df = pd.DataFrame({"s": [1, 2, 3], "m": ["A", "A", "A"]})
    with pytest.raises(ValueError, match="missing required columns"):
        compute_conditional_rho(df, "s", "t", "m")


def test_sign_flip_is_heterogeneous_sign() -> None:
    n = MIN_N_PER_STRATUM + 20
    up = _stratum(np.arange(n), np.arange(n), "A")  # rho = +1
    down = _stratum(np.arange(n), np.arange(n)[::-1], "B")  # rho = -1
    cr = compute_conditional_rho(pd.concat([up, down], ignore_index=True), "s", "t", "m")
    assert cr["rho"].tolist() == [1.0, -1.0]
    assert classify_heterogeneity(cr) == "heterogeneous_sign"


def test_homogeneous_when_same_direction_and_magnitude() -> None:
    rng = np.random.default_rng(0)
    n = MIN_N_PER_STRATUM + 50
    frames = []
    for label in ("A", "B", "C"):
        s = rng.normal(size=n)
        t = s + rng.normal(size=n) * 0.1  # strong positive everywhere
        frames.append(_stratum(s, t, label))
    cr = compute_conditional_rho(pd.concat(frames, ignore_index=True), "s", "t", "m")
    assert classify_heterogeneity(cr) == "homogeneous"


def test_thin_stratum_yields_nan_and_is_excluded() -> None:
    big = _stratum(np.arange(MIN_N_PER_STRATUM + 5), np.arange(MIN_N_PER_STRATUM + 5), "A")
    thin = _stratum(np.arange(3), np.arange(3), "B")  # below MIN_N
    cr = compute_conditional_rho(pd.concat([big, thin], ignore_index=True), "s", "t", "m")
    thin_row = cr[cr["stratum"] == "B"].iloc[0]
    assert np.isnan(thin_row["rho"])
    # Only one usable stratum remains -> cannot classify.
    assert classify_heterogeneity(cr) == "insufficient"


def test_metamorphic_monotonic_transform_preserves_rho() -> None:
    """Spearman is rank-based: a monotonic transform of the signal must not change rho."""
    rng = np.random.default_rng(1)
    n = MIN_N_PER_STRATUM + 40
    s = rng.normal(size=n)
    t = s * 0.6 + rng.normal(size=n) * 0.2
    df = _stratum(s, t, "A")
    df_transformed = _stratum(np.exp(s), t, "A")  # exp is strictly increasing
    rho = compute_conditional_rho(df, "s", "t", "m")["rho"].iloc[0]
    rho_t = compute_conditional_rho(df_transformed, "s", "t", "m")["rho"].iloc[0]
    assert rho == pytest.approx(rho_t, abs=1e-9)
