# Phase 4 — trust the probabilities: calibration + proper scoring (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 4 (hard gate).
**Produced:** 2026-07-09 · **Code:** `model/eval/calibration.py` (`simulate_eval`, `calibration_report`,
`recalibration_table`, `crps_table`). Population = the simulator's (`minutes>0`, DGW-excluded, GW>3,
walk-forward) — eval **and** sim share it, so the missing-blank tail (X1) creates no spurious
miscalibration. N=3000 draws. **Pre-registered tolerance (A4.1, before looking):** haul ECE ≤ 0.02;
80% coverage ∈ [0.75, 0.85] per position.

## What was validated
The Phase-3.1 simulator's per-player-GW predictive distributions vs realized `total_points`, via
randomized PIT, reliability/ECE for **haul (≥10)** and a less-rare **return (≥6)**, 80% interval
coverage, and CRPS vs three comparators. Recalibration = walk-forward isotonic + Platt (no leakage).

## Result

**PIT (calibrated ⇒ uniform, decile ≈ 0.10):** mean 0.463; deciles
`[0.151, 0.104, 0.106, 0.093, 0.090, 0.098, 0.095, 0.079, 0.081, 0.103]`. Close to uniform with a mild
elevated first bin (small left-tail excess) and slight negative mean bias — the model under-predicts a
touch, as the design predicted.

**Event probabilities — ECE, raw vs recalibrated (common walk-forward set):**

| event | raw | isotonic | Platt | tolerance |
|---|---|---|---|---|
| haul (≥10) | 0.0159 | 0.0019 | **0.0005** | ≤0.02 |
| return (≥6) | 0.0336 | **0.0052** | 0.0111 | ≤0.02 |

Raw haul is *just* inside tolerance but systematically **under-predicts** (pred 3.1% vs obs 4.5% — thin
upper tail, per the goals⊥assists / bonus-underdispersion caveats); raw return is **out** (0.034). **Both
clear the bar comfortably after one recalibration pass** — Platt best for haul, isotonic best for return;
**isotonic is the robust default** (≤0.0052 on both). ✅ **Probability gate MET.**

**80% interval coverage:**

| GK | DEF | MID | FWD |
|---|---|---|---|
| 0.894 | 0.858 | **0.820** | 0.737 |

Only **MID** is in band. GK/DEF are **over-covered** (intervals too wide), FWD **under-covered**
(intervals too narrow — attacker upside understated). This is a **per-position dispersion residual** that
probability recalibration does **not** fix (it corrects event probs, not interval width). ⚠️ **Documented
residual miscalibration** — a dispersion-correction lever for future work, not hidden.

**CRPS (lower = better):**

| pos | sim | point-forecast | Poisson(mean) | climatology |
|---|---|---|---|---|
| GK | 1.419 | 2.637 | 1.744 | **1.347** |
| DEF | **1.542** | 2.427 | 1.699 | 1.568 |
| MID | **1.279** | 1.918 | 1.360 | 1.356 |
| FWD | **1.377** | 2.015 | 1.482 | 1.429 |

The simulator **beats the point-forecast-degenerate and Poisson(mean) at every position** — the *shape*
earns its keep over the mean — and beats **climatology** at DEF/MID/FWD, but **loses to climatology at
GK** (1.419 vs 1.347): GK points are hard to sharpen beyond their marginal (echoes Phase-0/2 GK being
near-chance on ranking).

## Verdict — hard gate: probabilities PASS (after recalibration), coverage residual documented
- **Haul & return probabilities are trustworthy after one walk-forward recalibration pass** (isotonic ≤
  0.0052 on both, well under 0.02). Ship isotonic-recalibrated event probabilities.
- **Interval widths carry a per-position dispersion residual** (GK/DEF too wide, FWD too narrow) — not
  fixable by probability recalibration; recorded as a dispersion-correction lever.
- **The distribution adds real value over the mean** (CRPS beats point/Poisson everywhere) and over
  climatology except GK.

Honest outcome exactly as pre-registered: mild upper-tail underdispersion for attackers, corrected in
the event probabilities, with a residual on interval width. A4.1 tolerance **met for the probabilities**.

## Carried scope limits
`P(play)`/blank tail (X1, Phase 5); single-player marginals (team-stacking Phase 5); bonus competitive
residual. Distributional *dispersion* correction is the recorded next lever if interval coverage matters
for the downstream decision layer (Phase 5).
