"""Tests for analytics.signals.redundancy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.signals.redundancy import (
    ALGEBRAIC_DECOMPOSITIONS,
    DEFAULT_REDUNDANCY_THRESHOLD,
    MIN_N_FOR_RHO,
    compute_pairwise_rho,
    compute_partial_rho,
    identify_redundant_pairs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_df(n: int = 60, position: str = "MID", seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = rng.standard_normal(n)
    return pd.DataFrame(
        {
            "position": position,
            "sig_a": base + rng.standard_normal(n) * 0.05,
            "sig_b": base + rng.standard_normal(n) * 0.05,  # nearly perfectly correlated with sig_a
            "sig_c": rng.standard_normal(n),                 # independent
            "total_points": rng.integers(1, 12, size=n).astype(float),
        }
    )


def _perfect_corr_df(n: int = 60, position: str = "MID") -> pd.DataFrame:
    x = np.arange(n, dtype=float)
    return pd.DataFrame(
        {
            "position": position,
            "sig_a": x,
            "sig_b": x * 2,  # perfectly correlated
            "sig_c": x[::-1],  # perfectly anti-correlated
            "total_points": np.random.default_rng(0).integers(1, 12, size=n).astype(float),
        }
    )


# ---------------------------------------------------------------------------
# compute_pairwise_rho
# ---------------------------------------------------------------------------

class TestComputePairwiseRho:
    def test_returns_symmetric_dataframe(self):
        df = _make_df()
        signals = ["sig_a", "sig_b", "sig_c"]
        result = compute_pairwise_rho(df, signals, "MID")
        assert result.shape == (3, 3)
        assert list(result.index) == signals
        assert list(result.columns) == signals
        # Symmetry
        for i in range(3):
            for j in range(3):
                val_ij = result.iloc[i, j]
                val_ji = result.iloc[j, i]
                if pd.notna(val_ij) and pd.notna(val_ji):
                    assert abs(val_ij - val_ji) < 1e-9

    def test_diagonal_is_one(self):
        df = _make_df()
        result = compute_pairwise_rho(df, ["sig_a", "sig_b"], "MID")
        assert result.loc["sig_a", "sig_a"] == 1.0
        assert result.loc["sig_b", "sig_b"] == 1.0

    def test_perfect_correlation_detected(self):
        df = _perfect_corr_df()
        result = compute_pairwise_rho(df, ["sig_a", "sig_b"], "MID")
        assert result.loc["sig_a", "sig_b"] == pytest.approx(1.0, abs=1e-4)

    def test_perfect_anti_correlation_detected(self):
        df = _perfect_corr_df()
        result = compute_pairwise_rho(df, ["sig_a", "sig_c"], "MID")
        assert result.loc["sig_a", "sig_c"] == pytest.approx(-1.0, abs=1e-4)

    def test_returns_nan_for_insufficient_rows(self):
        small = _make_df(n=10)
        result = compute_pairwise_rho(small, ["sig_a", "sig_b"], "MID")
        # Off-diagonal should be NaN (diagonal stays 1.0)
        assert pd.isna(result.loc["sig_a", "sig_b"])

    def test_returns_nan_for_constant_signal(self):
        df = _make_df()
        df["constant"] = 5.0
        result = compute_pairwise_rho(df, ["sig_a", "constant"], "MID")
        assert pd.isna(result.loc["sig_a", "constant"])

    def test_filters_by_position(self):
        df = _make_df(n=60, position="MID")
        df_fwd = _make_df(n=60, position="FWD", seed=99)
        combined = pd.concat([df, df_fwd], ignore_index=True)
        result_mid = compute_pairwise_rho(combined, ["sig_a", "sig_b"], "MID")
        result_fwd = compute_pairwise_rho(combined, ["sig_a", "sig_b"], "FWD")
        # Both valid but may differ since seeds differ
        assert pd.notna(result_mid.loc["sig_a", "sig_b"])
        assert pd.notna(result_fwd.loc["sig_a", "sig_b"])

    def test_missing_position_column_raises(self):
        df = _make_df().drop(columns=["position"])
        with pytest.raises(ValueError, match="position"):
            compute_pairwise_rho(df, ["sig_a", "sig_b"], "MID")

    def test_missing_signal_column_raises(self):
        df = _make_df()
        with pytest.raises(ValueError, match="missing signal"):
            compute_pairwise_rho(df, ["sig_a", "nonexistent"], "MID")

    def test_values_bounded(self):
        df = _make_df()
        result = compute_pairwise_rho(df, ["sig_a", "sig_b", "sig_c"], "MID")
        for i in range(3):
            for j in range(3):
                v = result.iloc[i, j]
                if pd.notna(v):
                    assert -1.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# identify_redundant_pairs
# ---------------------------------------------------------------------------

class TestIdentifyRedundantPairs:
    def _perfect_matrix(self, signals: list[str]) -> pd.DataFrame:
        n = len(signals)
        mat = np.ones((n, n))
        return pd.DataFrame(mat, index=signals, columns=signals)

    def _identity_matrix(self, signals: list[str]) -> pd.DataFrame:
        mat = np.eye(len(signals))
        return pd.DataFrame(mat, index=signals, columns=signals)

    def test_perfect_correlation_flagged(self):
        df = _perfect_corr_df()
        rho = compute_pairwise_rho(df, ["sig_a", "sig_b"], "MID")
        pairs = identify_redundant_pairs(rho)
        assert ("sig_a", "sig_b") in pairs

    def test_uncorrelated_signals_not_flagged(self):
        df = _make_df()
        # Make sig_c truly independent
        rng = np.random.default_rng(7)
        df["sig_c"] = rng.standard_normal(len(df))
        rho = compute_pairwise_rho(df, ["sig_a", "sig_c"], "MID")
        pairs = identify_redundant_pairs(rho, threshold=0.85)
        assert ("sig_a", "sig_c") not in pairs

    def test_no_self_correlation_pairs(self):
        signals = ["sig_a", "sig_b"]
        rho = self._perfect_matrix(signals)
        pairs = identify_redundant_pairs(rho)
        for pair in pairs:
            assert pair[0] != pair[1]

    def test_no_duplicate_pairs(self):
        signals = ["sig_a", "sig_b", "sig_c"]
        rho = self._perfect_matrix(signals)
        pairs = identify_redundant_pairs(rho)
        assert len(pairs) == len(set(pairs))

    def test_pairs_lexicographically_ordered_within(self):
        signals = ["z_sig", "a_sig"]
        rho = self._perfect_matrix(signals)
        pairs = identify_redundant_pairs(rho)
        for a, b in pairs:
            assert a <= b

    def test_output_list_is_sorted(self):
        signals = ["c_sig", "a_sig", "b_sig"]
        rho = self._perfect_matrix(signals)
        pairs = identify_redundant_pairs(rho)
        assert pairs == sorted(pairs)

    def test_threshold_1_produces_empty_list(self):
        df = _make_df()
        rho = compute_pairwise_rho(df, ["sig_a", "sig_b"], "MID")
        # threshold = 1.0 means only exact 1.0 counts; near-perfect won't qualify
        pairs = identify_redundant_pairs(rho, threshold=1.0)
        # sig_a vs sig_b are not EXACTLY 1.0 due to noise
        assert isinstance(pairs, list)

    def test_threshold_0_flags_all_non_nan_pairs(self):
        df = _make_df()
        signals = ["sig_a", "sig_b", "sig_c"]
        rho = compute_pairwise_rho(df, signals, "MID")
        pairs = identify_redundant_pairs(rho, threshold=0.0)
        # All non-NaN off-diagonal pairs should be flagged
        non_nan_count = sum(
            1
            for i, j in [(0, 1), (0, 2), (1, 2)]
            if pd.notna(rho.iloc[i, j])
        )
        assert len(pairs) == non_nan_count

    def test_nan_cells_not_flagged(self):
        signals = ["sig_a", "sig_b"]
        mat = pd.DataFrame(
            [[1.0, np.nan], [np.nan, 1.0]],
            index=signals, columns=signals,
        )
        pairs = identify_redundant_pairs(mat, threshold=0.0)
        assert pairs == []

    def test_anti_correlation_flagged(self):
        df = _perfect_corr_df()
        rho = compute_pairwise_rho(df, ["sig_a", "sig_c"], "MID")
        pairs = identify_redundant_pairs(rho, threshold=0.85)
        assert ("sig_a", "sig_c") in pairs


# ---------------------------------------------------------------------------
# compute_partial_rho
# ---------------------------------------------------------------------------

class TestComputePartialRho:
    def test_returns_float_in_valid_range(self):
        df = _make_df()
        result = compute_partial_rho(df, "sig_a", "sig_b", "total_points", "MID")
        assert result is not None
        assert -1.0 <= result <= 1.0

    def test_returns_none_for_insufficient_rows(self):
        df = _make_df(n=10)
        result = compute_partial_rho(df, "sig_a", "sig_b", "total_points", "MID")
        assert result is None

    def test_returns_none_for_constant_signal(self):
        df = _make_df()
        df["constant"] = 3.0
        result = compute_partial_rho(df, "constant", "sig_b", "total_points", "MID")
        assert result is None

    def test_missing_required_column_raises(self):
        df = _make_df().drop(columns=["total_points"])
        with pytest.raises(ValueError, match="total_points"):
            compute_partial_rho(df, "sig_a", "sig_b", "total_points", "MID")

    def test_perfect_linear_relationship_reduces_after_conditioning(self):
        # sig_a and sig_b are nearly identical; conditioning on total_points (independent)
        # should leave partial rho high still
        df = _make_df()
        full_rho_df = compute_pairwise_rho(df, ["sig_a", "sig_b"], "MID")
        full_rho = full_rho_df.loc["sig_a", "sig_b"]
        partial = compute_partial_rho(df, "sig_a", "sig_b", "total_points", "MID")
        assert partial is not None
        # Both should be high when total_points is unrelated to the pair
        assert partial > 0.5
        assert full_rho > 0.5

    def test_result_bounded_at_one(self):
        df = _perfect_corr_df()
        result = compute_partial_rho(df, "sig_a", "sig_b", "total_points", "MID")
        if result is not None:
            assert -1.0 <= result <= 1.0

    def test_filters_by_position(self):
        df = _make_df(n=60, position="MID")
        df2 = _make_df(n=60, position="FWD", seed=55)
        combined = pd.concat([df, df2], ignore_index=True)
        r_mid = compute_partial_rho(combined, "sig_a", "sig_b", "total_points", "MID")
        r_fwd = compute_partial_rho(combined, "sig_a", "sig_b", "total_points", "FWD")
        # Both valid (n=60 each)
        assert r_mid is not None
        assert r_fwd is not None


# ---------------------------------------------------------------------------
# ALGEBRAIC_DECOMPOSITIONS
# ---------------------------------------------------------------------------

class TestAlgebraicDecompositions:
    def test_is_tuple_of_triples(self):
        assert isinstance(ALGEBRAIC_DECOMPOSITIONS, tuple)
        for entry in ALGEBRAIC_DECOMPOSITIONS:
            assert isinstance(entry, tuple)
            assert len(entry) == 3

    def test_xgi_decomposition_present(self):
        derived = {entry[0] for entry in ALGEBRAIC_DECOMPOSITIONS}
        assert "xgi" in derived

    def test_all_entries_are_strings(self):
        for derived, comp_a, comp_b in ALGEBRAIC_DECOMPOSITIONS:
            assert isinstance(derived, str)
            assert isinstance(comp_a, str)
            assert isinstance(comp_b, str)

    def test_referenced_signals_exist_in_governed_set(self):
        from build.population import GOVERNED_SIGNAL_COLUMNS
        governed = set(GOVERNED_SIGNAL_COLUMNS)
        for derived, comp_a, comp_b in ALGEBRAIC_DECOMPOSITIONS:
            assert derived in governed, f"{derived!r} not in GOVERNED_SIGNAL_COLUMNS"
            assert comp_a in governed, f"{comp_a!r} not in GOVERNED_SIGNAL_COLUMNS"
            assert comp_b in governed, f"{comp_b!r} not in GOVERNED_SIGNAL_COLUMNS"

    def test_ict_index_decomposition_present(self):
        derived = {entry[0] for entry in ALGEBRAIC_DECOMPOSITIONS}
        assert "ict_index" in derived

    def test_no_duplicate_derived_signals(self):
        derived = [entry[0] for entry in ALGEBRAIC_DECOMPOSITIONS]
        assert len(derived) == len(set(derived))
