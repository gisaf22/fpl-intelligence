# MID/FWD interval under-dispersion — scoping (measure before building)

**Status:** scoping (hypothesis REFUTED; forks proposed) · **Type:** spec
**Question:** the MID/FWD 80% intervals still under-cover (`cover_pit` MID 0.727, FWD 0.673 vs band
[0.75, 0.85]). The standing hypothesis was **parameter-uncertainty propagation** — "the simulator treats
its fitted rates as exact." Is that the cause?

## Verdict: the hypothesis is refuted (do not build the parameter-uncertainty machine)

"Parameter uncertainty" could mean two things; both are measured negligible.

**1. Coefficient uncertainty** (we don't know the GLM's β precisely). Propagated `Cov(β̂)` to per-row
`Var(λ)` via the delta method, as a share of the count variance:

| | goals | assists |
|---|---|---|
| DEF | 0.04% | 0.05% |
| MID | 0.10% | 0.16% |
| FWD | **0.54%** | 0.19% |

Even at FWD it is half a percent of the Poisson variance. Propagating it would widen intervals by <0.3%.

**2. Count overdispersion given the model's λ** (the weekly rate varies beyond the smoothed forecast →
Negative-Binomial not Poisson). Pearson dispersion (=1 if Poisson):

| | goals | assists |
|---|---|---|
| DEF | 1.14 | 0.90 |
| MID | 0.97 | 1.04 |
| FWD | **1.16** | **1.23** |

Mild. Scaled into **points** by the multiplier² it is worth ~0.38 (FWD goals) + ~0.14 (FWD assists)
≈ **0.5 pt-variance** — real but small, and `check_assumptions` already judges Poisson adequate.

So the rate is **not** meaningfully uncertain. The narrowness is **omitted** variance, not **uncertain**
rates — a different problem needing a different fix.

## What the residual actually is (the honest decomposition)

First, scale: the dispersion ratio is now **much better than when this was first flagged**. Pre-fix FWD
was `sim_sd/realized ≈ 0.69`; after the position + saves fixes it is **0.85** (`sim_sd`/RMSE-about-mean
0.88). The gap to the band floor is now small (0.02–0.08 of coverage). Sources of the residual per-row
under-dispersion, measured:

1. **Mild attacking overdispersion** (above) — ~0.5 pt-var at FWD. Poisson slightly too thin in the goal
   tail (the hat-trick week).
2. **Excluded negative events** — the sim gives every appearance 0 for yellow/red cards, own goals,
   penalty misses. Real rates: **P(yellow) DEF 0.15, MID 0.13**; `Var(neg_pts)` DEF 0.22, MID 0.15. This
   is **downside** variance, and it matches the PIT's known left-skew (elevated first decile 0.153 — more
   realized outcomes land below the sim's floor than it expects). The sim literally claims a defender
   never gets carded.
3. **Bonus competitive residual** — bonus depends on *other* players' BPS in the match; the sim maps it
   deterministically from a player's own returns. Unexplained `Var(bonus | returns)` ≈ 0.20–0.23 per
   position (FWD 0.23), never sampled.
4. **Mean-model error** — the balance. `Var(y − sim_mean)` exceeds the sim's predictive variance partly
   because the model's *features* don't capture all systematic rate variation (same xG_roll3, very
   different fixtures). **This is not honestly closeable by widening intervals** — padding uncertainty to
   cover a wrong mean is dishonest calibration. It is closed by a **better mean model**, not by the
   simulator.

## The trap (why (2) is a real slice, not a free add)

Adding negative events is **not** a pure variance add: it also **lowers the mean** (DEF by ~0.18). Compose
is currently ~unbiased vs realized *including* cards, so injecting card draws would push DEF to ~−0.09
biased **low** — trading calibration for coverage. Any negative-events work must be mean-neutral (the
downside it adds must already be implicit in where the current mean sits), which makes it a modelling
slice with its own gate, not a one-liner.

## Forks (proposed)

- **A — accept the residual, redirect to the mean model (recommend).** The interval gap is now small and
  its largest component is mean-model error, which interval work cannot honestly fix. The high-value
  lever for MID/FWD is the **§3 forward-agenda features** (opponent-forward, team attacking context —
  already declared in the specs, not yet materialized): they improve **ranking** *and* tighten
  calibration by explaining rate variation, and they carry no dishonesty risk. Record parameter-uncertainty
  as refuted (like the correlated-draws dead end) and open a features slice.
- **B — add excluded negative events to the simulator.** Honest on its own merits (the sim shouldn't claim
  cards never happen) and fixes the PIT left-skew specifically. But mean-neutral handling is required
  (see trap), and sizing says it closes only ~10–15% of the coverage gap — a correctness fix, not a
  coverage fix. Could pair with A.
- **C — Negative-Binomial attacking counts per position.** Addresses (1). Mild effect (~0.5 pt-var),
  contradicts the current `check_assumptions` Poisson verdict, and adds a dispersion parameter per
  position to fit. Lowest value/effort of the three.
- **D — sample the bonus competitive residual.** Addresses (3). Moderate complexity (needs a residual
  model for bonus given returns); ~0.2 pt-var. Defer.

## Recommendation

**A, optionally + B.** The parameter-uncertainty slice is refuted and must not be built. The interval
residual is small and mean-model-dominated; chase it through **better mean features** (which also help
ranking), not through interval inflation. Add negative events (B) only as an independent correctness fix,
mean-neutral, with no promise that it reaches the band. Do **not** do C/D now — both are small and one
contradicts a standing verdict.

## What would change the recommendation
If a features slice (A) lands and MID/FWD coverage is *still* materially short with the mean now accurate,
that residual would be genuine irreducible dispersion — at which point C (NB counts) becomes the honest
next lever. Order matters: mean first, dispersion second.
