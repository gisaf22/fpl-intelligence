# ADR-011 — The Model Forecast Supersedes the Serve Signal Composites

**Status:** Accepted
**Date:** 2026-08-01 (serve↔model integration; all serve composites retired)
**Supersedes:** [ADR-002 — Additive Weighted Composition for the Scoring Engine](002-additive-weighted-scoring.md)
**Applies to:** `serve/{captain,value,transfers}.py` (and the retired `serve/fixtures.py`), the deleted
`serve/weight_registry.{yaml,py}` + `serve/provenance.py`

---

## Context

ADR-002 chose **additive weighted composition** for the serve scoring engine: each recommendation
module (captain, value, transfers, fixtures) combined rank-normalised signals into a composite score
with weights carried in `weight_registry.yaml`. That decision was correct **for its moment** — one
season of data, no validated predictive model, and a hard explainability requirement made a
hand-weighted composite the defensible choice, and its ADR-002 alternatives table explicitly deferred
"linear regression weights / GBM / neural net" on the data-size-and-interpretability grounds.

Since then the predictive layer was built and validated: `model` emits per-position gated **terms** →
`compose_points` (a conditional mean `e_points`, and the ex-ante `e_points_uncond` = P(play) ×
E[points | played]) → `simulate_points` (the distribution: `p10/p50/p90`, `p_haul`), surfaced by
`model.predictions.assemble_forecast`. This is an evaluation-derived, per-position-valid forecast with
the interpretability ADR-002 demanded (every term is gated and traceable), and it is *not* a black box.

With the forecast available, the composites are strictly dominated: they hand-weight proxy signals
(xgi rolls, team-goal aggregates, DGW flags) that the forecast already prices — fixture difficulty lives
inside the `fdr` term, appearance risk inside `e_points_uncond`. Head-to-head backtests confirmed the
forecast is never worse, and significantly better for transfers and fixtures (see
`docs/serve-model-integration.md`).

---

## Decision

**Retire the serve signal composites. Each recommendation module ranks by the model forecast, read as
data off the enriched mart** (`serve` does not import `model` — the import-linter contract
`no_serve_to_research_or_model` is preserved; an operational runner merges `assemble_forecast(mart)`
columns onto the mart, serve reads the columns):

| module | ranks by |
|---|---|
| captain | `p_haul` (haul probability — a ceiling bet), tie-broken by the `p90` ceiling |
| value | `e_points_uncond / purchase_price` (ex-ante expected return per £m) |
| transfers | `e_points_uncond` at `target_gw` (best expected pick for the upcoming GW) |
| fixtures | **retired** — under lag-safety it duplicates transfers; transfers subsumes it |

The per-position ranking/level governance that the composites encoded as serve-side scope-guards
(xgi excluded at FWD/MID, fdr excluded everywhere) **relocates upstream to the model term gates**, where
it is enforced by construction and lag-safety — it is not dropped.

Consequently the weighting machinery is deleted: `serve/weight_registry.{yaml,py}`,
`serve/provenance.py`, and `weighted_composite` / `normalize_within_position` in
`serve/input_contracts.py` (the input contract `validate_intelligence_inputs` stays).

---

## Why this does not reopen the ADR-002 alternatives

ADR-002 rejected learned weights because there was no validated model and no held-out season. That
constraint is discharged, not ignored: the forecast's terms were each validated (ranking + level gates,
lag-safety, refutation of the ones that did not carry — e.g. `fdr_avg`, `team_xg_roll3`), and the
migration was gated per module by a real-mart head-to-head with a frozen paired-CI, not adopted on
faith. Explainability is preserved by the gated-terms decomposition, satisfying ADR-002's hard
requirement. This is the "future season with a validated model" branch ADR-002's Consequences
anticipated, now taken.

---

## Consequences

- The composites, `weight_registry`, and serve-side `score_provenance` no longer exist. Traceability for
  a recommendation now runs through the model layer: `assemble_forecast` → `compose`/`simulate` → the
  gated terms.
- **Forecast leakage boundary (transfers/fixtures):** the forecast at GW N is lag-safe (its terms fit on
  GWs < N), but the precomputed forecast column at N+1, N+2 embeds post-N rolling state. So a *forward
  window* of the forecast is **not** decision-time-realisable; transfers ranks the upcoming GW only. A
  true fixture-aware multi-week hold needs per-decision multi-step forecasts frozen at the deadline —
  deferred as a separate `model` piece.
- The report pipeline (`serve/scoring/*`, `serve/reporting/*`, `signal_selector`, `SignalManifest`) is a
  **separate** rho-based surface and is unaffected — it never consumed `weight_registry`.
- The anti-re-litigation evidence stands: `evaluation_metadata.yaml`, `signal_traceability.yaml`, and the
  decision-slug verdicts are untouched. ADR-002 is superseded, not deleted.
- Re-introducing a serve-side hand-weighted composite is now an ADR-level reversal requiring a new record.
