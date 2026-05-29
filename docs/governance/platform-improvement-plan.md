# PLATFORM-01 — Platform Improvement Plan

**Source:** `docs/governance/platform-assessment-2026-05.md`  
**Issued:** 2026-05-27  
**Status:** COMPLETE — 2026-05-27  
**Baseline:** Operational (Level 4) — weighted score 4.04/5.0  
**Target:** Platform Mature (Level 5)  
**Invariant:** 879 tests passed, 2 skipped — must hold throughout

---

## Scope

Five bounded improvement tasks derived directly from the May 2026 assessment.
No analytical changes. No new features. No layer restructuring.

Ordered by rubric priority weight × impact. CRITICAL-category items first.

---

## Phase 1 — Architecture Enforcement Closure

**Status:** `[x] COMPLETE — 2026-05-27`  
**Rubric categories:** Architecture & Layer Integrity (CRITICAL), Test Quality (CRITICAL)  
**Risk:** Low — additive test only, no logic changes  
**Effort:** Low

### What

The only remaining convention-only layer boundary rule is that `intelligence/` must not import from `studies/`. This is stated in `intelligence/_base.py` docstring but has no AST test backing it. Every other boundary is mechanically enforced.

### Tasks

- `[x]` Read `tests/test_dal_architecture.py` — understand the existing AST import scan pattern ✅
- `[x]` Add `test_intelligence_does_not_import_studies` to `tests/test_dal_architecture.py` ✅
- `[x]` Add vacuousness guard for `intelligence/` to `test_dal_architecture_tests_are_not_vacuous` ✅
- `[x]` Run full test suite — must remain at ≥ 879 ✅

### Done when

`grep -rn "from studies\|import studies" intelligence/` either returns zero results, or any violation causes the new test to fail.

---

## Phase 2 — Pre-Lens Signal Governance Closure

**Status:** `[x] COMPLETE — 2026-05-27`  
**Rubric categories:** Operational Governance (IMPORTANT), Maintainability (CRITICAL)  
**Risk:** Low-medium — changes exception handling in scoring path; requires test coverage  
**Effort:** Low-medium

### What

`intelligence/scoring/signals.py:125–130` silently skips signals not present in `evaluation_metadata.yaml` via `except GovernanceMetadataError: continue`. Pre-lens signals (`goals_scored`, `assists`, etc.) enter the scoring manifest without passing any evaluation gate. The fix is an explicit allowlist — signals exempt from evaluation governance are declared, not discovered by exception.

### Tasks

- `[x]` Read `intelligence/scoring/signals.py:100–150` — understand `_assert_governance_compliance` and the exception handler ✅
- `[x]` Read `signals/evaluation/evaluation_metadata.yaml` — identify which signals have records vs which do not ✅
- `[x]` Define `_PRE_LENS_SIGNAL_ALLOWLIST: frozenset[str]` in `signals.py` listing all signals legitimately exempt from evaluation governance (e.g. `goals_scored`, `assists`, `clean_sheets`) ✅
- `[x]` Replace `except GovernanceMetadataError: continue` with: if signal not in allowlist, re-raise; else continue ✅
- `[x]` Add a test asserting that a signal absent from both `evaluation_metadata.yaml` and the allowlist raises `GovernanceMetadataError` ✅
- `[x]` Add a test asserting allowlist signals pass governance without an evaluation record ✅
- `[x]` Run full test suite — must remain at ≥ 879 ✅ (883 passed)

### Done when

No signal can enter the scoring manifest silently. Every signal either has an evaluation record, is on the allowlist, or raises a hard error.

---

## Phase 3 — CONTEXT.md Accuracy

**Status:** `[x] COMPLETE — 2026-05-27`  
**Rubric categories:** Repository Usability (IMPORTANT)  
**Risk:** None — documentation only  
**Effort:** Low

### What

`CONTEXT.md` section 5 status table has stale entries: SYNTH-01 marked `BLOCKED`, lens studies marked `PENDING` that have `approved` entries in `evaluation_metadata.yaml`, and Phase references that predate the 9-phase program completion. A new engineer reads `CONTEXT.md` first — stale status creates navigability confusion.

### Tasks

