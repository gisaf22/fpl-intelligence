# Operational Convergence Plan — FPL Intelligence System

**Status:** ACTIVE  
**Issued:** 2026-05-26  
**Revised:** 2026-05-27 — re-sequenced to governance-first; Phases 1–9 complete; Consolidation Pass next  
**Author:** Analytics Governance  
**Classification:** Governance Program Document

---

## Revision Note (2026-05-27)

The original plan sequenced SYNTH-01 execution (composition weight derivation) immediately after Phase 4. This has been revised.

**Reason:** The system's biggest remaining weakness is not lack of synthesis — it is fragmented governance legibility. Analytical knowledge about signal validity, rejection basis, scope restrictions, and caveats is distributed across multiple documents and layers with no unified cross-layer view. The intelligence modules still hardcode weights with no runtime traceability to governance evidence. Before introducing composition weights (which make the system harder to interpret, not easier), the governance semantics need to be consolidated and made operationally legible end-to-end.

**New sequencing principle:** Analytical legibility and governance traceability before composition sophistication.

SYNTH-01 changes the system's nature from *representation governance* to *operational composition*. Once composition weights are derived, the operational outputs become harder to audit. The synthesis layer should operate on a foundation that is already fully explainable — not one that will be made explainable after the fact.

**Completed under original sequencing (unchanged):**
- Phase 1 — Contradiction Cleanup ✅
- Phase 3 — Representation Inventory Lock ✅
- Phase 4 — SYNTH-01 Readiness ✅ (frozen; execution deferred)

**Revised remaining sequence:**
- Phase 4 — Governance Consolidation ✅ *(complete 2026-05-27)*
- Phase 5 — Signal Traceability Matrix ✅ *(complete 2026-05-27)*
- Phase 6 — Operational Alignment ✅ *(complete 2026-05-27)*
- Phase 7 — SYNTH-01 Execution *(was Phase 5; deferred)*
- Phase 8 — Registry Rebuild ✅ *(complete 2026-05-27)*
- Phase 9 — Operational Validation ✅ *(complete 2026-05-27)*

---

## Purpose

This document is an executable governance program, not a research or feature roadmap.

The system has completed substantial analytical work: ontology classification, EDA characterization, representation governance, STATE cleanup, evaluation standardization, and synthesis candidate set construction. The remaining problem is not analytical gap — it is **governance propagation**: the knowledge the system has accumulated about signals is fragmented, the intelligence modules do not trace to governance evidence at runtime, and there is no unified view of what the system knows, position by position.

This plan closes the gap between analytical governance knowledge and operational runtime behavior across a sequenced program that prioritizes legibility before composition.

---

## Scope Boundaries

**In scope:**
- Governance propagation from evaluation evidence into runtime behavior
- Cross-layer traceability and operational legibility
- Removal of evidence-contradicted operational logic
- Runtime defensibility and operational explainability
- Representation enforcement at the STATE and consumer layers
- Synthesis execution and registry rebuild (deferred to Phases 7–8)
- Threshold classification and calibration from evidence

**Explicitly out of scope:**
- New signal engineering
- New predictive models beyond SYNTH-01 partial rho evaluation
- Orchestration systems or feature stores
- Infrastructure scaling
- Automation-heavy solutions
- Any work that does not advance governance propagation or operational legibility

---

## Governance Gap Inventory

| ID | Gap | Severity | Status | Phase |
|----|-----|----------|--------|-------|
| G-OPS-01 | All intelligence module weights are `PROVISIONAL-EDITORIAL` without analytical derivation | CRITICAL | Open | 6, 7 |
| G-OPS-02 | `MIN_RHO=0.15` in `signals.py:31` conflicts with CI-gate methodology; incorrectly caveats 3 informative candidates | CRITICAL | Annotated (Phase 1) | 8 |
| G-OPS-03 | 16 `REJECTED-BEHAVIORAL` columns materialized in STATE | HIGH | **Resolved (Phase 3)** | — |
| G-OPS-04 | `points_roll3/5` consumed by `captain.py` and `value.py` despite target leakage | HIGH | **Resolved (Phase 1)** | — |
| G-OPS-05 | `behavioral_reason`, `source_gate_decisions`, `lifecycle_state`, `leakage_risk` absent from runtime-accessible metadata | HIGH | **Resolved (Phase 4)** | — |
| G-OPS-06 | No lifecycle filtering gate at STATE layer | MEDIUM | **Resolved (Phase 3)** | — |
| G-OPS-07 | Editorial thresholds without provenance: `_DIVERGENCE_THRESHOLD=20.0`, `_MIN_MINUTES_ROLL3=45.0`, `minutes_trend` 30-min boundary | MEDIUM | Classified (Phase 1) | 9 |
| G-OPS-08 | `minutes_trend` editorial threshold with no LENS-AVAIL backing | MEDIUM | **Resolved (Phase 3)** | — |
| G-OPS-09 | No synthesis candidate set formally defined | HIGH | **Resolved (Phase 4)** | — |
| G-OPS-10 | Operational registry reflects pre-SYNTH-01 EDA; no composition weights | HIGH | Open | 7, 8 |
| G-OPS-11 | DAL curated contracts declared but not enforced at builder entry | LOW | Partially resolved (Phase 3) | — |
| G-OPS-12 | No unified cross-layer view of what each signal means, can say, and who consumes it | HIGH | **Resolved (Phase 5)** — `signal_traceability.yaml` + `signal-traceability-matrix.md` produced | — |
| G-OPS-13 | Intelligence modules have no runtime path to governance evidence — decisions are untraceable | HIGH | **Partially resolved (Phase 4/5)** — `get_signal_governance()` callable; consumer module map produced; runtime wiring deferred to Phase 6 | 6 |

