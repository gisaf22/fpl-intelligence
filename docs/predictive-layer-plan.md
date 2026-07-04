# Predictive-Layer Plan — Modeling, Forecasting & Decision Machinery

**Authority:** review-board plan (panel-data statistician · ML forecasting engineer · FPL domain analyst · skeptical reviewer)
**Date authored:** 2026-07-04
**Scope:** Sequence the machinery that turns validated signals into gated forecasts and decisions. Prescribe-only: this document plans the work; it moves no code until a phase is opened.
**Precondition:** the diagnostic layer is closed at Q1/Q1b/Q2 (see [research/diagnostic/DIAGNOSTIC_DESIGN.md](../research/diagnostic/DIAGNOSTIC_DESIGN.md)); the four LENS families (form/fixture/availability/market) are locked and run.

---

## 0. How to read this plan

Each **item** carries a fixed template — *What · Why · Where · Machinery · Recruiter signal · Prereq · Gate*.
Each **phase** carries a **promotion gate**: the measurable condition that must pass before the next phase opens. A phase without a passing gate does not advance.

**Ordering rule:** dependency + de-risking — benchmarks and the validation harness before any model; calibration before decisions. Never ordered by sophistication.

**Hard constraints (every item must honor):**
- **Rung boundaries** — association vs predictive kept distinct; predictive claims require lagged design.
- **Lag / leakage discipline** — lag-1 minimum, `.shift(1)` before `.rolling()`; every model asserts no-future-rows before scoring.
- **Locked LENS designs** — form/fixture/availability/market `validate/` designs are immutable; new family work lands in that family's **`explore/`** dir.
- **Notebooks-don't-emit** — a notebook never writes into `findings → registry → model`; promotion is a code+gate path.
- **Import-linter contracts** — layer order `dal → research → model → serve` preserved.
- **Dedup** — extend `research/kernels/inferential/variance_components.py` and `research/kernels/diagnostic/panel.py`; never rebuild them.

**Board recommendation (single, not consensus):** build **Phase 0 (baselines + harness)** and **Phase 1 (hierarchical/ICC)** first. They are cheap, low-risk, and *everything downstream is measured against them*. Phase 1 also formalizes work already done (Q1/Q1b), so it raises rigor without new surface area. Defer all glamour (simulation, Bayesian) until the benchmark and the correct target-distribution are locked.

---

## Phase 0 — Benchmarks everything is measured against

*Nothing downstream is claimable without these. Build first.*

### 0.1 — Baseline suite
- **What:** season-avg, rolling-avg, last-GW, position-mean predictors of next-GW points.
- **Why:** no model or signal can be said to "add value" without the naive floor; also *verifies* the unproven hypotheses "level persists / deviations mean-revert."
- **Where:** `model/eval/baselines.py` (new).
- **Machinery:** simple estimators + lag-1 alignment.
- **Recruiter signal:** defines the null before modeling — senior discipline.
- **Prereq:** current single-season mart suffices.
- **Gate:** reproducible per-GW scores on the harness.

### 0.2 — Walk-forward / expanding-window harness
- **What:** temporal CV substrate (train ≤ GW *t*, test *t+1*), reused by every later model.
- **Why:** random splits leak; expanding-window is the only valid evaluation for time series.
- **Where:** `model/eval/walkforward.py` (new).
- **Machinery:** expanding/rolling windows, per-GW scoring, leakage assertion.
- **Recruiter signal:** understands temporal validation — the top forecasting-credibility marker.
- **Prereq:** single-season suffices; more seasons strengthen it.
- **Gate:** passes a no-future-rows leakage assertion on every fold.

> **Phase 0 promotion gate:** baselines produce reproducible next-GW scores; harness passes the leakage assertion. **Baseline numbers frozen as the benchmark** for all later phases.

---

## Phase 1 — Formalize what we already found

*Cheap, low-risk, highest single credibility gain. The concrete first modeling piece.*

### 1.1 — Hierarchical / mixed-effects + ICC + partial-pooling shrinkage ⭐
- **What:** random-intercept model for points; ICC; shrunken player estimates.
- **Why:** correct model class for panel data; formalizes Q1/Q1b's between/within split; regularizes small-sample players (thin FWD/GK, ≥10-game floors).
- **Where:** extend `research/kernels/inferential/variance_components.py` (`mixed_effects_icc()` beside `decompose_variance()`); consume from a notebook augmenting `points_variance_ceiling.ipynb`.
- **Machinery:** `statsmodels` MixedLM (or `pymer4`); ICC from variance components; empirical-Bayes `u_i`.
- **Recruiter signal:** knows the data isn't iid — the strongest single maturity marker.
- **Prereq:** single-season, within-season panel suffices (no cross-season pooling here).
- **Gate:** see phase gate.

