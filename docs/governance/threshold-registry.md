# Threshold Registry

**Status:** ACTIVE  
**Issued:** 2026-05-26  
**Authority:** Operational Convergence Plan Phase 1 (task 1.1)

Every operational threshold — any magic number that gates, filters, or weights a runtime decision — must have an entry here. Classification is required before any threshold may remain in production code.

---

## Classification Vocabulary

| Class | Meaning | Acceptable post-Phase 8? |
|-------|---------|--------------------------|
| `EVALUATION-DERIVED` | Value comes directly from a lens study or SYNTH-01 finding with a documented gate decision | Yes |
| `PROVISIONAL-EDITORIAL` | Value has a plausible semantic justification but no predictive study supports it | Conditionally — must be reviewed in Phase 8 |
| `UNJUSTIFIED` | Value is a round number or gut call with no documented reasoning | No — must be calibrated in Phase 8 or removed |
| `CONTRADICTS-GATE` | Value actively conflicts with a governance gate decision | No — must be resolved in Phase 6 |

---

## Availability Module (`intelligence/availability.py`)

### AVAIL-T-01 — `_HIGH_RISK_MINUTES_ROLL3`
| Field | Value |
|-------|-------|
| **Constant** | `_HIGH_RISK_MINUTES_ROLL3` |
| **Value** | `30.0` |
| **Classification** | `UNJUSTIFIED` |
| **File** | `intelligence/availability.py:38` |
| **Stated rationale** | "less than half a match on average over 3 GWs" |
| **Governance assessment** | Semantic interpretation is plausible but no predictive study establishes that players below this threshold have materially different start rates. The "half a match" framing is intuitive, not empirically calibrated. |
| **Evidence required to promote** | LENS-AVAIL behavioral data: evaluate recall of "failed to start" at multiple thresholds (20, 25, 30, 35, 40 min). Select threshold maximising F1 against the "failed to start" label. |
| **Resolution phase** | Phase 8 |

### AVAIL-T-02 — `_MEDIUM_RISK_MINUTES_ROLL3`
| Field | Value |
|-------|-------|
| **Constant** | `_MEDIUM_RISK_MINUTES_ROLL3` |
| **Value** | `60.0` |
| **Classification** | `PROVISIONAL-EDITORIAL` |
| **File** | `intelligence/availability.py:39` |
| **Stated rationale** | Corresponds to FPL appearance bonus boundary (45+ min = appearance point; 60+ min = full bonus) |
| **Governance assessment** | Semantically grounded in FPL rules. However, the FPL appearance boundary is about points allocation, not predictive of future starts. A player averaging 60 min may still be a rotation risk. |
| **Evidence required to promote** | Same LENS-AVAIL threshold sweep as AVAIL-T-01. If 60.0 maximises F1, reclassify to `EVALUATION-DERIVED`. |
| **Resolution phase** | Phase 8 |

### AVAIL-T-03 — `_DIVERGENCE_THRESHOLD`
| Field | Value |
|-------|-------|
| **Constant** | `_DIVERGENCE_THRESHOLD` |
| **Value** | `20.0` |
| **Classification** | `UNJUSTIFIED` |
| **File** | `intelligence/availability.py:42` |
| **Stated rationale** | None documented. Editorial. |
| **Governance assessment** | No study defines what magnitude of roll3-vs-roll5 divergence is meaningful. 20 minutes is a round number. Players with a 20-minute divergence may or may not be at elevated risk; this has not been tested. |
| **Evidence required to promote** | LENS-AVAIL behavioral data: evaluate precision of "recent drop" flag at divergence thresholds of 10, 15, 20, 25, 30 minutes. Select threshold with best predictive precision against "started fewer games in next 3 GWs". |
| **Resolution phase** | Phase 8 |

---

## Captain Module (`intelligence/captain.py`)

### CAPT-T-01 — `_MIN_MINUTES_ROLL3`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL3` |
| **Value** | `45.0` |
| **Classification** | `UNJUSTIFIED` |
| **File** | `intelligence/captain.py:49` |
| **Stated rationale** | "Players below this threshold are not starting reliably enough" |
| **Governance assessment** | No lens study evaluates captain precision as a function of this eligibility cutoff. The 45-minute value is between the two FPL appearance bonus thresholds, with no documented basis for choosing it over 30, 60, or 75 minutes. |
| **Evidence required to promote** | Historical captain return data: evaluate captain precision (fraction of top-1 picks that returned ≥ haul threshold) at eligibility floors of 30, 45, 60, 75, 90 minutes. Select floor where precision plateaus. |
| **Resolution phase** | Phase 8 |

---

## Value Module (`intelligence/value.py`)

