"""Predictive-layer evaluation harness — Phase 0 of docs/predictive-layer-plan.md.

Benchmarks (baselines) and the walk-forward scoring substrate that every later
model is measured against. Leakage-safe by construction: every predictor reads
only strictly-prior gameweeks (shift(1) before any rolling/expanding window).
"""

from model.eval.baselines import BASELINES, base_season, build_baseline_features
from model.eval.metrics import (
    block_bootstrap_ci,
    grouped_spearman,
    ndcg_at_k,
    precision_at_k,
    spearman_with_ci,
)
from model.eval.population import canonical, full_universe
from model.eval.scorer import GateResult, score_gate, score_gates
from model.eval.walkforward import score_predictions, walk_forward_baselines, walk_forward_by_position

__all__ = [
    # baselines / population — the canonical reference bar + dataset
    "BASELINES",
    # the reusable gate
    "GateResult",
    "base_season",
    "block_bootstrap_ci",
    "build_baseline_features",
    "canonical",
    "full_universe",
    # metrics — shared primitives
    "grouped_spearman",
    "ndcg_at_k",
    "precision_at_k",
    "score_gate",
    "score_gates",
    # Phase-0 harness
    "score_predictions",
    "spearman_with_ci",
    "walk_forward_baselines",
    "walk_forward_by_position",
]
