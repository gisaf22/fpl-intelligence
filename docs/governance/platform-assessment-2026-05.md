# Platform Maturity & Maintainability Assessment — May 2026

**Date:** 2026-05-27
**Revision:** 1.0
**Scope:** Full 10-category assessment against `docs/governance/platform-rubric.md`
**Assessor:** Lead Platform Analytics Engineer
**Rubric version:** 1.0

---

## Executive Summary

The fpl-intelligence platform scores **4.06 (weighted)** — mapping to **Operational (Level 4)** under the rubric maturity scale. The system exhibits exceptional architectural discipline: six named layers with mechanically enforced boundaries, explicit column-level contracts with declared null semantics and dtype targets, a lifecycle gate that fires before the scoring path runs, and a test suite that protects real invariants rather than implementation details. The primary gap is that most eligibility and risk thresholds are classified `EVALUATION-DEFERRED` — they are documented and registered in the threshold registry but have not yet been calibrated against predictive evidence, which means operational decisions depend on editorial constants whose correctness has not been demonstrated. A secondary gap is docstring quality: module-level docstrings are strong but some inline comments inside intelligence modules contain process-history language ("Phase 8", "GAP-TRACE-02") that reduces signal-to-noise. Neither gap is a critical floor violation.

---

## Category Assessments

---

### 1. Architecture & Layer Integrity

**Score: 4**

**Priority:** CRITICAL

#### Rationale

Six named, documented layers (`staging → intermediate → curated → state → prepared` in the DAL, plus `signals/`, `intelligence/`, `studies/`) have one-way dependency rules that are enforced mechanically by `tests/test_dal_architecture.py` using AST import scanning. The test explicitly checks four directions: state must not import from staging, intermediate, or curated; validation must not import from curated (V-3 contract). A vacuousness guard (`test_dal_architecture_tests_are_not_vacuous`) ensures the scans operate on real files. The `intelligence/_base.py` module-level docstring explicitly prohibits research artifacts from entering the intelligence layer. Cross-layer governance for downstream modules is enforced by `tests/test_downstream_governance.py`, which scans `signals/`, `studies/`, and `intelligence/` for forbidden imports of retired module namespaces and raw SQL outside the DAL.

One tension exists: the `intelligence/` layer does not yet have a symmetric AST test asserting it never imports from `studies/`. The docstring in `_base.py` states the constraint ("Research artifacts... must not enter here"), but the enforcement is convention-based for this specific direction, not mechanically tested at the intelligence-layer level.

**Evidence:**
- `tests/test_dal_architecture.py:56–105` — four parametric AST import checks with vacuousness guard
- `intelligence/_base.py:3–7` — module-level docstring states the studies exclusion rule
- `tests/test_downstream_governance.py` — downstream governance scans for forbidden patterns

**Improvement action:** Add an AST test asserting no `intelligence/` module imports from `studies/`. This closes the only remaining convention-only enforcement direction and makes the critical "no research leakage into runtime" rule mechanically verifiable.

---

### 2. Contracts & Schemas

**Score: 5**

**Priority:** CRITICAL

#### Rationale

Contracts are explicit, typed, and enforced at multiple layers. `dal/curated/contracts.py` declares every spine column with its dtype (`DTYPES` dict), aggregation semantics (`FIRST_COLS`, `SUM_COLS`), null rules (`NULL_RULES` — `never_null`, `null_if_bgw`, `always_nullable`), and a `FIRST_COL_SEMANTICS` dict that explains exactly why each FIRST aggregation is valid. `dal/state/contracts.py` declares causality, warmup, and reliability for every derived rolling column. `signals/lifecycle/schema.py` declares required columns, controlled vocabulary (via `frozenset`s for every enumerated field), boolean columns, and nullable controlled columns. The `GovernanceMetadata` dataclass enforces typing for runtime governance. Contract violations are caught before computation: `_validate_spine_entry_contract` in `player_gameweek_state.py` raises `ValueError` with specific messages on missing columns, duplicate grain, or zero-substituted BGW rows. `tests/test_curated_state_boundary.py` demonstrates the semantic risk of zero substitution (Contract 4) — an explicit test proving that null vs. zero produces different rolling means.

**Evidence:**
- `dal/curated/contracts.py:176–220` — `NULL_RULES` dict; 22 `null_if_bgw` columns, 4 `never_null` identity columns
- `dal/state/player_gameweek_state.py:174` — `_validate_spine_entry_contract` with three distinct failure modes
- `signals/lifecycle/schema.py:226–258` — `GovernanceMetadata` dataclass with runtime governance fields
- `tests/test_curated_state_boundary.py:138–195` — semantic demonstration test for BGW null contract

