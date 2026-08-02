# Signal Traceability Matrix

**Status:** ACTIVE  
**Version:** 1.1  
**Produced:** 2026-05-27  
**Updated:** 2026-05-31 — independent review corrections: GAP-TRACE-02/-03/-06/-07 resolved, consumer module maps aligned to HEAD, eda_candidate vocabulary added, xgi_roll3×MID SYNTH-01 violation documented  
**Authority:** Operational Convergence Plan Phase 5  
**Machine-readable form:** [signals/characterisation/signal_traceability.yaml](../../signals/characterisation/signal_traceability.yaml)

---

## Purpose

This document is the unified cross-layer governance view of every (signal, position) pair in the system. It records what each signal means, what the lens evidence found, what its limitations are, what operational role it plays, and which intelligence modules consume it.

Coverage includes:
- All 15 signals evaluated across 4 lenses in `signals/governance/evaluation_metadata.yaml`
- All 8 STATE-governed columns not tracked in evaluation_metadata.yaml (xgc_roll3/5, goals_conceded_roll3/5, clean_sheets_roll3/5, minutes_trend, fixture_context)

**Source of truth for rho values:** `signals/governance/evaluation_metadata.yaml`  
**Source of truth for STATE column set:** `docs/governance/state-representation-inventory.md`  
**Source of truth for threshold classifications:** `docs/governance/threshold-registry.md`

---

## Lifecycle and Downstream Status Vocabulary

| Term | Meaning |
|------|---------|
| `candidate` | Passes all lens gates (CI excludes zero + monotonicity + block stability). Eligible for SYNTH-01 and operational use. |
| `eda_candidate` | Shortlisted by EDA (G-EDA8-05 or equivalent) but has NOT passed a named lens study. Must not enter SYNTH-01 without lens gate decisions. Distinguished from `candidate` to prevent premature synthesis entry. |
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
| xgi_roll3 | DEF | FORM-001 | candidate | 0.123 | eligible | Clears Gate 1 (CI ≠ 0); former MIN_RHO=0.15 caveat (SCORE-T-01) RESOLVED — MIN_RHO removed (G-OPS-02) |
| xgi_roll3 | MID | FORM-001 | candidate | 0.144 | caveated | Below naive baseline (points_roll5 MID rho=0.158); SYNTH-01 required |
| xgi_roll3 | FWD | FORM-001 | excluded | 0.091 | blocked | G2-FAIL: non-monotonic quintile ordering; haul-concentration destroys rolling mean |
| xgi_roll3 | GK | FORM-001 | not_applicable | — | blocked | G-EDA3-01: ontological exclusion from attacking signals |
| xgi_roll5 | DEF | FORM-002 | candidate | 0.113 | eligible | Clears Gate 1 (CI ≠ 0); former MIN_RHO=0.15 caveat (SCORE-T-01) RESOLVED — MIN_RHO removed (G-OPS-02) |
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
| purchase_price | DEF | MARKET-004 | **candidate** | 0.121 | caveated | Borderline temporal stability (2/3 blocks); former MIN_RHO caveat (SCORE-T-01) RESOLVED |
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

> **fdr_avg governance:** `fdr_avg` is excluded at all four positions and is **not scored** by any serve
> module. As of the serve↔model integration (2026-08-01) no serve module scores fixture context at all —
> captain/value/transfers/fixtures rank by the model forecast, where fixture difficulty enters through the
> gated `fdr` term (ADR-011). This supersedes the earlier resolution (GAP-TRACE-02, where the composites
> used a `fixture_context` binary DGW indicator in place of `fdr_avg`).

---

## STATE-Governed Extension

The following columns are in `_GOVERNED_ROLLING_COLS` but were not evaluated via a named lens study. They were approved via LENS-FORM team context studies (EDA findings) or editorial governance decisions. Individual rho values reside in `research/runs/` CSVs rather than `evaluation_metadata.yaml`.

### Defensive Signals (DEF/GK scope only)

| Signal | Pos | Lifecycle | Status | Redundancy | Operational Role | Consumer |
|--------|-----|-----------|--------|------------|-----------------|---------|
| xgc_roll3 | DEF | eda_candidate | eligible | G-EDA8-05: pooled redundancy with defensive signal group | defensive | — (not wired) |
| xgc_roll3 | GK | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| xgc_roll5 | DEF | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| xgc_roll5 | GK | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| goals_conceded_roll3 | DEF | eda_candidate | eligible | G-EDA8-05; moderate_shift risk at MID | defensive | — (not wired) |
| goals_conceded_roll3 | GK | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| goals_conceded_roll5 | DEF | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| goals_conceded_roll5 | GK | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll3 | DEF | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll3 | GK | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll5 | DEF | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |
| clean_sheets_roll5 | GK | eda_candidate | eligible | G-EDA8-05 | defensive | — (not wired) |

