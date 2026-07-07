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

**Shipped-work debt X2 — resolved (2026-07-06):** D1's Gaussian-LMM ICC was stress-tested with a
distribution-free bootstrap — ordering + small magnitude hold without normality; GK exact-0 is a
bias-corrected reading (caveat now on the D1 result). `tested-holds`, no re-work. See §4 / §6.

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

Each item carries the full build spec: **Goal · Where (module) · Machinery · Key decisions · Prereq · Gate · Risks**, plus **Done/Left** for shipped phases.

### Phase 0 — Benchmarks ✅
- **Goal:** the naive floor every model must beat, and a leak-proof temporal-CV harness reused by every later phase.
- **Where:** `model/eval/baselines.py`, `model/eval/walkforward.py`.
- **Machinery:** expanding-window walk-forward (train ≤ GW *t*, test *t+1*); within-player `.shift(1)` before rolling; per-GW scoring; leakage assertion.
- **Done:** baselines `base_last`, `base_roll3`, `base_roll5`, `base_season`, `base_posmean`; per-position walk-forward; **frozen bars** GK ~0.06, DEF 0.17, MID 0.31, FWD 0.33 (within-position Spearman). Findings: *level persists* (season-avg best), *deviations mean-revert* (last-GW worst), *identity dominates* (position-mean can't rank within position).
- **Key decisions:** ranking metrics not RMSE (zero-inflated/haul-dominated target); **within-position only** (cross-position pooling abolished — squads fill under quotas); common evaluation set (rows where all baselines defined) so comparisons aren't a coverage artifact; tie-aware precision@k; `WARMUP_GW=3`, `MIN_ROWS_PER_POS=10`, `TOP_K=20` (operational — A0.2).
- **Prereq:** single-season mart. **Gate (met):** reproducible per-GW scores; no-future-rows assertion passes on every fold. **Risks:** A0.2 arbitrary thresholds; conditional-on-appearance (X1) inherited by everything downstream.

### Phase 1 — Formalize identity ✅ (D1 ships, D2 null)
Two deliverables sharing a model but computed differently — must not be conflated:

| | **D1 — ICC inference** | **D2 — shrunk ranker** |
|---|---|---|
| Question | is between-player variance real, how big? | does shrinkage out-rank the raw mean? |
| Fit | whole-season, per position, one shot | walk-forward, strictly-prior only |
| Estimator | statsmodels MixedLM (REML) | closed-form empirical-Bayes |
| Output | σ²_between, σ²_within, ICC+CI, LRT | `lvl_shrunk` scored on the harness |

- **Model (per position):** `points_{i,t} = β0 + u_i + ε_{i,t}`, `u_i ~ N(0,σ²_between)`, `ε ~ N(0,σ²_within)`, `ICC = σ²_between/(σ²_between+σ²_within)`. ICC **is** Q1's between-share as a parameter with an SE.
- **D2 formula:** `lvl_shrunk = μ_pos + λ·(mean_i − μ_pos)`, `λ = n_i/(n_i + σ²_within/σ²_between)` — all from strictly-prior rows; variance ratio by method-of-moments per evaluated GW (no MixedLM refit in the loop). Few games ⇒ λ→0 ⇒ shrink to position mean; many ⇒ λ→1 ⇒ trust the player.
- **Where:** `research/kernels/inferential/variance_components.py` (`mixed_effects_icc` — D1); `model/eval/shrinkage.py` (`lvl_shrunk` — D2). Both tested.
- **Population parity (D1↔Q1):** `minutes>0`, DGW excluded, `min_appearances=10`, per position, whole season. ICC = SS-share only for a balanced panel; ours is unbalanced → reconcile to *tolerance*, not equality.
- **Done — D1:** ICC ~0.06–0.10 outfield, ~0 GK; small but **statistically real** (LRT decisive DEF/MID/FWD; GK null p=0.5); reconciles with Q1 SS-share (ICC slightly below — expected unbalanced-panel gap).
- **Done — D2:** **null** — slightly *worse* than raw mean at every position (thin between-slice + player-specific λ reorders by games-played, adding sample-size noise to the rank). Shelved, kept in-repo for a cross-season re-run.
- **Left:** none — the **X2 sensitivity** check is done (distribution-free bootstrap: conclusions robust; GK caveat recorded on the D1 result).
- **Gate (met, D1):** reconciles with Q1; σ²_between real where Q1 found it. **Failed (D2):** doesn't out-rank → pre-registered fallback = ship D1, record D2 null. **Risks:** X2 (Gaussian-on-counts debt), X5 (movers break the fixed intercept).

### Phase 2.1 — Count models 📐 (next)
- **Goal:** model the target's true shape — the **first phase with features (X)**.
- **Where:** `model/forecast/count_models.py` (new); scored on the Phase-0 harness unchanged; notebook `model/forecast/phase2_count_models.ipynb`.
- **Machinery:** statsmodels GLM (Poisson/NB), hurdle/ZIP, logistic; Cameron–Trivedi / LRT dispersion test; component→points composition via `domain/fpl_scoring.py`.
- **Decision — components→points map (NOT direct `total_points`).** Model the point-*drivers* and compose via the known FPL scoring rule. *Why:* respects the zero-inflated data-generating process (each component's zeros modeled where they live); interpretable; position-aware scoring falls out of the map. *Cost:* several models + the map; errors compound; more tests.

  | Component | Column | Family (confirm by test) | Positions |
  |---|---|---|---|
  | Goals | `goals_scored` | NB or ZIP (rare, over-dispersed) | MID, FWD (DEF secondary) |
  | Assists | `assists` | NB or ZIP | MID, FWD, DEF |
  | Clean sheet | `clean_sheets` | **Bernoulli/logistic** (binary — no rate) | GK, DEF, (MID) |

  Only *count* components take Poisson/NB; a binary outcome (conceded 0 or not) is Bernoulli and yields `P(clean sheet)` directly. Saves/bonus/cards deferred as fixed scoring arithmetic — **quantify the un-modeled points share** (A2.2) before "good enough".
- **Minutes — TESTED, not a hard-coded offset.** A log-minutes offset (coef=1) *asserts* a constant per-minute rate — likely false (late-game clustering, subs = selected population, the 60′ appearance/CS kink). Procedure: (1) enter `log(minutes)` with a **freely estimated** coefficient β → lock as offset only if β≈1; (2) inspect empirical per-minute component rate across bands 0–30/30–60/60–90 per position; (3) escalate to minutes-band dummies or a spline if non-proportional.
- **Features (X):** minimal, **strictly-prior** process stats — goals rate ← lagged `xgi`/`xg`; assists ← lagged `xa`/`creativity`; clean sheet ← `fixture_context`, lagged `goals_conceded_roll3`, `was_home`. `.shift(1)` enforced; component-target leakage assertion added to the harness contract.
- **Folded-in read:** the never-run **autocorrelation / form-persistence** study (via `research/kernels/diagnostic/serial.py`) enters here as a *gated* question — report within-player lag-1 autocorrelation per position, and test whether a lagged-form feature earns its place over the level-only baseline.
- **Prereq (verified):** component columns present in mart. **Gate:** (1) over-dispersion test justifies NB/ZIP over Poisson; (2) composed E[points] beats the Phase-0 baseline **and** (3) the best single signal, per position, walk-forward. Else ship the dispersion diagnosis as an honest null.
- **Risks:** X6 (xG>goals unproven — one sub-question), A2.1 (component independence — mean OK, haul-prob wrong), A2.2 (deferred bonus caps accuracy), X1 (conditional on appearance).

### Phase 2.2 — Regularized signal combination 📐
- **Goal:** combine the families' *informative* signals into one predictor, handling collinearity principledly (supersedes ad-hoc composition weights).
- **Where:** extend `model/assemble/composition_study.py`. **Machinery:** `sklearn` ElasticNetCV inside the walk-forward harness.
- **Key decision:** EN/LASSO assumes linear-additive combination — **probe against a non-linear reference** (gradient boosting) as a ceiling check for missed interactions (A2.3), not necessarily to ship.
- **Prereq:** Phase-0 harness + families' informative-signal set. **Gate:** beats baseline **and** the single best signal on held-out GWs. **Risks:** A2.3 non-linearity.

### Phase 3 — Distributions & uncertainty 🗒
- **3.1 Monte-Carlo simulator.** *Goal:* simulate components through the real scoring rules → full points distribution, haul probability, captaincy ceiling. *Where:* `model/forecast/simulator.py` (new), reuses `domain/fpl_scoring.py`. *Machinery:* MC sampling from the Phase-2 component models. *Prereq:* Phase-2 components fitted.
  - **Amendment (audit):** the original "simulated mean ≈ point forecast" gate is **circular** (validates a sim against its own centre, ignoring the tails that are the whole point) → **move the distributional validation into Phase 4** (PIT/haul-rate). *Risk:* A2.1 — independent components mis-estimate haul probability (hauls co-move); model the dependence.
- **3.2 Bookmaker odds.** *Goal:* odds → implied returns as both a signal and an external yardstick. *Where:* `model/eval/` (benchmark) + `research/families/fixture/explore/` (as signal). *Machinery:* odds de-vig, calibration vs realized. *Prereq:* **odds data — 🚧 hard blocker if absent.** *Gate:* comparator only.

### Phase 4 — Trust the probabilities 🗒 (hard gate)
- **Goal:** a probability is only useful if calibrated; point-accuracy can't reveal miscalibration.
- **Where:** `model/eval/calibration.py` (new). **Machinery:** reliability diagrams, Brier/log-loss (haul prob), CRPS (full distribution), isotonic/Platt recalibration.
- **Key decisions:** **pre-register the calibration tolerance** (A4.1); recalibrate via CV — isotonic/Platt **overfit on ~35 GWs**. Absorbs Phase-3's distributional validation.
- **Prereq:** Phase-3 probabilistic outputs. **Gate (hard):** reliability within the pre-registered tolerance (recalibrate if not); CRPS beats baseline. **No decisions on miscalibrated probabilities.**

### Phase 5 — Decision value 🗒 (build gap, not data gap)
- **Goal:** the only metric that matters — captain success, transfer gain, ranking quality, chip value, vs baseline decisions.
- **Where:** `serve/eval/decisions.py` (new). **Machinery:** backtested decision rules over walk-forward; ranking metrics; block bootstrap over GWs.
- **Key decisions:** **needs P(play) first** (X1) — decisions can't condition on realized minutes; **single-season backtest is one path** → attach block-bootstrap error bars, **don't rank rules on a point estimate** (A5.1); handle DGWs (X4) as sum-of-two-single-GW forecasts.
- **Data:** present (`purchase_price`, `ownership_count`, `transfers_in/out`) — this is an **un-built decision layer, not a data block**. **Prereq:** Phases 0–4 + P(play). **Gate:** decision rules beat baseline decisions (with uncertainty); only then promote to `serve/`.

### Phase 6 — Situational 🗒
- **6.1 Survival / hazard for availability.** Time-to-injury / minutes as time-to-event (Kaplan–Meier / Cox). Where: `research/families/availability/explore/`. Prereq: adequate event counts — **verify first**. Gate: beats a naive availability baseline. *(Also the P(play) source X1 wants earlier.)*
- **6.2 Cross-season drift.** Season-to-season change in relationships. Where: `research/foundation/temporal/`. Prereq: **≥2 seasons — 🚧 data-blocked.** Gate: ≥2 seasons present.
- **6.3 Full Bayesian hierarchical (PyMC).** Posterior-uncertainty upgrade of Phase 1. Prereq: EB (Phase 1) proven. Gate: posterior predictive checks pass; matches Phase-1 on the shared estimand.
- **6.4 Mutual information / transfer entropy — DROPPED** (Spearman/partial already capture monotone association; adds nothing interpretable).

---

## 4. Assumptions register (living — a schedule with teeth)

Board = panel-data econometrician · ML forecasting engineer · FPL analyst · skeptical statistician · pipeline engineer.
**Rule (enforced):** a phase does not open until every assumption whose **Due-by** is that phase is
resolved. Status ∈ `open` (undecided) · `must-fix` (blocks the Due-by phase) · `accepted-deferred`
(a *deliberate* decision to carry it, with a due-by) · `tested-holds` · `tested-fails`.

| ID | Assumption baked in | Sev | Test / mitigation | Due-by (gate) | Status |
|---|---|---|---|---|---|
| **X2** | **Gaussian LMM on a count target** (debt on shipped D1 — CIs/LRT assume normality) | High | distribution-free bootstrap of SS between-share | Phase 2 (sprint) | ✅ **tested-holds** — ordering + magnitude robust; GK exact-0 is bias-corrected (caveat on D1) |
| X6 | **Process (xG) forecasts components better than realized (goals)** — *goals are equation-inputs, excluded as contemporaneous signals but are Phase-2 targets; real test = lagged xG vs lagged goals → future component* | Med | lagged head-to-head, within-position | Phase 2 (sprint) | ✅ **tested-holds** — xG wins every position (MID +0.043, DEF +0.026, FWD +0.013) |
| A2.2 | **Deferred scoring parts (bonus/cards/saves) are minor** | Med | quantify un-modeled points share | Phase 2 (sprint) | ✅ **tested-holds → NOT minor** — GK saves ~18%, FWD bonus ~11.5%; add GK-saves early, flag FWD bonus |
| A2.1 | **Component independence** in the points map | Med | test residual cross-correlation; joint model in Phase 3 | Phase 3 | accepted-deferred |
| A2.3 | **Linear-additive signal combination** (EN) | Low-Med | non-linear ceiling probe (gradient boosting) | Phase 2.2 | accepted-deferred |
| A4.1 | **Calibration tolerance unspecified** | Med | pre-register tolerance; CV recalibration | Phase 4 | accepted-deferred |
| X1 | **Conditional-on-appearance is the right target** | High | score the unconditional (incl. DNP=0) gap; model P(play) | **Phase 5** (P(play) required) | accepted-deferred |
| X4 | **DGW exclusion is harmless** (product gap) | Med | state gap; DGW = sum of two single-GW forecasts | Phase 5 | accepted-deferred |
| A5.1 | **Single-season decision backtest is enough** | High | block-bootstrap error bars on every decision claim | Phase 5 | accepted-deferred |
| X3 | **Single-season stationarity** | Med | rolling-block stability read | Phase 3 (or when 2nd season lands) | accepted-deferred |
| X5 | **Player identity stable within season** | Low-Med | flag movers; ICC robustness excl. them | opportunistic (with X2 refit) | accepted-deferred |
| A0.2 | **Operational thresholds** (warmup=3, k=20, floors) | Low | ±1 sensitivity check once | opportunistic | accepted-deferred |

✅ **Phase 2 gate CLEARED (2026-07-06):** X2, X6, A2.2 all `tested-holds` — see
[pre-Phase-2 validation](studies/results/predictive-prephase2-validation.md). All others are
*deliberately carried* with a named due-by, not forgotten.

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

## 6. Pre-Phase-2 validation sprint — ✅ DONE (gate cleared 2026-07-06)

Results: [studies/results/predictive-prephase2-validation.md](studies/results/predictive-prephase2-validation.md).
1. **X2** ✅ `tested-holds` — distribution-free bootstrap: D1's ordering + small magnitude survive dropping normality; GK exact-0 is bias-corrected (caveat on D1).
2. **X6** ✅ `tested-holds` — lagged **xG beats lagged goals** at every position (MID +0.043, DEF +0.026, FWD +0.013) → use process features.
3. **A2.2** ✅ `tested-holds → NOT minor` — deferred points material: **GK saves ~18%, FWD bonus ~11.5%** → add GK-saves component early; flag FWD bonus as known bias.
4. **Component-target leakage assertion** ➡ reclassified as a **Phase-2 build-time contract** (it guards feature columns that don't exist until the harness does) — wired in with `count_models.py`, not a pre-build test.

**→ Phase 2 is OPEN.** Build order resumes at 2.1 (count models), carrying: leakage assertion into the
harness; a GK-saves component; FWD-bonus flagged.