**Improvement action:** None required at current maturity. For future enhancement, consider formalising contract versioning so that contract changes can be reviewed as diffs against a version-tagged baseline.

---

### 3. Runtime Simplicity

**Score: 4**

**Priority:** CRITICAL

#### Rationale

The scoring path from input to output is traceable without a debugger. `intelligence/captain.py` loads weights at module import via `get_module_weights("captain")`, validates inputs via `validate_intelligence_inputs`, applies four normalised component scores, and computes a `weighted_composite`. Every component column is emitted in the output (`_OUTPUT_COLS` includes all intermediates), making "why did player X get score Y?" answerable by reading the DataFrame. The `intelligence/provenance.py` module provides an explicit `score_provenance()` function that returns the complete audit trail — weights, STATE values, signal_id, provenance note, and caveats from `signal_traceability.yaml` — for any player/gameweek/module combination. Weights are loaded from YAML config, not hardcoded, and the loader fails hard on any missing entry (`WeightRegistryError`). `lru_cache` prevents repeated file reads.

One indirection layer adds modest complexity: scoring weights are in `weight_registry.yaml`, composition weights are in `synth01_decisions.yaml`, and threshold context is in `threshold-registry.md`. These are correctly separated by concern, but a new engineer answering "why is this weight 0.35?" must trace three files. The `weight_registry.yaml` comments reference `GAP-TRACE-02`, `PHASE 8`, and similar process-history codes that require reading the operational convergence plan to interpret.

**Evidence:**
- `intelligence/captain.py:28` — weights loaded at import: `_WEIGHTS: dict[str, float] = get_module_weights("captain")`
- `intelligence/provenance.py:81–177` — `score_provenance()` returns complete governance audit trail
- `signals/registry/weight_registry.yaml` — weights declared with `signal_id` and `note` per entry

**Improvement action:** Replace `GAP-TRACE-*` and `PHASE *` cross-references in `weight_registry.yaml` provenance notes with self-contained one-sentence governance rationale. A new engineer should be able to understand why a weight exists by reading the YAML alone — without following a reference chain.

---

### 4. Naming & Vocabulary

**Score: 4**

**Priority:** IMPORTANT

#### Rationale

Naming is largely consistent and domain-appropriate across all layers. The DAL uses `player_id`, `gw`, `is_bgw`, `is_dgw` — not FPL API names like `element` or `code`. Intelligence functions are named after their decision output (`rank_captain_candidates`, `flag_availability_risk`, `score_transfers_candidates`), not their implementation. Signal IDs follow a consistent `LENS-NNN` convention (FORM-001, AVAIL-003, MARKET-004). Registry vocabulary terms (`candidate`, `eligible`, `blocked`, `approved`) are defined in glossary sections of `evaluation_metadata.yaml` and `signal-traceability-matrix.md`. Module and function names in `signals/lifecycle/` use control-plane vocabulary (`assert_operational_safe`, `LifecycleViolationError`, `LeakageViolationError`).

Minor deviations: `_compute_minutes_trend` in the state layer is named after its implementation (rolling divergence calculation) rather than its contract (availability domain trend classifier). Internal helper names like `_xgi_roll5_scored` and `_fixture_context_dgw` in `captain.py` use leading underscores to flag temporariness, which is fine, but the `_scored` suffix is implementation-specific. No `_v2`, `_new`, or `_fixed` patterns observed.

**Evidence:**
- `intelligence/captain.py:100–101` — `_xgi_roll5_scored` (implementation name, acceptable as private temp)
- `dal/state/player_gameweek_state.py:10` — `_ROLL_COLS` (opaque abbreviation; `_ROLLING_PERFORMANCE_COLS` would be clearer)
- `signals/lifecycle/lifecycle.py:21–39` — `LifecycleViolationError`, `LeakageViolationError` (precise, domain-appropriate)

**Improvement action:** Rename `_ROLL_COLS` in `player_gameweek_state.py` to `_ROLLING_PERFORMANCE_COLS` or similar to eliminate the unexplained abbreviation. `_ROLL_COLS` is referenced in `contracts.py` (imported) and in tests, making it part of the semi-public contract; clarity matters.

---

### 5. Docstrings & Comments

**Score: 3**

**Priority:** IMPORTANT

#### Rationale

