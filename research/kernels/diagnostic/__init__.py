"""Diagnostic kernels — Rung Dg.

Why did this happen? Classifies structure and causes within the data.

  stability.py   — distribution stability and pooling decisions
  shape.py       — relationship shape classification from bin stats
  panel.py       — between-player vs within-player rho decomposition
  tail.py        — tail event concentration analysis
  conditioning.py — cross-stratum association consistency
"""

from research.kernels.diagnostic.conditioning import classify_heterogeneity, compute_conditional_rho
from research.kernels.diagnostic.panel import split_between_within_player_rho
from research.kernels.diagnostic.shape import (
    ASSOCIATION_CLASS_TAXONOMY,
    GEOMETRY_TAXONOMY,
    MIN_N_HAUL,
    MIN_N_PANEL_PLAYERS,
    MONO_CONF_HIGH,
    MONO_CONF_LOW,
    MONOTONIC_GEOMETRIES,
    SUPPORT_TYPE_TAXONOMY,
    UPPER_TAIL_GEOMETRIES,
    classify_geometry,
    get_bin_direction,
)
from research.kernels.diagnostic.stability import (
    BLOCK_HOMOGENEITY_VALUES,
    EPSILON,
    POOLING_DECISION_VALUES,
    STABLE_THRESHOLD,
    UNSTABLE_THRESHOLD,
    assess_distribution_stability,
    resolve_pooling_strategy,
    stability_classify,
)
from research.kernels.diagnostic.tail import measure_tail_event_dependence

__all__ = [
    "ASSOCIATION_CLASS_TAXONOMY",
    "BLOCK_HOMOGENEITY_VALUES",
    "EPSILON",
    "GEOMETRY_TAXONOMY",
    "MIN_N_HAUL",
    "MIN_N_PANEL_PLAYERS",
    "MONOTONIC_GEOMETRIES",
    "MONO_CONF_HIGH",
    "MONO_CONF_LOW",
    "POOLING_DECISION_VALUES",
    "STABLE_THRESHOLD",
    "SUPPORT_TYPE_TAXONOMY",
    "UNSTABLE_THRESHOLD",
    "UPPER_TAIL_GEOMETRIES",
    "assess_distribution_stability",
    "classify_geometry",
    "classify_heterogeneity",
    "compute_conditional_rho",
    "get_bin_direction",
    "measure_tail_event_dependence",
    "resolve_pooling_strategy",
    "split_between_within_player_rho",
    "stability_classify",
]
