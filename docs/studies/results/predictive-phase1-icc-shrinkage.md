# Phase 1 — ICC inference + EB shrinkage (frozen)

**Design:** [docs/predictive-phase1-design.md](../../predictive-phase1-design.md)
**Produced:** 2026-07-06
**Code:** `research/kernels/inferential/variance_components.py` (D1) ·
`model/eval/shrinkage.py` (D2)
**Outcome:** **D1 ships; D2 is a recorded null** (pre-registered fallback, §8 of the design).

Population/metrics inherited from Phase 0 / Q1: `minutes > 0`, DGW excluded,
`min_appearances = 10`, per position, within-position ranking only, conditional on
appearance. D1 whole-season one-shot; D2 walk-forward, strictly-prior, GW > 3.

## D1 — Variance-components inference (random intercept, MixedLM REML)

Formalizes Q1's between/within split as a model parameter with uncertainty.

| pos | Q1 SS between-share | ICC (D1) | ICC 95% CI | σ²_between | σ²_within | LRT p | n_players |
|---|---|---|---|---|---|---|---|
| GK | 0.038 | 0.000 | [0.000, 0.027] | 0.000 | 7.51 | 0.50 | 25 |
| DEF | 0.092 | 0.056 | [0.000, 0.082] | 0.558 | 9.43 | 1.1e-19 | 145 |
| MID | 0.136 | 0.101 | [0.070, 0.122] | 0.835 | 7.40 | 6.4e-64 | 191 |
| FWD | 0.132 | 0.097 | [0.000, 0.143] | 0.974 | 9.10 | 1.1e-17 | 51 |

**Reconciliation (gate 1) — pass.** ICC tracks the descriptive SS between-share in
order (GK < DEF < FWD ≈ MID) and magnitude. ICC sits slightly *below* the SS-share
at every position — the expected unbalanced-panel gap (the SS-share is inflated by
finite-group-mean dispersion; the variance component corrects for it). Reconciled to
tolerance, not equality, as the design pre-registered.

**Signal exists (gate 2) — pass where Q1 found it.** The LRT rejects the pooled-OLS
null decisively for DEF/MID/FWD; MID's ICC CI cleanly excludes 0. GK is genuine noise
(ICC 0, LRT p = 0.50) — consistent with Q1b's "GK ≈ chance". DEF/FWD CI lower bounds
touch 0 (thin positions), but the LRT is decisive.

**Read:** durable between-player level is a *small* share of weekly points variance
(ICC ~6–10% outfield, ~0 for GK). Week-to-week points are dominated by within-player
noise — the ceiling on any level-only ranker is low, which the D2 result then confirms.

## D2 — Empirical-Bayes shrunk ranker (walk-forward)

`lvl_shrunk = μ_pos + λ·(mean_i − μ_pos)`, `λ = n_i/(n_i + σ²_within/σ²_between)`,
all from strictly-prior rows; variance ratio by method-of-moments per evaluated GW.

| pos | mean Spearman | shrunk Spearman | mean prec@k | shrunk prec@k | mean ndcg | shrunk ndcg |
|---|---|---|---|---|---|---|
| GK | **0.041** | 0.022 | **0.360** | 0.329 | 0.460 | 0.458 |
| DEF | **0.185** | 0.174 | 0.341 | **0.351** | 0.426 | **0.440** |
| MID | **0.336** | 0.316 | 0.283 | **0.290** | 0.435 | **0.438** |
| FWD | **0.349** | 0.330 | **0.492** | **0.492** | 0.511 | **0.511** |

**Out-ranks (gate 3) — fail.** On the headline within-position Spearman, shrinkage is
*slightly worse* than the raw expanding mean at every position. Precision@k / NDCG are
marginally better for DEF/MID/FWD but within noise.

**Why (honest null, not a bug):** the between-player share is small (ICC ~0.06–0.10),
and shrinkage applies a *player-specific* λ, so it reorders players by games-played —
injecting sample-size structure into the rank rather than signal. Shrinkage delivers
variance reduction (squared-error benefit), but the incumbent expanding mean already
captures the *ordering*, so partial pooling does not improve within-position ranking on
a single season. Rank correlation is insensitive to the shrinkage shrinkage buys.

## Decision

- **Ship D1** — the ICC formalization is the durable Phase 1 output: it converts Q1's
  descriptive between-share into an inferential parameter with a CI and a hypothesis
  test, and confirms the ordering with uncertainty.
- **D2 is a recorded null.** Partial-pooling shrinkage toward the position mean does not
  out-rank the plain expanding mean within position on this single season. Kept in the
  codebase (`model/eval/shrinkage.py`, tested) so it can be re-run once cross-season
  data lands (Phase 6), where a stronger shrink target and drift may change the verdict.

## Scope limits carried forward

- **Single season** — cross-season pooling / drift explicitly out of scope (Phase 6).
- **Conditional on appearance** — ranks players who played, not who will play (Phase 0).
- **Shrink target = the mean** — established by the level-estimator study; the FWD
  recency tilt remains a deferred refinement, not part of this build.
- **Unbalanced-panel ICC < SS-share** — reconciled to tolerance, both reported above.
