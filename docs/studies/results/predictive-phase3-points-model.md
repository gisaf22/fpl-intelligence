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

## Parts remaining (Track 3)
- **3.5** per-position goals/assists specs vs pooled+multiplier.
- Then compose all parts to E[points] via `domain.fpl_scoring` and gate the full points model per position.
