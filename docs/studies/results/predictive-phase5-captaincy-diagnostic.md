# Door 1 — Captaincy diagnostic: is the edge irreducible or fixable? (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 5.
**Produced:** 2026-07-10 · **Code:** `model/eval/captaincy_diagnostics.py` (`captaincy_diagnostic_report`).
**Notebook:** `model/eval/captaincy_ceiling_diagnostic.ipynb`. Reuses the Phase-5 captaincy panel
(pool-free availability gate, ex-ante, blanks=0); all discrimination features strictly lagged. 35 GWs.

## Question & pre-registered decision rule
Phase 5 found a season-average beats the points model at captaincy, nothing separable on one season.
*Can more modelling ever help, or is the edge irreducible?* **Rule (before looking):** IRREDUCIBLE if
regret concentrated **and** AUC ~ null floor **and** divergent picks don't beat base_season; FIXABLE if
AUC clears the floor **or** divergent picks win; CEILING-TILT otherwise.

## Result

| # | question | finding |
|---|---|---|
| **Q1** | is captaincy won in a few GWs? | reducible regret **10.7 pts/GW**; top-20% of GWs hold **33%** (Gini **0.28**) — *moderate*, not a few-GW fluke |
| **Q2** | is the best captain predictable? | **hit@1 ≈ chance** for every strategy (base 0.03 / model 0.00 / p90 0.00 / ownership 0.03; chance 0.005) — the oracle is **unpredictable ex-ante** |
| **Q3** | when the model diverges, does it win? | model ≠ base on **27/35** GWs; win-rate **0.41** [0.26, 0.48], mean diff **−1.44 pts** — the model's deviations are **noise-negative** |
| **Q4** | any ex-ante signal separates the oracle? | combined LOGO-CV **AUC 0.614** vs min-detectable **0.581** — a **weak, real** signal (form `xgi_roll5` 0.66, ownership 0.63, price 0.63) barely above the one-season floor |

## Verdict — largely irreducible on this data (and underpowered to say more)
- **The single best captain is essentially unpredictable ex-ante** (Q2 hit@1 ≈ chance).
- **The model's weekly deviations from the season-average actively hurt** (Q3: 41% win-rate, −1.44 pts) —
  this is *why* base_season wins captaincy: the model adds noise at the top, not signal.
- **The only real signal is 'in-form premium'** (`xgi_roll5`/ownership/price), which `base_season`
  already approximates — and it sits **just above the one-season detectability floor** (AUC 0.614 vs 0.581),
  so it is **real-but-underpowered**.

**Decision (per the rule):** *largely irreducible on this data.* **Do not chase captaincy edge with more
model machinery** — the current model's divergent picks lose, and the residual signal is too weak to
confirm on one season. The honest resolution: **the definitive answer needs more seasons (Door 2)** to
power the weak in-form-premium signal; until then, captain in-form premiums (≈ `base_season` + a
form/ceiling tilt) and accept the rest is haul-noise.

## Failure points acknowledged
- **One-season power is the binding limit** — ~35 oracle observations; the min-detectable AUC (0.58) is
  high, so 'irreducible' here means *not detectable at this n*, not *proven absent*. The power floor is
  reported, not hidden — and it *is* the argument for Door 2.
- Leakage-guarded (oracle = realized; features strictly lagged); oracle not defined by the model's own
  `p90`; pool-free gate (ownership-pool a recorded robustness check); Q3/Q4 pre-registered as primaries.
