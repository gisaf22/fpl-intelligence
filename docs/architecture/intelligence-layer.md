# Intelligence Layer (`serve/`)

> The package was renamed `intelligence/` → `serve/`. This doc keeps the filename
> `intelligence-layer.md` (to preserve inbound links); the layer is the `serve/` package.

## Purpose

The serve layer (`serve/`) produces concrete FPL decision-support outputs from trusted, governed data.
It sits at the top of the pipeline:

```
fpl.db (source database)
  ↓
dal/ — validated, deterministic (player_id, gw) spine + state features (the mart)
  ↓
model/ — gated terms → compose_points (e_points, e_points_uncond) → simulate_points (p10/p50/p90, p_haul)
  ↓   [assemble_forecast(mart): the forecast columns, merged onto the mart by an operational runner]
serve/ — player ranking and weekly reporting  ← this layer
```

The layer answers *"which players should I pick this week?"* through explicit, reproducible artifacts.

**The boundary is preserved as data.** `serve` **must not import `model`** (import-linter
`no_serve_to_research_or_model`). The forecast crosses as columns, not a call: an operational runner
merges `model.predictions.assemble_forecast(mart)` (`e_points`, `e_points_uncond`, `p10/p50/p90`,
`p_haul`) onto the mart on `(player_id, gw)`, and the serve modules read those columns.

---

## Recommendation modules — ranked by the model forecast (ADR-011)

Each module ranks by the validated model forecast, not a hand-weighted signal composite. The former
composites (xgi/fdr/minutes, statically weighted from a `weight_registry`) were retired module-by-module
after a real-mart head-to-head showed the forecast is never worse (and significantly better for
transfers/fixtures). See [ADR-011](../decisions/011-model-forecast-supersedes-composites.md) and
[docs/serve-model-integration.md](../serve-model-integration.md) for the frozen head-to-head numbers.

Per-position validity — which the composites hand-encoded as serve-side scope-guards (xgi excluded at
FWD/MID, fdr excluded everywhere) — is now enforced **upstream** by the model's per-position term gates
(ranking + level) and lag-safety. It moved up a layer; it was not dropped.

```python
from dal.pipeline import load as load_mart
from model.predictions import assemble_forecast   # done in the operational runner, not in serve
from serve import (
    rank_captain_candidates,
    rank_transfer_targets,
    rank_value_players,
    flag_availability_risk,
)

mart = load_mart().mart
enriched = mart.merge(assemble_forecast(mart), on=["player_id", "gw"], how="left")

captains  = rank_captain_candidates(enriched, target_gw=28)
transfers = rank_transfer_targets(enriched, target_gw=28)
value     = rank_value_players(enriched, target_gw=28)
risk      = flag_availability_risk(enriched, target_gw=28)   # availability needs no forecast column
```

| Module | Ranks by | Why | Eligibility |
|---|---|---|---|
| `captain.py` | `p_haul` (haul probability), tie-broken by the `p90` ceiling | Captaincy is a *ceiling* bet; `p_haul` is an absolute probability, comparable **across** positions | `minutes_roll3 >= 45` |
| `transfers.py` | `e_points_uncond` at `target_gw` | Best expected pick for the upcoming GW; lag-safe (see the forward-window note below) | `minutes_roll5 >= 30`; optional `position` filter |
| `value.py` | `e_points_uncond / purchase_price` | Ex-ante expected return per £m; `e_points_uncond` already prices appearance risk | `minutes_roll5 >= 30`, `purchase_price >= 3.5`; optional `max_price` |
| `availability.py` | (descriptive — not a forecast) | Minutes-stability warning layer; see below | all players returned |

`e_points_uncond` = P(play) × E[points | played] — the ex-ante unconditional expectation. `p_haul`/`p90`
are the conditional-on-appearance distribution reads from the simulator.

**Retired:** `fixtures.py`. "Best fixture run" is a multi-week question; under lag-safety the only honest
signal is the forecast for the *upcoming* GW, which is exactly what `transfers` ranks by and which
already prices fixture difficulty (the `fdr` term). So a lag-safe fixtures ranking duplicated transfers —
transfers subsumes it.

### Forward-window / leakage note (transfers, and why fixtures could not be rebuilt)

The forecast at GW N is lag-safe (its terms fit on GWs < N). But the precomputed forecast **column** at
N+1, N+2 is built from rolling state through N, N+1 — i.e. post-deadline. So summing the forecast over a
forward window is **not** decision-time-realisable and would let a backtest peek into its own outcome
window. Transfers therefore ranks the upcoming GW only. A true fixture-aware multi-week hold needs
per-decision multi-step forecasts frozen at the deadline — a deferred `model` piece, not faked here.

