# Repository Alignment Report

**Date:** 2026-05-18
**Branch:** stabilization/dal-hardening
**Scope:** Full repository — lifecycle classification, ownership boundaries, dependency direction, research artifact governance, operationalization readiness.

Governance documents now canonical:
- `docs/system-purpose.md`
- `docs/research-lifecycle.md`
- `docs/architecture-boundaries.md`

---

## 1. Component Inventory

| Component | Purpose | Classification |
|-----------|---------|----------------|
| `dal/` | Five-layer pipeline producing canonical `(player_id, gw)` spine | DAL foundation |
| `core/governance/` | Registry loading, contract validation, signal layer semantics, promotion workflow | shared utility |
| `core/relationships/` | Rho decomposition, geometry classification, haul concentration, binning | shared utility |
| `core/signals/` | Signal population, profiling, redundancy, scoping, stability utilities | shared utility |
| `core/target/` | Target variable distribution analysis | shared utility |
| `signals/eda/notebooks/` | System EDA — one-time characterisation (eda_00 through eda_07) | research artifact (exploratory, closed) |
| `signals/eda/findings/` | EDA output CSVs; `eda_03_joint_registry.csv` is authoritative EDA output | research artifact (exploratory output) |
| `signals/lenses/form/` | Rolling output and attacking threat signal characterisation | research infrastructure (pre-investigational) |
| `signals/lenses/market/` | Transfer and ownership signal characterisation | research infrastructure (pre-investigational) |
| `signals/lenses/fixture-gw/` | Single-GW fixture difficulty characterisation | research infrastructure (pre-investigational) |
| `signals/lenses/avail/` | Minutes consistency and trend characterisation | research infrastructure (pre-investigational) |
| `signals/lenses/fixture-run/` | Fixture concentration lens (design phase) | research infrastructure (pre-investigational) |
| `signals/registry/SIGNAL_REGISTRY.md` | Governance registry — lifecycle status for all named signals | research infrastructure (empty governance layer) |
| `signals/evaluation/EVAL_DESIGN.md` | Success criteria and failure conditions (locked) | research infrastructure (gate document) |
| `signals/synthesis/synth-01/` | Signal synthesis — blocked until confirmed signals exist | research infrastructure (blocked scaffold) |
| `signals/experiments/` | ML backtesting scaffolds — blocked on synthesis | experimental (blocked scaffold) |
| `signals/runs/` | Run logs from prior (pre-methodology) lens executions | transitional (provenance unclear) |
| `registry/` | Registry build pipeline — two modes: packaged and computed | shared utility (build orchestration) |
| `report/` | Weekly snapshot and intelligence report generation | operational intelligence |
| `scorer/` | Player scoring from registry manifest | operational intelligence |
| `examples/` | Quickstart script for DAL validation | shared utility |
| `tests/` | 439+ tests across DAL stabilization waves + governance enforcement | shared utility |
| `docs/` | Architecture, design decisions, lifecycle, contract documents | shared utility |
| `archive/pipeline_legacy/` | Superseded pre-stabilization code | archive candidate |
| `archive/STABILIZATION_PLAN.md` | Stabilization wave history | archive candidate |
| `tasks/` | Session-scoped task tracking | transitional |
| `outputs/` | Runtime build artifacts — registry CSVs, weekly reports, scorer HTML | transitional |

---

## 2. Lifecycle Alignment Audit

### Components that map cleanly to a lifecycle state

| Component | Lifecycle State | Notes |
|-----------|----------------|-------|
| `signals/eda/notebooks/` | Exploratory (closed) | Non-repeatable per design. EDA is complete and gated. |
| `signals/eda/findings/` | Exploratory output | Authoritative EDA artifact. `eda_03_joint_registry.csv` is the promotion_class source. |
| `signals/evaluation/EVAL_DESIGN.md` | Gate document | Locked before results. Correct. |
| `signals/synthesis/synth-01/` | Blocked (pre-validated) | Correctly blocked; no confirmed signals exist. |
| `signals/experiments/` | Blocked (pre-synthesis) | Correctly blocked; no synthesis outputs exist. |