Module-level docstrings are strong and operationally focused: `intelligence/_base.py` states what is allowed and forbidden; `signals/lifecycle/lifecycle.py` states the purpose and usage pattern with a code example; `intelligence/availability.py` lists all three threshold values with their threshold-registry references. Function-level docstrings in intelligence modules follow a consistent pattern (Parameters, Returns, scoring components with percentages), which is genuinely useful. The threshold-registry references in `availability.py:7–13` are exemplary — the docstring explains the semantic grounding and explicitly flags that values are not evaluation-derived.

However, process-history commentary appears in production files. `weight_registry.yaml` contains comments like `# Phase 6 changes from hardcoded dicts`, `GAP-TRACE-02`, `GAP-TRACE-06`, and references to `G-OPS-01`, `G-OPS-02` without self-contained explanation. `dal/state/player_gameweek_state.py` inline comments include `# Approved derived rolling column set — Phase 3 Representation Inventory Lock` and `# SC-1 fix`. These are comprehensible with history but reduce signal-to-noise for a new reader. Some function docstrings (e.g., `normalize_within_position`) state preconditions and postconditions clearly; others (e.g., `_exclusion_reason` in `signals.py`) have no docstring at all. `_assert_governance_compliance` has a good docstring but references `Phase 2, operational-convergence-plan.md` inline.

**Evidence:**
- `intelligence/availability.py:7–13` — good: threshold values documented with rationale and external reference
- `signals/registry/weight_registry.yaml:14–30` — process history: `# Phase 6 changes`, `GAP-TRACE-02`, `G-OPS-01` without inline definitions
- `dal/state/player_gameweek_state.py:28` — `# Approved derived rolling column set — Phase 3 Representation Inventory Lock` (process history)
- `intelligence/scoring/signals.py:24` — `_exclusion_reason` has no docstring

**Improvement action:** Perform a targeted docstring hygiene pass on `weight_registry.yaml` and `player_gameweek_state.py`. Replace phase-reference comments with self-contained rationale. The test for this is: can a new engineer understand the constraint without reading the git history or the operational convergence plan?

---

### 6. Test Quality & Enforcement

**Score: 4**

**Priority:** CRITICAL

#### Rationale

The test suite (~739 tests per CONTEXT.md) protects real invariants across multiple categories. Architecture invariant tests use AST scanning to enforce import direction — not mocking of internal calls. Contract tests in `test_curated_state_boundary.py` are structured as seven numbered contracts with named test functions that describe what breaks if they fail (e.g., `test_grain_duplicate_input_rejected_at_state_entry`). Lifecycle gate tests in `test_registry_lifecycle.py` test the gate fires, that errors identify the path, that the gate fires before output is created (preventing partial output), and that determinism holds across repeated calls. Registry contract tests in `test_registry_contract.py` check controlled vocabulary enforcement (low_confidence row cannot be eligible, insufficient_support must be blocked). A vacuousness guard prevents architecture tests from passing on empty directories.

The test for "intelligence does not import studies" is stated in `_base.py` convention but lacks a corresponding test file asserting it mechanically — a gap noted under Architecture above. Some test names are shorter than ideal (e.g., `test_current_registry_loads_and_validates` — clear, but "validates what?" is not answered in the name). No commented-out tests or mock-heavy patterns observed in sampled files.

**Evidence:**
- `tests/test_curated_state_boundary.py:119–131` — grain duplicate test with docstring explaining the corruption risk
- `tests/test_registry_lifecycle.py:143–151` — gate fires before output dir is created (critical operational property)
- `tests/test_dal_architecture.py:108–122` — vacuousness guard preventing silent pass
- `tests/test_registry_contract.py:28–46` — behavioral contract tests, not implementation tests

**Improvement action:** Add an AST-based test asserting `intelligence/` has no imports from `studies/`. This closes the final convention-only enforcement gap in the architecture test coverage and aligns with the existing pattern in `test_dal_architecture.py`.

---

### 7. Configuration & Control Plane Design

**Score: 4**

**Priority:** IMPORTANT

#### Rationale

Scoring weights are fully externalised to `signals/registry/weight_registry.yaml`, loaded via `intelligence/weight_registry.py`, which fails hard on any missing entry. The signal registry (`studies/eda/findings/eda_03_joint_registry.csv`) is the canonical source for signal promotion decisions. Composition weights from SYNTH-01 are in `signals/evaluation/synth01_decisions.yaml`. Lifecycle states are enforced by the `assert_operational_safe` gate called at the start of `load_manifest_from_path`. Threshold constants in intelligence modules all have entries in `docs/governance/threshold-registry.md` with classification (`EVALUATION-DEFERRED`, `RESOLVED`) and a 2026/27 disposition.

