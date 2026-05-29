# REPO-CONS-01 — Repository Consolidation & Reference Stabilization

**Program:** Operational Convergence Plan — Consolidation Pass  
**Issued:** 2026-05-27  
**Status:** COMPLETE — 2026-05-27  
**Scope:** Repository surface only — zero analytical, governance, or schema changes  
**Invariant baseline:** 879 tests passed, 2 skipped (must hold throughout)

---

## Objective

After a 9-phase operational convergence program, the repository contains stale transitional
narrative, superseded working documents, convergence-era inline annotations, historical
phase-oriented comments, and mixed authoritative vs historical artifacts.

This pass improves repository usability, discoverability, reference authority clarity,
and cognitive navigation without altering analytical semantics or governance architecture.

**Core principle:** Historical process commentary disappears from runtime surfaces.
Current operational semantics and non-obvious governance constraints remain.

---

## Comment Retention Policy

**REMOVE — historical process narrative:**
- `# GAP-TRACE-XX (fixed/resolved/wired):` lines
- `# Phase N governance changes (date):` section headers and bullet lists
- `# PROVISIONAL-EDITORIAL — no analytical derivation exists`
- `# Resolution: Phase 7 SYNTH-01 will replace...`
- `# temporary until`, `# blocked until`, `# deferred to Phase N`
- `# Note: X removed in Phase N (GAP-TRACE-XX)`

**KEEP — current operational semantics:**
- Scope restrictions: `# xgi excluded at FWD: FORM-001/002 G2-FAIL`
- Positional constraints: `# minutes_roll8: DEF/MID only (AVAIL-003)`
- Threshold traceability: `# threshold not evaluation-derived — see threshold-registry.md §CAPT-T-01`
- Non-obvious behavioral constraints a reader would need to understand runtime behavior

**Rule:** When in doubt, keep. The risk of silently losing a constraint is higher than the
risk of leaving a slightly verbose comment.

---

## Archival Policy

Files move to `docs/archive/` unchanged. `docs/archive/README.md` lists every archived file
with its supersession. `docs/navigation-map.md` gets an "Archived" section.

ADRs are never archived — they are permanent decision records.

---

## Test Retention Policy

**Never touch:** Tests that enforce current system invariants and would catch real regressions.  
**Read before removing:** Tests that may be transitional stabilization artifacts.  
**Default:** If in doubt, keep. Test deletion is lowest priority, highest risk.

---

## Phase 0 — Inventory & Baseline Lock

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** Confirm the baseline and classify every artifact before anything moves.  
**Risk:** None — read-only.

### Tasks

- `[x]` Run full test suite — 879 passed, 2 skipped ✅
- `[x]` Verify `docs/navigation-map.md` — 61/61 links resolve ✅
- `[x]` Grep for doc references in tests — findings below ✅
  - `grep -rn "synth01-design\|synth01-candidate-set\|architecture-execution-plan\|lens-form-readiness\|minutes-stability-xgi-study" tests/ docs/`
- `[x]` Working tree — baseline commit d361d66 made (116 files, 9-phase program complete) ✅

### Grep findings (Phase 0)

**Test reference (comment only — not a runtime dependency):**
- `tests/test_minutes_stability_study.py:10` — comment line `Design doc: docs/studies/minutes-stability-xgi-study.md`
  - This test is already scheduled for Phase 4 review (keep vs demote). Archiving the file will not break the test (comment reference only).

**Doc-to-doc references (needs attention in Phase 3):**
- `docs/governance/evaluation-gate-criteria.md:131` — references `docs/architecture-execution-plan.md` (scheduled for archival)
- `docs/studies/results/minstab-01-results.md:6,244` — relative link to `../minutes-stability-xgi-study.md` (will break after archival; update in Phase 3)
- `docs/governance/state-representation-inventory.md` — references `synth01-candidate-set.md` (historical record; acceptable)
- `docs/governance/operational-convergence-plan.md` — multiple references to `synth01-design.md`, `synth01-candidate-set.md` (historical record; acceptable)

### Verification

All tasks complete, tests green, no blocking broken references found.

---

