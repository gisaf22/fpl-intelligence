"""Tests for research.kernels.stability.fraction_rank_order_changed."""

from __future__ import annotations

import pytest

from research.kernels.stability import fraction_rank_order_changed

pytestmark = pytest.mark.unit


def test_stable_ordering_is_zero() -> None:
    orderings = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]]
    assert fraction_rank_order_changed(orderings) == 0.0


def test_one_of_three_comparisons_changed() -> None:
    orderings = [["a", "b", "c"], ["a", "b", "c"], ["b", "a", "c"], ["a", "b", "c"]]
    assert fraction_rank_order_changed(orderings) == pytest.approx(1 / 3)


def test_all_changed_is_one() -> None:
    orderings = [["a", "b"], ["b", "a"], ["b", "a"]]
    assert fraction_rank_order_changed(orderings) == 1.0


def test_fewer_than_two_strata_returns_zero() -> None:
    assert fraction_rank_order_changed([["a", "b"]]) == 0.0
    assert fraction_rank_order_changed([]) == 0.0
