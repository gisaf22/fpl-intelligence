# Signal Traceability Matrix

**Status:** ACTIVE  
**Version:** 1.0  
**Produced:** 2026-05-27  
**Authority:** Operational Convergence Plan Phase 5  
**Machine-readable form:** [signals/registry/signal_traceability.yaml](../../signals/registry/signal_traceability.yaml)

---

## Purpose

This document is the unified cross-layer governance view of every (signal, position) pair in the system. It records what each signal means, what the lens evidence found, what its limitations are, what operational role it plays, and which intelligence modules consume it.

Coverage includes:
- All 15 signals evaluated across 4 lenses in `signals/evaluation/evaluation_metadata.yaml`
- All 8 STATE-governed columns not tracked in evaluation_metadata.yaml (xgc_roll3/5, goals_conceded_roll3/5, clean_sheets_roll3/5, minutes_trend, fixture_context)

**Source of truth for rho values:** `signals/evaluation/evaluation_metadata.yaml`  
**Source of truth for STATE column set:** `docs/governance/state-representation-inventory.md`  
**Source of truth for threshold classifications:** `docs/governance/threshold-registry.md`

---

## Lifecycle and Downstream Status Vocabulary

| Term | Meaning |
|------|---------|
| `candidate` | Passes all lens gates (CI excludes zero + monotonicity + block stability). Eligible for SYNTH-01 and operational use. |
| `excluded` | Failed one or more lens gates; must not be used as scored signal |
| `not_applicable` | Blocked by ontological design rule (e.g., GK excluded from attacking signals) |
| `provisional` | Retained for operational use but threshold/logic not backed by a predictive study |
| `eligible` | Downstream status: may be consumed by intelligence modules |
| `caveated` | Downstream status: may be consumed but carries documented limitation requiring resolution |
| `blocked` | Downstream status: must not be scored at this position |

---

## Evaluated Signal Matrix

### FORM Lens (target: `total_points`, population: minutes ≥ 60)

| Signal | Pos | ID | Lifecycle | Rho | Status | Gate Failure / Key Note |
|--------|-----|----|-----------|-----|--------|-------------------------|
| xgi_roll3 | DEF | FORM-001 | candidate | 0.123 | eligible | MIN_RHO=0.15 conflict (SCORE-T-01) incorrectly caveats — rho clears Gate 1 (CI ≠ 0) |
| xgi_roll3 | MID | FORM-001 | candidate | 0.144 | caveated | Below naive baseline (points_roll5 MID rho=0.158); SYNTH-01 required |
| xgi_roll3 | FWD | FORM-001 | excluded | 0.091 | blocked | G2-FAIL: non-monotonic quintile ordering; haul-concentration destroys rolling mean |
| xgi_roll3 | GK | FORM-001 | not_applicable | — | blocked | G-EDA3-01: ontological exclusion from attacking signals |
| xgi_roll5 | DEF | FORM-002 | candidate | 0.113 | eligible | MIN_RHO=0.15 conflict (SCORE-T-01) incorrectly caveats — rho clears Gate 1 |
| xgi_roll5 | MID | FORM-002 | candidate | 0.157 | caveated | Borderline below naive baseline (rho=0.157 vs 0.158); SYNTH-01 required |
| xgi_roll5 | FWD | FORM-002 | excluded | 0.097 | blocked | G2-FAIL: non-monotonic; same haul-concentration caveat as xgi_roll3 FWD |
| xgi_roll5 | GK | FORM-002 | not_applicable | — | blocked | G-EDA3-01: ontological exclusion |
| goals_scored_roll3 | DEF | FORM-003 | excluded | 0.018 | blocked | G1-FAIL: CI crosses zero at DEF |
| goals_scored_roll3 | MID | FORM-003 | excluded | 0.076 | blocked | G2-FAIL: non-monotonic; rolling mean destroys burst goal structure |
| goals_scored_roll3 | FWD | FORM-003 | excluded | 0.097 | blocked | G2-FAIL: non-monotonic; goals too sparse and bursty for rolling signal |
| goals_scored_roll3 | GK | FORM-003 | not_applicable | — | blocked | G-EDA3-01: ontological exclusion |
| points_roll3 | GK | FORM-004 | excluded | 0.071 | blocked | G-EDA7-02: evaluation circularity; G1-FAIL: CI crosses zero at GK |
| points_roll3 | DEF | FORM-004 | excluded | — | blocked | G-EDA7-02: circularity; G2-FAIL: non-monotonic at DEF |
| points_roll3 | MID | FORM-004 | excluded | — | blocked | G-EDA7-02: circularity; G2-FAIL at MID |
| points_roll3 | FWD | FORM-004 | excluded | — | blocked | G-EDA7-02: circularity; G3-FAIL: 1/3 blocks stable |
| points_roll5 | GK | FORM-005 | excluded | — | blocked | G-EDA7-02: circularity; G1-FAIL at GK |
| points_roll5 | DEF | FORM-005 | excluded | — | blocked | G-EDA7-02: circularity; G2-FAIL at DEF |
| points_roll5 | MID | FORM-005 | excluded | 0.158 | blocked | G-EDA7-02: circularity — passes all gates at MID but role is **evaluation baseline only** |
| points_roll5 | FWD | FORM-005 | excluded | — | blocked | G-EDA7-02: circularity; G2-FAIL at FWD |