## Phase 1 — Code Annotation Cleanup

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** Intelligence module surfaces read like current operational code, not a governance journal.  
**Scope:** `intelligence/` only — `_base.py`, `captain.py`, `transfers.py`, `availability.py`, `value.py`, `fixtures.py`, `weight_registry.py`  
**Risk:** Removing a comment that encodes a current constraint. Mitigated by conservative retention rule.

### Tasks

- `[x]` `intelligence/captain.py` — rewrite module docstring; strip GAP-TRACE/PROVISIONAL/Phase narrative; retain scope constraints ✅
- `[x]` `intelligence/transfers.py` — same ✅
- `[x]` `intelligence/availability.py` — same ✅
- `[x]` `intelligence/value.py` — same ✅
- `[x]` `intelligence/fixtures.py` — same ✅
- `[x]` `intelligence/_base.py` — strip GAP-TRACE annotations; retain positional/scope comments ✅
- `[x]` `intelligence/weight_registry.py` — rewrite module docstring to describe current behavior ✅
- `[x]` Replace all `# UNJUSTIFIED (threshold-registry.md §X):` with `# threshold not evaluation-derived — see threshold-registry.md §X` ✅

### Verification

- `grep -rn "GAP-TRACE\|PROVISIONAL-EDITORIAL\|Phase [0-9] will\|blocked until\|Resolution:" intelligence/` → zero results ✅
- Test suite: 879 passed, 2 skipped ✅

---

## Phase 2 — Document Archival

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** Working documents and superseded plans move to `docs/archive/`.  
**Risk:** A test or doc references a moved file. Mitigated by Phase 0 grep check.

### Tasks

- `[x]` Create `docs/archive/` directory ✅
- `[x]` Create `docs/archive/README.md` with supersession table ✅
- `[x]` Move `docs/architecture-execution-plan.md` → `docs/archive/` ✅
- `[x]` Move `docs/governance/synth01-design.md` → `docs/archive/` ✅
- `[x]` Move `docs/governance/synth01-candidate-set.md` → `docs/archive/` ✅
- `[x]` Move `docs/studies/lens-form-readiness.md` → `docs/archive/` ✅
- `[x]` Move `docs/studies/minutes-stability-xgi-study.md` → `docs/archive/` ✅

### Archive README template

| File | Archived | Superseded by |
|---|---|---|
| architecture-execution-plan.md | 2026-05-27 | System is operational; plan complete |
| synth01-design.md | 2026-05-27 | `signals/evaluation/synth01_decisions.yaml` |
| synth01-candidate-set.md | 2026-05-27 | `signals/registry/synth01_candidates.yaml` |
| lens-form-readiness.md | 2026-05-27 | Study complete; results in `studies/lenses/` |
| minutes-stability-xgi-study.md | 2026-05-27 | `docs/studies/results/minstab-01-results.md` |

### Verification

- All five files exist in `docs/archive/` ✅
- `docs/archive/README.md` exists with supersession table ✅
- Test suite: 879 passed, 2 skipped ✅

---

## Phase 3 — Reference Document Updates

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** The three stale reference documents updated to reflect completed program state.  
**Risk:** Low — doc-only changes. No code touched.

### Tasks

- `[x]` **`docs/governance/threshold-registry.md`** ✅
  - Removed "Acceptable post-Phase 8?" column; added "2026/27 disposition" column
  - Replaced all `Resolution phase: Phase 8` entries with `EVALUATION-DEFERRED — carries to 2026/27`
  - Updated SCORE-T-01 (MIN_RHO) to `RESOLVED — removed in Phase 8 (G-OPS-02)`
  - Updated classification vocabulary: `UNJUSTIFIED`/`PROVISIONAL-EDITORIAL` → `EVALUATION-DEFERRED`
  - Fixed broken link in evaluation-gate-criteria.md (architecture-execution-plan archived)
  - Fixed broken links in minstab-01-results.md (design doc archived)

- `[x]` **`docs/governance/operational-convergence-plan.md`** ✅
  - Slimmed Phase 4, 5, 6 detailed specs to ≤10 lines each
  - Removed Phase 7 original deferred spec (executed; narrative in git history)
  - Header status updated to "Phases 1–9 complete; Consolidation Pass in progress"

