# Minutes-exposure & substitute-selection study (frozen)

**Name:** Minutes-exposure structure — does the goal rate scale with minutes played?
**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 2.1 (minutes decision) · resolves register **A-P1**.
**Produced:** 2026-07-07 · `minutes > 0`, DGW excluded, per position.
**Code:** `model/forecast/count_models.py` → `analyze_minutes_exposure()` · **Tests:** `tests/test_model_forecast_count_models.py`.

## Question
Before fitting the goals model: does a player's goal rate scale **proportionally** with minutes played
(so minutes can enter as a fixed log-minutes *exposure offset*), or not? And is the inherited families
`minutes ≥ 60` "qualified-start" filter (A-P1) innocuous?

## Design
Contemporaneous, per position (DEF/MID/FWD): (1) the per-90 goal rate within minutes bands
(1,30] / (30,60] / (60,90] — is it flat across bands? and (2) a pooled Poisson regression of
`goals_scored` on `log(minutes)`; the coefficient **β = 1 ⇒ proportional exposure** (offset justified),
**β < 1 (CI excludes 1) ⇒ sub-proportional** (offset invalid, minutes must enter flexibly).

## Result

| pos | per-90 (1,30] | (30,60] | (60,90] | β log(min) [CI] | verdict |
|---|---|---|---|---|---|
| DEF | 0.077 | 0.020 | 0.043 | **0.59 [0.25, 0.94]** | sub-proportional — offset invalid |
| MID | 0.163 | 0.100 | 0.152 | 0.90 [0.72, 1.08] | proportional — offset ok |
| FWD | 0.620 | 0.248 | 0.386 | **0.66 [0.50, 0.83]** | sub-proportional — offset invalid |

## Findings
- **Proportional exposure is rejected for DEF and FWD** (β < 1, CI excludes 1); only MID is ~proportional.
- **Per-90 rate is highest at short (1,30] minutes** — the **attacking-substitute selection effect**: subs
  enter goal-chasing situations, and a goal in few minutes inflates the per-90 rate (small denominator).
- **Caveat:** the pooled contemporaneous β mixes mechanical exposure with player selection (subs ≠ starters).
  So this is the *effective* minutes-rate relationship a model must respect, not a clean causal exposure —
  but the modelling decision is the same either way.
- Quantifies and corroborates the salvaged family explore finding **"FRINGE > STABLE"** (rotation/fringe
  forwards behave differently from nailed starters).

## Decisions (feed Phase 2.1 fitting)
- **No fixed log-minutes offset for goals.** Minutes enters as a **free covariate / band terms**; MID may
  retain an offset, DEF/FWD must not.
- **A-P1 resolved (`tested-fails`):** the `minutes ≥ 60` filter is **not** adopted — short appearances are a
  materially distinct, higher-per-90 sub-population, not noise. The predictive population stays **`minutes > 0`**.
- At *prediction* time (future minutes unknown), minutes enters via **lagged expected-minutes** (e.g.
  `minutes_roll3/5`, the availability family's one strong signal), conditional on appearance (X1).
