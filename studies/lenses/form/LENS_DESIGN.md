# LENS_DESIGN.md — LENS-FORM

**Status:** LOCKED — no changes permitted after this document is locked  
**Locked:** 2026-05-22  
**Supersedes:** No prior design (first LENS-FORM design under locked methodology)  
**Governed by:** `signals/evaluation/EVAL_DESIGN.md` v1.5  
**Registry:** `signals/registry/SIGNAL_REGISTRY.md` v1.1 (FORM-001 through FORM-006)  
**EDA basis:** `studies/eda/findings/EDA_FINDINGS.md` (gate IDs referenced throughout)

---

## 1. Study question

Does smoothing raw form proxy signals over rolling gameweek windows (3-GW, 5-GW) improve
predictive association with next-gameweek FPL returns, relative to lag-1 raw total_points
as the naive baseline?

This is a signal characterisation study, not a model comparison. The output is a per-signal
per-position lens classification in `SIGNAL_REGISTRY.md` — not a scorer weight or a
ranked player list.

---

## 2. Signal set

Six signals are registered for LENS-FORM in `SIGNAL_REGISTRY.md` v1.1:

| Signal ID | Signal | EDA basis |
|---|---|---|
| FORM-001 | xgi_roll3 | Raw xgi is review_signal for MID (rho 0.31, stable — G-EDA3-01); FWD (rho 0.50, insufficient_data stability — G-EDA3-02); DEF (rho 0.16, insufficient_data — G-EDA3-02) |
| FORM-002 | xgi_roll5 | Same basis as FORM-001; tests 5-GW window against 3-GW |
| FORM-003 | goals_scored_roll3 | Raw goals_scored is core_signal for DEF (rho 0.32, stable — G-EDA3-03); review_signal MID/FWD with event sparsity caveat (G-EDA3-05) |
| FORM-004 | points_roll3 | Mandatory naive baseline per EVAL_DESIGN.md §6 (G-EDA7-02) |
| FORM-005 | points_roll5 | Mandatory naive baseline per EVAL_DESIGN.md §6 (G-EDA7-02) |
| FORM-006 | minutes_roll3 | Availability signal — flagged; raw association only; primary characterisation in LENS-AVAIL (G-EDA7-05) |

**Excluded candidates (not registered, not tested):**

| Signal | Reason |
|---|---|
| xa_roll3, xa_roll5 | xa is a component of xgi; not an independent candidate (G-EDA6-02) |
| xg_roll3, xg_roll5 | xg is component of xgi at FWD/MID (partial_rho 0.93); not independent (G-EDA6-03) |
| creativity_roll* | Component of ict_index; not a raw form signal (G-EDA7-06) |
| ict_index_roll* | Composite index; not a form signal candidate for this lens (G-EDA7-06) |
| assists_roll* | Not registered — assists is an established EDA baseline; future lens if needed |
| bonus_roll*, bps_roll* | Points components — target leakage risk (G-EDA7-06) |

---

## 3. Target variable

**Target:** `total_points` at GW N+1 (lag-1 alignment).

Signal at GW N predicts returns at GW N+1. This reflects the actual FPL decision context:
a manager selects a player for GW N+1 based on information available at GW N.

**Lag alignment verified by:** DAL state contract (`dal/state/STATE_CONTRACT.md`). Lens
execution code must assert this alignment before any correlation runs (G-EDA0-01,
G-EDA0-03).

---

## 4. Population

**Qualified-start threshold:** `minutes >= 60` at GW N (G-EDA1-04).

**Rationale:** Primary population confirmed by EDA-1 (n=5,879, GW6-33, minutes≥60). EDA-4 showed population robustness
is stable — delta_rho = 0 between primary and minimal population definitions for all 110
tested signal-position pairs (G-EDA4-01, G-EDA4-02). No position-specific override is
warranted.

**BGW rows:** Excluded naturally — BGW rows have null minutes and do not pass `minutes >= 60`.

**DGW rows:** Flagged but not excluded. DGW rows are included in the analysis with an
explicit `is_dgw` indicator column. Results must be reported with and without DGW rows
to assess DGW sensitivity (G-EDA1-05).

**GK playing time:** GK median minutes = 90 in both EDA halves. `minutes >= 60` effectively
includes all GK appearances. No adjustment needed for GK population.

---

## 5. GW window

**Study window:** GW 3 to GW 33 inclusive.

- Lower bound GW 3: rolling window warmup — GW 1-2 excluded because 3-GW rolling features
  are undefined or unreliable for these rows (G-EDA0-02, G-EDA1-03).
- Upper bound GW 33: GW 34 excluded (14 of 20 teams with a fixture — unequal
  exposure; G-EDA1-02).
- FORM-002 and FORM-005 (5-GW windows) require GW 6+ for valid values. These signals use
  GW 6-33 for correlation analysis. GW 3-5 rows are present in the dataset for alignment
  purposes but excluded from 5-GW signal correlation runs.