---

## Critical Path (Revised)

```
Phase 1 (Contradiction Cleanup)          ✅ COMPLETE
  → Phase 3 (Representation Lock)        ✅ COMPLETE
    → Phase 4 (SYNTH-01 Readiness)       ✅ COMPLETE — frozen, execution deferred
      → Phase 4 (Governance Consolidation) ✅ COMPLETE
        → Phase 5 (Signal Traceability Matrix) ✅ COMPLETE
          → Phase 6 (Operational Alignment)    ✅ COMPLETE
            → Phase 7 (SYNTH-01 Execution)   ← deferred; requires Phases 4–6 complete
              → Phase 8 (Registry Rebuild)
                → Phase 9 (Operational Validation)
```

Note on numbering: Phase numbers 4–6 in this revised plan correspond to new work not covered by the original Phase 2 (Runtime Metadata Propagation). Phase 2 of the original plan was designed but not implemented; its implementation tasks are absorbed into Phase 4 (Governance Consolidation) of this plan.

---

## Completed Phases — Summary Record

### Phase 1 — Contradiction Cleanup ✅

**Completed:** 2026-05-26

Removed `points_roll3/5` from `captain.py` and `value.py` as form inputs (target leakage, G-EDA7-02). Annotated `MIN_RHO=0.15` conflict at `signals.py:31` (G-OPS-02). Produced `docs/governance/threshold-registry.md` classifying all 12 operational thresholds across 6 modules as `EVALUATION-DERIVED`, `PROVISIONAL-EDITORIAL`, `UNJUSTIFIED`, or `CONTRADICTS-GATE`.

### Phase 3 — Representation Inventory Lock ✅

**Completed:** 2026-05-26

Removed 16 `REJECTED-BEHAVIORAL` columns from STATE (29 → 13 derived columns). Added governance assertion in `build_player_gameweek_state()` enforcing `_GOVERNED_ROLLING_COLS` at build time. Restricted `minutes_trend` to availability domain only (`_AVAILABILITY_DOMAIN_ONLY`). Produced `docs/governance/state-representation-inventory.md` with per-column gate citations and rejection log.

### Phase 4 (original) — SYNTH-01 Readiness ✅

**Completed:** 2026-05-27

Extracted 14 synthesis candidates from `evaluation_metadata.yaml`. Produced `docs/governance/synth01-candidate-set.md` (14 entries: 6 DEF, 7 MID, 1 FWD single-signal, 0 GK deferred). Identified two HIGH REDUNDANCY pairs (`ownership_count × transfers_in` at DEF rho=0.794 and MID rho=0.831). Made all 5 composition methodology decisions in `docs/governance/synth01-design.md`. Froze `signals/registry/synth01_candidates.yaml`. **SYNTH-01 execution deferred pending Phases 4–6 of revised plan.**

### Phase 4 — Governance Consolidation ✅

**Completed:** 2026-05-27

Closed G-OPS-05 and G-OPS-13 (runtime governance metadata). `GovernanceMetadata` dataclass and `get_signal_governance()` confirmed callable and tested. Added `LeakageViolationError` alongside `LifecycleViolationError` in `signals/lifecycle/lifecycle.py`. Updated `_assert_governance_compliance()` in `intelligence/scoring/signals.py` to raise `LifecycleViolationError` (excluded lifecycle, blocked downstream) and `LeakageViolationError` (direct leakage) as hard failures.

Cross-document consistency audit complete:
- `evaluation_metadata.yaml` ↔ `synth01-candidate-set.md` ↔ `synth01_candidates.yaml`: fully consistent — all 14 candidates with matching rho/CI/block values
- `state-representation-inventory.md` ↔ `_GOVERNED_ROLLING_COLS`: column sets identical (13); stale rho values in Evidence column documented as **GAP STATE-INVENTORY-EVIDENCE-01** (deferred to Phase 5)
- `threshold-registry.md` ↔ `intelligence/*.py`: 4 stale line-number references corrected (CAPT-T-01, TRANS-T-01, FIX-T-01, REG-T-03)

Both test files complete: `tests/test_evaluation_metadata.py` (5 Phase 4 tests added) and `tests/test_runtime_metadata_propagation.py` (8 Phase 4 tests added). Full suite: **827 passed, 2 skipped**.

### Phase 5 — Signal Traceability Matrix ✅

**Completed:** 2026-05-27

Produced the unified cross-layer governance view of every (signal, position) pair in the system. Closed G-OPS-12 (no unified cross-layer signal view).

**Artifacts produced:**
- `signals/registry/signal_traceability.yaml` — machine-readable matrix; 80 entries (60 from evaluation_metadata.yaml across 4 lenses + 20 STATE-only defensive/availability/fixture entries). Flat (signal, position) list with 17 fields per entry.
- `docs/governance/signal-traceability-matrix.md` — human-readable matrix covering all 60 evaluated entries and 20 STATE-governed extensions; Consumer Module Map section covering all 6 intelligence modules.
- `tests/test_traceability_completeness.py` — 10 tests covering: evaluated signal coverage, `_GOVERNED_ROLLING_COLS` coverage, candidate operational_role completeness, consumer module or note requirement, structural field presence, vocabulary conformance, excluded-implies-blocked consistency, and positional coverage.

