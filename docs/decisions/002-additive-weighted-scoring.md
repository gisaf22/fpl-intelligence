# ADR-002 — Additive Weighted Composition for the Scoring Engine

**Status:** Accepted  
**Date:** 2026-05-26 (SYNTH-01 execution; weight_registry.yaml locked)  
**Applies to:** `intelligence/scoring/scoring_runner.py`, `signals/governance/weight_registry.yaml`

---

## Context

The scoring engine combines signals from multiple lenses (form, availability, market, fixture) into a single per-player composite score used for captain, transfer, and value recommendations. A composition method must be chosen.

Available data: one season (25/26, GW 1–38), approximately 100–300 player-gameweek rows per position group per evaluation window. This is insufficient for ML model training without severe overfitting risk — the sample size is too small relative to the number of potential feature interactions, and there is no held-out validation season at training time.

Interpretability is a hard requirement. The explainability model (`docs/architecture/explainability-model.md`) requires that every score component is human-readable and traceable to a governed signal with a documented evaluation history. A model whose weights cannot be inspected without executing code violates this requirement.

---

## Decision

**Additive weighted combination** of rank-normalised signal scores. Weights are derived from SYNTH-01 partial rho per (signal, position) pair and stored in `signals/governance/weight_registry.yaml`.

**Equal-weight default rule:** when rho evidence does not improve by ≥ 0.02 over equal weights at a given (signal-group, position), equal weights are used. This rule was applied uniformly in SYNTH-01 — all seven position groups in the 25/26 season preferred equal weights by this criterion. The 0.02 threshold is the materiality gate: below it, the rho difference is within measurement noise given a single season and the improvement does not justify the maintenance cost of unequal weights.

No interaction terms, no position-specific models, no ML components.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Linear regression weights | Requires held-out validation season not available at training time; overfits on ~100–300 rows; weights are not interpretable in terms of signal quality |
| Gradient boosted / neural net | Same data-size problem at higher severity; violates explainability requirement; opaque to seasonal review |
| Manual editorial weights | Prior state of the system (pre-SYNTH-01); weights were PROVISIONAL-EDITORIAL with no evidential basis; replaced by evaluation-derived weights in Phase 6–7 |
| Multiplicative composition | No theoretical basis for multiplicative combination of rank-normalised scores; not used in comparable sports analytics applications |

---

## Consequences

- Weights in `weight_registry.yaml` are equal-weight for all position groups as of 25/26. They are not "trained" — they are a governance record that equal weights passed the ≥ 0.02 materiality test.
- Weights must be re-evaluated each season. If 26/27 evidence shows a rho improvement ≥ 0.02 with unequal weights for any position group, `weight_registry.yaml` is updated after the SYNTH-01 re-run.
- No ML model is permitted in the composition layer. Any proposal to add ML must address the data-size constraint and the explainability requirement before consideration.
- The composite score is a sum of weighted rank-normalised components. The maximum score is bounded and the contribution of each signal is directly readable from `weight_registry.yaml`.
