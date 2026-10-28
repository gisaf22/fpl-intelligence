"""Tests for `verdict.py`: Stage 5's primary-statistic verdict on a plain manager-week table (#60 L).

The one function both the power lab and the real Stage 5 run call. AC14 and AC15 are proposed on
#60 (the crossed-bootstrap arithmetic and P6's near-threshold re-run had no AC).
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import verdict
from research.kernels.hypothesis import multiplicity

pytestmark = pytest.mark.unit


def _table(outcomes: Mapping[tuple[int, int], float], bands: Mapping[int, str | None]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"manager_id": m, "gameweek": g, "outcome": y, "band": bands[m]} for (m, g), y in sorted(outcomes.items())]
    )


def _mixed_table(n_managers: int = 30, n_gameweeks: int = 5, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    bands = {m: ("top", "middle", "bottom")[m % 3] for m in range(n_managers)}
    outcomes = {
        (m, g): float(rng.choice([0.0, 0.5, 1.0])) for m in range(n_managers) for g in range(4, 4 + n_gameweeks)
    }
    return _table(outcomes, bands)


@pytest.mark.covers("#60 AC13")
def test_the_verdict_takes_a_plain_manager_week_table_and_returns_four_holm_adjusted_tests() -> None:
    result = verdict.primary_verdict(_mixed_table(), n_resamples=500, seed=0, rerun_resamples=1_000, rerun_seed=1)

    assert list(result.groups) == ["overall", "top", "middle", "bottom"]
    adjusted = multiplicity.holm_bonferroni(result.p_raw, alpha=verdict.FAMILY_WISE_ALPHA)
    assert np.array_equal(result.reject, adjusted["reject"])
    assert np.allclose(result.p_adj, adjusted["p_adj"])


@pytest.mark.covers("#60 AC13")
def test_the_verdict_holm_is_the_research_kernel_itself_not_a_copy() -> None:
    assert verdict.holm_bonferroni is multiplicity.holm_bonferroni


@pytest.mark.covers("#60 AC13")
@pytest.mark.parametrize("bad", [0.25, 2.0, float("nan")])
def test_an_outcome_other_than_win_tie_or_loss_is_refused(bad: float) -> None:
    table = _mixed_table()
    table.loc[0, "outcome"] = bad
    with pytest.raises(ValueError, match="outcome"):
        verdict.primary_verdict(table, n_resamples=100, seed=0, rerun_resamples=200, rerun_seed=1)


@pytest.mark.covers("#60 AC14")
def test_a_manager_week_counts_once_for_every_pairing_of_its_manager_and_gameweek_draws() -> None:
    # Two managers x two gameweeks; manager 1 drawn twice, gameweek 5 drawn twice.
    table = _table({(1, 4): 1.0, (1, 5): 0.0, (2, 4): 0.5, (2, 5): 1.0}, {1: "top", 2: "bottom"})
    shares = verdict.crossed_share(table, manager_counts={1: 2, 2: 0}, gameweek_counts={4: 0, 5: 2})
    # Only (1, 5) survives, weighted 2 x 2: share 0.0 overall and in its band; band "bottom" is empty.
    assert shares["overall"] == 0.0
    assert shares["top"] == 0.0
    assert np.isnan(shares["bottom"])

    shares = verdict.crossed_share(table, manager_counts={1: 1, 2: 2}, gameweek_counts={4: 1, 5: 1})
    # Weights: manager 1 rows x1, manager 2 rows x2 -> (1 + 0 + 2 * 0.5 + 2 * 1) / 6.
    assert shares["overall"] == pytest.approx(4.0 / 6.0)


@pytest.mark.covers("#60 AC14")
def test_the_two_sided_p_value_uses_the_one_plus_k_over_one_plus_b_convention() -> None:
    draws = np.array([0.40, 0.55, 0.60, 0.62, 0.70, 0.71, 0.72, 0.80, 0.81])  # B = 9, one draw at or below 0.5
    assert verdict.two_sided_p(draws) == pytest.approx(2 * (1 + 1) / (1 + 9))
    assert verdict.two_sided_p(np.full(9, 0.9)) == pytest.approx(2 * 1 / 10)
    assert verdict.two_sided_p(np.full(9, 0.5)) == 1.0  # clipped


@pytest.mark.covers("#60 AC15")
@pytest.mark.parametrize(
    ("p_raw", "expected"),
    [
        # Sorted ranks get thresholds 0.0125, 0.0167, 0.025, 0.05; SE at B=10,000 is sqrt(p(1-p)/B).
        ([0.0130, 0.30, 0.40, 0.50], True),  # 0.0130 is within 2 SE (~0.0023) of 0.0125
        ([0.0200, 0.30, 0.40, 0.50], False),  # 0.0200 is 3+ SE from 0.0125
        ([0.0010, 0.0160, 0.40, 0.50], True),  # second-ranked 0.0160 is near its own threshold 0.0167
        ([0.0010, 0.0020, 0.0030, 0.0510], True),  # largest is near 0.05
    ],
)
def test_a_raw_p_within_two_standard_errors_of_its_own_holm_threshold_triggers_the_rerun(
    p_raw: list[float], expected: bool
) -> None:
    assert verdict.needs_rerun(np.array(p_raw), n_resamples=10_000, alpha=0.05) is expected


@pytest.mark.covers("#60 AC15")
@pytest.mark.parametrize("near_threshold", [True, False])
def test_the_rerun_replaces_the_first_result_under_the_second_seed(
    monkeypatch: pytest.MonkeyPatch, near_threshold: bool
) -> None:
    table = _mixed_table()
    monkeypatch.setattr(verdict, "needs_rerun", lambda p_raw, *, n_resamples, alpha: near_threshold)

    result = verdict.primary_verdict(table, n_resamples=200, seed=0, rerun_resamples=400, rerun_seed=1)

    expected = (
        verdict.raw_p_values(table, n_resamples=400, seed=1)
        if near_threshold
        else verdict.raw_p_values(table, n_resamples=200, seed=0)
    )
    assert result.rerun is near_threshold
    assert np.array_equal(result.p_raw, expected)