**Key governance findings documented:**
- 8 governance gaps enumerated (GAP-TRACE-01 through GAP-TRACE-08) covering scope violations, governance inconsistencies, and unwired governed candidates
- `fdr_avg` identified as most critical: excluded at all positions but consumed at 20–40% weight in 3 modules (GOVERNANCE INCONSISTENCY — Phase 6 must resolve)
- `xgi_roll3/xgi_roll5` scope violation at FWD documented (Phase 6 positional guard required)
- 12 defensive signal candidates (DEF/GK scope) and `fixture_context` (all positions) enumerated as GOVERNED BUT NOT WIRED
- `minutes_roll8` DEF/MID candidates (rho=0.219, 0.222) identified as highest-evidence governed signals not yet consumed

Full suite after Phase 5: **837 passed, 2 skipped**.

### Phase 6 — Operational Alignment ✅

**Completed:** 2026-05-27

Wired all intelligence modules to the governance registry. Closed G-OPS-01 (hardcoded weights) and G-OPS-13 (no runtime traceability).

**Artifacts produced:**
- `signals/registry/weight_registry.yaml` — machine-readable weight registry; all weights marked `PROVISIONAL-EDITORIAL`; 4 modules (captain, value, fixtures, transfers)
- `intelligence/weight_registry.py` — hard-fail loader (`WeightRegistryError` if any entry missing)
- `intelligence/provenance.py` — `score_provenance()` returning complete audit trail (weights, STATE values, registry sources, signal_traceability.yaml caveats)
- `tests/test_runtime_consumer_alignment.py` — 7 test classes (42 new tests)

**GAP-TRACE resolutions:**
- GAP-TRACE-01: FWD scope guard for xgi_roll3/xgi_roll5 in captain.py, value.py, transfers.py (`.where(~fwd_mask, 0.0)` → neutral 0.5)
- GAP-TRACE-02: fdr_avg removed from all scoring weights; binary DGW flag from `fixture_context` replaces it in captain, fixtures, transfers
- GAP-TRACE-03: `minutes_roll8` wired to availability.py as `long_horizon_flag` for DEF/MID (rho=0.219, 0.222)
- GAP-TRACE-06: fixtures.py DGW detection migrated from spine `is_dgw` to STATE `fixture_context`
- GAP-TRACE-04/05/07/08: annotated as blocked until Phase 7 SYNTH-01

**Signal traceability consumer map updated:** fdr_avg entries cleared; fixture_context entries wired (fixtures, captain, transfers); minutes_roll8 DEF/MID entries wired (availability); xgi FWD entries marked scope-guard applied.

Full suite after Phase 6: **879 passed, 2 skipped**.

---

## Phase 4 — Governance Consolidation

### Objective

Complete the runtime governance metadata layer. Ensure every governance document is internally consistent and cross-referenced with every other. Close the gap between governance evidence (documented in analytical artifacts) and governance enforcement (implemented in runtime code).

### Why This Phase Exists

Three structural problems remain after the completed phases:

1. `GovernanceMetadata` was designed in the original plan but never implemented. The `get_signal_governance()` function does not exist. The runtime cannot answer "why is this signal here?" — that question can only be answered by reading offline documents.

2. Governance documents were produced independently across phases. The threshold registry, state representation inventory, evaluation metadata, and signal ontology have never been cross-checked for internal consistency. Contradictions between documents may exist.

3. Any signal with `lifecycle_state=excluded` can still be loaded by a runtime consumer without triggering a hard failure. The lifecycle enforcement chain is partially procedural rather than code-enforced.

### Required Tasks

**4.1 — Implement `GovernanceMetadata` schema**

Add a `GovernanceMetadata` dataclass to `signals/lifecycle/schema.py`:

| Field | Type | Source |
|-------|------|--------|
| `signal` | str | registry |
| `position` | str | registry |
| `lifecycle_state` | str | `evaluation_metadata.yaml` |
| `downstream_status` | str | `evaluation_metadata.yaml` |
| `behavioral_reason` | str | `evaluation_metadata.yaml` |
| `source_gate_decisions` | list[str] | `evaluation_metadata.yaml` |
| `leakage_risk` | str | `evaluation_metadata.yaml` |
| `rho_pooled` | float \| None | `evaluation_metadata.yaml` |
| `ci_lower` | float \| None | `evaluation_metadata.yaml` |
| `ci_upper` | float \| None | `evaluation_metadata.yaml` |

**4.2 — Implement `get_signal_governance(signal, position) -> GovernanceMetadata`**

In `signals/evaluation/governance.py`:
- Returns `GovernanceMetadata` for every signal-position pair in `evaluation_metadata.yaml`
- Raises `GovernanceMetadataError` (not None, not a warning) if the pair is absent
- Callable from any consumer module for traceability

**4.3 — Add runtime lifecycle assertions to the scoring gate**

In `intelligence/scoring/signals.py`, add assertions at signal load time:
- `lifecycle_state == "excluded"` → raises `LifecycleViolationError`
- `downstream_status == "blocked"` → raises `LifecycleViolationError`
- `leakage_risk == "direct"` → raises `LeakageViolationError`

These must be hard failures, not warnings. A signal that fails these checks must not participate in any scoring computation.

**4.4 — Cross-document consistency audit**

Audit the following pairs for contradictions or gaps:

