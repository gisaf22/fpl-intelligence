# Navigation Map

**Purpose:** Single index for all documentation in this repository. Start here.  
**Maintained:** Update this file whenever a document is added, moved, or archived.

---

## Quick orientation

fpl-intelligence is a governed analytical system for Fantasy Premier League. Its core layers:

```
dal/          → validated, deterministic (player_id, gw) spine
research/     → analytical methodology: foundation EDA, family lenses, statistical kernels
model/        → governance decisions: decision-of-record, promotion, traceability (governance) + composition weights (assemble)
domain/       → shared leaf: FPL scoring rules, decision contract, registry schema/loaders
serve/        → decision specs (captain/value/transfers) + the decision engine
```

## Spine traversal

To trace a feature to a decision:

1. Start with `dal/feat/feat_schema.py::FEATURE_REGISTRY` for feature status and approved positions.
2. Resolve the feature and position in the owning family study,
   `research/families/{form,market,availability,fixture}/validate/`.
3. Read the machine verdict in that family's `evidence.yaml` and the hand-authored judgment in its
   `annotations.yaml`.
4. Search the signal in `model/assemble/synth01_decisions.yaml` for composition decisions
   (superseded as a *ranking* input by ADR-011; retained as measurement).
5. For the live ranking path, read `serve/{captain,value,transfers}.py` — they rank on
   `model/predictions.py::assemble_forecast` columns directly, not on any weight registry.

If a feature has no evaluated traceability route, treat it as conditional/pre-lens and do not assume it is operationally governed.

**These documents give you 80% of the picture:**

| Document | Answers |
|----------|---------|
| [docs/system-purpose.md](system-purpose.md) | What is this system for? What does it not do? |
| [docs/architecture/adlc.md](architecture/adlc.md) | How is the model researched and chosen? (analysis lifecycle) |
| [docs/PROJECT.md](PROJECT.md) | What was built, what was found, and how a decision gets made at runtime |
| [dal/README.md](../dal/README.md) | What are the DAL layers and entry points? |

---

## Reading order by role

### New contributor (start here)

1. [docs/system-purpose.md](system-purpose.md) — mission, architectural intent, non-goals
2. [docs/architecture/adlc.md](architecture/adlc.md) — the analysis lifecycle: explore → validate → model → serve → monitor
3. [docs/PROJECT.md](PROJECT.md) — the research record: what each layer is, what it found, where it stands
4. [CONTEXT.md](../CONTEXT.md) — current project state, structure, and document hierarchy
5. [CLAUDE.md](../CLAUDE.md) — the standing rules and the session start-up read order (auto-loaded each session)

### DAL contributor

1. `dal/fct/fct_contracts.py` — spine column definitions, dtypes, null rules, aggregation semantics (code-enforced)
2. `dal/feat/feat_contracts.py` + `dal/feat/feat_schema.py` — feature columns and Pandera schema
3. `dal/exceptions.py` — `ErrorCode` vocabulary, `DALContractViolation`
4. [docs/architecture/downstream-dependency-governance.md](architecture/downstream-dependency-governance.md) — what downstream modules may and may not import
5. [dal/README.md](../dal/README.md) — layer overview and entry points

### Research contributor (lens studies, EDA, experiments)

1. [docs/system-purpose.md](system-purpose.md) — system question and research boundaries
2. [model/governance/EVAL_DESIGN.md](../model/governance/EVAL_DESIGN.md) — **locked** success criteria and failure conditions (cannot be revised retrospectively)
3. [docs/decisions/](decisions/) — architectural decisions: why Spearman, why additive weighting
4. [docs/studies/](studies/) — study designs and published results

### Intelligence / scoring contributor

1. [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) — scorer pipeline, component weights, eligibility thresholds, non-goals
2. [docs/architecture/downstream-dependency-governance.md](architecture/downstream-dependency-governance.md) — allowed imports from downstream modules

### Operational runner (running the system weekly)

1. `python -m dal.pipeline run` — build the mart (requires the live DB)
2. `python -m operational.recommend --target-gw {N}` — the composition root for a weekly run; see
   [docs/PROJECT.md](PROJECT.md) §3 for its call chain

---

## Document authority map

### Authoritative (single source of truth for their concern)

