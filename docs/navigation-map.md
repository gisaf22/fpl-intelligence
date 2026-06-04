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

## Spine traversal

To trace a feature to a decision:

1. Start with `dal/feat/feat_schema.py::FEATURE_REGISTRY` for feature status and approved positions.
2. Resolve the feature and position in `signals/characterisation/signal_traceability.yaml`.
3. Use `analysis_paths` for the study/lens implementation.
4. Derive the finding key as `signal@lens:target[#POS]` and resolve the verdict in `signals/governance/evaluation_metadata.yaml`.
5. Search that key in `signals/governance/synth01_decisions.yaml` for composition decisions.
6. Search that key or listed `derived_from` values in `signals/governance/weight_registry.yaml` for intelligence usage.

If a feature has no evaluated traceability route, treat it as conditional/pre-lens and do not assume it is operationally governed.

**These documents give you 80% of the picture:**

| Document | Answers |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | What is this system for? What does it not do? |
| [docs/architecture/system-model.md](architecture/system-model.md) | What is each part of the system responsible for? (3-plane model) |
| [docs/architecture/adlc.md](architecture/adlc.md) | How is the model researched and chosen? (analysis lifecycle) |
| [docs/architecture/analytical-architecture.md](architecture/analytical-architecture.md) | What are the analytical objects and where is each governed? (object spine) |
| [docs/architecture/runtime-execution.md](architecture/runtime-execution.md) | How does a decision get made at runtime, end to end? |
| [dal/README.md](../dal/README.md) | What are the DAL layers and entry points? |

---

## Reading order by role

### New contributor (start here)

1. [docs/system-purpose.md](system-purpose.md) — mission, architectural intent, non-goals
2. [docs/architecture/system-model.md](architecture/system-model.md) — 3-plane model: what each component is for
3. [docs/architecture/adlc.md](architecture/adlc.md) — the analysis lifecycle: explore → validate → model → serve → monitor
4. [docs/architecture/runtime-execution.md](architecture/runtime-execution.md) — runtime flow with failure modes + the run sequence
5. [docs/signal-promotion-states.md](signal-promotion-states.md) — signal governance states: how a signal travels from EDA to scorer
6. [docs/registry-governance.md](registry-governance.md) — exploratory vs operational registries, lifecycle gate enforcement
7. [CONTEXT.md](../CONTEXT.md) — current project state, rules, and session orientation

### DAL contributor

1. `dal/fct/fct_contracts.py` — spine column definitions, dtypes, null rules, aggregation semantics (code-enforced)
2. `dal/feat/feat_contracts.py` + `dal/feat/feat_schema.py` — feature columns and Pandera schema
3. `dal/exceptions.py` — `ErrorCode` vocabulary, `DALContractViolation`
4. [docs/architecture/downstream-dependency-governance.md](architecture/downstream-dependency-governance.md) — what downstream modules may and may not import
5. [dal/README.md](../dal/README.md) — layer overview and entry points

### Research contributor (lens studies, EDA, experiments)

1. [docs/system-purpose.md](system-purpose.md) — system question and research boundaries
2. [docs/signal-promotion-states.md](signal-promotion-states.md) — signal governance states and promotion criteria
3. [signals/characterisation/SIGNAL_REGISTRY.md](../signals/characterisation/SIGNAL_REGISTRY.md) — governance registry: signal schema, lifecycle rules, update protocol
4. [signals/governance/EVAL_DESIGN.md](../signals/governance/EVAL_DESIGN.md) — **locked** success criteria and failure conditions (cannot be revised retrospectively)
5. [docs/decisions/](decisions/) — architectural decisions: why Spearman, why additive weighting
6. [docs/studies/](studies/) — study designs and published results

### Intelligence / scoring contributor

1. [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) — scorer pipeline, component weights, eligibility thresholds, non-goals
2. [docs/registry-governance.md](registry-governance.md) — what the scorer is allowed to consume and why
3. [docs/architecture/runtime-execution.md](architecture/runtime-execution.md) — lifecycle gate enforcement at runtime
4. [docs/architecture/downstream-dependency-governance.md](architecture/downstream-dependency-governance.md) — allowed imports from `signals.governance.*`

