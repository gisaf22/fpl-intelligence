"""Inferential kernels — Rung I.

What is likely true beyond this data? Uncertainty quantification.

  resampling.py    — bootstrap CI for rank correlation and partial rho
  monotonicity.py  — bootstrap confidence for relationship shape
  variance_components.py — random-intercept ICC inference (MixedLM + LRT)
"""

from research.kernels.inferential.monotonicity import monotonicity_confidence
from research.kernels.inferential.resampling import (
    BOOTSTRAP_SEED,
    CI_LEVEL,
    MIN_N,
    N_BOOTSTRAP,
    bootstrap_partial_rho,
    bootstrap_spearman_ci,
    cluster_bootstrap_minutes_adjusted_rho,
    estimate_chance_correlation,
)
from research.kernels.inferential.variance_components import (
    mixed_effects_icc,
)

__all__ = [
    "BOOTSTRAP_SEED",
    "CI_LEVEL",
    "MIN_N",
    "N_BOOTSTRAP",
    "bootstrap_partial_rho",
    "bootstrap_spearman_ci",
    "cluster_bootstrap_minutes_adjusted_rho",
    "estimate_chance_correlation",
    "mixed_effects_icc",
    "monotonicity_confidence",
]
