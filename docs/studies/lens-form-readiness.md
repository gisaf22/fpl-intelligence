# LENS-FORM — Readiness Assessment and Execution Plan

**Type:** Pre-study assessment and phased execution plan  
**Status:** ACTIVE — gates execution of LENS-FORM  
**Authored:** 2026-05-22  
**Supersedes:** No prior document (first assessment of this study)

---

## 1. Goal of this step

Complete the first lens study (LENS-FORM) such that:

1. Form signal candidates advance from unregistered → registered → lens-classified in `SIGNAL_REGISTRY.md`
2. The signal registry contains its first entries with `Lens Status` set to `informative`, `uninformative`, `unstable`, or `conditional`
3. The evidence base is sufficient to decide whether form signals enter SYNTH-01

This is not a model comparison. This is signal characterisation. The output is a classification per signal per position, traceable to bootstrap confidence intervals and GW block stability analysis, against which SYNTH-01 can make defensible inclusion decisions.

---

## 2. Current state — what exists

### 2.1 System EDA

Seven EDA notebooks have been executed. CSV outputs exist in `studies/eda/findings/`:

| File | Content |
|---|---|
| `eda_02_signal_registry.csv` | 29 candidate signals with initial promotion classes |
| `eda_03_joint_registry.csv` | 116 rows — 29 signals × 4 positions. Full characterisation: rho, association class, temporal stability, promotion class, downstream status |
| `eda_04_population_validity.csv` | Population robustness assessment |
| `eda_05_signal_stability.csv` | GW block stability (first_half GW 1-17, second_half GW 18-38) |
| `eda_06_pairwise_rho.csv` | Inter-signal redundancy |
| `eda_06_partial_rho.csv` | Partial correlations controlling for co-variates |
| `eda_07_signal_synthesis.csv` | Final synthesis — promotion class and downstream status |

**What is missing:** `EDA_FINDINGS.md` — the synthesis document that EVAL_DESIGN.md Section 4.1 requires, documenting gate decisions and tracing each EDA design choice to its finding. The CSV outputs exist; the human-readable synthesis does not.

### 2.2 Form signals in the EDA

**Critical structural finding: no rolling window signals appear anywhere in the EDA.**

The EDA characterised 29 raw base signals. The form signals that the intelligence layer currently uses (`points_roll3`, `xgi_roll3`, `minutes_roll3`, `points_roll5`, `xgi_roll5`) are not in the EDA registry at all. They are DAL state-layer features that were not characterised during system EDA.

The raw form proxies that ARE in the EDA (relevant to LENS-FORM):

| Signal | Position | Promotion Class | Downstream Status | Temporal Stability | rho_pooled |
|---|---|---|---|---|---|
| xgi | MID | review_signal | caveated | stable | 0.31 |
| xgi | FWD | review_signal | caveated | insufficient_data | 0.50 |
| xgi | DEF | review_signal | caveated | insufficient_data | 0.16 |
| xgi | GK | review_signal | caveated | insufficient_data | −0.03 |
| goals_scored | DEF | core_signal | eligible | stable | 0.32 |
| goals_scored | MID | review_signal | caveated | stable | 0.58 |
| goals_scored | FWD | review_signal | caveated | stable | 0.85 |
| assists | MID | core_signal | eligible | stable | 0.49 |
| assists | FWD | core_signal | eligible | stable | 0.36 |
| assists | DEF | review_signal | eligible | moderate_shift | 0.27 |

**Implication:** The EDA provides the evidence base that raw form proxies associate with returns. It does not tell us whether smoothing those signals over rolling windows improves predictive quality. That is precisely what LENS-FORM must test — consistent with EVAL_DESIGN.md Section 6: *"lag-1 raw total_points versus roll-5 smoothed signal. Does smoothing over five gameweeks add information beyond the simplest possible form signal?"*

### 2.3 EDA structural observations

