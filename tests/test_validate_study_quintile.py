"""Direct unit tests for _stratify_by_quintile() computation in all four validate studies.

The qualification gate tests (test_validate_study_classify.py) consume pre-built quintile
dicts and verify the decision-relevance logic in the gate function. These tests exercise
_stratify_by_quintile() directly to protect the gap/monotonicity computation — especially
the fixture-family bidirectional monotonicity path.

decision_relevant is computed in the study's gate function (_apply_signal_qualification_gates),
not by the kernel. These tests verify the kernel outputs (q5_q1_gap, is_monotonic) that the
gate function uses to derive the decision.

All tests use synthetic DataFrames; no database dependency.
"""

from __future__ import annotations

import pandas as pd
import pytest

from research.families.availability.validate.study import _stratify_by_quintile as avail_quintile
from research.families.fixture.validate.study import _stratify_by_quintile as fixture_quintile
from research.families.form.validate.study import _stratify_by_quintile as form_quintile
from research.families.market.validate.study import _stratify_by_quintile as market_quintile
from research.kernels.hypothesis.stratification import quintile_stratification


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
    """Non-monotonic: target peaks in the middle quintile (inverted-V shape)."""
    signal = list(range(n))
    mid = n // 2
    target = [float(i) if i <= mid else float(n - i) for i in range(n)]
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
# FORM study — unidirectional, target = total_points_next_gw
# ===========================================================================

class TestFormQuintile:

    def test_increasing_signal_is_monotonic(self):
        df = _df_increasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["q5_q1_gap"] > 1.0

    def test_decreasing_signal_is_not_monotonic(self):
        df = _df_decreasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert result["is_monotonic"] is False

    def test_inverted_v_signal_is_not_monotonic(self):
        df = _df_inverted_v()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert result["is_monotonic"] is False

    def test_small_gap_below_standard_threshold(self):
        # Increasing but tiny gap (target range much less than 1.0)
        df = pd.DataFrame({
            "sig": list(range(100)),
            "total_points_next_gw": [i * 0.005 for i in range(100)],
        })
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["q5_q1_gap"] < 1.0  # gate function will reject this

    def test_large_gap_above_standard_threshold(self):
        df = _df_increasing(100)
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert result["q5_q1_gap"] > 1.0  # gate function will accept this

    def test_insufficient_n_returns_none(self):
        df = _df_increasing(20)
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is None

    def test_nulls_dropped_before_quintile(self):
        df = _df_with_nulls(100)
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None

    def test_output_schema(self):
        df = _df_increasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        required = {
            "signal_id", "signal", "position", "block", "target",
            "q1_mean", "q2_mean", "q3_mean", "q4_mean", "q5_mean",
            "q5_q1_gap", "is_monotonic",
        }
        assert required == set(result.keys())

    def test_gap_equals_q5_minus_q1(self):
        df = _df_increasing()
        result = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert abs(result["q5_q1_gap"] - (result["q5_mean"] - result["q1_mean"])) < 1e-6


# ===========================================================================
# MARKET study — unidirectional, target = total_points_next_gw
# ===========================================================================

class TestMarketQuintile:

    def test_increasing_signal_is_monotonic(self):
        df = _df_increasing()
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True

    def test_decreasing_not_monotonic(self):
        df = _df_decreasing()
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is False

    def test_insufficient_n_returns_none(self):
        df = _df_increasing(24)
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is None

    def test_exactly_25_rows_returns_result(self):
        df = _df_increasing(25)
        result = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        assert result is not None


# ===========================================================================
# AVAILABILITY study — unidirectional, target parameterised
# ===========================================================================

class TestAvailQuintile:

    def test_increasing_binary_target_has_positive_gap(self):
        df = pd.DataFrame({
            "sig": list(range(100)),
            "played_next_gw": [float(i >= 50) for i in range(100)],
        })
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw")
        assert result is not None
        assert result["is_monotonic"] is True
        assert result["q5_q1_gap"] > 0.10  # gate will accept (primary threshold = 0.10)

    def test_tiny_binary_gap_below_primary_threshold(self):
        rng = list(range(100))
        target = [0.50 + i * 0.0005 for i in rng]
        df = pd.DataFrame({"sig": rng, "played_next_gw": target})
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw")
        assert result is not None
        assert result["q5_q1_gap"] < 0.10  # gate will reject

    def test_target_column_parameter_respected(self):
        df = pd.DataFrame({
            "sig": list(range(100)),
            "total_points_next_gw": [float(i) for i in range(100)],
        })
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "total_points_next_gw")
        assert result is not None
        assert result["q5_q1_gap"] > 1.0

    def test_decreasing_unidirectional_not_monotonic(self):
        df = _df_decreasing(100, "played_next_gw")
        result = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw")
        assert result is not None
        assert result["is_monotonic"] is False


# ===========================================================================
# FIXTURE study — BIDIRECTIONAL monotonicity, target = total_points
# ===========================================================================

