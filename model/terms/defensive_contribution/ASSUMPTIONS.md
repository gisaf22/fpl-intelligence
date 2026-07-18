# defensive_contribution term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/defensive_contribution/defensive_contribution.py`
**Frozen record of the numbers:** [docs/studies/results/predictive-phase3-points-model.md](../../../docs/studies/results/predictive-phase3-points-model.md)

The DC term predicts **P(a player clears their position's defensive-contribution threshold)** one
gameweek ahead, for DEF/MID/FWD; `E[DC points] = DC_POINTS × P(hit)`. It is a **different shape** from the
Poisson-player terms (goals/assists/saves) — the assumptions below are why.

## 1. Logistic, on a derived binary target

DC scores a fixed +2 once, at a threshold — it is a **hit/no-hit** event, not a count. So the target is
the **derived binary** `dc_hit = 1{defensive_contribution ≥ position_threshold}` and the family is
**Binomial/logistic**, not Poisson. `check_assumptions` therefore reports class balance (hit rate) and
requires **both classes present + enough hits** to be `detectable`, rather than a count-dispersion index.

## 2. Position-specific thresholds → per-position fit

The threshold differs by position (DEF ≥ 10 CBIT; MID/FWD ≥ 12 CBIRT; **GK exempt** — no DC term), and
the action dynamics differ, so a **separate logistic is fit per position** (the fit loops position × gw,
not just gw). The population is restricted to DEF/MID/FWD; GK carry no DC prediction.

## 3. Standalone by D-A (not folded into the defensive joint model)

Per diagnostic **D-A**, DC is **conditionally independent** of conceding / clean sheets given minutes, so
it is its own component — deliberately **not** part of `team_goals_against`. Modelling it jointly with CS
would impose a dependence the data rejects.

## 4. Baseline = the lagged DC-action count (a feature)

The per-term naive bar (spec §5) is **`dc_roll3`** — the player's lagged rolling mean of the raw
DC-action count — ranking the binary hit. Unlike the Poisson terms (baseline = lagged mean of the *same*
target), here the baseline is a lagged mean of the *underlying* count, which is also one of the model
features. It answers "does the calibrated model out-rank just carrying recent DC form forward?".

## 5. Lag-safety + emit is a probability

`dc_roll3/5` are strictly-prior (shift(1) before rolling); `fdr_avg` / `was_home` are known-future
(the upcoming fixture). The term **emits raw `P(hit)`**; the `× DC_POINTS` conversion is a compose-layer
step (like saves ÷ 3), kept out of the term.

## 6. Thresholds are UNVERIFIED

`DC_CBIT_THRESHOLD_DEF = 10` and `DC_CBIRT_THRESHOLD_MID_FWD = 12` are marked **UNVERIFIED** in
`domain/fpl_scoring.py` (not in bootstrap-static). If they are corrected, the derived target — and every
DC number — shifts; that is a domain-constant fix, tracked there, not a modelling change here.

## 7. Structure note — standalone, base extracted later

DC is the **first logistic term**. It is written standalone but cleanly factored (`population` builds the
target, `_fit_predict` is the per-position logistic, `fit` is the position × gw loop) so a shared
`BinaryPerPositionComponent` base can be lifted out **mechanically once `minutes` (the second logistic
term) confirms the shape** — the same rule-of-three discipline that produced the Poisson-player base.
