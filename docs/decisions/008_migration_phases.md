# Decision 008 — Architecture Migration Phases

**Status:** ACTIVE  
**Applies to:** All directories, all import paths  
**Companion:** docs/adr/010-enforcement-contract.md  
**Prerequisite:** docs/adr/006-layer-architecture.md (frozen)

---

## Purpose

This document is the implementation playbook for migrating the current repository to the target architecture defined in Decision 007. The architecture is frozen and must not be redesigned here. Every phase in this document converts existing code — it does not introduce new concepts.

---

## 1. Current-State Gap Analysis

| Current Path | Target Path | Migration Type | Risk | Blocking Dependencies |
|---|---|---|---|---|
| `core/governance/` | `signals/lifecycle/` | rename + rewrite imports | medium | none |
| `core/signals/profiling.py`, `stability.py`, `redundancy.py`, `scoping.py` | `studies/kernels/` | move + rewrite imports | medium | Must strip FPL constants from `profiling.py` (`POSITION_MAP`, `POSITIONS`, `BLOCK_ORDER`) before move |
| `core/signals/population.py` | absorbed into calling study | isolate computation | medium | `POPULATION_ROBUSTNESS_VALUES` governance dep — cannot enter `studies/kernels/` |
| `core/target/distribution.py` | `studies/kernels/` | move + rewrite imports | low | none |
| `core/relationships/panel.py`, `tail.py` | `studies/kernels/correlation/` | move + rewrite imports | medium | `geometry.py` import must be removed first; constants passed as parameters |
| `core/relationships/geometry.py` | absorbed into `registry/sections.py` and `signals/eda/notebooks/_joint_helpers.py` | isolate computation | high | All consumers must inline the constants before file deleted |
| `core/relationships/association.py` | absorbed into `registry/sections.py` and `signals/eda/notebooks/` | isolate computation | high | Same as `geometry.py` |
| `registry/sections.py` (computation) | new study in `studies/experiments/` | isolate computation | high | `core/relationships` must resolve first |
| `registry/` (storage residual after extraction) | `signals/registry/` | rename | low | Computation isolation complete |
| `signals/eda/` | `studies/eda/` | move | low | none |
| `signals/lenses/` | `studies/lenses/` | move | low | none |
| `signals/experiments/` | `studies/experiments/` | move | low | none |
| `signals/synthesis/` | `studies/synthesis/` | move | low | none |
| `evaluation/captain.py`, `transfers.py`, `value.py` | `tests/integration/` | move | low | none |
| `evaluation/baselines.py`, `metrics.py`, `windows.py`, `features.py` | `tests/integration/` | move | low | evaluation test files moved first |
| `evaluation/rolling_xgi_study.py`, `minutes_stability_study.py` | `studies/experiments/` | move + rewrite imports | medium | `studies/kernels/` in place; `evaluation.*` imports rewritten |
| `report/db.py` | rewrite `dal.staging` → `dal.curated` accessor | rewrite imports | medium | new curated GW accessor in `dal/curated/` |
| `scorer/` | `intelligence/scoring/` | move | medium | `signals/lifecycle/` in place |
| `report/` | `intelligence/reporting/` | move | medium | `db.py` staging fix complete; `signals/lifecycle/` in place |
| `core/` (residual) | deleted | delete | low | all moves above complete |

---

## 2. Migration Dependency Graph

