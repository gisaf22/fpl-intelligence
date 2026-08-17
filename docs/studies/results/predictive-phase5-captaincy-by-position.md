# Captaincy per position — the last untested cut, and a flat null

**Audits:** [predictive-phase5-captaincy-realistic-pool.md](predictive-phase5-captaincy-realistic-pool.md)
(which raised this question and did not answer it),
[predictive-phase5-captaincy-diagnostic-rerun.md](predictive-phase5-captaincy-diagnostic-rerun.md),
[predictive-phase5-decisions.md](predictive-phase5-decisions.md).
**Produced:** 2026-08-14 · **Run against commit:** `c475873` (working tree: `model/eval/captaincy_backtest.py`,
`model/eval/captaincy_diagnostics.py`, `model/eval/metrics.py` modified — frozen study numbers do not
reproduce against current code, see prior reruns).
**Code:** `model/eval/captaincy_backtest.py::captaincy_by_position`;
`model/eval/metrics.py::block_bootstrap_draws`. 35 GWs, N=2000 sim draws, `minutes_roll3 >= 45` gate,
pre-deadline `ownership_lag` pools throughout.

## Why

The restricted-pool study found the oracle's position mix flips with pool size — MID-dominated on the
full pool (MID 15 / DEF 13 / FWD 7), FWD-dominated at top-20 (FWD 15 / DEF 12 / MID 6 / GK 2) — and
noted that **no strategy has ever been evaluated per position**. Every captaincy comparison to date is
a pooled average, which can mask offsetting per-position effects.

## Pre-registration (stated before running)

**Hypothesis:** `ceiling_phaul` beats `base_season` on **FWD** specifically — where hauls are the whole
decision — while losing on **DEF**, with the pooled average masking both.

**What counts as support:** a paired delta CI excluding zero on FWD in **at least two of the three
pools** (top-10, top-20, top-50).

**Null handling:** if no cell shows a delta CI excluding zero, captaincy is closed and no further
captaincy tests are proposed.

**Design choices fixed before seeing results:** each cell is the sub-decision *"best captain at
position Q, shopping in the top-N most-owned"* — candidates are the pool members at that position, the
oracle is the best of them. A gameweek counts toward a cell only if it offers **≥2 candidates** (a
one-candidate GW forces every strategy onto the same player and would inject structural zeros into the
paired deltas); the pooled convention of ≥3 is relaxed because a choice between two is a real decision.
GK is excluded. Benchmark is `base_season`, never `template` — template ranks by ownership, the variable
defining the pool, so its difficulty is confounded with pool size.

## Cell sizes — read these first

| pool | position | n_gw | median candidates/GW | chance hit@1 | cell oracle pts/GW |
|---|---|---|---|---|---|
| top-10 | FWD | 33 | 3 | 0.371 | 8.24 |
| top-10 | MID | 35 | 3 | 0.357 | 7.43 |
| top-10 | DEF | 34 | 3 | 0.402 | 7.06 |
| top-20 | FWD | 35 | 4 | 0.252 | 9.20 |
| top-20 | MID | 35 | 7 | 0.148 | 9.66 |
| top-20 | DEF | 35 | 7 | 0.151 | 10.00 |
| top-50 | FWD | 35 | 9 | 0.123 | 11.97 |
| top-50 | MID | 35 | 16 | 0.063 | 13.17 |
| top-50 | DEF | 35 | 17 | 0.060 | 11.43 |

Gameweek coverage is near-complete everywhere (33–35 of 35), so the CIs rest on a full season in every
cell. The thinness is in **candidates**, not gameweeks: a top-10 pool splits into ~3 per position, where
chance hit@1 is already ~0.37 and there is barely a decision to make. Forwards are the scarcest cut at
top-50 (9/GW vs 16–17 for MID/DEF), which is the ownership skew the prior study documented.

## Result — 0 of 36 comparisons reach significance

| position | pool | strategy | mean pts/GW | Δ vs base_season | 95% CI | boot p |
|---|---|---|---|---|---|---|
| **FWD** | top-10 | ceiling_phaul | 6.09 | **+0.36** | [−0.91, +1.91] | 0.807 |
| | top-10 | model_mean | 6.09 | +0.36 | [−0.91, +1.91] | 0.807 |
| | top-10 | ceiling_p90 | 5.58 | −0.15 | [−0.97, +0.33] | 0.361 |
| | top-20 | ceiling_phaul | 5.20 | **−0.29** | [−1.26, +0.51] | 0.450 |
| | top-20 | ceiling_p90 | 4.89 | −0.60 | [−1.51, +0.06] | **0.072** |
| | top-20 | model_mean | 4.83 | −0.66 | [−2.17, +0.46] | 0.239 |
| | top-50 | ceiling_phaul | 5.43 | **−0.06** | [−1.17, +0.92] | 0.846 |
| | top-50 | model_mean | 5.63 | +0.14 | [−1.51, +1.34] | 0.980 |
| | top-50 | ceiling_p90 | 5.29 | −0.20 | [−1.37, +0.63] | 0.514 |
| **MID** | top-10 | ceiling_phaul | 4.37 | −0.97 | [−2.69, +0.57] | 0.295 |
| | top-20 | ceiling_p90 | 4.46 | −0.89 | [−2.40, +0.26] | 0.161 |
| | top-50 | ceiling_phaul | 6.09 | +0.74 | [−1.11, +2.46] | 0.418 |
| | top-50 | model_mean | 6.06 | +0.71 | [−1.11, +2.43] | 0.433 |
| **DEF** | top-10 | ceiling_p90 | 5.00 | +0.71 | [−0.77, +1.88] | 0.515 |
| | top-20 | ceiling_phaul | 4.46 | −0.26 | [−1.69, +1.09] | 0.629 |
| | top-50 | ceiling_phaul | 5.51 | **+1.14** | [−0.26, +2.57] | 0.121 |
| | top-50 | ceiling_p90 | 5.17 | +0.80 | [−0.40, +1.89] | 0.212 |