| Document A | Document B | Check |
|-----------|-----------|-------|
| `threshold-registry.md` | `player_gameweek_state.py` | Every inline threshold in STATE has a registry entry |
| `state-representation-inventory.md` | `_GOVERNED_ROLLING_COLS` in code | Column sets are identical |
| `evaluation_metadata.yaml` | `synth01-candidate-set.md` | Every candidate in the MD has a matching `lifecycle_state=candidate` entry in YAML |
| `evaluation_metadata.yaml` | `synth01_candidates.yaml` | rho, CI, and block_stability values match exactly |
| `threshold-registry.md` | `intelligence/*.py` | Every constant classified in the registry exists at the stated file:line |

Document any inconsistency found. Resolve or record as a named gap with a phase reference.

**4.5 — Write `tests/test_evaluation_metadata.py` and `tests/test_runtime_metadata_propagation.py`**

`test_evaluation_metadata.py` must verify:
- Every entry in `evaluation_metadata.yaml` has `behavioral_reason`, `source_gate_decisions`, `leakage_risk` populated (no null or empty)
- Every entry with `lifecycle_state=candidate` has `rho_pooled` not null
- Every entry with `lifecycle_state=candidate` has a matching entry in `synth01_candidates.yaml`

`test_runtime_metadata_propagation.py` must verify:
- `get_signal_governance()` returns complete `GovernanceMetadata` for all entries
- Missing entries raise `GovernanceMetadataError`
- Loading a signal with `lifecycle_state=excluded` raises `LifecycleViolationError`
- Loading a signal with `leakage_risk=direct` raises `LeakageViolationError`

### Dependencies
- Phases 1, 3, 4 (original) complete — all prerequisite governance artifacts exist

### Verification Criteria
- `GovernanceMetadata` defined in `signals/lifecycle/schema.py`
- `get_signal_governance()` callable and tested
- Runtime assertions fire for excluded and blocked signals
- Cross-document consistency audit complete with no unresolved contradictions
- Both test files pass

### Failure Conditions
- `get_signal_governance()` returns None for a missing entry rather than raising
- Runtime assertions implemented as warnings rather than hard failures
- Consistency audit skipped or flagged contradictions left unresolved

---

## Phase 5 — Signal Traceability Matrix

### Objective

Produce a unified, position-level view of what the system knows about every signal it has evaluated. Make governance legible end-to-end: any stakeholder should be able to look up any signal at any position and read, in one place, what it means, what the evidence says, what role it plays, what its limitations are, and which runtime modules consume it.

### Why This Phase Exists

Governance knowledge is currently fragmented across: `evaluation_metadata.yaml`, `state-representation-inventory.md`, `threshold-registry.md`, `synth01-candidate-set.md`, `signals/registry/SIGNAL_REGISTRY.md`, and the intelligence module code. No single artifact answers the question: "What does the system know about `xgi_roll3` at DEF?" A reader must consult four or five documents to reconstruct the full picture.

This fragmentation is a legibility risk, not just a documentation problem. When SYNTH-01 eventually runs, its decisions will need to be traced back to governance evidence. If that evidence is not consolidated and readable before synthesis begins, the traceability chain breaks at the point where it matters most.

This phase closes that gap by building a governance matrix that is the single authoritative source for the question: *what does the system know about this signal at this position?*

### Required Tasks

**5.1 — Define the traceability matrix schema**

Each entry in the matrix covers one signal × position pair and includes:

| Field | Description |
|-------|-------------|
| `signal` | Signal identifier (e.g. `xgi_roll3`) |
| `position` | Position (DEF / MID / FWD / GK) |
| `meaning` | Plain-language description of what the signal measures |
| `scope` | Where the signal is valid (e.g. "DEF/GK only"; "all outfield") |
| `evaluation_lens` | Which lens study evaluated it |
| `evaluation_target` | What the lens evaluated against |
| `lifecycle_state` | `candidate` / `excluded` / `not_applicable` |
| `downstream_status` | `eligible` / `caveated` / `blocked` |
| `rho_pooled` | Spearman rho from lens study (null if not evaluated) |
| `rejection_basis` | For excluded signals: the specific gate failure or governance rule |
| `caveat` | For caveated signals: the specific limitation |
| `redundancy` | Known high-redundancy relationships at this position |
| `operational_role` | What role this signal plays in the intelligence layer (form, availability, market, none) |
| `consumer_modules` | Which intelligence modules reference this signal |
| `threshold_dependencies` | Any operational threshold (from threshold-registry.md) that governs use of this signal |

**5.2 — Produce the matrix for all evaluated signals**

Populate the matrix for every signal-position pair in `evaluation_metadata.yaml`. This covers all signals from LENS-FORM, LENS-AVAIL, LENS-MARKET, and LENS-FIXTURE-GW. Both candidates and excluded signals are included — the rejected signals need to be legible too, so that their exclusion basis is findable in one place rather than buried in EDA documents.

Output: `docs/governance/signal-traceability-matrix.md` (human-readable) and `signals/registry/signal_traceability.yaml` (machine-readable).

**5.3 — Extend the matrix to STATE-governed columns not in evaluation metadata**

The following STATE columns are governed but have no lens evaluation entry (they are defensive signals studied at DEF/GK scope under LENS-FORM team context, but their individual gate evaluations are documented in lens study CSVs rather than evaluation_metadata.yaml):
- `xgc_roll3`, `xgc_roll5` (DEF/GK scope)
- `goals_conceded_roll3`, `goals_conceded_roll5` (DEF/GK scope)
- `clean_sheets_roll3`, `clean_sheets_roll5` (DEF/GK scope)
- `minutes_trend` (availability domain only; PROVISIONAL-EDITORIAL)
- `fixture_context` (contemporaneous label; candidate)

