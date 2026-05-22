# Documentation Architecture Migration Plan

**Created:** 2026-05-21  
**Based on:** Full documentation architecture assessment (50 files, ~10,388 lines)  
**Branch:** stabilization/dal-hardening  

---

## Goal

Converge the repository toward a compact, portfolio-grade documentation structure with:
- Low ambiguity (one source of truth per concept)
- Low duplication (no concept explained twice)
- High navigability (a reader can orient in one document)
- Clear authority boundaries (governance artifacts separated from reference docs)
- Correct content (no doc that actively misleads a code reviewer)

Verdict from assessment: **FEASIBLE WITH EXCEPTIONS**  
Exceptions: `docs/studies/` survives; `dal-contract.md` stays full-length; `SIGNAL_REGISTRY.md` and `EVAL_DESIGN.md` stay in `signals/`.

---

## Target Structure

```
docs/
├── adr/
│   ├── 001-minutes-certainty.md
│   ├── 002-stack-definition.md
│   ├── 003-team-id-resolution.md
│   ├── 004-analytical-foundations.md
│   ├── 005-signal-exclusions.md
│   ├── 006-layer-architecture.md
│   ├── 007-bgw-team-semantics.md
│   ├── 008-dgw-aggregation-rules.md
│   ├── 009-first-cols-ordering.md
│   └── 010-enforcement-contract.md
├── architecture/
│   ├── system-purpose.md              ← keep
│   ├── operational-flow.md            ← EXECUTION_GUIDE.md renamed
│   ├── layer-boundaries.md            ← architecture-boundaries.md updated + renamed
│   ├── dal-contract.md                ← DAL_CONTRACT.md (full 734 lines, keep)
│   ├── downstream-governance.md       ← DOWNSTREAM_DEPENDENCY_GOVERNANCE.md updated + renamed
│   ├── registry-governance.md         ← keep
│   ├── research-lifecycle.md          ← keep
│   ├── intelligence-layer.md          ← operational-intelligence.md renamed
│   ├── test-coverage.md               ← stabilization/TEST_COVERAGE.md relocated
│   └── db-schema.md                   ← DB_SCHEMA.md relocated
├── studies/
│   ├── minutes-stability-xgi-study.md
│   ├── rolling-xgi-horizon-study.md
│   └── results/
│       ├── minstab-01-results.md
│       ├── rolling-xgi-horizon-study-results.md
│       └── rolling-xgi-real-validation.md
├── navigation-map.md                  ← NEW (Phase B)
└── README.md                          ← NEW top-level docs entry point (Phase B)

Root level (unchanged):
  README.md                            ← update links in Phase A
  CONTEXT.md                           ← keep; stays at root

In-place governance artifacts (not docs/):
  dal/README.md
  dal/state/STATE_CONTRACT.md
  signals/registry/SIGNAL_REGISTRY.md  ← governance artifact, never moves to docs/
  signals/evaluation/EVAL_DESIGN.md    ← locked methodology gate, never moves to docs/

Archive:
  archive/stabilization/               ← docs/stabilization/ moved here (after S6)
```

---

## Phased Execution

### Phase A — Stop Documentation Drift (P0)

**Goal:** Eliminate incorrect governance and stale architectural guidance before restructuring. No document that actively misleads a code reviewer should survive past this phase.

| Item | File | Action |
|------|------|--------|
| A1 | `docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md` | Remove `core.*` imports and `registry.db` (both dead). Update header. Add `signals.lifecycle.*` and `studies.kernels.*`. |
| A2 | `docs/architecture/ENFORCEMENT_CONTRACT.md` | Add lifecycle supersession annotation at top only. Do not rewrite. |
| A3 | `README.md` | Fix pipeline table (registry/ gone; intelligence/ exists). Add `EXECUTION_GUIDE.md` to architecture links. Remove stale `architecture-boundaries.md` link. |
| A4 | `dal/DAL_CONTRACT.md` | Delete. It is a deprecated pointer (11 lines). `dal/README.md` already points to the canonical location. |
| A5 | `signals/registry/SIGNAL_REGISTRY.md` | Fix `Owned by: research/registry/` → `Owned by: signals/registry/`. |
| A6 | `signals/runs/README.md` | Delete. 1-line null placeholder. |
| A7 | `tests/stabilization/README.md` | Delete. 4-line null stub. |