---

## 6. GW block structure

Three temporal blocks are defined for stability analysis. These are independent of the
EDA two-block structure (GW 1-17 / GW 18-38), which was too coarse for lens analysis
(G-EDA5-01).

| Block | GW range | Description |
|---|---|---|
| early | GW 3-12 | Season opening — squad settling, form establishment |
| mid | GW 13-26 | Core season — stable squad compositions, reliable signal |
| late | GW 27-33 | End-of-season — rotation risk, motivation effects |

**Block size note:** The early block is 10 GWs, mid is 14 GWs, late is 7 GWs. The late
block is smaller — results from this block carry more uncertainty and should be interpreted
with caution for sparse event signals (goals_scored, assists).

For FORM-002 and FORM-005 (5-GW window), the effective early block starts at GW 6, reducing
it to 7 GWs. This is noted in the run artefact per block.

---

## 7. Correlation method

**Method:** Spearman rank correlation (G-EDA1-01).

**Rationale:** `total_points` is right-skewed (skew=1.58, kurt=2.80). Pearson is not
appropriate. Spearman is justified at STRONG_EVIDENCE level (skew=1.58 from EDA-1).

**Resampling unit for bootstrap:** Gameweek-level observations, not player-level.
One bootstrap sample = resample with replacement from the set of (player, GW) observation
pairs within the analysis window or block. This preserves the temporal structure of the
data and avoids overstating precision from players with many appearances.

**Bootstrap parameters:**

| Parameter | Value | Rationale |
|---|---|---|
| N samples | 2,000 | Standard for bootstrap CI stability |
| CI level | 95% | Per EVAL_DESIGN.md §4.2 |
| Seed | 42 | Fixed for reproducibility |

**Reported per run:**

- `rho` — pooled Spearman correlation across full study window
- `ci_lower`, `ci_upper` — 2.5th and 97.5th percentile of bootstrap distribution
- `n` — number of (player, GW) observations used
- `ci_excludes_zero` — boolean (True if `ci_lower > 0` or `ci_upper < 0`)

---

## 8. Classification logic

Signal classification follows EVAL_DESIGN.md §4.2 and the registry schema:

| Condition | Classification |
|---|---|
| CI excludes zero AND quintile bin separation confirmed AND consistent across ≥2 of 3 GW blocks | `informative` |
| CI crosses zero | `uninformative` |
| CI excludes zero in aggregate but inconsistent across GW blocks (passes <2 of 3 blocks) | `unstable` |
| CI excludes zero but only for specific positions or only in specific block contexts | `conditional` |

**Decision sequence — applied per signal per position:**

1. Check CI gate: does `ci_excludes_zero = True` for the full study window?
   - If False → `uninformative`. Stop.
2. Check decision relevance: does quintile bin analysis show meaningful separation?
   - If not → `uninformative` even if CI gate passes. (A signal can pass CI and fail here.)
3. Check block stability: does the signal pass CI gate in ≥2 of 3 GW blocks?
   - If passes in all 3 → `informative` (if step 2 also passed)
   - If passes in 2 of 3 → `informative` with block caveat documented
   - If passes in <2 → `unstable`
4. Check positional scope: if the signal passes in some positions but not others →
   `conditional` (informative with explicit position constraint)

**Naive baseline gate (per EVAL_DESIGN.md §6):** For each signal, compare `rho` against
the naive baseline (FORM-004 points_roll3 or FORM-005 points_roll5). Record
`clears_naive_baseline = True/False`. A signal that fails the naive baseline gate
may still be classified `informative` — but the failure is documented in the registry
Known Caveats. The naive baseline gate is not a disqualifying gate; it is a context gate.

---

## 9. Quintile bin decision relevance

**Procedure:**

1. Within each (position, GW), rank players by signal value.
2. Assign to quintile bins Q1 (lowest signal) through Q5 (highest signal).
3. Compute mean actual `total_points` at GW N+1 per bin.
4. Assess: is the Q5 mean materially greater than the Q1 mean? Is the ordering
   approximately monotonic (Q1 < Q2 < Q3 < Q4 < Q5)?

**Threshold for "meaningful separation":** A Q5−Q1 mean gap of at least 1.0 point AND
approximately monotonic bin ordering (no reversal of more than one step that is sustained
across blocks). This threshold is set a priori and cannot be revised after results are known.

**Output:** `studies/runs/LENS-FORM-{timestamp}/quintile_results.csv` with columns:
`signal`, `position`, `block`, `q1_mean`, `q2_mean`, `q3_mean`, `q4_mean`, `q5_mean`,
`q5_q1_gap`, `is_monotonic`, `decision_relevant`.

---

## 10. Run artefacts

All run outputs are written to `studies/runs/LENS-FORM-{timestamp}/`:

