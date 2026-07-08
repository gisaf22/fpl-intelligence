# Phase 2.1 — component forecast v1 (interim, frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 2.1 — the Phase-2 gate.
**Produced:** 2026-07-07 · `minutes > 0`, DGW excluded, per position, GW > 3, expanding walk-forward.
**Code:** `model/forecast/component_forecast.py` → `walk_forward_component_points()`.
**Question:** do situation features improve **within-position ranking** over the identity-only baseline
(`base_season`), on held-out gameweeks, conditional on appearance? (The main Phase-2 bet.)

## Model v1
- Components fit one-GW-ahead from **lag-safe** mart features (verified to exclude the current GW):
  goals & assists ~ `xgi_roll3` + `minutes_roll3` (Poisson); clean sheet ~ `goals_conceded_roll3` +
  `xgc_roll3` + `minutes_roll3` (logistic). Expanding walk-forward (fit on `gw < t`).
- **Minutes as a covariate, not a proportional offset** (exposure test rejected proportionality).
- Composed to E[points] via the FPL scoring rule (goal/assist/CS multipliers per position); constant/
  deferred pieces (appearance, saves, bonus, cards) dropped — a within-position constant does not change rank.

## Result (within-position Spearman vs incumbent)

| pos | base_season (incumbent) | component model | Δ | verdict |
|---|---|---|---|---|
| GK | 0.041 | 0.039 | −0.002 | tie (near chance; saves not yet added) |
| DEF | 0.185 | **0.197** | **+0.012** | ✅ features beat identity |
| MID | 0.336 | **0.353** | **+0.017** | ✅ features beat identity |
| FWD | 0.349 | 0.337 | −0.012 | ✗ behind incumbent |

## Findings
- **Features add ranking value where the data is rich — DEF (+0.012) and MID (+0.017) beat the
  identity-only baseline.** This is the first positive answer to the main Phase-2 bet: situation
  features (attacking form + expected minutes + fixture) improve within-position ranking over "who the
  player is," for the two most rankable outfield positions. Consistent with the families roster (xGI
  approved at DEF/MID).
- **FWD is behind (−0.012).** Forwards' points are goal-dominated and noisy, `base_season` (level)
  already ranks them well, and v1's attacking feature (`xgi_roll3`) plus the substitute-selection
  minutes effect are not yet enough. The salvaged "FRINGE > STABLE" finding and the xGI-horizon choice
  are the natural next levers.
- **GK ties** (≈ chance) — expected; the flagged **saves component (~18% of GK points)** is not yet in
  the composition.

## Status — interim, gate PARTIALLY met
Gate: beat baseline per position. **Met for DEF/MID; not for FWD/GK.** This is a genuine partial win, not
a full pass — recorded honestly. **Next levers (v2):** add the GK-saves component; FWD-specific features
(xGI horizon per "FRINGE > STABLE", recency/EW term); NB for goals; add `was_home`/fixture strength.
Conditional on appearance throughout (X1).