> **Phase 1 promotion gate:** ICC point estimate reconciles with Q1's bootstrap between-share; **σ²_between CI excludes 0**; shrunken player estimates beat raw player means on held-out weeks (walk-forward). See §Concrete first piece.

---

## Phase 2 — Model the target correctly

### 2.1 — Count models: NB / Hurdle / ZIP (with overdispersion diagnosis)
- **What:** model point-components (goals ~ Poisson(xG), assists ~ Poisson(xA), CS ~ Bernoulli) with the right count family.
- **Why:** the target is zero-inflated, over-dispersed counts — Poisson is wrong; diagnosing that is the maturity move.
- **Where:** `model/forecast/count_models.py` (new).
- **Machinery:** `statsmodels` GLM (NB), hurdle/ZIP; dispersion test.
- **Recruiter signal:** fits distributions to data, not habit.
- **Prereq:** component columns (goals/assists/CS/xG/xA) present in mart — verify before build.
- **Gate:** overdispersion test justifies NB/hurdle over Poisson.

### 2.2 — Regularized signal combination (elastic net)
- **What:** penalized fit combining the families' *informative* signals into one predictor.
- **Why:** signals are collinear (documented in `signal_correlation`); EN/LASSO handles it principledly; supersedes ad-hoc composition weights.
- **Where:** extend `model/assemble/composition_study.py`.
- **Machinery:** `sklearn` ElasticNetCV inside the walk-forward harness.
- **Recruiter signal:** principled feature selection under collinearity.
- **Prereq:** Phase 0 harness + the families' informative-signal set.
- **Gate:** beats baseline and the single best signal on held-out GWs.

> **Phase 2 promotion gate:** overdispersion test justifies the chosen count family; the combined model beats **P0 baseline AND best single signal** on walk-forward.

---

## Phase 3 — Distributions & uncertainty

*The distinctive, FPL-native layer.*

### 3.1 — Generative component model + Monte-Carlo simulator
- **What:** simulate components through the real scoring rules → full points distribution, haul probability, captaincy ceiling.
- **Why:** decisions need distributions, not point estimates; mirrors the true data-generating process.
- **Where:** `model/forecast/simulator.py` (new); reuses `domain/fpl_scoring.py`.
- **Machinery:** Monte-Carlo sampling from the Phase-2 component models.
- **Recruiter signal:** probabilistic thinking + simulation — rare and distinctive.
- **Prereq:** Phase 2 component models fitted.
- **Gate:** simulated mean reconciles with the direct point forecast (sanity).

### 3.2 — Bookmaker odds as external benchmark & signal
- **What:** convert odds → implied returns; use as both a signal and a yardstick.
- **Why:** the market is the sharpest external baseline; if you can't beat it, learn early.
- **Where:** `model/eval/` (benchmark) + `research/families/fixture/explore/` (as signal — explore dir is unlocked).
- **Machinery:** odds de-vig; calibration vs realized.
- **Recruiter signal:** benchmarks against the strongest external predictor.
- **Prereq:** **odds data required — flag as blocker if absent.**
- **Gate:** none (comparator).

> **Phase 3 promotion gate:** simulator mean reconciles with the point forecast; haul-probability has face validity; bookmaker comparison computed if odds data present.

---

## Phase 4 — Trust the probabilities

### 4.1 — Calibration + proper scoring rules
- **What:** Brier, log-loss, reliability diagrams (haul prob); CRPS (full distribution).
- **Why:** a probability is only useful if calibrated; point-accuracy can't reveal miscalibration.
- **Where:** `model/eval/calibration.py` (new).
- **Machinery:** reliability curves; isotonic/Platt recalibration; CRPS.
- **Recruiter signal:** evaluates uncertainty honestly — most projects never do.
- **Prereq:** Phase 3 probabilistic outputs.
- **Gate:** reliability within tolerance (recalibrate if not); CRPS beats baseline.

> **Phase 4 promotion gate (hard):** probabilities pass calibration tolerance. **No decisions built on miscalibrated probabilities.**

---

## Phase 5 — Decision-level value

