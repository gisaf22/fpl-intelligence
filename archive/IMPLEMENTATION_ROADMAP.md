# FPL Intelligence — Implementation Roadmap

**Status:** AUTHORITATIVE  
**Supersedes:** `WEEKLY_ANALYTICS_PLATFORM_PLAN.md`, `ANALYTICAL_CONTENT_LAYER_PLAN.md`  
**Scope:** Current milestone only — foundational signal characterization and reproducible execution

---

## 1. Project Objective

Build a stable, reproducible analytical platform that characterizes foundational FPL signal behavior across positions and population scopes. All characterization outputs must be governed, testable, and reproducible without notebook execution.

---

## 2. Platform Identity

**What this system IS:**

- A signal characterization platform that describes how FPL metrics behave structurally
- A governed registry that classifies signal-position relationships by geometry, stability, population robustness, and promotion class
- A reproducible execution pipeline that produces weekly descriptive outputs from the governed registry

**What this system IS NOT:**

- A prediction system
- A player recommendation engine
- A transfer or captaincy optimizer
- A ranking system
- A dashboard or UI
- An ML pipeline or feature store

---

## 3. Current Milestone

**Milestone: Foundational Signal Characterization + Reproducible Execution**

Complete the analytical characterization of the current signal set, operationalize `promotion_class` assignment, make the computed registry the authoritative build path, and produce weekly outputs driven by governed characterization rather than governance-reminder boilerplate.

This milestone is complete when the 3-command sequence below runs without notebook intervention and produces outputs with real analytical content:

```bash
# Step 1: Build analytical dataset (requires live DB)
python -m dal.prepared.analytical_dataset \
  --gw 36 --output-path outputs/prepared_gw36.csv

# Step 2: Build governed registry artifact
python -m signals.registry.runner \
  --gw 36 \
  --source-registry-path studies/eda/findings/eda_03_joint_registry.csv \
  --output-dir outputs/registry/gw36

# Step 3: Generate weekly signal intelligence outputs
python -m intelligence.reporting.runner \
  --gw 36 \
  --registry-path outputs/registry/gw36/registry.csv
```

---

## 4. Layer Ownership

> **Archived reference** — layer names below reflect the pre-migration architecture. Current layer names: dal/, signals/, studies/, intelligence/.

### Research (`research/eda/notebooks/`)
- Owns: orchestration, visualization, interpretation, checkpoint writing, EDA narrative
- Does NOT own: computation logic, governance vocabulary, classification rules, canonical output creation
- Rule: notebooks call `analytics.*` modules. They do not define business logic inline.

### Analytics (`core/`)
- Owns: all reusable signal computation — geometry, association, stability, population, redundancy, promotion classification, registry schema and validation
- Does NOT own: execution orchestration, file I/O, notebook state, raw data loading

### Registry Build (`build/`)
- Owns: registry assembly pipeline, computed mode execution, parity validation, build metadata
- Does NOT own: raw relationship computation (delegates to `core/`)
- Rule: `--mode computed` is the authoritative path. Packaged mode is a bootstrap fallback only.

### Pipeline (`pipeline/`)
- Owns: data loading, staging, curated spine, prepared analytical datasets
- Does NOT own: analytical computation, registry assembly, signal characterization

### Weekly (`weekly/`)
- Owns: snapshot diffing, summary tables, signal intelligence outputs, markdown reports
- Does NOT own: signal characterization (reads from governed registry only)
- Rule: all content must be signal-level or position-level. No player-level outputs.

### Not In Scope Yet
- Historical governed snapshot sequences (Phase 7 from superseded doc)
- ML training pipelines
- Predictive backtesting
- Dashboards
- Transfer or captaincy scoring

---

## 5. Sprint Roadmap

Sprints are ordered by dependency. Each sprint produces tested, shippable artifacts.

---

### [COMPLETE] Sprint A — Complete Signal Characterization Modules
> Current implementation: `studies/kernels/stability.py`, `studies/kernels/redundancy.py`