Add entries for these signals to the matrix. Source their evidence from the state representation inventory and lens study CSVs.

**5.4 — Produce a consumer module map**

Document, for each intelligence module (`captain.py`, `value.py`, `fixtures.py`, `availability.py`, `transfers.py`, `scoring/signals.py`):
- Which signals it currently consumes (by name)
- Which STATE columns it reads
- Which of those signals are governed candidates vs. provisional vs. unjustified

This map is the diagnostic tool for Phase 6 (Operational Alignment). It makes visible any signal that is being consumed without governance authority, or any governed signal that is not being consumed.

Output: a section in `docs/governance/signal-traceability-matrix.md` titled "Consumer Module Map."

**5.5 — Write `tests/test_traceability_completeness.py`**

Assertions:
- Every signal in `evaluation_metadata.yaml` has a corresponding entry in `signal_traceability.yaml`
- Every signal in `_GOVERNED_ROLLING_COLS` has a traceability entry
- Every entry with `lifecycle_state=candidate` has a non-null `operational_role`
- Every entry with `operational_role` not null has at least one `consumer_module` listed (or a documented note that it is governed but not yet wired)

### Dependencies
- Phase 4 complete (GovernanceMetadata schema and get_signal_governance() must exist before the matrix can assert runtime-traceability)

### Verification Criteria
- `signal-traceability-matrix.md` covers all evaluated signal-position pairs
- `signal_traceability.yaml` is machine-readable and complete
- Consumer module map covers all 6 intelligence modules
- `test_traceability_completeness.py` passes
- A reader can answer "what is `xgi_roll3 DEF` and why is it here?" from one document

### Failure Conditions
- Matrix populated for candidates only — excluded signals omitted
- Consumer module map missing any module
- Machine-readable YAML absent (human-readable MD only is insufficient for Phase 6 automation)

---

## Phase 6 — Operational Alignment

### Objective

Align all intelligence and scoring modules to consume the governed registry rather than hardcoded constants. Implement the `score_provenance()` function. Ensure every runtime consumption decision has a traceable governance source. This phase does not require SYNTH-01 weights — provisional editorial weights are acceptable as placeholders, but the loading architecture must be registry-driven.

### Why This Phase Exists

The intelligence modules currently hardcode weight dicts that are disconnected from the governance registry. Even if the registry correctly documents the governance state, the runtime ignores it. Phase 6 wires the governance layer into the operational layer — not by changing what the weights are, but by changing where they come from. When SYNTH-01 weights are eventually derived (Phase 7), they slot into the registry and propagate automatically to all consumers.

This phase makes the system's architecture **synthesis-ready** without requiring synthesis to have happened yet.

### Required Tasks

**6.1 — Replace hardcoded weight dicts in all intelligence modules**

For each module, replace the editorial weight dict with a registry-derived load:

| Module | Current hardcoded weights | Action |
|--------|--------------------------|--------|
| `captain.py:35-43` | `form: 0.35, involvement: 0.30, fixture: 0.20, minutes: 0.15` | Load from registry; retain current values as provisional entries |
| `value.py:35-39` | `efficiency: 0.50, form: 0.30, consistency: 0.20` | Load from registry; retain current values as provisional |
| `fixtures.py:38-42` | `fdr_opportunity: 0.40, team_attack: 0.35, dgw_bonus: 0.25` | Load from registry; retain current values as provisional |
| `availability.py` | Risk thresholds (30.0, 60.0, 20.0) | Retain as `UNJUSTIFIED` with annotations; Phase 9 calibration |

The registry entries for these weights are initially populated with the current editorial values, explicitly marked `PROVISIONAL-EDITORIAL`. The architecture change is in the loading path, not the values.

Weight loading must:
- Fail hard (not silently default) if a registry entry is missing
- Log the governance source at load time for traceability
- Be position-specific where the signal traceability matrix (Phase 5) documents position-specific behavior

**6.2 — Align `intelligence/scoring/signals.py` to governed registry**

Update `signals.py` to:
- Load signals via the registry exclusively (no direct column name references)
- Apply `GovernanceMetadata` assertions from Phase 4 at every signal load
- Block any signal with `lifecycle_state=excluded` or `downstream_status=blocked` from loading

**6.3 — Implement `score_provenance(player_id, gw, module) -> dict`**

Returns, for any player at any GW from any module:
- Which signals contributed to the score
- What weight each received
- What governance source authorized that weight (registry entry reference)
- The player's STATE values for each contributing signal
- Any caveats from the signal traceability matrix that apply at that position

This function is the primary tool for operational defensibility in Phase 9. It must be callable without modifying any production code path.

**6.4 — Write `tests/test_runtime_consumer_alignment.py`**

Assertions:
- No intelligence module contains a hardcoded weight value (pattern test)
- All modules load weights from the registry
- `signals.py` rejects excluded lifecycle signals with `LifecycleViolationError`
- `score_provenance()` returns complete data for a synthetic test case covering all modules

**6.5 — Update the signal traceability matrix consumer module map**

After wiring, update the consumer module map in Phase 5 to reflect the actual post-Phase-6 consumption state. Any signal that was consumed without governance authority and has now been removed must be marked removed with the date.