### Components with lifecycle classification gaps

**All four active lens studies — `form`, `market`, `fixture-gw`, `avail`**

Classification issue: These are between lifecycle states. EDA is closed. Previous lens runs (SA, SB, SC, SE) are archived as invalid. New lens runs have not started. The `SIGNAL_REGISTRY.md` — which must be populated before a lens study begins — is empty.

Per `docs/research-lifecycle.md`, `investigational` state requires an active lens study with a locked `LENS_DESIGN.md`. Per `docs/architecture-boundaries.md`, no lens study may begin without a prior registry entry. Neither condition is met.

Current state: The lenses have locked LENS_DESIGN.md files but no registry entries and no results. The lifecycle position is correctly unstarted, but no document states this explicitly. A formal `pending` classification in SIGNAL_REGISTRY.md would close this gap.

**`signals/registry/SIGNAL_REGISTRY.md`**

Classification issue: The document is declared the authoritative lifecycle record per `docs/architecture-boundaries.md`. It is empty. No signals have been registered.

`eda_03_joint_registry.csv` contains promotion_class values from EDA-7 synthesis — this is the data that should seed the initial SIGNAL_REGISTRY.md entries (EDA Status column). That handoff has not occurred.

### Critical lifecycle bypass

**Severity: HIGH**

The scorer and the registry build pipeline default to reading `signals/eda/findings/eda_03_joint_registry.csv` directly:

```python
# core/governance/schema.py
DEFAULT_REGISTRY_PATH = Path("signals/eda/findings/eda_03_joint_registry.csv")
```

This path is used by:
- `scorer/runner.py` → `load_manifest_from_path(input.registry_path)` — loads and filters the EDA CSV as if it were a governed signal registry
- `registry/config.py` → `DEFAULT_SOURCE_REGISTRY_PATH = DEFAULT_REGISTRY_PATH` — in `packaged` mode, the registry builder repackages this EDA CSV as its output artifact

Consequence: Signals in `exploratory` lifecycle state (EDA output, never through a lens study) are producing operational intelligence outputs via the scorer. The lifecycle gate — `investigational → candidate → validated → operationalized` — is not enforced in the runtime pipeline.

Per `docs/architecture-boundaries.md`: "The intelligence layer may only consume signals with `operationalized` status." The scorer is consuming `exploratory` signals.

---

## 3. Boundary Ownership Audit

### Violations

| Violation | Why It Violates Boundary | Severity | Minimal Fix |
|-----------|--------------------------|----------|-------------|
| `core/governance/schema.py` contains `DEFAULT_REGISTRY_PATH = Path("signals/eda/findings/eda_03_joint_registry.csv")` | `core/` owns stateless utilities. Encoding a specific research artifact file path couples governance to the EDA output location — a research-layer concern. The DAL and core layers must not know about signals-layer file locations. | HIGH | Move the default path constant to `registry/config.py` and `scorer/contracts.py` (where it is used). Remove from `core/governance/schema.py`. |
| `scorer/` and `registry/` both default to the EDA findings CSV as their registry input | Per `docs/research-lifecycle.md`, EDA findings are exploratory-state artifacts. Using them as the default runtime registry input bypasses all lifecycle gates. | HIGH | The default registry path must resolve to a lens-validated registry, not EDA findings. Until validated signals exist, the scorer should require an explicit `--registry-path` with no default, or fail with an informative message when no validated registry exists. |
| `SIGNAL_REGISTRY.md` has no enforcement hook in the runtime pipeline | `docs/architecture-boundaries.md` declares SIGNAL_REGISTRY.md as the authoritative signal lifecycle record. No code reads it. The technical registry (CSV) and the governance registry (markdown) are disconnected. | MEDIUM | Define a promotion gate: the registry build pipeline in `packaged` mode should require that its source CSV corresponds to signals that have entries in SIGNAL_REGISTRY.md. Until then, document this disconnect explicitly. |
| `registry/` (computed mode) re-computes full signal characterisation (geometry, Rho decomposition, haul concentration, monotonicity CI) from prepared data | `docs/architecture-boundaries.md` assigns signal characterisation to lens studies. The registry builder is documented as a read-only consumer of confirmed signals — it "assembles what the registry marks as confirmed." In computed mode it generates characterisation from scratch, which overlaps with the lens study concern. | MEDIUM | Clarify intent in the `registry/` contract: computed mode is for rebuilding characterisation metrics on already-confirmed signals (post-lens), not for initial characterisation. Document this constraint in `registry/runner.py` or a `registry/REGISTRY_CONTRACT.md`. |
| `dal/DAL_CONTRACT.md` is a deprecated stub | Dead file at the DAL root. Not a boundary violation but creates ambiguity about where the authoritative contract lives. | LOW | Delete `dal/DAL_CONTRACT.md`. Update any test or doc references to point directly to `docs/architecture/DAL_CONTRACT.md`. |

