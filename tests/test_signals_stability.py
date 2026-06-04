"""Unit tests for analytics.signals.stability."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from research.kernels.stability import (
    BLOCK_HOMOGENEITY_VALUES,
    EPSILON,
    POOLING_DECISION_VALUES,
    STABLE_THRESHOLD,
    UNSTABLE_THRESHOLD,
    classify_block_homogeneity,
    compute_signal_block_distributions,
    flag_pooling_decision,
)

pytestmark = pytest.mark.unit

DEFAULT_GW_BLOCKS: dict[str, tuple[int, int]] = {
    "first_half": (1, 17),
    "second_half": (18, 38),
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_df(
    position: str = "MID",
    signal_name: str = "xg",
    first_half_values: list[float] | None = None,
    second_half_values: list[float] | None = None,
    gw_column: str = "gw",
) -> pd.DataFrame:
    """Build a minimal synthetic DataFrame with two GW blocks."""
    if first_half_values is None:
        first_half_values = [float(i) for i in range(1, 18)]  # GW 1-17
    if second_half_values is None:
        second_half_values = [float(i) for i in range(18, 35)]  # GW 18-34

    first_gws = list(range(1, len(first_half_values) + 1))
    second_gws = list(range(18, 18 + len(second_half_values)))

    rows = [{gw_column: gw, "position": position, signal_name: v} for gw, v in zip(first_gws, first_half_values)] + [
        {gw_column: gw, "position": position, signal_name: v} for gw, v in zip(second_gws, second_half_values)
    ]
    return pd.DataFrame(rows)


def _block_stats_for(
    df: pd.DataFrame,
    signal: str = "xg",
    position: str = "MID",
    gw_blocks: dict | None = None,
) -> pd.DataFrame:
    return compute_signal_block_distributions(
        df,
        signals=[signal],
        positions=[position],
        gw_blocks=gw_blocks if gw_blocks is not None else DEFAULT_GW_BLOCKS,
    )


# ---------------------------------------------------------------------------
# Vocabulary contract
# ---------------------------------------------------------------------------


def test_block_homogeneity_values_complete():
    assert BLOCK_HOMOGENEITY_VALUES == {"stable", "moderate_shift", "unstable"}


def test_pooling_decision_values_complete():
    assert POOLING_DECISION_VALUES == {"pool_confirmed", "pool_with_caveat", "restrict_to_midseason"}


def test_default_gw_blocks_keys():
    assert set(DEFAULT_GW_BLOCKS.keys()) == {"first_half", "second_half"}


def test_stable_threshold_less_than_unstable():
    assert STABLE_THRESHOLD < UNSTABLE_THRESHOLD


# ---------------------------------------------------------------------------
# compute_signal_block_distributions — output schema
# ---------------------------------------------------------------------------


def test_output_has_required_columns():
    df = _make_df()
    result = compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS)
    expected_cols = {"signal", "position", "block", "n", "median", "q1", "q3", "iqr", "min_gw", "max_gw"}
    assert expected_cols.issubset(set(result.columns))


def test_output_row_count_signal_x_position_x_block():
    df = _make_df(position="MID")
    df2 = _make_df(position="FWD")
    combined = pd.concat([df, df2], ignore_index=True)
    result = compute_signal_block_distributions(
        combined, signals=["xg"], positions=["MID", "FWD"], gw_blocks=DEFAULT_GW_BLOCKS
    )
    # 1 signal x 2 positions x 2 blocks = 4 rows
    assert len(result) == 4


def test_missing_signal_is_skipped():
    df = _make_df()
    result = compute_signal_block_distributions(
        df, signals=["nonexistent"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS
    )
    assert len(result) == 0


def test_raises_on_missing_gw_column():
    df = pd.DataFrame({"position": ["MID"] * 5, "xg": [1.0] * 5})
    with pytest.raises(ValueError, match="missing required columns"):
        compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS)


def test_raises_on_missing_position_column():
    df = pd.DataFrame({"gw": list(range(1, 6)), "xg": [1.0] * 5})
    with pytest.raises(ValueError, match="missing required columns"):
        compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS)


# ---------------------------------------------------------------------------
# compute_signal_block_distributions — values
# ---------------------------------------------------------------------------


def test_iqr_is_q3_minus_q1():
    df = _make_df()
    result = compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS)
    for _, row in result.iterrows():
        if not np.isnan(row["iqr"]):
            assert abs(row["iqr"] - (row["q3"] - row["q1"])) < 1e-9


def test_block_n_matches_gw_range():
    first = [1.0] * 14  # GW 1-14
    second = [2.0] * 10  # GW 18-27
    df = _make_df(first_half_values=first, second_half_values=second)
    result = compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS)
    first_row = result[result["block"] == "first_half"].iloc[0]
    second_row = result[result["block"] == "second_half"].iloc[0]
    assert first_row["n"] == 14
    assert second_row["n"] == 10


def test_insufficient_n_produces_nan_stats():
    # Only 3 rows per block — below MIN_N_FOR_BLOCK_STATS
    df = _make_df(
        first_half_values=[1.0, 2.0, 3.0],
        second_half_values=[4.0, 5.0, 6.0],
    )
    result = compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=DEFAULT_GW_BLOCKS)
    for _, row in result.iterrows():
        assert np.isnan(row["median"])
        assert row["n"] in (3, 0)


# ---------------------------------------------------------------------------
# classify_block_homogeneity — all three classifications
# ---------------------------------------------------------------------------


def _make_block_stats(
    medians: list[float],
    iqrs: list[float],
    blocks: list[str] | None = None,
) -> pd.DataFrame:
    if blocks is None:
        blocks = [f"b{i}" for i in range(len(medians))]
    return pd.DataFrame(
        {
            "block": blocks,
            "median": medians,
            "iqr": iqrs,
        }
    )


def test_classify_stable_when_identical_blocks():
    stats = _make_block_stats(medians=[5.0, 5.0], iqrs=[2.0, 2.0])
    assert classify_block_homogeneity(stats) == "stable"


def test_classify_stable_when_small_shift():
    # normalized_shift = |5.0 - 5.1| / ((2.0 + 2.0)/2 + eps) ≈ 0.05 < STABLE_THRESHOLD
    stats = _make_block_stats(medians=[5.0, 5.1], iqrs=[2.0, 2.0])
    assert classify_block_homogeneity(stats) == "stable"


def test_classify_moderate_shift():
    # normalized_shift = |0.0 - 1.5| / ((1.0 + 1.0)/2 + eps) = 1.5 / 1.0 = 1.5
    # That's exactly at UNSTABLE_THRESHOLD boundary; shift < 1.5 needed for moderate_shift.
    # Use shift = 1.0: |0.0 - 1.0| / 1.0 = 1.0 → moderate
    stats = _make_block_stats(medians=[0.0, 1.0], iqrs=[1.0, 1.0])
    result = classify_block_homogeneity(stats)
    assert result == "moderate_shift"


def test_classify_unstable_when_large_shift():
    # normalized_shift = |0.0 - 10.0| / ((0.1 + 0.1)/2 + eps) >> UNSTABLE_THRESHOLD
    stats = _make_block_stats(medians=[0.0, 10.0], iqrs=[0.1, 0.1])
    assert classify_block_homogeneity(stats) == "unstable"


def test_classify_stable_boundary_just_below_threshold():
    # shift just below STABLE_THRESHOLD
    shift = STABLE_THRESHOLD - 0.001
    stats = _make_block_stats(
        medians=[0.0, shift * (1.0 + EPSILON)],
        iqrs=[1.0, 1.0],
    )
    assert classify_block_homogeneity(stats) == "stable"


def test_classify_moderate_shift_boundary_just_above_stable():
    # shift just above STABLE_THRESHOLD
    shift = STABLE_THRESHOLD + 0.001
    stats = _make_block_stats(
        medians=[0.0, shift * (1.0 + EPSILON)],
        iqrs=[1.0, 1.0],
    )
    assert classify_block_homogeneity(stats) == "moderate_shift"


def test_classify_raises_on_missing_columns():
    stats = pd.DataFrame({"block": ["b1", "b2"], "median": [1.0, 2.0]})
    with pytest.raises(ValueError, match="missing required columns"):
        classify_block_homogeneity(stats)


# ---------------------------------------------------------------------------
# classify_block_homogeneity — edge cases
# ---------------------------------------------------------------------------


def test_all_zero_signal_is_stable():
    """An all-zero signal is consistently zero across blocks → stable."""
    stats = _make_block_stats(medians=[0.0, 0.0], iqrs=[0.0, 0.0])
    assert classify_block_homogeneity(stats) == "stable"


def test_all_nan_blocks_returns_stable():
    """All blocks insufficient data — treated as unobservable → stable."""
    stats = _make_block_stats(
        medians=[float("nan"), float("nan")],
        iqrs=[float("nan"), float("nan")],
    )
    assert classify_block_homogeneity(stats) == "stable"


def test_one_valid_one_nan_block_returns_unstable():
    """One block has data, the other does not — cannot pool → unstable."""
    stats = _make_block_stats(
        medians=[5.0, float("nan")],
        iqrs=[2.0, float("nan")],
    )
    assert classify_block_homogeneity(stats) == "unstable"


def test_three_blocks_uses_max_pairwise_shift():
    """With 3 blocks, worst-case pairwise shift determines classification."""
    # b1 and b3 are far apart; b1 and b2 are close
    stats = _make_block_stats(
        medians=[0.0, 0.1, 20.0],
        iqrs=[1.0, 1.0, 1.0],
        blocks=["early", "mid", "late"],
    )
    # max shift = |0.0 - 20.0| / 1.0 = 20.0 >> UNSTABLE_THRESHOLD
    assert classify_block_homogeneity(stats) == "unstable"


# ---------------------------------------------------------------------------
# classify_block_homogeneity — via compute_signal_block_distributions
# ---------------------------------------------------------------------------


def test_stable_signal_end_to_end():
    """Signal with same distribution in both halves → stable."""
    rng = np.random.default_rng(42)
    first = rng.normal(loc=2.0, scale=0.1, size=20).tolist()
    second = rng.normal(loc=2.05, scale=0.1, size=20).tolist()
    df = _make_df(first_half_values=first, second_half_values=second)
    block_stats = _block_stats_for(df)
    assert classify_block_homogeneity(block_stats) == "stable"


def test_unstable_signal_end_to_end():
    """Signal with very different distributions → unstable."""
    first = [0.0] * 20
    second = [100.0] * 20
    df = _make_df(first_half_values=first, second_half_values=second)
    block_stats = _block_stats_for(df)
    assert classify_block_homogeneity(block_stats) == "unstable"


def test_all_zero_signal_end_to_end():
    """All-zero signal across both halves → stable."""
    first = [0.0] * 20
    second = [0.0] * 20
    df = _make_df(first_half_values=first, second_half_values=second)
    block_stats = _block_stats_for(df)
    assert classify_block_homogeneity(block_stats) == "stable"


# ---------------------------------------------------------------------------
# Parameterized GW block behavior
# ---------------------------------------------------------------------------


def test_custom_gw_blocks_are_respected():
    """Custom block definitions override defaults."""
    df = pd.DataFrame(
        {
            "gw": list(range(1, 11)),
            "position": ["MID"] * 10,
            "xg": [float(i) for i in range(1, 11)],
        }
    )
    custom_blocks = {"early": (1, 5), "late": (6, 10)}
    result = compute_signal_block_distributions(df, signals=["xg"], positions=["MID"], gw_blocks=custom_blocks)
    assert set(result["block"].unique()) == {"early", "late"}
    early = result[result["block"] == "early"].iloc[0]
    late = result[result["block"] == "late"].iloc[0]
    assert early["n"] == 5
    assert late["n"] == 5


def test_custom_gw_column_name():
    df = pd.DataFrame(
        {
            "gameweek": list(range(1, 21)),
            "position": ["MID"] * 20,
            "xg": [1.0] * 20,
        }
    )
    blocks = {"first_half": (1, 10), "second_half": (11, 20)}
    result = compute_signal_block_distributions(
        df,
        signals=["xg"],
        positions=["MID"],
        gw_column="gameweek",
        gw_blocks=blocks,
    )
    assert len(result) == 2
    assert all(result["n"] == 10)


# ---------------------------------------------------------------------------
# flag_pooling_decision
# ---------------------------------------------------------------------------


def test_pooling_stable_maps_to_pool_confirmed():
    assert flag_pooling_decision("stable") == "pool_confirmed"


def test_pooling_moderate_shift_maps_to_pool_with_caveat():
    assert flag_pooling_decision("moderate_shift") == "pool_with_caveat"


def test_pooling_unstable_maps_to_restrict_to_midseason():
    assert flag_pooling_decision("unstable") == "restrict_to_midseason"


def test_pooling_mapping_is_complete():
    """Every homogeneity value maps to a valid pooling decision."""
    for h in BLOCK_HOMOGENEITY_VALUES:
        decision = flag_pooling_decision(h)
        assert decision in POOLING_DECISION_VALUES


def test_pooling_raises_on_unknown_value():
    with pytest.raises(ValueError, match="unrecognized homogeneity value"):
        flag_pooling_decision("unknown_class")
