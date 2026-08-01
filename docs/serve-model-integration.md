# Serve ↔ model integration — record

**Type:** `changelog` · **Status:** in progress (captain + value + transfers + fixtures migrated; shared-root sweep next) · **Started:** 2026-07-31

Wiring the validated predictive layer (`model` — terms → `compose_points` → `simulate_points`) into the
operational advice layer (`serve`), replacing the pre-model **signal composites** module by module. Each
module is a **clean break**: the forecast path goes in, the old composite / scope-guards / `weight_registry`
entry come out, once a head-to-head shows the model is not worse.

## Architecture — the boundary is preserved
`serve` **must not import `model`** (import-linter `no_serve_to_research_or_model`, deliberate: serve
consumes the mart + governed artifacts, not the engine). So the forecast crosses as **data**, not a call:
`model.predictions.assemble_forecast(mart)` joins the mean (`e_points`, `e_points_uncond`) and the
distribution (`p10/p50/p90`, `p_haul`) into one per-(player, gw) frame; an operational runner (outside
`serve`) merges those columns onto the mart and hands the enriched frame to the serve modules, which read
the columns. Import-linter stays green (6/6).

## Governance — relocated, not dropped
The composites hardcoded signal-selection governance (xgi excluded at FWD/MID, etc.) in per-module
scope-guards + `weight_registry.yaml`. Under `e_points` this is **moot** (the forecast is not a signal
pick) and is **replaced** by the model's per-position **term gates** (ranking + level, incl. the level-gate
completion). Leakage is handled upstream by term lag-safety. So retiring the serve scope-guards + their
governance tests moves the rigor to the model layer; it is not a loss.

---

## captain — DONE (2026-07-31)

