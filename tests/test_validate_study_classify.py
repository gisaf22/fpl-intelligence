"""Unit tests for _apply_signal_qualification_gates() in all four validate studies.

Each study's _apply_signal_qualification_gates() produces lens_status flowing into
evidence.yaml and governance. A bug in the gate sequence would propagate silently
into ratified artifacts. These tests verify correct verdict for each distinct gate
outcome (Gate 1: CI, Gate 2: decision relevance, Gate 3: GW-window stability).

All tests use synthetic dicts — no database dependency.
"""

import pytest

from research.families.form.validate.study import _apply_signal_qualification_gates as form_qualify
from research.families.availability.validate.study import _apply_signal_qualification_gates as avail_qualify
from research.families.market.validate.study import _apply_signal_qualification_gates as market_qualify
from research.families.fixture.validate.study import _apply_signal_qualification_gates as fixture_qualify


# ---------------------------------------------------------------------------
# Helpers — synthetic input builders
# ---------------------------------------------------------------------------

def _corr(rho: float, ci_lo: float, ci_hi: float, n: int = 200) -> dict:
    return {
        "rho": rho,
        "ci_lower": ci_lo,
        "ci_upper": ci_hi,
        "n": n,
        "ci_excludes_zero": bool(ci_lo > 0 or ci_hi < 0),
    }


def _quint(gap: float, monotonic: bool) -> dict:
    return {
        "q1_mean": 2.0, "q2_mean": 2.5, "q3_mean": 3.0, "q4_mean": 3.5,
        "q5_mean": 2.0 + gap,
        "q5_q1_gap": gap,
        "is_monotonic": monotonic,
    }


def _quint_avail(gap: float, monotonic: bool) -> dict:
    return {
        "q1_mean": 0.60, "q2_mean": 0.65, "q3_mean": 0.70, "q4_mean": 0.75,
        "q5_mean": 0.60 + gap,
        "q5_q1_gap": gap,
        "is_monotonic": monotonic,
    }


def _blocks_passing(n: int) -> list:
    """Return 3 block records where n of them have ci_excludes_zero=True."""
    blocks = []
    for i in range(3):
        if i < n:
            blocks.append(_corr(0.15, 0.05, 0.25))
        else:
            blocks.append(_corr(0.05, -0.05, 0.15))
    return blocks


BASE = ("xgi_roll3", "FORM-001", "DEF")


# ===========================================================================
# FORM study
# ===========================================================================

