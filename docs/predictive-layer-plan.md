# Predictive Layer — Master Plan & Status

**Single source of truth** for the predictive layer: phased plan, live status, claims discipline,
assumptions register, and data inventory. Supersedes and folds in the former `predictive-phase1-design`,
`predictive-phase2-design`, `analysis-strategy-review`, and `predictive-plan-assumptions-audit` docs.
Frozen per-phase *results* live separately (linked in §1) and are the immutable evidence trail.

**Last updated:** 2026-07-06 · **Now at:** Phase 1 complete → Phase 2 (designed, not built).

---

## 1. Status dashboard

| Phase | Item | Status | Gate result | Evidence |
|---|---|---|---|---|
| 0.1 | Baseline suite | ✅ complete | reproducible per-GW scores | [results](studies/results/predictive-phase0-baselines.md) |
| 0.2 | Walk-forward harness | ✅ complete | leakage assertion passes | same |
| pre-1 | Point-estimate (level) study | ✅ complete | shrink toward the **mean** | [results](studies/results/predictive-level-estimators.md) |
| 1 · D1 | ICC / variance components | ✅ **shipped** | reconciles w/ Q1; σ²_between real (LRT) | [results](studies/results/predictive-phase1-icc-shrinkage.md) |
| 1 · D2 | EB shrinkage ranker | ✅ built, ⛔ **null** | does NOT out-rank raw mean → shelved | same |
| 2.1 | Count models (NB/ZIP/Bernoulli) | 📐 designed, not built | — | §3 |
| 2.2 | Regularized signal combination | 📐 planned | — | §3 |
| 3.1 | Monte-Carlo simulator | 🗒 planned | — | §3 |
| 3.2 | Bookmaker odds benchmark | 🚧 blocked (odds data) | — | §3 |
| 4.1 | Calibration + proper scoring | 🗒 planned | — | §3 |
| 5.1 | Decision evaluation | 🗒 planned (build gap) | — | §3 |
| 6.x | Survival / drift / PyMC | 🗒 planned (6.2 data-blocked) | — | §3 |

Legend: ✅ done · 📐 designed · 🗒 planned · 🚧/⛔ blocked/null.

**Open debt on shipped work:** D1's ICC uses a Gaussian LMM on a count target — variance *share* holds,
but its CIs/LRT assume normality (see A-X2). Sensitivity check owed before the ICC p-values are cited.

---

## 2. Claims discipline (the language guardrail — check every notebook / results doc / commit)

The most repeated error is over-claiming the *rung*. Match the verb to what was actually done.

| Verb / claim | Means | Allowed only when | Tempting WRONG use → RIGHT use |
|---|---|---|---|
| **associate / correlate** | X and Y move together | any rung; contemporaneous OK | — |
| **explain / decompose** | partition observed variance (descriptive/inferential) | e.g. ICC, between/within | "identity *predicts* points" → "identity *explains* a share of points variance" |
| **rank** | order units by a score; metric = Spearman/precision@k | within-position; conditional on appearance | "we *predict* his score" → "we *rank* players who played, within position" |
| **predict / forecast** | estimate a *future* value from strictly-prior data | lagged design + P(play) modeled (end-to-end) | calling a walk-forward *ranker* a *forecaster* → say "rank, given played" until P(play) is modeled |
| **cause / drive** | intervention would change Y | **never** (we stay at Pearl rung 1) | "form *drives* returns" → "form *is associated with* returns" |

**Standing caveats to attach, not assume away:**
- **Conditional on appearance** — every metric so far is "given the player featured" (see A-X1). Not end-to-end forecast skill.
- **Contemporaneous ≠ lagged** — Q1/Q1b/D1 are same-week *descriptions/associations*, not predictions.
- **Variance-share ≠ prediction** — ICC says how much is durable level, not how well we predict it.
- **"Beats baseline" is a claim** — only after clearing the per-position walk-forward gate, with uncertainty.

---

## 3. Phases — goal · done · left · gate · key decisions

**Ordering rule:** dependency + de-risking (benchmarks → target shape → uncertainty → calibration →
decisions). Never ordered by sophistication. **Build order:** `0.1→0.2→1.1→[pre-2 sprint]→2.1→2.2→3.1→(3.2 if odds)→4.1→5.1→6.x`.