> **Note on points_roll5 MID:** rho=0.158 establishes the MID FORM naive evaluation baseline. It is excluded as a synthesis candidate to prevent evaluation circularity contaminating SYNTH-01. Removed from STATE in Phase 3.

---

### AVAIL Lens (target: `played_next_gw`, population: appeared in GW)

> **Note on minutes_roll3:** Also evaluated under FORM as FORM-006 (excluded all positions by G-EDA2-02: minutes blocked as form proxy). AVAIL is the authoritative lens for all minutes signals.

| Signal | Pos | ID | Lifecycle | Rho | Status | Gate Failure / Key Note |
|--------|-----|----|-----------|-----|--------|-------------------------|
| minutes_roll3 | GK | AVAIL-001 | excluded | — | blocked | AVAIL G2-FAIL: Q5-Q1=0.058; insufficient availability separation at GK |
| minutes_roll3 | DEF | AVAIL-001 | excluded | 0.223 | blocked | AVAIL G2-FAIL: non-monotonic (Q5-Q1=0.214); consumed by captain.py (provisional) |
| minutes_roll3 | MID | AVAIL-001 | **candidate** | 0.232 | eligible | Sole MID candidate in availability domain; must not be used as form signal |
| minutes_roll3 | FWD | AVAIL-001 | excluded | 0.186 | blocked | AVAIL G2-FAIL: non-monotonic at FWD; consumed by captain.py (provisional) |
| minutes_roll5 | GK | AVAIL-002 | excluded | — | blocked | AVAIL G2-FAIL: Q5-Q1=0.083; insufficient separation even at 5-GW window |
| minutes_roll5 | DEF | AVAIL-002 | excluded | 0.213 | blocked | AVAIL G2-FAIL: non-monotonic at DEF; used as eligibility floor (provisional) |
| minutes_roll5 | MID | AVAIL-002 | **candidate** | 0.227 | eligible | Candidate; used as eligibility floor in 3 modules |
| minutes_roll5 | FWD | AVAIL-002 | excluded | — | blocked | AVAIL G3-FAIL: 1/3 blocks stable; used as eligibility floor at FWD (provisional) |
| minutes_roll8 | GK | AVAIL-003 | excluded | — | blocked | AVAIL G2-FAIL: non-monotonic even at 8-GW window at GK |
| minutes_roll8 | DEF | AVAIL-003 | **candidate** | 0.219 | eligible | Best availability signal at DEF; not yet wired to any module |
| minutes_roll8 | MID | AVAIL-003 | **candidate** | 0.222 | eligible | Candidate at MID; SYNTH-01 to test independence from roll3/roll5 |
| minutes_roll8 | FWD | AVAIL-003 | excluded | 0.206 | blocked | AVAIL G2-FAIL: non-monotonic at FWD |

---

### MARKET Lens (target: `total_points`, population: minutes ≥ 60)