*The only metric that ultimately matters.*

### 5.1 — Decision evaluation
- **What:** captain success, transfer gain, ranking quality (NDCG/Spearman), chip value — vs baseline.
- **Why:** RMSE ≠ FPL usefulness; this is what a manager (and a hiring manager) cares about.
- **Where:** `serve/eval/decisions.py` (new).
- **Machinery:** backtested decision rules over walk-forward; ranking metrics.
- **Recruiter signal:** connects models to business value — the strongest senior signal.
- **Prereq:** Phases 0–4 complete.
- **Gate:** decision rules beat baseline decisions.

> **Phase 5 promotion gate:** captain/transfer/ranking rules beat baseline decisions; only then is a model promoted to `serve/`.

---

## Phase 6 — Situational / advanced

*Build only if data supports; several are single-season-blocked.*

### 6.1 — Survival / hazard for availability
- **What / Why:** time-to-injury / minutes as time-to-event; correct framing for availability.
- **Where:** `research/families/availability/explore/` (explore dir unlocked).
- **Machinery:** Kaplan-Meier / Cox.
- **Recruiter signal:** right framing for time-to-event.
- **Prereq:** sufficient event counts — verify first.
- **Gate:** event count adequate; beats a naive availability baseline.

### 6.2 — Cross-season drift
- **What / Why:** season-to-season change in feature relationships / meta drift.
- **Where:** `research/foundation/temporal/`.
- **Machinery:** rolling-relationship comparison across seasons.
- **Recruiter signal:** assesses stability across eras.
- **Prereq:** **≥ 2 seasons — BLOCKED on single-season data.**
- **Gate:** ≥ 2 seasons present before run.

### 6.3 — Full Bayesian hierarchical (PyMC)
- **What / Why:** showcase upgrade of 1.1 with full posterior uncertainty.
- **Where:** `model/forecast/` (optional).
- **Machinery:** PyMC / Stan.
- **Recruiter signal:** full probabilistic modeling.
- **Prereq:** empirical-Bayes version (1.1) proven out first.
- **Gate:** posterior predictive checks pass; matches 1.1 on the shared estimand.

### 6.4 — Mutual information / transfer entropy — **DROP**
- Monotone associations are already captured by Spearman/partial; MI adds nothing interpretable here. Transfer entropy for market lead-lag is exotic overkill. Not built.

> **Phase 6 promotion gate:** each item's data prerequisite verified met before it runs.

---

## Concrete first piece — hierarchical / ICC vs Q1/Q1b

**Estimand.** Q1 asked how much points variance is between-player vs within-player and answered it by a **sum-of-squares partition** (`variance_components.decompose_variance`) with a **cluster bootstrap** for uncertainty. The hierarchical model reframes that as a **variance-components model** and reads the same split off fitted parameters.

**Model (per position):**
```
points_{i,t} = β0 + u_i + ε_{i,t}
u_i    ~ N(0, σ²_between)   # player random intercept
ε_{i,t} ~ N(0, σ²_within)   # week-to-week residual
ICC = σ²_between / (σ²_between + σ²_within)
```
`ICC` **is** Q1's between-share — now a **model parameter with a standard error**, not a bootstrap percentile.

**What it adds beyond Q1 (why it's worth doing):**
1. **Inference on the components** — likelihood-based SE/CI and an LRT on σ²_between ("is between-player variance significantly non-zero"), which the SS partition only approximated.
2. **Shrunken player estimates** — `u_i` are partial-pooled (empirical-Bayes) skill estimates that regularize small-sample players — a *new artifact* Q1 could not produce.
3. **Extensible** — adding signals as fixed effects yields Q1b/Q2 inside one model (`points ~ signal + minutes + (1|player)`), unifying three diagnostic reads under one estimator.

**Where / dedup:** add `mixed_effects_icc()` beside `decompose_variance()` in `research/kernels/inferential/variance_components.py` (keep both — SS partition = descriptive read, ICC = inferential read); consume from a notebook that augments `points_variance_ceiling.ipynb`, not replaces it.

**Validation / gate:** ICC reconciles with Q1's bootstrap between-share (agreement check); σ²_between CI excludes 0; shrunken `u_i` predict held-out player weeks better than raw player means on the walk-forward harness.

---

## Build order (one line)

`0.1 → 0.2 → 1.1 → 2.1 → 2.2 → 3.1 → (3.2 if odds) → 4.1 → 5.1 → 6.x as data permits`