### Operational runner (running the system weekly)

1. [docs/architecture/runtime-execution.md](architecture/runtime-execution.md) — the run sequence (`python -m …`), entry points, failure modes
2. [docs/registry-governance.md](registry-governance.md) — when a registry path is safe for operational use

---

## Document authority map

### Authoritative (single source of truth for their concern)

| Document | Authoritative for |
|----------|-------------------|
| `dal/fct/fct_contracts.py`, `dal/validation/` | All DAL behavior: grain, column contracts, null semantics, dtype contracts, BGW/DGW invariants (code-enforced) |
| [signals/governance/EVAL_DESIGN.md](../signals/governance/EVAL_DESIGN.md) | Success criteria and failure conditions for 2025-26 methodology |
| [signals/characterisation/SIGNAL_REGISTRY.md](../signals/characterisation/SIGNAL_REGISTRY.md) | Lifecycle status for every named signal |
| [docs/signal-promotion-states.md](signal-promotion-states.md) | Signal governance state definitions and promotion rules |
| [docs/registry-governance.md](registry-governance.md) | Exploratory vs operational registry semantics; lifecycle gate enforcement |
| [docs/architecture/downstream-dependency-governance.md](architecture/downstream-dependency-governance.md) | Allowed and forbidden import patterns for downstream modules |
| [docs/governance/threshold-registry.md](governance/threshold-registry.md) | All operational thresholds: values, classifications, 2026/27 disposition |
| [docs/governance/evaluation-gate-criteria.md](governance/evaluation-gate-criteria.md) | Lens study gate definitions: what constitutes pass/fail at each gate |
| [docs/governance/eng-issues-2026.md](governance/eng-issues-2026.md) | Engineering issue backlog — 12 issues in 3 phases; sorted by blast radius |

### Architectural decisions

Bounded, immutable records of why key decisions were made. Read before changing evaluation methodology or scoring composition.

| Document | Decision |
|----------|----------|
| [docs/decisions/001-spearman-as-evaluation-metric.md](decisions/001-spearman-as-evaluation-metric.md) | Why Spearman rank correlation (not Pearson, RMSE, or AUC) |
| [docs/decisions/002-additive-weighted-scoring.md](decisions/002-additive-weighted-scoring.md) | Why additive weighted composition (not ML); equal-weight default rule |

### Operational reference

| Document | Use for |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | Orienting new contributors; scoping new research |
| [docs/architecture/system-model.md](architecture/system-model.md) | 3-plane conceptual model: Control · Execution · Measurement |
| [docs/architecture/adlc.md](architecture/adlc.md) | The analysis lifecycle: explore → validate → model → serve → monitor; mode tags; test contracts |
| [docs/architecture/analytical-architecture.md](architecture/analytical-architecture.md) | The analytical object spine: Entity → Signal → Feature → Analysis → Finding → Decision, and where each is governed |
| [docs/architecture/runtime-execution.md](architecture/runtime-execution.md) | Runtime flow + the run sequence: DAL → registry → intelligence → output |
| [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) | Scorer pipeline, registry consumption, rho weighting, explainability |
| [docs/architecture/explainability-model.md](architecture/explainability-model.md) | Scoring formula, signal selection rationale, independent verification steps |
| [docs/architecture/testing-strategy.md](architecture/testing-strategy.md) | Test categories, integration marker, unit vs full suite |
| [docs/architecture/test-coverage.md](architecture/test-coverage.md) | Invariant → validator → test status map (Verified / Partial / Unverified / Missing) |
| [docs/architecture/platform-capabilities.md](architecture/platform-capabilities.md) | The eight platform capabilities every design must address; the design-doc capabilities table |
| [docs/architecture/layer-boundaries.md](architecture/layer-boundaries.md) | Component ownership boundaries, dependency direction, non-overlap rules |
| [docs/architecture/runtime-artifacts.md](architecture/runtime-artifacts.md) | What artifacts are produced, where they live, gitignore policy |
| [docs/architecture/db-schema.md](architecture/db-schema.md) | Source database table and column reference |
| [docs/architecture/platform-evaluation-2026.md](architecture/platform-evaluation-2026.md) | Platform evaluation program: completed changes and one remaining study |
| [docs/foundations/representation-governance.md](foundations/representation-governance.md) | Transform admissibility rules: what operations are valid per signal temporal type |
| [docs/foundations/signal-ontology.md](foundations/signal-ontology.md) | 8 information classes; forward constraints for future research |
| [dal/README.md](../dal/README.md) | DAL entry points and layer overview |
| [CONTEXT.md](../CONTEXT.md) | Project state and session orientation |