- `[x]` **`docs/navigation-map.md`** ✅
  - Fixed broken link (minutes-stability-xgi-study.md → archived location)
  - Added "Archived" section with all five archived files
  - Added `outputs/operational-baseline.md` to Operational outputs section
  - Added `studies/operational/phase9_backtest.py` to Study record section
  - 68/68 links now resolve ✅

### Verification

- `grep -rn "resolution_phase: Phase" docs/governance/threshold-registry.md` → zero results ✅
- All 68 links in `docs/navigation-map.md` resolve ✅
- Test suite: 879 passed, 2 skipped ✅

---

## Phase 4 — Test Audit

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** Identify transitional stabilization tests that are candidates for demotion. No deletion without reading.  
**Risk:** Highest risk phase. Conservative default: keep.

### Permanent Architecture Enforcement Tests (never touch)

These enforce current system invariants. They are as permanent as the ADRs:

| Test file | Invariant enforced |
|---|---|
| `test_downstream_governance.py` | Import direction between layers |
| `test_runtime_consumer_alignment.py` | No hardcoded weights; lifecycle enforcement; provenance |
| `test_traceability_completeness.py` | Signal traceability matrix completeness |
| `test_ontology_consistency.py` | Ontology YAML schema |
| `test_state_architecture.py` | STATE column structure; rejected column absence |
| `test_evaluation_metadata.py` | evaluation_metadata.yaml schema contract |
| `test_runtime_metadata_propagation.py` | Governance metadata propagation |
| `test_scorer_signals.py` | Manifest loading contract |
| `test_scorer_engine.py` | Scoring correctness |
| `test_registry_lifecycle.py` | Registry lifecycle gate |
| `test_registry_contract.py` | Registry schema |

### Tasks (read-before-decide)

- `[x]` Read `tests/stabilization/` — classify each test: regression guard vs transitional artifact ✅
- `[x]` Read `test_minutes_stability_study.py` — decide: keep in CI or demote to `studies/` (do not delete) ✅
- `[x]` Read `test_rolling_xgi_study.py` — same decision ✅
- `[x]` Read `test_rolling_xgi_real_validation.py` — same decision ✅
- `[x]` Document decision for each with one-sentence rationale ✅

### Classification Decisions

#### `tests/stabilization/` — all KEEP (regression guards)

All 10 stabilization test files test specific behavioral correctness of the current DAL. Each encodes a concrete regression class that would be silently reintroduced without it.

| File | Classification | Rationale |
|------|---------------|-----------|
| `test_wave1_sc1_minutes_trend.py` | **KEEP — regression guard** | Tests look-ahead leak fix in `minutes_trend`; removing would allow future reintroduction of data leakage. |
| `test_wave1_sc2_bgw_team_id.py` | **KEEP — regression guard** | Tests BGW team_id temporal correctness (pre-BGW team, not latest); enforces ADR-007 semantics. |
| `test_wave1_sc3_goals_conceded.py` | **KEEP — regression guard** | Tests DGW goals_conceded sum vs mean; enforces ADR-008 aggregation correctness. |
| `test_wave1_sc4_opponent_team_id.py` | **KEEP — regression guard** | Tests opponent_team_id fixture context override; a live correctness invariant in state derivation. |
| `test_wave1_sc11_missing_gw_context.py` | **KEEP — regression guard** | Tests that missing GW context raises DALContractViolation; prevents silent failure mode. |
| `test_wave2_contract_enforcement.py` | **KEEP — regression guard** | Tests V-3 upward coupling absence and nullable type contracts; these are live architecture constraints. |
| `test_wave3_determinism.py` | **KEEP — regression guard** | Tests SQL ORDER BY presence and FIRST_COLS aggregation reproducibility; determinism is a current DAL guarantee. |
| `test_wave4_invariant_expansion.py` | **KEEP — regression guard** | Tests fixture_context BGW/DGW/SGW classification and xgc DEF validation; live behavioral invariants. |
| `test_wave5_architecture.py` | **KEEP — regression guard** | Tests dead code absence and exception hierarchy; architecture cleanliness is an ongoing constraint. |
| `test_wave6_observability.py` | **KEEP — regression guard** | Tests logging, hash reproducibility, and env var DB path; operational observability is a live requirement. |

#### Study tests — all KEEP in CI

