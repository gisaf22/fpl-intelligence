# Layer Boundaries

**Authoritative for:** component ownership, dependency direction, cross-cutting concerns.  
**Supersedes:** `docs/architecture-boundaries.md`, `docs/architecture/SYSTEM_CONTEXT.md`.

> **Note on planes vs. layers.** This document describes the layered import hierarchy (DAL → research → model → serve, with `domain/registry/` as the shared leaf both model and serve import), which governs dependency direction and import rules. The import hierarchy is not the same as the conceptual role of each component. For the question "what is each part of the system *for*?", see [system-model.md](system-model.md). The registry, for instance, is part of the Control Plane in the conceptual model — not a pipeline step. Tests are structural validation — not the Measurement Plane.

---

## System architecture

```
Source database (fpl.db — populated by fpl-ingest)
    ↓
dal/          — deterministic (player_id, gw) spine
    ↓
research/     — analytical methodology (foundation EDA, family lenses, kernels, findings)
    ↓
model/        — governance decisions (validate, promote, decision-of-record) + assembly/weighting
    ↓
serve/ — player scoring and weekly reporting
```

`domain/registry/` is the shared leaf: it holds the registry contract, the loaders, and the
runtime lifecycle gate + governance lookup that both `model/` and `serve/` import.

Dependency direction is strictly one-way. No layer imports from a layer above it. `serve/` also reads `dal/` directly for current-gameweek data — this is permitted; the prohibition is on `dal/` depending on upper layers, not the reverse.

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

**Does not own:** Signal lifecycle status (owned by `model/governance/`), DAL transformations, operational scoring, registry build / governance vocab (owned by `model/governance/`), composition/weighting (owned by `model/assemble/`).

**Contract:** Research writes results to files (`research/runs/`, `outputs/`). No downstream layer imports from `research.*` as Python modules — all cross-layer consumption is file-based via `research/findings/`. Every validate study must have a locked `LENS_DESIGN.md` before any code runs.

**Consumers:** registry construction (`research/registry/`) builds the finding from research artifacts in-layer. `serve/` does not consume research outputs directly.

---

### Governance (split across `model/governance/` + `domain/registry/`)

There is no longer a `signals/` layer. Signal governance is split along a **decide vs. consume** seam:

- **Decision side — `model/governance/`** owns the decision-of-record (`evaluation_metadata.yaml`, `EVAL_DESIGN.md`), promotion/publication (`promote.py` — the only permitted writer to `outputs/registry/`), and the lifecycle ledger (`SIGNAL_REGISTRY.md`, `signal_traceability.yaml`).
- **Consume side — `domain/registry/`** (the shared leaf) owns the runtime governance primitives every consumer may import: the registry contract (`schema.py`, `validation.py`), the pure + operational loaders (`loader.py`, `operational.py`), the lifecycle gate (`lifecycle.py:assert_operational_safe()`), and the governance lookup (`governance.py:get_signal_governance()`).

**Why split:** `serve/` must consult the decision-of-record at scoring time but may not import `model/` (contract `no_serve_to_research_or_model`). Housing the runtime gate/lookup in `domain/registry/` keeps every consumer's imports legal; `model/governance/` owns the authoring/decision artifacts.

**Contract:** `domain/registry/lifecycle.py:assert_operational_safe()` is the runtime lifecycle gate — it raises `LifecycleViolationError` if an operational runner attempts to consume a registry from an exploratory path. No signal may be scored without passing this gate.

**Consumers:** `serve/` reads the governed registry artifact from `outputs/registry/gw{N}/` and consults `domain.registry` for the gate/lookup. `research/registry/build.py` builds the finding (to `research/findings/`); `model/governance/promote.py` is the only permitted writer to `outputs/registry/` (it validates and promotes the finding).

---

### Serve (`serve/`)

**Owns:** Operational decision support outputs from trusted, governed signal data (the operational-intelligence layer; package renamed `intelligence/` → `serve/`).

| Sub-directory | Concern |
|---|---|
| `serve/scoring/` | Player scoring from governed registry manifest |
| `serve/reporting/` | Weekly signal intelligence report generation |

**Does not own:** Signal characterisation (owned by lens studies), signal lifecycle decisions (owned by `model/governance/`), DAL transformations.

**Contract:** The serve layer consumes DAL state features and governed registry artifacts only. It does not consume exploratory EDA registries or research-stage signal lists. Enforced by `validate_intelligence_inputs()` in `serve/input_contracts.py`. See [intelligence-layer.md](intelligence-layer.md) for full specification.

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
| Signal lifecycle status | `model/governance/SIGNAL_REGISTRY.md` |
| Lifecycle gate enforcement | `domain/registry/lifecycle.py` |
| Registry artifact assembly | `research/registry/build.py` |
| Operational signal scoring | `serve/scoring/` |
| Weekly reporting | `serve/reporting/` |

No two components share ownership of any row in this table. If a proposed change would require two components to govern the same concern, the boundary must be resolved before the change proceeds.

---

## Key boundary rules

**SQL only in `dal/`.** No SQL outside `dal/`. Research and serve layers read DAL output DataFrames — they do not query the source database.

**Single canonical base table.** The mart layer output (`dal.pipeline.load`) is the only permitted source for all downstream analytics. Using intermediate-layer, fixture-grain, or raw fct/feat data to compute GW-level targets is a contract violation.

**Research does not define signals.** Classification, lifecycle assignment, and signal IDs are determined by the study that produces the evidence and stored in the registry. Research writes artifacts; registry construction (`research/registry/`) ingests them in-layer.

**Lifecycle gate is path-based.** A registry CSV in `outputs/registry/` is operationally safe. The same content in `research/findings/` is not — path determines safety, not content. `assert_operational_safe()` enforces this at runtime.

**Design before code.** No lens study executes without a locked `LENS_DESIGN.md`. No signals enter the registry without a confirmed lens status. No signals enter synthesis without a validated registry entry.