**Hard constraints (every item):** rung boundaries (assoc vs predictive); lag/leakage (`.shift(1)` before
`.rolling()`, no-future-rows assertion); locked LENS `validate/` designs immutable (new work in `explore/`);
notebooks-don't-emit; import-linter `dal→research→model→serve`; extend kernels, don't rebuild.

### Phase 0 — Benchmarks ✅
- **Goal:** the naive floor every model must beat; a leak-proof temporal-CV harness.
- **Done:** season-avg/rolling/last-GW/position-mean baselines; per-position walk-forward; **frozen bars** GK ~0.06, DEF 0.17, MID 0.31, FWD 0.33 (within-position Spearman). Cross-position pooling abolished.
- **Key decisions:** ranking metrics (not RMSE — skewed target); within-position only; common eval set.

### Phase 1 — Formalize identity ✅ (D1 ships, D2 null)
- **Goal:** between/within split as a model parameter; test if shrinkage out-ranks the raw mean.
- **Done — D1:** `mixed_effects_icc()` — ICC ~0.06–0.10 outfield, ~0 GK; small but real (LRT decisive); reconciles with Q1 SS-share.
- **Done — D2:** `lvl_shrunk` EB ranker — **null**: slightly *worse* than raw mean everywhere (thin between-slice + λ reorders by games-played). Shelved, kept for cross-season re-run.
- **Left:** the A-X2 count-GLMM sensitivity check on D1.

### Phase 2.1 — Count models 📐 (next)
- **Goal:** model the target's true shape — first phase with **features (X)**.
- **Decision — components→points map (not direct `total_points`).** Model the point-*drivers* and compose via the FPL scoring rule. Respects zero-inflation; interpretable; position-aware. Cost: more models + the map (bonus/cards/saves deferred, share to be quantified).
- **Families:** goals & assists → NB or ZIP (rare, over-dispersed); clean sheet → **Bernoulli** (binary, no rate). Family chosen by an **over-dispersion test**, not habit.
- **Minutes — TESTED, not a hard-coded offset.** Constant per-minute rate is an *assumption* (late-game clustering, sub selection, the 60′ kink). Estimate the `log(minutes)` coefficient freely → lock as offset only if β≈1; inspect per-minute rate by band; spline if non-proportional.
- **Features:** minimal, **strictly-prior** process stats (lagged xG/xA/fixture). Reuse the Phase-0 harness unchanged.
- **Folded-in:** the never-run **autocorrelation / form-persistence** read (via `serial.py`) enters here as a *gated* "do form features earn their place" test.
- **Gate:** (1) over-dispersion test justifies the family; (2) composed E[points] beats the Phase-0 baseline **and** (3) the best single signal, per position, on walk-forward. Else ship the dispersion diagnosis as an honest null.

### Phase 2.2 — Regularized combination 📐
- Elastic-net over the families' informative signals (collinear). Sanity-probe against a non-linear reference (interactions). Gate: beats baseline + best single signal.

### Phase 3 — Distributions & uncertainty 🗒
- **3.1 simulator:** Monte-Carlo components through the scoring rule → points distribution, haul prob. **Caveat:** components co-move (A-A2.1); an independent-component sim mis-estimates hauls. **Amendment:** the old "sim mean ≈ point forecast" gate is circular — move the *distributional* validation into Phase 4.
- **3.2 odds:** external benchmark. 🚧 **blocked on odds data.**

### Phase 4 — Trust the probabilities 🗒 (hard gate)
- Reliability diagrams, Brier/log-loss, CRPS; isotonic/Platt recal (CV — overfits on ~35 GWs). **Pre-register the calibration tolerance.** No decisions on miscalibrated probabilities.

### Phase 5 — Decision value 🗒 (build gap, not data gap)
- Captain / transfer / ranking / chip value vs baseline decisions. **Needs P(play) first** (A-X1). **Single-season backtest is one path** → block-bootstrap error bars, don't rank on a point estimate (A-A5.1).
- **Data is present** (`purchase_price`, `ownership_count`, `transfers_in/out`) — Phase 5 is an un-built decision layer, not data-blocked.

### Phase 6 — Situational 🗒
- 6.1 survival for availability (verify event counts); 6.2 cross-season drift (**data-blocked: needs ≥2 seasons**); 6.3 full-Bayesian PyMC (after EB proven); 6.4 MI/transfer-entropy **dropped**.

---

## 4. Assumptions register (living — each: `open / tested-holds / tested-fails / accepted`)

