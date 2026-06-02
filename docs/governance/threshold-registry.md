# Threshold Registry

**Status:** ACTIVE — 9-phase program complete; thresholds carry to 2026/27 calibration  
**Issued:** 2026-05-26  
**Updated:** 2026-05-27 (REPO-CONS-01 — post-program disposition added)  
**Authority:** Operational Convergence Plan Phase 1 (task 1.1)

Every operational threshold — any magic number that gates, filters, or weights a runtime decision — must have an entry here. Classification is required before any threshold may remain in production code.

---

## Classification Vocabulary

| Class | Meaning | 2026/27 disposition |
|-------|---------|---------------------|
| `EVALUATION-DERIVED` | Value comes directly from a lens study or SYNTH-01 finding with a documented gate decision | Carry forward — no action required |
| `EVALUATION-DEFERRED` | Value has a plausible semantic justification or is unjustified, but calibration was not completed in the 2025/26 program | Calibrate in 2026/27 lens studies; see `outputs/operational-baseline.md` |
| `RESOLVED` | Value was removed or superseded during the 2025/26 program | No action — historical record only |
| `CONTRADICTS-GATE` | Value actively conflicts with a governance gate decision | Must be resolved before operational use |

---

## Availability Module (`intelligence/availability.py`)

### AVAIL-T-01 — `_HIGH_RISK_MINUTES_ROLL3`
| Field | Value |
|-------|-------|
| **Constant** | `_HIGH_RISK_MINUTES_ROLL3` |
| **Value** | `30.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/availability.py:38` |
| **Stated rationale** | "less than half a match on average over 3 GWs" |
| **Governance assessment** | Semantic interpretation is plausible but no predictive study establishes that players below this threshold have materially different start rates. The "half a match" framing is intuitive, not empirically calibrated. |
| **Evidence required to promote** | LENS-AVAIL behavioral data: evaluate recall of "failed to start" at multiple thresholds (20, 25, 30, 35, 40 min). Select threshold maximising F1 against the "failed to start" label. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

### AVAIL-T-02 — `_MEDIUM_RISK_MINUTES_ROLL3`
| Field | Value |
|-------|-------|
| **Constant** | `_MEDIUM_RISK_MINUTES_ROLL3` |
| **Value** | `60.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/availability.py:39` |
| **Stated rationale** | Corresponds to FPL appearance bonus boundary (45+ min = appearance point; 60+ min = full bonus) |
| **Governance assessment** | Semantically grounded in FPL rules. However, the FPL appearance boundary is about points allocation, not predictive of future starts. A player averaging 60 min may still be a rotation risk. |
| **Evidence required to promote** | Same LENS-AVAIL threshold sweep as AVAIL-T-01. If 60.0 maximises F1, reclassify to `EVALUATION-DERIVED`. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

### AVAIL-T-03 — `_DIVERGENCE_THRESHOLD`
| Field | Value |
|-------|-------|
| **Constant** | `_DIVERGENCE_THRESHOLD` |
| **Value** | `20.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/availability.py:42` |
| **Stated rationale** | None documented. Editorial. |
| **Governance assessment** | No study defines what magnitude of roll3-vs-roll5 divergence is meaningful. 20 minutes is a round number. Players with a 20-minute divergence may or may not be at elevated risk; this has not been tested. |
| **Evidence required to promote** | LENS-AVAIL behavioral data: evaluate precision of "recent drop" flag at divergence thresholds of 10, 15, 20, 25, 30 minutes. Select threshold with best predictive precision against "started fewer games in next 3 GWs". |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Captain Module (`intelligence/captain.py`)

### CAPT-T-01 — `_MIN_MINUTES_ROLL3`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL3` |
| **Value** | `45.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/captain.py:49` |
| **Stated rationale** | "Players below this threshold are not starting reliably enough" |
| **Governance assessment** | No lens study evaluates captain precision as a function of this eligibility cutoff. The 45-minute value is between the two FPL appearance bonus thresholds, with no documented basis for choosing it over 30, 60, or 75 minutes. |
| **Evidence required to promote** | Historical captain return data: evaluate captain precision (fraction of top-1 picks that returned ≥ haul threshold) at eligibility floors of 30, 45, 60, 75, 90 minutes. Select floor where precision plateaus. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Value Module (`intelligence/value.py`)

### VAL-T-01 — `_MIN_MINUTES_ROLL5`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL5` |
| **Value** | `30.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/value.py:51` |
| **Stated rationale** | "bench-warmers inflate value artificially" |
| **Governance assessment** | Correct intuition but no lens study establishes 30 minutes as the threshold below which value scores become unreliable. 30 is a round number. |
| **Evidence required to promote** | Evaluate value score precision (forward return per £ of selected players) at minutes floors of 15, 30, 45, 60 minutes. Select floor where spurious selections (low minutes, high apparent value) are minimised. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Transfers Module (`intelligence/transfers.py`)