| File | Content |
|---|---|
| `lag_alignment_check.txt` | Pass/fail assertion for lag-1 alignment. Includes sample of (GW N signal value, GW N+1 target value) pairs for manual verification. |
| `correlation_results.csv` | Per-signal × position × window (full). Columns: signal, position, rho, ci_lower, ci_upper, n, ci_excludes_zero, clears_naive_baseline. |
| `block_results.csv` | Per-signal × position × block. Same columns as correlation_results plus block. |
| `quintile_results.csv` | Per-signal × position × block. Quintile bin means and decision_relevant flag. |
| `classification_summary.csv` | Per-signal × position. Final lens classification: informative/uninformative/unstable/conditional. Includes rationale column. |
| `run_metadata.json` | Timestamp, seed, N bootstrap samples, GW window, population filter, study window per signal. |

---

## 11. EDA-0 pre-run assertion

Before any correlation runs, the execution code must perform and log the following checks:

1. **Lag alignment check:** Verify that for a sample of rows, `xgi_roll3` at GW N reflects
   GWs N-3 through N-1. Spot-check 10 player-GW pairs against raw GW-level data.
2. **Rolling window warmup:** Verify that GW 1-2 rows have NaN for all rolling features.
   If any GW 1-2 row has a non-null rolling value, fail with an assertion error.
3. **Target alignment:** Verify that target column (`total_points_next_gw`) at GW N
   matches `total_points` at GW N+1 for the same player.

Pass/fail for each check is written to `lag_alignment_check.txt`. If any check fails,
the run halts with a descriptive error. Results are not produced until all three pass.

---

## 12. Positions covered

| Signal | GK | DEF | MID | FWD |
|---|---|---|---|---|
| FORM-001 xgi_roll3 | ✗ | ✓ | ✓ | ✓ |
| FORM-002 xgi_roll5 | ✗ | ✓ | ✓ | ✓ |
| FORM-003 goals_scored_roll3 | ✗ | ✓ | ✓ | ✓ |
| FORM-004 points_roll3 | ✓ | ✓ | ✓ | ✓ |
| FORM-005 points_roll5 | ✓ | ✓ | ✓ | ✓ |
| FORM-006 minutes_roll3 | ✗ | ✓ | ✓ | ✓ |

**GK exclusions:**
- FORM-001, FORM-002: raw xgi GK rho = −0.03 — no EDA basis for GK candidacy
- FORM-003: goals_scored GK is a structural zero (G-EDA2-03)
- FORM-006: GK playing time near-constant (median 90 both halves) — rolling minutes adds no information

---

## 13. Limitations

Documented a priori as required by EVAL_DESIGN.md §4.6:

**Single-season scope:** All findings describe the 2025-26 population. No cross-season
generalisation is supported by this study.

**Two-block temporal stability from EDA:** EDA-5 temporal stability used first/second half
blocks (GW 1-17 / GW 18-38). LENS-FORM uses a finer three-block structure. EDA stability
findings are indicative only — they do not determine LENS-FORM block stability conclusions.

**Sparse event signals:** goals_scored and assists have median 0 within any 3-GW window
for most players. Rolling window means are dominated by observations where the event
occurred. Small-n positions (FWD n=49, GK n=35) amplify this effect.

**xgi DEF and GK:** Raw xgi DEF rho = 0.16 (insufficient_data stability); xgi GK rho = −0.03.
Rolling window signals at these positions have weak EDA foundations and are expected to
produce uninformative or conditional classifications.

**minutes_roll3 scope:** LENS-FORM characterises raw association only. Playing time
consistency, reliability, and availability properties are LENS-AVAIL territory.
minutes_roll3 classification from this study should not be used to inform availability
modeling without LENS-AVAIL findings.

**No causal inference:** This study measures rank correlation. Association is not causation.
A signal that associates with future returns does not cause those returns.

---

## 14. What this study does not do

- Does not modify the intelligence scoring layer
- Does not produce a ranked player output for operational use
- Does not constitute a claim that form signals improve live FPL decisions
- Does not advance signals to synthesis — that is SYNTH-01
- Does not characterise fixture context effects on form — that is LENS-FIXTURE-GW
- Does not characterise playing time reliability — that is LENS-AVAIL

The sole output is a classification per signal per position in `SIGNAL_REGISTRY.md`,
traceable to bootstrap confidence intervals, GW block stability evidence, and quintile
bin decision relevance analysis.

---

## 15. Design lock declaration

This document is locked as of 2026-05-22.

No design decisions may be changed after Phase 1 execution begins. If a material error is
discovered in this document before execution begins, a corrected version may be produced
with a documented changelog entry. After the first correlation run is produced, this
document is immutable.

Post-hoc changes to population definition, GW window, bootstrap parameters, block
boundaries, or classification logic constitute methodological failure per EVAL_DESIGN.md §8.2.