class TestFixtureQuintile:

    def test_increasing_signal_is_monotonic(self):
        df = _df_increasing(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True

    def test_decreasing_signal_is_monotonic_bidirectionally(self):
        """fdr_avg case: negative association must be accepted as monotone."""
        df = _df_decreasing(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True       # bidirectional: decreasing accepted
        assert result["q5_q1_gap"] < 0              # raw gap is negative
        assert abs(result["q5_q1_gap"]) > 1.0       # gate uses abs(gap) >= threshold

    def test_inverted_v_not_monotonic_in_any_direction(self):
        df = _df_inverted_v(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is False

    def test_decreasing_tiny_range_below_threshold(self):
        signal = list(range(100))
        target = [5.0 - i * 0.005 for i in range(100)]
        df = pd.DataFrame({"sig": signal, "total_points": target})
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True
        assert abs(result["q5_q1_gap"]) < 1.0       # gate will reject

    def test_target_column_is_same_gw_total_points(self):
        df = _df_increasing(100, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["is_monotonic"] is True

    def test_insufficient_n_returns_none(self):
        df = _df_increasing(20, "total_points")
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is None

    def test_large_negative_gap_abs_value_above_threshold(self):
        signal = list(range(100))
        target = [10.0 - i * 0.1 for i in range(100)]
        df = pd.DataFrame({"sig": signal, "total_points": target})
        result = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        assert result is not None
        assert result["q5_q1_gap"] < -1.0           # raw gap strongly negative
        assert result["is_monotonic"] is True        # monotone decreasing
        assert abs(result["q5_q1_gap"]) > 1.0        # gate uses abs(gap)


# ===========================================================================
# Kernel parity — quintile_stratification matches all per-study variants
# ===========================================================================

class TestKernelParity:
    """Verify that quintile_stratification() produces identical results to each
    study's _stratify_by_quintile() on the same inputs, across all behavioral variants."""

    def _study_parity_fields(self, study: dict | None, kernel: dict | None) -> None:
        assert (study is None) == (kernel is None)
        if study is None:
            return
        parity_keys = {
            "signal_id", "signal", "position", "block",
            "q1_mean", "q2_mean", "q3_mean", "q4_mean", "q5_mean",
            "q5_q1_gap", "is_monotonic",
        }
        for k in parity_keys:
            assert study[k] == kernel[k], f"Mismatch on {k!r}: study={study[k]!r}, kernel={kernel[k]!r}"

    def test_form_parity_increasing(self):
        df = _df_increasing()
        study = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        kernel = quintile_stratification(
            df, "sig", "FORM-001", "DEF", "full",
            target="total_points_next_gw", bidirectional=False,
        )
        self._study_parity_fields(study, kernel)
        assert kernel["target"] == "total_points_next_gw"

    def test_form_parity_inverted_v(self):
        df = _df_inverted_v()
        study = form_quintile(df, "sig", "FORM-001", "DEF", "full", "total_points_next_gw")
        kernel = quintile_stratification(
            df, "sig", "FORM-001", "DEF", "full",
            target="total_points_next_gw", bidirectional=False,
        )
        self._study_parity_fields(study, kernel)

    def test_market_parity_increasing(self):
        df = _df_increasing()
        study = market_quintile(df, "sig", "MARKET-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "MARKET-001", "DEF", "full",
            target="total_points_next_gw", bidirectional=False,
        )
        self._study_parity_fields(study, kernel)

    def test_availability_parity_binary_target(self):
        df = pd.DataFrame({
            "sig": list(range(100)),
            "played_next_gw": [float(i >= 50) for i in range(100)],
        })
        study = avail_quintile(df, "sig", "AVAIL-001", "DEF", "full", "played_next_gw")
        kernel = quintile_stratification(
            df, "sig", "AVAIL-001", "DEF", "full",
            target="played_next_gw", bidirectional=False,
        )
        assert study == kernel

    def test_fixture_parity_increasing(self):
        df = _df_increasing(100, "total_points")
        study = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FIXTURE-001", "DEF", "full",
            target="total_points", bidirectional=True,
        )
        self._study_parity_fields(study, kernel)

    def test_fixture_parity_decreasing(self):
        df = _df_decreasing(100, "total_points")
        study = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FIXTURE-001", "DEF", "full",
            target="total_points", bidirectional=True,
        )
        self._study_parity_fields(study, kernel)

    def test_fixture_parity_inverted_v(self):
        df = _df_inverted_v(100, "total_points")
        study = fixture_quintile(df, "sig", "FIXTURE-001", "DEF", "full")
        kernel = quintile_stratification(
            df, "sig", "FIXTURE-001", "DEF", "full",
            target="total_points", bidirectional=True,
        )
        self._study_parity_fields(study, kernel)

    def test_kernel_returns_none_for_insufficient_n(self):
        df = _df_increasing(20)
        result = quintile_stratification(
            df, "sig", "FORM-001", "DEF", "full",
            target="total_points_next_gw", bidirectional=False,
        )
        assert result is None