### No violations found

- DAL internal layer dependencies (staging → intermediate → curated → state → prepared) are one-directional and clean.
- `tests/test_downstream_governance.py` enforces forbidden import patterns (dal.staging, dal.intermediate, direct sqlite, retired pipeline namespace) via AST analysis.
- `core/` modules are stateless; no core module imports from dal.staging or dal.intermediate.
- `report/` and `scorer/` consume `dal.access` entry points only; no internal DAL layer imports.

---

## 4. Dependency Direction Audit

### Actual dependency flow

```
fpl.db (SQLite)
  ↓ sqlite3 (internal to DAL only)
dal/staging/ → dal/intermediate/ → dal/curated/ → dal/state/ → dal/prepared/
  ↓ dal.access (canonical entry points)
signals/eda/         → dal.prepared
registry/            → dal.prepared, dal.access, core.governance, core.relationships
report/              → dal.access, core.governance
scorer/              → dal.access, core.governance
```

### Direction conformance

The DAL → downstream direction is correct and enforced. No reverse dependencies exist. No cycles were found.

### Direction risks

**Risk 1 — Research artifact in governance layer (HIGH)**

`core/governance/schema.py` encodes `DEFAULT_REGISTRY_PATH` pointing into `signals/eda/findings/`. This makes a cross-cutting governance utility dependent on a research-layer artifact path. If the EDA findings directory is reorganised, the core governance module breaks. The dependency direction is inverted: core should not know about signals-layer paths.

**Risk 2 — Operational consumers on exploratory inputs (HIGH)**

The scorer and registry builder default to the EDA findings CSV. The dependency graph shows:

```
signals/eda/findings/eda_03_joint_registry.csv → scorer (operational intelligence)
```

This is a reverse lifecycle dependency: operational intelligence depending on exploratory research output. The expected direction is: research (lens studies) → validated signals → intelligence.

**Risk 3 — `signals/runs/` provenance (LOW)**

Run logs exist in `signals/runs/`. These appear to be from pre-methodology lens executions (SA, SB, SC, SE). Their provenance relative to the current methodology is unclear. If these influence any build or test, they represent an undocumented runtime dependency.

---

## 5. Research Artifact Assessment

| Artifact | Reproducible? | Versioned? | Trusted? | Lifecycle State |
|----------|---------------|------------|----------|-----------------|
| EDA notebooks (eda_00 – eda_07) | No (declared non-repeatable) | No (non-repeatable by design) | Yes — methodology is locked | Exploratory (closed) |
| `eda_03_joint_registry.csv` | No (EDA output artifact) | No explicit version tag | Yes — authoritative EDA output | Exploratory output |
| `eda_07_signal_synthesis.csv` | No | No | Yes — EDA synthesis findings | Exploratory output |
| `SIGNAL_REGISTRY.md` | N/A (governance document) | Version table present (1.0 only) | Empty — no entries | Not populated |
| `LENS_DESIGN.md` × 4 | N/A (design documents) | Locked by convention | Locked | Pre-investigational gate documents |
| Lens results directories (×4) | N/A | N/A | N/A — empty | No results exist |
| `EVAL_DESIGN.md` | N/A (locked gate document) | Locked | Locked | Pre-evaluation gate document |
| `SYNTH-01/` | N/A | N/A | N/A | Blocked scaffold |
| `EXP-FH-STACK/`, `EXP-FH-PREDICTOR/` | N/A | N/A | N/A | Blocked scaffold |
| `signals/runs/*.json` | No (point-in-time outputs) | Timestamped | Unknown — from pre-methodology runs | Pre-methodology; not valid inputs |
| Registry build outputs (`outputs/registry/`) | Yes (if inputs fixed) | Per-GW directories | Trusted only if built from validated inputs | Exploratory state (current default input) |

