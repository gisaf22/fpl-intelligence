# Door 1 rerun — does 'largely irreducible' survive the ceiling strategies and a walk-forward CV?

**Audits:** [predictive-phase5-captaincy-diagnostic.md](predictive-phase5-captaincy-diagnostic.md) (frozen 2026-07-10).
**Produced:** 2026-08-14 · **Code:** `model/eval/captaincy_diagnostics.py`
(`divergence_winrate` generalized to arbitrary score-column pairs; `oracle_discrimination` now reports
both CV schemes via `_oos_scores`/`_auc_and_floor`). Same Phase-5 captaincy panel, same pool-free
availability gate, same 35 GWs, N=2000 sim draws. No new modelling — both are reruns of existing
diagnostic code with different inputs.

## Why rerun

The frozen diagnostic issued a verdict — *largely irreducible, do not chase captaincy edge with more
model machinery* — on the strength of two crux tests. An audit of the code found both under-scoped:

1. **Q3 (divergence) was hardcoded to `base_season` vs `e_points`.** It only ever asked whether the
   *mean* strategy's divergent picks win. But `model_mean` was the strategy that already showed no
   edge; the strategies that beat template in
   [predictive-phase5-decisions.md](predictive-phase5-decisions.md) were the **ceilings**
   (`ceiling_p90`/`ceiling_phaul`, win-rate 0.37 vs template's own 0.11 baseline). The crux was never
   asked of them.
2. **Q4 (discrimination) used leave-one-GW-out CV** (`sub[sub["gw"] != gw]`) — training on gameweeks
   *after* the test GW. Every term-level fit in `model/terms/` is strictly walk-forward
   (`_poisson_component.fit`: `train = df[df["gw"] < t]`). The frozen doc's "weak, real signal"
   (AUC 0.614 vs floor 0.581) rests on a CV scheme the rest of the stack does not use, and gameweeks
   autocorrelate — exactly the condition under which LOGO flatters.

## Q3 result — the crux, asked of every strategy that made a Phase-5 claim

| baseline | challenger | n divergent | win-rate | win-rate 95% CI | mean pts Δ | Δ 95% CI |
|---|---|---|---|---|---|---|
| base_season | e_points | 25/35 | 0.440 | [0.280, 0.560] | +0.20 | [−1.72, +1.64] |
| base_season | **p90** | 26/35 | 0.385 | [0.269, 0.462] | −0.62 | [−2.50, +0.58] |
| base_season | **p_haul** | 26/35 | 0.385 | [0.231, 0.500] | 0.00 | [−1.62, +1.42] |
| ownership_count | **p90** | 28/35 | 0.464 | [0.321, 0.571] | +0.71 | [−1.79, +2.75] |
| ownership_count | **p_haul** | 27/35 | 0.444 | [0.296, 0.556] | +1.33 | [−0.63, +3.37] |

**No ceiling strategy's divergent picks win at a rate the CI can distinguish from chance.** Every
win-rate point estimate sits at or below 0.5, every win-rate CI includes or falls below it, and every
paired mean-delta CI contains zero. Against `base_season` the ceilings are, if anything, worse than
the mean was (0.385 vs 0.440). The one directionally favourable cell is **template vs `p_haul`**
(+1.33 pts/GW, CI [−0.63, +3.37]) — consistent in sign with the Phase-5 finding that ceilings beat
template, but the interval straddles zero, so it does not clear the bar the pre-registered rule sets.

## Q4 result — LOGO vs walk-forward, each against its own floor

| CV scheme | out-of-sample AUC | min-detectable AUC (95th pct permutation null) | signal? | rows scored | GWs scored |
|---|---|---|---|---|---|
| leave-one-GW-out (frozen method) | **0.626** | 0.577 | **yes** | 7528 | 35 |
| strictly walk-forward (`gw < t`) | **0.561** | 0.578 | **no** | 7311 | 34 |

Single-feature AUCs (unchanged, whole-panel): `xgi_roll5` 0.658, `ownership_count` 0.629,
`purchase_price` 0.628, `p90` 0.546, `was_home` 0.522, `fdr_avg` 0.431.

**The signal does not survive the chronological constraint.** This is not a power-loss artifact: the
walk-forward scheme loses only one gameweek and 217 of 7528 rows, and its own permutation floor is
0.578 — statistically the same bar as LOGO's 0.577. Same features, same panel, same floor; the only
thing that changed is whether the fold may see the future. The 0.065 AUC drop is what that peek was
worth.

## Verdict — the verdict survives, and Q4 now argues it more strongly than the frozen doc did

The pre-registered rule was: **FIXABLE if AUC clears the floor OR divergent picks win.**

- **Divergent picks do not win** — now confirmed for `p90` and `p_haul`, not just `e_points`. The
  frozen verdict was under-scoped when written, but the missing tests **agree** with it. This leg
  holds for every strategy that ever made a Phase-5 claim.
- **The AUC does not clear the floor** under the CV discipline the rest of the stack uses (0.561 vs
  0.578). The frozen doc's "weak, real signal … real-but-underpowered" was the *one* piece of
  evidence pointing toward FIXABLE, and it is an artifact of the non-chronological fold.

So *largely irreducible* stands, and it no longer needs the "real-but-underpowered signal" hedge: on
this season, with these features, there is **no ex-ante discrimination of the oracle captain that a
manager could actually have used**. The honest resolution is unchanged — captain in-form premiums
(≈ `base_season`) and accept the rest is haul-noise — but the Door-2 (multi-season) motivation now
rests on a weaker prior than the frozen doc implied: what Door 2 would be powering is a signal that
walk-forward CV cannot currently see at all, not one measured just above its floor.

**Q4's LOGO number should not be retired.** It answers a real and different question — *is there
structure here at maximum power?* — and its gap to walk-forward is itself the finding. Both are
reported side by side in `oracle_discrimination`; neither replaces the other.

## Frozen numbers no longer reproduce (model drift, not a rerun artifact)

The default Q3 pair now reads **25 divergent GWs / 0.440 / +0.20 pts**, against the frozen doc's
**27 / 0.41 / −1.44**. This is drift in `e_points` since 2026-07-10 (the god-file deletion and the
mean-features `fdr_avg` work both moved compose — see `docs/model-redesign-changelog.md`), **not** an
effect of the generalization: running the pre-edit logic verbatim on the current panel reproduces
25 / 0.440 / +0.20 exactly, and the pool carries zero nulls in all six score columns, so the added
`dropna` is a no-op for that pair. Q1 concentration likewise drifted slightly (top-20% share 0.332,
Gini 0.281, vs the frozen 0.33 / 0.28 — unchanged at reported precision). The frozen doc's *direction*
on Q3 (model deviations are noise-negative) has weakened to roughly zero-mean under the current model;
its conclusion is unaffected because zero-mean divergence is still not a win.

## Failure points acknowledged

- **Block bootstrap on a sparse subset.** Divergent GWs are non-contiguous, so a block of 4 is 4
  adjacent *divergent* GWs, not 4 adjacent calendar GWs. The autocorrelation guard is approximate
  here in a way it is not in the Phase-5 backtest (documented in `divergence_winrate`'s docstring).
  Inherited from the frozen method, not introduced — but it applies to all ten CIs above.
- **Thin early walk-forward folds.** GW5's fold trains on ~1 prior gameweek and 1 prior oracle. That
  thinness is genuine — a deployable model does not have data it has not seen — and it is part of why
  walk-forward scores lower. No minimum-train guard was added, deliberately: adding one would change
  which GWs are scored and make the two schemes non-comparable.
- **One season is still the binding limit** for everything here (35 oracle observations, 34
  walk-forward). "No detectable signal" means *not detectable at this n under this CV*, not proven
  absent. That was the frozen doc's caveat and it remains the right one.
- **Position is still not stratified** in any Q1–Q4 test; the pool is ~42% MID / 38% DEF / 10% FWD /
  9% GK and the realized oracle over 35 GWs was MID 15 / DEF 13 / FWD 7 / GK 0. Pooling is defensible
  for a squad-wide decision but no per-position claim is licensed by any number in this document.