### VAL-T-01 — `_MIN_MINUTES_ROLL5`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL5` |
| **Value** | `30.0` |
| **Classification** | `UNJUSTIFIED` |
| **File** | `intelligence/value.py:51` |
| **Stated rationale** | "bench-warmers inflate value artificially" |
| **Governance assessment** | Correct intuition but no lens study establishes 30 minutes as the threshold below which value scores become unreliable. 30 is a round number. |
| **Evidence required to promote** | Evaluate value score precision (forward return per £ of selected players) at minutes floors of 15, 30, 45, 60 minutes. Select floor where spurious selections (low minutes, high apparent value) are minimised. |
| **Resolution phase** | Phase 8 |

---

## Transfers Module (`intelligence/transfers.py`)

### TRANS-T-01 — `_MIN_MINUTES_ROLL5`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL5` |
| **Value** | `30.0` |
| **Classification** | `UNJUSTIFIED` |
| **File** | `intelligence/transfers.py:51` |
| **Stated rationale** | "transfers need sustained involvement" |
| **Governance assessment** | Same as VAL-T-01. The 30-minute floor is a round number without predictive calibration. |
| **Evidence required to promote** | Same methodology as VAL-T-01. May share calibration evidence. |
| **Resolution phase** | Phase 8 |

---

## Fixtures Module (`intelligence/fixtures.py`)

### FIX-T-01 — `_MIN_MINUTES_ROLL5`
| Field | Value |
|-------|-------|
| **Constant** | `_MIN_MINUTES_ROLL5` |
| **Value** | `30.0` |
| **Classification** | `UNJUSTIFIED` |
| **File** | `intelligence/fixtures.py:49` |
| **Stated rationale** | Implicit — same as VAL-T-01 and TRANS-T-01 |
| **Governance assessment** | Same as VAL-T-01. All three 30-minute floors may be calibrated together. |
| **Evidence required to promote** | Same methodology as VAL-T-01. |
| **Resolution phase** | Phase 8 |

---

## Scoring Gate (`intelligence/scoring/signals.py`)

### SCORE-T-01 — `MIN_RHO`
| Field | Value |
|-------|-------|
| **Constant** | `MIN_RHO` |
| **Value** | `0.15` |
| **Classification** | `CONTRADICTS-GATE` |
| **File** | `intelligence/scoring/signals.py:31` |
| **Stated rationale** | Undocumented; editorial magnitude filter |
| **Governance assessment** | Conflicts with the evaluation gate methodology in `docs/governance/evaluation-gate-criteria.md`, which uses CI exclusion of zero as Gate 1 — not rho magnitude. Three lens-validated signals with `decision_class=informative` have `rho_pooled < 0.15` and are incorrectly caveated: `xgi_roll3 DEF` (rho=0.123), `xgi_roll5 DEF` (rho=0.113), `purchase_price DEF` (rho=0.121). This creates an active contradiction between the lifecycle registry and the scoring gate. |
| **Evidence required to promote** | SYNTH-01 (Phase 5) will determine whether any rho-magnitude floor is warranted. If SYNTH-01 finds that all three affected signals receive `APPROVED-*` decisions, `MIN_RHO` should be removed entirely. If any are excluded, the exclusion must derive from a `G-SYNTH1-*` decision, not rho magnitude. |
| **Resolution phase** | Phase 6 — do not resolve before SYNTH-01 |

---

## Signal Registry (`signals/registry/`)

### REG-T-01 — `MINUTES_THRESHOLD`
| Field | Value |
|-------|-------|
| **Constant** | `MINUTES_THRESHOLD` |
| **Value** | `60` |
| **Classification** | `PROVISIONAL-EDITORIAL` |
| **File** | `signals/registry/population.py:13` |
| **Stated rationale** | FPL appearance bonus boundary (60+ minutes = full appearance bonus) |
| **Governance assessment** | Semantically grounded in FPL rules. The 60-minute boundary is meaningful for participation classification. However, for predictive population robustness purposes, this threshold has not been evaluated empirically. |
| **Evidence required to promote** | Population robustness analysis: evaluate signal-to-noise in `xgi_roll3` associations at 45, 60, and 75 minute participation floors. |
| **Resolution phase** | Phase 8 (low priority — population classification is less operationally critical than scoring thresholds) |

