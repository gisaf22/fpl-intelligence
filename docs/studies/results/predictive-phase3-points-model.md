# Phase 3.0 Track 3 — per-position points model (frozen, in progress)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) §3 Phase 3.0 Track 3.
**Code:** `model/forecast/points_model.py`. **Population:** `minutes > 0`, DGW-excluded, expanding
walk-forward (fit on `gw < t`), within position. Builds on the Track-2 diagnostics
([scoring diagnostics](predictive-phase3-scoring-diagnostics.md)) and the Track-1 per-position spec.

Track 3 re-casts Phase 2 into a *points* model, one sub-part per commit. This doc grows as parts land.

## Part 3.1 — team goals-against layer ✅ (2026-07-08)
**Motivation (D-D).** `clean_sheet = 1{GA=0}` and the conceded penalty `-floor(GA/2)` are the same
random variable (team goals-against); independent CS + conceded models permit the impossible
`CS=1 & GA>0` state (observed 0% of the time). So model team goals-against **once** and derive both.

**Model.** Per team-fixture (team GA = max `goals_conceded` among the team's appearances; a full-match
player saw every goal), Poisson GLM of team GA on **leakage-safe lagged team defensive form**
(`ga_roll3/5`, `xgc_roll3/5`) + venue (`was_home`) + fixture difficulty (`fdr_avg`). From the fitted
mean `lambda_ga`:
- `p_cs = P(GA = 0) = exp(-lambda_ga)`,
- `e_conceded_pts = E[-floor(GA/2)]` over `GA ~ Poisson(lambda_ga)`.

Both quantities come from the one `lambda_ga` → **internally consistent by construction** (no impossible
states; `p_cs ∈ (0,1)`; `e_conceded_pts ≤ 0`).

**Validation — does the derived P(CS) rank clean sheets?** Within-position Spearman of `p_cs` vs
realized `clean_sheets`, vs the lagged `clean_sheets_roll3` incumbent (35 eval GWs):

| pos | team-GA P(CS) | clean_sheets_roll3 (incumbent) | Δ |
|---|---|---|---|
| GK | **0.159** | 0.037 | **+0.122** |
| DEF | **0.140** | 0.072 | **+0.068** |
| MID | **0.116** | 0.109 | +0.007 |

`lambda_ga ∈ [0.31, 3.73]`, `p_cs ∈ [0.024, 0.734]`, 680 team-fixtures modelled.

**Verdict:** the single team-GA model beats the naive lagged-CS ranker at every clean-sheet position
(materially at GK/DEF, parity+ at MID), and delivers CS **and** the conceded penalty jointly and
consistently. Gate met. 4 hermetic tests.

## Part 3.2 — defensive-contribution (DC) component ✅ (2026-07-08)
**Motivation (D-A).** DC (+2 once a player hits their action threshold: DEF ≥10 CBIT, MID/FWD ≥12
CBIRT; GK exempt) is conditionally independent of conceding/CS given minutes, so it is a **standalone**
component — no coupling to the team-GA layer. Model `P(hit)` with a per-position logistic GLM on
leakage-safe lagged DC-action form (`dc_roll3/5`) + `minutes_roll3` + `fdr_avg` + `was_home`, then
`E[DC pts] = 2 × P(hit)`.

**Validation — P(hit) vs realized `dc_hit`, vs the lagged-count baseline (`dc_roll3`):**

| pos | DC logistic P(hit) | dc_roll3 (baseline) | Δ | hit-rate | verdict |
|---|---|---|---|---|---|
| DEF | **0.312** | 0.298 | +0.015 | 0.214 | ✅ beats baseline; DC ~10% of DEF pts (material) |
| MID | 0.311 | 0.309 | +0.001 | 0.116 | ≈ parity; DC ~7% of MID pts (keep) |
| FWD | 0.189 | 0.228 | −0.039 | **0.008** | ✗ loses; DC ~0.4% of FWD pts → **immaterial, exclude-and-flag** |

**Verdict:** the logistic DC component earns its place at **DEF** (beats baseline) and is parity at
**MID** — both positions where DC is a material share of points. For **FWD** the threshold is hit ~1%
of the time and the model can't rank a near-never event, so DC is immaterial and flagged (the composed
`e_dc_pts` there is a tiny near-constant, harmless). GK carry no DC term. 6 hermetic tests.