The remaining gap is that all eligibility and risk thresholds (8 of 12 registry entries) are `EVALUATION-DEFERRED` — they are hardcoded constants with documented rationale but without empirical calibration. Adding a new threshold currently requires touching the Python source, the threshold registry, and (for module weights) the weight YAML. The control plane does not yet offer a fully declarative path for threshold management — that requires code changes. Additionally, module-level scoring weights are marked `PROVISIONAL-EDITORIAL`, meaning the weight YAML is config for weights that have not yet been validated.

**Evidence:**
- `signals/registry/weight_registry.yaml` — all module weights externalised; `get_module_weights` raises `WeightRegistryError` on missing entry
- `docs/governance/threshold-registry.md:195–213` — open items table: 8 `EVALUATION-DEFERRED`, 1 `RESOLVED`, 0 `CONTRADICTS-GATE`
- `intelligence/captain.py:31` — `_MIN_MINUTES_ROLL3 = 45.0` with comment `# threshold not evaluation-derived — see threshold-registry.md §CAPT-T-01` (registered but hardcoded)

**Improvement action:** Move `EVALUATION-DEFERRED` threshold constants into `weight_registry.yaml` or a dedicated `threshold_registry.yaml` config file, so threshold changes are reviewable diffs rather than Python source edits. This is the path to a fully config-driven control plane.

---

### 8. Repository Usability

**Score: 4**

**Priority:** IMPORTANT

#### Rationale

A new contributor has a clear entry path: `docs/navigation-map.md` provides a role-based reading order (new contributor, DAL contributor, research contributor, scoring contributor, operational runner), an authority table mapping every concern to its canonical document, and an architecture migration status table. `CONTEXT.md` gives project state, directory structure, naming conventions, and session-start rules. The Makefile provides named targets (`make prepare`, `make build-registry`, `make weekly`). Directory names map directly to functional layers — no `temp/`, `old/`, or `wave3_refactor/` directories. The `archive/` directory is clearly labelled and contains a README with a supersession table.

Minor gap: `CONTEXT.md` section 5 contains status entries (`PENDING`, `BLOCKED`) for lens studies that may be stale relative to actual `evaluation_metadata.yaml` content (which contains `approved` lifecycle_state entries for multiple signals, suggesting at least some lens work is complete). The status table describes `SYNTH-01` as `BLOCKED ON Signal registry` while `signals/evaluation/synth01_decisions.yaml` and `evaluation_metadata.yaml` both contain `synth01_decision: APPROVED-*` entries. This creates a navigability ambiguity for a new contributor who reads CONTEXT.md and then looks at the YAML files.

**Evidence:**
- `docs/navigation-map.md:33–72` — role-based reading order with seven-step new contributor path
- `CONTEXT.md:117–131` — status table with `BLOCKED` entries that conflict with `evaluation_metadata.yaml` approved decisions
- `docs/navigation-map.md:126–142` — archive supersession table with six entries and reasons

**Improvement action:** Update `CONTEXT.md` section 5 status table to reflect the actual system state: mark SYNTH-01 as complete (Phase 7 execution 2026-05-27), update lens statuses to `COMPLETE` where `evaluation_metadata.yaml` records approved lifecycle states. A stale status table in the primary orientation document creates confusion for new contributors.

---

### 9. Operational Governance

**Score: 4**

**Priority:** IMPORTANT

#### Rationale

Governance is mechanically wired into the scoring execution path, not just documented. `load_manifest_from_path` calls `assert_operational_safe` (path gate) before loading the registry, and `_assert_governance_compliance` (signal-level gate) after building the manifest. The signal-level gate raises `LeakageViolationError` on `direct` leakage risk, `LifecycleViolationError` on `excluded` lifecycle_state or `blocked` downstream_status — all with specific error messages naming the signal, position, and source gate decision. The report runner (`run_week`) enforces the lifecycle gate before creating any output directory — tested by `TestReportRunnerLifecycleEnforcement.test_run_week_rejects_exploratory_before_output_is_created`. Governance metadata is machine-readable in `evaluation_metadata.yaml` (YAML, consumed by `signals/evaluation/governance.py`) and in `signal_traceability.yaml` (consumed by `intelligence/provenance.py`).

