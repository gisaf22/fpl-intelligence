# Navigation Map

**Purpose:** Single index for all documentation in this repository. Start here.  
**Maintained:** Update this file whenever a document is added, moved, or archived.

---

## Quick orientation

fpl-intelligence is a governed analytical system for Fantasy Premier League. It has four layers:

```
dal/          → validated, deterministic (player_id, gw) spine
studies/      → analytical methodology: EDA, lenses, statistical kernels
signals/      → signal lifecycle governance and registry build pipeline
intelligence/ → player scoring and weekly reporting
```

**Three documents give you 80% of the picture:**

| Document | Answers |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | What is this system for? What does it not do? |
| [docs/architecture/operational-flow.md](architecture/operational-flow.md) | How do I run it end to end? |
| [docs/architecture/DAL_CONTRACT.md](architecture/DAL_CONTRACT.md) | What guarantees does the data layer provide? |

---

## Reading order by role

### New contributor (start here)

1. [docs/system-purpose.md](system-purpose.md) — mission, architectural intent, non-goals
2. [docs/architecture/operational-flow.md](architecture/operational-flow.md) — 3-command execution sequence, entry points
3. [docs/research-lifecycle.md](research-lifecycle.md) — signal lifecycle: how a signal travels from EDA to scorer
4. [docs/registry-governance.md](registry-governance.md) — exploratory vs operational registries, lifecycle gate enforcement
5. [CONTEXT.md](../CONTEXT.md) — current project state, rules, and session orientation

### DAL contributor

1. [docs/architecture/DAL_CONTRACT.md](architecture/DAL_CONTRACT.md) — authoritative behavioral contract (grain, aggregation rules, null semantics, invariants)
2. [docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md) — what downstream modules may and may not import
3. [docs/adr/007-bgw-team-semantics.md](adr/007-bgw-team-semantics.md) — BGW team_id temporal rule
4. [docs/adr/008-dgw-aggregation-rules.md](adr/008-dgw-aggregation-rules.md) — DGW aggregation and normalization
5. [docs/adr/009-first-cols-ordering.md](adr/009-first-cols-ordering.md) — FIRST_COLS semantic classification
6. [dal/state/STATE_CONTRACT.md](../dal/state/STATE_CONTRACT.md) — 30 derived state columns: causality, warmup, reliability

### Research contributor (lens studies, EDA, experiments)

1. [docs/system-purpose.md](system-purpose.md) — system question and research boundaries
2. [docs/research-lifecycle.md](research-lifecycle.md) — lifecycle states and promotion criteria
3. [signals/registry/SIGNAL_REGISTRY.md](../signals/registry/SIGNAL_REGISTRY.md) — governance registry: signal schema, lifecycle rules, update protocol
4. [signals/evaluation/EVAL_DESIGN.md](../signals/evaluation/EVAL_DESIGN.md) — **locked** success criteria and failure conditions (cannot be revised retrospectively)
5. [docs/adr/004-analytical-foundations.md](adr/004-analytical-foundations.md) — locked EDA-1 gate decisions (Spearman, GW bounds, population)
6. [docs/adr/005-signal-exclusions.md](adr/005-signal-exclusions.md) — locked EDA-2 signal exclusions
7. [docs/studies/](studies/) — study designs and published results

### Intelligence / scoring contributor

1. [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) — scorer pipeline, component weights, eligibility thresholds, non-goals
2. [docs/registry-governance.md](registry-governance.md) — what the scorer is allowed to consume and why
3. [docs/architecture/operational-flow.md](architecture/operational-flow.md) — lifecycle gate enforcement at runtime
4. [docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md) — allowed imports from `signals.lifecycle.*`

### Operational runner (running the system weekly)

1. [docs/architecture/operational-flow.md](architecture/operational-flow.md) — 3-command sequence: `make prepare`, `make build-registry`, `make weekly`
2. [Makefile](../Makefile) — all available `make` targets
3. [docs/registry-governance.md](registry-governance.md) — when a registry path is safe for operational use

---

## Document authority map

### Authoritative (single source of truth for their concern)

| Document | Authoritative for |
|----------|-------------------|
| [docs/architecture/DAL_CONTRACT.md](architecture/DAL_CONTRACT.md) | All DAL behavior: grain, aggregation rules, null semantics, dtype contracts, BGW/DGW semantics |
| [signals/evaluation/EVAL_DESIGN.md](../signals/evaluation/EVAL_DESIGN.md) | Success criteria and failure conditions for 2025-26 methodology |
| [signals/registry/SIGNAL_REGISTRY.md](../signals/registry/SIGNAL_REGISTRY.md) | Lifecycle status for every named signal |
| [docs/research-lifecycle.md](research-lifecycle.md) | Signal lifecycle state definitions and promotion rules |
| [docs/registry-governance.md](registry-governance.md) | Exploratory vs operational registry semantics; lifecycle gate enforcement |
| [docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md) | Allowed and forbidden import patterns for downstream modules |
| [docs/adr/](adr/) | All immutable architectural decisions (append-only; ADR-001 through ADR-010) |
| [docs/decisions/008_migration_phases.md](decisions/008_migration_phases.md) | Active architecture migration playbook (converts to ADR-011 when migration commits land) |

### Operational reference