### Dependencies
- Phase 5 complete (signal traceability matrix needed to identify all governed signals and their intended consumer modules)
- Phase 4 complete (GovernanceMetadata and runtime assertions needed before wiring)

### Verification Criteria
- No intelligence module has a hardcoded weight dict (verified by pattern test)
- All weights have a registry source traceable to a governance entry
- `score_provenance()` returns complete data for all modules
- Full test suite passes (all existing tests plus new tests from Phases 4–6)
- Signal traceability consumer module map updated to reflect Phase 6 state

### Failure Conditions
- Any module silently defaults to editorial weights when a registry entry is missing
- `score_provenance()` returns incomplete data (missing governance references)
- Phase 6 architecture change leaves any module still reading hardcoded constants

---

## Phase 7 — SYNTH-01 Execution ✅

**Completed:** 2026-05-27

Evaluated independent contribution of all 14 frozen candidates via partial Spearman rho (controlling for all other same-position × same-lens candidates). Resolved all redundancy pairs and within-window families. Derived composition weights. Ran FDR moderation sensitivity check.

**Artifacts produced:**
- `signals/evaluation/synth01_decisions.yaml` — 14 `G-SYNTH1-*` decisions (10 approved, 3 excluded-redundant, 1 FWD-single-signal)
- `signals/evaluation/evaluation_metadata.yaml` v3.0 — `synth01_decision`, `composition_weight`, `composition_role` added to all 14 candidate entries
- `studies/synthesis/synth01_study.py` — reproducible study script
- `studies/runs/SYNTH-01-20260527_*/` — run artifacts

**Key findings:**
- DEF × FORM: xgi_roll3 (primary, w=0.50) + xgi_roll5 (secondary, w=0.50). Both windows complement; equal-weight preferred (evidence composite improved only 0.0006 over equal-weight).
- DEF × AVAIL: minutes_roll8 sole signal (primary, w=1.0). Bivariate partial_rho=0.219.
- DEF × MARKET: transfers_in (primary, w=0.50) + purchase_price (secondary, w=0.50). **ownership_count EXCLUDED-REDUNDANT** (partial_rho=0.009 < 0.02 — SUBSTITUTE confirmed at DEF).
- MID × FORM: **xgi_roll3 EXCLUDED-REDUNDANT** (partial_rho=0.009). xgi_roll5 sole retained (primary, w=1.0). Composite rho=0.157 — **does not clear naive baseline (0.158)** by 0.001; documented gap.
- MID × AVAIL: minutes_roll3 (primary, w=0.50) + minutes_roll8 (secondary, w=0.50). **minutes_roll5 EXCLUDED-REDUNDANT** (partial_rho=0.012). Short + long windows are complementary; medium window absorbed.
- MID × MARKET: transfers_in (primary, w=0.50) + ownership_count (secondary, w=0.50). **ownership_count COMPLEMENTARY at MID** (partial_rho=0.035 > 0.02 — retained, contrasting with DEF SUBSTITUTE). MID composite clears naive baseline (0.173 vs 0.158).
- **FDR moderation: MATERIAL** — FDR quartile changes signal rank ordering in > 15% of cases. Flagged for Phase 8 registry rebuild.

All equal-weight compositions: evidence-derived weights did not improve over equal-weight by ≥0.02 rho in any group; equal weights applied per design doc §Decision 2 protocol.

Full suite after Phase 7: **879 passed, 2 skipped**.

---

## Phase 7 — SYNTH-01 Execution (original deferred spec)

**Prerequisite:** Phases 4, 5, and 6 must be complete before Phase 7 begins.

**Rationale for deferral:** SYNTH-01 generates composition weights that make the system harder to interpret and audit. Phases 4–6 ensure the governance foundation is fully legible before composition is introduced. A synthesis layer built on an opaque foundation produces results that cannot be defended. After Phase 6, the system can answer "why is this signal here?" for every signal. SYNTH-01 then extends that to "what does this signal contribute relative to others?" — a question that only makes sense once the individual signals are already traceable.

**Candidate set:** Frozen in `signals/registry/synth01_candidates.yaml` (2026-05-27). 14 entries: 6 DEF, 7 MID, 1 FWD (single-signal only), 0 GK (deferred to LENS-GK).

### Required Tasks (summary — original Phase 5 specification applies)

**7.1 — Evaluate independent contribution**

For each candidate, compute partial Spearman rho against the target, controlling for all other same-lens candidates at the same position. Report `partial_rho`, `partial_ci_lower`, `partial_ci_upper`, `contribution_class` (`primary`, `secondary`, `redundant`).

**7.2 — Resolve high-redundancy pairs**

For `ownership_count × transfers_in` at DEF and MID: compute marginal gain of each signal over the other. Apply protocol from `synth01-candidate-set.md §High-Redundancy Resolution Protocol`:
- marginal_gain < 0.02 → SUBSTITUTE; retain transfers_in (higher rho at both positions)
- marginal_gain ≥ 0.02 → COMPLEMENTARY; retain both

**7.3 — Determine composition weights**

Derive normalized weights from partial rho magnitudes. Constraint: no signal receives weight > 0.60. If constrained, document the binding constraint. Produce bootstrap CIs for all weights.

**7.4 — Run moderation sensitivity check**

Test whether FDR quartile materially changes signal rank ordering (> 15% of cases). If material, flag for Phase 8 implementation.

**7.5 — Issue `G-SYNTH1-*` decisions**

