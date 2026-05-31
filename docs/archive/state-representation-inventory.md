# State Representation Inventory

**Status:** ACTIVE  
**Issued:** 2026-05-27  
**Authority:** Operational Convergence Plan Phase 3 (§Phase 3 — Representation Inventory Lock)  
**Reference:** [docs/governance/operational-convergence-plan.md](operational-convergence-plan.md)

---

## Purpose

This document declares the complete, approved set of derived rolling columns that the STATE layer (`dal/state/player_gameweek_state.py`) is authorised to produce. It establishes the clean STATE baseline that SYNTH-01 (Phase 5) will operate on.

**Any addition to this set requires:**
1. A governance decision recorded in this document with a gate reference.
2. The column added to `_GOVERNED_ROLLING_COLS` in `dal/state/player_gameweek_state.py`.
3. A `_COLUMN_META` entry with all four required keys (`scope`, `causality`, `behavioral_reason`, `source_gate_decisions`).

**Removal of a column from this inventory requires** a rejection-basis reference (lens gate ID or EDA finding) and must be reflected in `_GOVERNED_ROLLING_COLS` and `_COLUMN_META`.

---

## Governance Status Vocabulary

| Status | Meaning |
|--------|---------|
| `candidate` | Signal passed the lens study gate (CI excludes zero, clears naive baseline at ≥ 1 position). Eligible for SYNTH-01 evaluation. |
| `candidate (scope-restricted)` | Candidate at the specified position subset only. Use outside that scope is prohibited. |
| `provisional — availability domain only` | Retained for operational availability classification; 30-minute threshold PROVISIONAL-EDITORIAL (STATE-T-01); must not feed form, value, or captain scoring. |

---

## Approved STATE Rolling Columns

| Column | Governance Status | Evidence |
|--------|-------------------|----------|
| `xgi_roll3` | candidate | LENS-FORM FORM-001 (DEF rho=0.123, MID rho=0.144, 3/3 blocks each) |
| `xgi_roll5` | candidate | LENS-FORM FORM-002 (DEF rho=0.113, MID rho=0.157, 3/3 blocks each) |
| `xgc_roll3` | candidate (DEF/GK scope) | LENS-FORM; team defensive context; pooled redundancy (G-EDA8-05) does not rule out positional utility |
| `xgc_roll5` | candidate (DEF/GK scope) | LENS-FORM; team defensive context; same scope restriction as xgc_roll3 |
| `goals_conceded_roll3` | candidate (DEF/GK scope) | LENS-FORM; team defensive context; moderate_shift risk at MID (G-EDA5) |
| `goals_conceded_roll5` | candidate (DEF/GK scope) | LENS-FORM; team defensive context; same caveat as goals_conceded_roll3 |
| `clean_sheets_roll3` | candidate (DEF/GK scope) | G-EDA8-05; surviving defensive signal after xgc redundancy resolved |
| `clean_sheets_roll5` | candidate (DEF/GK scope) | G-EDA8-05; same basis as clean_sheets_roll3 |
| `minutes_roll3` | candidate | LENS-AVAIL AVAIL-001 (MID rho=0.179, 3/3 blocks); availability domain |
| `minutes_roll5` | candidate | LENS-AVAIL AVAIL-002 (MID rho=0.168, 3/3 blocks); availability domain |
| `minutes_roll8` | candidate | LENS-AVAIL AVAIL-003 (DEF rho=0.130, MID rho=0.169, 3/3 blocks each) |
| `minutes_trend` | provisional — availability domain only | Phase 8 calibration required; 30-minute divergence threshold PROVISIONAL-EDITORIAL (STATE-T-01) |
| `fixture_context` | candidate | LENS-FIXTURE-GW; DGW/BGW/SGW classification from spine flags; contemporaneous label |

**Total approved derived columns: 13**

---

## Rejected Columns — Phase 3 Removal Log

The following 16 columns were present in STATE prior to Phase 3 and have been permanently removed. They must not be re-introduced without a new governance decision.

