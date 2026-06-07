"""Direct unit tests for _quintile_record() computation in all four validate studies.

The classify gate tests (test_validate_study_classify.py) consume pre-built quintile
dicts and do not validate the quintile computation itself. These tests exercise
_quintile_record() directly to protect the gap/monotonicity logic — especially the
fixture-family bidirectional monotonicity path — before and after C3 consolidation.

All tests use synthetic DataFrames; no database dependency.
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.families.availability.validate.study import _quintile_record as avail_quintile
from research.families.fixture.validate.study import _quintile_record as fixture_quintile
from research.families.form.validate.study import _quintile_record as form_quintile
from research.families.market.validate.study import _quintile_record as market_quintile
from research.kernels.stratification import quintile_stratification


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------

def _df_increasing(n: int = 100, target_col: str = "total_points_next_gw") -> pd.DataFrame:
    """Perfectly monotone-increasing: higher signal → higher target."""
    signal = list(range(n))
    target = [i * 0.5 for i in range(n)]
    return pd.DataFrame({"sig": signal, target_col: target})


def _df_decreasing(n: int = 100, target_col: str = "total_points_next_gw") -> pd.DataFrame:
    """Perfectly monotone-decreasing: higher signal → lower target."""
    signal = list(range(n))
    target = [50.0 - i * 0.5 for i in range(n)]
    return pd.DataFrame({"sig": signal, target_col: target})


def _df_inverted_v(n: int = 100, target_col: str = "total_points_next_gw") -> pd.DataFrame:
    """Non-monotonic: target peaks in the middle quintile (inverted-V shape).

    With a monotonically-increasing signal, quintile means follow the shape of the
    target function. An alternating target distributes evenly across quintiles and
    produces flat (weakly-monotone) means — that is not a useful non-monotone case.
    An inverted-V target produces Q1 < Q2 < Q3 > Q4 > Q5, which fails both
    monotone-increasing and monotone-decreasing checks.
    """
    signal = list(range(n))
    mid = n / 2
    target = [10.0 - abs(i - mid) * 0.2 for i in range(n)]
    return pd.DataFrame({"sig": signal, target_col: target})


def _df_flat(n: int = 100, target_col: str = "total_points_next_gw") -> pd.DataFrame:
    """Flat signal — all same value."""
    return pd.DataFrame({"sig": [1.0] * n, target_col: [float(i) for i in range(n)]})


def _df_with_nulls(n: int = 100, target_col: str = "total_points_next_gw") -> pd.DataFrame:
    df = _df_increasing(n, target_col)
    df.loc[0, "sig"] = None
    df.loc[1, target_col] = None
    return df


# ===========================================================================
# FORM study — unidirectional, target = total_points_next_gw, threshold = 1.0
# ===========================================================================

class TestFormQuintile:

    def test_increasing_signal_is_monotonic_and_decision_relevant(self):
        df = _df_increasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["q5_q1_gap"] > 1.0
        assert result["decision_relevant"] is True

    def test_decreasing_signal_is_not_monotonic(self):
        df = _df_decreasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is False
        assert result["decision_relevant"] is False

    def test_inverted_v_signal_is_not_monotonic(self):
        df = _df_inverted_v()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is False
        assert result["decision_relevant"] is False

    def test_small_gap_fails_decision_relevance(self):
        # Increasing but tiny gap (target range much less than 1.0)
        df = pd.DataFrame({
            "sig": list(range(100)),
            "total_points_next_gw": [i * 0.005 for i in range(100)],
        })
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["decision_relevant"] is False  # gap < 1.0

    def test_sufficient_gap_passes_decision_relevance(self):
        df = _df_increasing(100)
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        assert result["decision_relevant"] is True  # gap well above 1.0

    def test_insufficient_n_returns_none(self):
        df = _df_increasing(20)
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is None

    def test_nulls_dropped_before_quintile(self):
        df = _df_with_nulls(100)
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None  # enough valid rows remain

    def test_output_schema(self):
        df = _df_increasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        required = {
            "signal_id", "signal", "position", "block", "target",
            "q1_mean", "q2_mean", "q3_mean", "q4_mean", "q5_mean",
            "q5_q1_gap", "is_monotonic", "decision_relevant",
        }
        assert required == set(result.keys())

    def test_gap_equals_q5_minus_q1(self):
        df = _df_increasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        assert result is not None
        assert abs(result["q5_q1_gap"] - (result["q5_mean"] - result["q1_mean"])) < 1e-6


# ===========================================================================
# MARKET study — unidirectional, target = total_points_next_gw, threshold = 1.0
# (structurally identical to form quintile; tests verify independence)
# ===========================================================================

class TestMarketQuintile:

    def test_increasing_signal_is_monotonic(self):
        df = _df_increasing()
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["decision_relevant"] is True

    def test_decreasing_not_monotonic(self):
        df = _df_decreasing()
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is False
        assert result["decision_relevant"] is False

    def test_insufficient_n_returns_none(self):
        df = _df_increasing(24)
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is None

    def test_exactly_25_rows_returns_result(self):
        df = _df_increasing(25)
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is not None


# ===========================================================================
# AVAILABILITY study — unidirectional, target parameterised, threshold = 0.10
# ===========================================================================

class TestAvailQuintile:

    def test_increasing_binary_target_passes_with_low_threshold(self):
        # Binary-range target [0,1]: Q5-Q1 gap of ~0.4 easily clears 0.10 threshold
        df = pd.DataFrame({
            "sig": list(range(100)),
            "played_next_gw": [float(i >= 50) for i in range(100)],
        })
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw", 0.10)
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["decision_relevant"] is True

    def test_tiny_binary_gap_fails_threshold(self):
        # Negligible gap even with increasing signal
        rng = list(range(100))
        # All values near 0.5; difference across quintiles < 0.10
        target = [0.50 + i * 0.0005 for i in rng]
        df = pd.DataFrame({"sig": rng, "played_next_gw": target})
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw", 0.10)
        assert result is not None
        # Confirm the gap is less than the threshold
        assert result["q5_q1_gap"] < 0.10
        assert result["decision_relevant"] is False

    def test_target_column_parameter_respected(self):
        df = pd.DataFrame({
            "sig": list(range(100)),
            "total_points_next_gw": [float(i) for i in range(100)],
        })
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "total_points_next_gw", 1.0)
        assert result is not None
        assert result["decision_relevant"] is True

    def test_decreasing_unidirectional_fails(self):
        df = _df_decreasing(100, "played_next_gw")
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw", 0.10)
        assert result is not None
        assert result["is_monotonic"] is False
        assert result["decision_relevant"] is False


# ===========================================================================
# FIXTURE study — BIDIRECTIONAL monotonicity, abs_gap, target = total_points
# ===========================================================================

class TestFixtureQuintile:

    def test_increasing_signal_is_monotonic(self):
        df = _df_increasing(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["decision_relevant"] is True

    def test_decreasing_signal_is_monotonic_bidirectionally(self):
        """fdr_avg case: negative association must be accepted as monotone."""
        df = _df_decreasing(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        # Bidirectional: monotone-decreasing is valid
        assert result["is_monotonic"] is True
        # abs_gap is used: Q5-Q1 is negative but abs value should exceed threshold
        assert result["q5_q1_gap"] < 0            # raw gap is negative
        assert result["decision_relevant"] is True  # abs_gap >= 1.0

    def test_inverted_v_not_monotonic_in_any_direction(self):
        """Inverted-V: Q means peak in Q3 then fall, failing both mono-up and mono-down."""
        df = _df_inverted_v(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is False
        assert result["decision_relevant"] is False

    def test_negative_gap_below_threshold_not_decision_relevant(self):
        # Decreasing but tiny range → abs_gap < 1.0
        signal = list(range(100))
        target = [5.0 - i * 0.005 for i in range(100)]  # total range = 0.495
        df = pd.DataFrame({"sig": signal, "total_points": target})
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True    # monotone-decreasing
        assert abs(result["q5_q1_gap"]) < 1.0
        assert result["decision_relevant"] is False

    def test_target_column_is_same_gw_total_points(self):
        """Fixture uses same-GW total_points (no lag), unlike form/market which use _next_gw."""
        df = _df_increasing(100, "total_points")   # column name used by fixture
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True

    def test_insufficient_n_returns_none(self):
        df = _df_increasing(20, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is None

    def test_decision_relevant_uses_abs_gap(self):
        """Explicitly verify abs_gap semantics: a large negative gap is still relevant."""
        # Build a DataFrame where Q5 << Q1 (strongly decreasing)
        signal = list(range(100))
        target = [10.0 - i * 0.1 for i in range(100)]  # Q1 ~9.5, Q5 ~0.5; gap = -9.0
        df = pd.DataFrame({"sig": signal, "total_points": target})
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["q5_q1_gap"] < -1.0          # raw gap strongly negative
        assert result["is_monotonic"] is True       # monotone decreasing
        assert result["decision_relevant"] is True   # abs_gap >> 1.0


# ===========================================================================
# Kernel parity — quintile_stratification matches all per-study variants
# ===========================================================================

class TestKernelParity:
    """Verify that quintile_stratification() produces identical results to each
    study's _quintile_record() on the same inputs, across all behavioral variants."""

    # The kernel always includes "target" in its output (it parameterises the target
    # column). The per-study _quintile_record implementations for form, fixture, and
    # market hard-code the target column and do NOT include "target" in their output
    # dict; availability does include it. Post-migration all four call sites will use
    # the kernel, so quint_rows will gain the "target" key for form/fixture/market —
    # this only affects the output CSV, not governance. Parity tests compare the
    # decision-relevant fields; the extra key is excluded for pre-migration studies.

    def _study_parity_fields(self, study: dict | None, kernel: dict | None) -> None:
        """Assert that governance-critical fields match between study and kernel."""
        assert (study is None) == (kernel is None)
        if study is None:
            return
        parity_keys = {
            "signal_id", "signal", "position", "block",
            "q1_mean", "q2_mean", "q3_mean", "q4_mean", "q5_mean",
            "q5_q1_gap", "is_monotonic", "decision_relevant",
        }
        for k in parity_keys:
            assert study[k] == kernel[k], f"Mismatch on {k!r}: study={study[k]!r}, kernel={kernel[k]!r}"

    def test_form_parity_increasing(self):
        df = _df_increasing()
        study = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FORM-001", "DEF", "full",
            target="total_points_next_gw", gap_threshold=1.0, bidirectional=False,
        )
        self._study_parity_fields(study, kernel)
        assert kernel["target"] == "total_points_next_gw"

    def test_form_parity_inverted_v(self):
        df = _df_inverted_v()
        study = form_quintile(df, "sig", "FORM-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FORM-001", "DEF", "full",
            target="total_points_next_gw", gap_threshold=1.0, bidirectional=False,
        )
        self._study_parity_fields(study, kernel)

    def test_market_parity_increasing(self):
        df = _df_increasing()
        study = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "MARKET-001", "DEF", "full",
            target="total_points_next_gw", gap_threshold=1.0, bidirectional=False,
        )
        self._study_parity_fields(study, kernel)

    def test_availability_parity_binary_target(self):
        df = pd.DataFrame({
            "sig": list(range(100)),
            "played_next_gw": [float(i >= 50) for i in range(100)],
        })
        study = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw", 0.10)
        kernel = quintile_stratification(
            df, "sig", "AVAIL-001", "DEF", "full",
            target="played_next_gw", gap_threshold=0.10, bidirectional=False,
        )
        # Availability study already includes "target" in its output — full equality holds.
        assert study == kernel

    def test_fixture_parity_increasing(self):
        df = _df_increasing(100, "total_points")
        study = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FIXTURE-001", "DEF", "full",
            target="total_points", gap_threshold=1.0, bidirectional=True,
        )
        self._study_parity_fields(study, kernel)

    def test_fixture_parity_decreasing(self):
        """Core parity test: bidirectional decreasing must match fixture study."""
        df = _df_decreasing(100, "total_points")
        study = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FIXTURE-001", "DEF", "full",
            target="total_points", gap_threshold=1.0, bidirectional=True,
        )
        self._study_parity_fields(study, kernel)

    def test_fixture_parity_inverted_v(self):
        df = _df_inverted_v(100, "total_points")
        study = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FIXTURE-001", "DEF", "full",
            target="total_points", gap_threshold=1.0, bidirectional=True,
        )
        self._study_parity_fields(study, kernel)

    def test_kernel_returns_none_for_insufficient_n(self):
        df = _df_increasing(20)
        result = quintile_stratification(
            df, "sig", "FORM-001", "DEF", "full",
            target="total_points_next_gw", gap_threshold=1.0, bidirectional=False,
        )
        assert result is None