### TRANS-T-01 — `_MIN_MINUTES_ROLL5`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL5` |
| **Value** | `30.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/transfers.py:51` |
| **Stated rationale** | "transfers need sustained involvement" |
| **Governance assessment** | Same as VAL-T-01. The 30-minute floor is a round number without predictive calibration. |
| **Evidence required to promote** | Same methodology as VAL-T-01. May share calibration evidence. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Fixtures Module (`intelligence/fixtures.py`)

### FIX-T-01 — `_MIN_MINUTES_ROLL5`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL5` |
| **Value** | `30.0` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `intelligence/fixtures.py:49` |
| **Stated rationale** | Implicit — same as VAL-T-01 and TRANS-T-01 |
| **Governance assessment** | Same as VAL-T-01. All three 30-minute floors may be calibrated together. |
| **Evidence required to promote** | Same methodology as VAL-T-01. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Scoring Gate (`intelligence/scoring/signals.py`)

### SCORE-T-01 — `MIN_RHO`
| Field | Value |
|-------|-------|
| **Constant** | `MIN_RHO` |
| **Value** | `0.15` (removed) |
| **Classification** | `RESOLVED` |
| **File** | `intelligence/scoring/signals.py` — removed in Phase 8 (G-OPS-02) |
| **Resolution** | Removed in Phase 8 (G-OPS-02). All three affected signals (xgi_roll3 DEF, xgi_roll5 DEF, purchase_price DEF) received `APPROVED-*` decisions in SYNTH-01. CI gate is now the sole authority for scoring manifest confirmation. |

---

## Signal Registry (`signals/characterisation/`)

### REG-T-01 — `CLEAN_SHEET_MIN_MINUTES` (formerly `MINUTES_THRESHOLD`)
| Field | Value |
|-------|-------|
| **Constant** | `CLEAN_SHEET_MIN_MINUTES` (in `domain/fpl_scoring.py`) |
| **Value** | `60` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `domain/fpl_scoring.py` (platform Change 1); consumed via `population/populations.py:filter_performance` (platform Change 2). `MINUTES_THRESHOLD` in `signals/characterisation/population.py` was removed and replaced by this import. |
| **Stated rationale** | FPL scoring regime boundary: clean sheet eligibility, additional appearance point, and BPS minutes baseline all change at 60 minutes. |
| **Governance assessment** | Semantically grounded in FPL rules. The 60-minute boundary is meaningful for participation classification. However, for predictive population robustness purposes, this threshold has not been evaluated empirically. |
| **Evidence required to promote** | Population robustness analysis: evaluate signal-to-noise in `xgi_roll3` associations at 45, 60, and 75 minute participation floors. See `studies/experiments/population_threshold_study.py` (Change 3 — deferred to 2026/27). |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see platform-evaluation-2026.md §Change 3 |

### REG-T-02 — `HAUL_THRESHOLD_PTS`
| Field | Value |
|-------|-------|
| **Constant** | `HAUL_THRESHOLD_PTS` |
| **Value** | `12` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `signals/characterisation/geometry.py:62` |
| **Stated rationale** | Identifies top-bin concentration in scoring (haul-sensitivity analysis) |
| **Governance assessment** | 12 points is a commonly used FPL "haul" threshold (goal + assist + clean sheet + bonuses ≈ 12-15 pts). The threshold is semantically reasonable but was not derived from a distributional analysis of the total_points distribution. |
| **Evidence required to promote** | Analyse the total_points distribution to identify the natural break point separating the top performance cluster. May use kernel density estimation or percentile analysis. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

### REG-T-03 — `HAUL_DROP_MATERIAL`
| Field | Value |
|-------|-------|
| **Constant** | `HAUL_DROP_MATERIAL` |
| **Value** | `0.20` |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `signals/characterisation/geometry.py:63` |
| **Stated rationale** | A ≥ 20% rho drop indicates haul sensitivity |
| **Governance assessment** | No sensitivity study defines what magnitude of rho drop constitutes "material" haul concentration effect. 20% is a round editorial choice. |
| **Evidence required to promote** | Bootstrap sensitivity analysis: simulate haul removal and evaluate rho stability distribution. Select threshold where rho drop reliably indicates a haul-structure-dependent signal. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Signal Governance — FWD purchase_price phase cutoff

### MARKET-T-01 — FWD purchase_price phase cutoff (proposed GW ≤ 30)