```
Phase 1 — evaluation/ split (test files)
  → no dependencies
  → unblocks: evaluation studies move in Phase 8

Phase 2 — core/governance/ → signals/lifecycle/
  → no dependencies
  → unblocks: scorer/ move, report/ move, registry/ rename, core/signals/ move

Phase 3 — core/signals/ + core/target/ → studies/kernels/
  → requires: Phase 2 (governance import path changes needed for population.py decision)
  → unblocks: evaluation study file move, future study authorship

Phase 4 — core/relationships/ refactor
  → requires: Phase 3 (kernels/ exists as landing target for panel + tail)
  → unblocks: Phase 5 (registry computation extraction)

Phase 5 — registry computation isolation (sections.py → study)
  → requires: Phase 4 (core/relationships resolved)
  → unblocks: Phase 6 (registry/ storage rename)

Phase 6 — registry/ → signals/registry/
  → requires: Phase 5 (computation extracted)
  → unblocks: Phase 11 (enforcement)

Phase 7 — signals/ research directories → studies/
  → requires: none structurally; safest after Phase 2 to avoid test churn
  → unblocks: cleaner studies/ namespace

Phase 8 — evaluation study files → studies/experiments/
  → requires: Phase 3 (studies/kernels/ in place)
  → requires: Phase 1 (evaluation/ package partially vacated)

Phase 9 — report/db.py staging fix
  → requires: none structurally
  → unblocks: Phase 10 (report/ move)

Phase 10 — scorer/ + report/ → intelligence/scoring/ + intelligence/reporting/
  → requires: Phase 2 (signals/lifecycle/ in place)
  → requires: Phase 9 (db.py staging clean)

Phase 11 — enforcement
  → requires: all phases complete; core/ deleted
```

---

## 3. Execution Phases

---

### Phase 1 — evaluation/ split (test harness files) ✓ COMPLETE

**Goal:** Remove upward imports from `evaluation/` by moving the three files that import `intelligence.*` into `tests/integration/`.

**Files/directories touched:**
- `evaluation/captain.py`
- `evaluation/transfers.py`
- `evaluation/value.py`
- `evaluation/baselines.py`
- `evaluation/metrics.py`
- `evaluation/windows.py`
- `evaluation/features.py`
- `tests/integration/` (create)
- `tests/test_evaluation_captain.py`, `tests/test_evaluation_transfers.py`, `tests/test_evaluation_core.py`, `tests/test_evaluation_features.py`

**Exact operations:**
1. Create `tests/integration/__init__.py`
2. Move `evaluation/captain.py`, `transfers.py`, `value.py` → `tests/integration/`
3. Move `evaluation/baselines.py`, `metrics.py`, `windows.py`, `features.py` → `tests/integration/`
4. Update import paths in the four test files (`from evaluation.X` → `from tests.integration.X`)
5. Verify `evaluation/rolling_xgi_study.py` and `minutes_stability_study.py` remain in `evaluation/`
6. Run full test suite; confirm moved tests still pass

**Completion criteria:**
- No file in `evaluation/` imports from `intelligence.*`
- `tests/integration/` contains the seven moved files
- All moved tests pass
- `evaluation/` contains only `rolling_xgi_study.py`, `minutes_stability_study.py`, `__init__.py`

**Forbidden during this phase:**
- Modifying `evaluation/rolling_xgi_study.py` or `minutes_stability_study.py`
- Touching any DAL file
- Touching `scorer/`, `report/`, `registry/`

---

### Phase 2 — core/governance/ → signals/lifecycle/ ✓ COMPLETE

**Goal:** Establish `signals/lifecycle/` as the canonical governance path and rewrite all consumers.

**Files/directories touched:**
- `core/governance/` (all files)
- `signals/lifecycle/` (create)
- `scorer/signals.py`
- `report/runner.py`
- `registry/runner.py`, `registry/assembly.py`, `registry/comparison.py`, `registry/config.py`, `registry/inputs.py`
- All tests importing `core.governance.*` (~15 test files)

**Exact operations:**
1. Create `signals/lifecycle/__init__.py` mirroring `core/governance/__init__.py` exports
2. Copy `lifecycle.py`, `loader.py`, `promotion.py`, `schema.py`, `semantics.py`, `validation.py` into `signals/lifecycle/`
3. Update internal imports within the copied files (`from core.governance.X` → `from signals.lifecycle.X`)
4. Rewrite all external consumers: `scorer/signals.py`, `report/runner.py`, `registry/runner.py`, `registry/assembly.py`, `registry/comparison.py`, `registry/config.py`, `registry/inputs.py`
5. Rewrite all test files importing `core.governance.*`
6. Run full test suite
7. Delete `core/governance/`