| Signal | Pos | ID | Lifecycle | Rho | Status | Gate Failure / Key Note |
|--------|-----|----|-----------|-----|--------|-------------------------|
| transfers_in | GK | MARKET-001 | excluded | — | blocked | MARKET G2-FAIL: non-monotonic at GK |
| transfers_in | DEF | MARKET-001 | **candidate** | 0.187 | eligible | HIGH REDUNDANCY with ownership_count DEF (partial rho=0.794); SYNTH-01 to resolve |
| transfers_in | MID | MARKET-001 | **candidate** | 0.190 | eligible | HIGH REDUNDANCY with ownership_count MID (partial rho=0.831); SYNTH-01 to resolve |
| transfers_in | FWD | MARKET-001 | excluded | 0.127 | blocked | MARKET G2-FAIL: non-monotonic at FWD; reflects tier, not form |
| transfers_balance | GK | MARKET-002 | excluded | — | blocked | MARKET G1-FAIL: CI crosses zero at GK |
| transfers_balance | DEF | MARKET-002 | excluded | 0.066 | blocked | MARKET G2-FAIL: Q5-Q1=0.563; insufficient scoring separation |
| transfers_balance | MID | MARKET-002 | excluded | 0.102 | blocked | MARKET G2-FAIL: uninformative at MID |
| transfers_balance | FWD | MARKET-002 | excluded | — | blocked | MARKET G1-FAIL: CI crosses zero at FWD |
| ownership_count | GK | MARKET-003 | excluded | — | blocked | MARKET G2-FAIL: non-monotonic at GK |
| ownership_count | DEF | MARKET-003 | **candidate** | 0.156 | eligible | HIGH REDUNDANCY with transfers_in DEF (partial rho=0.794); SYNTH-01 to resolve |
| ownership_count | MID | MARKET-003 | **candidate** | 0.168 | eligible | HIGH REDUNDANCY with transfers_in MID (partial rho=0.831); SYNTH-01 to resolve |
| ownership_count | FWD | MARKET-003 | excluded | — | blocked | MARKET G3-FAIL: CI excludes zero but only 1/3 blocks stable |
| purchase_price | GK | MARKET-004 | excluded | — | blocked | MARKET G2-FAIL: non-monotonic bin ordering at GK |
| purchase_price | DEF | MARKET-004 | **candidate** | 0.121 | caveated | Borderline temporal stability (2/3 blocks); MIN_RHO conflict (SCORE-T-01) |
| purchase_price | MID | MARKET-004 | excluded | 0.121 | blocked | MARKET G2-FAIL: non-monotonic at MID despite large Q5-Q1 gap |
| purchase_price | FWD | MARKET-004 | **candidate** | 0.155 | caveated | 2/3 block temporal stability; may proxy role seniority |

---

### FIXTURE-GW Lens (target: `total_points`, same-GW, population: minutes ≥ 60)

| Signal | Pos | ID | Lifecycle | Rho | Status | Gate Failure / Key Note |
|--------|-----|----|-----------|-----|--------|-------------------------|
| fdr_avg | GK | FIXTURE-001 | excluded | −0.147 | blocked | G2-FAIL: non-monotonic middle quintiles; reserved for binary moderator role in SYNTH-01 |
| fdr_avg | DEF | FIXTURE-001 | excluded | −0.196 | blocked | G2-FAIL: Q3>Q2 quintile reversal; reserved for binary moderator role |
| fdr_avg | MID | FIXTURE-001 | excluded | −0.159 | blocked | G2-FAIL: non-monotonic; reserved for binary moderator role |
| fdr_avg | FWD | FIXTURE-001 | excluded | −0.092 | blocked | G2-FAIL: fails decision relevance; reserved for binary moderator role |
| was_home | GK | FIXTURE-002 | excluded | — | blocked | G1-FAIL: CI crosses zero |
| was_home | DEF | FIXTURE-002 | excluded | 0.068 | blocked | G2-FAIL: Q5-Q1=−0.145 non-monotonic |
| was_home | MID | FIXTURE-002 | excluded | 0.044 | blocked | G2-FAIL: Q5-Q1=0.044 trivially small |
| was_home | FWD | FIXTURE-002 | excluded | — | blocked | G1-FAIL: CI crosses zero |
| fixture_count | GK | FIXTURE-003 | not_applicable | — | blocked | G-EDA2-01: ontological exclusion from schedule context signals |
| fixture_count | DEF | FIXTURE-003 | excluded | 0.098 | blocked | G2-FAIL: non-monotonic; DGW effect is binary, not graded |
| fixture_count | MID | FIXTURE-003 | excluded | 0.083 | blocked | G2-FAIL: non-monotonic at MID; same conclusion as DEF |
| fixture_count | FWD | FIXTURE-003 | not_applicable | — | blocked | G-EDA2-01: ontological exclusion |

