# Decision 007 — System Layer Architecture

**Status:** FROZEN  
**Applies to:** All directories, all import paths, all new work  
**Prerequisite to:** any directory rename or restructure  
**Enforcement:** docs/adr/010-enforcement-contract.md

---

## Layer Model

```
dal/               ground truth
  staging/
  intermediate/
  fct/
  feat/
  mart/

studies/           measurement layer
  kernels/         domain-agnostic statistical utilities
  eda/             system-wide exploration
  lenses/          subject-domain studies
  experiments/     backtesting runs
  synthesis/       signal combination studies

signals/           canonical knowledge
  registry/        signal data model + storage
  lifecycle/       validation, promotion, versioning

intelligence/      consumption and output
  scoring/
  reporting/
```

**Flow:** `dal/ → studies/ → signals/ → intelligence/`

`intelligence/` also reads `dal/` directly for current gameweek data. This is permitted — the prohibition is on `dal/` depending on upper layers, not on upper layers depending on `dal/`.

---

## Layer Definitions

**DAL** — Deterministic, versioned access to player and fixture data. No analytical logic. No upstream system dependencies.

**Studies** — Measures statistical properties of observed DAL data. Produces file artifacts. Does not define, store, or mutate signals.

**Signals** — Stores, validates, and versions study-derived signal entities. Does not run statistical computation on raw data.

**Intelligence** — Combines validated signals and current DAL data to produce rankings and decisions. Does not define new signals.

---

## Design Principles

### Classification belongs to studies, not signals

Signals does not classify. Any association classification, geometry labelling, or stability determination is computed inside the study that produces the evidence and written into the study artifact. The `signals/registry/` ingestion step reads a pre-classified artifact — it validates the schema and stores the result, nothing more.

This eliminates the need for classification logic inside `signals/` and removes the ambiguity about where domain-specific computation lives.

### studies/kernels/ is strictly domain-agnostic

`studies/kernels/` contains reusable statistical and mathematical functions. A module belongs in `kernels/` only if it has zero FPL-specific knowledge:

- No signal names or IDs
- No governance schema imports
- No classification labels
- No FPL season, position, or fixture constants

Any function that references schema constants, signal taxonomy, or FPL domain structure belongs in the study that uses it, not in `kernels/`. If two studies need the same FPL-specific logic, they duplicate it or extract a shared study-layer module — they do not push it into `kernels/`.

### Artifacts are the cross-layer interface

Studies write results to files. Downstream layers read those files by path. No layer ever imports from `studies.lenses.*`, `studies.experiments.*`, `studies.eda.*`, or `studies.synthesis.*` as Python modules.

### DAL access levels

`intelligence/` reads from `dal.fct`, `dal.feat`, or `dal.mart`. Access to `dal.staging` from `intelligence/` requires explicit justification documented in the consuming module.

### studies/ organised by subject, not epistemology

Lenses are holistic investigations of a signal domain. A single lens simultaneously runs correlation, robustness, and population sub-analyses — it cannot be filed under `predictive/` or `causal/` without fragmentation. Studies are organised by subject domain (form, market, fixture, availability), not by analysis type.

---

## What Moves Where

| Current path | Target path | Notes |
|---|---|---|
| `core/governance/` | `signals/lifecycle/` | Validation, promotion, versioning |
| `core/signals/` | `studies/kernels/` | Domain-agnostic signal profiling utilities |
| `core/target/` | `studies/kernels/` | Domain-agnostic outcome distribution utilities |
| `core/relationships/panel.py`, `tail.py` | `studies/kernels/correlation/` | Pure statistical routines; refactor to remove `geometry.py` import — pass needed constants as parameters |
| `core/relationships/geometry.py`, `association.py` | Absorbed into study layer | FPL-specific; classification is a study responsibility, not a shared utility |
| `signals/eda/` | `studies/eda/` | Measurement work |
| `signals/lenses/` | `studies/lenses/` | Subject-domain studies |
| `signals/experiments/` | `studies/experiments/` | Backtesting |
| `signals/synthesis/` | `studies/synthesis/` | Signal combination |
| `signals/runs/` | `studies/runs/` | Run logs |
| `registry/` (builder) | `signals/registry/` | Ingestion + storage only; statistical computation removed — see note below |
| `scorer/` | `intelligence/scoring/` | Output layer |
| `report/` | `intelligence/reporting/` | Output layer — see prerequisite below |

### Note: registry builder computation

