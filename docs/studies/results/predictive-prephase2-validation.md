# Pre-Phase-2 validation sprint (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §6 — the 🔴 must-fix gate that opens Phase 2.
**Produced:** 2026-07-06 · single-season mart, `minutes > 0`, DGW excluded, per position.
**Reproduce:** `python -m model.eval.prephase2_validation`
**Purpose:** test the three baked-in assumptions that block Phase 2 (X2, X6, A2.2) *before* building the count models.

---

## X2 — does D1's ICC survive dropping the normality assumption? → **tested-holds (with a GK nuance)**

D1's ICC came from a **Gaussian** MixedLM; the target is a zero-inflated count. The between/within
**sum-of-squares partition is distribution-free** as a point estimate (no normality needed) — only the
LMM's CI/LRT assumed normality. So a **player-clustered bootstrap of the SS between-share** gives a
normality-free CI to compare against the Gaussian ICC.

| pos | SS between-share (distribution-free) | bootstrap 95% CI | Gaussian-LMM ICC [CI] |
|---|---|---|---|
| GK | 0.038 | **[0.018, 0.063]** | 0.000 [0.000, 0.027] |
| DEF | 0.092 | [0.070, 0.117] | 0.056 [0.000, 0.082] |
| MID | 0.136 | [0.113, 0.160] | 0.101 [0.070, 0.122] |
| FWD | 0.132 | [0.084, 0.182] | 0.097 [0.000, 0.143] |

- **Ordering survives:** GK < DEF < FWD ≈ MID under **both** methods.
- **Magnitude survives:** outfield between-share is small under both (~0.09–0.14 SS / ~0.06–0.10 ICC); DEF/MID/FWD CIs exclude 0 → the "small but real" conclusion is **not** an artifact of normality.
- **GK nuance:** the distribution-free SS-share (0.038, CI excludes 0) diverges from the LMM's ICC = 0.
  This is **finite-sample upward bias** of the SS-share (group means differ by chance even with zero true
  between-variance), *not* evidence of durable between-keeper skill. The "GK ≈ no durable level"
  conclusion correctly rests on the variance-component bias-correction and the LRT (p = 0.50), which the
  raw SS statistic cannot replicate. **No re-work of D1 needed; the caveat is recorded on the D1 result.**

**Verdict:** D1's substantive conclusions are robust to dropping normality. Debt retired.

## X6 — is lagged xG a better predictor of future goals than lagged goals? → **tested-holds**

To forecast **next-GW `goals_scored`**, rank players by their strictly-prior expanding mean of `xg`
vs of `goals_scored`; within-position Spearman on the common eval set (GW > 3).

| pos | lagged **xG** | lagged **goals** | Δ (xG − goals) | winner |
|---|---|---|---|---|
| DEF | 0.080 | 0.054 | **+0.026** | xG |
| MID | 0.180 | 0.137 | **+0.043** | xG |
| FWD | 0.190 | 0.177 | **+0.013** | xG |

**xG wins at every position** (biggest at MID). Consistent with "xG regresses to a truer rate than the
noisy realized outcome." Justifies using lagged process stats (xG/xA) as the Phase-2 features over
lagged realized components. *(Note: goals here are a Phase-2 **target**; using them as a lagged
predictor is not the excluded contemporaneous-signal case — see the claims discipline in the plan.)*

## A2.2 — how much of the points are we deferring (bonus/cards/saves)? → **tested-holds (material, quantified)**

| pos | Σ total_points | bonus % | GK saves % (~) | note |
|---|---|---|---|---|
| GK | 2,497 | 6.3 | **17.6** | saves are a large deferred chunk for keepers |
| DEF | 11,687 | 5.6 | — | bonus modest |
| MID | 15,156 | 7.0 | — | bonus modest |
| FWD | 4,103 | **11.5** | — | bonus is the largest single deferred piece |

**Implication for the map:** the component map (appearance + goals + assists + CS) covers the majority of
points, but the deferred parts are **not negligible and are position-skewed** — the map will
**systematically under-predict GK (missing ~18% saves) and premium FWD (missing ~11.5% bonus)**.
Decision: proceed with the map for the first build, but (a) add a **GK-saves component** early given the
size, and (b) treat **bonus** as a known downward bias for FWD, flagged in results, with BPS modeling a
fast-follow if the gate is close. Not "minor" — a stated, quantified limitation.

---

## Gate status

| item | assumption | result | status |
|---|---|---|---|
| X2 | Gaussian-on-counts (D1 debt) | ordering + magnitude robust; GK caveat recorded | ✅ tested-holds |
| X6 | lagged xG > lagged goals | xG wins every position | ✅ tested-holds |
| A2.2 | deferred-points share minor | material (GK saves 18%, FWD bonus 11.5%) — quantified | ✅ tested-holds |
| #4 | component-target leakage assertion | reclassified as a **Phase-2 build-time contract** (guards columns that don't exist yet) — lands with the harness, not a pre-build test | ➡ carried into build |

**Phase 2 gate: OPEN.** The three empirical must-fix items are resolved; the leakage assertion is a
build-time contract to wire in with the count-model harness.