> **GOVERNANCE INCONSISTENCY — fdr_avg:** `fdr_avg` is excluded at all four positions but is carried as a 20–40% weighted component in `captain.py`, `fixtures.py`, and `transfers.py`. This creates an active conflict between evaluation findings and production scoring. Phase 6 must resolve this — the likely resolution is replacing the continuous FDR weight with a binary DGW/fixture-tier moderator derived from SYNTH-01 findings.

---

## STATE-Governed Extension

The following columns are in `_GOVERNED_ROLLING_COLS` but were not evaluated via a named lens study. They were approved via LENS-FORM team context studies (EDA findings) or editorial governance decisions. Individual rho values reside in `studies/runs/` CSVs rather than `evaluation_metadata.yaml`.

### Defensive Signals (DEF/GK scope only)

| Signal | Pos | Lifecycle | Status | Redundancy | Operational Role | Consumer |
|--------|-----|-----------|--------|------------|-----------------|---------|
| xgc_roll3 | DEF | candidate | eligible | G-EDA8-05: pooled redundancy with defensive signal group | defensive | — (not wired) |
| xgc_roll3 | GK | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| xgc_roll5 | DEF | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| xgc_roll5 | GK | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| goals_conceded_roll3 | DEF | candidate | eligible | G-EDA8-05; moderate_shift risk at MID | defensive | — (not wired) |
| goals_conceded_roll3 | GK | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| goals_conceded_roll5 | DEF | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| goals_conceded_roll5 | GK | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll3 | DEF | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll3 | GK | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll5 | DEF | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll5 | GK | candidate | eligible | G-EDA8-05 | defensive | — (not wired) |

> All 12 defensive signal entries are **GOVERNED BUT NOT WIRED**: present in `_GOVERNED_ROLLING_COLS` but not consumed by any intelligence module. Phase 6 must wire the subset surviving SYNTH-01 to relevant modules. G-EDA8-05 documents pooled redundancy across the defensive signal group; SYNTH-01 will determine which individual signals add independent defensive contribution.

### Availability Classification Signal

| Signal | Pos | Lifecycle | Status | Threshold | Consumer |
|--------|-----|-----------|--------|-----------|---------|
| minutes_trend | DEF | provisional | caveated | STATE-T-01 (30-min divergence) | `availability.py` |
| minutes_trend | MID | provisional | caveated | STATE-T-01, AVAIL-T-03 | `availability.py` |
| minutes_trend | FWD | provisional | caveated | STATE-T-01, AVAIL-T-03 | `availability.py` |
| minutes_trend | GK | provisional | caveated | STATE-T-01; GK playing time near-constant | `availability.py` |

> `minutes_trend` is restricted to the **availability domain only** (`_AVAILABILITY_DOMAIN_ONLY` in `player_gameweek_state.py`). It must not feed form, captain, or value scoring. The 30-minute divergence threshold (STATE-T-01) is `PROVISIONAL-EDITORIAL`; Phase 8 calibration required.

### Fixture Classification Signal

| Signal | Pos | Lifecycle | Status | Note |
|--------|-----|-----------|--------|------|
| fixture_context | DEF | candidate | eligible | Contemporaneous label: DGW \| BGW \| SGW |
| fixture_context | MID | candidate | eligible | Contemporaneous label |
| fixture_context | FWD | candidate | eligible | Contemporaneous label |
| fixture_context | GK | candidate | eligible | Contemporaneous label |

> `fixture_context` is **GOVERNED BUT NOT WIRED**: `fixtures.py` reads `is_dgw` from the spine directly rather than consuming `fixture_context` from STATE. Phase 6 must migrate `fixtures.py` to use `fixture_context` for consistent governance. The column is a contemporaneous label (same-GW classification), valid for conditional scoring adjustment only — not an independent predictive lag-1 feature.

---

## Consumer Module Map

