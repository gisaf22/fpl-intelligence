# Phase 5 — decision evaluation: captaincy (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 5.
**Produced:** 2026-07-09 · **Code:** `model/eval/decisions.py` (`captaincy_backtest`, `build_captaincy_panel`,
`_p_play`). Ex-ante scoring via `walk_forward_points(mart, predict_all=True)` (scores potential blanks);
`P(play)` from lagged minutes/starts (no injury news — a real limitation). N=2000 sim draws.

## Question
Not "is the model accurate" (Phase 3) or "calibrated" (Phase 4) but **does it help you pick a captain** —
with honest error bars? One pick per GW, scored by realized points (blanks=0, so rotation is priced).

## Strategies & views
Strategies: **template** (ownership), **base_season** (expanding mean incl blanks), **model_mean**
(`full_pts`), **model_mean × P(play)** (rotation-adjusted), **ceiling_p90**, **ceiling_phaul**. Two
choice-set views: **pool-free** (lagged-minutes availability gate, model-agnostic — primary) and
**ownership top-50** (secondary). Reads: mean pts/GW + **block-bootstrap CI** (blocks of 4 GWs, A5.1),
head-to-head win rate vs template, regret vs the oracle.

## Result — pool-free (35 GWs, oracle 16.66 pts/GW)

| strategy | mean pts/GW | block 95% CI | win-rate vs template | regret |
|---|---|---|---|---|
| **base_season** | **6.00** | [4.54, 7.69] | 0.11 | 10.66 |
| ceiling_p90 | 5.26 | [3.40, 6.71] | 0.37 | 11.40 |
| ceiling_phaul | 5.17 | [3.34, 6.89] | 0.37 | 11.49 |
| template | 4.97 | [3.77, 6.49] | — | 11.69 |
| model_mean | 4.89 | [3.34, 6.17] | 0.37 | 11.77 |
| model_mean × P(play) | 4.43 | [3.31, 5.60] | 0.34 | 12.23 |

**Ownership top-50 view agrees** (base_season 6.00 best, ceilings ~5.3, model_mean 5.06) — the verdict
is **robust to the choice-set definition**, so the pool question is moot.

## Findings (honest, and humbling)
1. **A simple season-average (base_season) is the best captaincy strategy** — it beats the full points
   model, the ceiling strategies, and template on mean pts/GW, in *both* views. The sophisticated model
   does **not** improve captaincy over a stable average.
2. **The distribution *does* add value: ceiling > mean** (p90/phaul ~5.2 > model_mean 4.9). Captaining by
   *upside* beats captaining by the mean — the one clear positive for the Phase-3 distribution — but not
   by enough to top base_season.
3. **The `P(play)` multiplier *hurt*** (4.43 < 4.89) — down-weighting by lagged rotation risk (no injury
   news) made captaincy worse here.
4. **On one season, nothing is statistically separable** — every block-bootstrap CI overlaps heavily
   (e.g. model_mean [3.34, 6.17] vs base_season [4.54, 7.69]). Exactly what **A5.1** guards against:
   a single season cannot distinguish these strategies. **No over-claiming.**
5. **Mean and win-rate diverge:** base_season has the highest mean but a *low* head-to-head win rate
   (0.11) — its edge comes from a few big GWs; model_mean wins more GWs (0.37) but by smaller margins.
   Reporting both is why the picture is honest rather than a single misleading number.
6. **Regret ~11 pts/GW** — even the best strategy leaves ~11 of the oracle's 16.7 on the table;
   captaincy is haul-dominated and intrinsically hard to time.

## Verdict
The stack is **excellent for ranking (Phase 3) and calibrated (Phase 4)** — but **that skill does not
translate into a measurable captaincy edge over a simple season-average on one season of data.** The
distribution helps (ceiling > mean); the point model and the `P(play)` adjustment do not. This is the
value of decision evaluation: it separates "accurate/calibrated" from "actually useful for the decision,"
and here the honest answer is "not demonstrably, yet, on this sample." `P(play)` (X1) is now built
(pred 0.374 vs obs 0.383, well-calibrated on the mean), so blanks finally enter the evaluation.

## Scope limits / next levers
Single season (A5.1 — wider CIs need multi-season); **captaincy only** (squad/transfers, team-stacking
deferred); `P(play)` from lagged minutes only (**no injury/press-conference news** — the biggest gap vs
real managers); FWD interval dispersion (Phase 4 residual) may under-serve ceiling picks. A multi-season
backtest and injury-aware `P(play)` are the clear next steps before any decision claim can sharpen.
