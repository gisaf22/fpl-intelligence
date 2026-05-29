# Layer Boundaries

**Authoritative for:** component ownership, dependency direction, cross-cutting concerns.  
**Supersedes:** `docs/architecture-boundaries.md`, `docs/architecture/SYSTEM_CONTEXT.md`.

> **Note on planes vs. layers.** This document describes the 4-layer import hierarchy (DAL → studies → signals → intelligence), which governs dependency direction and import rules. The import hierarchy is not the same as the conceptual role of each component. For the question "what is each part of the system *for*?", see [system-model.md](system-model.md). The registry, for instance, is part of the Control Plane in the conceptual model — not a pipeline step. Tests are structural validation — not the Measurement Plane.

---

## System architecture

```
Source database (fpl.db — populated by fpl-ingest)
    ↓
dal/          — deterministic (player_id, gw) spine
    ↓
studies/      — analytical methodology (EDA, lenses, kernels, experiments)
    ↓
signals/      — lifecycle governance and registry build pipeline
    ↓
intelligence/ — player scoring and weekly reporting
```

Dependency direction is strictly one-way. No layer imports from a layer above it. `intelligence/` also reads `dal/` directly for current-gameweek data — this is permitted; the prohibition is on `dal/` depending on upper layers, not the reverse.

---

## Layer ownership

### DAL (`dal/`)

**Owns:** Raw data transformation into the canonical `(player_id, gw)` gameweek-grain spine.

| Sub-layer | Concern |
|---|---|
| `staging/` | Column rename, type cast, null standardisation — no joins, no aggregation |
| `intermediate/` | Join staging outputs into enriched fixture-grain records |
| `fct/` | Aggregate fixture-grain to gameweek-grain; complete spine with BGW rows |
| `feat/` | Derive rolling windows, lag features, and trend signals |
| `mart/` | Filter to cutoff GW, add position label — governed analytical output |
| `validation/` | Cross-cutting assertion modules (grain uniqueness, join safety) — never embedded in transformation code |

**Does not own:** Signal characterisation, signal scoring, analytical methodology, ML feature engineering.

**Contract:** `dal/fct/fct_contracts.py`, `dal/feat/feat_schema.py`, `dal/validation/` — code-enforced.

**Consumers:** All downstream layers. Canonical entry point: `dal.get_analytics_dataset(db_path) -> MartResult`. Direct imports from `dal.staging`, `dal.intermediate`, `dal.fct`, or `dal.feat` are forbidden outside the DAL. See [DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](DOWNSTREAM_DEPENDENCY_GOVERNANCE.md).

---

### Studies (`studies/`)

**Owns:** Analytical measurement of DAL data — one-time EDA, per-group lens studies, statistical kernels, synthesis experiments, backtesting.

| Sub-directory | Concern |
|---|---|
| `studies/eda/` | One-time characterisation of the full dataset — gates all lens work; closed and non-repeatable |
| `studies/lenses/` | Per-signal-group characterisation studies (LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW, LENS-AVAIL) |
| `studies/kernels/` | Domain-agnostic statistical utilities — no FPL constants, no governance imports |
| `studies/experiments/` | Backtesting simulations (EXP-FH-STACK, EXP-FH-PREDICTOR) |
| `studies/synthesis/` | Signal combination study (SYNTH-01) |

**Does not own:** Signal lifecycle status (owned by `signals/`), DAL transformations, operational scoring.

**Contract:** Studies write results to files (`studies/runs/`, `outputs/`). No downstream layer imports from `studies.*` as Python modules — all cross-layer consumption is file-based. Every lens study must have a locked `LENS_DESIGN.md` before any code runs.

**Consumers:** `signals/registry/` ingests study artifacts. `intelligence/` does not consume study outputs directly.

---

### Signals (`signals/`)

**Owns:** Signal lifecycle governance and the registry build pipeline.

