# Phase 2.1 — over-dispersion diagnosis (Gate 1, frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 2.1 — the family-choice gate.
**Produced:** 2026-07-07 · `minutes > 0`, DGW excluded, per position.
**Code:** `model/forecast/count_models.py` · **Reproduce:** `diagnose_by_position(load_mart().mart)`.
**Question:** before fitting, what count family does each component need — Poisson, NB, or ZIP/hurdle?

## Result (per position x count component)

| pos | component | mean | Var/Mean | material (>1.5)? | NB α | LRT p | excess-zero | family |
|---|---|---|---|---|---|---|---|---|
| DEF | assists | 0.059 | 0.99 | no | 0.03 | 0.50 | ~0 | poisson |
| DEF | goals | 0.034 | 1.10 | no | 3.27 | 3e-4 | ~0 | negative_binomial* |
| MID | assists | 0.111 | 1.02 | no | 0.20 | 0.15 | ~0 | poisson |
| MID | goals | 0.099 | 1.05 | no | 0.46 | 0.015 | ~0 | negative_binomial* |
| FWD | assists | 0.076 | 1.10 | no | 1.22 | 0.020 | ~0 | negative_binomial* |
| FWD | goals | 0.235 | 1.09 | no | 0.43 | 0.010 | ~0 | negative_binomial* |

\* NB flagged by the LRT but **not material** — see below.

## Findings

- **The components are near-Poisson.** The dispersion index is **1.0–1.1 everywhere** (Poisson = 1.0),
  and **zero-inflation is nil** (observed P(y=0) matches the Poisson-implied `exp(-mean)`; excess ~0).
  No component needs ZIP/hurdle.
- **"Significant" ≠ "material".** With n = 1,390–5,208, the NB LRT detects the *tiny* excess variance in
  goals (DEF/MID/FWD) as statistically significant, but the absolute over-dispersion is negligible
  (index < 1.15; **no component clears the 1.5 material flag**). NB is technically justified for goals and
  is ~Poisson in practice; assists at DEF/MID are cleanly Poisson.
- **Most of that mild over-dispersion is between-player heterogeneity, not count noise.** The diagnosis is
  marginal (intercept-only); it pools good and weak scorers. A mean model with features/exposure will
  absorb much of it, so **conditional dispersion should sit even closer to Poisson.** Re-check after fitting.

## The design-shaping takeaway

The plan's premise "the target is zero-inflated / over-dispersed — Poisson is wrong" is **true for
`total_points`** (hauls, mixed components) but **false for the individual components**. That is exactly the
vindication of the **component→points map**: decomposing points converts a nasty zero-inflated/haul-heavy
target into a set of **near-Poisson components** that simple GLMs fit well. The messiness lives in the
*composition* (a MID's points jump when a rare goal lands), not in the component distributions.

## Decision (Gate 1)

- **Fit goals with NB** (LRT-justified, cheap insurance; collapses to ~Poisson via small α) and
  **assists with Poisson**; **no ZIP/hurdle** anywhere.
- Carry a **conditional dispersion re-check** into the fitting step (does adding features/exposure push the
  index to ~1.0?). Recorded, not assumed.
- Clean sheets remain **Bernoulli** (binary, excluded from this count diagnosis by construction).

---

## Minutes exposure — is a log-minutes offset valid? (resolves A-P1)

`analyze_minutes_exposure()` — contemporaneous goals-vs-minutes structure per position: per-90 goal rate
by minutes band, and the pooled Poisson coefficient β on `log(minutes)` (β = 1 ⇒ proportional exposure ⇒
offset justified).

| pos | per-90 rate (1,30] | (30,60] | (60,90] | β log(min) [CI] | verdict |
|---|---|---|---|---|---|
| DEF | 0.077 | 0.020 | 0.043 | **0.59 [0.25, 0.94]** | sub-proportional — offset invalid |
| MID | 0.163 | 0.100 | 0.152 | 0.90 [0.72, 1.08] | proportional — offset ok |
| FWD | 0.620 | 0.248 | 0.386 | **0.66 [0.50, 0.83]** | sub-proportional — offset invalid |

**Finding — proportional exposure is rejected for DEF and FWD** (β < 1, CI excludes 1); only MID is ~proportional.
The per-90 rate is **non-monotonic — highest at short (1,30] minutes** (FWD 0.62 vs 0.39 at 60–90): the
**attacking-substitute selection effect** (subs enter goal-chasing situations) plus small-minute denominator
inflation. *Caveat:* pooled contemporaneous β mixes exposure with player selection (subs ≠ starters), so this
is the *effective* minutes-rate relationship a model must respect, not clean causal exposure — but either way
the offset decision is the same.

**Decisions:**
- **Do NOT use a fixed log-minutes offset** (coef=1) for goals. Enter minutes as a **free covariate**
  (β estimated) or **minutes-band terms**; MID may keep an offset, DEF/FWD must not.
- **A-P1 resolved (`minutes ≥ 60` "qualified start"):** the threshold is **not innocuous** — short
  appearances carry a *different, higher* per-90 rate, so filtering to `minutes ≥ 60` (families' choice)
  discards a materially distinct sub-population. Our predictive population stays **`minutes > 0`**, and
  minutes enters the model flexibly rather than as a filter or a proportional offset. Status: **tested-fails
  (proportional-exposure assumption); `minutes ≥ 60` not adopted.**
- Connects to the salvaged family finding **"FRINGE > STABLE"** — same phenomenon (sub/rotation forwards
  behave differently), now quantified.
