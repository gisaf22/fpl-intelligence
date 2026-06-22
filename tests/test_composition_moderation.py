"""Tests for model.assemble.composition_study._moderation_instability_rate."""

from __future__ import annotations

import pytest

from model.assemble.composition_study import _moderation_instability_rate

pytestmark = pytest.mark.unit


def test_stable_ordering_is_zero() -> None:
    orderings = [["a", "b", "c"], ["a", "b", "c"], ["a", "b", "c"]]
    assert _moderation_instability_rate(orderings) == 0.0


def test_one_of_three_comparisons_changed() -> None:
    orderings = [["a", "b", "c"], ["a", "b", "c"], ["b", "a", "c"], ["a", "b", "c"]]
    assert _moderation_instability_rate(orderings) == pytest.approx(1 / 3)


def test_all_changed_is_one() -> None:
    orderings = [["a", "b"], ["b", "a"], ["b", "a"]]
    assert _moderation_instability_rate(orderings) == 1.0


def test_fewer_than_two_strata_returns_zero() -> None:
    assert _moderation_instability_rate([["a", "b"]]) == 0.0
    assert _moderation_instability_rate([]) == 0.0