**Done when:** No doc in the repo points to `core.*` imports, `registry.*` imports, or nonexistent ownership paths. README pipeline table matches actual directory structure.

---

### Phase B — Create the Navigation Spine (P0)

**Goal:** Create a clean onboarding path before moving any documents.

| Item | File | Action |
|------|------|--------|
| B1 | `docs/navigation-map.md` | ✅ DONE — created. Reading order by role (5 roles), authority map, governance artifacts section, migration status summary. |
| B2 | folder structure | ✅ DONE — `docs/adr/` created with `.gitkeep`. |
| B3 | path stabilization | ✅ DONE — renamed: `EXECUTION_GUIDE.md` → `architecture/operational-flow.md`, `operational-intelligence.md` → `architecture/intelligence-layer.md`, `DB_SCHEMA.md` → `architecture/db-schema.md`. Inbound links updated. |

**Done when:** A reader can orient in `docs/navigation-map.md`. `docs/adr/` exists. Three docs have been renamed with no content changes.

---

### Phase C — Consolidate Operational Architecture (P1)

**Goal:** Make the architecture layer the visible system center. Eliminate content scattered across overlapping docs.

| Item | File | Action |
|------|------|--------|
| C1 | `docs/architecture/layer-boundaries.md` | ✅ DONE — built. Four-layer model, per-layer ownership, non-overlap table, key boundary rules. `architecture-boundaries.md` and `SYSTEM_CONTEXT.md` archived. |
| C2 | `docs/architecture/intelligence-layer.md` | ✅ DONE — expanded. Added: registry consumption flow, `assert_operational_safe()` gate, rho-based signal filtering, weekly artifact lineage, explainability column contract. |
| C3 | `docs/architecture/runtime-artifacts.md` | ✅ DONE — created. Artifact map, registry/ lifecycle, scorer HTML, gitignore policy, fresh checkout bootstrap, lifecycle gate dependency. |

**Done when:** `layer-boundaries.md` is the single ownership reference. `SYSTEM_CONTEXT.md` and `architecture-boundaries.md` are archived. Runtime artifacts are documented.

---

### Phase D — ADR Migration (P1)

**Goal:** Separate immutable architectural decisions from active guidance.

| Item | Source | Target | Notes |
|------|--------|--------|-------|
| ADR-001 | `decisions/001_minutes_certainty.md` | `adr/001-minutes-certainty.md` | ✅ DONE |
| ADR-002 | `decisions/002_stack_definition.md` | `adr/002-stack-definition.md` | ✅ DONE |
| ADR-003 | `decisions/004_team_id_resolution.md` | `adr/003-team-id-resolution.md` | ✅ DONE |
| ADR-004 | `decisions/005_analytical_foundations.md` | `adr/004-analytical-foundations.md` | ✅ DONE |
| ADR-005 | `decisions/006_signal_exclusions.md` | `adr/005-signal-exclusions.md` | ✅ DONE |
| ADR-006 | `decisions/007_layer_architecture.md` | `adr/006-layer-architecture.md` | ✅ DONE |
| ADR-007 | `decisions/bgw_team_semantics.md` | `adr/007-bgw-team-semantics.md` | ✅ DONE |
| ADR-008 | `decisions/dgw_aggregation_rules.md` | `adr/008-dgw-aggregation-rules.md` | ✅ DONE |
| ADR-009 | `decisions/first_cols_ordering.md` | `adr/009-first-cols-ordering.md` | ✅ DONE |
| ADR-010 | `architecture/ENFORCEMENT_CONTRACT.md` | `adr/010-enforcement-contract.md` | ✅ DONE |

**Remaining:** `decisions/008_migration_phases.md` — ACTIVE. Convert to ADR-011 after the architecture migration commits land (core/ deletions staged and pushed). `docs/decisions/` has only this file.

---

### Phase E — Archive Historical Noise (P1)

**Goal:** Remove implementation history from the operational documentation space.