## Part 3.3 — bonus proxy ✅ (2026-07-08)
**Motivation (D-B/D-C).** Bonus (top-3 BPS in the match → 3/2/1) is caused by the *same-match*
performance, so the proxy is a **contemporaneous scoring-map** (returns → bonus), applied at
composition/simulation time when returns are expected/sampled — not a lagged forecast. Coefficients
are still fit walk-forward for honest validation.

**What was tried, and the honest outcome.**
- A per-component Poisson GLM (`goals, assists, CS, saves, DC, minutes`) **lost** to the plain
  `returns_pts` composite at every position (e.g. FWD 0.578 vs 0.767) — the composite already encodes
  BPS's position weights, and the mostly-zero target fits poorly under a log link.
- **Adding DC to a `returns_pts` calibration *hurt* the ranking** (DEF 0.530→0.436, FWD 0.767→0.584):
  D-C's small positive *partial correlation* (+0.15 DEF) does **not** survive as a linear model term
  (DC's scale/variance injects noise). A measured diagnostic that did not translate to a modelling gain.
- **Chosen proxy:** a per-position OLS calibration on `returns_pts` alone — it *preserves* that ranking
  (a monotone map) and yields a bounded `E[bonus] ∈ [0,3]` magnitude for composition.

**Validation — `e_bonus` vs realized `bonus` (35 GWs):** equals the `returns_pts` signal by
construction (D-B levels): **GK 0.503 · DEF 0.530 · MID 0.554 · FWD 0.767**. The calibration only sets
the magnitude; ranking is the strong returns signal. 7 hermetic tests.

## Part 3.4 — minutes hurdle + appearance ✅ (2026-07-08)
**Motivation.** Minutes is a **gate**, not a smooth covariate: appearance is 1 (1–59') / 2 (≥60'), and
the clean-sheet term is only awarded at ≥60'. Within the conditional-on-appearance population
(`minutes > 0`), model `P(≥60' | played)`; this sets `E[appearance | played] = 1 + P(≥60')` and gates
the CS term per player (a sub before 60' can't earn the team's clean sheet).

**Model.** Outfield: per-position logistic on lagged minutes form (`minutes_roll3/5/8`, `starts_roll3`).
GK: a robust lagged expanding `play60` rate — GK play ≥60' ~99% of the time, so the target is
near-constant and a logistic is degenerate (a raw fit gave a spurious −0.28).

**Validation — `p60` vs realized ≥60', vs the `minutes_roll3` baseline (35 GWs):**

| pos | P(≥60') hurdle | minutes_roll3 (baseline) | play60-rate | note |
|---|---|---|---|---|
| GK | 0.173 | 0.379 | 0.985 | near-constant → ranking meaningless; use ~0.99 probability |
| DEF | 0.418 | 0.426 | 0.774 | ≈ parity |
| MID | 0.511 | 0.507 | 0.619 | ≈ parity |
| FWD | 0.548 | 0.548 | 0.541 | ≈ parity |

**Verdict:** the hurdle is at **ranking parity** with lagged minutes for outfield — it does *not* beat
the baseline. It earns its place by producing a **calibrated probability** (a raw minutes level is not
one), which the appearance tier and the CS gate require; GK is ~constant. 9 hermetic tests.

**Scope gap (X1, deferred to Phase 5):** `P(play)` — the blank / 0-minute tail — is **not** modelled
here (the population is conditional on appearance). It is the biggest missing tail for a full points
distribution; flagged, not hidden.

## Part 3.5 — per-position vs pooled goals/assists (A-P2) ✅ (2026-07-08)
**Question.** Phase 2 fit goals/assists **pooled** across positions + a position multiplier. The
multiplier is a within-position constant (irrelevant to within-position ranking), so this asks whether
the rate *process* differs by position enough that a per-position fit ranks better.

**Result — within-position Spearman, pooled vs per-position (35 GWs):**

| component | pos | pooled | per-position | Δ |
|---|---|---|---|---|
| goals | DEF | 0.041 | 0.018 | −0.023 |
| goals | MID | 0.163 | 0.155 | −0.008 |
| goals | FWD | 0.158 | 0.164 | +0.006 |
| assists | GK | 0.060 | −0.053 | −0.112 |
| assists | DEF | 0.068 | 0.056 | −0.012 |
| assists | MID | 0.104 | 0.100 | −0.004 |
| assists | FWD | 0.103 | 0.066 | −0.037 |

**Verdict:** per-position **loses or ties at every cell** except a negligible +0.006 (FWD goals).
Pooling gives more data per fit and the process is common up to scale (the multiplier handles scale);
splitting just adds noise, worst at thin positions (GK assists −0.112). **A-P2 resolves: keep the
pooled model + multiplier (Phase 2's approach).** 10 hermetic tests.

*This is the third Track-3 refinement (after the bonus per-component GLM and DC-augmentation) that
loses to the simpler baseline — the test-before-committing discipline consistently favouring parsimony.*

## Composition — full points model ✅ (2026-07-08) — Track 3 complete
Compose the shipped parts to `E[points]` per player-GW via the position scoring structure: pooled
goals/assists (×mult), team-GA `p_cs·P(≥60')·cs_mult` + `e_conceded_pts`, DC `2·P(hit)`, bonus
(calibrated on **expected** returns — the chain is linear so the plug-in is exact for the mean),
appearance `1+P(≥60')`, and GK saves (ported from Phase 2.1). Gated per position against **two** bars
on identical rows: `base_season` and the **Phase-2.1 four-component model** (honest-null vs Phase-2.1
was pre-registered as acceptable).

**Result — within-position Spearman (35 GWs):**

| pos | full points model | Phase-2.1 component | base_season | Δ vs Phase-2.1 |
|---|---|---|---|---|
| GK | **0.154** | 0.036 | 0.041 | **+0.118** |
| DEF | **0.263** | 0.214 | 0.185 | **+0.048** |
| MID | **0.391** | 0.347 | 0.336 | **+0.044** |
| FWD | **0.398** | 0.354 | 0.349 | **+0.044** |

**CI addendum (2026-07-12, eval-layer hardening).** `points_model_gate` now routes through the reusable
`model.eval.scorer.score_gate`, which attaches a **block-bootstrap CI** to every cell (point estimates
unchanged). The CIs sharpen the verdict honestly: **DEF** (full [0.235,0.301] vs base [0.151,0.221]) and
**MID** ([0.370,0.422] vs [0.315,0.363]) are **separable** (CIs don't overlap) — real wins; but **GK**
([0.074,0.247] vs [-0.047,0.120]) and **FWD** ([0.355,0.427] vs [0.292,0.389]) **overlap** → those gains
are **not statistically separable on one season**. So "beats both bars at every position" holds on point
estimates but only **DEF/MID are demonstrable**; GK/FWD are directional-only (A5.1 again). *This is exactly
the error-bar gap the Phase-0 stress-test flagged — now closed for this gate.*

**Verdict — exceeds expectation.** The full points model beats **both** bars at **every** position (point estimate).
The design review predicted parity-vs-Phase-2.1 at goal-dominated MID/FWD; instead, closing the
equation improves ranking **everywhere** — hugely at GK (+0.118, the team-GA clean-sheet layer turning
a near-chance position into a real signal) and materially at DEF (+0.048). Leakage-safe (all inputs
lagged; `base_season` strictly prior). 12 hermetic tests.

**Why it beat the goal-dominated positions too:** the added appearance/minutes signal (`1+P(≥60')`) and
the bonus term (which amplifies the returns ranking) carry independent lift at MID/FWD beyond the raw
goal/assist forecast; the team-GA CS layer + conceded + DC carry DEF/GK.

## Status — Track 3 complete; Phase 3.0 (points-equation closure) complete
Every part shipped and gated: 3.1 team-GA (CS+conceded joint), 3.2 DC, 3.3 bonus, 3.4 minutes hurdle,
3.5 pooled>per-position, + composition. The full points model beats the Phase-2.1 ranking model and
the incumbent at all four positions. **Next: Phase 3.1 Monte-Carlo simulator** — the equation is now
complete and consistent, so the simulator can sample the components through the real scoring rules for
a full points *distribution* (haul probability, captaincy ceiling). Distributional validation is Phase 4.

**Carried scope limits:** `P(play)` / blank tail (X1, Phase 5); bonus competitive residual (irreducible
without a full-match sim); rare events (cards/OG/pen) excluded-and-flagged.
