# Phase 0 — Baseline benchmark (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) Phase 0
**Produced:** 2026-07-04
**Code:** `model/eval/baselines.py`, `model/eval/walkforward.py`
**Population:** `minutes > 0`, DGW excluded; evaluate GW > 3; per-GW Spearman over GWs with ≥ 20 rows.

## Frozen benchmark (real mart, GW 1–38)

| baseline | MAE | RMSE | spearman_mean | n |
|---|---|---|---|---|
| expanding season avg | 2.137 | 2.986 | **0.267** | 10110 |
| rolling avg (5) | 2.284 | 3.170 | 0.217 | 8728 |
| rolling avg (3) | 2.338 | 3.297 | 0.208 | 9659 |
| last-GW points | 2.622 | 3.977 | 0.193 | 10110 |
| position mean (identity-free) | 2.207 | 2.967 | 0.017 | 10277 |

**The number to beat:** spearman ≈ **0.267** (expanding season avg). Any later model that does
not clear this on the same harness adds nothing.

## What it establishes

- **"Level persists"** — season average is the best ranker → a player's cumulative level is the
  strongest simple signal. Confirmed.
- **"Deviations mean-revert"** — last-GW is the *worst* ranker and smoothing helps monotonically
  (roll3 < roll5 < season) → chasing last week's result hurts. Confirmed.
- **Identity dominates (corroborates Q1b)** — position-mean, which removes player identity, ranks at
  chance (0.017). The ranking signal *is* player identity, not position or recency.

## Phase 0 gate — PASSED

Baselines produce reproducible per-GW scores (deterministic); the walk-forward harness passes its
no-future-rows leakage assertion (`_assert_no_leakage`). Phase 1 (hierarchical/ICC) may open.
