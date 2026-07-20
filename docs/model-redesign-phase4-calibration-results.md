# Phase-4 calibration — real-mart verdict (Track A: are the distributions trustworthy?)

**Type:** results (frozen record) · **Plan:** [model-redesign-phase4-calibration-slice.md](model-redesign-phase4-calibration-slice.md)
**Run:** `calibration_report(mart, n_sims=4000, seed=0)` on the full 2025-26 mart (GW1-38), conditional
population (`minutes>0`, DGW-excluded, GW>3), **n = 10,110** scored player-GWs. Render-not-decide: the
reproducible pin is on a synthetic panel (`tests/test_model_eval_calibration.py`); these real-mart numbers
are the *interpretation* and move as the mart is refreshed.

**Pre-registered tolerances (stated before looking):** haul (>=10) ECE ≤ 0.02; 80% interval coverage
∈ [0.75, 0.85] per position. Gate = within tolerance after ≤1 walk-forward recalibration pass, else
**documented residual miscalibration** (a fail is informative, not model surgery — that is a separate track).

## Power surface (interpret only where events are not a handful)

| position | n | haul (≥10) | return (≥6) |
|---|---|---|---|
| GK | 668 | 26 | 164 |
| DEF | 3,479 | 146 | 769 |
| MID | 4,699 | 227 | 655 |
| FWD | 1,264 | 58 | 218 |

Every position is **well-powered** for coverage and return ECE; haul ECE is adequately powered (GK/FWD
haul counts 26/58 are the thinnest, so read those with a little caution). No cell is "inconclusive."

## Verdict

**1. Haul calibration — PASS.** Raw haul ECE **0.0160 ≤ 0.02** (within the pre-registered tolerance *before*
any recalibration); one walk-forward isotonic/Platt pass tightens it to **0.0017 / 0.0005**. The
"probability of a haul" is trustworthy.

**2. The distribution is genuinely informative — PASS (CRPS).** `crps_sim` beats the degenerate point
forecast and Poisson(mean) at **every** position, and beats (in-sample-optimistic) climatology at **3 of 4**:

| position | sim | point | Poisson(mean) | climatology |
|---|---|---|---|---|
| GK | 1.423 | 2.640 | 1.754 | **1.347** |
| DEF | **1.543** | 2.427 | 1.700 | 1.568 |
| MID | **1.280** | 1.918 | 1.360 | 1.356 |
| FWD | **1.377** | 2.015 | 1.482 | 1.429 |

GK is the one position where in-sample climatology edges the simulator — consistent with (3) below.

**3. Interval coverage — RESIDUAL MISCALIBRATION (per-position spread).** Nominal 80%; in-band only for MID.
A per-position `sim_sd` vs realized-std check separates *genuine* mis-dispersion from a discrete-interval
metric artifact (`[p10,p90]` over-covers lumpy discrete distributions even when the width is right):

| position | coverage (initial) | `sim_sd`/realized | diagnosis |
|---|---|---|---|
| GK | 0.894 | **1.48** | genuine **over**-dispersion → **fixed** (see below) |
| DEF | 0.857 | 1.01 | width right → **discreteness artifact**, not a defect |
| MID | 0.818 | 0.80 | ✅ in band |
| FWD | 0.735 | 0.69 | genuine **under**-dispersion (thin haul tail) |

### GK over-dispersion — root cause + fix (done)

Decomposing the GK simulated variance by component, **goals dominated at 6.3** (vs clean-sheet 2.95). The
pooled goals model emits a spurious tiny `e_goals ≈ 0.063` for keepers (~2.4 goals/season — absurd), and a
GK goal is worth **10** points, so `Var(10·Poisson(0.063)) = 100 × 0.063 ≈ 6.3` — larger than the
clean-sheet term, and essentially the entire GK over-dispersion. **Fix:** a position-eligibility gate
(`_GOAL_POS = DEF/MID/FWD`) attributes goal points to outfield only — `E[GK goals] ≈ 0`, the honest value —
applied at the *scoring* layer in both `compose` and `simulate` so the simulator's rng stream (and its
seed-pinned golden) stay bit-identical. Outcome on the real mart:

| GK metric | before | after |
|---|---|---|
| `sim_sd` / realized | 1.48 (over-dispersed) | **0.97** (matches realized) |
| coverage | 0.894 | 0.882 |
| CRPS (sim) | 1.423 | **1.374** (gap to climatology 0.076 → 0.027) |
| raw haul ECE (all pos) | 0.0160 | 0.0199 (still ≤ 0.02; recal → 0.003) |

The GK **over-dispersion is resolved** (variance now matches realized; CRPS improved; the ×10 goal-variance
artifact gone) and the GK mean is more accurate (drops 0.63 spurious goal points). The residual GK coverage
0.882 is now the **same discreteness artifact as DEF** (width right, ratio ~1), not over-dispersion. The
one honest cost: removing the spurious GK goal pathway thinned GK haul prob, nudging raw haul ECE
0.0160 → 0.0199 (still within the pre-registered tolerance; recalibration drives it to 0.003).

**Remaining coverage residuals (not addressed here):** FWD **under**-dispersion (ratio 0.69) is a genuine
thin-tail defect from drawing components **independently** (goals ⊥ assists ⊥ team-CS), so the sim misses
the return co-movement that stacks a forward haul — a correlated-draw modelling change, its own later slice.
DEF/MID over-coverage is a discrete-interval **metric artifact**, not over-dispersion (would be addressed by
an interpolated-quantile coverage metric, not model surgery).

**4. PIT — mild left-skew.** Mean 0.463 (ideal 0.5); deciles roughly flat except an elevated first decile
(0.153 vs ~0.10): slightly more realized outcomes land in the lowest predicted quantile than the
distribution expects — a small downside the sim under-weights. Directionally consistent with (3).

## Bottom line + open items (out of this slice's scope)

**Trustworthy for its headline job:** the haul/return **probabilities** are calibrated (raw haul ECE within
tolerance; a single walk-forward recalibration pass makes haul/return ECE excellent — 0.002 / 0.003), and
the distribution adds real information over point/Poisson/climatology baselines. Captaincy ceiling reads
(`p90`, `p_haul`) can be relied on, especially after the light recalibration.

**Residual, after the GK fix:** the GK over-dispersion is **resolved** (§3). What remains is (a) FWD
**under**-dispersion — a genuine thin-tail defect needing correlated component draws (its own slice), and
(b) DEF/MID over-coverage — a discrete-interval **metric artifact**, not a model defect. Neither is
addressed by recalibrating event probabilities; both are recorded as the next-actionable levers, out of
this slice's scope.
