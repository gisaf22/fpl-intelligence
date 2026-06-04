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

> **Scope of this section.** This is the **import / dependency** view — a code-enforced rule
> (see [downstream-dependency-governance.md](downstream-dependency-governance.md)), and it is
> what this document is authoritative for. It is *not* the conceptual flow story: how a question
> moves through the analysis *stages* (explore → validate → model → serve → monitor) is owned by
> [adlc.md §2](adlc.md), and what each component is *for* (the Control/Execution/Measurement
> planes) is owned by [system-model.md](system-model.md). Those three views rhyme but are
> distinct; this doc keeps only the enforceable import/ownership rules below.

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

**Consumers:** All downstream layers. Canonical entry point: `dal.pipeline.load(db_path) -> MartResult`. Direct imports from `dal.staging`, `dal.intermediate`, `dal.fct`, or `dal.feat` are forbidden outside the DAL. See [downstream-dependency-governance.md](downstream-dependency-governance.md).

---

### Research (`research/`)

**Owns:** Analytical measurement of DAL data — cross-signal foundation EDA, per-family explore/validate studies, statistical kernels, durable findings.

| Sub-directory | Concern |
|---|---|
| `research/foundation/<stage>/` | One-time cross-signal characterisation of the full dataset — gates all family work; closed and non-repeatable |
| `research/families/<f>/validate/` | Per-family confirmatory lens studies (form, market, fixture, availability) |
| `research/families/<f>/explore/` | Per-family hypothesis-generation studies (below the firewall) |
| `research/kernels/` | Domain-agnostic statistical utilities — no FPL constants, no governance imports |
| `research/findings/` | Durable verdict-of-record — the sole governance handoff |

**Does not own:** Signal lifecycle status (owned by `signals/`), DAL transformations, operational scoring, registry build / governance vocab (owned by `model/governance/`), composition/weighting (owned by `model/assemble/`).

**Contract:** Research writes results to files (`research/runs/`, `outputs/`). No downstream layer imports from `research.*` as Python modules — all cross-layer consumption is file-based via `research/findings/`. Every validate study must have a locked `LENS_DESIGN.md` before any code runs.

**Consumers:** `signals/characterisation/` ingests research artifacts. `intelligence/` does not consume research outputs directly.

---

### Signals (`signals/`)

**Owns:** Signal lifecycle governance and the registry build pipeline.

| Sub-directory | Concern |
|---|---|
| `signals/governance/` | Lifecycle enforcement: `assert_operational_safe()`, promotion rules, schema validation, evaluation metadata, `EVAL_DESIGN.md` |
| `signals/characterisation/` | Registry build pipeline — assembles the governed artifact from confirmed signals |

**Does not own:** Statistical computation on raw data (owned by `studies/`), DAL transformations, operational scoring.

**Contract:** `signals/governance/lifecycle.py:assert_operational_safe()` is the runtime lifecycle gate — it raises `LifecycleViolationError` if an operational runner attempts to consume a registry from an exploratory path. No signal may be scored without passing this gate.

**Consumers:** `intelligence/` reads the governed registry artifact from `outputs/registry/gw{N}/`. `signals/characterisation/registry_build_runner.py` is the only permitted writer to `outputs/registry/`.

---

### Intelligence (`intelligence/`)

**Owns:** Operational decision support outputs from trusted, governed signal data.

| Sub-directory | Concern |
|---|---|
| `intelligence/scoring/` | Player scoring from governed registry manifest |
| `intelligence/reporting/` | Weekly signal intelligence report generation |

**Does not own:** Signal characterisation (owned by lens studies), signal lifecycle decisions (owned by `signals/`), DAL transformations.

**Contract:** The intelligence layer consumes DAL state features and governed registry artifacts only. It does not consume exploratory EDA registries or research-stage signal lists. Enforced by `validate_intelligence_inputs()` in `intelligence/intelligence_contracts.py`. See [intelligence-layer.md](intelligence-layer.md) for full specification.

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
| Dataset-level signal characterisation | `research/foundation/` |
| Per-family signal methodology and results | `research/families/<f>/validate/` |
| Domain-agnostic statistical utilities | `research/kernels/` |
| Signal lifecycle status | `signals/governance/SIGNAL_REGISTRY.md` |
| Lifecycle gate enforcement | `signals/governance/lifecycle.py` |
| Registry artifact assembly | `signals/characterisation/registry_build_runner.py` |
| Operational signal scoring | `intelligence/scoring/` |
| Weekly reporting | `intelligence/reporting/` |

No two components share ownership of any row in this table. If a proposed change would require two components to govern the same concern, the boundary must be resolved before the change proceeds.

---

## Key boundary rules

**SQL only in `dal/`.** No SQL outside `dal/`. Research and intelligence layers read DAL output DataFrames — they do not query the source database.

**Single canonical base table.** The mart layer output (`dal.pipeline.load`) is the only permitted source for all downstream analytics. Using intermediate-layer, fixture-grain, or raw fct/feat data to compute GW-level targets is a contract violation.

**Research does not define signals.** Classification, lifecycle assignment, and signal IDs are determined by the study that produces the evidence and stored in the registry. Research writes artifacts; `signals/characterisation/` ingests them.

**Lifecycle gate is path-based.** A registry CSV in `outputs/registry/` is operationally safe. The same content in `studies/eda/findings/` is not — path determines safety, not content. `assert_operational_safe()` enforces this at runtime.

**Design before code.** No lens study executes without a locked `LENS_DESIGN.md`. No signals enter the registry without a confirmed lens status. No signals enter synthesis without a validated registry entry.