| Sub-directory | Concern |
|---|---|
| `signals/lifecycle/` | Lifecycle enforcement: `assert_operational_safe()`, promotion rules, schema validation |
| `signals/registry/` | Registry build pipeline — assembles the governed artifact from confirmed signals |
| `signals/evaluation/` | Measurement Plane design specification (`EVAL_DESIGN.md`) — locked success criteria and failure conditions. This is not an evaluation *layer*; it is the contract the future Measurement Plane must satisfy. |

**Does not own:** Statistical computation on raw data (owned by `studies/`), DAL transformations, operational scoring.

**Contract:** `signals/lifecycle/lifecycle.py:assert_operational_safe()` is the runtime lifecycle gate — it raises `LifecycleViolationError` if an operational runner attempts to consume a registry from an exploratory path. No signal may be scored without passing this gate.

**Consumers:** `intelligence/` reads the governed registry artifact from `outputs/registry/gw{N}/`. `signals/registry/runner.py` is the only permitted writer to `outputs/registry/`.

---

### Intelligence (`intelligence/`)

**Owns:** Operational decision support outputs from trusted, governed signal data.

| Sub-directory | Concern |
|---|---|
| `intelligence/scoring/` | Player scoring from governed registry manifest |
| `intelligence/reporting/` | Weekly signal intelligence report generation |

**Does not own:** Signal characterisation (owned by lens studies), signal lifecycle decisions (owned by `signals/`), DAL transformations.

**Contract:** The intelligence layer consumes DAL state features and governed registry artifacts only. It does not consume exploratory EDA registries or research-stage signal lists. Enforced by `validate_intelligence_inputs()` in `intelligence/_base.py`. See [intelligence-layer.md](intelligence-layer.md) for full specification.

**Consumers:** End users (FPL decision makers). Outputs: scored player tables, weekly HTML report.

---

## Ownership non-overlap

| Concern | Single owner |
|---|---|
| All SQL queries | `dal/` |
| Raw data transformation | `dal/staging/` |
| Fixture context enrichment | `dal/intermediate/` |
| Canonical `(player_id, gw)` spine | `dal/fct/` |
| Rolling/lag feature derivation | `dal/feat/` |
| Governed analytical output (mart) | `dal/mart/` |
| Validation assertions | `dal/validation/` |
| Dataset-level signal characterisation | `studies/eda/` |
| Per-group signal methodology and results | `studies/lenses/` |
| Domain-agnostic statistical utilities | `studies/kernels/` |
| Signal lifecycle status | `signals/registry/SIGNAL_REGISTRY.md` |
| Lifecycle gate enforcement | `signals/lifecycle/` |
| Registry artifact assembly | `signals/registry/runner.py` |
| Operational signal scoring | `intelligence/scoring/` |
| Weekly reporting | `intelligence/reporting/` |

No two components share ownership of any row in this table. If a proposed change would require two components to govern the same concern, the boundary must be resolved before the change proceeds.

---

## Key boundary rules

**SQL only in `dal/`.** No SQL outside `dal/`. Research and intelligence layers read DAL output DataFrames — they do not query the source database.

**Single canonical base table.** The mart layer output (`dal.get_analytics_dataset`) is the only permitted source for all downstream analytics. Using intermediate-layer, fixture-grain, or raw fct/feat data to compute GW-level targets is a contract violation.

**Studies do not define signals.** Classification, lifecycle assignment, and signal IDs are determined by the study that produces the evidence and stored in the registry. Studies write artifacts; `signals/registry/` ingests them.

**Lifecycle gate is path-based.** A registry CSV in `outputs/registry/` is operationally safe. The same content in `studies/eda/findings/` is not — path determines safety, not content. `assert_operational_safe()` enforces this at runtime.

**Design before code.** No lens study executes without a locked `LENS_DESIGN.md`. No signals enter the registry without a confirmed lens status. No signals enter synthesis without a validated registry entry.