The remaining gap is that `_assert_governance_compliance` silently skips signals not present in `evaluation_metadata.yaml` (`GovernanceMetadataError → continue`). For pre-lens signals (`goals_scored`, `assists`, etc.), this is documented as "governed separately" — but the alternative governance path for pre-lens signals is not mechanically enforced anywhere. Those signals can enter the scoring manifest without passing any evaluation gate, which represents a secondary governance gap.

**Evidence:**
- `intelligence/scoring/signals.py:106–148` — `_assert_governance_compliance`: three hard-fail conditions with specific error messages
- `tests/test_registry_lifecycle.py:143–151` — gate fires before output dir created
- `intelligence/scoring/signals.py:125–130` — pre-lens signal silently skipped: `except GovernanceMetadataError: continue`

**Improvement action:** Create an explicit allowlist of pre-lens signals exempt from evaluation governance, and raise if a signal appears in the scoring manifest without either an evaluation record or an allowlist entry. This closes the "silently skipped" path and makes the governance boundary complete.

---

### 10. Maintainability & Evolution Safety

**Score: 4**

**Priority:** CRITICAL

#### Rationale

The signal addition path is clearly documented and mostly config-driven: add an entry to `evaluation_metadata.yaml`, promote through the lifecycle gate, add to `synth01_decisions.yaml`, update `weight_registry.yaml`, run tests. Adding a signal does not require logic changes to the scoring engine — `load_manifest` builds the manifest dynamically from the registry. Removing a deprecated signal that is still referenced in scoring logic would raise `LifecycleViolationError` at manifest load time, not silently change behavior. Threshold changes require touching one Python constant and updating the threshold registry — the registry entry is the audit trail. `_GOVERNED_ROLLING_COLS` in `player_gameweek_state.py` is a frozenset with a comment stating "Any addition requires a governance decision recorded in `docs/governance/state-representation-inventory.md`" — an explicit evolution gate for the state layer.

The main friction is that module-level scoring weights are `PROVISIONAL-EDITORIAL`, meaning they have not been validated and may need adjustment once Phase 9 (operational validation) runs. Changing a module weight requires touching the YAML file and re-running tests — low friction in absolute terms, but the weights are not yet evidence-derived, so the evolution path to calibrated weights is a future program, not a current workflow. The `EVALUATION-DEFERRED` threshold situation is the same: the system knows what calibration is needed (registered, classified, with disposition) but has not done it yet.

**Evidence:**
- `dal/state/player_gameweek_state.py:28–42` — `_GOVERNED_ROLLING_COLS` frozenset with governance requirement comment
- `intelligence/scoring/signals.py:36–103` — `load_manifest` dynamically builds from registry; no signal names hardcoded in logic
- `signals/registry/weight_registry.yaml:8–12` — explicit note that module weights are `PROVISIONAL-EDITORIAL`, deferred to Phase 9

**Improvement action:** Document the Phase 9 operational validation pathway as a concrete checklist in `docs/governance/` — specifying what evidence is required to promote each `EVALUATION-DEFERRED` threshold and each `PROVISIONAL-EDITORIAL` weight to `EVALUATION-DERIVED`. This converts the deferred items from an implicit backlog into a governed forward roadmap.

---

## Aggregate Score Table

| # | Category | Priority | Weight | Score | Weighted Score |
|---|----------|----------|--------|-------|----------------|
| 1 | Architecture & Layer Integrity | CRITICAL | 1.5 | 4 | 6.00 |
| 2 | Contracts & Schemas | CRITICAL | 1.5 | 5 | 7.50 |
| 3 | Runtime Simplicity | CRITICAL | 1.5 | 4 | 6.00 |
| 4 | Naming & Vocabulary | IMPORTANT | 1.0 | 4 | 4.00 |
| 5 | Docstrings & Comments | IMPORTANT | 1.0 | 3 | 3.00 |
| 6 | Test Quality & Enforcement | CRITICAL | 1.5 | 4 | 6.00 |
| 7 | Configuration & Control Plane | IMPORTANT | 1.0 | 4 | 4.00 |
| 8 | Repository Usability | IMPORTANT | 1.0 | 4 | 4.00 |
| 9 | Operational Governance | IMPORTANT | 1.0 | 4 | 4.00 |
| 10 | Maintainability & Evolution Safety | CRITICAL | 1.5 | 4 | 6.00 |
| | **Total** | | **12.5** | | **50.50** |

**Weighted aggregate score: 50.50 / 12.5 = 4.04**

---

## Critical Floor Check