> All 12 defensive signal entries are `eda_candidate`: shortlisted by EDA (G-EDA8-05) but no named lens study completed. They are not wired to any intelligence module and must not enter SYNTH-01 without lens gate decisions. G-EDA8-05 documents pooled redundancy across the defensive signal group; a defensive lens study must precede SYNTH-01 consideration.

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

> `fixture_context` is a **governed contemporaneous label** (same-GW DGW/BGW/SGW classification), valid for
> conditional scoring adjustment only — not an independent predictive lag-1 feature. It was wired into the
> serve composites (GAP-TRACE-06, resolved 2026-05-31); those composites are now retired (ADR-011,
> 2026-08-01) and no serve module consumes it — fixture context is carried by the model forecast instead.

---

## Consumer Module Map

This section documents, for each serve module, which signals it consumes and the governance status of
each consumption relationship.

> **RETIRED (2026-08-01) — captain / value / transfers / fixtures composite consumption.** These four
> modules no longer consume weighted signal composites: they rank by the model forecast
> (`model.predictions.assemble_forecast`) — captain by `p_haul`/`p90`, value by
> `e_points_uncond / purchase_price`, transfers by `e_points_uncond`; `serve/fixtures.py` is deleted
> (transfers subsumes it). Their signal→weight consumption tables (and the associated FWD/MID xgi and
> fdr scope-guards) are removed here — that per-position governance relocated **upstream** to the model
> term gates. The signal *evidence* rows earlier in this doc, and the availability + signal_selector
> tables below, are unchanged. See [ADR-011](../decisions/011-model-forecast-supersedes-composites.md)
> and `docs/serve-model-integration.md`. The retained per-module eligibility thresholds are CAPT-T-01
> (captain), VAL-T-01 (value), TRANS-T-01 (transfers).

### `serve/availability.py`

**Purpose:** Classify player availability risk based on recent minutes patterns. (Descriptive warning
layer — not a forecast consumer; unchanged by the serve↔model integration.)

| Signal | Weight / Role | Positions | Governance Status | Issue |
|--------|---------------|-----------|------------------|-------|
| minutes_roll3 | HIGH/MEDIUM risk thresholds | all | GK/DEF/FWD: **excluded** (AVAIL G2-FAIL); MID: candidate | Classification at non-MID is provisional (AVAIL-T-01/T-02) |
| minutes_roll5 | divergence calculation vs roll3 | all | GK/DEF/FWD: **excluded** (AVAIL G2-FAIL); MID: candidate | Divergence use at non-MID is provisional (AVAIL-T-03) |
| minutes_trend | falling_trend_flag | all | provisional (all positions) | 30-min divergence threshold PROVISIONAL-EDITORIAL (STATE-T-01) |
| minutes_roll8 | long_horizon_flag (DEF/MID only) | DEF, MID | DEF: candidate (rho=0.219); MID: candidate (rho=0.222) | WIRED — positional guard enforced; GAP-TRACE-03 resolved |

**Threshold dependencies:** AVAIL-T-01 (`_HIGH_RISK_MINUTES_ROLL3 = 30.0` — `UNJUSTIFIED`), AVAIL-T-02 (`_MEDIUM_RISK_MINUTES_ROLL3 = 60.0` — `PROVISIONAL-EDITORIAL`), AVAIL-T-03 (`_DIVERGENCE_THRESHOLD = 20.0` — `UNJUSTIFIED`), STATE-T-01

**Key issues:**
- All three availability thresholds (AVAIL-T-01, AVAIL-T-02, AVAIL-T-03) are unjustified or provisional. Phase 8 calibration is the resolution path.
- `minutes_roll8` DEF (rho=0.219) and MID (rho=0.222) wired via `long_horizon_flag` with positional guard (`_MINUTES_ROLL8_POSITIONS = frozenset({"DEF", "MID"})`). GAP-TRACE-03 resolved.

---

### `serve/scoring/signal_selector.py`

**Purpose:** Load the signal manifest from the registry and enforce lifecycle governance at scoring time.

| Signal | Role | Governance Status | Issue |
|--------|------|------------------|-------|
| (all governed signals) | Loaded from registry manifest | Enforced by `_assert_governance_compliance()` | Lifecycle gate active |
| MIN_RHO = 0.15 | Editorial magnitude floor on rho | `RESOLVED` (SCORE-T-01, G-OPS-02) | Removed in Phase 8. All three affected signals (xgi_roll3 DEF, xgi_roll5 DEF, purchase_price DEF) passed SYNTH-01 with APPROVED-* decisions. |

