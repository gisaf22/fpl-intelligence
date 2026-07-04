"""Predictive-layer evaluation harness — Phase 0 of docs/predictive-layer-plan.md.

Benchmarks (baselines) and the walk-forward scoring substrate that every later
model is measured against. Leakage-safe by construction: every predictor reads
only strictly-prior gameweeks (shift(1) before any rolling/expanding window).
"""

from model.eval.baselines import BASELINES, build_baseline_features
from model.eval.walkforward import score_predictions, walk_forward_baselines

__all__ = [
    "BASELINES",
    "build_baseline_features",
    "score_predictions",
    "walk_forward_baselines",
]
