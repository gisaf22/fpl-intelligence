# goals term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/goals/goals.py` → `GoalsModel` / `GoalsTerm`
**Frozen record of the numbers:** [docs/studies/results/predictive-phase2-component-model.md](../../../docs/studies/results/predictive-phase2-component-model.md)

The goals term predicts **E[goals_scored] one gameweek ahead** and emits a single term (`goals`),
composed into E[points] via the position goal weights. This file records the assumptions the model
*rests on* — each was a footnote or standalone phase doc in the old layout; they live here now, next
to the code, as spec §9 requires. These are checked pre-fit by `GoalsModel.check_assumptions`.

## 1. Family — Poisson (near-Poisson, not NB)

`goals_scored` is a count. The count-shape diagnosis (`model.forecast.count_models.diagnose_overdispersion`)
finds goals **near-Poisson**: the material dispersion index sits ≈1 (Gate 1), so Var ≈ Mean and Poisson
is justified. We deliberately key `family_ok` off **material** over-dispersion, *not* the likelihood-ratio
test: at thousands of rows the LRT flags NB even at a dispersion index of ~1.06 (statistically
over-dispersed, materially Poisson). Choosing NB there would buy nothing and lose the clean Poisson mean.
NB-for-goals remains a recorded future lever if a richer feature set surfaces genuine material dispersion.

## 2. Minutes enter as a covariate, not a proportional offset

The exposure test (`count_models.analyze_minutes_exposure`) **rejected proportionality** for DEF/FWD:
the Poisson coefficient on log(minutes) is < 1 with a CI excluding 1, so a fixed log-minutes *offset*
is invalid. Minutes therefore enter as a free covariate — `minutes_roll3` (expected minutes) — one of
the two mechanistic features, never an `exposure=` offset.

## 3. Lagged process stats (xG), not lagged realized goals

The design check (`component_forecast.xg_vs_goals_forecast_skill`, frozen) showed **lagged xG out-ranks
lagged realized goals** at every position (DEF +0.026, MID +0.043, FWD +0.013): xG regresses to a truer
scoring rate than the noisy realized outcome. So the leading feature is `xgi_roll3`, not a goals roll.
(Using lagged goals as a *predictor* is not the excluded contemporaneous-signal case — it is strictly
prior; goals are the term's **target**.)

## 4. Lag-safety — strictly prior, verified

Both mechanistic inputs are the mart's `*_roll3` columns, verified to **exclude the current GW**. The
leakage property (`model.features.build.assert_lag_safe`) asserts every strictly-prior feature is NaN on
each player's first appearance; it runs at build-time / in CI (spec §4 stage 0), so `fit` trusts the
inputs and does not re-derive the check per call.

## 5. Detectability floor (pre-fit power)

A Poisson mean is only learnable away from zero with enough positive events. `check_assumptions` requires
≥30 feature-complete training rows **and** ≥10 positive-goal events before the slice is `detectable`.
Below the floor a null verdict is **inconclusive**, never a licence to abandon the term (spec §0-B).

## 6. Conditional on appearance (X1)

Population is `minutes > 0`, DGW excluded (the project v1 base population). The term ranks players who
**actually featured**; jointly predicting who plays is the minutes/availability term's job, out of scope
here. Read every goals number as "ranking accuracy **given** the player played".

## 7. One pool, two draws (spec §3)

`GOALS_POOL.minimal = (xgi_roll3, minutes_roll3)` is both the fast smoke-test and the comparison **bar**.
The `selected` model regularizes over the full pool — but the §3 opponent-forward / team-context
candidates are declared, not yet materialized, so today `selected` draws the same two columns as
`minimal` and is **not** wired into `compose`. The frozen composed numbers are therefore unchanged; the
minimal model reproduces the god-file goals GLM bit-for-bit (golden test in `test_goals.py`).
