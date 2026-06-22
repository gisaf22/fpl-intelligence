"""Hypothesis kernels — Rung H.

Given inference, what decision do I make?

  stratification.py — quintile stratification; Gate 2 input for qualification studies
  multiplicity.py   — multiple comparison correction (BH FDR, Holm-Bonferroni)
"""

from research.kernels.hypothesis.multiplicity import benjamini_hochberg, holm_bonferroni
from research.kernels.hypothesis.stratification import MIN_N, quintile_stratification

__all__ = [
    "MIN_N",
    "benjamini_hochberg",
    "holm_bonferroni",
    "quintile_stratification",
]