**Completion criteria:**
- `grep -rn "from core.governance" --include="*.py"` returns zero matches
- All tests pass
- `signals/lifecycle/` exports the same public interface `core/governance/` did

**Forbidden during this phase:**
- Changing any logic in the governance modules — rename only
- Touching `core/relationships/`, `core/signals/`, `core/target/`
- Any concurrent DAL changes

---

### Phase 3 — core/signals/ + core/target/ → studies/kernels/ ✓ COMPLETE (partial)

**Goal:** Move domain-agnostic statistical utilities into `studies/kernels/`; isolate FPL-specific files.

**Files/directories touched:**
- `core/signals/profiling.py`, `stability.py`, `redundancy.py`, `scoping.py`
- `core/signals/population.py` (special handling — not domain-free)
- `core/target/distribution.py`
- `studies/kernels/` (create)
- `signals/eda/notebooks/_signal_distribution_helpers.py`, `_target_distribution_helpers.py`

**Exact operations:**
1. Create `studies/kernels/__init__.py`
2. Audit `profiling.py`: remove `POSITION_MAP`, `POSITIONS`, `BLOCK_ORDER` constants — pass as parameters at call sites, or move constants to calling study
3. Move `profiling.py`, `stability.py`, `redundancy.py`, `scoping.py` → `studies/kernels/`
4. Move `core/target/distribution.py` → `studies/kernels/distribution.py`
5. For `population.py`: it imports `POPULATION_ROBUSTNESS_VALUES` from governance schema — FPL-specific, not a kernel. Move into the EDA study that consumes it, not into `studies/kernels/`
6. Update import paths in `signals/eda/notebooks/_signal_distribution_helpers.py` and `_target_distribution_helpers.py`
7. Update all test files importing `core.signals.*` and `core.target.*`
8. Run full test suite
9. Delete `core/signals/`, `core/target/`

**Completion criteria:**
- `grep -rn "from core.signals\|from core.target" --include="*.py"` returns zero matches
- No file in `studies/kernels/` imports from `signals.*` or `intelligence.*` or contains FPL-specific constants
- All tests pass

**Forbidden during this phase:**
- Moving `core/relationships/` (Phase 4)
- Changing statistical logic — move only
- Adding new utility functions to kernels

---

### Phase 4 — core/relationships/ refactor ✓ COMPLETE

**Goal:** Move domain-agnostic correlation utilities to `studies/kernels/correlation/`; inline FPL-specific classification into consuming study.

**Files/directories touched:**
- `core/relationships/panel.py`, `tail.py`
- `core/relationships/geometry.py`, `association.py`
- `registry/sections.py` (receives inlined geometry/association constants)
- `signals/eda/notebooks/_joint_helpers.py` (receives inlined geometry/association constants)
- `studies/kernels/correlation/` (create)

**Exact operations:**
1. Create `studies/kernels/correlation/__init__.py`
2. In `panel.py`: remove `from core.relationships.geometry import ...`; make all geometry constants parameters
3. In `tail.py`: same — remove geometry dep, parameterize
4. Copy `panel.py` and `tail.py` (now geometry-free) → `studies/kernels/correlation/`
5. In `registry/sections.py`: inline the geometry and association constants/logic directly
6. In `signals/eda/notebooks/_joint_helpers.py`: inline the geometry/association constants used there
7. Update all callers of `decompose_rho` and `haul_concentration` to new import path
8. Run full test suite
9. Delete `core/relationships/`

**Completion criteria:**
- `grep -rn "from core.relationships" --include="*.py"` returns zero matches
- `studies/kernels/correlation/panel.py` and `tail.py` have zero FPL-specific imports
- `registry/sections.py` and `_joint_helpers.py` contain all needed geometry constants inline
- All tests pass