**Key governance gap:** No signal has reached `candidate`, `validated`, or `operationalized` status. The current production path — EDA findings → registry builder → scorer — runs entirely within the `exploratory` lifecycle state.

---

## 6. Transitional / Residual Structure

| Item | Classification | Disposition |
|------|---------------|-------------|
| `archive/pipeline_legacy/` | Dead code; superseded by `dal/` | archive (already in archive) |
| `archive/STABILIZATION_PLAN.md` | Historical record; not referenced by code | archive (already in archive) |
| `dal/DAL_CONTRACT.md` | Deprecated pointer stub | remove — delete this file; all references should point to `docs/architecture/DAL_CONTRACT.md` |
| `signals/runs/*.json` | Run logs from pre-methodology lenses (SA, SB, SC, SE) | archive — move to `archive/pre-methodology-runs/` or delete; they are declared invalid inputs in SIGNAL_REGISTRY.md |
| `tasks/` | Session-scoped task tracking | keep (external coordination; does not affect code paths) |
| `outputs/` | Runtime artifacts (registry CSVs, HTML scoring outputs) | keep (runtime output directory); clarify whether outputs are `.gitignored` or committed |
| SYSTEM_CONTEXT.md test count | Stale: "331 tests passing" vs 439+ actual | update — minor documentation drift |

---

## 7. Operationalization Readiness

### Boundary readiness

The DAL boundary is clean and enforced. All five sub-layers have well-defined concerns. Downstream access is restricted to `dal.access` entry points. Governance tests enforce import patterns. This layer is ready to support downstream operationalization without modification.

`core/` is stateless and decoupled. Ready for downstream consumption.

### Lifecycle readiness

Not ready. No signal has reached `validated` or `operationalized` status. The lifecycle pipeline is blocked between exploratory (EDA closed) and investigational (lens studies not started). The EDA-to-registry handoff has not occurred (SIGNAL_REGISTRY.md is empty).

### Promotion-path clarity

The promotion path is documented in `docs/research-lifecycle.md` but not mechanically enforced. The technical pipeline can be run with any signals regardless of their lifecycle status. The architectural documents define the gates; no code enforces them.

Three gaps block a clean promotion path:

1. **EDA-to-registry handoff missing.** eda_03_joint_registry.csv promotion_class values have not been formally recorded in SIGNAL_REGISTRY.md. Until this handoff occurs, no signal has an official lifecycle entry.
2. **Lens studies unstarted.** All four lenses are pre-investigational. Investigational status requires an active lens study producing results.
3. **Scorer accepts unvalidated signals.** The scorer's lifecycle gate (`promotion_class in {"core_signal", "review_signal"}`) filters by EDA classification, not by lens validation status. A signal can reach the scorer without ever passing a lens study.

### Dependency cleanliness

The DAL-to-downstream direction is clean. The one structural problem — `core/governance/schema.py` encoding the EDA findings path — pollutes the governance utility layer with a research-artifact location.

---

## 8. Minimal Next-Step Recommendations

Ordered by governance impact. Each item is scoped to a single bounded change.

---

### R-1 — Populate SIGNAL_REGISTRY.md from eda_03_joint_registry.csv

**What:** Register all signals from eda_03_joint_registry.csv into SIGNAL_REGISTRY.md, setting EDA Status per signal based on EDA findings. This completes the EDA-to-registry handoff.

**Why:** SIGNAL_REGISTRY.md is declared the authoritative lifecycle record. It is empty. The EDA is closed. The handoff is complete in data but not in governance. Until this step is done, the lifecycle pipeline has no registered signals, no lens studies can formally begin, and no boundary document is accurate.