### REG-T-02 — `HAUL_THRESHOLD_PTS`
| Field | Value |
|-------|-------|
| **Constant** | `HAUL_THRESHOLD_PTS` |
| **Value** | `12` |
| **Classification** | `PROVISIONAL-EDITORIAL` |
| **File** | `signals/registry/geometry.py:62` |
| **Stated rationale** | Identifies top-bin concentration in scoring (haul-sensitivity analysis) |
| **Governance assessment** | 12 points is a commonly used FPL "haul" threshold (goal + assist + clean sheet + bonuses ≈ 12-15 pts). The threshold is semantically reasonable but was not derived from a distributional analysis of the total_points distribution. |
| **Evidence required to promote** | Analyse the total_points distribution to identify the natural break point separating the top performance cluster. May use kernel density estimation or percentile analysis. |
| **Resolution phase** | Phase 8 (geometry classification is used in EDA characterisation, not directly in runtime scoring) |

### REG-T-03 — `HAUL_DROP_MATERIAL`
| Field | Value |
|-------|-------|
| **Constant** | `HAUL_DROP_MATERIAL` |
| **Value** | `0.20` |
| **Classification** | `PROVISIONAL-EDITORIAL` |
| **File** | `signals/registry/geometry.py:63` |
| **Stated rationale** | A ≥ 20% rho drop indicates haul sensitivity |
| **Governance assessment** | No sensitivity study defines what magnitude of rho drop constitutes "material" haul concentration effect. 20% is a round editorial choice. |
| **Evidence required to promote** | Bootstrap sensitivity analysis: simulate haul removal and evaluate rho stability distribution. Select threshold where rho drop reliably indicates a haul-structure-dependent signal. |
| **Resolution phase** | Phase 8 |

---

## State Layer (`dal/state/player_gameweek_state.py`)

### STATE-T-01 — `_compute_minutes_trend` divergence threshold
| Field | Value |
|-------|-------|
| **Constant** | Inline literal `30` in `_compute_minutes_trend` |
| **Value** | `30` (minutes) |
| **Classification** | `PROVISIONAL-EDITORIAL` |
| **File** | `dal/state/player_gameweek_state.py` — `_compute_minutes_trend` |
| **Stated rationale** | "30-minute divergence between last-3 and prior-3 GW mean classifies trend as rising or falling" |
| **Governance assessment** | Semantically plausible — a 30-minute swing in average minutes is a meaningful participation shift. However, no predictive study has evaluated whether this threshold maximises recall of actual availability changes. Could equally be 15 or 45 minutes without a principled justification. |
| **Domain restriction** | `minutes_trend` is restricted to the availability domain only (see `_AVAILABILITY_DOMAIN_ONLY`). It must not be consumed by form, captain, or value scoring modules. |
| **Evidence required to promote** | LENS-AVAIL Phase 8 calibration: evaluate recall of "failed to start in next 3 GWs" at divergence thresholds of 15, 20, 25, 30, 35, 45 minutes. Select threshold maximising F1. |
| **Resolution phase** | Phase 8 |

---

## Open Items

| ID | Threshold | Status | Resolution |
|----|-----------|--------|------------|
| STATE-T-01 | `minutes_trend` 30-min divergence (inline) | PROVISIONAL-EDITORIAL | Phase 8 calibration |
| AVAIL-T-01 | `_HIGH_RISK_MINUTES_ROLL3 = 30.0` | UNJUSTIFIED | Phase 8 calibration |
| AVAIL-T-02 | `_MEDIUM_RISK_MINUTES_ROLL3 = 60.0` | PROVISIONAL-EDITORIAL | Phase 8 review |
| AVAIL-T-03 | `_DIVERGENCE_THRESHOLD = 20.0` | UNJUSTIFIED | Phase 8 calibration |
| CAPT-T-01 | `_MIN_MINUTES_ROLL3 = 45.0` | UNJUSTIFIED | Phase 8 calibration |
| VAL-T-01 | `_MIN_MINUTES_ROLL5 = 30.0` (value) | UNJUSTIFIED | Phase 8 calibration |
| TRANS-T-01 | `_MIN_MINUTES_ROLL5 = 30.0` (transfers) | UNJUSTIFIED | Phase 8 calibration |
| FIX-T-01 | `_MIN_MINUTES_ROLL5 = 30.0` (fixtures) | UNJUSTIFIED | Phase 8 calibration |
| SCORE-T-01 | `MIN_RHO = 0.15` | CONTRADICTS-GATE | Phase 6 (post-SYNTH-01) |
| REG-T-01 | `MINUTES_THRESHOLD = 60` | PROVISIONAL-EDITORIAL | Phase 8 review |
| REG-T-02 | `HAUL_THRESHOLD_PTS = 12` | PROVISIONAL-EDITORIAL | Phase 8 review |
| REG-T-03 | `HAUL_DROP_MATERIAL = 0.20` | PROVISIONAL-EDITORIAL | Phase 8 review |

*This registry must be updated when any threshold value changes or its classification is revised.*
