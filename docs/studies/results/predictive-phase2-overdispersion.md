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

**Companion:** the minutes-exposure / substitute-selection read (offset validity + A-P1) is its own study —
[predictive-phase2-minutes-exposure.md](predictive-phase2-minutes-exposure.md).