**Threshold dependencies:** SCORE-T-01 (`RESOLVED` — MIN_RHO removed in Phase 8, G-OPS-02)

**Key issues:**
- No active key issues. SCORE-T-01 resolved. MIN_RHO constant removed from signal_selector.py.

---

## Governance Gap Summary

> **Composite-consumption gaps superseded (2026-08-01, ADR-011).** The gaps below about xgi/fdr/minutes
> consumption in captain/value/transfers/fixtures — both the RESOLVED scope-guards (GAP-TRACE-01, -02, -06,
> -09) and the OPEN Phase-6/8 deferrals (GAP-TRACE-04, -05, -08) — are moot: those composites are retired
> and the modules rank by the model forecast, with per-position validity enforced by the model term gates.
> Rows kept as historical record. GAP-TRACE-03 (availability `minutes_roll8` wiring) and GAP-TRACE-07
> (the report-pipeline `MIN_RHO`) are unaffected.

| ID | Gap | Affected Modules | Resolution Phase |
|----|-----|-----------------|-----------------|
| GAP-TRACE-01 | xgi_roll3/roll5 consumed at FWD despite exclusion (SCOPE VIOLATION) | captain.py, value.py, transfers.py | **RESOLVED 2026-05-31** — FWD zeroing guard implemented in all three modules |
| GAP-TRACE-02 | fdr_avg carried at 20–40% weight despite excluded at all positions | captain.py, fixtures.py, transfers.py | **RESOLVED 2026-05-31** — fdr_avg not scored in any module; fixture_context binary DGW used instead |
| GAP-TRACE-03 | minutes_roll8 DEF/MID candidates not wired to any module | availability.py | **RESOLVED 2026-05-31** — wired via `long_horizon_flag` with `_MINUTES_ROLL8_POSITIONS` positional guard |
| GAP-TRACE-04 | transfers_in and ownership_count governed candidates not consumed | (none yet) | Phase 6 (post-SYNTH-01) |
| GAP-TRACE-05 | 12 defensive signals (xgc_roll3/5, goals_conceded_roll3/5, clean_sheets_roll3/5) at DEF/GK not wired | (none yet) | Phase 6 (post-SYNTH-01) |
| GAP-TRACE-06 | fixture_context governed candidate not consumed; modules read is_dgw from spine directly | fixtures.py, captain.py, transfers.py | **RESOLVED 2026-05-31** — fixture_context consumed in all three modules |
| GAP-TRACE-07 | SCORE-T-01 (MIN_RHO=0.15) CONTRADICTS-GATE — incorrectly caveats 3 valid candidates | scoring/signal_selector.py | **RESOLVED** (Phase 8, G-OPS-02) — MIN_RHO removed; xgi_roll3 DEF, xgi_roll5 DEF, purchase_price DEF all passed SYNTH-01 with APPROVED-* decisions |
| GAP-TRACE-08 | minutes_roll3/roll5 eligibility use at DEF/FWD is provisional (signals excluded at those positions) | captain.py, value.py, fixtures.py, transfers.py | Phase 8 calibration |
| GAP-TRACE-09 | xgi_roll3 consumed at MID in captain.py, value.py, transfers.py despite SYNTH-01 G-SYNTH1-07 EXCLUDED-REDUNDANT | captain.py, value.py, transfers.py | **RESOLVED 2026-06-01** — MID zeroing guard implemented in all three modules; consistency/momentum neutralised at MID |

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

1. **SYNTH-01 decisions** must be reflected in updates to this matrix, `state-representation-inventory.md`, and `_GOVERNED_ROLLING_COLS`. Any `EXCLUDED-*` decision from SYNTH-01 requires a corresponding consumer module guard within the same phase.
2. **Phase 6 alignment** must address all open governance gaps (GAP-TRACE-04, -05, -07, -08) before any new signals are added to production scoring. GAP-TRACE-01/-02/-03/-06/-09 are resolved.
4. **Phase 8 calibration** must resolve all `UNJUSTIFIED` and `PROVISIONAL-EDITORIAL` thresholds. No `UNJUSTIFIED` threshold may remain in production code after Phase 8.
5. **`eda_candidate` signals** (12 defensive signals) must not enter SYNTH-01 without first completing a named defensive lens study with 3-gate evaluations. The `eda_candidate` state is a hard gate.
6. **PENDING-EVAL entries** (consistency_score, form_momentum_score, team_goals_roll5) must be tracked in `docs/governance/pending-evaluation-register.md` and resolved before any weight increases or new module dependencies are added.