### Study record (permanent research artifacts)

| Document | Content |
|----------|---------|
| [docs/studies/popthresh-01-design.md](studies/popthresh-01-design.md) | POPTHRESH-01 calibration study design — 60-min threshold validation; deferred to 2026/27 |
| [docs/studies/rolling-xgi-horizon-study.md](studies/rolling-xgi-horizon-study.md) | Rolling xGI horizon study design |
| [docs/studies/results/minstab-01-results.md](studies/results/minstab-01-results.md) | MINSTAB-01 published results |
| [docs/studies/results/rolling-xgi-horizon-study-results.md](studies/results/rolling-xgi-horizon-study-results.md) | Rolling xGI published results |
| [docs/studies/results/rolling-xgi-real-validation.md](studies/results/rolling-xgi-real-validation.md) | Real validation results |

### Archived (historical record only — read-only)

Complete working documents superseded by durable artifacts. See [docs/archive/README.md](archive/README.md) for the full supersession table.

| File | Superseded by |
|------|---------------|
| [docs/archive/operational-convergence-plan.md](archive/operational-convergence-plan.md) | All 9 phases complete; `threshold-registry.md` carries live governance |
| [docs/archive/state-representation-inventory.md](archive/state-representation-inventory.md) | `_GOVERNED_ROLLING_COLS` / `_COLUMN_META` in `dal/feat/feat_player_gameweek.py` |
| [docs/archive/minutes-stability-xgi-study.md](archive/minutes-stability-xgi-study.md) | `docs/studies/results/minstab-01-results.md` |
| [docs/archive/synth01-design.md](archive/synth01-design.md) | `signals/governance/synth01_decisions.yaml` |
| [docs/archive/synth01-candidate-set.md](archive/synth01-candidate-set.md) | `signals/characterisation/synth01_candidates.yaml` |
| [docs/archive/architecture-execution-plan.md](archive/architecture-execution-plan.md) | System operational; plan complete |

### Operational outputs

| File | Content |
|------|---------|
| [outputs/operational-baseline.md](../outputs/operational-baseline.md) | Phase 9 validation record — holdout backtest results, 2026/27 recommendations |

---

## Governance artifacts (not in docs/)

These files are active governance artifacts owned by their respective layers. They are **not** documentation — do not move them to `docs/`.

| File | Owned by | Purpose |
|------|----------|---------|
| [signals/characterisation/SIGNAL_REGISTRY.md](../signals/characterisation/SIGNAL_REGISTRY.md) | `signals/characterisation/` | Single source of truth for signal lifecycle status. Updated only at methodology milestones. |
| [signals/governance/EVAL_DESIGN.md](../signals/governance/EVAL_DESIGN.md) | `signals/governance/` | Locked success criteria for 2025-26 methodology. Cannot be revised retrospectively. |
| [signals/governance/weight_registry.yaml](../signals/governance/weight_registry.yaml) | `signals/governance/` | Operational scoring weights per (signal, position). Updated after SYNTH-01 re-run. |
| [signals/governance/evaluation_metadata.yaml](../signals/governance/evaluation_metadata.yaml) | `signals/governance/` | Per-signal lens findings, lifecycle states, downstream status. |

---

## What to add here

When you add, move, or archive a document:

1. Add it to the appropriate section above.
2. If it's authoritative, add a row to the authority table.
3. If it's a new architectural decision, add it to the decisions table.
4. If it's being archived, add it to the archived table and update [docs/archive/README.md](archive/README.md).
