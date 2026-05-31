# Study: Population Threshold Calibration (POPTHRESH-01)

**Status:** DESIGN — not yet executed  
**Study ID:** POPTHRESH-01  
**Study type:** Calibration (threshold selection), not hypothesis test  
**Design authored:** 2026-05-31  
**Governed by:** `signals/governance/EVAL_DESIGN.md`  
**Governance items:** `docs/governance/threshold-registry.md` §REG-T-01, §AVAIL-T-02  
**Execution module:** `studies/experiments/population_threshold_study.py` (to be written)  
**Results document:** `docs/studies/results/popthresh-01-results.md` (written after execution)

---

## 1. Study Question

> Is 60 minutes the correct boundary for the performance population used in signal
> characterisation and scoring engine evaluation?
>
> Specifically: does restricting signal-target analysis to `minutes >= 60` produce more
> coherent (higher and more temporally stable) rho estimates than alternative minute
> thresholds, consistent with the structural break in FPL's scoring formula at that
> boundary?

This is a **calibration study**. The output is not "supported" or "rejected" — it is a
threshold value with a governance classification. The 60-minute threshold either gets
promoted to `EVALUATION-DERIVED` in `threshold-registry.md`, or the threshold changes
to whatever the evidence supports.

---

## 2. Analytical Motivation

FPL's scoring formula has a structural break at 60 minutes:

| Minutes played | Appearance points | Clean sheet eligible | BPS baseline |
|---|---|---|---|
| 0 | 0 | No | No |
| 1–59 | 1 | No (GK/DEF/MID) | Partial |
| 60+ | 2 | Yes (GK/DEF/MID) | Full |

Pooling rows from both regimes into a single `total_points` target produces a dependent
variable whose generating process differs across observations. For a DEF who plays 45
minutes, `total_points` cannot include a clean sheet bonus regardless of the team
result. For a DEF who plays 61 minutes in the same match, it can. Signal associations
computed on a mixed-regime population conflate "does this signal predict scoring-regime
membership?" with "does this signal predict returns within a regime?" — which are
different questions.

The current `filter_performance` boundary (`CLEAN_SHEET_MIN_MINUTES = 60`, from
`domain/fpl_scoring`) is semantically justified by this game-rule structure. This study
tests whether the semantic justification is supported empirically: does signal-target
rho actually improve at 60 minutes relative to lower thresholds, or is the 60-minute
choice arbitrary within a flat rho landscape?

A secondary question is whether the improvement (if any) is driven by the structural
break or simply by N — larger populations at lower thresholds may reduce noise and
inflate rho estimates. The range population analysis (§7) controls for this.

---

## 3. Study Type: Calibration, Not Hypothesis

MINSTAB-01 tested a **directional hypothesis** (stability conditions signal; H0 can be
rejected or supported). This study is different.

The question "which threshold is right?" has no null hypothesis to reject. Rho does not
have a known distribution under a point null, and no single test statistic answers
whether 60 is "better" than 45. The right framework is:

1. Define a metric (rho + temporal stability of rho)
2. Compute that metric across a pre-specified threshold grid
3. Apply a pre-specified decision rule to select the threshold
4. Classify the chosen threshold as `EVALUATION-DERIVED` or `GOVERNANCE-CONVENTIONAL`

The decision rule is committed below (§8) before any data is examined. **Post-hoc
adjustment of the decision rule is not permitted.** If the results are ambiguous, the
correct classification is `GOVERNANCE-CONVENTIONAL`, not reclassification of 60 as
`EVALUATION-DERIVED`.

---

## 4. Threshold Sweep Design

### Primary grid

| Label | Filter | Analytical meaning |
|---|---|---|
| T1 | `minutes >= 1` | Participation: appeared at all |
| T30 | `minutes >= 30` | Meaningful involvement: half a match |
| T45 | `minutes >= 45` | Standard match threshold |
| T60 | `minutes >= 60` | FPL scoring break: current `filter_performance` |
| T75 | `minutes >= 75` | Substantial playing time |
| T90 | `minutes >= 90` | Full match only |

### Range populations (N-effect control)

| Label | Filter | Purpose |
|---|---|---|
| R30_59 | `30 <= minutes < 60` | Sub-break regime (1pt appearance, no clean sheet) |
| R60_74 | `60 <= minutes < 75` | Narrowband at the break |
| R75_89 | `75 <= minutes < 90` | Above-break, sub-full |

If rho improvement from T30→T60 holds within the range populations (R30_59 vs R60_74),
the structural break is real. If it disappears in range populations, the improvement is
N-driven and the threshold is not justified by the scoring-regime argument.

---

## 5. Signal Set

All governed signals currently approved for operational scoring (from
`signals/governance/evaluation_metadata.yaml`, `downstream_status: approved`):