- **116 rows, 29 signals × 4 positions.** 9 eligible, 83 caveated, 24 blocked.
- **76/116 rows have `insufficient_data` temporal stability.** Most signals could not be assessed for GW block consistency — likely due to the two-block structure (GW 1-17 / GW 18-38) and small within-block sample sizes for some positions.
- **GW block structure is two-block only** (first_half / second_half). EVAL_DESIGN.md requires early/mid/late stratification for the lens study. This is a gap between EDA block structure and lens study requirements.
- **Only 8 `core_signal` entries across all 116 rows.** Eligible core signals: goals_scored (DEF), assists (MID, FWD, DEF), bonus (GK, DEF), bps (GK), creativity (MID), ict_index (DEF).

### 2.4 Signal registry

`SIGNAL_REGISTRY.md` is empty. Version 1.0, April 2026: *"Registry is empty. No signals are registered."* Previous study outputs (SA, SB, SC, SE) are explicitly invalidated and archived.

### 2.5 Existing lens code

`studies/lenses/form/study.py` is a non-functional stub:

| Property | Current state | Required state |
|---|---|---|
| Signal tested | `assists` | rolling form signals (xgi_roll3, xgi_roll5, points_roll3 etc.) |
| Target variable | same-GW `total_points` | next-GW `total_points` (lag-1) |
| CI method | scipy p-value | bootstrap 95% CI |
| Positions covered | MID only | GK, DEF, MID, FWD |
| Time structure | pooled across all GWs | GW block stratification |
| Population filter | minutes ≥ 60 | to be defined in LENS_DESIGN.md per EDA-4 findings |

The stub must be replaced entirely. It does not represent a partial implementation — it represents a structurally different approach to the wrong problem.

### 2.6 No LENS_DESIGN.md

No locked design document exists for LENS-FORM. EVAL_DESIGN.md Section 4.2 requires all design decisions to be traceable to EDA findings or documented a priori rationale before any code runs.

---

## 3. Findings summary

| # | Finding | Severity | Implication |
|---|---|---|---|
| F1 | `EDA_FINDINGS.md` does not exist | Blocking | Cannot start LENS-FORM until gate 4.1 is satisfied |
| F2 | Rolling signals not in EDA | Structural | Lens study scope must be explicitly justified against raw-signal EDA findings |
| F3 | `SIGNAL_REGISTRY.md` is empty | Blocking | Signal candidates must be registered before lens runs |
| F4 | No `LENS_DESIGN.md` | Blocking | No code may run before design is locked |
| F5 | Existing `study.py` is wrong on every dimension | Operational | Must be replaced, not patched |
| F6 | GW block structure is two-block (first/second half) | Constraint | Lens study must define three-block structure explicitly |
| F7 | 76/116 EDA signals have insufficient temporal stability data | Evidence quality | Conditional signal classification is likely for many positions |
| F8 | xgi association is stable for MID (rho 0.31) only; insufficient data for other positions | Signal scope | Lens study scope may need to constrain by position from the start |

---

## 4. Phased execution approach

Three phases before any lens code runs. One phase of execution. One phase of registry update.

---

### Phase 0 — Prerequisites (no code, no lens analysis)

**Gate: all three tasks complete before Phase 1 begins.**

#### 0.1 — Write EDA_FINDINGS.md

Produce the synthesis document from existing CSV outputs. This is a writing task, not a computation task — the data exists.

Required content:
- EDA-0: lag alignment status, rolling window construction verification, leakage check result
- EDA-1: target distribution findings that justify Spearman (non-normal, rank-based)
- EDA-2: signal space findings, initial pruning decisions
- EDA-3: joint registry summary — which signals are eligible/caveated/blocked and why
- EDA-4: population validity findings — which population filter to use per position
- EDA-5: signal stability findings — which signals are stable vs insufficient data across blocks
- EDA-6: redundancy findings — which signal pairs are co-linear; which to exclude
- EDA-7: synthesis gate decisions — which signals advance to lens analysis and why

**Output:** `studies/eda/findings/EDA_FINDINGS.md`  
**Success criterion:** Every design decision in LENS_DESIGN.md can reference a finding in this document.

#### 0.2 — Register form signal candidates in SIGNAL_REGISTRY.md