| Document | Authoritative for |
|----------|-------------------|
| `dal/fct/fct_contracts.py`, `dal/validation/` | All DAL behavior: grain, column contracts, null semantics, dtype contracts, BGW/DGW invariants (code-enforced) |
| [model/governance/EVAL_DESIGN.md](../model/governance/EVAL_DESIGN.md) | Success criteria and failure conditions for 2025-26 methodology |
| `research/families/*/validate/evidence.yaml` | Machine verdict (`decision_class`) for every tested signal-position cell |
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
| [docs/architecture/adlc.md](architecture/adlc.md) | The analysis lifecycle: explore → validate → model → serve → monitor; mode tags; test contracts |
| [docs/architecture/intelligence-layer.md](architecture/intelligence-layer.md) | Scorer pipeline, registry consumption, rho weighting, explainability |
| [docs/architecture/explainability-model.md](architecture/explainability-model.md) | Scoring formula, signal selection rationale, independent verification steps |
| [docs/architecture/testing-strategy.md](architecture/testing-strategy.md) | Test categories, integration marker, unit vs full suite |
| [docs/architecture/test-coverage.md](architecture/test-coverage.md) | Invariant → validator → test status map (Verified / Partial / Unverified / Missing) |
| [docs/architecture/platform-capabilities.md](architecture/platform-capabilities.md) | The eight platform capabilities every design must address; the design-doc capabilities table |
| [docs/architecture/layer-boundaries.md](architecture/layer-boundaries.md) | Component ownership boundaries, dependency direction, non-overlap rules |
| [docs/architecture/db-schema.md](architecture/db-schema.md) | Source database table and column reference |
| [docs/foundations/representation-governance.md](foundations/representation-governance.md) | Transform admissibility rules: what operations are valid per signal temporal type |
| [docs/foundations/signal-ontology.md](foundations/signal-ontology.md) | 8 information classes; forward constraints for future research |
| [dal/README.md](../dal/README.md) | DAL entry points and layer overview |
| [CONTEXT.md](../CONTEXT.md) | Project state, structure, and document hierarchy |
| [CLAUDE.md](../CLAUDE.md) | Standing rules ("never break these") + session start-up read order; auto-loaded |

### Study record (permanent research artifacts)

| Document | Content |
|----------|---------|
| [docs/studies/popthresh-01-design.md](studies/popthresh-01-design.md) | POPTHRESH-01 calibration study design — 60-min threshold validation; deferred to 2026/27 |
| [docs/studies/rolling-xgi-horizon-study.md](studies/rolling-xgi-horizon-study.md) | Rolling xGI horizon study design |
| [docs/studies/results/minstab-01-results.md](studies/results/minstab-01-results.md) | MINSTAB-01 published results |
| [docs/studies/results/rolling-xgi-horizon-study-results.md](studies/results/rolling-xgi-horizon-study-results.md) | Rolling xGI published results |
| [docs/studies/results/rolling-xgi-real-validation.md](studies/results/rolling-xgi-real-validation.md) | Real validation results |

### Operational outputs

| File | Content |
|------|---------|
| [outputs/operational-baseline.md](../outputs/operational-baseline.md) | Phase 9 validation record — holdout backtest results, 2026/27 recommendations |

---

## Governance artifacts (not in docs/)

These files are active governance artifacts owned by their respective layers. They are **not** documentation — do not move them to `docs/`.

| File | Owned by | Purpose |
|------|----------|---------|
| [model/governance/EVAL_DESIGN.md](../model/governance/EVAL_DESIGN.md) | `model/governance/` | Locked success criteria for 2025-26 methodology. Cannot be revised retrospectively. |
| `research/families/*/validate/{evidence,annotations}.yaml` | `research/families/` | Per-signal lens findings: machine verdict + hand-authored judgment. |
| [model/assemble/synth01_decisions.yaml](../model/assemble/synth01_decisions.yaml) | `model/assemble/` | SYNTH-01 composition decisions. Superseded as a ranking input by ADR-011; retained as measurement. |

---

## What to add here

When you add, move, or archive a document:

1. Add it to the appropriate section above.
2. If it's authoritative, add a row to the authority table.
3. If it's a new architectural decision, add it to the decisions table.
4. If a document is fully superseded, delete it (git history preserves it) and fix inbound links — do not keep a parallel archive of stale docs.