For every candidate, issue a formal decision in `signals/evaluation/synth01_decisions.yaml`:
```
G-SYNTH1-[NN]: [signal]-[position]
Decision: APPROVED-PRIMARY | APPROVED-SECONDARY | EXCLUDED-REDUNDANT | EXCLUDED-INSUFFICIENT
Weight: [value] (CI: [lower]-[upper])
Evidence: partial_rho=[value]; marginal_gain=[value]
```

**7.6 — Update `evaluation_metadata.yaml`**

Add `synth01_decision`, `composition_weight`, and `composition_role` to each entry.

### Verification Criteria
- `G-SYNTH1-*` decisions exist for all 14 candidates
- No weight is a round number without derivation
- All SUBSTITUTE pairs resolved
- `synth01_decisions.yaml` complete

---

## Phase 8 — Registry Rebuild ✅ Complete (2026-05-27)

**Prerequisite:** Phase 7 complete. ✅

Rebuild the operational signal registry from `synth01_decisions.yaml`. Replace pre-SYNTH-01 registry with a `registry_version: "synth01"` artifact. Resolve the `MIN_RHO=0.15` conflict (G-OPS-02): if the three affected signals receive `APPROVED-*` decisions, remove `MIN_RHO` entirely; if any receive `EXCLUDED-*` decisions, the exclusion must derive from a `G-SYNTH1-*` decision, not the magnitude threshold. Mark the registry `frozen_at` with a timestamp. Update `evaluation-gate-criteria.md`.

**Phase 8 completion record (2026-05-27):**

- `SIGNAL_REGISTRY.md` updated to `registry_version: synth01` (v2.0). Synthesis Status set for all 14 SYNTH-01 entries — 10 approved, 3 excluded-redundant, 1 FWD single-signal. Every approved entry traces to a `G-SYNTH1-*` decision in `signals/evaluation/synth01_decisions.yaml`.
- `MIN_RHO=0.15` removed from `intelligence/scoring/signals.py` (G-OPS-02 resolved). All three affected signals received `APPROVED-*` decisions; removal was the correct resolution. CI gate is now the sole authority for scoring manifest confirmation.
- `signals/evaluation/evaluation_metadata.yaml` `lifecycle_state` updated for 14 entries: `approved` for 10 APPROVED-* decisions; `excluded` for 3 EXCLUDED-REDUNDANT decisions. `approved` added to `lifecycle_state_vocab`.
- `docs/governance/evaluation-gate-criteria.md` updated to v2.0: MIN_RHO section updated to resolved.
- `signals/registry/weight_registry.yaml` updated to v2.0: FDR moderation MATERIAL finding annotated; `synth01_composition_weights` pointer added; `resolution_phase` moved to 9 (module-level calibration deferred).
- FDR moderation: MATERIAL finding documented in weight registry. Implementation deferred to Phase 9.
- `test_scorer_signals.py`: `test_confirmed_signals_meet_rho_threshold` replaced by `test_confirmed_signals_have_non_null_rho` (CI gate).

### Verification Criteria
- ✅ Registry version = `synth01`; every weight traces to a `G-SYNTH1-*` decision
- ✅ `MIN_RHO` removed (all three affected signals received APPROVED-* decisions)
- ✅ `test_registry_contract.py` and `test_registry_semantics.py` pass

---

## Phase 9 — Operational Validation ✅ Complete (2026-05-27)

**Prerequisite:** Phase 8 complete.

**Phase 9 completion record (2026-05-27):**

Context: 25/26 season fully ingested (GW 1–38, 841 players, 29,747 player_history rows).
SYNTH-01 had used GW_MAX=33; GW 34–38 are true holdout data.

Study: `studies/operational/phase9_backtest.py`
Results: `outputs/phase9_backtest_results.yaml`
Baseline: `outputs/operational-baseline.md`

| Group | SYNTH-01 rho | Holdout rho | Δ | Verdict |
|---|---|---|---|---|
| DEF × FORM | 0.119 | 0.114 | −0.005 | STABLE |
| DEF × AVAIL | 0.219 | 0.208 | −0.010 | STABLE |
| DEF × MARKET | 0.172 | 0.204 | +0.032 | IMPROVED |
| MID × FORM | 0.157 | 0.171 | +0.013 | IMPROVED |
| MID × AVAIL | — | 0.208 | — | STABLE |
| MID × MARKET | 0.172 | 0.117 | −0.055 | DEGRADED |
| FWD × MARKET | 0.155 | −0.095 | −0.250 | REVERSED (n=89, p=0.374, non-significant) |

5 of 7 groups stable or improved. AVAIL signals are most robust. MID × MARKET shows end-of-season decay. FWD purchase_price reversed in holdout (non-significant, small n; already flagged G3-WEAK in SYNTH-01).

FDR moderation: MATERIAL verdict from SYNTH-01 stands unrefuted; insufficient holdout GWs to re-validate.

**Top recommendations for 2026/27:**
- P1: Implement FDR stratification (SYNTH-01 MATERIAL)
- P1: Restrict FWD purchase_price to GW 1–30 or add phase-conditional caveat
- P2: Expand lens studies to GK position
- P2: Re-run SYNTH-01 on 25/26 full-season data

---

## Phase Sequencing Summary