| Column | Rejection Basis | Gate Reference |
|--------|----------------|----------------|
| `points_roll3` | Rolling mean of target variable is analytically circular; uninformative or unstable at all positions | LENS-FORM FORM-004 |
| `points_roll5` | Position-conditional baseline only (MID rho=0.157); not an operational feature | LENS-FORM FORM-005 |
| `xg_roll3` | Absorbed by xgi (partial_rho FWD=0.93, MID=0.74); blocked at DEF/GK | G-EDA6-03 |
| `xg_roll5` | Same as xg_roll3 | G-EDA6-03 |
| `goals_scored_roll3` | Rolling mean destroys episodic burst structure; uninformative at all positions | LENS-FORM FORM-003 |
| `goals_scored_roll5` | Longer window further dilutes rare haul events | LENS-FORM FORM-003 |
| `assists_roll3` | No assists variant clears naive baseline (MID rho=0.051 vs naive 0.140) | G-EDA8-07, G-EDA8-08, G-EDA8-09 |
| `assists_roll5` | Same pattern as roll3 (MID rho=0.062, FWD rho=0.092 — both fail naive baseline) | G-EDA8-07, G-EDA8-08, G-EDA8-09 |
| `saves_roll3` | Uninformative at GKP (rho=−0.029); REJECTED-SEMANTIC at outfield (structural zero) | G-EDA8-01, G-EDA2-03 |
| `saves_roll5` | Same basis as saves_roll3; Layer 1 failure at GKP | G-EDA8-02 |
| `penalties_saved_roll3` | 99.7% zero-rate across 2,512 GKP player-GW records; analytically meaningless | G-EDA8-06 |
| `penalties_saved_roll5` | Same basis as penalties_saved_roll3; structural sparsity | G-EDA8-06 |
| `bonus_roll3` | Target leakage: bonus is a direct component of total_points (DEF/GK rho=0.54) | G-EDA7-06 |
| `bonus_roll5` | Same basis as bonus_roll3; target leakage | G-EDA7-06 |
| `bps_roll3` | Target leakage: bps is input to bonus allocation → total_points (GK rho=0.91) | G-EDA7-06 |
| `bps_roll5` | Same basis as bps_roll3; indirect target leakage | G-EDA7-06 |

---

## Enforcement

The approved set is enforced at build time by the governance assertion in `build_player_gameweek_state()`:

```python
_produced = set(df.columns) - set(spine.columns)
if _produced != _GOVERNED_ROLLING_COLS:
    raise RuntimeError(...)
```

The test suite asserts each of the 16 rejected columns is individually absent (`tests/test_state_architecture.py::test_each_rejected_column_individually_absent`) and that the total derived column count equals 13 (`test_derived_column_count_is_13`).

---

## Consistency Audit — Phase 4 Findings

**Audit date:** 2026-05-27  
**Authority:** Operational Convergence Plan Phase 4 §4.4

### GAP: STATE-INVENTORY-EVIDENCE-01 — Stale rho values in Evidence column

**Status:** Documented gap. Does not affect column set correctness.  
**Resolution phase:** Phase 5 (Signal Traceability Matrix will supersede this inventory's Evidence column)

The Evidence column in the Approved STATE Rolling Columns table contains rho values from an earlier EDA run that pre-date the final lens study runs. The column **sets** are correct and match `_GOVERNED_ROLLING_COLS` exactly (13 columns, identical members). Only the evidence rho annotations are stale:

| Column | Inventory Evidence (stale) | evaluation_metadata.yaml (authoritative) |
|--------|---------------------------|------------------------------------------|
| `minutes_roll3` | MID rho=0.179 | AVAIL-001 MID rho=0.232 |
| `minutes_roll5` | MID rho=0.168 | AVAIL-002 MID rho=0.227 |
| `minutes_roll8` | DEF rho=0.130, MID rho=0.169 | AVAIL-003 DEF rho=0.219, MID rho=0.222 |

**Source of truth:** `signals/evaluation/evaluation_metadata.yaml`  
**Impact:** None on governance enforcement (column sets are correct). Readers consulting this document for rho evidence should use `evaluation_metadata.yaml` directly.  
**Resolution:** Phase 5 will produce `docs/governance/signal-traceability-matrix.md` as the unified signal evidence document. This inventory's Evidence column will be superseded by that artifact and need not be corrected here.

### Other audit results (Phase 4 §4.4)

| Check | Result |
|-------|--------|
| Column set: inventory ↔ `_GOVERNED_ROLLING_COLS` | ✅ Consistent — 13 columns, sets identical |
| `evaluation_metadata.yaml` ↔ `synth01-candidate-set.md` | ✅ All 14 candidates consistent |
| `evaluation_metadata.yaml` ↔ `synth01_candidates.yaml` | ✅ All rho/CI/block values match exactly |
| `threshold-registry.md` ↔ `intelligence/*.py` | ✅ Resolved — 4 stale line references corrected |

---

## Forward Constraint

SYNTH-01 (Phase 7) will evaluate independent signal contribution across all 13 approved columns. Its outputs may produce `APPROVED-*` or `EXCLUDED-*` decisions for each column at each position. Any EXCLUDED decision from SYNTH-01 must be reflected in a subsequent update to this inventory and to `_GOVERNED_ROLLING_COLS`.