**Prerequisite:** `core/signals/population.py` and `core/governance/promotion.py` exist (done).

**Remaining deliverables:**

| File | Purpose |
|---|---|
| `core/signals/stability.py` | Block-distribution stability, pooling decisions |
| `core/signals/redundancy.py` | Pairwise rho, construct identification, partial rho |
| `tests/test_signals_stability.py` | Block homogeneity, pooling decisions |
| `tests/test_signals_redundancy.py` | Pairwise correlation, construct identification |

**Key functions:**

`stability.py`:
- `compute_signal_block_distributions(df, signals, positions)` → per-signal per-position per-block stats
- `classify_block_homogeneity(block_stats)` → `stable | moderate_shift | unstable`
- `flag_pooling_decision(homogeneity)` → `pool_confirmed | pool_with_caveat | restrict_to_midseason`

`redundancy.py`:
- `compute_pairwise_rho(df, signals, position)` → correlation matrix
- `identify_redundant_pairs(rho_matrix, threshold)` → flagged pairs
- `compute_partial_rho(df, signal_a, signal_b, target, position)` → partial correlation
- `ALGEBRAIC_DECOMPOSITIONS` constant for known algebraic relationships (xgi = xg + xa, etc.)

**Completion gate:** All new modules importable from `core/` with passing tests. No notebook dependency.

---

### [COMPLETE] Sprint B — EDA-4 and EDA-5 Execution
> Current implementation: `studies/eda/notebooks/`

**Prerequisite:** Sprint A complete.

**Deliverables:**

| Artifact | Source | Destination |
|---|---|---|
| `eda_04_population_validity.csv` | EDA-4 notebook | `research/eda/findings/` |
| `eda_04_dual_rho_bounds.csv` | EDA-4 notebook | `research/eda/findings/` |
| `eda_05_signal_stability.csv` | EDA-5 notebook | `research/eda/findings/` |
| `eda_05_pooling_decisions.csv` | EDA-5 notebook | `research/eda/findings/` |

**Registry enrichment from EDA-4:** `population_robustness` column populated from output CSV, not manual notebook assignment.

**Registry enrichment from EDA-5:** `temporal_stability` re-derived from `eda_05_pooling_decisions.csv`.

**Completion gate:** Both CSVs written with non-placeholder values.

---

### [COMPLETE] Sprint C — EDA-6 and EDA-7 Execution + Promotion Class Wiring
> Current implementation: `studies/eda/notebooks/`, `signals/lifecycle/promotion.py`

**Prerequisite:** Sprint B complete.

**Deliverables:**

| Artifact | Source | Destination |
|---|---|---|
| `eda_06_pairwise_rho.csv` | EDA-6 notebook | `research/eda/findings/` |
| `eda_06_construct_map.csv` | EDA-6 notebook | `research/eda/findings/` |
| `eda_06_partial_rho.csv` | EDA-6 notebook | `research/eda/findings/` |
| `eda_07_signal_synthesis.csv` | EDA-7 notebook | `research/eda/findings/` |

**EDA-7 output contract:** One row per `(signal, position, population_scope)`. EDA-7 is an assembly notebook: it sources `population_robustness` and `preferred_population` from `eda_04_population_validity.csv`, `temporal_stability` from `eda_05_pooling_decisions.csv`, and reads `association_class` and `downstream_status` from the EDA-3 packaged registry. It calls `assign_promotion_class()` from `analytics.registry.promotion` to produce `promotion_class`. The output CSV contains only the synthesis and input fields — it does not replicate statistical computation fields (`rho_pooled`, `n_records`, bin statistics, decomposition, haul) that are owned by the computed registry build. Minimum 10–15 rows across positions with non-placeholder values for all synthesis fields.

**Promotion class wiring to registry build:**

In `build/assembly.py`:
```python
from analytics.registry.promotion import assign_promotion_class
registry["promotion_class"] = [assign_promotion_class(row) for row in registry.to_dict(orient="records")]
```