Board = panel-data econometrician · ML forecasting engineer · FPL analyst · skeptical statistician · pipeline engineer.
No phase promotes with an unresolved assumption it depends on.

| ID | Assumption baked in | Phase | Risk | Test / mitigation | Sev | Status |
|---|---|---|---|---|---|---|
| X1 | **Conditional-on-appearance is the right target** | all | manager picks *before* kickoff; flatters accuracy | score the unconditional (incl. DNP=0) gap; model P(play) before Phase 5 | High | open |
| X2 | **Gaussian LMM on a count target** | 1 (shipped) | ICC CIs/LRT assume normality the target violates | refit ICC via NB-GLMM or distribution-free bootstrap; caveat D1 | High | open (debt) |
| X3 | **Single-season stationarity** | all | regime breaks (managers, winter, congestion) | rolling-block stability read | Med | open |
| X4 | **DGW exclusion is harmless** | all | DGWs are the highest-value moments; stack is silent there | state gap; scope DGW = sum of two single-GW forecasts before Phase 5 | Med | open (product gap) |
| X5 | **Player identity stable within season** | 1 | transfers / role changes break the fixed intercept | flag movers; ICC robustness excl. them | Low-Med | open |
| X6 | **Process (xG) forecasts components better than realized (goals)** | 2 | *goals are equation-inputs (excluded as contemporaneous signals) but Phase-2 targets;* real test = lagged xG vs lagged goals → future component (one sub-question, not the main bet). xG same-match → leak risk | `.shift(1)`; head-to-head test; coverage check | Med | open |
| A2.1 | **Component independence** in the points map | 2/3 | mean OK, but haul-probability/variance wrong (components co-move) | test residual cross-correlation; joint model in Phase 3 | Med | open |
| A2.2 | **Deferred scoring parts (bonus/cards/saves) are minor** | 2 | bonus is a large, correlated share of premium points | quantify un-modeled points share before "good enough" | Med | open |
| A5.1 | **Single-season decision backtest is enough** | 5 | one path → overfits the season's meta | block-bootstrap error bars on every decision claim | High | open |
| A0.2 | **Operational thresholds** (warmup=3, k=20, floors) | 0 | arbitrary; shape every comparison | ±1 sensitivity check once | Low | open |

**Main Phase-2 bet (the headline, stated plainly):** *do situation features improve within-position
ranking over the identity-only baseline, on held-out GWs, conditional on appearance?* Everything
downstream rests on this being yes.

---

## 5. Data inventory & strategy

**Have (verified in mart):** points + components (`goals_scored`, `assists`, `clean_sheets`,
`goals_conceded`, `saves`, `bonus`, `bps`), process (`xg`, `xa`, `xgi`, `ict_index`, + roll3/roll5),
minutes (+trend/roll), fixture context, `was_home`, **market** (`purchase_price`, `ownership_count`,
`transfers_in`, `transfers_out` — validated weak: ownership rho≈0.16 MID/DEF, price≈0.12 DEF).

**Don't have / need:** **≥2 seasons** (biggest unlock — cross-season drift, cohorts, D2 re-run,
out-of-season validation); **bookmaker odds** (Phase 3.2); explicit **price-change / chip** state (light
derivation from per-GW price).

**Segmentation vs cohort:** segmentation is pervasive (per-position, minutes-bands, quintiles). **Cohort
/ longitudinal analysis has never been done** — blocked mainly by single-season data; a genuine gap.

**Anti-sprawl / discipline:** tie every analysis to a **gate or a decision**, not curiosity. The risk is
breadth creep, not over-reach — the gate system already prevents building glamour prematurely.

**Highest joint FPL × recruiter × practice value:** count/GLM target (Phase 2) · calibration (Phase 4) ·
survival-for-availability (Phase 6.1). Reserve "reach" for the rare muscles (survival, calibration).

---

## 6. Immediate next — pre-Phase-2 validation sprint

Small, cheap code that tests the biggest baked-in bets *before* writing the count models:
1. **X6** — lagged xG vs lagged goals as predictors of the *future* component (per position).
2. **X2** — count-GLMM (or bootstrap) ICC sensitivity: does D1's split/ordering survive dropping normality?
3. **A2.2** — quantify the deferred-points share (bonus/cards/saves).
4. Add a **component-target leakage assertion** to the Phase-2 harness contract.

Then build 2.1. Prove the hypotheses, then model.
