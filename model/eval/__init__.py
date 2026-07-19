"""Predictive-layer evaluation harness — Phase 0 of docs/predictive-layer-plan.md.

Benchmarks (baselines) and the walk-forward scoring substrate that every later
model is measured against. Leakage-safe by construction: every predictor reads
only strictly-prior gameweeks (shift(1) before any rolling/expanding window).
"""

from model.eval.baselines import BASELINES, build_baseline_features, expanding_prior_mean
from model.eval.metrics import (
    block_bootstrap_ci,
    grouped_spearman,
    ndcg_at_k,
    precision_at_k,
    spearman_with_ci,
)
from model.eval.population import canonical, full_universe
from model.eval.scorer import GateResult, score_gate, score_gates
from model.eval.walkforward import per_gw_scores, score_predictions, walk_forward_by_position

# Public surface: baselines/population, the reusable gate, shared metric primitives,
# and the Phase-0 walk-forward harness (incl. per_gw_scores, the per-gameweek substrate).
__all__ = [
    "BASELINES",
    "GateResult",
    "block_bootstrap_ci",
    "build_baseline_features",
    "canonical",
    "expanding_prior_mean",
    "full_universe",
    "grouped_spearman",
    "ndcg_at_k",
    "per_gw_scores",
    "precision_at_k",
    "score_gate",
    "score_gates",
    "score_predictions",
    "spearman_with_ci",
    "walk_forward_by_position",
]