In `core/governance/schema.py`:
- Add `promotion_class` to `REQUIRED_COLUMNS`
- Add `PROMOTION_CLASS_VALUES` to `CONTROLLED_VALUE_COLUMNS`

**Coherence assertions in `core/governance/validation.py`:**
- Blocked rows never receive `core_signal`
- Exposure controls never receive `eligible` downstream status
- All `promotion_class` values are from `PROMOTION_CLASS_VALUES`

**Completion gate:** `eda_07_signal_synthesis.csv` has ≥ 10 characterized signal-position rows. Registry build produces `promotion_class` column passing coherence assertions.

---

### [COMPLETE] Sprint D — Computed Registry Authority + Parity Test
> Current implementation: `dal/prepared/analytical_dataset.py`, `signals/registry/runner.py`

**Prerequisite:** Sprint C complete.

**Deliverables:**

| File | Purpose |
|---|---|
| `dal/prepared/analytical_dataset.py` | Governed prepared dataset builder |
| `tests/test_dal_prepared_dataset.py` | Schema contract, grain uniqueness, GW bounds |
| `tests/test_registry_build_parity.py` | Computed vs. packaged rho within tolerance |

**Prepared dataset contract:**
- Grain: `(player_id, gameweek)` unique
- Columns: `position`, all signal columns, `total_points`
- Filtered to `minutes >= 60` primary population
- GW range validated against `data_cutoff_gw`

**Parity test contract:**
- Run computed registry build against GW6–33 prepared data
- Load packaged EDA-3 registry
- Assert: row count parity, schema parity, rho values within 0.02 tolerance

**Completion gate:** Parity test passes. The 3-command reproducibility sequence runs end-to-end without notebook intervention.

---

### Sprint E — Weekly Signal Intelligence

**Prerequisite:** Sprint D complete. Registry contains `promotion_class` with real values.

**Deliverables:**

| File | Purpose |
|---|---|
| `weekly/signal_intelligence.py` | Signal-driven weekly observations |
| `tests/test_weekly_signal_intelligence.py` | Output schema, template rendering, forbidden-phrase assertion |

**Output functions in `signal_intelligence.py`:**
- `build_stable_signal_observations(registry, gw)` → one row per `(signal, position)` for `core_signal` and `review_signal` rows
- `build_positional_signal_summary(registry)` → one row per position with signal-class counts
- `build_context_condition_notes(registry)` → rows for context-sensitive signals

All weekly notes use governed template strings. No free text. No LLM generation.

**Forbidden content (enforced by test):** player-level outputs, transfer recommendations, captaincy rankings, predicted scores, ranking language.

**Completion gate:** Weekly report contains signal-level and position-level observations derived from `promotion_class`, `rho_pooled`, `temporal_stability`, and `association_class`. The current governance-reminder boilerplate is supplemented with real analytical content.

---

## 6. Current Priorities

1. Build and test `core/signals/stability.py` (Sprint A)
2. Build and test `core/signals/redundancy.py` (Sprint A)
3. Execute EDA-4 and EDA-5 notebooks; populate finding CSVs (Sprint B)
4. Execute EDA-6 and EDA-7; wire `promotion_class` into registry build (Sprint C)
5. Implement prepared dataset builder and computed registry parity test (Sprint D)

---

## 7. Non-Goals

The following are explicitly out of scope for the current milestone. PRs introducing these should be rejected and the work deferred:

- ML model training or feature engineering
- Captaincy or transfer scoring
- Player-level ranking systems
- Dashboard or UI components
- Predictive backtesting
- Hyperparameter grids or experiment tracking
- New governance vocabulary not exercised by real characterized signals
- Historical snapshot sequences (GW-by-GW rebuilds across seasons)
- LLM-generated insight text

---

## 8. Execution Discipline Rules

1. **Notebooks orchestrate, they do not own logic.** Any business logic found in a notebook cell that is not a direct call to `analytics.*` must be extracted before the sprint closes.