This section documents, for each intelligence module, which signals it currently consumes, at which positions, and the governance status of each consumption relationship.

### `intelligence/captain.py`

**Purpose:** Rank players for captaincy selection each gameweek.

| Signal | Weight / Role | Positions | Governance Status | Issue |
|--------|---------------|-----------|------------------|-------|
| xgi_roll5 | form_score (35%) | DEF, MID, FWD, GK | DEF/MID: candidate; FWD: **excluded** | SCOPE VIOLATION at FWD |
| xgi_roll3 | involvement_score (30%) | DEF, MID, FWD, GK | DEF/MID: candidate; FWD: **excluded** | SCOPE VIOLATION at FWD |
| fdr_avg | fixture_score (20%) | all | excluded at all positions | GOVERNANCE INCONSISTENCY |
| minutes_roll3 | minutes_score (15%) + eligibility filter | all | DEF/FWD: **excluded**; MID: candidate | Eligibility use at DEF/FWD is provisional |

**Threshold dependencies:** CAPT-T-01 (`_MIN_MINUTES_ROLL3 = 45.0` — `UNJUSTIFIED`), SCORE-T-01

**Key issues:**
- `fdr_avg` carries 20% weight despite being excluded at all positions. Phase 6 must replace with binary fixture moderator.
- xgi_roll3 and xgi_roll5 consumed at FWD despite exclusion. Phase 6 must add positional scope filter.
- `minutes_roll3` eligibility gate at DEF and FWD: signal excluded at those positions from AVAIL study; gate is provisionally correct but unvalidated.

---

### `intelligence/value.py`

**Purpose:** Score player value relative to price (efficiency-adjusted form).

| Signal | Weight / Role | Positions | Governance Status | Issue |
|--------|---------------|-----------|------------------|-------|
| xgi_roll5 | efficiency_score numerator (50%) | DEF, MID, FWD | DEF/MID: candidate; FWD: **excluded** | SCOPE VIOLATION at FWD |
| purchase_price | efficiency_score denominator (50%) | all | DEF/FWD: candidate (2/3 blocks); MID: **excluded** | Denominator role differs from scored signal; MID exclusion documented |
| xgi_roll3 | form_score (30%), consistency_score base (20%) | DEF, MID, FWD | DEF/MID: candidate; FWD: **excluded** | SCOPE VIOLATION at FWD |
| minutes_roll5 | eligibility filter | all | DEF/FWD: **excluded**; MID: candidate | Eligibility use at DEF/FWD is provisional |

**Threshold dependencies:** VAL-T-01 (`_MIN_MINUTES_ROLL5 = 30.0` — `UNJUSTIFIED`), SCORE-T-01

**Key issues:**
- xgi_roll3 and xgi_roll5 consumed at FWD despite exclusion. Phase 6 positional guard required.
- `purchase_price` role as efficiency denominator is semantically distinct from using it as a scored signal; MID exclusion in the MARKET lens study concerns its direct signal use, not its role as a price normalizer. The distinction should be documented explicitly in Phase 6.

---

### `intelligence/fixtures.py`

**Purpose:** Identify players with the most favourable upcoming fixtures.

| Signal | Weight / Role | Positions | Governance Status | Issue |
|--------|---------------|-----------|------------------|-------|
| fdr_avg | fdr_opportunity_score (40%) | all | excluded at all positions | GOVERNANCE INCONSISTENCY |
| is_dgw (spine) | dgw_bonus_score (25%) | all | Not a STATE column — read from spine | Governance misalignment with `fixture_context` |
| goals_scored (team) | team_attack_score (35%) | all | Not a STATE column — raw aggregation | No lens evaluation for team-level goal rate |
| minutes_roll5 | eligibility filter | all | DEF/FWD: **excluded**; MID: candidate | Eligibility at DEF/FWD is provisional |

**Threshold dependencies:** FIX-T-01 (`_MIN_MINUTES_ROLL5 = 30.0` — `UNJUSTIFIED`)

**Key issues:**
- `fdr_avg` at 40% weight is the most significant governance inconsistency in the system. Phase 6 must replace.
- `is_dgw` is read directly from the spine rather than the governed `fixture_context` STATE column. Phase 6 must migrate to `fixture_context`.
- Team-level `goals_scored` aggregation is uncharted territory — no lens study evaluates team goal rate as a signal; Phase 6 should flag for evaluation.