**Forbidden during this phase:**
- Removing computation from `registry/sections.py` — that is Phase 5
- Refactoring the statistical logic in `panel.py` or `tail.py`

---

### Phase 5 — registry computation isolation

**Goal:** Extract `registry/sections.py` statistical computation into a named study artifact; leave registry as schema-validation and storage only.

**Files/directories touched:**
- `registry/sections.py`
- `registry/assembly.py`
- `registry/runner.py`
- New: `studies/experiments/registry_sections_study.py`

**Exact operations:**
1. Create `studies/experiments/__init__.py` if not exists
2. Create `studies/experiments/registry_sections_study.py`: contains the moved computation from `sections.py`; reads DAL prepared dataset; writes classification artifact to `studies/runs/`
3. Strip all statistical computation from `registry/sections.py`; make it a thin reader of the classification artifact produced by the study
4. Update `registry/runner.py` to expect a pre-computed artifact path rather than computing inline
5. Update `registry/assembly.py` — remove `from core.relationships import assign_association_class, consolidate_flags` (now inlined in the study)
6. Run full test suite; confirm registry build produces identical output when study artifact is present

**Completion criteria:**
- `registry/sections.py` contains no statistical computation; reads study artifact only
- `registry/assembly.py` contains no `core.*` imports
- `studies/experiments/registry_sections_study.py` produces an artifact the registry can consume
- All registry build tests pass

**Forbidden during this phase:**
- Renaming `registry/` to `signals/registry/` — that is Phase 6
- Changing the schema of the registry output artifact
- Modifying DAL

---

### Phase 6 — registry/ → signals/registry/

**Goal:** Rename the now-computation-free registry package to its target path.

**Files/directories touched:**
- `registry/` (all files)
- `signals/registry/` (target)
- All consumers importing `registry.*`

**Exact operations:**
1. Move all files from `registry/` → `signals/registry/`
2. Update all internal imports (`from registry.X` → `from signals.registry.X`)
3. Update test files importing `registry.*`
4. Run full test suite
5. Delete `registry/`

**Completion criteria:**
- `grep -rn "from registry\." --include="*.py"` returns zero matches
- `signals/registry/` is the canonical package
- All tests pass

**Forbidden during this phase:**
- Any further logic changes to the registry
- Touching scorer, report, or intelligence layer

---

### Phase 7 — signals/ research directories → studies/

**Goal:** Move EDA, lenses, experiments, and synthesis directories from `signals/` to `studies/`.

**Files/directories touched:**
- `signals/eda/` → `studies/eda/`
- `signals/lenses/` → `studies/lenses/`
- `signals/experiments/` → `studies/experiments/`
- `signals/synthesis/` → `studies/synthesis/`

**Exact operations:**
1. Move `signals/eda/` → `studies/eda/`
2. Move `signals/lenses/` → `studies/lenses/`
3. Move `signals/experiments/` → `studies/experiments/`
4. Move `signals/synthesis/` → `studies/synthesis/`
5. Update any internal notebook imports referencing `signals.eda.*` paths
6. Verify no runtime Python import from `signals.eda.*` exists outside tests
7. Run test suite

**Completion criteria:**
- `signals/` contains only `registry/` and `lifecycle/` subdirectories
- No `.py` file imports `from signals.eda`, `from signals.lenses`, `from signals.experiments`, `from signals.synthesis`
- All tests pass

**Forbidden during this phase:**
- Modifying notebook content
- Touching `signals/registry/` or `signals/lifecycle/`

---

### Phase 8 — evaluation study files → studies/experiments/

**Goal:** Move the two remaining study files from `evaluation/` into `studies/experiments/` and rewrite their imports.

**Files/directories touched:**
- `evaluation/rolling_xgi_study.py`
- `evaluation/minutes_stability_study.py`
- `studies/experiments/`
- `tests/test_rolling_xgi_study.py`, `tests/test_minutes_stability_study.py`

