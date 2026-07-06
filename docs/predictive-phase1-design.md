# Phase 1 Design — Hierarchical / ICC + partial-pooling shrinkage

**Status:** design (resolves the open decisions before build)
**Date:** 2026-07-06
**Authority:** [docs/predictive-layer-plan.md](predictive-layer-plan.md) §Phase 1 + concrete first piece
**Preconditions:** Phase 0 complete (per-position walk-forward harness frozen); level-estimator study
concluded *shrink toward the mean* ([results](studies/results/predictive-level-estimators.md));
statsmodels + scikit-learn installed.

---

## 1. Purpose & where it sits

Formalize the between/within split (Q1/Q1b) as a **variance-components model**, and turn its
partial-pooling estimates into a **shrunken player-level ranker** that must beat the naive season mean
on the Phase-0 harness. Statistical **Rung 3 (inferential)** used in service of **Rung 4 (predictive)**;
Pearl rung 1 (association) throughout. Within-season only (no cross-season pooling — needs ≥2 seasons).

## 2. Two deliverables (delineated — different runs, different regimes)

They share a model but are computed differently and must not be conflated.

| | **D1 — ICC inference** (formalize Q1) | **D2 — shrunk ranker** (harness gate) |
|---|---|---|
| Question | Is between-player variance real, and how big? | Does shrinkage out-rank the raw mean? |
| Fit | **whole-season**, per position, one shot | **walk-forward**, strictly-prior only |
| Estimator | `statsmodels` MixedLM (REML) | closed-form empirical-Bayes (§4) |
| Output | σ²_between, σ²_within, ICC + CIs, LRT | `lvl_shrunk` column scored on the harness |
| Leakage | n/a (descriptive inference) | must be leakage-safe (expanding) |

## 3. Model & estimand (per position)

```
points_{i,t} = β0 + u_i + ε_{i,t}
u_i    ~ N(0, σ²_between)     # player random intercept (stable level)
ε_{i,t} ~ N(0, σ²_within)     # week-to-week residual
ICC = σ²_between / (σ²_between + σ²_within)
```
ICC is Q1's between-share as a **model parameter with a standard error** (not a bootstrap percentile).

## 4. Decision — D2 uses closed-form empirical Bayes (not per-GW MixedLM refits)

Refitting MixedLM at every gameweek is slow and does not fit the column-based harness. Instead the
walk-forward ranker uses the **closed-form EB shrinkage** of the *same* model, computable incrementally
exactly like the Phase-0 baselines:

```
lvl_shrunk_{i,t} = μ_pos,t + λ_{i,t} · (mean_{i,t} − μ_pos,t)
λ_{i,t} = n_{i,t} / (n_{i,t} + σ²_within / σ²_between)
```
where, **all from strictly-prior rows (≤ t−1):**
- `mean_{i,t}` — player i's expanding prior mean (== Phase-0 `base_season`),
- `μ_pos,t` — the position's expanding prior grand mean (the shrink target — the mean, per §precondition),
- `n_{i,t}` — player i's prior appearance count,
- `σ²_within / σ²_between` — the position's variance-ratio, estimated by **method-of-moments** from the
  prior slice (derived from `decompose_variance` components), re-estimated per evaluated GW. No iterative
  fit in the walk-forward loop.

Interpretation: few games ⇒ `λ→0` ⇒ shrink hard to the position mean; many games ⇒ `λ→1` ⇒ trust the
player's own mean. This is the variance-reduction the stress test prescribed.

## 5. Population parity (for the D1↔Q1 reconciliation)

D1 must match Q1's population exactly or the reconciliation is invalid: **`minutes > 0`, DGW excluded,
`min_appearances = 10`, per position, whole season**. Note ICC (variance-component) equals
`decompose_variance`'s SS-share `pct_between` only for a **balanced** panel; our panel is unbalanced, so
reconcile to a **tolerance** (agreement in magnitude and ordering, not exact equality), and report both.

## 6. Placement & dedup

- **Kernel:** add `mixed_effects_icc()` **beside** `decompose_variance()` in
  `research/kernels/inferential/variance_components.py` (keep both — SS partition = descriptive read,
  ICC = inferential read). Add a small EB-shrink helper (D2) — either here or in `model/eval/`.
- **D2 column:** add `lvl_shrunk` alongside the Phase-0 level estimators (`model/eval/`), scored by the
  existing per-position harness — no harness changes.
- **Render:** a notebook that **augments** `points_variance_ceiling.ipynb` (D1) and reports the D2 harness
  result; `fpl-intelligence` kernel; diagnostic rubric.
- Do **not** modify `panel.py`, `decompose_variance`, or the locked LENS designs.

## 7. How to run & read

- **D1:** fit per position on the whole season → table of σ²_between, σ²_within, ICC (+ CI), LRT p-value;
  a plot of ICC per position with Q1's bootstrap between-share overlaid (the reconciliation).
- **D2:** build `lvl_shrunk`, score via `score_levels_by_position`-style harness → per-position Spearman
  vs the `mean` incumbent and the Phase-0 bars; a 4-panel bar with the incumbent marked.
- Read per position; GK (≈ chance) is not expected to move.

## 8. Gate (promotion criteria — all must pass)

1. **Reconciliation:** D1 ICC agrees with Q1's bootstrap between-share within tolerance (magnitude + order).
2. **Signal exists:** σ²_between CI excludes 0 (and LRT p < 0.05) for the positions where Q1 found it.
3. **It out-ranks:** `lvl_shrunk` beats the raw `mean` on held-out weeks on the Phase-0 harness, **per
   position** — materially for the low-sample positions (FWD/GK), at least neutral for MID/DEF.

If (3) fails (shrinkage doesn't out-rank), Phase 1 ships **D1 only** (the inferential formalization) and
records that partial pooling did not improve ranking on this single season — an honest null, not a failure.

## 9. Constraints honored

Rung boundaries (inference feeding prediction, association only); lag/leakage discipline (D2 strictly
prior, `_assert_no_leakage`-style guard); within-position ranking only; notebooks-don't-emit; import-linter
(kernel work in `research`, harness in `model`); extend-not-rebuild. Single-season — cross-season pooling
and drift explicitly out of scope (Phase 6).

## 10. Risks & scope limits

- **Unbalanced-panel ICC vs SS-share** — reconcile to tolerance, not equality (§5).
- **Variance-ratio instability early-season** — few prior GWs make `σ²_within/σ²_between` noisy; mitigate
  with the warmup (GW > 3) and a per-position floor on prior n.
- **Conditional on appearance** — inherited from Phase 0; D2 ranks players who played, not who will play.
- **Shrinking toward the mean assumes the mean is the right target** — established by the level-estimator
  study; the FWD recency tilt remains a deferred refinement, not part of this build.