2. **No new governance vocabulary unless exercised by real signals.** Adding a new controlled-vocabulary value requires at least one real signal-position row using it in `eda_07_signal_synthesis.csv`.

3. **Computed registry is authoritative.** Once Sprint D completes, `--mode packaged` is a fallback only. All downstream systems consume computed registry outputs.

4. **Downstream systems are blocked until foundational characterization stabilizes.** Weekly signal intelligence (Sprint E), historical snapshots, and all ML-adjacent work are blocked until the parity test passes.

5. **All analytical modules must have tests.** No `core/signals/` or `core/governance/` module ships without a corresponding test file. Zero-coverage analytical modules are not permitted.

6. **Weekly outputs must be signal-level or position-level.** Player-level outputs are prohibited in the weekly layer. Any player identifier appearing in a weekly output file is a bug.

7. **Registry coherence assertions run at build time.** If the registry build produces an incoherent output (e.g., blocked rows receiving `core_signal`), the build fails before writing files.

---

## 9. Success Criteria for Current Milestone

| Criterion | Verification |
|---|---|
| `core/signals/stability.py` implemented and tested | `pytest tests/test_signals_stability.py` passes |
| `core/signals/redundancy.py` implemented and tested | `pytest tests/test_signals_redundancy.py` passes |
| EDA-4 through EDA-7 complete with finding artifacts | CSVs present in `research/eda/findings/` |
| ≥ 10 signal-position rows characterized with non-placeholder values | `eda_07_signal_synthesis.csv` row count ≥ 10 with full column coverage |
| Registry contains `promotion_class` with all 6 values tested | `pytest tests/test_registry_promotion.py` passes; invariant assertions passing |
| Computed registry parity within tolerance | `pytest tests/test_registry_build_parity.py` passes |
| Reproducible execution without notebook intervention | 3-command sequence above runs clean |
| Weekly outputs contain real signal observations | `stable_signal_observations.csv`, `positional_signal_summary.csv`, `context_condition_notes.csv` present with non-placeholder content |
| No notebook-owned business logic | No classification rules or vocabulary assignments in notebook cells |

---

## Archival Notes

**`WEEKLY_ANALYTICS_PLATFORM_PLAN.md`** — superseded. Phases 1–6 are fully implemented and reflected in the current codebase. Phases 7–8 (historical snapshots, README update) are deferred non-goals for this milestone. Archive or delete.

**`ANALYTICAL_CONTENT_LAYER_PLAN.md`** — superseded by this document. Phase 1 is partially complete (`population.py` and `promotion.py` done; `stability.py` and `redundancy.py` remaining). The detailed implementation guidance (function signatures, thresholds, output contracts) is preserved in this roadmap at the appropriate sprint. Archive or delete.

**Duplicated concepts removed:**
- Architecture principles section (stated twice across both docs, consolidated into Layer Ownership above)
- Non-goals list (stated in both docs, unified in Section 7)
- Success criteria (existed in both docs with overlapping items, merged into Section 9)
- Reproducibility contract (stated twice, consolidated as the milestone success definition in Section 3)

**Scope items that were improperly layered in previous docs:**
- `ANALYTICAL_CONTENT_LAYER_PLAN.md` Phase 4 (weekly signal intelligence) introduced `WEEKLY_NOTE_TEMPLATES` with specific string constants inside a planning document. Those belong in code, not in a plan. This roadmap describes what the layer must do; the implementation detail lives in `weekly/signal_intelligence.py`.
- `WEEKLY_ANALYTICS_PLATFORM_PLAN.md` Phase 7 (historical snapshots) was listed as a sprint-level item in the same document as Phase 1 (registry contract). The scope gap between those two is too large. Phase 7 is now an explicit deferred non-goal.
- `ANALYTICAL_CONTENT_LAYER_PLAN.md` included full Python code blocks for every function in the plan document. That level of detail belongs in the implementation, not the roadmap. This document removes it while preserving the contract definitions that matter for sprint planning.
