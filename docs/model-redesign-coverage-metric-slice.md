# Coverage metric — discreteness correction (Phase-4 follow-on)

**Status:** approved (forks A–D ruled) · **Type:** spec
**Parent:** [Phase-4 calibration slice](model-redesign-phase4-calibration-slice.md) ·
[Phase-4 results](model-redesign-phase4-calibration-results.md)
**Goal:** make the 80% **interval-coverage gate** discreteness-correct, so it distinguishes a real
dispersion defect from a metric artifact. The current `[p10,p90]` rule cannot, and is currently issuing
both a **false pass** (MID) and a **false fail** (DEF/GK/FWD).

## Why this is the blocking item (evidence, not assertion)

FPL points are **lumpy**: a player who plays and returns nothing scores exactly 1 or 2. The simulated
distribution therefore has huge atoms, and `np.percentile` lands *inside* one. Measured on the real mart
(`n_sims=3000, seed=0`), the simulator puts **47.5% of its FWD mass at or below its own `p10`** — so
`[p10, p90]` is not an 80% interval at all.

The bonus term makes it worse in a specific, diagnosable way: bonus adds a *continuous* sliver to a
*discrete* score, so `p10` lands at **1.02** rather than exactly `1.00`, and the **modal** FWD outcome
`y = 1` is scored as falling *below* the interval. **76 of the 154 FWD below-`p10` misses are exactly
this** — half the FWD "under-coverage", pure artifact.

Replacing the rule with **randomized-PIT coverage** (`0.10 ≤ u ≤ 0.90`, where `u` is the randomized PIT
the suite *already computes*) changes the verdict at every position:

| pos | `[p10,p90]` (current) | PIT-correct | what actually changed |
|---|---|---|---|
| GK | 0.876 | **0.792** ✅ | over-coverage was artifact — dissolves |
| DEF | 0.858 | **0.803** ✅ | over-coverage was artifact — dissolves |
| MID | 0.818 ✅ | **0.720** ❌ | **was passing only by artifact** (false pass) |
| FWD | 0.733 | **0.656** ❌ | genuinely worse than recorded |

So the Phase-4 results doc is wrong in three places, and the *next* modelling slice cannot be chosen
until the metric is trustworthy — it is currently pointing at the wrong positions.

### Corollary (recorded so nobody rebuilds it): correlated draws are a dead end

The Phase-4 doc names FWD under-dispersion as a "correlated component draws" slice. **Probed and
rejected.** A shared attacking latent `Z ~ Gamma(1/φ, φ)` (`E[Z]=1`, means preserved exactly) per
player-fixture *and* per team-fixture, with `goals|Z ~ Pois(λ_g·Z)`, `assists|Z ~ Pois(λ_a·Z)` — the
exact mechanism the doc calls for — moves nothing:

| FWD | φ=0 | φ=0.3 | φ=0.8 |
|---|---|---|---|
| `sim_sd`/realized | 0.707 | 0.730 | 0.765 |
| coverage | 0.733 | 0.734 | **0.731** |
| CRPS | 1.377 | 1.376 | 1.377 |

Added variance is `φ·(4λ_g + 3λ_a)²`; FWD λ's are small, so closing the ratio would need `φ ≈ 6`
(absurd). The narrowness is **mean-model error**, not component independence: RMSE about `sim_mean`
(3.04) far exceeds mean `sim_sd` (2.15), and the simulator propagates **zero** parameter uncertainty —
it draws as if `e_goals`/`e_assists`/`p60` were known exactly. That is a separate, better-motivated
slice (see open items).

## Forks (ruled)

- **A — replace or add?** **Report both, gate on PIT.** `p10`/`p90` are *shipped product outputs*
  (captaincy ceiling / downside reads), so the operational hit-rate of the interval a consumer actually
  sees stays reported as `coverage`. The **pre-registered tolerance band [0.75, 0.85] moves onto**
  `coverage_pit`. Showing both side by side is also the evidence for the artifact claim.
- **B — rng.** **None added.** PIT-coverage is a *deterministic function of the existing `pit` column*
  (already drawn from the `seed+1` scoring rng, Phase-4 Fork B). No new stream, no new seed, draw
  primitive untouched.
- **C — golden scope.** This is a **metric** change, not a model change: `simulate`'s seed-pinned golden
  is **bit-identical** (no draw touched) — that is the gate. Only the *calibration* frozen vector
  re-freezes, and only its coverage entries.
- **D — the wrong results doc.** The Phase-4 results doc is a **frozen record**, so it gets a dated
  **correction section** (superseding, not silently rewritten), carrying all three findings: the metric
  artifact, the corrected per-position verdict, and the correlated-draws negative result.

## Sequence (one reviewable commit each)

1. **Metric** — add `cover_pit` to `simulate_eval`, `coverage_pit` to `calibration_report`; move
   `coverage_in_band` onto it; update the module docstring's pre-registered tolerance wording.
   Re-freeze the calibration vector's coverage entries. **Gate: `simulate` golden bit-identical.**
2. **Verdict** — re-run `calibration_report` on the real mart; write the correction section into the
   Phase-4 results doc (both coverage columns, corrected pass/fail, correlated-draws negative result).

## Stress-test constraints

1. **Golden safety:** no draw is touched — `simulate`'s golden must reproduce to the bit, unchanged.
2. **No new randomness:** `cover_pit` is derived from `pit`; if it needs its own rng, the design is wrong.
3. **Don't move the goalposts:** the tolerance band stays **[0.75, 0.85]** — it was pre-registered. Only
   the *quantity it applies to* changes, and that change is justified above, not by the result it gives.
4. **Report the artifact, don't hide it:** both coverage numbers stay in the report; a reader must be able
   to see the gap that motivated this slice.
5. **Honesty about the flip:** MID goes from pass to **fail**. That is the point — record it plainly.

## Invariant
`simulate` golden bit-identical · import-linter 6/6 · ruff clean · full `pytest` green · tolerance band
unmoved · conditional population only.

## Open items (out of scope, newly surfaced)

- **Parameter-uncertainty propagation** — the simulator conditions on point-estimate parameters; the
  leading hypothesis for MID/FWD narrowness. Own slice.
- **Per-position mean bias** — DEF **+0.39**, FWD **−0.40** pts/GW (sim − realized) on the real mart.
  Not previously recorded; ~0.8 pts of *relative* cross-position distortion, which directly biases
  transfer/captaincy comparisons. Own slice, arguably the highest decision-impact one.
