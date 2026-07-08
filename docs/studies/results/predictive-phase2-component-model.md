# Phase 2.1 — component forecast v1 (interim, frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 2.1 — the Phase-2 gate.
**Produced:** 2026-07-07 · `minutes > 0`, DGW excluded, per position, GW > 3, expanding walk-forward.
**Code:** `model/forecast/component_forecast.py` → `walk_forward_component_points()`.
**Question:** do situation features improve **within-position ranking** over the identity-only baseline
(`base_season`), on held-out gameweeks, conditional on appearance? (The main Phase-2 bet.)

## Model (v2)
- Components fit one-GW-ahead from **lag-safe** mart features (verified to exclude the current GW):
  goals & assists ~ `xgi_roll3` + `minutes_roll3` (Poisson); clean sheet ~ `goals_conceded_roll3` +
  `xgc_roll3` + `minutes_roll3` + `was_home` (logistic); **GK saves ~ `xgc_roll3` + `minutes_roll3`
  (Poisson)**, converted at 3 saves = 1 pt. Expanding walk-forward (fit on `gw < t`).
- **Minutes as a covariate, not a proportional offset** (exposure test rejected proportionality).
- **`was_home` in the clean-sheet model only** — venue helps defenders (v2 added +0.019 at DEF) but *hurt*
  MID/FWD attacking when included there (v1→v2 A/B). A feature-placement finding, recorded.
- Composed to E[points] via the FPL scoring rule; constant/deferred pieces (appearance, bonus, cards) dropped.

## Result (within-position Spearman vs incumbent)

| pos | base_season (incumbent) | component model (v2) | Δ | verdict |
|---|---|---|---|---|
| GK | 0.041 | 0.039 | −0.002 | parity (GK ≈ chance for all models; saves added) |
| DEF | 0.185 | **0.217** | **+0.031** | ✅ features beat identity |
| MID | 0.336 | **0.355** | **+0.019** | ✅ features beat identity |
| FWD | 0.349 | 0.337 | −0.012 | ✗ behind incumbent (scope limit) |

*(v1, for the record: DEF +0.012, MID +0.017, FWD −0.012, GK −0.002. v2 adds `was_home`→CS and GK-saves.)*

## Findings
- **Features beat identity-only, materially, at DEF (+0.031) and MID (+0.019)** — the main Phase-2 bet is
  answered *yes* for the rankable outfield positions. Consistent with the families roster (xGI at DEF/MID).
- **Venue is a defensive signal, not an attacking one.** `was_home` lifts clean-sheet ranking (DEF) but
  adds noise to goals/assists (MID/FWD) — so it belongs only in the CS model. Concrete feature-placement lesson.
- **GK reaches parity** with the incumbent once saves are added (~18% of GK points), but no better — GK
  ranking is near-chance for *every* model (echoes Phase 0). An honest ceiling, not a fixable gap.
- **FWD remains behind (−0.012) — an honest scope limit.** Forwards' points are goal-dominated; their
  scoring *level* (`base_season`) already ranks them well, and lagged `xgi_roll3` doesn't beat it. The
  salvaged **"FRINGE > STABLE"** / xGI-horizon findings point to **position-specific FWD features**
  (roll5 horizon, recency/EW, sub-context) — real future work, not a quick win.

## Status — gate: 2 of 4 pass, 1 parity, 1 miss (honest)
Gate = beat baseline per position. **DEF ✅ / MID ✅ / GK parity / FWD ✗.** A real, material result for the
rankable positions — not a full pass, not a null. Conditional on appearance throughout (X1). FWD-specific
modelling and NB-for-goals are the recorded next levers; diminishing returns judged reached for v2.
