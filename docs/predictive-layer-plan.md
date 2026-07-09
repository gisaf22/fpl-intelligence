# Predictive Layer — Master Plan & Status

**Single source of truth** for the predictive layer: phased plan, live status, claims discipline,
assumptions register, and data inventory. Supersedes and folds in the former `predictive-phase1-design`,
`predictive-phase2-design`, `analysis-strategy-review`, and `predictive-plan-assumptions-audit` docs.
Frozen per-phase *results* live separately (linked in §1) and are the immutable evidence trail.

**Last updated:** 2026-07-08 · **Now at:** Phase 3.0 COMPLETE (points-equation closure — full points model beats Phase-2.1 + incumbent at every position) → **RESUME HERE: Phase 3.1** (Monte-Carlo simulator on the closed equation). `main` clean & pushed.

> **▶ Resume pointer.** Phase 2.2 done (remediated: `L1_wt` tuned, `minutes_trend` re-tested, selection
> receipts added): regularized per-component combination clears BOTH gates (incumbent + best single signal)
> **only at DEF** (0.237 > 0.217 > 0.162); MID regresses, FWD/GK beat incumbent but not the single
> ([results](studies/results/predictive-phase2-signal-combination.md)). A-F1 **resolved** with a
> selection-stability table (`selection_stability()`): `fdr_avg` kept across every component, process
> `xg/xa_roll5` > roll3 (X6), `was_home` kept most for *assists* not CS (overturns v2 "defensive-only"),
> `minutes_trend` retained-but-immaterial. A2.3 ceiling probe recorded (headroom modest at DEF/FWD, larger
> at MID/GK). Read §1 dashboard + §4 register before building. Discipline: rank≠predict (§2); population
> `minutes>0`; honest-null is valid; families
> demoted to *prior* (§5, don't delete — serve depends).
>
> **Phase 3.0 — points-equation closure — ✅ COMPLETE (2026-07-08).** Phase 2 modelled 4 of the 12
> scoring terms (fine for ranking, incomplete for a distribution). Closed the equation: verified rules,
> per-position spec (100% SGW reconstruction), scoring diagnostics (D-A null / D-B proxy / D-C rejected
> in-model / D-D CS≡GA identity), and a per-position **points** model (team-GA→CS+conceded joint; DC;
> bonus=returns_pts; minutes hurdle; pooled goals/assists). Composed + dual-bar gated: the **full points
> model beats the Phase-2.1 model AND the incumbent at every position** (vs Phase-2.1: GK +0.118 / DEF
> +0.048 / MID +0.044 / FWD +0.044). **Next: Phase 3.1 Monte-Carlo simulator** on the closed equation.

---

## 1. Status dashboard

| Phase | Item | Status | Gate result | Evidence |
|---|---|---|---|---|
| 0.1 | Baseline suite | ✅ complete | reproducible per-GW scores | [results](studies/results/predictive-phase0-baselines.md) |
| 0.2 | Walk-forward harness | ✅ complete | leakage assertion passes | same |
| pre-1 | Point-estimate (level) study | ✅ complete | shrink toward the **mean** | [results](studies/results/predictive-level-estimators.md) |
| 1 · D1 | ICC / variance components | ✅ **shipped** | reconciles w/ Q1; σ²_between real (LRT) | [results](studies/results/predictive-phase1-icc-shrinkage.md) |
| 1 · D2 | EB shrinkage ranker | ✅ built, ⛔ **null** | does NOT out-rank raw mean → shelved | same |
| 2.1 | Count models — gate 1 (dispersion) | 🔨 **in build** | components near-Poisson (index ~1.1, no ZIP) | [results](studies/results/predictive-phase2-overdispersion.md) |
| 2.1 | Count models — fit + compose + gate | ✅ **v2 done** | features beat baseline **DEF +0.031 / MID +0.019**; GK parity; FWD −0.012 (scope limit) | [results](studies/results/predictive-phase2-component-model.md) |
| 2.2 | Regularized signal combination | ✅ **done (remediated)** | clears both gates only at **DEF** (0.237); MID regresses, FWD/GK beat incumbent not the single; **A-F1 closed** w/ selection table | [results](studies/results/predictive-phase2-signal-combination.md) |
| 3.0 | Points-equation closure (verify · per-position spec · diagnostics · per-position points model + compose) | ✅ **done** | **full points model beats Phase-2.1 + incumbent at every position** (vs Phase-2.1: GK +0.118/DEF +0.048/MID +0.044/FWD +0.044); T1 spec 100% SGW; T2 diagnostics resolved | [result](studies/results/predictive-phase3-points-model.md) | [diagnostics](studies/results/predictive-phase3-scoring-diagnostics.md) |
| 3.1 | Monte-Carlo simulator | 📐 **design ready** (2026-07-09) | consumes `walk_forward_points`; team-GA shared draw couples CS/conceded; dist. adequacy = Phase-4 hypothesis; blanks + team-stacking deferred | §3 |
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
decisions). Never ordered by sophistication. **Build order:** `0.1→0.2→1.1→[pre-2 sprint]→2.1→2.2→3.0→3.1→(3.2 if odds)→4.1→5.1→6.x`.

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
- **Gate 1 DONE (dispersion diagnosis, [results](studies/results/predictive-phase2-overdispersion.md)):** components are **near-Poisson** (index ~1.0–1.1, zero-excess ~0, no ZIP/hurdle). NB LRT-flags goals but *not materially* (mostly between-player heterogeneity a mean model absorbs). **Decision:** goals→NB (cheap), assists→Poisson, CS→Bernoulli. Key insight: the component map turns the zero-inflated `total_points` into near-Poisson *components* — vindicates the decomposition. Conditional dispersion re-checked at fit.
- **Minutes — TESTED, offset REJECTED (A-P1, [minutes-exposure study](studies/results/predictive-phase2-minutes-exposure.md)).** The β-on-log(minutes) test came back **sub-proportional for DEF (0.59) and FWD (0.66)** — CI excludes 1 — with per-90 rates *highest at short minutes* (attacking-sub selection). So **no fixed log-minutes offset** for goals; minutes enters as a **free covariate / band terms** (MID ~proportional, may keep offset). Population stays `minutes > 0` (the families' `minutes≥60` filter discards a distinct sub-population).
- **Features (X):** minimal, **strictly-prior** process stats — goals rate ← lagged `xg` (per X6, xG > goals); assists ← lagged `xa`; clean sheet ← `fixture_context`, lagged `goals_conceded_roll3`, `was_home`. `.shift(1)` enforced; component-target leakage assertion added to the harness contract. Use component-appropriate parts (`xg`→goals, `xa`→assists), **not** the composite `xgi` (avoid double-counting).
- **Salvaged from families (as a *prior*, not authority — see families disposition below):**
  - **Candidate roster to re-test per component:** `xgi_roll3/5`, `minutes_roll3/8`, `transfers_in`, `ownership_count`, `purchase_price` (family rho 0.12–0.23). **Re-test each against its *component* target, not `total_points`** (A-F1) — the family verdicts gated on points with a brittle quintile rule and never enforced beating the baseline, so their "informative"/"excluded" labels are a weak prior, not a filter. Expect `xg`(FWD-goals) and `fixture`(CS) to re-enter *despite* family points-exclusion.
  - **FWD explore findings (lagged/predictive, ref `research/families/form/explore/`):** (i) **"FRINGE > STABLE"** — rolling xGI correlates *more* for rotation/fringe forwards than nailed ones (bears on the minutes/exposure treatment above); (ii) xGI **horizon** 3/5/8-GW window choice for FWD. Carry as hypotheses into the FWD goals model.
  - **Domain rationales (from family annotations):** transfers = crowd momentum (lagged); ownership tracks form with a lag; price proxies quality tier; GK excluded from attacking signals (ontological). Domain priors, not verdicts.
- **Folded-in read:** the never-run **autocorrelation / form-persistence** study (via `research/kernels/diagnostic/serial.py`) enters here as a *gated* question — report within-player lag-1 autocorrelation per position, and test whether a lagged-form feature earns its place over the level-only baseline.
- **Prereq (verified):** component columns present in mart. **Gate:** (1) over-dispersion test justifies NB/ZIP over Poisson; (2) composed E[points] beats the Phase-0 baseline **and** (3) the best single signal, per position, walk-forward. Else ship the dispersion diagnosis as an honest null.
- **Risks:** X6 (xG>goals unproven — one sub-question), A2.1 (component independence — mean OK, haul-prob wrong), A2.2 (deferred bonus caps accuracy), X1 (conditional on appearance).

### Phase 2.2 — Regularized signal combination ✅ done (2026-07-08)
- **Goal:** combine the **re-validated** candidate signals (the family roster re-tested per component, §2.1) into one predictor, handling collinearity principledly (supersedes ad-hoc composition weights). *Not* the family "informative" labels — those are demoted to a prior (A-F1).
- **Where:** `model/forecast/signal_combination.py` → `walk_forward_signal_combination()`, `selection_stability()`, `gradient_boosting_ceiling()` (NOT the stale `model/assemble/composition_study.py`, the legacy SYNTH-01 governance path — slated for Phase-5 retirement). **Machinery:** per-component `statsmodels` **GLM.fit_regularized** (elastic net; BOTH `alpha` and `L1_wt` chosen by inner temporal CV), NOT Gaussian `sklearn` ElasticNetCV — keeps each component's evidence-picked count/logistic family.
- **Key decision:** EN/LASSO assumes linear-additive combination — **probe against a non-linear reference** (gradient boosting, `gradient_boosting_ceiling()`) as a ceiling check for missed interactions (A2.3), not shipped.
- **Result:** clears both gates (incumbent + best single signal) **only at DEF** (0.237 > 0.217 > 0.162); MID regresses (0.319 < 0.339), FWD/GK beat incumbent but not the best single signal. **A-F1 closed** with a selection-stability receipt: `fdr_avg` kept across every component, process `xg/xa_roll5` > roll3 (X6), `was_home` kept most for *assists* (overturns v2 "defensive-only" placement), `minutes_trend` retained-but-immaterial. A2.3 headroom modest at DEF/FWD, larger at MID/GK. [results](studies/results/predictive-phase2-signal-combination.md).
- **Prereq:** Phase-0 harness + families' informative-signal set. **Gate:** beats baseline **and** the single best signal on held-out GWs. **Risks:** A2.3 non-linearity.

### Phase 3.0 — Points-equation closure 🗒 (NEW — blocks 3.1)
**Why this exists.** Phase 2 models 4 of the 12 scoring terms. That is correct for *ranking* (the
dropped terms are within-position constants or low-variance noise), but a simulator composes *actual
points*, so omissions with variance distort the distribution and its tails. Measured un-modeled
*variable* share (appearance excluded — it is a near-constant +2): **GK ~19% / DEF ~27% / MID ~18% /
FWD ~14%**; for defenders `defensive_contribution` (~10%) and `goals_conceded` (~8%) each rival goals.
**Discipline:** separate DEFINITIONAL truths (act now) from EMPIRICAL hypotheses (measure first — no
untested sign/magnitude claims, e.g. the DC↔conceded "siege" direction is UNPROVEN); honest-null valid
at every gate. Each track has a **validation gate** that must pass before the next opens.

- **Track 0 — Verify the rulebook** [FIX]. Confirm the `UNVERIFIED` constants (`goals_conceded` −1/2;
  DC thresholds 10 CBIT / 12 CBIRT; `DC_POINTS` 2) against FPL bootstrap-static. *Where:*
  `domain/fpl_scoring.py` + `tests/`. **Gate:** a test asserts each constant matches bootstrap-static.
  *Plain terms:* two rules were written from memory — confirm against the official source before building on them.
- **Track 1 — Document per-position equations** ✅ **done (2026-07-08)**. `POSITION_SCORING` declarative
  spec + `score_components` engine + `position_components()` accessor in `domain/fpl_scoring.py`;
  `decompose_total_points` now delegates to it (single source). **Gate MET:** reconstructs `total_points`
  **100% exact on 28,929 single-GW rows** (DGW DC-threshold caveat documented); 15 hermetic tests.
  Modelled roster per position (what Track 3 fits): GK {goals, assists, CS, saves, conceded, bonus};
  DEF {goals, assists, CS, conceded, DC, bonus}; MID {goals, assists, CS, DC, bonus};
  FWD {goals, assists, DC, bonus}. *Plain terms:* one sheet per position of exactly what scores points,
  proven by rebuilding every real score perfectly.
- **Track 2 — Scoring diagnostics** [TEST; research tier, human-only, association-only, NO model
  emission, bootstrap CI for any beyond-noise claim]. **D-A** DC↔conceded/CS association →
  `research/diagnostic/`; **D-B** bonus↔returns attribution (R²/rank-corr; how often top-BPS = top-returns)
  → `research/diagnostic/`; **D-C** bonus↔DC overlap (partial corr | returns) → `research/diagnostic/`;
  **D-D** `CS = 1{GA=0}` identity / impossible-state rate → `research/foundation/composition/scoring_engine.ipynb`.
  **Gate:** each yields a measured number + bootstrap CI, human-rendered; frozen verdicts in
  `docs/studies/results/predictive-phase3-scoring-diagnostics.md`; the **plan** (not the notebook) records
  the resulting modeling decision. *Plain terms:* measure the real relationships before choosing how to model them.
- **Track 3 — Re-cast Phase 2 as a per-position POINTS model** [CHANGE; items gated on Track 2].
  *Where:* `model/forecast/` (new module) + frozen `docs/studies/results/predictive-phase3-points-model.md`.
  (3.1) ✅ **done (2026-07-08)** **team goals-against layer** → one Poisson team-GA model derives
  `p_cs=exp(-λ)` + `e_conceded_pts=E[-floor(GA/2)]` jointly (no impossible states). P(CS) beats the
  lagged-CS incumbent at every position (GK +0.122, DEF +0.068, MID +0.007). `points_model.py`,
  4 tests, [result](studies/results/predictive-phase3-points-model.md);
  (3.2) ✅ **done (2026-07-08)** **DC component** — per-position logistic P(hit) → `E[DC]=2·P(hit)`;
  beats the lagged baseline at DEF (+0.015) and parity at MID; FWD immaterial (~1% hit-rate) →
  exclude-and-flag; GK exempt. 6 tests, [result](studies/results/predictive-phase3-points-model.md);
  (3.3) ✅ **done (2026-07-08)** **bonus proxy** — per-position OLS calibration on `returns_pts` (D-B);
  a per-component GLM lost and **DC-augmentation hurt** (D-C partial didn't survive as a term). Ranking
  = returns_pts (GK 0.50/DEF 0.53/MID 0.55/FWD 0.77), `E[bonus]∈[0,3]`; competitive residual irreducible
  without a full-match sim. 7 tests, [result](studies/results/predictive-phase3-points-model.md);
  (3.4) ✅ **done (2026-07-08)** **minutes hurdle** — `P(≥60'|played)` (outfield logistic, GK lagged
  rate), sets `E[appearance]=1+P(≥60')` + gates CS. Ranking ~parity with lagged minutes; value is the
  calibrated probability. `P(play)` blank tail deferred (X1, Phase 5). 9 tests;
  (3.5) ✅ **done (2026-07-08)** **per-position vs pooled goals/assists** — per-position **loses or ties
  everywhere** (only FWD goals +0.006); A-P2 resolves *keep pooled+multiplier*. 10 tests;
  **(compose)** ✅ **done (2026-07-08)** — full points model composed via the position scoring
  structure + dual-bar gate (`base_season` + Phase-2.1). **Beats BOTH bars at every position**
  (full vs Phase-2.1: GK +0.118 / DEF +0.048 / MID +0.044 / FWD +0.044) — closing the equation
  improved ranking everywhere, not just DEF/GK. `points_model_gate()`, 12 tests.
  *Plain terms:* we added up each player's likely points with all the pieces — and it predicts better
  than the old model at every position.

### Phase 3 — Distributions & uncertainty 🗒
- **3.1 Monte-Carlo simulator 📐 (design ready — 2026-07-09).** *Goal:* sample the components through the real scoring rules → full points **distribution** (P(haul≥10), captaincy ceiling p90, downside p10). *Where:* `model/forecast/simulator.py` (new), **consumes `walk_forward_points` output** (recover sampling params from its columns — `λ_goals=e_goals`, `λ_ga=−log(p_cs)`, `p_dc`, `p60`, `e_saves`), reuses `domain/fpl_scoring.py`. *Machinery:* N≈10k seeded draws per player-GW; per draw sample `play60~Bern(p60)`, `goals/assists~Poisson`, `saves~Poisson`, `DC~Bern(p_dc)`, **team `GA~Poisson(λ_ga)` once per team-fixture** → CS`=1{GA=0}·1{≥60'}` and conceded`=−floor(GA/2)` from that one draw; bonus = proxy applied to the drawn returns; sum through the scoring rule.
  - **Dependence — STRUCTURE grounded in diagnostics, DISTRIBUTION unverified (honest framing, not "settled").** *Definitional:* CS/conceded are one team-GA variable (D-D) → shared team-GA draw couples teammates' CS/conceded — **exact for full-90 players, approximate for subs** (on-pitch GA ≠ team GA). *Supported approximation:* DC⊥GA given minutes (D-A, partial ρ≈0.05, clustered-robust) → independent DC draw. *Mean-correct but underdispersed:* bonus proxy per draw (competitive residual not sampled). *Untested assumption:* the Poisson **forms/dispersion** of GA & goals/assists are validated only at the mean/ranking level — their distributional adequacy is a **Phase-4 hypothesis** (PIT/haul-rate/CRPS), not asserted here.
  - **Gate — internal correctness ONLY:** reproducible under seed; sim mean ≈ analytic `E[points]` within MC error (consistency, *not* the circular "sim mean predicts points"); no draw has CS=1 with conceded>0. Distributional validation is **Phase 4** (`model/eval/calibration.py`).
  - **Scope limits (first-class):** **`P(play)`/blank 0-minute tail NOT represented** (conditional on appearance, X1 → Phase 5) — the biggest missing tail for any haul/ceiling number. **Cross-player *attacking* co-movement** (a team's attackers hauling together) needs a team **goals-for** layer we don't have → **single-player marginals correct, team-stacked joints are NOT a 3.1 deliverable** (Phase 5). Within-player goals⊥assists; rare events excluded-and-flagged.
  - **Locked decisions (2026-07-09):** defer team goals-for/stacking to Phase 5; bonus = proxy-per-draw; recover params from `walk_forward_points` columns; N=10k, seed=0. *Plain terms:* roll the dice thousands of times per player for their full range of outcomes — but only for players we already assume start, and one player at a time (not whole-team pileups yet).
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
| A2.2 | **Deferred scoring parts (bonus/cards/saves/DC/conceded) are minor** | Med | quantify un-modeled points share | Phase 2 (sprint) → **full audit Phase 3.0** | ✅ **tested-holds → NOT minor** — full per-position decomposition (2026-07-08): un-modeled *variable* share DEF ~27% / GK ~19% / MID ~18% / FWD ~14%; DC ~10% and conceded ~8% rival goals for DEF → **Phase 3.0 Track 3** closes them |
| A2.1 | **Component independence** in the points map | Med | test residual cross-correlation (D-A); joint team-goals model (CS+conceded) | **Phase 3.0** | 🟡 **partially resolved (2026-07-08)** — CS≡1{GA=0} confirmed (D-D, 0% impossible) → one team-GA model required; DC↔conceded is **null given minutes** (D-A) → no DC coupling needed. [diagnostics](studies/results/predictive-phase3-scoring-diagnostics.md) |
| **RULE-V** | **`goals_conceded` / DC constants are UNVERIFIED** in `domain/fpl_scoring.py` | Med | assert each against bootstrap-static | **Phase 3.0 Track 0** | 🟡 **partly done (2026-07-08)** — all point *coefficients* + position applicability VERIFIED vs `game_config.scoring`; the ÷2 (conceded), ÷3 (saves), and DC thresholds 10/12 are **not in the endpoint** → stay by-rule |
| **D-A** | **DC↔conceded/CS co-movement** ("siege" vs "dominance") | Med | minutes-adjusted partial corr, bootstrap CI; `research/diagnostic/` | **Phase 3.0 Track 2** | ✅ **tested → NULL** — partial(DC,conceded\|min)=+0.05, (DC,CS\|min)=+0.00; "siege" was a minutes artifact, retracted; **no coupling** |
| **D-B** | **Bonus recoverable from modeled returns** | Med | rank-corr bonus~returns, bootstrap CI | **Phase 3.0 Track 2** | ✅ **tested → YES** — rho FWD +0.78, others ~0.5; reduced-form bonus proxy viable |
| **D-C** | **Bonus↔DC overlap** (shared inputs) | Low-Med | partial corr `corr(DC, bonus \| returns)` | **Phase 3.0 Track 2** | ✅ **tested → modest-real** — DEF +0.15, MID +0.10; add DC to bonus-proxy features |
| **A-P2** | **Pooled component + position multiplier** ≈ per-position rate process (specification) | Med | per-position vs pooled walk-forward; keep only if it beats pooled | **Phase 3.0 Track 3.5** | ✅ **tested-holds (2026-07-08)** — per-position loses/ties at every cell (GK-assists −0.11, DEF-goals −0.02; only FWD-goals +0.006) → **keep pooled+multiplier**. [result](studies/results/predictive-phase3-points-model.md) |
| A2.3 | **Linear-additive signal combination** (EN) | Low-Med | non-linear ceiling probe (gradient boosting) | Phase 2.2 | ✅ **probed (2026-07-08)** — GBM headroom modest at DEF (+0.017)/FWD (+0.044), larger at GK (+0.067)/MID (+0.050) over the reg. combination; recorded lever, not shipped |
| A4.1 | **Calibration tolerance unspecified** | Med | pre-register tolerance; CV recalibration | Phase 4 | accepted-deferred |
| X1 | **Conditional-on-appearance is the right target** | High | score the unconditional (incl. DNP=0) gap; model P(play) | **Phase 5** (P(play) required) | accepted-deferred |
| X4 | **DGW exclusion is harmless** (product gap) | Med | state gap; DGW = sum of two single-GW forecasts | Phase 5 | accepted-deferred |
| A5.1 | **Single-season decision backtest is enough** | High | block-bootstrap error bars on every decision claim | Phase 5 | accepted-deferred |
| X3 | **Single-season stationarity** | Med | rolling-block stability read | Phase 3 (or when 2nd season lands) | accepted-deferred |
| X5 | **Player identity stable within season** | Low-Med | flag movers; ICC robustness excl. them | opportunistic (with X2 refit) | accepted-deferred |
| A0.2 | **Operational thresholds** (warmup=3, k=20, floors) | Low | ±1 sensitivity check once | opportunistic | accepted-deferred |
| **A-F1** | **Family signal-verdicts are `total_points` marginal reads, not component-validated** (gate never enforced beating the baseline; brittle quintile-monotonicity) — treat roster as a *prior*, not a filter | High | re-test each candidate against its *component* target with the Phase-0 baseline gate | Phase 2 (build) | ✅ **closed (2026-07-08)** — re-tested per component under a tuned elastic net + best-single gate; roster earns its place only at DEF; verdicts demoted to prior with a `selection_stability()` receipt (fdr_avg kept everywhere, roll5>roll3, was_home mainly attacking-assists) |
| A-F2 | **Does Q1b identity-dominance carry to components?** (if points are identity-dominant, features may add little beyond level) | Med | per-component within-predictability check vs level baseline | Phase 2 | open |
| A-P1 | **`minutes ≥ 60` "qualified start"** + **proportional-minutes exposure** | Med | minutes-band + Poisson-β test ([study](studies/results/predictive-phase2-minutes-exposure.md)) | Phase 2 | ✅ **tested-fails** — β<1 for DEF/FWD (offset invalid); short mins carry higher per-90 rate → `minutes≥60` NOT adopted; keep `minutes>0`, minutes enters flexibly |
| A-F3 | **FWD/GK have no validated point-signals** (families) — component-only reliance | Med | honest scope limit; GK via saves+CS, FWD via xG→goals | Phase 2 | accepted-deferred |

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

**Canonical population (verified):** `minutes > 0`, DGW-excluded — the Phase-0/1 population we've gated
on. Recorded here, not in a separate contract artifact (research-first — we don't grow the production
registry). Any deviation is a register item, not a silent choice: `minutes ≥ 60` is **A-P1 (open)**.

### Layer disposition & ownership (families reconciliation)

**Families are demoted, not deleted (Option A).** They currently feed the live `serve/` scorer via
`registry → governance`, so files stay in place. But their **authority is downgraded to "prior +
explanatory"**: the predictive layer (Phase 2+) is now the **authoritative signal arbiter** (re-tests
per component, gates on the Phase-0 baseline — the thing families never enforced). The salvage (candidate
roster, FWD explore findings, domain rationales) is **referenced into Phase 2.1 above** — not moved
(the useful stats already live in `research/kernels/`; the explore findings are lagged/predictive so they
belong on the predictive side, *not* diagnostic, which is association-only).

**Per-layer ownership going forward:**
`dal` data + population · `research/foundation` EDA · `research/diagnostic` association (Q1/Q1b/Q2,
contemporaneous) · `research/families` **demoted → hypothesis/prior only** · `model` **authoritative
predictive validation + governance reconciler** · `serve` consumes governance-approved (family path now,
predictive at Phase 5).

**Action B — legacy-chain retirement (roadmap, decide at Phase 5):** research-first means
`families → registry → governance → serve` is transient. **At the Phase-5 cutover**, promote the
predictive scorer into `serve/` and retire the legacy signal-selection chain (freeze registry, archive
family `validate/`). Not now — the live scorer must keep running until predictive can replace it. Logged
as a one-line roadmap item, not an open action.

---

## 6. Pre-Phase-2 validation sprint — ✅ DONE (gate cleared 2026-07-06)

Results: [studies/results/predictive-prephase2-validation.md](studies/results/predictive-prephase2-validation.md).
1. **X2** ✅ `tested-holds` — distribution-free bootstrap: D1's ordering + small magnitude survive dropping normality; GK exact-0 is bias-corrected (caveat on D1).
2. **X6** ✅ `tested-holds` — lagged **xG beats lagged goals** at every position (MID +0.043, DEF +0.026, FWD +0.013) → use process features.
3. **A2.2** ✅ `tested-holds → NOT minor` — deferred points material: **GK saves ~18%, FWD bonus ~11.5%** → add GK-saves component early; flag FWD bonus as known bias.
4. **Component-target leakage assertion** ➡ reclassified as a **Phase-2 build-time contract** (it guards feature columns that don't exist until the harness does) — wired in with `count_models.py`, not a pre-build test.

**→ Phase 2 is OPEN.** Build order resumes at 2.1 (count models), carrying: leakage assertion into the
harness; a GK-saves component; FWD-bonus flagged.