Based on EDA findings, register the rolling window signal candidates that LENS-FORM will characterise. Per SIGNAL_REGISTRY.md protocol: signals must be registered before lens runs.

Candidate signals for LENS-FORM (to be confirmed against EDA_FINDINGS.md):

| Signal ID | Signal | Basis for candidacy |
|---|---|---|
| FORM-001 | xgi_roll3 | Raw xgi is review_signal for MID (rho 0.31, stable); test whether 3-GW smoothing improves |
| FORM-002 | xgi_roll5 | Same basis; test whether 5-GW window outperforms 3-GW |
| FORM-003 | goals_scored_roll3 | goals_scored is core_signal for DEF (rho 0.32, stable); test smoothed version |
| FORM-004 | points_roll3 | Composite output signal — test whether smoothed points predicts future points |
| FORM-005 | points_roll5 | Test whether 5-GW window reduces noise vs 3-GW |
| FORM-006 | minutes_roll3 | Candidate for availability characterisation; may belong in AVAIL lens |

**Note on FORM-004 and FORM-005:** `total_points` as a predictor of future `total_points` is the naive baseline defined in EVAL_DESIGN.md Section 6. These must be included to confirm whether any other form signal clears the naive baseline. If xgi_roll3 does not outperform points_roll3 as a predictor, xgi_roll3 adds nothing.

**Note on FORM-006:** `minutes_roll3` is an availability signal. Register it here as it appears in the form layer of the intelligence code, but flag it as a candidate for the AVAIL lens. LENS-FORM will characterise its raw association; LENS-AVAIL will characterise its stability and reliability properties.

**Output:** Updated `SIGNAL_REGISTRY.md` with EDA Status set per finding  
**Success criterion:** Every LENS-FORM candidate has a registry entry with `EDA Status` populated.

#### 0.3 — Lock LENS_DESIGN.md for LENS-FORM

Write and lock the methodology document before any code runs. Must specify:

- **Signal set:** Which signals from 0.2, which excluded and why
- **Population:** Qualified-start threshold (minutes ≥ N per EDA-4 findings), position handling
- **Target:** `total_points` at GW N+1 (lag-1 alignment explicit)
- **Method:** Spearman rank correlation with bootstrap 95% CIs (N bootstrap samples to be specified)
- **Time structure:** Three GW blocks — early (GW 3-12), mid (GW 13-26), late (GW 27-38). GW 1-2 excluded: rolling features are in warmup period.
- **Baselines:** Null (rho=0, CI crossing zero); naive (lag-1 raw total_points vs roll-N smoothed)
- **Decision gate:** CI excludes zero AND quintile bin outcome separation confirmed
- **Decision categories:** `informative` / `uninformative` / `unstable` / `conditional` (matching registry schema)
- **Traceability:** Each design decision references a specific finding in EDA_FINDINGS.md

**Output:** `studies/lenses/form/LENS_DESIGN.md` (locked)  
**Success criterion:** Document is locked. No further changes permitted once Phase 1 begins.

---

### Phase 1 — Lens Execution

**Gate: Phase 0 complete. LENS_DESIGN.md locked.**

#### 1.1 — EDA-0 verification

Before any correlation runs: confirm lag-1 alignment in the state layer. Verify that `xgi_roll3` at GW N reflects GWs N-3 through N-1, not N-2 through N (off-by-one error risk). Verify no future data leaks into rolling windows. This is an execution risk identified in EVAL_DESIGN.md Section 12.1.

**Output:** Pass/fail assertion logged in run artefact.

#### 1.2 — Per-signal Spearman with bootstrap 95% CIs

For each registered signal × position combination:
- Filter to qualified-start population per LENS_DESIGN.md
- Align signal at GW N to target at GW N+1 (lag-1)
- Compute Spearman rho across the full study window
- Compute bootstrap 95% CI (resample GW-level observations, not player-level)
- Record: rho, CI lower, CI upper, N, whether CI excludes zero

**Output:** `studies/runs/LENS-FORM-{timestamp}/correlation_results.csv`

#### 1.3 — GW block stratification

