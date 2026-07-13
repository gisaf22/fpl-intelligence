# Phase 1 audit -- ICC / variance components + shrinkage ranker (D1/D2) + level-estimator study

**Run:** 2026-07-12 - assessment + plan only (no code changed).
**Lenses:** platform SWE / analytics engineer / data scientist.
**Reproduction oracle:** `docs/studies/results/predictive-phase1-icc-shrinkage.md`,
`docs/studies/results/predictive-level-estimators.md` (frozen numbers are sacred; any change must
reproduce them to 4dp).

ASCII throughout (`sigma2_*`, `->`, `<=`) to honor the code convention.

---

## 1. What it is / what it touches

Phase 1 turns Q1's descriptive between/within split into (D1) an inferential variance-components
parameter with a CI + hypothesis test, and (D2) a predictive empirical-Bayes shrinkage ranker; a
pre-Phase-1 "level-estimator" study decides what D2 should shrink toward.

| unit | module | key API | how used | tested by |
|---|---|---|---|---|
| D1 | [research/kernels/inferential/variance_components.py](../../research/kernels/inferential/variance_components.py) | `mixed_effects_icc` ([:71](../../research/kernels/inferential/variance_components.py#L71)) | REML MixedLM random-intercept ICC + player-clustered bootstrap CI + boundary-corrected LRT; called x2 in `phase1_icc_shrinkage.ipynb`; exported from `research/kernels/inferential/__init__.py` | `tests/test_kernels_inferential_variance_components.py` |
| D2 | [model/forecast/shrinkage.py](../../model/forecast/shrinkage.py) | `build_shrunk_features` ([:78](../../model/forecast/shrinkage.py#L78)), `score_shrinkage_by_position` ([:111](../../model/forecast/shrinkage.py#L111)) | walk-forward strictly-prior EB shrink of `lvl_mean` toward `mu_pos`; called in `phase1_icc_shrinkage.ipynb` | `tests/test_model_forecast_shrinkage.py` |
| level study | [model/forecast/level_estimators.py](../../model/forecast/level_estimators.py) | `build_level_features` ([:68](../../model/forecast/level_estimators.py#L68)), `score_levels_by_position` ([:94](../../model/forecast/level_estimators.py#L94)) | 7 leakage-safe "level" summaries scored as within-position rankers; called in `level_estimators.ipynb` | `tests/test_model_forecast_level_estimators.py` |
| D1 cross-check | [model/eval/prephase2_validation.py](../../model/eval/prephase2_validation.py) | `x2_between_share_bootstrap` ([:33](../../model/eval/prephase2_validation.py#L33)) | distribution-free SS between-share bootstrap feeding D1's frozen "normality sensitivity (X2)" note | (runnable script) |

**Shared eval API it should sit on** (`model/eval/`, per the EVAL_DESIGN appendix
[EVAL_DESIGN.md:536-561](../../model/governance/EVAL_DESIGN.md#L536)):
`population.canonical` ([population.py:13](../../model/eval/population.py#L13)),
`baselines.base_season` ([baselines.py:59](../../model/eval/baselines.py#L59)),
`baselines.best_baseline_per_position` (via
[walkforward.py:186](../../model/eval/walkforward.py#L186)),
`metrics.spearman_with_ci` / `block_bootstrap_ci`
([metrics.py:61](../../model/eval/metrics.py#L61) / [:39](../../model/eval/metrics.py#L39)),
`scorer.score_gate/score_gates` ([scorer.py:33](../../model/eval/scorer.py#L33) / [:63](../../model/eval/scorer.py#L63)).
**Precedent:** Phase 3.0 already migrated its gate onto `score_gates`
([points_model.py:427](../../model/forecast/points_model.py#L427)) and thereby carries a
CI+coverage. Phase 1 is the laggard: both forecast modules still hand-roll the gate and import a
private symbol.

**Outcome on record:** D1 ships; D2 is a deliberately-kept **recorded null** (partial pooling does
not out-rank the plain mean on a single season) -- so this audit is a *cleanup + honesty* pass, not a
"delete D2" pass.

---

## 2. Findings by lens + severity

Legend: HIGH = correctness / missing CI / cross-cutting redundancy; MED = reuse/boundary/naming;
LOW = cosmetic. **[FACT]** = definitional / verified in code; **[HYP]** = plausible but unverified.

### Data scientist

- **DS-1 (HIGH) -- the D2 gate decides "fail" and asserts "within noise" with no CI. [FACT]**
  `score_shrinkage_by_position` reports bare Spearman/prec@k/ndcg point estimates
  ([shrinkage.py:143-149](../../model/forecast/shrinkage.py#L143)); the frozen table
  (`predictive-phase1-icc-shrinkage.md` D2) and its verdict "Out-ranks (gate 3) -- fail" +
  "marginally better ... but within noise" carry **no interval**. This directly violates the project
  rule "every ranking gate reports a block-bootstrap CI so 'beats the baseline' is always qualified by
  whether the CIs separate" ([EVAL_DESIGN.md:561](../../model/governance/EVAL_DESIGN.md#L561)). The
  exact primitive exists (`metrics.spearman_with_ci`, wrapped by `scorer.score_gate`). **Fix:** route
  the Spearman column through the shared CI machinery and print `ci_lo/ci_hi` in the table.
  *Note:* adding the CI almost certainly **supports** the honest-null (overlapping mean/shrunk CIs at
  every position) rather than overturning it **[HYP]** -- but as presented the "within noise" claim is
  asserted, not shown. This is the single highest-leverage item.

- **DS-2 (MED) -- per-position incumbent is `base_season` everywhere; GK's real bar is rolling-5. [FACT]**
  D2 compares `lvl_shrunk` vs `lvl_mean` (== `base_season`) at every position, but
  `best_baseline_per_position` documents that at GK the rolling-5 average out-ranks `base_season`
  ([walkforward.py:186-198](../../model/eval/walkforward.py#L186)). For D2's *specific* question
  ("does shrinking the mean beat the mean?") `base_season` is the correct control, so this is not a
  bug -- but the GK row is near-degenerate: ICC(GK)=0 -> `var_ratio`=inf -> lambda->0 -> `lvl_shrunk`
  collapses to the position mean `mu_pos`. The GK "mean 0.041 vs shrunk 0.022" line should be flagged
  as a degenerate ranker, not read as a model comparison. **Fix:** annotate GK degeneracy in the doc;
  optionally show rolling-5 as the GK reference bar for context.

- **DS-3 (LOW, positive) -- D1 is correctly instrumented; no untested claim. [FACT]**
  ICC carries a player-clustered bootstrap CI + a boundary-corrected LRT (0.5*chi2 mixture,
  [variance_components.py:181-198](../../research/kernels/inferential/variance_components.py#L181)),
  and the Gaussian-LMM assumption is cross-checked distribution-free
  ([prephase2_validation.py:33](../../model/eval/prephase2_validation.py#L33)), already folded into the
  frozen doc's "normality sensitivity" note. Leakage is N/A (whole-season decomposition, not a
  predictor). No action beyond the reuse items below.

- **DS-4 (LOW, positive) -- D2/level leakage handling is correct. [FACT]**
  Both feature builders compute the expanding statistic then `shift(1)` and assert the estimate is NaN
  on a player's first appearance ([shrinkage.py:121-124](../../model/forecast/shrinkage.py#L121),
  [level_estimators.py:103-106](../../model/forecast/level_estimators.py#L103)); pinned by
  `test_*_leakage_safe_on_first_appearance`. Idiom differs from `baselines` (expand-then-shift vs
  shift-then-expand) but is numerically identical for the mean (see PR-4).

### Analytics engineer

- **AE-1 (HIGH) -- the per-position scorer is re-implemented three times; metrics have no single source. [FACT]**
  `score_levels_by_position` ([level_estimators.py:112-131](../../model/forecast/level_estimators.py#L112)),
  `score_shrinkage_by_position` ([shrinkage.py:130-149](../../model/forecast/shrinkage.py#L130)), and
  `walk_forward_by_position` ([walkforward.py:158-177](../../model/eval/walkforward.py#L158)) are the
  **same loop** (per position: `_position_k`, groupby-gw, skip-thin, `precision_at_k`+`ndcg_at_k`,
  `grouped_spearman`, categorical sort, `set_index`). Any metric fix (e.g. tie-handling) must be made
  in three places, and only one of the three (none of the forecast pair) reports the harness-standard
  CI+coverage. **Fix:** one shared per-position scorer in the harness that returns
  `spearman + ci_lo + ci_hi + coverage + precision_at_k + ndcg_at_k + k + n_gw` (via
  `metrics.spearman_with_ci` + a shared top-K helper), consumed by all three.

- **AE-2 (MED) -- population filter re-typed instead of `population.canonical`. [FACT]**
  `mart[(mart["minutes"] > 0) & (~mart["is_dgw"].astype(bool))]...sort_values(...).reset_index(...)`
  is re-typed in [shrinkage.py:85-86](../../model/forecast/shrinkage.py#L85),
  [level_estimators.py:75-76](../../model/forecast/level_estimators.py#L75) and
  [prephase2_validation.py:29-30](../../model/eval/prephase2_validation.py#L29) -- the exact body of
  `population.canonical` ([population.py:13-16](../../model/eval/population.py#L13)), which is the
  documented single definition. `canonical` additionally coerces `minutes` with `to_numeric`
  (strictly safer; identical on the numeric mart). **Fix:** import `population.canonical`.

- **AE-3 (MED) -- frozen tables omit the CI/coverage columns the harness standardizes. [FACT]**
  The D2 and level tables predate the scorer and show only point estimates. Per the EVAL_DESIGN
  appendix every ranking gate now carries a block-bootstrap CI + coverage. This is the doc-side of DS-1
  / AE-1. **Fix:** once the code emits CIs, add `ci_lo/ci_hi` (and coverage) columns to both frozen
  tables with a dated note (values unchanged; columns added).

- **AE-4 (LOW) -- `prephase2_validation.py` re-inlines pop + a private grouped-spearman. [FACT]**
  `_population` ([:29](../../model/eval/prephase2_validation.py#L29)) and `_wp_spearman`
  ([:57-63](../../model/eval/prephase2_validation.py#L57)) duplicate `population.canonical` and
  `metrics.grouped_spearman`. Same SSOT drift as AE-1/AE-2 in a script that feeds D1's frozen note.
  **Fix:** reuse the harness primitives (numbers must reproduce; `_wp_spearman` uses `nanmean`, so
  verify the tolerance -- see plan).

### Platform SWE

- **SWE-1 (MED) -- private cross-module import `_position_k`. [FACT]**
  Both forecast modules import the underscore-private `_position_k` from `walkforward`
  ([level_estimators.py:26](../../model/forecast/level_estimators.py#L26),
  [shrinkage.py:35](../../model/forecast/shrinkage.py#L35)). Same layer (no import-linter breach), but a
  private symbol leaking across modules. **Fix:** promote to public (`position_k`) or absorb it inside
  the shared top-K helper (AE-1), so no caller reaches for the underscore. (The public constants
  `WARMUP_GW`, `MIN_ROWS_PER_POS`, `POSITIONS` are correctly imported, not re-hardcoded -- keep.)

- **SWE-2 (MED, reuse) -- `lvl_mean` re-derives `baselines.base_season`. [FACT]**
  `lvl_mean = pts.transform(lambda s: s.expanding().mean().shift(1))`
  ([shrinkage.py:90](../../model/forecast/shrinkage.py#L90),
  [level_estimators.py:84](../../model/forecast/level_estimators.py#L84)) is numerically identical to
  `baselines.base_season` (`shift(1).expanding().mean()`,
  [baselines.py:67](../../model/eval/baselines.py#L67)); the shrinkage docstring even asserts the
  equality ([:13](../../model/forecast/shrinkage.py#L13)) and `test_lvl_mean_matches_expanding_prior_mean`
  pins it. **Fix:** source `lvl_mean` from `baselines.base_season` **applied to the canonical
  population** (the equality only holds when both run on the `minutes>0`/DGW-excluded frame -- the
  standalone `base_season` on the *full* mart would include blanks and diverge; see plan caveat).

- **SWE-3 (LOW) -- `prior_expand` closure used inconsistently. [FACT]**
  `build_level_features` defines `prior_expand` ([level_estimators.py:81-82](../../model/forecast/level_estimators.py#L81))
  but `lvl_mean`/`lvl_median` bypass it and inline the expand-then-shift; only trim/huber/p75/p90 use
  it. Cosmetic; fold when touching the file.

- **SWE-4 (LOW, positive) -- D1's clustered bootstrap is NOT a redundant re-impl of `block_bootstrap_ci`. [FACT]**
  D1 resamples *players with relabeling then refits the MixedLM*
  ([variance_components.py:132-160](../../research/kernels/inferential/variance_components.py#L132)) --
  a cluster bootstrap of a variance-component refit, categorically different from
  `metrics.block_bootstrap_ci` (blocks of a per-GW metric series) and from
  `resampling.cluster_bootstrap_minutes_adjusted_rho` (rho-based). Do **not** "consolidate" it into
  either -- that would be wrong. Only the tiny percentile-CI tail (`np.percentile(reps, [lo,hi])`) is a
  micro-dup of `resampling._percentile_ci`; not worth a cross-layer import.

---

## 3. Action list by verb

- **REUSE** -- route the D2 + level Spearman gate through the shared CI machinery
  (`metrics.spearman_with_ci` / `scorer.score_gates`), gaining `ci_lo/ci_hi`+coverage. *(fixes DS-1, AE-1, AE-3; highest leverage; matches points_model.py:427 precedent)*
- **REUSE** -- replace the inline `minutes>0 & DGW` filter with `population.canonical` in `shrinkage.py:85`, `level_estimators.py:75`, `prephase2_validation.py:29`. *(AE-2, AE-4)*
- **REUSE** -- source `lvl_mean` from `baselines.base_season` on the canonical population. *(SWE-2)*
- **RESTRUCTURE** -- extract one shared per-position top-K scorer (prec@k/ndcg) used by `walkforward` + `level_estimators` + `shrinkage`, collapsing the triplicated loop. *(AE-1)*
- **RENAME / HARDEN** -- promote `_position_k` -> public `position_k` (or fold into the shared helper); drop the private cross-module import. *(SWE-1)*
- **MODIFY (doc)** -- add `ci_lo/ci_hi`(+coverage) columns to the frozen D2 + level tables; annotate GK as a degenerate ranker (ICC=0 -> full shrink); note GK's true incumbent bar is rolling-5; fix the "the shrinkage shrinkage buys" duplicate word (`predictive-phase1-icc-shrinkage.md` line 68). *(DS-2, AE-3)*
- **GO** -- nothing to delete. D2 is a documented recorded null kept for Phase 6 re-run; do **not** remove `shrinkage.py`. `_position_k`/`prior_expand` are refactored, not deleted.

---

## 4. Reproduction anchors (must still reproduce to 4dp after any change)

**D1 -- ICC table** (`mixed_effects_icc`, defaults `n_bootstrap=300`, `seed=12345`, `ci_level=0.95`,
`min_appearances=10`):

| pos | ICC | ICC 95% CI | sigma2_between | sigma2_within | LRT p | n_players |
|---|---|---|---|---|---|---|
| GK | 0.000 | [0.000, 0.027] | 0.000 | 7.51 | 0.50 | 25 |
| DEF | 0.056 | [0.000, 0.082] | 0.558 | 9.43 | 1.1e-19 | 145 |
| MID | 0.101 | [0.070, 0.122] | 0.835 | 7.40 | 6.4e-64 | 191 |
| FWD | 0.097 | [0.000, 0.143] | 0.974 | 9.10 | 1.1e-17 | 51 |

**D2 -- shrink vs mean** (Spearman / prec@k / ndcg, mean then shrunk):

| pos | mean rho | shrunk rho | mean p@k | shrunk p@k | mean ndcg | shrunk ndcg |
|---|---|---|---|---|---|---|
| GK | 0.041 | 0.022 | 0.360 | 0.329 | 0.460 | 0.458 |
| DEF | 0.185 | 0.174 | 0.341 | 0.351 | 0.426 | 0.440 |
| MID | 0.336 | 0.316 | 0.283 | 0.290 | 0.435 | 0.438 |
| FWD | 0.349 | 0.330 | 0.492 | 0.492 | 0.511 | 0.511 |

**Level study -- within-position Spearman headline:** GK mean 0.041 (best EW 0.076); DEF mean 0.185
(median 0.189 / Huber 0.187); MID mean 0.336 (EW 0.341); FWD mean 0.349 (**EW 0.371**).

These values do not move under the plan below; the migration is additive (new CI/coverage columns) and
reuse (numerically identical substitutions).

---

## 5. Sequenced plan (behavior-preserving; each step = green tests + numbers reproduced)

Order is additive/reuse first, then structure, then naming/doc -- the safest for a frozen oracle.
Per step: `pytest` the touched tests + `ruff` + `lint-imports`, then re-run the notebook/functions on
the real mart and diff against Section 4.

- **S0 -- baseline snapshot.** Run `phase1_icc_shrinkage.ipynb` + `level_estimators.ipynb` (or call
  the three functions) on the live mart; capture the exact tables. Confirm
  `pytest tests/test_model_forecast_{shrinkage,level_estimators}.py tests/test_kernels_inferential_variance_components.py`
  green + `ruff` + `lint-imports` clean. *(gate: matches Section 4)*

- **S1 -- REUSE population + base_season (pure substitution).** Swap the inline filter ->
  `population.canonical`; source `lvl_mean` <- `baselines.base_season(population.canonical(mart))`.
  *Caveat:* keep the call on the canonical frame -- `base_season` on the full mart would include blanks
  and diverge. *(gate: D2 + level Spearman/p@k/ndcg reproduce to 4dp; leakage tests still pass)*

- **S2 -- RESTRUCTURE the shared top-K scorer.** Extract one harness helper returning
  `spearman+precision_at_k+ndcg_at_k+k+n_gw` (+ CI columns from `spearman_with_ci`); route
  `walk_forward_by_position`, `score_levels_by_position`, `score_shrinkage_by_position` through it.
  Promote `_position_k` -> public inside that helper (SWE-1). *(gate: all three tables reproduce; it is
  the same loop; update the moved-symbol imports)*

- **S3 -- REUSE the CI on the gate + emit columns.** Have the shared helper (S2) attach `ci_lo/ci_hi`
  (block bootstrap, `seed=0` per `scorer` default) + `coverage`. Update
  `test_model_forecast_level_estimators.py:57` (exact-column assertion) to the new column list.
  Regenerate the D2 + level tables and add the CI/coverage columns to both frozen docs with a dated
  note (point estimates unchanged). *(gate: Spearman/p@k/ndcg unchanged to 4dp; CI columns new)*

- **S4 -- doc hygiene (no code).** GK degeneracy note + rolling-5 reference note in the D2 doc; fix the
  "shrinkage shrinkage" typo; optional AE-4 cleanup of `prephase2_validation.py` (verify the X2/X6
  numbers reproduce -- `_wp_spearman` uses `nanmean` vs `grouped_spearman`'s `mean`, so confirm no
  all-NaN GW changes a value before swapping).

**Out of scope (do not touch this run):** D2's *verdict* (stays a recorded null); the cross-season
shrink target / FWD recency tilt (Phase 6); any re-fit or re-tuning of D1 (bootstrap n/seed are
reproduction-load-bearing); the metric *definitions* themselves; deleting `shrinkage.py`.

---

## 6. Summary + highest-leverage move

```
- Phase 1 D1 is solid (ICC + clustered-bootstrap CI + boundary-corrected LRT + normality cross-check).
- D2 + the level study hand-roll a per-position gate that is triplicated with walk_forward_by_position
  and, unlike Phase 3.0, carries NO confidence interval -- the "within noise" null is asserted, not shown.
- Population filter, lvl_mean(==base_season), and _position_k are re-typed/private-imported, not reused.
- Fix is additive+reuse: route the gate through the shared CI machinery, extract one top-K scorer,
  swap in population.canonical / base_season. Frozen numbers are preserved; CI/coverage columns are new.
- Keep D2 (documented recorded null for Phase 6); nothing to delete.
```

**Single highest-leverage move:** put a block-bootstrap **CI on the D2 gate** by routing
`score_shrinkage_by_position` (and `score_levels_by_position`) through the shared
`spearman_with_ci`/`score_gates` machinery -- exactly as `points_model.py:427` already does. It closes
the one HIGH correctness/honesty gap (an untested "within noise" claim), retires the triplicated loop,
and drops the private `_position_k` import in a single behavior-preserving change.