**Scope:** Manual documentation update to SIGNAL_REGISTRY.md. No code changes.

---

### R-2 — Remove default EDA registry path from scorer and registry builder

**What:** Remove `DEFAULT_REGISTRY_PATH` from `core/governance/schema.py`. Update `scorer/runner.py` to require `--registry-path` with no default (or fail informatively if no registry exists). Update `registry/config.py` to derive its default from its own config, not from `core/governance/schema.py`.

**Why:** The current default couples operational intelligence outputs to exploratory-state EDA findings. This is the primary lifecycle gate bypass. Removing the default forces explicit registry path specification, making it impossible to accidentally score players with unvalidated signals.

**Scope:** Changes to `core/governance/schema.py`, `scorer/runner.py`, `registry/config.py`. No logic changes — only path defaults and validation.

---

### R-3 — Delete `dal/DAL_CONTRACT.md`

**What:** Delete `dal/DAL_CONTRACT.md`. Update any references in tests or documentation to point directly to `docs/architecture/DAL_CONTRACT.md`.

**Why:** The file is a deprecated stub that creates confusion about the authoritative contract location. Dead residue.

**Scope:** One file deletion. Grep for references first.

---

### R-4 — Document `dal/prepared/` as the fifth DAL sub-layer

**What:** Update `docs/architecture/SYSTEM_CONTEXT.md` (currently says "four sub-layers") and `docs/architecture/DAL_CONTRACT.md` to include the `prepared/` sub-layer. Update the architecture-boundaries.md DAL table if needed.

**Why:** SYSTEM_CONTEXT.md describes four sub-layers; five exist. The `dal/prepared/` layer is used by the registry builder (computed mode) and by EDA notebooks. Undocumented sub-layers create ambiguity about what is part of the DAL contract.

**Scope:** Documentation-only changes to two docs files.

---

### R-5 — Archive `signals/runs/` pre-methodology run logs

**What:** Move the contents of `signals/runs/` to `archive/pre-methodology-runs/` or delete them. Add a note in `signals/runs/` or in SIGNAL_REGISTRY.md confirming these logs are from archived studies (SA, SB, SC, SE) and are not valid methodology inputs.

**Why:** SIGNAL_REGISTRY.md already declares that SA/SB/SC/SE results are invalid inputs because they predate the locked methodology. The run logs sitting in `signals/runs/` are residue from those invalid studies. Their presence creates ambiguity about whether any results exist from current methodology lens runs.

**Scope:** File move or deletion. One documentation note.

---

### R-6 — Clarify registry builder's computed mode scope in contract

**What:** Add a brief contract note in `registry/runner.py` or a new `registry/REGISTRY_CONTRACT.md` clarifying that computed mode is for rebuilding characterisation metrics on already-confirmed signals (post-lens study confirmation), not for initial signal characterisation. Initial characterisation is the lens study's responsibility.

**Why:** The registry builder in computed mode performs full Rho decomposition, geometry classification, haul concentration, and monotonicity confidence computation — the same analysis that lens studies are supposed to own. Without a documented scope boundary, the registry builder can be used to characterise unvalidated signals, bypassing the lens study gate.

**Scope:** Documentation only (contract note). No code changes.

---

## Summary

The DAL is clean, fully tested, and ready to support downstream work without modification.

The primary structural problem is a lifecycle gate bypass: EDA findings flow directly to the scorer as the default registry input (`DEFAULT_REGISTRY_PATH = signals/eda/findings/eda_03_joint_registry.csv`), making exploratory-state signals operational without passing through any lens study. This is the highest-priority finding.

The secondary structural problem is the disconnection between the technical registry (CSV consumed by scorer and registry builder) and the governance registry (SIGNAL_REGISTRY.md), which is empty and has no enforcement hook in the runtime pipeline.

Everything else is documentation drift or dead residue. The research infrastructure (lens studies, synthesis, experiments) is correctly blocked and correctly scoped. The architecture is sound; the governance gap is what requires closing.
