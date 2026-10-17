# Layer Boundaries

**Authoritative for:** component ownership, dependency direction, cross-cutting concerns.  
**Supersedes:** `docs/architecture-boundaries.md`, `docs/architecture/SYSTEM_CONTEXT.md`.

> **Note on planes vs. layers.** This document describes the layered import hierarchy (DAL → research → model → serve, with `domain/registry/` as the shared leaf both model and serve import), which governs dependency direction and import rules. The import hierarchy is not the same as the conceptual role of each component; for what each layer is *for*, see [docs/PROJECT.md](../PROJECT.md) §3. Tests are structural validation, not a system layer.

---

## System architecture

```
Source database (fpl.db — populated by fpl-ingest)
    ↓
dal/          — deterministic (player_id, gw) spine
    ↓
research/     — analytical methodology (foundation EDA, family lenses, kernels, findings)
    ↓
model/        — forecast terms + governance enrichment + assembly/weighting
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
> [adlc.md §2](adlc.md), and what each component is *for* is recorded in
> [docs/PROJECT.md](../PROJECT.md) §3. Those views rhyme but are
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

- **Decision side — `model/governance/`** owns the locked evaluation design (`EVAL_DESIGN.md`), and registry enrichment (`semantics.py`, `promotion.py` — signal-layer semantics, downstream status, promotion class). The publication step (`promote.py`, the only writer to `outputs/registry/`) was deleted 2026-08-16 along with the artifact's last reader. The decision-of-record artifacts it used to own (`evaluation_metadata.yaml`, `SIGNAL_REGISTRY.md`, `signal_traceability.yaml`) were deleted at `ae90398`; the durable verdict record is now `research/families/*/validate/{evidence,annotations}.yaml`. The research build assembles only the *raw evidence* finding; classifying each signal is a governance decision, and with `promote.py` gone nothing applies it on any live path.
- **Consume side — `domain/registry/`** (the shared leaf) owns the runtime governance primitives every consumer may import: the registry contract (`schema.py`, `validation.py`) and the pure typed loader (`loader.py`). The split mirrors meaning vs. mechanism: `schema.py`/`validation.py` are the contract; the loader is a consume-side runtime primitive that reads decisions authored in `model/governance/` — it does not make decisions. (`governance_lookup.py`, `governance_types.py` and `verdict.py` were deleted at `ae90398` along with their only consumers; `operational.py` and `lifecycle.py` followed once the promotion step was removed — see below.)

**Why split:** `serve/` must consult the decision-of-record at scoring time but may not import `model/` (contract `no_serve_to_research_or_model`). Housing the contract and loader in `domain/registry/` keeps every consumer's imports legal; `model/governance/` owns the authoring/decision artifacts.

**Contract:** there is no longer a runtime lifecycle gate. `domain/registry/lifecycle.py` (`assert_operational_safe()`, `LifecycleViolationError`) and its wrapper `domain/registry/operational.py` were deleted once `model/governance/promote.py` went: the gate was path-based, and its "safe" side — `outputs/registry/` — no longer has a writer, so it had no passing input and would have rejected every registry the system can produce. `domain/registry/loader.py` is now the only loader.

**Consumers:** none on the live path. `serve/` used to read the governed registry artifact from `outputs/registry/gw{N}/`; both readers (`serve/scoring/`, `serve/reporting/`) and the artifact itself were deleted at `ae90398`, and the writer (`model/governance/promote.py`) on 2026-08-16. `research/registry/build.py` still builds the raw evidence finding to `research/findings/`; nothing publishes it.

---

### Serve (`serve/`)

**Owns:** Operational decision support outputs from trusted, governed signal data (the operational-intelligence layer; package renamed `intelligence/` → `serve/`).

| Module | Concern |
|---|---|
| `serve/{captain,value,transfers}.py` | `DecisionSpec` declarations — ranking rules per decision |
| `serve/decision_engine.py` | Generic ranking engine (`run_decision`) |
| `serve/input_contracts.py` | Input validation for the serve layer |

(`serve/scoring/` and `serve/reporting/` were deleted at `ae90398`.)

**Does not own:** Signal characterisation (owned by lens studies), signal lifecycle decisions (owned by `model/governance/`), DAL transformations.

**Contract:** The serve layer consumes DAL state features and governed registry artifacts only. It does not consume exploratory EDA registries or research-stage signal lists. Enforced by `validate_intelligence_inputs()` in `serve/input_contracts.py`. See [intelligence-layer.md](intelligence-layer.md) for full specification.

**Consumers:** `operational/recommend.py` (the composition root). Outputs: ranked decision frames.

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
| Signal lifecycle status | `research/families/*/validate/evidence.yaml` |
| Registry contract and typed loading | `domain/registry/{schema,validation,loader}.py` |
| Registry artifact assembly (raw evidence) | `research/registry/build.py` |
| Registry governance enrichment (signal_layer, downstream_status, promotion_class) | `model/governance/{semantics,promotion}.py` (no caller since `promote.py` was deleted) |
| Decision ranking rules | `serve/{captain,value,transfers}.py` |
| Generic ranking execution | `serve/decision_engine.py` |

No two components share ownership of any row in this table. If a proposed change would require two components to govern the same concern, the boundary must be resolved before the change proceeds.

---

## Key boundary rules

**SQL only in `dal/`.** No SQL outside `dal/`. Research and serve layers read DAL output DataFrames — they do not query the source database.

**Single canonical base table.** The mart layer output (`dal.pipeline.load`) is the only permitted source for all downstream analytics. Using intermediate-layer, fixture-grain, or raw fct/feat data to compute GW-level targets is a contract violation.

**Research does not define signals.** Classification, lifecycle assignment, and signal IDs are determined by the study that produces the evidence and stored in the registry. Research writes artifacts; registry construction (`research/registry/`) ingests them in-layer.

**Every registry artifact is exploratory.** `research/registry/build.py` writes findings to `research/findings/registry_builds/gw{N}/`, and with `model/governance/promote.py` deleted nothing publishes to `outputs/registry/`. The path-based runtime gate that once drew this distinction is gone; treat any registry read as a research finding, not a governed operational artifact.

**Design before code.** No lens study executes without a locked `LENS_DESIGN.md`. No signals enter the registry without a confirmed lens status. No signals enter synthesis without a validated registry entry.