*(Abridged to the strategies bearing on the hypothesis plus every cell with |Δ| > 0.7; the full 45-row
grid — 5 non-benchmark strategies × 9 cells — shows the same picture. `model_mean_x_pplay` is omitted
above as a near-duplicate of `model_mean`, giving the pre-registered 36-comparison frame.)*

**Not one cell has a delta CI excluding zero.** The smallest bootstrap p-value across all 36
comparisons is **0.072** (FWD top-20, `ceiling_p90`) — nothing is significant even *before* any
multiplicity correction. The multiplicity caution turns out to be moot: with zero nominally significant
cells there is nothing to correct. For the record, Bonferroni at 36 comparisons is 0.00139 and the
observed minimum is 52× that.

### The hypothesis is refuted, including its direction

`ceiling_phaul` vs `base_season` on **FWD**: **+0.36** (top-10, p=0.81), **−0.29** (top-20, p=0.45),
**−0.06** (top-50, p=0.85). **Zero of three pools**, against a required two — and the point estimate is
not even consistently positive.

The secondary directional claim fares worse. `ceiling_phaul` was predicted to *lose* on DEF; it is
**positive in the largest DEF cell** (+1.14 at top-50, the biggest single delta anywhere in the grid,
p=0.12) and the whole-grid maximum sits at exactly the position the hypothesis said it would fail.
Nothing significant either way — but the sign is wrong, so this is not a near-miss that a longer sample
would confirm.

### hit@1 — identification is real, and not the constraint

Nine cells × 6 strategies = 54 binomial tests against each cell's own `mean(1/n)` baseline. Minimum
p = **0.0011** (DEF top-10, `ceiling_p90`, 23/34 vs 0.402 chance). **Nothing survives Bonferroni**
(threshold 0.000926 — the minimum misses by a hair). **12 tests survive BH-FDR at q=0.05**, headed by
MID top-50 (`ceiling_phaul`/`model_mean` 8/35 vs 0.063 chance, p=0.0013) and FWD top-20
(`base_season` 17/35 vs 0.252, p=0.0024).

So strategies do identify the within-position oracle above chance — consistent with the restricted-pool
finding. But `base_season` is among the survivors, and the delta grid shows that identification does
not convert into points against it anywhere. Identification was never the binding constraint.

## Verdict — captaincy is closed

Per the pre-registered null handling: **no cell shows a delta CI excluding zero, so captaincy is
closed.** Three independent lines of evidence now agree, each having attacked a different candidate
explanation for the earlier nulls:

1. **Full-pool divergence** ([rerun](predictive-phase5-captaincy-diagnostic-rerun.md)) — when any model
   strategy diverges from `base_season` or template, it does not win; every win-rate CI includes or
   sits below 0.5 and every mean-delta CI contains zero, for `e_points`, `p90` and `p_haul` alike.
2. **Walk-forward discrimination** (same doc) — the one signal that looked real (LOGO AUC 0.626 vs
   floor 0.577) does not survive chronological CV (0.561 vs floor 0.578), at near-identical power.
3. **Restricted pools, pooled then per position** ([realistic-pool](predictive-phase5-captaincy-realistic-pool.md)
   and this document) — the "wrong universe" objection was correct on its own terms (there *is* 5.6–6.8
   pts/GW of headroom in a realistic pool, and the oracle *is* findable there ~3× above chance), yet no
   strategy beats a season average pooled, and none beats it in any of the 9 position cells.

The remaining explanation the per-position cut was designed to test — *the pooled average is masking a
FWD win and a DEF loss* — is refuted with the wrong sign on both halves. There is no masked effect.

**`base_season` extracts essentially all of the available captaincy signal, and the model adds nothing
on top of it at any position, in any pool.** The residual headroom is haul-timing variance. Per the
pre-registered rule, **no further captaincy tests are proposed.**

For the shipped ranker (`serve/captain.py`, ranking by `p_haul`): `ceiling_phaul` remains never
significantly worse than `base_season` in any of the 9 cells, and it ties for the best hit@1 in several.
That is a defensible thing to ship. It is not evidence that it beats a season average, and this document
should not be cited as such.

## Failure points acknowledged

- **Top-10 cells are ~3 candidates wide.** Chance hit@1 there is ~0.37; a "decision" among three
  near-equivalent options is thin, and the deltas are correspondingly compressed toward zero. The
  top-50 cells (9–17 candidates) carry the real discriminating power, and they are equally null.
- **Zero significant cells is itself unusual** across 36 comparisons — under a pure null one would
  expect ~1.8 nominally significant at α=0.05. Seeing none suggests the paired deltas are not merely
  noisy but genuinely centred near zero, which strengthens the null reading rather than weakening it.
- **The ≥2-candidate rule was chosen before running** but is a judgment call; a ≥3 rule would drop most
  top-10 cells entirely rather than change any verdict.
- **hit@1 and the deltas answer different questions** and disagree in tone (identification is
  significant under FDR; points differences are not significant at all). The decision-relevant one is
  the delta — being right about *who* the oracle is does not pay unless it changes *which player you
  captain*, and against `base_season` it does not.
- **One season, 35 GWs**, as with all prior captaincy work. "Closed" means closed on this evidence, at
  this sample. It is not a proof of absence, and multi-season data would still be the only thing that
  could reopen it — which is precisely why no further single-season test is proposed.