**Exact operations:**
1. In `rolling_xgi_study.py`: rewrite `from evaluation.metrics import ...` and `from evaluation.windows import ...` to equivalent functions from `studies/kernels/`
2. In `minutes_stability_study.py`: same import rewrite
3. Move both files to `studies/experiments/`
4. Update test import paths
5. Run test suite
6. Delete `evaluation/__init__.py` and the `evaluation/` directory

**Completion criteria:**
- `evaluation/` directory does not exist
- `studies/experiments/rolling_xgi_study.py` and `minutes_stability_study.py` pass their tests
- No file imports from `evaluation.*`

**Forbidden during this phase:**
- Changing the statistical logic in the study files
- Adding new experiments

---

### Phase 9 — report/db.py staging fix

**Goal:** Remove `report/db.py`'s direct `dal.staging` dependency by promoting GW resolution to a curated DAL accessor.

**Files/directories touched:**
- `dal/curated/gameweek_context.py`
- `report/db.py`
- `tests/test_integrated_pipeline.py`

**Exact operations:**
1. Read `dal/curated/gameweek_context.py` — determine if GW resolution is already available
2. If not: add `resolve_target_gw(db_path: Path) -> int` to `dal/curated/gameweek_context.py`
3. Rewrite `report/db.py` to import from `dal.curated.gameweek_context` instead of `dal.staging`
4. Rewrite or document the `get_staged_player_histories` call — either promote to curated or document the staging exception in `dal/DAL_CONTRACT.md`
5. Run test suite

**Completion criteria:**
- `report/db.py` contains no `from dal.staging import` statement
- `tests/test_integrated_pipeline.py` passes
- If any staging access is retained: exception documented in `dal/DAL_CONTRACT.md`

**Forbidden during this phase:**
- Moving `report/` to `intelligence/reporting/` — that is Phase 10
- Changing report business logic

---

### Phase 10 — scorer/ + report/ → intelligence/scoring/ + intelligence/reporting/

**Goal:** Move the intelligence-layer packages to their target subpaths.

**Files/directories touched:**
- `scorer/` → `intelligence/scoring/`
- `report/` → `intelligence/reporting/`
- All tests importing `scorer.*` or `report.*`

**Exact operations:**
1. Create `intelligence/scoring/__init__.py`; move all `scorer/` files into it
2. Update all internal imports (`from scorer.X` → `from intelligence.scoring.X`)
3. Update all test files importing `scorer.*`
4. Create `intelligence/reporting/__init__.py`; move all `report/` files into it
5. Update all internal imports (`from report.X` → `from intelligence.reporting.X`)
6. Update all test files importing `report.*`
7. Run full test suite
8. Delete `scorer/`, `report/`

**Completion criteria:**
- `grep -rn "from scorer\.\|from report\." --include="*.py"` returns zero matches
- `intelligence/scoring/runner.py` and `intelligence/reporting/runner.py` are the operational entry points
- All tests pass

**Forbidden during this phase:**
- Changing scorer or report logic
- Touching DAL or signals layers

---

### Phase 11 — enforcement

**Goal:** Wire `import-linter` and the CI grep check so violations fail the build.

**Files/directories touched:**
- `.importlinter` (create)
- CI config or `Makefile` (add grep check)

**Exact operations:**
1. Install `import-linter` in dev dependencies
2. Write `.importlinter` with one contract per layer boundary matching Section 2 of `docs/adr/010-enforcement-contract.md`
3. Run `lint-imports` — fix any remaining violations surfaced
4. Add to CI: `grep -rn "from studies\.\(lenses\|eda\|experiments\|synthesis\)" --include="*.py" $(find . -not -path "./studies/*" -not -path "./tests/*")` — fail on non-zero exit
5. Delete `core/` (now empty)
6. Run full test suite

**Completion criteria:**
- `lint-imports` passes with zero violations
- CI grep check passes
- `core/` directory does not exist
- All tests pass

