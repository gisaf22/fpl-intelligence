# Position specification — results (Phase 1: the first change that moves shipped numbers)

**Type:** results (frozen record) · **Plan:** [coverage-metric slice](model-redesign-coverage-metric-slice.md) §open items
**Run:** real mart, GW1–38, conditional population (`minutes>0`, DGW-excluded, GW>3), n = 10,110 scored
player-GWs. Compose-level bias measured on `compose_points` vs realized `total_points`.

## What changed

The Poisson count machinery (`goals`, `assists`) fit **one GLM across all four positions with `position`
absent from the design entirely**. Every other component in the repo already fits per position
(`_binary_component`: `p_cs`, DC, `p60`, `p_play`; `bonus`: per-position OLS; `saves`: GK-only), so this
was one file breaking a convention the other five already followed.

Three changes, all in the shared machinery:

1. **A per-position intercept** in the Poisson design (`_design(..., levels)`), reference level DEF. The
   slope stays **shared** — every position keeps borrowing strength for the signal itself. Evidence said
   the intercept is ~99% of the fix; full slope separation bought nothing (max points bias 0.026 vs
   0.027) and cost 2× the DEF ranking.
2. **`fit_positions`** — positions whose target is structurally degenerate are not estimated. GK is
   excluded from `goals` (realized mean **exactly 0.0000** across 668 keeper-GWs) and receives the
   structural value `0.0` on the same slices the walk-forward scores.
3. **The `_GOAL_POS` scoring gate is retired.** `compose`/`simulate` no longer patch the model's output;
   the model emits the honest value at source, and a regression is now caught by the term's own level
   gate rather than silently masked.

## Result — level bias (the headline)

Compose `e_points` − realized, points per gameweek:

| position | before | after |
|---|---|---|
| GK | +0.599 | **+0.420** |
| DEF | +0.351 | **+0.064** |
| MID | −0.041 | +0.098 |
| FWD | −0.413 | **+0.038** |

**The DEF↔FWD relative distortion — the one that lands on every defender-vs-forward decision — goes from
0.764 points to 0.026. A 97% reduction.** In the underlying count, goals: DEF +105% → −1.6%, FWD −47% →
−3.6%, GK exactly 0.0000. Both terms now pass the level gate at every position.

**GK's residual +0.420 is NOT this defect.** It decomposes to the `saves` scoring-rule gap (+0.28:
compose scores `E[S]/3` where FPL pays `floor(S/3)`, a Jensen gap worth 0.331) plus clean-sheet (+0.09,
still undiagnosed). Different bug classes, separate slices — the assists half of GK's error *did* resolve
here (0.179 → 0.024 points).

## Ranking — no verdict changed

Fork D asked whether the level fix costs ranking. It does not: the per-position ranking verdicts are
**identical before and after** (`goals` = {DEF: fail, MID: pass, FWD: fail}). Deltas moved; no position
flipped. GK now reports no ranking verdict for `goals` at all, which is correct — a constant structural
prediction makes a rank correlation undefined, so the position is absent from the ranking table rather
than recorded as a failure. It stays in the **level** table, which is exactly where an over-reaching
structural assumption gets caught (see below).

## The gate caught an over-reach — worth recording

`assists` was initially given the same `fit_positions = (DEF, MID, FWD)` as `goals`. The level gate
**failed it in the opposite direction**: predicted 0.0000 vs realized 0.0060 assists/GW. Keepers do
occasionally assist — rare, but **not structurally zero**, unlike GK goals. Corrected to fit all four
positions, so a keeper gets an *estimated* intercept rather than an assumed zero. The pooled model's
failure was inflating that rate ~9×, not the rate existing.

This is the difference between building right and fitting an assumption, and it was caught by a gate
written one commit earlier rather than by review.

## Distribution calibration — improved, not resolved

