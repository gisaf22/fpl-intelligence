"""Tests for `METRIC.md` §2.1's verdict machinery -- `DESIGN.MD` §7.5's `verdict.py`.

Every case here is synthetic and has a known answer: a series with an obviously positive mean must
reject, an all-zero or negative series must not, Holm must reproduce hand-computable adjusted
values, and the conjunctive reduction must fail on a single unrejected leg. These are the
correctness checks for machinery that is deliberately re-derived rather than imported (§7.5), so
nothing else in the repository guards it.

No live DB: `test_evaluate_integration.py` covers the end-to-end run against the real mart.
"""

from __future__ import annotations

import numpy as np
import pytest

from decisions.free_hit.verdict import (
    BLOCK_LENGTH,
    FAMILY_WISE_ALPHA,
    block_bootstrap_means,
    holm_bonferroni,
    leg_statistics,
    one_sided_p_value,
    percentile_ci,
    verdict,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Block bootstrap
# ---------------------------------------------------------------------------


def test_the_bootstrap_draws_concentrate_around_the_series_mean() -> None:
    series = np.arange(1.0, 33.0)  # mean 16.5
    draws = block_bootstrap_means(series, n_resamples=2000)
    assert draws.size == 2000
    assert draws.mean() == pytest.approx(series.mean(), abs=0.5)


def test_the_bootstrap_is_deterministic_given_the_seed() -> None:
    series = np.arange(1.0, 33.0)
    np.testing.assert_array_equal(
        block_bootstrap_means(series, n_resamples=500, seed=7),
        block_bootstrap_means(series, n_resamples=500, seed=7),
    )
    assert not np.array_equal(
        block_bootstrap_means(series, n_resamples=500, seed=7),
        block_bootstrap_means(series, n_resamples=500, seed=8),
    )


def test_a_constant_series_collapses_to_a_point_distribution() -> None:
    """Every resample of a constant series has the same mean, whatever blocks are drawn."""
    draws = block_bootstrap_means(np.full(32, 4.0), n_resamples=200)
    np.testing.assert_allclose(draws, 4.0)


def test_nans_are_dropped_before_resampling() -> None:
    with_nan = np.array([5.0, np.nan, 5.0, 5.0, np.nan, 5.0])
    np.testing.assert_allclose(block_bootstrap_means(with_nan, n_resamples=100), 5.0)


def test_a_series_shorter_than_one_block_returns_no_draws() -> None:
    """Mirrors `block_bootstrap_ci`'s `(nan, nan)` degenerate case."""
    assert block_bootstrap_means(np.array([1.0]), block=2).size == 0


def test_a_block_length_of_one_is_the_iid_bootstrap() -> None:
    """The block bootstrap must reduce to ordinary resampling at block = 1 -- the property that
    makes `BLOCK_LENGTH = 2` the shortest choice that is still a block bootstrap."""
    series = np.arange(1.0, 33.0)
    rng = np.random.default_rng(0)
    expected = np.array([series[rng.integers(0, 32, size=32)].mean() for _ in range(200)])
    np.testing.assert_allclose(block_bootstrap_means(series, block=1, n_resamples=200, seed=0), expected)


def test_the_default_block_length_is_the_measured_choice() -> None:
    """`DESIGN.MD` §7.7 left this undetermined pending real data; `verdict.BLOCK_LENGTH`'s
    docstring records the measurement it was chosen from."""
    assert BLOCK_LENGTH == 2


@pytest.mark.parametrize("bad", [0, -1])
def test_a_nonpositive_block_length_is_rejected(bad: int) -> None:
    with pytest.raises(ValueError, match="block must be"):
        block_bootstrap_means(np.arange(10.0), block=bad)


# ---------------------------------------------------------------------------
# One-sided p-value -- H0: mean regret <= 0
# ---------------------------------------------------------------------------


def test_an_obviously_positive_series_gives_a_tiny_p_value() -> None:
    p = one_sided_p_value(block_bootstrap_means(np.full(32, 10.0) + np.arange(32) * 0.01))
    assert p < 0.001


def test_an_all_zero_series_does_not_reject() -> None:
    """Every draw is exactly 0, so every draw is in the `<= 0` tail: p = 1."""
    assert one_sided_p_value(block_bootstrap_means(np.zeros(32))) == pytest.approx(1.0)


def test_an_obviously_negative_series_does_not_reject() -> None:
    assert one_sided_p_value(block_bootstrap_means(np.full(32, -10.0))) == pytest.approx(1.0)


def test_a_series_centred_on_zero_gives_a_p_value_near_one_half() -> None:
    rng = np.random.default_rng(3)
    p = one_sided_p_value(block_bootstrap_means(rng.normal(0.0, 5.0, 32), n_resamples=5000))
    assert 0.2 < p < 0.8


def test_the_p_value_uses_the_plug_in_and_is_never_exactly_zero() -> None:
    """`(1 + k) / (1 + n)` with k = 0 -- no finite draw count is infinitely significant."""
    assert one_sided_p_value(np.full(999, 1.0)) == pytest.approx(1 / 1000)


def test_an_empty_draw_array_gives_nan() -> None:
    assert np.isnan(one_sided_p_value(np.empty(0)))


def test_the_reported_interval_brackets_the_mean_of_a_favourable_series() -> None:
    lo, hi = percentile_ci(block_bootstrap_means(np.full(32, 8.0) + np.arange(32) * 0.1))
    assert 0.0 < lo < hi


# ---------------------------------------------------------------------------
# Holm-Bonferroni step-down
# ---------------------------------------------------------------------------


def test_holm_reproduces_the_hand_computed_step_down() -> None:
    """m = 3: the smallest p is multiplied by 3, the next by 2, the largest by 1, then made
    monotone non-decreasing."""
    p_adj, reject = holm_bonferroni([0.01, 0.02, 0.04])
    np.testing.assert_allclose(p_adj, [0.03, 0.04, 0.04])
    np.testing.assert_array_equal(reject, [True, True, True])


def test_holm_enforces_monotonicity_so_a_later_step_cannot_undercut_an_earlier_one() -> None:
    """Raw step values are 0.03 and 0.02; the second must be lifted to 0.03, not reported below
    the first."""
    p_adj, _ = holm_bonferroni([0.01, 0.01, 0.5])
    np.testing.assert_allclose(p_adj, [0.03, 0.03, 0.5])


def test_holm_stops_at_the_first_failure() -> None:
    """Step-down: once a step fails, nothing above it can be rejected either.

    Sorted, the steps are 0.001*3 = 0.003 (rejects), 0.03*2 = 0.06 (fails), 0.04*1 = 0.04 -- which
    on its own would clear alpha. Monotonicity lifts it to 0.06, so it does not. That carrying-up
    is the step-down, and a naive per-step comparison would wrongly reject here.
    """
    p_adj, reject = holm_bonferroni([0.001, 0.03, 0.04])
    np.testing.assert_allclose(p_adj, [0.003, 0.06, 0.06])
    np.testing.assert_array_equal(reject, [True, False, False])


def test_holm_preserves_input_order() -> None:
    p_adj, reject = holm_bonferroni([0.04, 0.01, 0.02])
    np.testing.assert_allclose(p_adj, [0.04, 0.03, 0.04])
    np.testing.assert_array_equal(reject, [True, True, True])


def test_holm_has_equal_or_greater_power_than_plain_bonferroni() -> None:
    """`METRIC.md` §2.1 step 3's stated reason for choosing Holm over Bonferroni."""
    p_values = np.array([0.004, 0.02, 0.04])
    p_adj, _ = holm_bonferroni(p_values)
    assert np.all(p_adj <= np.clip(p_values * p_values.size, 0.0, 1.0))
    assert np.any(p_adj < np.clip(p_values * p_values.size, 0.0, 1.0))


def test_holm_clips_to_the_unit_interval() -> None:
    p_adj, reject = holm_bonferroni([0.5, 0.6, 0.9])
    assert p_adj.max() <= 1.0
    assert not reject.any()


def test_holm_on_an_empty_family_returns_empty_arrays() -> None:
    p_adj, reject = holm_bonferroni([])
    assert p_adj.size == 0 and reject.size == 0


@pytest.mark.parametrize("bad", [[np.nan, 0.1], [-0.1, 0.1], [0.1, 1.5]])
def test_holm_rejects_malformed_p_values(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        holm_bonferroni(bad)


# ---------------------------------------------------------------------------
# Leg descriptives and the conjunctive reduction
# ---------------------------------------------------------------------------


def test_a_legs_descriptives_are_of_the_series_not_of_the_draws() -> None:
    series = np.array([1.0, 2.0, 3.0, 4.0, np.nan])
    _, stats = leg_statistics(series, n_resamples=200)
    assert stats["n"] == 4  # the NaN gameweek is not an observation
    assert stats["mean"] == pytest.approx(2.5)
    assert stats["std"] == pytest.approx(np.std([1.0, 2.0, 3.0, 4.0], ddof=1))


def test_pass_requires_all_three_legs_to_reject() -> None:
    strong = np.full(32, 12.0) + np.arange(32) * 0.01
    result = verdict({"vs_C1": strong, "vs_C2": strong + 1.0, "vs_C3": strong + 2.0}, n_resamples=2000)
    assert result.passed
    assert all(leg.rejected for leg in result.legs)
    assert [leg.name for leg in result.legs] == ["vs_C1", "vs_C2", "vs_C3"]


def test_one_unrejected_leg_fails_the_whole_verdict() -> None:
    """`METRIC.md` §2.2: beating two baselines comfortably is not a PASS, and the report must
    still show which leg fell short."""
    strong = np.full(32, 12.0) + np.arange(32) * 0.01
    result = verdict({"vs_C1": strong, "vs_C2": strong, "vs_C3": np.zeros(32)}, n_resamples=2000)
    assert not result.passed
    failed = [leg.name for leg in result.legs if not leg.rejected]
    assert failed == ["vs_C3"]


def test_a_family_of_all_null_series_fails() -> None:
    result = verdict({f"vs_C{i}": np.zeros(32) for i in (1, 2, 3)}, n_resamples=500)
    assert not result.passed
    assert not any(leg.rejected for leg in result.legs)


def test_an_empty_family_is_not_a_vacuous_pass() -> None:
    """A conjunctive rule about clearing the baselines cannot be satisfied by clearing none."""
    assert not verdict({}).passed


def test_each_leg_carries_its_own_n() -> None:
    """`METRIC.md` §2.3's instruction: the per-leg n is reported, not assumed shared."""
    result = verdict(
        {"full": np.full(32, 5.0), "short": np.full(29, 5.0)},
        n_resamples=200,
    )
    assert {leg.name: leg.n for leg in result.legs} == {"full": 32, "short": 29}


def test_the_verdict_reports_the_family_wise_alpha_it_was_decided_at() -> None:
    result = verdict({"vs_C1": np.zeros(32)}, n_resamples=200)
    assert result.alpha == FAMILY_WISE_ALPHA == 0.05


def test_the_verdict_is_deterministic() -> None:
    fam = {"vs_C1": np.arange(32.0) - 8.0, "vs_C2": np.arange(32.0) - 4.0}
    first = verdict(fam, n_resamples=1000)
    second = verdict(fam, n_resamples=1000)
    assert [(leg.name, leg.p_value, leg.p_adjusted) for leg in first.legs] == [
        (leg.name, leg.p_value, leg.p_adjusted) for leg in second.legs
    ]
