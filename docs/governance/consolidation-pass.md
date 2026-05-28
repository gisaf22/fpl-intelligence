# REPO-CONS-01 — Repository Consolidation & Reference Stabilization

**Program:** Operational Convergence Plan — Consolidation Pass  
**Issued:** 2026-05-27  
**Status:** PENDING  
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
- `[ ]` Working tree — uncommitted changes present (all from 9-phase program); needs baseline commit before pass proceeds

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

**Status:** `[ ] PENDING`  
**Goal:** Intelligence module surfaces read like current operational code, not a governance journal.  
**Scope:** `intelligence/` only — `_base.py`, `captain.py`, `transfers.py`, `availability.py`, `value.py`, `fixtures.py`, `weight_registry.py`  
**Risk:** Removing a comment that encodes a current constraint. Mitigated by conservative retention rule.

### Tasks

- `[ ]` `intelligence/captain.py` — rewrite module docstring; strip GAP-TRACE/PROVISIONAL/Phase narrative; retain scope constraints
- `[ ]` `intelligence/transfers.py` — same
- `[ ]` `intelligence/availability.py` — same
- `[ ]` `intelligence/value.py` — same
- `[ ]` `intelligence/fixtures.py` — same
- `[ ]` `intelligence/_base.py` — strip GAP-TRACE annotations; retain positional/scope comments
- `[ ]` `intelligence/weight_registry.py` — rewrite module docstring to describe current behavior (loads from YAML; raises on missing)
- `[ ]` Replace all `# UNJUSTIFIED (threshold-registry.md §X):` with `# threshold not evaluation-derived — see threshold-registry.md §X`

### Verification

- `grep -rn "GAP-TRACE\|PROVISIONAL-EDITORIAL\|Phase [0-9] will\|blocked until\|Resolution:" intelligence/` → zero results
- Test suite: 879 passed, 2 skipped

---

## Phase 2 — Document Archival

**Status:** `[ ] PENDING`  
**Goal:** Working documents and superseded plans move to `docs/archive/`.  
**Risk:** A test or doc references a moved file. Mitigated by Phase 0 grep check.

### Tasks

- `[ ]` Create `docs/archive/` directory
- `[ ]` Create `docs/archive/README.md` with supersession table (see template below)
- `[ ]` Move `docs/architecture-execution-plan.md` → `docs/archive/`
- `[ ]` Move `docs/governance/synth01-design.md` → `docs/archive/`
- `[ ]` Move `docs/governance/synth01-candidate-set.md` → `docs/archive/`
- `[ ]` Move `docs/studies/lens-form-readiness.md` → `docs/archive/`
- `[ ]` Move `docs/studies/minutes-stability-xgi-study.md` → `docs/archive/`

### Archive README template

| File | Archived | Superseded by |
|---|---|---|
| architecture-execution-plan.md | 2026-05-27 | System is operational; plan complete |
| synth01-design.md | 2026-05-27 | `signals/evaluation/synth01_decisions.yaml` |
| synth01-candidate-set.md | 2026-05-27 | `signals/registry/synth01_candidates.yaml` |
| lens-form-readiness.md | 2026-05-27 | Study complete; results in `studies/lenses/` |
| minutes-stability-xgi-study.md | 2026-05-27 | `docs/studies/results/minstab-01-results.md` |

### Verification

- All five files exist in `docs/archive/`
- `docs/archive/README.md` exists with supersession table
- Test suite: 879 passed, 2 skipped

---

## Phase 3 — Reference Document Updates

**Status:** `[ ] PENDING`  
**Goal:** The three stale reference documents updated to reflect completed program state.  
**Risk:** Low — doc-only changes. No code touched.

### Tasks

- `[ ]` **`docs/governance/threshold-registry.md`**
  - Remove "Acceptable post-Phase 8?" column from classification table
  - Add "2026/27 disposition" column
  - Replace `resolution_phase: Phase 8` on all 7 thresholds with `EVALUATION-DEFERRED — carries to 2026/27` and pointer to `outputs/operational-baseline.md`
  - Update `MIN_RHO` entry to `RESOLVED — removed in Phase 8 (G-OPS-02)`
  - Update classification vocabulary: `UNJUSTIFIED` → `EVALUATION-DEFERRED` where appropriate

- `[ ]` **`docs/governance/operational-convergence-plan.md`**
  - Slim each completed phase body to its completion record only (≤10 lines per phase)
  - Full phase narrative is preserved in git history
  - Confirm header status line reads "Phases 1–9 complete; Consolidation Pass in progress"

- `[ ]` **`docs/navigation-map.md`**
  - Validate every existing link resolves after Phase 2 archival
  - Add "Archived" section listing the five archived files with one-line summaries
  - Add `outputs/operational-baseline.md` to the Outputs section if missing
  - Add `studies/operational/phase9_backtest.py` to the Studies section if missing

### Verification

- `grep -rn "resolution_phase: Phase" docs/governance/threshold-registry.md` → zero results
- All links in `docs/navigation-map.md` resolve
- Test suite: 879 passed, 2 skipped

---

## Phase 4 — Test Audit

**Status:** `[ ] PENDING`  
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

- `[ ]` Read `tests/stabilization/` — classify each test: regression guard vs transitional artifact
- `[ ]` Read `test_minutes_stability_study.py` — decide: keep in CI or demote to `studies/` (do not delete)
- `[ ]` Read `test_rolling_xgi_study.py` — same decision
- `[ ]` Read `test_rolling_xgi_real_validation.py` — same decision
- `[ ]` Document decision for each with one-sentence rationale

### Verification

- Test suite count ≥ 879 (may increase if stabilization tests are kept; must not decrease)
- Every removed or demoted test has a documented rationale in this document

---

## Phase 5 — Verification & Closure

**Status:** `[ ] PENDING`  
**Goal:** Full verification pass confirming all criteria met. Update program status to COMPLETE.

### Final verification checklist

- `[ ]` `pytest` passes at ≥ 879 (same count as baseline)
- `[ ]` `grep -rn "GAP-TRACE\|PROVISIONAL-EDITORIAL\|Phase [0-9] will\|blocked until" intelligence/` → zero results
- `[ ]` `grep -rn "resolution_phase: Phase" docs/governance/threshold-registry.md` → zero results
- `[ ]` Every link in `docs/navigation-map.md` resolves to an existing file
- `[ ]` `docs/archive/README.md` exists and lists all archived files
- `[ ]` No runtime code imports a path that was archived
- `[ ]` `outputs/operational-baseline.md` is linked from `docs/navigation-map.md`
- `[ ]` `docs/governance/consolidation-pass.md` status updated to `COMPLETE`
- `[ ]` Project memory updated

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