- `[x]` Read `CONTEXT.md` section 5 status table ✅
- `[x]` Read `signals/evaluation/evaluation_metadata.yaml` — note which signals have `lifecycle_state: approved` or `synth01_decision: APPROVED-*` ✅
- `[x]` Update SYNTH-01 status → `COMPLETE (Phase 7, 2026-05-27)` ✅
- `[x]` Update lens study statuses to match `evaluation_metadata.yaml` actual states ✅
- `[x]` Update any `BLOCKED` or `PENDING` entries that are now resolved ✅
- `[x]` Update Phase references to reflect 9-phase program complete + REPO-CONS-01 complete ✅

### Done when

Every status entry in `CONTEXT.md` matches the actual state in `evaluation_metadata.yaml` and the operational convergence plan.

---

## Phase 4 — Docstring & Comment Hygiene

**Status:** `[x] COMPLETE — 2026-05-27`  
**Rubric categories:** Docstrings & Comments (IMPORTANT, score 3 — lowest category)  
**Risk:** Low — no logic changes; same retention rules as REPO-CONS-01 Phase 1  
**Effort:** Low-medium

### What

Process-history commentary persists in two production files:
- `signals/registry/weight_registry.yaml` — `# Phase 6 changes`, `GAP-TRACE-02`, `GAP-TRACE-06`, `G-OPS-01`, `G-OPS-02` without self-contained explanation
- `dal/state/player_gameweek_state.py` — `# Approved derived rolling column set — Phase 3 Representation Inventory Lock`, `# SC-1 fix`

Additionally: `intelligence/scoring/signals.py` — `_exclusion_reason` function has no docstring.

**Retention rule (same as REPO-CONS-01):** Replace phase/trace references with a self-contained one-sentence rationale. The test: can a new engineer understand the constraint by reading the file alone?

### Tasks

- `[x]` Read `signals/registry/weight_registry.yaml` — identify all phase/trace/G-OPS references ✅
- `[x]` Replace each with self-contained rationale ✅
- `[x]` Read `dal/state/player_gameweek_state.py` — identify `Phase 3`, `SC-1 fix`, and similar inline process references ✅
- `[x]` Replace with self-contained rationale ✅ (also cleaned `dal/state/contracts.py`)
- `[x]` Add a one-line docstring to `_exclusion_reason` in `intelligence/scoring/signals.py` ✅ (added in Phase 2)
- `[x]` Verify: zero results in targeted production files ✅
- `[x]` Run full test suite — must remain at ≥ 879 ✅ (883 passed)

### Done when

Grep returns zero process-history references in the three targeted files. All comments are self-contained.

---

## Phase 5 — Verification & Closure

**Status:** `[x] COMPLETE — 2026-05-27`  
**Goal:** Confirm all four phases complete and score has moved toward Level 5.

### Final checklist

- `[x]` `pytest` passes at ≥ 879 ✅ (883 passed, 2 skipped)
- `[x]` `grep -rn "from studies\|import studies" intelligence/` → zero import violations (string literals in error messages are not imports) ✅
- `[x]` No signal enters scoring manifest without evaluation record or allowlist entry ✅
- `[x]` `CONTEXT.md` status table matches `evaluation_metadata.yaml` actual states ✅
- `[x]` `grep -rn "Phase [0-9]\|GAP-TRACE\|SC-[0-9] fix\|G-OPS-0"` → zero results in targeted production files ✅
- `[x]` `docs/governance/platform-improvement-plan.md` status updated to `COMPLETE` ✅
- `[x]` Next assessment scheduled: 2026-11 (semi-annual cadence)

---

## Out of Scope

The following assessment findings are deliberately deferred — they require analytical work, not engineering cleanup:

| Finding | Why deferred |
|---------|-------------|
| Move threshold constants to YAML config | Requires calibration study first; no point configuring uncalibrated values |
| Document Phase 9 validation roadmap for EVALUATION-DEFERRED thresholds | This is the 2026/27 calibration program — separate track |
| Layer naming coherence audit | Separate program; architectural vocabulary, not code hygiene |

---

## What Must Not Change

- No analytical logic changes
- No schema changes  
- No signal additions or removals
- No threshold value changes
- Test count must not decrease below 879