| Signal | Position(s) | Registry entry |
|---|---|---|
| `xgi_roll3` | DEF, MID, FWD | FORM-001 |
| `xgi_roll5` | MID | FORM-002 |
| `minutes_roll8` | DEF, MID | AVAIL-003 |
| `transfers_in` | DEF, MID | MARKET-001 |
| `purchase_price` | DEF | MARKET-003 |
| `ownership_count` | MID | MARKET-004 |

Analysis is run **per signal per position** as registered. Signals not approved for a
position are excluded at that position (e.g. `xgi_roll3` is not evaluated at GK).

---

## 6. Target Variable and Population Window

**Target:** `total_points` at GW N+1 (lag-1 alignment, consistent with lens studies).

**Evaluation window:** GW 6–38 inclusive (full 2025/26 season; rolling window warmup
requires GW 6 minimum). GW 34–38 are the SYNTH-01 holdout; they are included here
because this study characterises population structure, not signal decisions.

**Data source:** `load_mart(db_path).mart` — the governed analytical mart via
`dal.pipeline.load()`.

**Temporal note:** At row (player_id, gw=N), all features are computed with lag-1 shift
applied by the DAL feat layer. `total_points` at GW N+1 is produced by joining on
`(player_id, gw=N+1)`. This alignment is structural — no manual shift is required in
the study code, but it must be asserted before evaluation runs.

---

## 7. Metrics

For each (threshold, signal, position) combination:

| Metric | Definition | Interpretation |
|---|---|---|
| `mean_rho` | Mean Spearman rho(signal, total_points_next) across GW blocks | Average predictive association |
| `std_rho` | Std of per-block rho | Temporal stability |
| `n_mean` | Mean population size per GW at this threshold | Exposure |
| `n_min` | Minimum population size per GW | Identifies sparse regimes |

**GW blocks for temporal stability:** Split GW 6–38 into three equal-size blocks
(GW 6–18, GW 19–30, GW 31–38). Stability = rho sign is consistent across all three
blocks. This matches the stability kernel used in the lens studies
(`studies/kernels/windows.py`).

**Summary metric per threshold:** `threshold_score` = `mean_rho` weighted by block
stability (1.0 if all 3 blocks positive, 0.67 if 2/3, 0.33 if 1/3, 0.0 if none). This
combines predictive strength and consistency into a single comparand for the decision
rule.

---

## 8. Pre-Specified Decision Rule

This rule is **locked at design time**. It cannot be adjusted after results are observed.

### Step 1 — Identify the candidate threshold

Compute `threshold_score` for T60 and all alternatives across all (signal, position)
pairs in §5. Average across signals and positions to produce one score per threshold.

**Candidate threshold** = threshold with highest average `threshold_score`.

### Step 2 — Apply the materiality gate

| Condition | Classification | Action |
|---|---|---|
| T60 is the candidate AND T60 score >= all alternatives | `EVALUATION-DERIVED` | Retain `CLEAN_SHEET_MIN_MINUTES = 60` in `filter_performance`; update threshold-registry.md |
| T60 is the candidate but an alternative is within 0.02 of T60 score | `EVALUATION-DERIVED` (retained by design rule) | Retain 60; note that alternatives are not materially different |
| An alternative threshold beats T60 by >= 0.02 AND N >= 30 at that threshold | `EVALUATION-DERIVED` (new value) | Update `domain/fpl_scoring.py` `CLEAN_SHEET_MIN_MINUTES`; update `filter_performance` reference; update threshold-registry.md |
| `threshold_score` values are flat across all thresholds (all within 0.02) | `GOVERNANCE-CONVENTIONAL` | Retain 60; document that the threshold is semantically grounded but not empirically distinguished; update threshold-registry.md |
| N < 30 at all thresholds above T45 | Inconclusive — data quality issue | Do not update registry; inspect population composition |

### Step 3 — Range population check (structural break confirmation)

If Step 2 produces `EVALUATION-DERIVED` at T60:

Compare R30_59 vs R60_74 `mean_rho` per (signal, position). If R60_74 > R30_59 for
>= 50% of (signal, position) pairs, the improvement is consistent with the structural
break. Record as "break confirmed" in the results document. If not, record as
"break not confirmed — N-effect cannot be ruled out" — classification stands but with
this caveat added to the registry entry.

---

## 9. Governance Items Updated on Completion

Both entries are updated based on Step 2 outcome:

| Entry | Current classification | Outcome if evidence supports 60 | Outcome if different threshold | Outcome if flat |
|---|---|---|---|---|
| `REG-T-01` (`MINUTES_THRESHOLD`) | `EVALUATION-DEFERRED` | `EVALUATION-DERIVED` | `EVALUATION-DERIVED` (new value) | `GOVERNANCE-CONVENTIONAL` |
| `AVAIL-T-02` (`_MEDIUM_RISK_MINUTES_ROLL3`) | `EVALUATION-DEFERRED` | `EVALUATION-DERIVED` | `EVALUATION-DERIVED` (new value) | `GOVERNANCE-CONVENTIONAL` |

If the threshold changes, `domain/fpl_scoring.py:CLEAN_SHEET_MIN_MINUTES` is updated
and all downstream consumers (`filter_performance`, `population_builder.py`) inherit
the new value automatically.

---

## 10. Unsupported Claims

Regardless of outcome, this study does NOT support:

- "Signal X is a better predictor than signal Y" — the study is about population
  structure, not signal comparison. Signal rankings may differ across thresholds but
  the study cannot attribute this to signal quality vs. population composition effects.
- "The 45-minute threshold is better for FPL transfers" — threshold applicability for
  the transfer module (`TRANS-T-01`, `VAL-T-01`, `FIX-T-01`) requires a separate
  study with a transfer-specific metric. Those thresholds gate a different analytical
  question (eligible for ranking consideration) not the performance regime question.
- "GK should use a different threshold" — GK lens study is deferred to LENS-GK.
  GK rows are excluded from this study for the same reason.
- "The 60-minute boundary changes rho because of selection bias in starters" —
  the study cannot isolate scoring-regime effects from starter-quality effects without
  an instrumental variable. The range population analysis provides partial control only.

---

## 11. Validation Requirements

Before any result is interpreted:

1. **Temporal integrity** — assert that `total_points` column at GW N uses lag-1
   alignment (target is GW N+1, not GW N).
2. **Population monotonicity** — N(T1) >= N(T30) >= N(T45) >= N(T60) >= N(T75) >= N(T90)
   at every GW. Violation indicates a data issue.
3. **Range population partition** — R30_59 + R60_74 + R75_89 rows sum to T30 rows for
   each GW (within the 30–89 range). Violation indicates a filter implementation error.
4. **Block coverage** — each GW block contains >= 5 GWs with n_per_gw >= 10 at T60
   for at least one position (DEF or MID). If not, evaluation window is too sparse.
5. **Reproducibility** — same input DataFrame produces identical results on two
   consecutive calls (no random state).

---

## 12. Known Limitations

1. **Single season.** 2025/26 only. A threshold that performs best on one season may
   not generalise. A second season is required to confirm if the threshold changes.

2. **Target contamination at extremes.** At T1, the population includes sub-5-minute
   appearances whose `total_points` is generated by a very different regime (no
   appearance bonus, not in clean sheet counting). rho estimates at T1 are expected
   to be noisy by design, not as a finding.

3. **Starter quality confound.** Higher-minute players are systematically better players.
   Part of any rho improvement at higher thresholds may reflect this selection effect
   rather than the scoring-regime argument. The range analysis partially controls for
   this but cannot eliminate it.

4. **GW block count.** Three blocks (GW 6–18, 19–30, 31–38) is the minimum for
   stability assessment. The Phase 9 backtest showed end-of-season degradation for some
   signals. Block 3 (GW 31–38) may systematically underperform regardless of threshold,
   which would compress the stability metric for all thresholds equally.

---

## 13. Expected Artifacts

| Artifact | Path | Produced by |
|---|---|---|
| Design document | `docs/studies/popthresh-01-design.md` | This document |
| Study module | `studies/experiments/population_threshold_study.py` | Implementation (Change 3) |
| Results document | `docs/studies/results/popthresh-01-results.md` | Written after execution |
| Detail CSV | `outputs/popthresh_01_detail.csv` | Saved after execution |

---

## 14. Study Lifecycle

```
DESIGN LOCKED  →  IMPLEMENTATION  →  VALIDATION PASS  →  EXECUTION  →  RESULTS WRITTEN  →  REGISTRY UPDATED
2026-05-31         population_         all validation     run module      popthresh-01-       threshold-
(this doc)         threshold_study.py  tests pass                         results.md          registry.md
```

---

## 15. Related Documents

- `docs/governance/threshold-registry.md` §REG-T-01, §AVAIL-T-02 — governance items this study closes
- `docs/architecture/platform-evaluation-2026.md` Change 3 — engineering context for this study
- `population/populations.py` — `filter_performance` is updated if threshold changes
- `domain/fpl_scoring.py` — `CLEAN_SHEET_MIN_MINUTES` is updated if threshold changes
- `docs/archive/minutes-stability-xgi-study.md` — MINSTAB-01 design (template for this doc)
- `studies/kernels/windows.py` — block stability kernel used in §7