The current `registry/sections.py` computes relationship statistics (geometry, panel decomposition, tail analysis, association class) against a prepared DAL dataset. Under this model, that computation is a study. It either moves into the lens studies that produce signal evidence (each lens outputs pre-classified statistics in its artifact), or becomes a named study in `studies/experiments/` that reads lens artifacts and produces a classification artifact. Either way, the computation lives in `studies/`, not in `signals/registry/`. The registry builder's residual responsibility is: read a study artifact, validate schema, write to `SIGNAL_REGISTRY.md`.

---

## Prerequisites Before Moving

### evaluation/ split

Split before any restructure begins. The boundary is the import direction — any file that imports from `intelligence.*` cannot go to `studies/`.

| Files | Destination | Reason |
|---|---|---|
| `rolling_xgi_study.py`, `minutes_stability_study.py` | `studies/experiments/` | No upward imports |
| `captain.py`, `transfers.py`, `value.py` | `tests/integration/` | Import from `intelligence.*`; are integration tests, not studies |
| `baselines.py`, `metrics.py`, `windows.py`, `features.py` | `tests/integration/` | Support the above; not standalone studies |

`rolling_xgi_study.py` and `minutes_stability_study.py` currently import from `evaluation.metrics` and `evaluation.windows`. Those imports must be rewritten before or during the move — either inline or via `studies/kernels/`.

No file from `evaluation/` moves intact. This split is a prerequisite, not a concurrent step.

### report/ DAL access level

`report/db.py` reads from `dal.staging` directly (`get_staged_events`, `get_staged_player_histories`). Before `report/` moves to `intelligence/reporting/`, either:

- Promote the staging data to a curated DAL accessor (e.g. `dal/curated/events.py` exposing `get_current_gameweek()`), and update `report/db.py` accordingly; or
- Document the exception with justification in the DAL contract.

Do not move `report/` until this is resolved.

---

## Import Path Changes

| Old import | New import |
|---|---|
| `from core.governance.*` | `from signals.lifecycle.*` |
| `from core.signals.*` | `from studies.kernels.*` |
| `from core.target.*` | `from studies.kernels.*` |
| `from core.relationships.panel import decompose_rho` | `from studies.kernels.correlation import decompose_rho` |
| `from core.relationships.tail import haul_concentration` | `from studies.kernels.correlation import haul_concentration` |
| `from core.relationships.geometry.*` | No shared import — move usage into the calling study |
| `from core.relationships.association.*` | No shared import — move usage into the calling study |

Tests in `tests/` that import from `core/` must be updated in the same commit as the move.

---

## What Does Not Change

- Everything inside `dal/` — the 5-layer pipeline, validation, contracts, reproducibility
- Naming conventions (LENS-[NAME], FORM-[NNN], EXP-[NAME])
- Governance documents (EVAL_DESIGN.md, SIGNAL_REGISTRY.md, LENS_DESIGN.md variants)
- Test structure in `tests/`
- The `docs/` hierarchy

---

## What Changed from Prior Draft and Why

| Removed / changed | Reason |
|---|---|
| `signals/governance/` → `signals/lifecycle/` | `governance/` mixed lifecycle rules, schema, promotion, and semantics under one vague label. `lifecycle/` names the actual responsibility: managing signal state transitions and validation. Schema and semantics are implementation details of that, not a separate concept. |
| `signals/registry/_stats/` removed entirely | Created a computation layer inside signals, violating the principle that signals does not compute. The `_stats/` modules were there to support classification — removing classification from signals removes the need for them. |
| Classification removed from signals | "Signals classify" was ambiguous and untestable. Every boundary question about `assign_association_class` became a debate. The correct owner is the study that produces the evidence — classification is a measurement act, not a governance act. |
| `studies/primitives/` → `studies/kernels/` | `primitives/` implied a broad shared-library concept. `kernels/` is narrower and communicates the actual constraint: domain-free mathematical/statistical routines only. The rename also removes the confusion caused by `core/relationships/` being forced into `primitives/` despite failing the domain-free test. |
| `core/relationships/geometry.py`, `association.py` no longer have a shared destination | They are FPL-specific and registry-build-specific. The previous draft routed them to `signals/registry/_stats/` to keep signals coherent, but that was a workaround for having classification in signals. Removing classification from signals removes the need for a shared home. Each study that needs this logic owns it directly. |
| Registry builder computation treated as a study | The current `registry/sections.py` runs statistical analysis against a DAL dataset. That is study-layer work regardless of where it lives. Making this explicit removes the last computation from `signals/` and enforces the one-owner principle. |
| Removed epistemological taxonomy critique | Operational content only. The critique is recorded in git history. |

---

## One-Line Principle

DAL defines reality. Studies answer questions about it. Signals define what is valid to believe. Intelligence decides what to do.