class TestFormClassify:

    def test_insufficient_observations_returns_uninformative(self):
        result = form_qualify(None, None, [], *BASE, naive_rho=None)
        assert result["lens_status"] == "uninformative"
        assert "insufficient" in result["rationale"]

    def test_ci_crosses_zero_returns_uninformative(self):
        corr = _corr(0.05, -0.03, 0.13)
        result = form_qualify(corr, None, [], *BASE, naive_rho=None)
        assert result["lens_status"] == "uninformative"
        assert "CI crosses zero" in result["rationale"]

    def test_gate2_fail_no_quint_returns_uninformative(self):
        corr = _corr(0.15, 0.05, 0.25)  # CI excludes zero
        result = form_qualify(corr, None, [], *BASE, naive_rho=None)
        assert result["lens_status"] == "uninformative"
        assert "decision relevance" in result["rationale"]

    def test_gate2_fail_gap_too_small_returns_uninformative(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=0.5, monotonic=True)  # gap < 1.0 threshold
        result = form_qualify(corr, quint, [], *BASE, naive_rho=None)
        assert result["lens_status"] == "uninformative"

    def test_gate2_fail_non_monotonic_returns_uninformative(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=2.0, monotonic=False)  # gap passes but non-monotonic
        result = form_qualify(corr, quint, [], *BASE, naive_rho=None)
        assert result["lens_status"] == "uninformative"

    def test_all_gates_pass_2_blocks_returns_informative(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(2)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=None)
        assert result["lens_status"] == "informative"
        assert "2/3" in result["rationale"]

    def test_all_gates_pass_3_blocks_returns_informative(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(3)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=None)
        assert result["lens_status"] == "informative"
        assert "3/3" in result["rationale"]

    def test_gate3_fail_1_block_returns_unstable(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(1)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=None)
        assert result["lens_status"] == "unstable"
        assert "1/3" in result["rationale"]

    def test_gate3_fail_0_blocks_returns_unstable(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(0)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=None)
        assert result["lens_status"] == "unstable"

    def test_naive_rho_clears_baseline_true(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(2)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=0.10)
        assert result["clears_naive_baseline"] is True

    def test_naive_rho_clears_baseline_false(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(2)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=0.20)
        assert result["clears_naive_baseline"] is False

    def test_naive_rho_none_gives_none_baseline(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(2)
        result = form_qualify(corr, quint, blocks, *BASE, naive_rho=None)
        assert result["clears_naive_baseline"] is None

    def test_base_keys_always_present(self):
        result = form_qualify(None, None, [], *BASE, naive_rho=None)
        assert result["signal"] == "xgi_roll3"
        assert result["signal_id"] == "FORM-001"
        assert result["position"] == "DEF"


# ===========================================================================
# AVAIL study
# ===========================================================================

AVAIL_BASE = ("minutes_roll3", "AVAIL-001", "DEF")


class TestAvailClassify:

    def test_insufficient_observations(self):
        result = avail_qualify(None, None, [], *AVAIL_BASE)
        assert result["lens_status"] == "uninformative"

    def test_ci_crosses_zero(self):
        corr = _corr(0.05, -0.03, 0.13)
        result = avail_qualify(corr, None, [], *AVAIL_BASE)
        assert result["lens_status"] == "uninformative"
        assert "CI crosses zero" in result["rationale"]

    def test_gate2_fail_gap_below_binary_threshold(self):
        # Binary target: gap threshold is 0.10
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint_avail(gap=0.05, monotonic=True)  # gap < 0.10
        result = avail_qualify(corr, quint, [], *AVAIL_BASE)
        assert result["lens_status"] == "uninformative"

    def test_gate2_pass_binary_threshold(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint_avail(gap=0.12, monotonic=True)  # gap >= 0.10
        blocks = _blocks_passing(2)
        result = avail_qualify(corr, quint, blocks, *AVAIL_BASE)
        assert result["lens_status"] == "informative"

    def test_informative_verdict(self):
        corr = _corr(0.20, 0.10, 0.30)
        quint = _quint_avail(gap=0.15, monotonic=True)
        blocks = _blocks_passing(3)
        result = avail_qualify(corr, quint, blocks, *AVAIL_BASE)
        assert result["lens_status"] == "informative"

    def test_unstable_verdict(self):
        corr = _corr(0.20, 0.10, 0.30)
        quint = _quint_avail(gap=0.15, monotonic=True)
        blocks = _blocks_passing(1)
        result = avail_qualify(corr, quint, blocks, *AVAIL_BASE)
        assert result["lens_status"] == "unstable"

    def test_no_quint_with_ci_passing(self):
        corr = _corr(0.20, 0.10, 0.30)
        result = avail_qualify(corr, None, [], *AVAIL_BASE)
        assert result["lens_status"] == "uninformative"
        assert "N/A" in result["rationale"]


# ===========================================================================
# MARKET study
# ===========================================================================

MARKET_BASE = ("transfers_in", "MARKET-001", "DEF")


class TestMarketClassify:

    def test_insufficient_observations(self):
        result = market_qualify(None, None, [], *MARKET_BASE)
        assert result["lens_status"] == "uninformative"

    def test_ci_crosses_zero(self):
        corr = _corr(0.05, -0.03, 0.13)
        result = market_qualify(corr, None, [], *MARKET_BASE)
        assert result["lens_status"] == "uninformative"

    def test_gate2_fail_non_monotonic(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=False)
        result = market_qualify(corr, quint, [], *MARKET_BASE)
        assert result["lens_status"] == "uninformative"

    def test_informative_verdict(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(2)
        result = market_qualify(corr, quint, blocks, *MARKET_BASE)
        assert result["lens_status"] == "informative"

    def test_unstable_verdict(self):
        corr = _corr(0.15, 0.05, 0.25)
        quint = _quint(gap=1.5, monotonic=True)
        blocks = _blocks_passing(1)
        result = market_qualify(corr, quint, blocks, *MARKET_BASE)
        assert result["lens_status"] == "unstable"

    def test_negative_ci_excluded_zero_uninformative_without_quint(self):
        corr = _corr(-0.15, -0.25, -0.05)  # CI excludes zero on negative side
        result = market_qualify(corr, None, [], *MARKET_BASE)
        assert result["lens_status"] == "uninformative"

    def test_base_keys_always_present(self):
        result = market_qualify(None, None, [], *MARKET_BASE)
        assert result["signal"] == "transfers_in"
        assert result["signal_id"] == "MARKET-001"
        assert result["position"] == "DEF"


# ===========================================================================
# FIXTURE study — includes bidirectional monotonicity tests
# ===========================================================================

FIXTURE_BASE = ("fdr_avg", "FIXTURE-001", "DEF")
FIXTURE_POS_BASE = ("was_home", "FIXTURE-002", "DEF")


def _quint_fixture_negative(gap: float) -> dict:
    """Quintile dict for a signal with negative rho (fdr_avg): Q1 highest, Q5 lowest."""
    # gap = means[4] - means[0] will be negative; abs_gap = |gap|
    base_mean = 5.0
    return {
        "q1_mean": base_mean,
        "q2_mean": base_mean - 0.5,
        "q3_mean": base_mean - 1.0,
        "q4_mean": base_mean - 1.5,
        "q5_mean": base_mean + gap,  # gap is negative, so q5 < q1
        "q5_q1_gap": gap,
        "is_monotonic": True,        # bidirectional: monotone decreasing
    }


class TestFixtureClassify:

    def test_insufficient_observations(self):
        result = fixture_qualify(None, None, [], *FIXTURE_BASE)
        assert result["lens_status"] == "uninformative"

    def test_ci_crosses_zero(self):
        corr = _corr(0.05, -0.03, 0.13)
        result = fixture_qualify(corr, None, [], *FIXTURE_BASE)
        assert result["lens_status"] == "uninformative"

    def test_positive_rho_informative(self):
        # was_home: positive association
        corr = _corr(0.10, 0.02, 0.18)
        quint = _quint(gap=1.2, monotonic=True)
        blocks = _blocks_passing(2)
        result = fixture_qualify(corr, quint, blocks, *FIXTURE_POS_BASE)
        assert result["lens_status"] == "informative"

    def test_negative_rho_informative_with_bidirectional_monotone(self):
        # fdr_avg: negative rho, monotone decreasing
        corr = _corr(-0.15, -0.25, -0.05)  # CI excludes zero on negative side
        quint = _quint_fixture_negative(gap=-1.5)  # decision_relevant = True (abs=1.5 >= 1.0)
        blocks = [_corr(-0.15, -0.25, -0.05), _corr(-0.15, -0.25, -0.05), _corr(0.05, -0.05, 0.15)]
        result = fixture_qualify(corr, quint, blocks, *FIXTURE_BASE)
        assert result["lens_status"] == "informative"

    def test_negative_rho_uninformative_when_gap_too_small(self):
        corr = _corr(-0.10, -0.20, -0.01)
        quint = _quint_fixture_negative(gap=-0.5)  # abs_gap=0.5 < 1.0 threshold
        blocks = _blocks_passing(0)
        result = fixture_qualify(corr, quint, blocks, *FIXTURE_BASE)
        assert result["lens_status"] == "uninformative"

    def test_unstable_verdict(self):
        corr = _corr(0.10, 0.02, 0.18)
        quint = _quint(gap=1.2, monotonic=True)
        blocks = _blocks_passing(1)
        result = fixture_qualify(corr, quint, blocks, *FIXTURE_POS_BASE)
        assert result["lens_status"] == "unstable"

    def test_gate2_fail_non_monotonic(self):
        corr = _corr(0.10, 0.02, 0.18)
        quint = _quint(gap=1.5, monotonic=False)
        result = fixture_qualify(corr, quint, [], *FIXTURE_POS_BASE)
        assert result["lens_status"] == "uninformative"

    def test_no_quint_with_ci_passing(self):
        corr = _corr(0.10, 0.02, 0.18)
        result = fixture_qualify(corr, None, [], *FIXTURE_POS_BASE)
        assert result["lens_status"] == "uninformative"
        assert "N/A" in result["rationale"]