### Availability Risk (`availability.py`)

Descriptive, not a forecast — an **operational warning layer** flagging unstable minute patterns. It does
not predict injuries or suspensions.

| Risk Level | Condition |
|------------|-----------|
| HIGH | `minutes_roll3 < 30` |
| MEDIUM | `minutes_roll3 < 60` OR `minutes_trend == "falling"` OR divergence > 20 min |
| LOW | none of the above |

Long-horizon flag uses `minutes_roll8` for DEF/MID only (AVAIL-003 positional guard). All players at the
target GW are returned so consumers can filter for LOW-risk when building squads.

---

## Design principles

1. **Forecast-ranked, not hand-weighted.** Ranking is by the model forecast columns; there are no serve
   weight constants and no `weight_registry`. Governance of *which signal is valid where* lives in the
   model term gates upstream.
2. **The boundary crosses as data.** `serve` reads forecast columns off the enriched mart; it never
   imports `model` (import-linter 6/6).
3. **Explicit eligibility filters** — minimum-minutes thresholds and price floors are named constants
   documented with rationale (see [threshold-registry.md](../governance/threshold-registry.md)).
4. **Explainability columns** — every output carries the forecast reads it ranked on (`e_points_uncond`,
   `p90`, `p_haul`, the score) so a reviewer can reconstruct any row's rank from the output alone.
5. **Pure functions** — deterministic; identical output for identical input. (The simulator that produces
   `p_haul`/`p90` upstream is seed-pinned.)
6. **Input contract** — every module calls `validate_intelligence_inputs()` (`serve/input_contracts.py`),
   which asserts the required mart columns are present and raises `IntelligenceInputError` otherwise; the
   forecast-consuming modules additionally require their `assemble_forecast` columns.

---

## The report pipeline (`serve/scoring/`, `serve/reporting/`) — **REMOVED at `ae90398`**

There used to be a second surface here: a rho-based **signal report** that read the governed registry
(`outputs/registry/gw{N}/`) rather than the model forecast, gated at runtime by
`domain/registry/lifecycle.py::assert_operational_safe`. It was not part of the serve↔model
integration and was unaffected by ADR-011. (That gate has since been deleted too — with
`model/governance/promote.py` gone, nothing writes `outputs/registry/`, so the gate had no
passing input.)

Commit `ae90398` deleted the whole surface — `serve/scoring/`, `serve/reporting/`,
`domain/registry/{verdict,governance_lookup,governance_types}.py`, the `outputs/registry/gw36/`
bootstrap artifact and their tests — on the grounds that it had no consumer on the live decision
path. `serve/` now contains only the decision specs and the decision engine described above.

---

## Relationship to research signals

The recommendation modules consume **governed** inputs only — the DAL mart plus the model forecast
columns. They do not consume EDA registries from `research/findings/`, research-stage promoted lists,
or exploratory artifacts. For the mart contract this is enforced by `validate_intelligence_inputs()`
in `serve/input_contracts.py`.

## Current limitations

- **No price trajectory.** Value uses static current price; no FPL price rise/fall modelling.
- **Warmup period.** The forecast is undefined before the model's warmup GWs; rows without a scored
  forecast (`e_points_uncond`/`p_haul` NaN) are dropped from the ranked output. Early-GW output is thin.
- **Single-season scope.** The mart and the fitted terms cover one FPL season; the head-to-head edges are
  *promising, not multi-season-proven* (captain/value reached "not worse"; transfers/fixtures were
  significantly better on one season). Cross-season confirmation is the standing caveat.
- **No multi-week hold.** Transfers/fixtures rank the upcoming GW only — no fixture-aware forward window
  (see the leakage note). The multi-step forecast is deferred.
- **No declared output contract.** Upstream layers publish enforced schemas (`MART_SCHEMA`, `FEAT_SCHEMA`);
  the recommendation outputs are golden-tested, not contract-validated. The output column set is a
  convention, not a guarantee.

## Non-Goals

This layer explicitly does not:

- **Fit or own the points model** — it *consumes* the model forecast as data; the model lives in `model/`.
- Model injury probability, or simulate the transfer market / price dynamics.
- Optimize squad selection (a combinatorial problem requiring explicit constraint handling).
- Replace human judgement on news, motivation, or rotation.
- Consume external data beyond the DAL-governed database.