| CRITICAL Category | Score | Floor Threshold (≤ 2) | Result |
|-------------------|-------|----------------------|--------|
| Architecture & Layer Integrity | 4 | ≤ 2 | PASS |
| Contracts & Schemas | 5 | ≤ 2 | PASS |
| Runtime Simplicity | 4 | ≤ 2 | PASS |
| Test Quality & Enforcement | 4 | ≤ 2 | PASS |
| Maintainability & Evolution Safety | 4 | ≤ 2 | PASS |

**Critical floor result: CLEAR — no CRITICAL category at or below 2. Assessment proceeds normally.**

---

## Overall Maturity Level Determination

**Weighted score: 4.04**

| Range | Level |
|-------|-------|
| 4.0 – 4.4 | **Operational** |

**Platform Maturity Level: Operational (Level 4)**

The platform operates as governed infrastructure. Layer boundaries are mechanically enforced, contracts are explicit and tested, the lifecycle gate is wired into the execution path, and provenance is complete. The primary gap separating this platform from Level 5 (Platform Mature) is that threshold calibration and module weight validation remain deferred to the 2026/27 program — meaning operational parameters are registered and documented but not yet evidence-derived. A second gap is the incomplete intelligence-layer import test and the pre-lens governance bypass. Neither represents a structural failure; both are deliberate deferrals with documented remediation paths.

---

## Top 5 Prioritised Improvement Actions

Ranked by rubric priority weight × estimated impact. CRITICAL-category items rank above IMPORTANT-category items of equal impact.

### Action 1 — Close the intelligence → studies import enforcement gap
**Rubric categories:** Architecture & Layer Integrity (CRITICAL, 1.5×), Test Quality (CRITICAL, 1.5×)
**File:** `tests/test_dal_architecture.py` or a new `tests/test_intelligence_architecture.py`
**Action:** Add an AST-based test scanning `intelligence/` for any import of `studies.*`. This is the only mechanically unenforced layer boundary rule and the highest-priority architectural gap.
**Effort:** Low (one test function following the existing pattern in `test_dal_architecture.py`)

### Action 2 — Close the pre-lens signal governance bypass
**Rubric categories:** Operational Governance (IMPORTANT, 1.0×), Maintainability (CRITICAL, 1.5×)
**File:** `intelligence/scoring/signals.py:125–130`
**Action:** Replace the silent `except GovernanceMetadataError: continue` with an explicit check against an allowlist of pre-lens signals. Signals absent from `evaluation_metadata.yaml` and absent from the allowlist should raise a `GovernanceMetadataError` rather than silently entering the scoring manifest.
**Effort:** Low-medium (define the allowlist, replace the exception handler, add a test)

### Action 3 — Update CONTEXT.md status table to reflect Phase 7 completion
**Rubric categories:** Repository Usability (IMPORTANT, 1.0×)
**File:** `CONTEXT.md` section 5
**Action:** Mark SYNTH-01 as `COMPLETE` (Phase 7, 2026-05-27), update lens statuses for studies with `approved` entries in `evaluation_metadata.yaml`, and update the Phase 11 section to reflect the 9-phase program completion noted in the threshold registry.
**Effort:** Low (documentation update only)

### Action 4 — Document Phase 9 validation pathway as a governed checklist
**Rubric categories:** Maintainability & Evolution Safety (CRITICAL, 1.5×), Configuration & Control Plane (IMPORTANT, 1.0×)
**File:** New `docs/governance/phase9-validation-roadmap.md` or extension of `threshold-registry.md`
**Action:** For each `EVALUATION-DEFERRED` threshold and each `PROVISIONAL-EDITORIAL` weight, document the concrete evidence required to promote to `EVALUATION-DERIVED`. This converts 12 deferred items from an implicit backlog into a governed, reviewable forward plan.
**Effort:** Medium (requires editorial decisions on methodology for each threshold)

### Action 5 — Docstring hygiene pass on weight_registry.yaml and state layer
**Rubric categories:** Docstrings & Comments (IMPORTANT, 1.0×)
**Files:** `signals/registry/weight_registry.yaml`, `dal/state/player_gameweek_state.py`
**Action:** Replace process-history references (`GAP-TRACE-*`, `Phase 3`, `Phase 6`, `SC-1 fix`) with self-contained one-sentence rationale. The test is whether a new engineer can understand the constraint by reading the file, without access to the operational convergence plan or git history.
**Effort:** Low-medium (editorial, no logic changes)

---

*Assessment completed: 2026-05-27. Next full assessment: 2026-11 (semi-annual cadence per rubric). Architecture spot-check recommended after any signal addition or registry schema change.*