| Field | Value |
|-------|-------|
| **Constant** | No code constant exists — phase restriction not yet implemented |
| **Value** | GW 30 (proposed cutoff for FWD purchase_price active window) |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `signals/governance/evaluation_metadata.yaml` — FWD purchase_price entry (removed from scoring pending SYNTH-02) |
| **Stated rationale** | Phase 9 holdout (GW 34–38) found purchase_price reversed at FWD (rho=−0.095, p=0.374). SYNTH-01 in-sample rho=0.155. GW 30 proposed as the phase boundary based on squad rotation patterns in the final third of the season. |
| **Governance assessment** | The reversal is non-significant (p=0.374) but directionally concerning. The GW 30 cutoff is an editorial proposal — no study has evaluated which gameweek boundary maximises the period-conditional rho. GW 25, 30, or 33 are all plausible boundaries. The signal has been removed from scoring entirely pending SYNTH-02 phase-conditional evaluation. |
| **Evidence required to promote** | SYNTH-02 phase-conditional analysis: compute FWD purchase_price rho in rolling 5-GW windows across GW 1–38. Identify the inflection point where rho direction changes. If a stable GW ≤ N phase exists with positive rho, implement a `gw <= N` gate and reclassify to `EVALUATION-DERIVED`. |
| **2026/27 disposition** | EVALUATION-DEFERRED — pending SYNTH-02. Signal excluded from scoring in 2026/27 until phase-conditional evidence is available. See ENG-02 in `docs/governance/eng-issues-2026.md`. |

---

## State Layer (`dal/feat/feat_player_gameweek.py`)

### STATE-T-01 — `_compute_minutes_trend` divergence threshold
| Field | Value |
|-------|-------|
| **Constant** | Inline literal `30` in `_compute_minutes_trend` |
| **Value** | `30` (minutes) |
| **Classification** | `EVALUATION-DEFERRED` |
| **File** | `dal/feat/feat_player_gameweek.py` — `_compute_minutes_trend` |
| **Stated rationale** | "30-minute divergence between last-3 and prior-3 GW mean classifies trend as rising or falling" |
| **Governance assessment** | Semantically plausible — a 30-minute swing in average minutes is a meaningful participation shift. However, no predictive study has evaluated whether this threshold maximises recall of actual availability changes. Could equally be 15 or 45 minutes without a principled justification. |
| **Domain restriction** | `minutes_trend` is restricted to the availability domain only (see `_AVAILABILITY_DOMAIN_ONLY`). It must not be consumed by form, captain, or value scoring modules. |
| **Evidence required to promote** | LENS-AVAIL Phase 8 calibration: evaluate recall of "failed to start in next 3 GWs" at divergence thresholds of 15, 20, 25, 30, 35, 45 minutes. Select threshold maximising F1. |
| **2026/27 disposition** | EVALUATION-DEFERRED — carries to 2026/27; see `outputs/operational-baseline.md` |

---

## Open Items

| ID | Threshold | Status | 2026/27 disposition |
|----|-----------|--------|---------------------|
| MARKET-T-01 | FWD purchase_price phase cutoff (GW 30 proposed) | EVALUATION-DEFERRED | SYNTH-02 phase-conditional analysis |
| STATE-T-01 | `minutes_trend` 30-min divergence (inline) | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| AVAIL-T-01 | `_HIGH_RISK_MINUTES_ROLL3 = 30.0` | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| AVAIL-T-02 | `_MEDIUM_RISK_MINUTES_ROLL3 = 60.0` | EVALUATION-DEFERRED | Review in 2026/27 |
| AVAIL-T-03 | `_DIVERGENCE_THRESHOLD = 20.0` | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| CAPT-T-01 | `_MIN_MINUTES_ROLL3 = 45.0` | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| VAL-T-01 | `_MIN_MINUTES_ROLL5 = 30.0` (value) | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| TRANS-T-01 | `_MIN_MINUTES_ROLL5 = 30.0` (transfers) | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| FIX-T-01 | `_MIN_MINUTES_ROLL5 = 30.0` (fixtures) | EVALUATION-DEFERRED | Calibrate in 2026/27 |
| SCORE-T-01 | `MIN_RHO = 0.15` | RESOLVED | Removed Phase 8 (G-OPS-02) |
| REG-T-01 | `MINUTES_THRESHOLD = 60` | EVALUATION-DEFERRED | Review in 2026/27 |
| REG-T-02 | `HAUL_THRESHOLD_PTS = 12` | EVALUATION-DEFERRED | Review in 2026/27 |
| REG-T-03 | `HAUL_DROP_MATERIAL = 0.20` | EVALUATION-DEFERRED | Review in 2026/27 |

*This registry must be updated when any threshold value changes or its classification is revised. All EVALUATION-DEFERRED items carry forward to the 2026/27 calibration program.*