---

### `intelligence/availability.py`

**Purpose:** Classify player availability risk based on recent minutes patterns.

| Signal | Weight / Role | Positions | Governance Status | Issue |
|--------|---------------|-----------|------------------|-------|
| minutes_roll3 | risk classification (HIGH/MEDIUM/OK thresholds) | all | GK/DEF/FWD: **excluded**; MID: candidate | Classification at non-MID positions is provisional |
| minutes_roll5 | divergence calculation vs roll3 | all | GK/DEF/FWD: **excluded**; MID: candidate | Divergence use at non-MID is provisional |
| minutes_trend | falling_trend_flag | all | provisional (all positions) | 30-min divergence threshold PROVISIONAL-EDITORIAL |

**Threshold dependencies:** AVAIL-T-01 (`_HIGH_RISK_MINUTES_ROLL3 = 30.0` — `UNJUSTIFIED`), AVAIL-T-02 (`_MEDIUM_RISK_MINUTES_ROLL3 = 60.0` — `PROVISIONAL-EDITORIAL`), AVAIL-T-03 (`_DIVERGENCE_THRESHOLD = 20.0` — `UNJUSTIFIED`), STATE-T-01

**Key issues:**
- All three availability thresholds (AVAIL-T-01, AVAIL-T-02, AVAIL-T-03) are unjustified or provisional. Phase 8 calibration is the resolution path.
- `minutes_roll8` DEF (rho=0.219) and MID (rho=0.222) are the best-evidenced availability signals at DEF but are not consumed. Phase 6 must wire them.

---

### `intelligence/transfers.py`

**Purpose:** Identify differential and value transfer opportunities.

| Signal | Weight / Role | Positions | Governance Status | Issue |
|--------|---------------|-----------|------------------|-------|
| xgi_roll3 | recent_form_score (30%), involvement_score (15%) | DEF, MID, FWD | DEF/MID: candidate; FWD: **excluded** | SCOPE VIOLATION at FWD |
| xgi_roll5 | form_momentum_score base (25%) | DEF, MID, FWD | DEF/MID: candidate; FWD: **excluded** | SCOPE VIOLATION at FWD |
| fdr_avg | fixture_score (20%) | all | excluded at all positions | GOVERNANCE INCONSISTENCY |
| minutes_roll5 | eligibility filter (10%) + minutes_stability_score | all | DEF/FWD: **excluded**; MID: candidate | Eligibility at DEF/FWD is provisional |

**Threshold dependencies:** TRANS-T-01 (`_MIN_MINUTES_ROLL5 = 30.0` — `UNJUSTIFIED`)

**Key issues:**
- Same xgi_roll3/roll5 scope violation at FWD as captain.py and value.py. Phase 6 systemic fix.
- `fdr_avg` at 20% weight: same governance inconsistency as captain.py. Phase 6 resolution required.
- `transfers_in` (DEF rho=0.187, MID rho=0.190) and `ownership_count` (DEF rho=0.156, MID rho=0.168) are governed candidates but not consumed by transfers.py. Phase 6 alignment required after SYNTH-01 resolves the HIGH REDUNDANCY pair.

---

### `intelligence/scoring/signals.py`

**Purpose:** Load the signal manifest from the registry CSV and enforce lifecycle governance at scoring time.

| Signal | Role | Governance Status | Issue |
|--------|------|------------------|-------|
| (all governed signals) | Loaded from registry manifest CSV | Enforced by `_assert_governance_compliance()` | Lifecycle gate active |
| MIN_RHO = 0.15 | Editorial magnitude floor on rho | `CONTRADICTS-GATE` (SCORE-T-01) | Incorrectly caveats xgi_roll3 DEF (0.123), xgi_roll5 DEF (0.113), purchase_price DEF (0.121) — all valid Gate 1 passes |

**Threshold dependencies:** SCORE-T-01 (`MIN_RHO = 0.15` — `CONTRADICTS-GATE`)

