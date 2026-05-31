# ADR-001 — Spearman Rank Correlation as the Signal Evaluation Metric

**Status:** Accepted  
**Date:** 2026-05-22 (lens study design lock)  
**Applies to:** All signal-target association measurement in lens studies, SYNTH-01, and registry rho values

---

## Context

FPL decisions are ranking decisions: which player to captain, which player to transfer in. The output of the scoring engine is an ordered list, not a point estimate of expected points. The metric used to characterise signal quality must match the decision structure.

`total_points` is non-normal: heavily right-skewed by haul gameweeks where a single player returns 15–20+ points. A player who hauls once in a 5-GW window will dominate a Pearson correlation even if their other four GW returns are unremarkable. This conflates "haul concentration" with "signal quality" — they are different properties.

Per-GW evaluation produces 33 rho estimates over the study window (GW 6–33 for SYNTH-01). Temporal stability of rho across GW blocks is used to confirm that signal quality holds across different seasonal phases, not just in aggregate.

---

## Decision

**Spearman rank correlation** is the sole association metric for signal-target evaluation.

Bootstrap 95% confidence intervals (1000 resamples) are reported per signal per position. Signal status (`informative` / `uninformative`) is determined by whether the CI excludes zero — not by rho magnitude alone. A signal that passes the CI gate and a practical meaningfulness check on outcome distribution separation is classified `informative`.

Temporal stability is assessed by computing rho independently in three equal GW blocks (early, mid, late season). A signal that passes in ≥ 2/3 blocks is classified as stable.

---

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Pearson correlation | Assumes linearity; sensitive to haul-season outliers; measures magnitude association rather than rank association, which is not what FPL decisions use |
| RMSE / MAE (regression metrics) | Penalises point-estimate error; inapplicable to a ranking problem; would require training a regression model, introducing overfitting risk on a single season |
| AUC (binary classification) | Only applies to the availability binary target (`played_next_gw`); cannot unify evaluation across form, market, and availability signals |
| Kendall's τ | Computationally slower; no practical advantage over Spearman for this use case; Spearman is the standard in sports analytics literature |

---

## Consequences

- Signal rho values in `signals/characterisation/SIGNAL_REGISTRY.md` and `signals/governance/evaluation_metadata.yaml` are Spearman rho, not Pearson.
- Rho is not a weight directly — it is a quality indicator. Weight derivation for the composite scorer uses SYNTH-01 partial rho with the equal-weight default rule (see ADR-002).
- Rho values are bivariate; they do not reflect partial effects or signal interactions. Cross-signal redundancy is assessed separately via correlation analysis before SYNTH-01 candidate selection.
- Haul-sensitivity is tracked as a separate diagnostic (geometry analysis in `signals/characterisation/geometry.py`) because Spearman alone does not surface it.
