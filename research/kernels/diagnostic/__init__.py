"""Diagnostic kernels — Rung Dg.

Why did this happen? Classifies structure and causes within the data.

  stability.py   — distribution stability and pooling decisions
  shape.py       — relationship shape classification from bin stats
  panel.py       — between-player vs within-player rho decomposition
  tail.py        — tail event concentration analysis
  redundancy.py  — pairwise signal overlap detection
  conditioning.py — cross-stratum association consistency
"""

from research.kernels.diagnostic.stability import (
    BLOCK_HOMOGENEITY_VALUES, EPSILON, POOLING_DECISION_VALUES,
    STABLE_THRESHOLD, UNSTABLE_THRESHOLD,
    assess_distribution_stability, resolve_pooling_strategy, stability_classify,
)
from research.kernels.diagnostic.shape import (
    ASSOCIATION_CLASS_TAXONOMY, GEOMETRY_TAXONOMY, MONO_CONF_HIGH, MONO_CONF_LOW,
    MONOTONIC_GEOMETRIES, SUPPORT_TYPE_TAXONOMY, UPPER_TAIL_GEOMETRIES,
    MIN_N_HAUL, MIN_N_PANEL_PLAYERS,
    classify_geometry, get_bin_direction,
)
from research.kernels.diagnostic.panel import split_between_within_player_rho
from research.kernels.diagnostic.tail import measure_tail_event_dependence
from research.kernels.diagnostic.redundancy import compute_pairwise_rho, identify_redundant_pairs
from research.kernels.diagnostic.conditioning import classify_heterogeneity, compute_conditional_rho

__all__ = [
    "assess_distribution_stability", "resolve_pooling_strategy", "stability_classify",
    "BLOCK_HOMOGENEITY_VALUES", "POOLING_DECISION_VALUES",
    "STABLE_THRESHOLD", "UNSTABLE_THRESHOLD", "EPSILON",
    "classify_geometry", "get_bin_direction",
    "GEOMETRY_TAXONOMY", "MONOTONIC_GEOMETRIES", "UPPER_TAIL_GEOMETRIES",
    "ASSOCIATION_CLASS_TAXONOMY", "SUPPORT_TYPE_TAXONOMY",
    "MONO_CONF_LOW", "MONO_CONF_HIGH", "MIN_N_HAUL", "MIN_N_PANEL_PLAYERS",
    "split_between_within_player_rho",
    "measure_tail_event_dependence",
    "compute_pairwise_rho", "identify_redundant_pairs",
    "compute_conditional_rho", "classify_heterogeneity",
]