**Key issues:**
- `MIN_RHO = 0.15` actively contradicts the evaluation gate methodology in `docs/governance/evaluation-gate-criteria.md`. Gate 1 uses CI exclusion of zero, not rho magnitude. Three valid candidates are incorrectly downgraded.
- Resolution is blocked until SYNTH-01 (Phase 5/6): if all three affected signals pass SYNTH-01 with `APPROVED-*` decisions, `MIN_RHO` should be removed entirely.

---

## Governance Gap Summary

| ID | Gap | Affected Modules | Resolution Phase |
|----|-----|-----------------|-----------------|
| GAP-TRACE-01 | xgi_roll3/roll5 consumed at FWD despite exclusion (SCOPE VIOLATION) | captain.py, value.py, transfers.py | Phase 6 |
| GAP-TRACE-02 | fdr_avg carried at 20–40% weight despite excluded at all positions (GOVERNANCE INCONSISTENCY) | captain.py, fixtures.py, transfers.py | Phase 6 |
| GAP-TRACE-03 | minutes_roll8 DEF/MID candidates not wired to any module | availability.py | Phase 6 |
| GAP-TRACE-04 | transfers_in and ownership_count governed candidates not consumed | (none yet) | Phase 6 (post-SYNTH-01) |
| GAP-TRACE-05 | 12 defensive signals (xgc_roll3/5, goals_conceded_roll3/5, clean_sheets_roll3/5) at DEF/GK not wired | (none yet) | Phase 6 (post-SYNTH-01) |
| GAP-TRACE-06 | fixture_context governed candidate not consumed; fixtures.py reads is_dgw from spine directly | fixtures.py | Phase 6 |
| GAP-TRACE-07 | SCORE-T-01 (MIN_RHO=0.15) CONTRADICTS-GATE — incorrectly caveats 3 valid candidates | scoring/signals.py | Phase 6 (post-SYNTH-01) |
| GAP-TRACE-08 | minutes_roll3/roll5 eligibility use at DEF/FWD is provisional (signals excluded at those positions) | captain.py, value.py, fixtures.py, transfers.py | Phase 8 calibration |

---

## Candidate Set Summary

**14 governance candidates entering SYNTH-01:**

| # | Signal | Position | Rho | Lens | Operational Role |
|---|--------|----------|-----|------|-----------------|
| 1 | xgi_roll3 | DEF | 0.123 | FORM | form |
| 2 | xgi_roll3 | MID | 0.144 | FORM | form |
| 3 | xgi_roll5 | DEF | 0.113 | FORM | form |
| 4 | xgi_roll5 | MID | 0.157 | FORM | form |
| 5 | minutes_roll3 | MID | 0.232 | AVAIL | availability |
| 6 | minutes_roll5 | MID | 0.227 | AVAIL | availability |
| 7 | minutes_roll8 | DEF | 0.219 | AVAIL | availability |
| 8 | minutes_roll8 | MID | 0.222 | AVAIL | availability |
| 9 | transfers_in | DEF | 0.187 | MARKET | market |
| 10 | transfers_in | MID | 0.190 | MARKET | market |
| 11 | ownership_count | DEF | 0.156 | MARKET | market |
| 12 | ownership_count | MID | 0.168 | MARKET | market |
| 13 | purchase_price | DEF | 0.121 | MARKET | market |
| 14 | purchase_price | FWD | 0.155 | MARKET | market |

Plus 12 STATE-only defensive candidates (xgc_roll3/5, goals_conceded_roll3/5, clean_sheets_roll3/5 at DEF/GK) and 4 fixture_context candidates (all positions) awaiting SYNTH-01 evaluation.

---

## Forward Constraints

1. **SYNTH-01 (Phase 5)** will evaluate independent signal contribution across the 14 evaluation-metadata candidates. Any `EXCLUDED-*` decision from SYNTH-01 must be reflected in an update to this matrix, `state-representation-inventory.md`, and `_GOVERNED_ROLLING_COLS`.
2. **Phase 6 alignment** must address all 8 governance gaps listed above before any new signals are added to production scoring.
3. **Phase 8 calibration** must resolve all `UNJUSTIFIED` and `PROVISIONAL-EDITORIAL` thresholds. No `UNJUSTIFIED` threshold may remain in production code after Phase 8.
4. This document is superseded by updates from SYNTH-01 gate decisions. Each SYNTH-01 decision should produce a corresponding update to `signal_traceability.yaml` and this document.
