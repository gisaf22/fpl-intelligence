# Serve ↔ model integration — record

**Type:** `changelog` · **Status:** in progress (captain migrated) · **Started:** 2026-07-31

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

## Remaining
- **Operational runner** — a top-level orchestrator that builds the enriched frame (`assemble_forecast` →
  merge) and feeds the serve modules; captain is migrated but not yet wired into a production entry point.
- **value / transfers / fixtures** — migrate to `e_points_uncond` / forward-window `e_points` (fixtures ≈
  transfers — candidate merge); retire the rest of `weight_registry` after the last leaves it.
- **availability** — descriptive; optional `p_play`/`p60` enrich, low priority.
- **Report pipeline** (`serve/scoring` + `serve/reporting`, the rho-composite surface) — a separate
  decision: keep as a descriptive signal report, or migrate later.