| Document | Use for |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | Orienting new contributors; scoping new research |
| [docs/architecture/operational-flow.md](architecture/operational-flow.md) | Running the system end to end |
| [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) | Scorer pipeline, registry consumption, rho weighting, explainability, weekly artifact lineage |
| [docs/architecture/explainability-model.md](architecture/explainability-model.md) | Scoring formula, signal selection rationale, rho weighting, independent verification steps |
| [docs/architecture/testing-strategy.md](architecture/testing-strategy.md) | Test categories, integration marker, make test vs make test-unit, import enforcement |
| [docs/architecture/layer-boundaries.md](architecture/layer-boundaries.md) | Component ownership boundaries, dependency direction, non-overlap rules |
| [docs/architecture/runtime-artifacts.md](architecture/runtime-artifacts.md) | What artifacts are produced, where they live, gitignore policy, bootstrap semantics |
| [docs/architecture/db-schema.md](architecture/db-schema.md) | Source database table and column reference |
| [dal/README.md](../dal/README.md) | DAL entry points and layer overview |
| [dal/state/STATE_CONTRACT.md](../dal/state/STATE_CONTRACT.md) | 30 derived state columns with causality and warmup specs |
| [CONTEXT.md](../CONTEXT.md) | Project state and session orientation |

### Study record (permanent research artifacts)

| Document | Content |
|----------|---------|
| [docs/studies/minutes-stability-xgi-study.md](studies/minutes-stability-xgi-study.md) | MINSTAB-01 study design |
| [docs/studies/rolling-xgi-horizon-study.md](studies/rolling-xgi-horizon-study.md) | Rolling xGI horizon study design |
| [docs/studies/results/minstab-01-results.md](studies/results/minstab-01-results.md) | MINSTAB-01 published results |
| [docs/studies/results/rolling-xgi-horizon-study-results.md](studies/results/rolling-xgi-horizon-study-results.md) | Rolling xGI published results |
| [docs/studies/results/rolling-xgi-real-validation.md](studies/results/rolling-xgi-real-validation.md) | Real validation results |

### Supplementary / transitional

| Document | Status | Notes |
|----------|--------|-------|
| `archive/architecture-boundaries.md` | Archived (Phase C) | Superseded by `architecture/layer-boundaries.md`. |
| `archive/SYSTEM_CONTEXT.md` | Archived (Phase C) | Superseded by `architecture/layer-boundaries.md`. |
| [docs/adr/010-enforcement-contract.md](adr/010-enforcement-contract.md) | Authoritative | Frozen system contract. Lifecycle annotation added. Lives in `adr/` as ADR-010. |
| `archive/evaluation-framework.md` | Archived (Phase E) | Module map outdated (modules moved to `tests/helpers/`). Philosophy and metrics preserved with annotation. |
| `archive/research-program.md` | Archived (Phase E) | Scope boundaries absorbed into `system-purpose.md`. |
| `archive/stabilization/` | Archived (Phase E) | Wave history, risk register, Phase 11 execution plan. |
| [docs/stabilization/PHASE11_STATUS.md](stabilization/PHASE11_STATUS.md) | Active until S6 | Tracks the one remaining open Phase 11 slice. Archives when S6 completes. |

---

## Governance artifacts (not in docs/)

These files are active governance artifacts owned by their respective layers. They are **not** documentation — do not move them to `docs/`.

| File | Owned by | Purpose |
|------|----------|---------|
| [signals/registry/SIGNAL_REGISTRY.md](../signals/registry/SIGNAL_REGISTRY.md) | `signals/registry/` | Single source of truth for signal lifecycle status. Updated only at methodology milestones. |
| [signals/evaluation/EVAL_DESIGN.md](../signals/evaluation/EVAL_DESIGN.md) | `signals/evaluation/` | Locked success criteria for 2025-26 methodology. Cannot be revised retrospectively. |

---

## Current architecture migration status

The architecture migration defined in [docs/adr/006-layer-architecture.md](adr/006-layer-architecture.md) (frozen) and [docs/decisions/008_migration_phases.md](decisions/008_migration_phases.md) (active) is in progress.

**Completed:**
- `core/governance/` → `signals/lifecycle/` ✅
- `signals/eda/` → `studies/eda/` ✅
- `signals/lenses/` → `studies/lenses/` ✅
- `signals/experiments/` → `studies/experiments/` ✅
- `scorer/` → `intelligence/scoring/` ✅
- `report/` → `intelligence/reporting/` ✅
- `registry/` (storage residual) → `signals/registry/` ✅
- `core/signals/*`, `core/relationships/*`, `core/target/*` → `studies/kernels/` ✅

**Working tree (unstaged deletions — not yet committed):**
- `core/` directory deleted
- `registry/sections.py` deleted

**Remaining (per Decision 008):**
- Stage and commit the core/ deletions
- Convert `docs/decisions/008_migration_phases.md` to ADR-011 after migration commits land

Until migration commits land, `docs/decisions/008_migration_phases.md` remains active guidance. Do not treat it as historical.

---

## What to add here

When you add, move, or archive a document:

1. Add it to the appropriate section above.
2. If it's authoritative, add a row to the authority table.
3. If it's being superseded, add it to the supplementary/transitional table with a note.
4. Remove it from all sections when it moves to `archive/`.