Repeat 1.2 within each GW block (early / mid / late per LENS_DESIGN.md definition). Record per-block rho and CI. This produces the stability evidence required by EVAL_DESIGN.md 4.2 (*"practical meaningfulness confirmed across GW blocks"*).

**Output:** `studies/runs/LENS-FORM-{timestamp}/block_results.csv`

#### 1.4 — Naive baseline comparison

For each signal: compare rho against the naive baseline (lag-1 raw total_points). If a smoothed rolling signal does not outperform raw lag-1 total_points, it fails the naive baseline gate defined in EVAL_DESIGN.md Section 6.

**Output:** Added column in `correlation_results.csv`: `clears_naive_baseline` (True/False)

#### 1.5 — Quintile bin decision relevance

Rank players by signal value within position × GW. Assign to quintile bins (Q1-Q5). Compute mean actual total_points per bin. Assess whether separation across bins is monotonic and meaningful. This is the decision-relevance gate from EVAL_DESIGN.md 4.2 — a signal can pass the CI gate and still fail here.

**Output:** `studies/runs/LENS-FORM-{timestamp}/quintile_results.csv`

---

### Phase 2 — Registry Update and Classification

**Gate: Phase 1 complete. All run artefacts present.**

#### 2.1 — Classify each signal per registry schema

Apply the decision logic from LENS_DESIGN.md:

| Condition | Classification |
|---|---|
| CI excludes zero AND quintile bin separation confirmed AND consistent across ≥2 of 3 blocks | `informative` |
| CI crosses zero | `uninformative` |
| CI excludes zero in aggregate but inconsistent across blocks | `unstable` |
| CI excludes zero but only in specific positions or contexts | `conditional` |

#### 2.2 — Update SIGNAL_REGISTRY.md

Set `Lens Status` per signal per position. Document known caveats (redundancy with other signals, positional distortion, contextual dependency). Mark any signal that fails the naive baseline even if it passes the CI gate.

#### 2.3 — Determine synthesis eligibility

Signals with `Lens Status` of `informative` or `conditional` advance to SYNTH-01 as candidates. All others remain in registry as `uninformative` or `unstable` — documented, not deleted.

---

## 5. Success criteria

| Phase | Done when |
|---|---|
| Phase 0.1 | `EDA_FINDINGS.md` exists with gate decisions traceable to CSV outputs |
| Phase 0.2 | SIGNAL_REGISTRY.md has ≥4 form signal candidates with EDA Status populated |
| Phase 0.3 | `LENS_DESIGN.md` is locked; no design decisions are post-hoc |
| Phase 1 | Bootstrap CI and quintile results exist for all registered signals across all three GW blocks |
| Phase 2 | Every registered form signal has a `Lens Status` in SIGNAL_REGISTRY.md with documented rationale |

**Failure condition (per EVAL_DESIGN.md 8.1):** If no form signal passes both the CI gate and the decision-relevance gate in any position, the outcome is `uninformative` across the board. This is a valid and informative result — it is not a failure of execution. It is reported honestly and the signals remain in the registry with status `uninformative`.

---

## 6. What this step does not do

- Does not modify the intelligence scoring layer
- Does not retrain any model or adjust any weights
- Does not produce a ranked output for operational use
- Does not constitute a claim that form signals improve live FPL decisions
- Does not advance signals to synthesis — that is SYNTH-01, which follows this step

The sole output is a classified set of form signal candidates in `SIGNAL_REGISTRY.md`, grounded in bootstrap evidence and GW block stability, traceable to a locked design document and existing EDA findings.

---

## 7. Sequencing relative to other lens studies

LENS-FORM is the first lens study. It does not need to wait for LENS-MARKET, LENS-FIXTURE-GW, or LENS-AVAIL. However:

- LENS-AVAIL should run before SYNTH-01 because minutes stability signals interact with form signals in the intelligence layer. If minutes_roll3 is classified as conditional or uninformative, the form signal population filter may need adjustment.
- LENS-FIXTURE-GW should run before SYNTH-01 for the same reason — SYNTH-01 tests whether fixture difficulty conditions form.

All four lens studies should complete before SYNTH-01 begins. LENS-FORM does not gate the others.
