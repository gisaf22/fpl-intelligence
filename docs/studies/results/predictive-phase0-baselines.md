# Phase 0 — Baseline benchmark (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) Phase 0
**Produced:** 2026-07-04
**Code:** `model/eval/baselines.py`, `model/eval/walkforward.py`
**Population:** `minutes > 0`, DGW excluded; evaluate GW > 3; per-GW metrics over GWs with ≥ 20 rows.

## Frozen benchmark (real mart, GW 1–38, common evaluation set)

All baselines scored on the **same rows** (the common set where every baseline is defined; n = 8728),
so the comparison is not a sampling artifact. `coverage` = share of post-warmup rows on which the
baseline is defined at all. Headline metric is **ranking** (Spearman / precision@20 / NDCG@20); the
target is zero-inflated and right-skewed, so squared error is haul-dominated — **RMSE is omitted**;
MAE is a secondary sanity number. Proper scoring (Poisson deviance, CRPS) arrives in Phase 4.

| baseline | spearman_mean | precision@20 | ndcg@20 | mae | coverage |
|---|---|---|---|---|---|
| expanding season avg | **0.245** | **0.150** | **0.377** | 2.193 | 0.984 |
| rolling avg (5) | 0.217 | 0.136 | 0.351 | 2.284 | 0.849 |
| rolling avg (3) | 0.196 | 0.132 | 0.335 | 2.378 | 0.940 |
| last-GW points | 0.174 | 0.112 | 0.313 | 2.703 | 0.984 |
| position mean (sanity floor) | 0.011 | 0.070 | 0.288 | 2.229 | 1.000 |

**The bar to beat:** spearman **0.245** / precision@20 **0.150** / ndcg@20 **0.377** (expanding season
avg). Any later model that does not clear these on the same harness adds nothing.

## What it establishes

- **"Level persists"** — season average is the best ranker → a player's cumulative level is the
  strongest simple signal. Confirmed.
- **"Deviations mean-revert"** — last-GW is the *worst* ranker and smoothing helps monotonically
  (roll3 < roll5 < season) → chasing last week's result hurts. Confirmed.
- **Identity dominates (corroborates Q1b)** — position mean, which removes player identity, ranks at
  chance (spearman 0.011; precision@20 0.070 ≈ 20/300 random). The ranking signal *is* player identity.

## v1 scope limits (documented; deferred to later phases)

These are deliberate simplifications of the Phase-0 floor, named here rather than hidden:

- **(C) Rolling over appearances, not calendar** — because `minutes > 0` is filtered first, rolling
  windows average the last N *appearances*, silently skipping blanks/injury gaps (1598 such gaps in
  the data). Absence carries no signal and a window can be stale. Revisit when availability is modelled.
- **(D) DGWs dropped entirely** — never predicted or evaluated (avoids double-points distortion in a
  floor). A high-value FPL event is out of scope until a DGW-aware target is defined.
- **(E) New-player / early-GW under-coverage** — insufficient history yields NaN features (see
  `coverage`); the common set restricts to players with enough history, so newly-arrived players are
  under-represented exactly where interest is high. A cold-start treatment is a later-phase concern.

## Phase 0 gate — PASSED

Baselines produce reproducible per-GW scores (deterministic); the walk-forward harness passes its
no-future-rows leakage assertion (`_assert_no_leakage`); baselines compared on a coverage-matched
common set with ranking-appropriate metrics. Phase 1 (hierarchical/ICC) may open — its promotion test
is to beat spearman 0.245 on this harness.
