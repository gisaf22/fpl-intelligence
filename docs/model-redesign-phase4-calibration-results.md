# Phase-4 calibration — real-mart verdict (Track A: are the distributions trustworthy?)

> **⚠️ SUPERSEDED IN PART (2026-07-20) — read the [correction](#correction-2026-07-20--the-coverage-metric-was-broken) at the bottom first.**
> §3's coverage table was measured with a rule that is **not valid on an atomic distribution**. The
> corrected numbers **flip MID from pass to fail**, **clear GK/DEF outright**, and **retire the proposed
> "correlated component draws" slice as a measured dead end**. §§1, 2, 4 (haul ECE, CRPS, PIT) stand
> unchanged. Plan: [coverage-metric slice](model-redesign-coverage-metric-slice.md).

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

---

## Correction (2026-07-20) — the coverage metric was broken

Everything above this line is the original frozen record. This section supersedes **§3 only**; §§1, 2, 4
stand. Run: `calibration_report(mart, n_sims=4000, seed=0)`, same mart, same population, n = 10,110.

### What was wrong

§3 measured coverage as `p10 <= y <= p90`. FPL points are **atomic** — a player who plays and returns
nothing scores exactly 1 or 2 — so `np.percentile` lands *inside* an atom and the interval is not an 80%
interval at all: the simulator puts **47.5% of its FWD mass at or below its own `p10`**. The bonus term
sharpens this into a specific bug: bonus adds a *continuous* sliver to a *discrete* score, so `p10` lands
at **1.02** instead of `1.00`, and the **modal** FWD outcome `y = 1` is scored as falling *below* the
interval. **76 of the 154 FWD below-`p10` misses are exactly that** — half the headline "FWD
under-coverage" was the metric, not the model.

The gate is now the **randomized-PIT** coverage (`0.10 <= u <= 0.90`), which is discreteness-correct by
construction and reuses the PIT the suite already computes (no added randomness). The pre-registered band
**[0.75, 0.85] is unmoved** — only the quantity it applies to changed.

### Corrected §3 verdict

| position | `[p10,p90]` (operational) | **`cover_pit` (gate)** | corrected verdict |
|---|---|---|---|
| GK | 0.882 | **0.802** | ✅ **in band** — the "over-coverage" was artifact |
| DEF | 0.857 | **0.801** | ✅ **in band** — the "over-coverage" was artifact |
| MID | 0.818 | **0.713** | ❌ **out of band** — *was a false pass* |
| FWD | 0.735 | **0.654** | ❌ out of band — worse than recorded |

Both columns stay in the report: `coverage` is what a consumer of the shipped `p10`/`p90` actually
experiences, `coverage_pit` is the calibration gate. **Net:** the DEF/GK "artifact" reading in §3 was
right and is now *dissolved* rather than asserted; MID was never actually passing; FWD is a real defect.

### The proposed "correlated component draws" slice is a measured dead end

§3 attributed FWD to independent component draws and named a correlated-draw slice. **Probed and
rejected.** A shared attacking latent `Z ~ Gamma(1/φ, φ)` (`E[Z]=1`, means preserved exactly) per
player-fixture *and* per team-fixture, with `goals|Z ~ Pois(λ_g·Z)` and `assists|Z ~ Pois(λ_a·Z)` — the
exact mechanism proposed — does essentially nothing:

| FWD | φ=0 (control) | φ=0.3 | φ=0.8 |
|---|---|---|---|
| `sim_sd`/realized | 0.707 | 0.730 | 0.765 |
| coverage | 0.733 | 0.734 | **0.731** |
| CRPS | 1.377 | 1.376 | 1.377 |

Coverage moves by −0.002 and CRPS by 0.000 even at an already-implausible φ=0.8. Added variance is
`φ·(4λ_g + 3λ_a)²`; FWD λ's are small, so closing the ratio this way would need `φ ≈ 6`. **Do not build
this slice.**

**Why it does nothing — the correlation isn't there to capture (measured directly, 2026-07-21).** The
above is the *simulated* refutation; the *direct* one agrees. On the same population (n=10,110), the
residual correlation `corr(g − e_goals, a − e_assists)` — the quantity the independence assumption is
actually about — is DEF **−0.008**, MID **+0.019**, FWD **+0.038**, and **every 95% CI contains 0**. The
marginal correlation (+0.038) is just good attackers having high rates for both, which the per-player
λ's already carry; it is not a violation. Cost of assuming independence, in variance of attacking points
(observed / independence-implied): GK 1.00, DEF 1.00, MID **1.03**, FWD **1.04** — ≤4% of variance, ~2%
of interval width. Mechanistically two effects cancel: shared team attacking form pulls positive, while a
goal has one scorer and at most one *different* assister, which pulls negative.

Note also that correlation is a **spread-only** question: `E[4G + 3A] = 4E[G] + 3E[A]` regardless of
dependence, so this assumption cannot move rankings, transfers, or captaincy at all. `goals ⊥ assists` is
now recorded as **MEASURED** in the `model/simulate.py` assumption block rather than inherited.

### What the FWD/MID narrowness actually is (next lever)

RMSE about `sim_mean` (FWD: 3.04) far exceeds mean `sim_sd` (2.15). That excess is **mean-model error**,
not component independence — the simulator draws as if `e_goals`/`e_assists`/`p60` were **known exactly**
and propagates **zero parameter uncertainty**. That is the leading hypothesis for MID/FWD, and its own
slice.

### Newly surfaced, not previously recorded: per-position mean bias

| position | bias (`sim_mean` − realized), pts/GW |
|---|---|
| GK | +0.25 |
| DEF | **+0.39** |
| MID | −0.01 |
| FWD | **−0.40** |

The model systematically **over-rates defenders and under-rates forwards by ~0.8 pts *relative***. It is
a small share of MSE (bias²/mse ≈ 0.017) but it is *systematic and cross-position*, so it lands directly
on transfer and captaincy comparisons — arguably the highest-decision-impact open item. Own slice.