| Phase | Name | Status | Prerequisite | Key artifacts |
|-------|------|--------|-------------|---------------|
| 1 | Contradiction Cleanup | ✅ Complete | None | `threshold-registry.md` |
| 3 (orig) | Representation Inventory Lock | ✅ Complete | Phase 1 | `state-representation-inventory.md` |
| 4 (orig) | SYNTH-01 Readiness | ✅ Complete (frozen) | Phase 3 | `synth01-candidate-set.md`, `synth01-design.md`, `synth01_candidates.yaml` |
| **4** | **Governance Consolidation** | ✅ Complete | Phases 1, 3, 4 | `LeakageViolationError`, runtime assertions, cross-doc audit, test files |
| **5** | **Signal Traceability Matrix** | ✅ Complete | Phase 4 | `signal-traceability-matrix.md`, `signal_traceability.yaml` |
| **6** | **Operational Alignment** | ✅ Complete | Phase 5 | `weight_registry.yaml`, registry loader, `score_provenance()`, 879 tests |
| **7** | **SYNTH-01 Execution** | ✅ Complete | Phases 4–6 | `synth01_decisions.yaml`, `evaluation_metadata.yaml` v3.0 |
| **8** | **Registry Rebuild** | ✅ Complete | Phase 7 | `SIGNAL_REGISTRY.md` v2.0; MIN_RHO removed; `evaluation_metadata.yaml` v3.0 lifecycle states |
| **9** | **Operational Validation** | ✅ Complete | Phase 8 | `outputs/operational-baseline.md`; `phase9_backtest_results.yaml` |
| **C** | **Consolidation Pass** | Deferred | Phase 9 | Archived docs, simplified terminology, culled tests |

---

## Editorial Logic Disposition

The following editorial logic is **temporary** and must be replaced by the phase indicated. No other editorial logic is acceptable in the operational runtime after Phase 9 completes.

| Logic item | Location | Temporary acceptable? | Replacement phase |
|---|---|---|---|
| Captain weights (form 0.35, etc.) | `captain.py:35-43` | YES — Phase 6 wires architecture | Phase 7 (weights), Phase 6 (loading path) |
| Value weights (efficiency 0.50, etc.) | `value.py:35-39` | YES | Phase 7 (weights), Phase 6 (loading path) |
| Fixture weights (fdr 0.40, etc.) | `fixtures.py:38-42` | YES | Phase 7 (weights), Phase 6 (loading path) |
| `MIN_RHO=0.15` | `signals.py:31` | YES — annotated conflict | Phase 8 |
| `_DIVERGENCE_THRESHOLD=20.0` | `availability.py:42` | YES — UNJUSTIFIED annotation | Phase 9 |
| `_MIN_MINUTES_ROLL3=45.0` (captain) | `captain.py:47` | YES — UNJUSTIFIED annotation | Phase 9 |
| `minutes_trend` 30-min boundary | `player_gameweek_state.py` | YES — PROVISIONAL annotation | Phase 9 |
| `HAUL_THRESHOLD_PTS=12` | `geometry.py:62` | YES — geometry classification only | Phase 9 |

**Not acceptable at any point:**
- `points_roll3/5` as form input to any intelligence module
- Any `REJECTED-BEHAVIORAL` representation consumed without an explicit override annotation

---

## Governance Traceability Chain

After Phase 9 completes, the following chain must be demonstrable for any operational decision:

```
Player rank for GW N
  └── composite_score(player, gw, module)         ← score_provenance() (Phase 6)
        └── signal_value × weight (per signal)
              ├── signal_value ← STATE representation
              │     └── governed by: state-representation-inventory.md (Phase 3)
              ├── weight ← operational registry
              │     ├── provisional: PROVISIONAL-EDITORIAL entry (Phase 6)
              │     └── post-synth: G-SYNTH1-* decision (Phase 7)
              │           └── evidence: evaluation_metadata.yaml (Phase 4)
              └── signal semantics ← signal-traceability-matrix.md (Phase 5)
                    └── meaning, scope, caveats, consumer modules
```

The `score_provenance()` function (Phase 6) is the mechanism for demonstrating this chain on demand. The signal traceability matrix (Phase 5) is the reference document for interpreting what each element in the chain means.

---

## Consolidation Pass (after Phase 9)

**Prerequisite:** Phase 9 complete — system is analytically validated.

**Rationale:** The governance program accumulated planning artifacts, enterprise-scale vocabulary, and audit tests that are disproportionate to a personal analytics project. This pass sheds that overhead once the analytical work is done and the system is stable.

**Tasks:**

| Task | What |
|---|---|
| Archive planning docs | Move `synth01-candidate-set.md`, `synth01-design.md`, `threshold-registry.md`, `state-representation-inventory.md`, `signal-traceability-matrix.md`, this document to `docs/archive/` — machine-readable YAMLs stay in place |
| Terminology sweep | Replace enterprise vocabulary throughout live files: "feature" not "signal", "feature registry" not "signal traceability matrix", "placeholder weight" not "PROVISIONAL-EDITORIAL", "data leakage check" not `LeakageViolationError` where it appears in docs/comments |
| Test cull | Remove governance audit tests (cross-document YAML field completeness, traceability coverage assertions); keep analytical correctness tests (STATE builds, scoring correctness, lifecycle gates) |
| Scope close | Drop ChatGPT-suggested plans (observability telemetry, RFC process, UX governance, experimental sandbox, model risk contracts, meta-governance) permanently — not deferred, not future phases |

**Not a plan.** No YAML registries, no verification criteria tables, no phase dependencies. Run it as a checklist once.

---

*This document is the authority for sequencing, verification, and failure conditions of the operational convergence program. Deviations from phase ordering or verification criteria require an explicit governance decision recorded as an amendment to this document.*
