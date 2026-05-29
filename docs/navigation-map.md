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

**Four documents give you 80% of the picture:**

| Document | Answers |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | What is this system for? What does it not do? |
| [docs/architecture/system-model.md](architecture/system-model.md) | What is each part of the system responsible for? (3-plane model) |
| [docs/architecture/decision-lifecycle.md](architecture/decision-lifecycle.md) | How does a decision get made, end to end? |
| [dal/README.md](../dal/README.md) | What are the DAL layers and entry points? |

---

## Reading order by role

### New contributor (start here)

1. [docs/system-purpose.md](system-purpose.md) — mission, architectural intent, non-goals
2. [docs/architecture/system-model.md](architecture/system-model.md) — 3-plane model: what each component is for and what is missing
3. [docs/architecture/decision-lifecycle.md](architecture/decision-lifecycle.md) — full decision flow with failure modes
4. [docs/architecture/operational-flow.md](architecture/operational-flow.md) — 3-command execution sequence, entry points
5. [docs/research-lifecycle.md](research-lifecycle.md) — signal lifecycle: how a signal travels from EDA to scorer
6. [docs/registry-governance.md](registry-governance.md) — exploratory vs operational registries, lifecycle gate enforcement
7. [CONTEXT.md](../CONTEXT.md) — current project state, rules, and session orientation

### DAL contributor

1. `dal/fct/fct_contracts.py` — spine column definitions, dtypes, null rules, aggregation semantics (code-enforced)
2. `dal/feat/feat_contracts.py` + `dal/feat/feat_schema.py` — feature columns and Pandera schema
3. `dal/exceptions.py` — `ErrorCode` vocabulary, `DALContractViolation`
4. [docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md) — what downstream modules may and may not import
5. [dal/README.md](../dal/README.md) — layer overview and entry points

### Research contributor (lens studies, EDA, experiments)

1. [docs/system-purpose.md](system-purpose.md) — system question and research boundaries
2. [docs/research-lifecycle.md](research-lifecycle.md) — lifecycle states and promotion criteria
3. [signals/registry/SIGNAL_REGISTRY.md](../signals/registry/SIGNAL_REGISTRY.md) — governance registry: signal schema, lifecycle rules, update protocol
4. [signals/evaluation/EVAL_DESIGN.md](../signals/evaluation/EVAL_DESIGN.md) — **locked** success criteria and failure conditions (cannot be revised retrospectively)
5. [docs/studies/](studies/) — study designs and published results

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
| `dal/fct/fct_contracts.py`, `dal/validation/` | All DAL behavior: grain, column contracts, null semantics, dtype contracts, BGW/DGW invariants (code-enforced) |
| [signals/evaluation/EVAL_DESIGN.md](../signals/evaluation/EVAL_DESIGN.md) | Success criteria and failure conditions for 2025-26 methodology |
| [signals/registry/SIGNAL_REGISTRY.md](../signals/registry/SIGNAL_REGISTRY.md) | Lifecycle status for every named signal |
| [docs/research-lifecycle.md](research-lifecycle.md) | Signal lifecycle state definitions and promotion rules |
| [docs/registry-governance.md](registry-governance.md) | Exploratory vs operational registry semantics; lifecycle gate enforcement |
| [docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md) | Allowed and forbidden import patterns for downstream modules |
| [docs/governance/platform-rubric.md](governance/platform-rubric.md) | Platform maturity & maintainability assessment rubric — 10 categories, scoring methodology, maturity levels |
| [docs/governance/platform-assessment-2026-05.md](governance/platform-assessment-2026-05.md) | May 2026 platform assessment — Operational (Level 4), score 4.04, top gaps and improvement actions |
| [docs/governance/platform-improvement-plan.md](governance/platform-improvement-plan.md) | PLATFORM-01 improvement plan — 5 phases addressing assessment findings; no analytical changes |

### Operational reference

| Document | Use for |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | Orienting new contributors; scoping new research |
| [docs/architecture/system-model.md](architecture/system-model.md) | 3-plane conceptual model: Control · Execution · Measurement; component classification table |
| [docs/architecture/decision-lifecycle.md](architecture/decision-lifecycle.md) | Full decision flow: DAL → registry → intelligence → output → (future measurement) |
| [docs/architecture/operational-flow.md](architecture/operational-flow.md) | Running the system end to end |
| [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) | Scorer pipeline, registry consumption, rho weighting, explainability, weekly artifact lineage |
| [docs/architecture/explainability-model.md](architecture/explainability-model.md) | Scoring formula, signal selection rationale, rho weighting, independent verification steps |
| [docs/architecture/testing-strategy.md](architecture/testing-strategy.md) | Test categories, integration marker, make test vs make test-unit, import enforcement |
| [docs/architecture/layer-boundaries.md](architecture/layer-boundaries.md) | Component ownership boundaries, dependency direction, non-overlap rules |
| [docs/architecture/runtime-artifacts.md](architecture/runtime-artifacts.md) | What artifacts are produced, where they live, gitignore policy, bootstrap semantics |
| [docs/architecture/db-schema.md](architecture/db-schema.md) | Source database table and column reference |
| [dal/README.md](../dal/README.md) | DAL entry points and layer overview |
| [CONTEXT.md](../CONTEXT.md) | Project state and session orientation |

