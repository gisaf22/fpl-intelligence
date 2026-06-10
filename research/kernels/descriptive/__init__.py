"""Descriptive kernels — Rung D.

What happened in this data? No inference, no claims beyond the rows passed in.

  distribution.py        — series statistics, cohort comparison
  block_distributions.py — per-(signal, position, GW block) distribution stats
  binning.py             — adaptive signal bucketing and per-bin target stats
"""

from research.kernels.descriptive.distribution import compare_cohorts, compute_distribution_stats
from research.kernels.descriptive.block_distributions import (
    MIN_N_FOR_BLOCK_STATS,
    compute_signal_block_distributions,
)
from research.kernels.descriptive.binning import (
    BLOCK_ORDER, DISCRETE_BINS, DISCRETE_LABELS, FDR_ORDINAL_BINS,
    FDR_ORDINAL_LABELS, FDR_SIGNALS, MATCH_LEVEL_SIGNALS, MIN_ACTIVE_BINS,
    MIN_N_PER_BIN, MIN_N_SHAPE, POSITIONS, POPULATION_ROBUSTNESS_VALUES,
    POPULATION_SCOPE_VALUES, QUANTILE_N_BINS, SPARSE_THRESHOLD,
    TWO_STAGE_NZ_LABELS, bin_analysis, select_bucketing_scheme,
)

__all__ = [
    "compute_distribution_stats", "compare_cohorts",
    "compute_signal_block_distributions", "MIN_N_FOR_BLOCK_STATS",
    "select_bucketing_scheme", "bin_analysis",
    "MATCH_LEVEL_SIGNALS", "POSITIONS", "BLOCK_ORDER",
    "FDR_SIGNALS", "FDR_ORDINAL_BINS", "FDR_ORDINAL_LABELS",
    "DISCRETE_BINS", "DISCRETE_LABELS", "TWO_STAGE_NZ_LABELS",
    "QUANTILE_N_BINS", "MIN_N_SHAPE", "MIN_N_PER_BIN",
    "SPARSE_THRESHOLD", "MIN_ACTIVE_BINS",
    "POPULATION_ROBUSTNESS_VALUES", "POPULATION_SCOPE_VALUES",
]