| position | coverage (gate) before | after | CRPS before | after |
|---|---|---|---|---|
| GK | 0.802 ✅ | 0.807 ✅ | 1.374 | **1.368** |
| DEF | 0.801 ✅ | 0.784 ✅ | 1.543 | **1.531** |
| MID | 0.713 ❌ | 0.727 ❌ | 1.280 | 1.279 |
| FWD | 0.654 ❌ | 0.673 ❌ | 1.377 | **1.364** |

CRPS improves at every position (FWD most, now clearly beating climatology 1.429). MID/FWD coverage
improves but **still fails** — so the bias was a *contributing* cause of the interval failure, not the
whole of it. The parameter-uncertainty hypothesis stands as the next lever.

Raw haul ECE 0.0199 → **0.0204**, marginally over the pre-registered 0.02 raw tolerance; the gate allows
one walk-forward recalibration pass, after which it is **0.0006** (Platt) / 0.0029 (isotonic). Passes as
specified, but the raw number is worth watching. PIT mean 0.463 (unchanged).

## Re-frozen (the approved consequence)

First slice in this project to move shipped predictions. Re-frozen: `goals` minimal + selected,
`assists` minimal + selected, the `simulate` seed-pinned vector, the calibration synthetic vector.
The goals spot indices were **repointed onto DEF/MID/FWD rows** — the old indices landed on GK, whose
predictions are now a constant 0.0, and an all-zero spot vector cannot detect drift.

## Collection gap found and fixed

`testpaths = ["tests"]` meant CI (`pytest -m unit`) collected **none** of the co-located term tests —
87 tests including every model golden, the strangler-invariant vectors, `compose` and `simulate`. They
had to be run by hand to be seen. `testpaths` now includes `model`; the suite goes 1327 → 1414.

## Follow-on: the `saves` scoring-rule gap (fixed)

FPL pays `floor(S/3)`, a concave step function, but `compose` scored `E[S]/3` — the payout of the
expectation, not the expectation of the payout. A Jensen gap of ~0.33 pt at a typical keeper rate, and
the reason `compose` and the simulator **disagreed** on GK saves (the simulator draws `Poisson(e_saves)`
then floors, so it was always right; only the point estimate was wrong, and `simulator_consistency`
excludes GK so nobody caught it).

Fix: `saves_points_expectation(e_saves) = E[floor(S/3)]` summed over the Poisson count support — the same
construction as `conceded_penalty_expectation` (`E[-floor(GA/2)]`), verified against a draw-then-floor
Monte-Carlo to 3 dp. Applied at the one buggy line in `compose`; the simulator was already correct, so
**no draw, no simulate golden, and no calibration vector moved** — the point estimate simply stopped
diverging from the distribution.

Result (real mart) — every position is now within ±0.10 pt/GW:

| position | after position fix | **after saves fix** |
|---|---|---|
| GK | +0.420 | **+0.025** |
| DEF | +0.064 | +0.064 |
| MID | +0.098 | +0.098 |
| FWD | +0.038 | +0.038 |

The GK drop (0.395) is the saves Jensen gap plus its small bonus knock-on (lower saves points → lower
expected returns → lower `e_bonus`). This also **absorbed the clean-sheet +0.09** I had flagged as a
separate residual — GK is now essentially unbiased, so that residual was inside the saves error, not
independent of it.

## Open, in order

1. **Parameter-uncertainty propagation** — the remaining MID/FWD interval failure (coverage 0.727 /
   0.673, still under band). The simulator conditions on point-estimate parameters; the leading
   hypothesis for the residual narrowness.
2. **DC unverifiable** — 0.417 pts/GW at DEF with no realized column on the mart.
3. **Level gate not wired** into the three custom-`validate` terms (`bonus`, `clean_sheet`, `conceded`).
4. **Scoring-rule conformance check** — the saves gap was a *class* of bug (linear expectation of a
   nonlinear rule) that no gate could see; a general `E[rule]` vs `rule(E)` check would catch the next one.