### Study record (permanent research artifacts)

| Document | Content |
|----------|---------|
| [docs/studies/rolling-xgi-horizon-study.md](studies/rolling-xgi-horizon-study.md) | Rolling xGI horizon study design |
| [docs/studies/results/minstab-01-results.md](studies/results/minstab-01-results.md) | MINSTAB-01 published results |
| [docs/studies/results/rolling-xgi-horizon-study-results.md](studies/results/rolling-xgi-horizon-study-results.md) | Rolling xGI published results |
| [docs/studies/results/rolling-xgi-real-validation.md](studies/results/rolling-xgi-real-validation.md) | Real validation results |
| [studies/operational/phase9_backtest.py](../studies/operational/phase9_backtest.py) | Phase 9 operational backtest — holdout validation GW 34–38 |

### Supplementary / transitional

| Document | Status | Notes |
|----------|--------|-------|
| `archive/architecture-boundaries.md` | Archived | Superseded by `architecture/layer-boundaries.md`. |
| `archive/SYSTEM_CONTEXT.md` | Archived | Superseded by `architecture/layer-boundaries.md`. |
| `archive/evaluation-framework.md` | Archived | Module map outdated (modules moved to `tests/helpers/`). Philosophy and metrics preserved with annotation. |
| `archive/research-program.md` | Archived | Scope boundaries absorbed into `system-purpose.md`. |
| `archive/stabilization/` | Archived | Wave history, risk register, Phase 11 execution plan, Phase 11 slice status. |
| `archive/DOC_MIGRATION_PLAN.md` | Archived | Documentation architecture migration plan — all six phases complete. |

### Archived (REPO-CONS-01 — 2026-05-27)

Working documents superseded by durable artifacts during the 9-phase program. Read-only historical record. See [docs/archive/README.md](archive/README.md) for the supersession table.

| File | Archived | Summary |
|------|----------|---------|
| [docs/archive/architecture-execution-plan.md](archive/architecture-execution-plan.md) | 2026-05-27 | Phase-by-phase execution plan — system is operational, plan complete |
| [docs/archive/synth01-design.md](archive/synth01-design.md) | 2026-05-27 | SYNTH-01 methodology decisions — superseded by `signals/evaluation/synth01_decisions.yaml` |
| [docs/archive/synth01-candidate-set.md](archive/synth01-candidate-set.md) | 2026-05-27 | SYNTH-01 candidate set — superseded by `signals/registry/synth01_candidates.yaml` |
| [docs/archive/lens-form-readiness.md](archive/lens-form-readiness.md) | 2026-05-27 | LENS-FORM readiness assessment — study complete, results in `studies/lenses/` |
| [docs/archive/minutes-stability-xgi-study.md](archive/minutes-stability-xgi-study.md) | 2026-05-27 | MINSTAB-01 design doc — superseded by `docs/studies/results/minstab-01-results.md` |

### Operational outputs

| File | Content |
|------|---------|
| [outputs/operational-baseline.md](../outputs/operational-baseline.md) | Phase 9 validation record — holdout backtest results, 2026/27 recommendations |

---

## Governance artifacts (not in docs/)

These files are active governance artifacts owned by their respective layers. They are **not** documentation — do not move them to `docs/`.

| File | Owned by | Purpose |
|------|----------|---------|
| [signals/registry/SIGNAL_REGISTRY.md](../signals/registry/SIGNAL_REGISTRY.md) | `signals/registry/` | Single source of truth for signal lifecycle status. Updated only at methodology milestones. |
| [signals/evaluation/EVAL_DESIGN.md](../signals/evaluation/EVAL_DESIGN.md) | `signals/evaluation/` | Locked success criteria for 2025-26 methodology. Cannot be revised retrospectively. |

---

## What to add here

When you add, move, or archive a document:

1. Add it to the appropriate section above.
2. If it's authoritative, add a row to the authority table.
3. If it's being superseded, add it to the supplementary/transitional table with a note.
4. Remove it from all sections when it moves to `archive/`.