Ranks by the forecaster's **haul probability** `p_haul` (captaincy is a *ceiling* bet), tie-broken by the
`p90` ceiling. Because `p_haul` is an absolute probability it is comparable **across** positions — unlike
the retired within-position normalised composite. Replaced: the xgi form/involvement + fixture + minutes
composite (`weight_registry` `captain` block, the FWD/MID xgi scope-guards, `get_module_weights("captain")`,
and captain's weight-provenance).

### Head-to-head (real mart, 2025-26, GW6–38, n=32; frozen)

| captain ranker | avg captain return / GW | top-1 hit-rate |
|---|---|---|
| OLD — xgi composite | 3.22 | 0.00 |
| **NEW — model `p_haul`** | **5.09** | 0.00 |
| oracle (best possible) | 17.25 | 1.00 |

**Δ (new − old) = +1.9 pts/GW**, paired 95% CI **[−0.03, +3.9]**. The model captain is better on the point
estimate (+58%) and **never significantly worse**; the CI just touches zero — *promising, not proven on one
season*, which is the standing captaincy caveat (the edge needs multi-season, Door 2). Neither ranker picks
the exact best captain (hit-rate 0) — captaincy's ex-ante irreducibility, confirmed. The distribution reads
(`p90`/`p_haul`) are a capability the composite structurally lacked, independent of the ranking delta.

*(Measurement is a real-mart backtest — non-deterministic across data refreshes; the numbers above are the
interpretation, frozen at migration.)*

### Deletions (the clean break)
`weight_registry.yaml` `captain` block · captain's `_MODULE_SIGNAL_MAP` provenance entry · the captain
scope-guard tests in `test_governance_compliance.py` · the captain weight/provenance/fdr/FWD cases in
`test_runtime_consumer_alignment.py`. Nothing in the model layer moved; the term goldens reproduce.

---

## value — DONE (2026-07-31)

Ranks by the forecaster's ex-ante expected points per £m: `value_score = e_points_uncond / purchase_price`.
Because `e_points_uncond` = P(play) × E[points | played] already prices appearance risk, a rotation-doubtful
cheap punt is no longer flattered by a high per-cost score the way the raw xgi/cost composite flattered it.
Replaced: the xgi efficiency (`xgi_roll5/price`) + form (`xgi_roll3`) + consistency composite
(`weight_registry` `value` block, the FWD/MID xgi scope-guards, `get_module_weights("value")`, and value's
weight-provenance).

### Head-to-head (real mart, 2025-26, GW6–34, n=29; frozen)

Metric: mean **points-per-£m** over a 4-GW forward window (the existing value backtest,
`tests/helpers/value._points_per_cost`), top-10 of each ranker, paired per GW.

| value ranker | avg points-per-£m / GW |
|---|---|
| OLD — xgi composite | 2.214 |
| **NEW — model `e_points_uncond / price`** | **2.351** |

**Δ (new − old) = +0.137 ppc/GW**, paired 95% CI **[−0.165, +0.439]**; NEW wins **17/29** GWs. Better on
the point estimate (+6.2%) and **never significantly worse** — the CI spans zero, the same *promising, not
proven on one season* standing as captain (which cleared the identical bar at +1.9 pts/GW). This meets the
prove-then-delete bar: the model is not worse.

*(Measurement is a real-mart backtest — non-deterministic across data refreshes; the numbers above are the
interpretation, frozen at migration.)*

### Deletions (the clean break)
`weight_registry.yaml` `value` block · value's `_MODULE_SIGNAL_MAP` provenance entry · the `TestValueMidXgiGuard`
+ `test_value_fwd_efficiency_score_neutral` guards in `test_governance_compliance.py` · value's rows in
`test_runtime_consumer_alignment.py` (module-paths list, weight-loader/metadata/provenance parametrizations).
Nothing in the model layer moved; the term goldens reproduce.

---

## transfers — DONE (2026-07-31)

Ranks incoming candidates by the forecaster's ex-ante expected points for the **upcoming** GW:
`transfer_score = e_points_uncond` at `target_gw`. Price is carried in the output as a budget aid, not
in the score. Replaced: the xgi form + momentum + fixture + involvement + minutes composite
(`weight_registry` `transfers` block, the FWD/MID xgi scope-guards, `get_module_weights("transfers")`,
and transfers' weight-provenance).

**Forward-window decision (temporal integrity).** A transfer is a multi-week hold, so the natural score
is Σ `e_points_uncond` over the next K GWs. But the forecast column past `target_gw` is **not**
decision-time-available: by the lag-1 contract, `e_points_uncond[N+1]` is built from rolling state
through GW N and `[N+2]` through N+1 — both post-deadline. Summing the precomputed column would let the
ranker peek into the outcome window, inflating the head-to-head and producing a ranking no live run could
reproduce. So transfers scores the **upcoming GW only** (strictly lag-safe, same footing as OLD, which
reads `features[gw==N]`). A true fixture-aware forward hold needs per-decision multi-step forecasts frozen
at the deadline — deferred as a separate model-layer piece, not faked here.

### Head-to-head (real mart, 2025-26, GW6–35, n=30, 3-GW forward hold; frozen)

Metric: mean **cumulative `total_points`** over the next 3 GWs (the existing transfer backtest,
`tests/helpers/transfers._cumulative_future_returns`), top-10 of each ranker, paired per GW.

| transfer ranker | avg cumulative return / decision |
|---|---|
| OLD — xgi composite | 9.14 |
| **NEW — model `e_points_uncond` @ target_gw** | **10.87** |

**Δ (new − old) = +1.73 pts**, paired 95% CI **[+0.76, +2.70]**; NEW wins **24/30** GWs. This one is
**significantly better** — the CI excludes zero, a stronger result than captain (CI touched zero) or value
(CI spanned zero). The ranker uses only pre-deadline data, so the edge is real, not a peek.

*(Measurement is a real-mart backtest — non-deterministic across data refreshes; the numbers above are the
interpretation, frozen at migration.)*

### Deletions (the clean break)
`weight_registry.yaml` `transfers` block · transfers' `_MODULE_SIGNAL_MAP` provenance entry · the
`TestTransfersMidXgiGuard` / `TestFwdZeroingGuard` / `TestFixtureContextWired` guards in
`test_governance_compliance.py` · transfers' rows in `test_runtime_consumer_alignment.py` (module-paths,
weight-loader/metadata/provenance parametrizations, the `TestFwdScopeGuard` xgi-neutralisation class).
**`fixtures` is now the last composite** — the shared-root sweep follows it. Nothing in the model layer
moved; the term goldens reproduce.

---

## fixtures — DONE / MERGED INTO transfers (2026-08-01)

**Decision: merge, don't rebuild.** "Fixtures" asks *which players have a good fixture run ahead* — a
multi-week question that needs a per-decision multi-step forecast frozen at the deadline (the deferred
model piece). Under the lag-safe rule (the transfers ruling), the only honest signal available is the
model's expected points for the **upcoming** GW — which is exactly what `transfers` now ranks by, and
which already prices fixture difficulty through the gated `fdr` term. So a lag-safe fixtures ranking is a
duplicate of transfers. Rather than ship a redundant surface, **`fixtures` is retired and transfers
subsumes it.** (The old composite's forward-window read of `fixture_context`/`fdr` was schedule data —
not itself leaky — but its scored signal was the refuted `fdr` + an unvalidated team-attack proxy.)

### Head-to-head (real mart, 2025-26, GW6–35, n=30, horizon 3; frozen)

Prove-then-delete: OLD fixtures composite vs the model `e_points_uncond` @ target_gw (the transfers
ranker), on mean cumulative `total_points` over the next 3 GWs, top-10 each, paired per GW.

| ranker | avg cumulative return / decision |
|---|---|
| OLD — fixtures composite | 8.65 |
| **NEW — model `e_points_uncond`** | **10.87** |

**Δ (new − old) = +2.23 pts**, paired 95% CI **[+1.18, +3.27]**; NEW wins **25/30** GWs — **significantly
better**, CI excludes zero. NEW's column is identical to the transfers head-to-head, confirming the merge
(fixtures collapses to transfers under lag-safety).

*(Real-mart backtest — non-deterministic across refreshes; frozen at migration.)*

### Deletions (this commit)
`serve/fixtures.py` (whole module) · its `serve/__init__.py` export · the `rank_fixture_opportunities`
behavioral tests (`TestRankFixtureOpportunities` + fixtures explainability + `_ALL_FUNCTIONS` entry in
`test_intelligence_outputs.py`; `TestFdrAvgNotScored` in `test_governance_compliance.py`;
`TestFdrRemovedFromScoring` in `test_runtime_consumer_alignment.py`). The `_intelligence_module_paths()`
list is now empty.

### Deliberately deferred to the shared-root sweep (next commit)
The `weight_registry.yaml` `fixtures` block, `provenance._MODULE_SIGNAL_MAP["fixtures"]`, and the
registry/provenance machinery tests (`TestWeightRegistryLoader`, `TestScoreProvenance`,
`TestNoHardcodedWeights`) are left intact and green here — they are removed **wholesale** when
`weight_registry.{yaml,py}` + `provenance.py` are deleted, since `fixtures` is the last module and its
registry/provenance entries have no separate consumer.

---

## Remaining
- **Operational runner** — a top-level orchestrator that builds the enriched frame (`assemble_forecast` →
  merge) and feeds the serve modules; captain is migrated but not yet wired into a production entry point.
- **shared-root sweep** (next) — with every composite retired, delete `serve/weight_registry.{yaml,py}`,
  `weighted_composite`/`normalize_within_position` from `input_contracts.py` (keep
  `validate_intelligence_inputs`), `serve/provenance.py`, and their now-subjectless tests
  (`test_weighting_authority.py`, the weight/provenance test classes). Then ADR-011 (supersede ADR-002) +
  doc cleanup.
- **availability** — descriptive; optional `p_play`/`p60` enrich, low priority.
- **Report pipeline** (`serve/scoring` + `serve/reporting`, the rho-composite surface) — a separate
  decision: keep as a descriptive signal report, or migrate later.