| File | Classification | Rationale |
|------|---------------|-----------|
| `test_minutes_stability_study.py` | **KEEP — study reproducibility guard** | 31 tests enforce determinism, population closure, and no-future-leakage invariants of MINSTAB-01; needed for 2026/27 replication. Note: line 10 comment references archived design doc — comment is informational only, not a runtime dependency. |
| `test_rolling_xgi_study.py` | **KEEP — study reproducibility guard** | Tests enforce determinism and correctness of rolling xGI horizon evaluation; the study motivates the current signal registry state. |
| `test_rolling_xgi_real_validation.py` | **KEEP — study reproducibility guard** | Tests real-data validation path for rolling xGI; companion to the study, needed for future-season replication. |

No tests demoted or deleted. Conservative default applied throughout.

### Verification

- Test suite count ≥ 879 (may increase if stabilization tests are kept; must not decrease)
- Every removed or demoted test has a documented rationale in this document

---

## Phase 5 — Verification & Closure

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** Full verification pass confirming all criteria met. Update program status to COMPLETE.

### Final verification checklist

- `[x]` `pytest` passes at ≥ 879 — **879 passed, 2 skipped** ✅
- `[x]` `grep -rn "GAP-TRACE\|PROVISIONAL-EDITORIAL\|Phase [0-9] will\|blocked until" intelligence/` → **zero results** ✅
- `[x]` `grep -rn "resolution_phase: Phase" docs/governance/threshold-registry.md` → **zero results** ✅
- `[x]` Every link in `docs/navigation-map.md` resolves to an existing file — **68/68** ✅
- `[x]` `docs/archive/README.md` exists and lists all archived files ✅
- `[x]` No runtime code imports a path that was archived — YAML historical record fields noted and classified as acceptable per Phase 0 ✅
- `[x]` `outputs/operational-baseline.md` is linked from `docs/navigation-map.md` ✅
- `[x]` `docs/governance/consolidation-pass.md` status updated to `COMPLETE` ✅
- `[x]` Project memory updated ✅

### Failure conditions

- Test count drops → stop, diagnose, do not proceed
- Removed comment caused a test to stop testing its claimed invariant → restore comment
- Archived doc still referenced by a test → restore doc or update reference first

---

## What Must Remain Discoverable (audit trail)

The following must remain findable and navigable for future auditability and 2026/27 season reproducibility:

| Artifact | Location | Reason |
|---|---|---|
| SYNTH-01 decisions | `signals/evaluation/synth01_decisions.yaml` | Analytical lineage for composition weights |
| Evaluation metadata | `signals/evaluation/evaluation_metadata.yaml` | Gate decisions for all 14 candidates |
| Signal traceability | `signals/registry/signal_traceability.yaml` | Governance-to-runtime topology |
| Phase 9 retrospective | `outputs/operational-baseline.md` | Season validation record |
| Backtest results | `outputs/phase9_backtest_results.yaml` | Machine-readable validation stats |
| Gate criteria | `docs/governance/evaluation-gate-criteria.md` | Reproducibility of gate decisions |
| Threshold registry | `docs/governance/threshold-registry.md` | Calibration carry-forward record |
| Convergence plan | `docs/governance/operational-convergence-plan.md` | Full 9-phase program record |

---

## Answers to Standing Policy Questions

**Documents that remain authoritative:** All `docs/architecture/*`, `docs/adr/001–011`, `docs/governance/signal-traceability-matrix.md`, `evaluation-gate-criteria.md`, `threshold-registry.md`, `state-representation-inventory.md`, `operational-convergence-plan.md`, `docs/foundations/*`, `docs/navigation-map.md`.

**Biggest risks of over-cleaning:** (1) Removing a comment that encodes a scope constraint → future developer reintroduces excluded signal. (2) Archiving a doc still providing orientation not captured elsewhere. (3) Deleting a test that catches a real regression class even if it resembles governance ceremony.

**Ordering rationale:** Phase 0 first (inventory while repo is clean). Phase 1 before Phase 2 (code annotations are highest semantic risk — do while everything else is stable). Phase 2 before Phase 3 (archival before navigation-map update, so links are correct when map is written). Phase 4 last (most conservative; tests are the safety net throughout).
