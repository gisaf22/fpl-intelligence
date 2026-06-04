"""Tests for research.kernels.multiplicity (multiple-comparison control)."""

from __future__ import annotations

import numpy as np
import pytest

from research.kernels.multiplicity import benjamini_hochberg, holm_bonferroni

pytestmark = pytest.mark.unit

# Classic Benjamini-Hochberg worked example (10 p-values).
P_FAMILY = [0.001, 0.008, 0.039, 0.041, 0.042, 0.060, 0.074, 0.205, 0.212, 0.216]


def test_bh_rejections_match_known_vector() -> None:
    out = benjamini_hochberg(P_FAMILY, alpha=0.05)
    assert out["reject"].tolist() == [True, True] + [False] * 8


def test_bh_q_values_are_monotone_in_p_order() -> None:
    out = benjamini_hochberg(P_FAMILY)
    q_sorted_by_p = out["q_value"][np.argsort(P_FAMILY, kind="stable")]
    assert np.all(np.diff(q_sorted_by_p) >= -1e-9)


def test_holm_is_not_more_powerful_than_bh() -> None:
    bh = benjamini_hochberg(P_FAMILY, alpha=0.05)["reject"].sum()
    holm = holm_bonferroni(P_FAMILY, alpha=0.05)["reject"].sum()
    assert holm <= bh  # FWER control rejects no more than FDR control


def test_order_is_preserved_under_shuffle() -> None:
    p = [0.04, 0.001, 0.2, 0.008]
    out = benjamini_hochberg(p)
    # q-value for the smallest p (index 1) must be the smallest q.
    assert np.argmin(out["q_value"]) == 1


def test_empty_input_returns_empty_arrays() -> None:
    for fn in (benjamini_hochberg, holm_bonferroni):
        out = fn([])
        assert out["reject"].size == 0


@pytest.mark.parametrize("bad", [[-0.1, 0.5], [0.5, 1.2], [np.nan, 0.3]])
def test_invalid_p_values_raise(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        benjamini_hochberg(bad)


def test_q_values_bounded_unit_interval() -> None:
    out = benjamini_hochberg([0.9, 0.95, 0.99])
    assert np.all((out["q_value"] >= 0.0) & (out["q_value"] <= 1.0))
