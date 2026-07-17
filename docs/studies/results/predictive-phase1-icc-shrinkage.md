# Phase 1 — ICC inference + EB shrinkage (frozen)

**Plan/design:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) (§3 Phase 1)
**Produced:** 2026-07-06
**Code:** `research/kernels/inferential/variance_components.py` (ICC inference) ·
`model/forecast/shrinkage.py` (EB shrinkage)
**Outcome:** **ICC inference ships; EB shrinkage is a recorded null** (pre-registered fallback, §8 of the design).

Population/metrics inherited from Phase 0 / Q1: `minutes > 0`, DGW excluded,
`min_appearances = 10`, per position, within-position ranking only, conditional on
appearance. ICC inference is whole-season one-shot; EB shrinkage is walk-forward, strictly-prior, GW > 3.

## ICC inference — variance components (random intercept, MixedLM REML)

Formalizes Q1's between/within split as a model parameter with uncertainty.

| pos | Q1 SS between-share | ICC | ICC 95% CI | σ²_between | σ²_within | LRT p | n_players |
|---|---|---|---|---|---|---|---|
| GK | 0.038 | 0.000 | [0.000, 0.027] | 0.000 | 7.51 | 0.50 | 25 |
| DEF | 0.092 | 0.056 | [0.000, 0.082] | 0.558 | 9.43 | 1.1e-19 | 145 |
| MID | 0.136 | 0.101 | [0.070, 0.122] | 0.835 | 7.40 | 6.4e-64 | 191 |
| FWD | 0.132 | 0.097 | [0.000, 0.143] | 0.974 | 9.10 | 1.1e-17 | 51 |

### ICC normality robustness — does the ICC survive dropping the Gaussian assumption? (2026-07-06)

The ICC above is from a *Gaussian* MixedLM, but the target is a zero-inflated count. The between/within
**sum-of-squares partition is distribution-free** as a point estimate (no normality needed) — only the
LMM's CI/LRT assumed normality. A **player-clustered bootstrap of the SS between-share**
(`research.kernels.inferential.variance_components.between_share_bootstrap`) gives a normality-free CI
to set beside the Gaussian ICC:

| pos | SS between-share (distribution-free) | bootstrap 95% CI | Gaussian-LMM ICC [CI] |
|---|---|---|---|
| GK | 0.038 | **[0.018, 0.063]** | 0.000 [0.000, 0.027] |
| DEF | 0.092 | [0.070, 0.117] | 0.056 [0.000, 0.082] |
| MID | 0.136 | [0.113, 0.160] | 0.101 [0.070, 0.122] |
| FWD | 0.132 | [0.084, 0.182] | 0.097 [0.000, 0.143] |

- **Ordering survives:** GK < DEF < FWD ≈ MID under **both** methods.
- **Magnitude survives:** outfield between-share is small under both (~0.09–0.14 SS / ~0.06–0.10 ICC); DEF/MID/FWD CIs exclude 0 → the "small but real" conclusion is **not** an artifact of normality.
- **GK caveat:** the distribution-free SS-share (0.038, CI excludes 0) diverges from the LMM's ICC = 0.
  This is **finite-sample upward bias** of the SS statistic (group means differ by chance even with zero
  true between-variance), *not* durable between-keeper skill. The "GK ≈ no durable level" conclusion
  correctly rests on the variance-component correction + the LRT (p = 0.50), which the raw SS statistic
  cannot replicate.

**Verdict:** the ICC's substantive conclusions are robust to dropping normality. Debt retired; no re-work.

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
noise — the ceiling on any level-only ranker is low, which the EB-shrinkage result then confirms.

## Empirical-Bayes shrunk ranker (walk-forward)

`lvl_shrunk = μ_pos + λ·(mean_i − μ_pos)`, `λ = n_i/(n_i + σ²_within/σ²_between)`,
all from strictly-prior rows; variance ratio by method-of-moments per evaluated GW.

| pos | mean Spearman [95% CI] | shrunk Spearman [95% CI] | mean prec@k | shrunk prec@k | mean ndcg | shrunk ndcg |
|---|---|---|---|---|---|---|
| GK | **0.041** [-0.047, 0.120] | 0.022 [-0.044, 0.099] | **0.360** | 0.329 | 0.460 | 0.458 |
| DEF | **0.185** [0.151, 0.221] | 0.174 [0.147, 0.206] | 0.341 | **0.351** | 0.426 | **0.440** |
| MID | **0.336** [0.315, 0.363] | 0.316 [0.292, 0.345] | 0.283 | **0.290** | 0.435 | **0.438** |
| FWD | **0.349** [0.292, 0.389] | 0.330 [0.270, 0.374] | **0.492** | **0.492** | 0.511 | **0.511** |

> **Block-bootstrap CIs added 2026-07-12 (Phase 1 cleanup).** The Spearman gate now routes through the
> shared harness helper (`model.eval.walkforward.score_topk_by_position`, seed=0, block=4 GWs), so the
> comparison carries a 95% CI on every cell (point estimates unchanged; coverage ~0.97-0.99, equal for
> both columns since shrunk is defined exactly where the mean is post-warmup). The mean and shrunk CIs
> **overlap heavily at every position** (each point estimate sits inside the other's interval), which
> now *shows* the "within noise" read the verdict below asserted -- the null is confirmed, not merely
> stated. GK is degenerate (see note under the table): ICC(GK)=0 -> variance ratio = inf -> lambda -> 0
> -> `lvl_shrunk` collapses to the position mean `mu_pos`, so the GK row is not a genuine model
> comparison. GK's true naive bar is rolling-5, not `base_season`
> (`scorer.best_baseline_per_position`); `base_season` is used here only as the correct *control*
> for the narrow question "does shrinking the mean beat the mean?".

**Out-ranks (gate 3) — fail.** On the headline within-position Spearman, shrinkage is
*slightly worse* than the raw expanding mean at every position, and the mean/shrunk 95% CIs overlap at
every position (see the note above). Precision@k / NDCG are marginally better for DEF/MID/FWD but
within noise.

**Why (honest null, not a bug):** the between-player share is small (ICC ~0.06–0.10),
and shrinkage applies a *player-specific* λ, so it reorders players by games-played —
injecting sample-size structure into the rank rather than signal. Shrinkage delivers
variance reduction (squared-error benefit), but the incumbent expanding mean already
captures the *ordering*, so partial pooling does not improve within-position ranking on
a single season. Rank correlation is insensitive to the variance reduction shrinkage buys.

## Decision

- **Ship the ICC inference** — the ICC formalization is the durable Phase 1 output: it converts Q1's
  descriptive between-share into an inferential parameter with a CI and a hypothesis
  test, and confirms the ordering with uncertainty.
- **EB shrinkage is a recorded null.** Partial-pooling shrinkage toward the position mean does not
  out-rank the plain expanding mean within position on this single season. Kept in the
  codebase (`model/forecast/shrinkage.py`, tested) so it can be re-run once cross-season
  data lands (Phase 6), where a stronger shrink target and drift may change the verdict.

## Scope limits carried forward

- **Single season** — cross-season pooling / drift explicitly out of scope (Phase 6).
- **Conditional on appearance** — ranks players who played, not who will play (Phase 0).
- **Shrink target = the mean** — established by the level-estimator study; the FWD
  recency tilt remains a deferred refinement, not part of this build.
- **Unbalanced-panel ICC < SS-share** — reconciled to tolerance, both reported above.
