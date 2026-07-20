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

**3. Interval coverage — RESIDUAL MISCALIBRATION (per-position spread).** Nominal 80%; in-band only for MID:

| position | coverage | vs [0.75, 0.85] |
|---|---|---|
| GK | 0.894 | too **wide** (over-covers) |
| DEF | 0.857 | slightly too wide |
| MID | 0.818 | ✅ in band |
| FWD | 0.735 | too **narrow** (under-covers) |

The simulator's spread is too wide for GK/DEF (their outcomes are more concentrated than simulated — points
dominated by appearance + clean-sheet) and too narrow for FWD (forwards carry a fatter haul tail than the
draw captures). Well-powered, so this is a genuine structural finding, not noise.

**4. PIT — mild left-skew.** Mean 0.463 (ideal 0.5); deciles roughly flat except an elevated first decile
(0.153 vs ~0.10): slightly more realized outcomes land in the lowest predicted quantile than the
distribution expects — a small downside the sim under-weights. Directionally consistent with (3).

## Bottom line + open items (out of this slice's scope)

**Trustworthy for its headline job:** the haul/return **probabilities** are calibrated (raw haul ECE within
tolerance; a single walk-forward recalibration pass makes haul/return ECE excellent — 0.002 / 0.003), and
the distribution adds real information over point/Poisson/climatology baselines. Captaincy ceiling reads
(`p90`, `p_haul`) can be relied on, especially after the light recalibration.

**The residual is interval width, per position** — GK/DEF too wide, FWD too narrow — which recalibrating
*event probabilities* does not fix (it needs the simulator's per-position **variance** tuned: e.g. GK/DEF
draws are over-dispersed, FWD under-dispersed on the haul tail). That is **model work, deliberately out of
scope here** (the Phase-4 gate is the trust verdict + one recalibration pass, not distributional surgery).
Recorded as the next-actionable calibration lever.