| Item | Action | Prerequisite |
|------|--------|--------------|
| `docs/stabilization/OVERVIEW.md` | ✅ DONE → `archive/stabilization/` | |
| `docs/stabilization/PHASE11_STATUS.md` | ⏳ DEFERRED — S6 still pending | Archives when S6 (conftest) completes |
| `docs/stabilization/RISKS.md` | ✅ DONE → `archive/stabilization/` | |
| `docs/stabilization/STABILIZATION_EXECUTION_PLAN.md` | ✅ DONE → `archive/stabilization/` | |
| `docs/stabilization/TEST_COVERAGE.md` | ✅ DONE → `docs/architecture/test-coverage.md` | |
| `docs/architecture/SYSTEM_CONTEXT.md` | ✅ DONE (Phase C) | |
| `docs/evaluation-framework.md` | ✅ DONE → `archive/` (note added re: dead module map) | |
| `docs/research-program.md` | ✅ DONE → `archive/` (scope absorbed into system-purpose.md) | |

**Do NOT delete archive docs** — the stabilization risk register and wave history are the only authoritative record of why specific DAL behaviors are what they are. `DAL_CONTRACT.md` references these decisions.

**Done when:** `docs/stabilization/` is empty and removed. `docs/` contains no implementation-history content.

---

### Phase F — Intelligence-First Polish (P2)

**Goal:** Make the project externally impressive. This is where portfolio quality jumps.

| Item | File | Action |
|------|------|--------|
| F1 | `docs/architecture/explainability-model.md` | ✅ DONE — scoring formula, signal selection rationale, rho weighting, within-position normalisation, independent verification steps. |
| F2 | `docs/architecture/testing-strategy.md` | ✅ DONE — 739 tests, category breakdown with file names, integration marker semantics, make test vs test-unit, import enforcement. |
| F3 | Registry lineage in HTML | ✅ DONE — `ScorerOutput` extended with `registry_path` + `registry_meta`; runner loads `build_metadata.json`; renderer outputs provenance footer (path, build timestamp, GW cutoff, signal counts, version). 13 scorer tests pass. |

**Done when:** A reviewer can understand the system's testing philosophy and explainability contract from two documents without reading source code.

---

## Completion Criteria (Full)

| Phase | Done when |
|-------|-----------|
| A | No doc references `core.*` imports, `registry.*` imports, or nonexistent paths. README pipeline table matches actual structure. |
| B | `docs/navigation-map.md` exists and is accurate. `docs/adr/` folder exists. Three docs renamed without content change. |
| C | `layer-boundaries.md` is the single layer ownership reference. `SYSTEM_CONTEXT.md` and `architecture-boundaries.md` archived. Runtime artifacts documented. |
| D | 10 ADRs in `docs/adr/`. `docs/decisions/` empty except `008_migration_phases.md`. |
| E | `docs/stabilization/` removed. `docs/` free of implementation history. |
| F | Explainability model and testing strategy documented. |

## Governance Rules (Post-Consolidation)

1. `docs/adr/` is append-only. ADRs are never modified after creation. New decisions supersede old ones via new ADRs that reference the superseded entry.
2. Any document that references an import path or file path must be verified on every architecture-change PR. The `core.*` failure happened because no one verified path accuracy when `core/` was deleted.
3. `docs/navigation-map.md` is updated whenever a doc is added, moved, or archived.
4. `signals/registry/SIGNAL_REGISTRY.md` and `signals/evaluation/EVAL_DESIGN.md` are never moved to `docs/`. Their location encodes their ownership.
5. Every new study design document goes to `docs/studies/`. Results go to `docs/studies/results/`. No exception.
6. `docs/decisions/008_migration_phases.md` converts to ADR-011 the commit after the architecture migration lands. It does not remain as active guidance after that point.

---

## What NOT To Do

- Do not compress `DAL_CONTRACT.md` into a summary. Its length is load-bearing.
- Do not merge `docs/studies/` into `docs/architecture/`. Research artifacts are not architectural documentation.
- Do not move `SIGNAL_REGISTRY.md` or `EVAL_DESIGN.md` into `docs/`. They are governance artifacts owned by `signals/`.
- Do not delete historical ADR-worthy decisions without converting them first.
- Do not over-normalize into a tiny docs tree. The goal is low ambiguity and high navigability, not minimum file count.