**Forbidden during this phase:**
- Adding suppression rules to `import-linter` to hide existing violations

---

## 4. Recommended Phase Order

```
Phase 1  → establishes clean evaluation/ boundary before any study migration begins
Phase 2  → governance rename unblocks scorer/, report/, registry/ moves; nothing else can complete without it
Phase 3  → kernels/ must exist before study files can rewrite their evaluation.* imports
Phase 4  → relationships must resolve before registry computation can be extracted cleanly
Phase 5  → computation must leave registry before registry is renamed
Phase 6  → rename only after Phase 5; no logic risk at this point
Phase 7  → signals/ research directories are structurally independent; safe here; clears signals/ namespace
Phase 8  → requires Phase 3 (kernels target exists) and Phase 1 (evaluation/ partially vacated)
Phase 9  → staging fix is prerequisite for Phase 10; independent of phases 3–8
Phase 10 → scorer/ and report/ moves require Phase 2 (lifecycle path) and Phase 9 (staging clean)
Phase 11 → enforcement only after all structural moves complete and core/ deleted
```

---

## 5. First Executable Slice

**Phase 1, subset:** Move `evaluation/captain.py`, `evaluation/transfers.py`, `evaluation/value.py` to `tests/integration/`.

**Exact files touched:**
- `evaluation/captain.py` → `tests/integration/captain.py`
- `evaluation/transfers.py` → `tests/integration/transfers.py`
- `evaluation/value.py` → `tests/integration/value.py`
- `tests/test_evaluation_captain.py` — update import path
- `tests/test_evaluation_transfers.py` — update import path

**Exact imports rewritten:**
```python
# before
from evaluation.captain import evaluate_captain_heuristic
# after
from tests.integration.captain import evaluate_captain_heuristic
```

**Exact directories created:**
- `tests/integration/__init__.py`

**Exact directories untouched:**
- `dal/`, `scorer/`, `report/`, `registry/`, `signals/`, `core/`, `intelligence/`, `studies/`
- `evaluation/baselines.py`, `evaluation/metrics.py`, `evaluation/windows.py`, `evaluation/features.py`
- `evaluation/rolling_xgi_study.py`, `evaluation/minutes_stability_study.py`

**Rollback strategy:**
Move the three files back to `evaluation/`; revert the two test file import lines. Three `git mv` operations; fully reversible in one commit revert.

**Success criteria:**
- `grep -rn "from intelligence\." evaluation/` returns zero matches
- `pytest tests/test_evaluation_captain.py tests/test_evaluation_transfers.py` passes
- No other test failures

**Estimated blast radius:**
3 source files moved, 2 test files modified, 1 directory created. Zero production code paths affected.

---

## 6. Freeze Protection Rules

1. No two layer boundaries move in the same commit. One phase = one commit or one PR.
2. No rename and logic rewrite in the same commit. Move files first; rewrite logic in a follow-on commit if needed.
3. No import path is rewritten until the target module exists and its tests pass at the new path.
4. No phase proceeds if the test suite is failing from a prior phase.
5. No new shared utility directory may be created. `studies/kernels/` is the only permitted destination for extracted utilities, and only for domain-agnostic functions.
6. No analytical feature work during the migration. Signal studies, scoring changes, and report logic changes are blocked until Phase 11 completes.
7. No modification to `docs/adr/006-layer-architecture.md` or `docs/adr/010-enforcement-contract.md` during migration. They are frozen. If a migration step contradicts the contract, stop and raise it explicitly.
8. No file in `studies/kernels/` may be committed without a reviewer confirming: zero governance imports, zero FPL-specific constants, generic numeric or DataFrame inputs and outputs.
9. No `dal.staging` import outside `dal/` and `tests/` may be introduced. `report/db.py` is the only existing violation and must be fixed in Phase 9, not worked around.
10. No suppression or exclusion rule may be added to `import-linter` to bypass a real violation. Every violation surfaced in Phase 11 must be fixed in code.
