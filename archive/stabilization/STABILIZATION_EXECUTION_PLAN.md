# Operational Usability Stabilization Plan

**Status:** Ready to execute  
**Branch:** `stabilization/dal-hardening`  
**Baseline:** 738 passed, 1 skipped | import-linter clean  
**Assessment date:** 2026-05-21  
**Scope:** Operational maturity, onboarding clarity, execution discoverability, explainability surfacing

---

## Governing Constraints

- Green suite preserved after every slice (738 passed, 1 skipped minimum)
- No architecture changes — layer structure is frozen
- No new top-level packages
- No namespace churn or directory reorganization outside declared scope
- Every slice independently committable and reversible
- Architecture invariants enforced at all times

---

## Slice Classification Index

| # | Name | Type | Priority | Execution |
|---|---|---|---|---|
| S1 | CONTEXT.md truth alignment | doc-only | P0 | Auto |
| S2 | ROADMAP correction + 3-command fix | doc-only | P0 | Auto |
| S3 | Governance test real-directory fix | test-only | P0 | Auto |
| S4 | pyproject.toml dependency hygiene | metadata-only | P1 | Auto |
| S5 | Integration test marking | test-only | P1 | Auto |
| S7 | Makefile execution targets | operational | P1 | Auto |
| S9 | Rho weights + methodology callout in scorer HTML | operational + explainability | P1 | Auto |
| S8 | Bootstrap registry artifact | artifact-producing | P1 | Approve |
| S6 | conftest.py + db_path fixture | test-only | P1 | Approve |
| S10 | Stale doc archival + dead directory removal | doc-only | P2 | Auto |
| S11 | tests/integration/ → tests/helpers/ rename | test-only | P2 | Approve |

---

## Recommended Execution Order

```
S1  — CONTEXT.md truth alignment              [doc-only]         25 min  auto
S2  — ROADMAP correction + 3-command fix      [doc-only]         20 min  auto
S3  — Governance test real-dir fix            [test-only]        20 min  auto
S4  — pyproject.toml dependency hygiene       [metadata-only]    10 min  auto
S5  — Integration test marking                [test-only]        35 min  auto
S7  — Makefile execution targets              [operational]      30 min  auto
S9  — Rho weights + methodology callout       [explainability]   45 min  auto
─────────────────────────────────────────────────────────────────────────────
S8  — Bootstrap registry artifact             [artifact]         15 min  APPROVE
S6  — conftest.py + db_path fixture           [test-only]        60 min  APPROVE
S10 — Stale doc archival + dir cleanup        [doc-only]         20 min  auto
S11 — tests/integration/ rename              [test-only]         30 min  APPROVE
```

After S9 is complete the system is operationally mature. S10 and S11 are polish, not stability.

---

## Phase 1 — Operational Truth Alignment

### S1 — CONTEXT.md truth alignment

**Type:** doc-only | **Priority:** P0 | **Execute:** Auto

**Objective:** The primary onboarding document must accurately describe the current four-layer architecture, actual test count, actual directory structure, and current "what is next."

**Why this slice exists:** CONTEXT.md shows `core/`, `registry/`, `research/`, `pipeline/` in the directory tree — none exist. It says 442 tests (actual: 739). "What is next" is lens study design (actual: Phase 11 enforcement). Every downstream decision a new engineer makes from this document is made against a false model.

**Exact files touched:**
- `CONTEXT.md` — sections 3, 5, 6 only. Sections 1–2, 4, 7–9 are accurate and must not change.

**Scope of changes:**

Section 3 directory tree — replace with the actual current structure:
```
fpl-intelligence/
├── archive/         — retired code (pipeline_legacy/) and planning documents
├── dal/             — data access layer — staging, intermediate, curated, state, validation, prepared
├── docs/            — architectural and decision documents
│   ├── architecture/   — DAL_CONTRACT.md, DOWNSTREAM_DEPENDENCY_GOVERNANCE.md, SYSTEM_CONTEXT.md
│   ├── decisions/      — per-signal and design decision records
│   └── stabilization/  — stabilization wave history and Phase 11 plan
├── examples/        — quickstart script for DAL end-to-end validation
├── intelligence/    — operational intelligence layer
│   ├── reporting/   — weekly registry snapshot runner and output generators
│   └── scoring/     — player scoring from governed registry manifest
├── outputs/         — runtime artifacts (scorer HTML, registry CSVs, weekly reports)
├── signals/         — signal governance layer
│   ├── evaluation/  — EVAL_DESIGN.md (locked evaluation framework)
│   ├── lifecycle/   — lifecycle enforcement, registry loading, promotion schema
│   └── registry/    — registry build pipeline (runner, assembly, config, inputs)
├── studies/         — analytical methodology layer
│   ├── eda/         — system EDA notebooks and findings (complete, closed)
│   ├── experiments/ — experiment scaffolds (blocked on synthesis)
│   ├── kernels/     — reusable statistical kernels
│   └── lenses/      — lens study scaffolds (pre-investigational)
└── tests/           — test suite (739 tests as of Phase 11)
```

Section 5 current state — update DAL status to "COMPLETE (739 tests passing)". Update signal registry row to reflect `SIGNAL_REGISTRY.md` is empty but `eda_03_joint_registry.csv` holds the governed signal set. Mark SYNTH-01 and experiments as correctly blocked.

Section 6 "what is next" — replace lens study language with Phase 11 enforcement items.

**Blast radius:** One document. Zero code changes. Zero test impact.

**Rollback:** `git checkout CONTEXT.md`

**Validation:**
1. Read section 3 tree, run `ls` — every listed directory must exist; none absent.
2. `pytest --collect-only -q | tail -1` — confirm 739. Update the count in the document.
3. Read section 5 cold — every status must match observable reality.
4. Read section 6 cold — "what is next" must match current work.

**Expected test impact:** None.
**Estimated time:** 25 minutes.

---

### S2 — IMPLEMENTATION_ROADMAP.md correction + 3-command fix

**Type:** doc-only | **Priority:** P0 | **Execute:** Auto

**Objective:** The milestone verification sequence must run without errors. Stale sprint content must be clearly marked as historical.

**Why this slice exists:** The 3-command sequence references `python -m registry_build.runner` (does not exist; correct: `python -m signals.registry.runner`) and `python -m weekly.runner` (does not exist; correct: `python -m intelligence.reporting.runner`). Sections 4–5 reference `core/`, `analytics.*`, `build/`, `weekly/` namespaces — all retired.

**Exact files touched:**
- `docs/IMPLEMENTATION_ROADMAP.md` — Section 3 code block, Section 4 layer ownership, Sprint headings

**Scope of changes:**

Section 3 code block — replace with the working sequence:
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

Section 4 — prepend: `> **Archived reference** — layer names below reflect the pre-migration architecture. Current layer names: dal/, signals/, studies/, intelligence/.`

Sprint headings A–E — prepend each with `[COMPLETE]` and a single-line reference to the current implementation path:
- Sprint A → `studies/kernels/stability.py`, `studies/kernels/redundancy.py`
- Sprint B → `studies/eda/notebooks/`
- Sprint C → `studies/eda/notebooks/`, `signals/lifecycle/promotion.py`
- Sprint D → `dal/prepared/analytical_dataset.py`, `signals/registry/runner.py`
- Sprint E → `intelligence/reporting/`

**Blast radius:** One document. Zero code changes.

**Rollback:** `git checkout docs/IMPLEMENTATION_ROADMAP.md`

**Validation:**
1. Copy the Section 3 block and run each command with valid arguments — all three must exit 0.
2. `grep -n "registry_build.runner\|weekly.runner" docs/IMPLEMENTATION_ROADMAP.md` — must return zero results.

**Expected test impact:** None.
**Estimated time:** 20 minutes.

---

## Phase 2 — Architecture Contract Hardening

### S3 — Governance test real-directory fix

**Type:** test-only | **Priority:** P0 | **Execute:** Auto

**Objective:** `test_downstream_governance.py` must scan the actual downstream source directories — `intelligence/` and `studies/` — not ghost directories.

**Why this slice exists:** `_DOWNSTREAM_DIRS` currently lists `[signals/, weekly/, build/, core/]`. Three of those (`weekly/`, `build/`, `core/`) do not exist. The test passes vacuously for them. `intelligence/` and `studies/` — the actual downstream consumers — are not scanned. The governance contract is unenforced on the directories where violations would appear.

**Exact files touched:**
- `tests/test_downstream_governance.py` — lines 21–26 (`_DOWNSTREAM_DIRS` list), module docstring, `_STAGING_ALLOWLIST` block

**Scope of changes:**
```python
# Before
_DOWNSTREAM_DIRS = [
    _PROJECT_ROOT / "signals",
    _PROJECT_ROOT / "weekly",
    _PROJECT_ROOT / "build",
    _PROJECT_ROOT / "core",
]

# After
_DOWNSTREAM_DIRS = [
    _PROJECT_ROOT / "signals",
    _PROJECT_ROOT / "studies",
    _PROJECT_ROOT / "intelligence",
]
```

Also update module docstring (line 3): `"research/, weekly/, build/, core/"` → `"signals/, studies/, intelligence/"`.

Also remove the `_STAGING_ALLOWLIST` entry for `weekly/db.py` — that file does not exist. The allowlist becomes empty `{}`.

**Pre-flight scan (required before making the change):**
```bash
grep -rn "sqlite3\|pd.read_sql\|read_sql_query" intelligence/ studies/ --include="*.py" | grep -v __pycache__
grep -rn "from pipeline\.\|import pipeline\." intelligence/ studies/ --include="*.py" | grep -v __pycache__
grep -rn "from dal\.staging\|from dal\.intermediate" intelligence/ studies/ --include="*.py" | grep -v __pycache__
```
If any hits are returned, fix violations before committing this slice.

**Blast radius:** One test file, three lines changed. The test will now actually scan `intelligence/` and `studies/`.

**Rollback:** `git checkout tests/test_downstream_governance.py`

**Validation:**
1. Run pre-flight scan — confirm zero violations.
2. `pytest tests/test_downstream_governance.py -v` — all tests pass.
3. Temporarily insert `import sqlite3` in `intelligence/__init__.py`, confirm test catches it, revert.

**Expected test impact:** No count change. All tests remain green.
**Estimated time:** 20 minutes (including pre-flight scan).

---

## Phase 3 — Dependency Hygiene

### S4 — pyproject.toml dependency hygiene

**Type:** metadata-only | **Priority:** P1 | **Execute:** Auto

**Objective:** Remove the stale `pipeline` package reference and the unused `mlflow` dependency.

**Why this slice exists:** `packages = ["pipeline"]` references an archived directory — the project cannot be packaged. `mlflow>=3.11.1` is never imported in any source file. It adds Flask, SQLAlchemy, and their full dependency trees with zero benefit, and misrepresents the system as an ML experiment platform.

**Exact files touched:**
- `pyproject.toml` — remove `[tool.hatch.build.targets.wheel]` block (3 lines), remove `"mlflow>=3.11.1"` from dependencies (1 line)
- `uv.lock` — regenerated by `uv lock`

**Scope of changes:**

Remove from `pyproject.toml`:
```toml
# Remove entirely:
[tool.hatch.build.targets.wheel]
packages = ["pipeline"]

# Remove from dependencies list:
"mlflow>=3.11.1",
```

Then run `uv lock` to update the lockfile.

Do not replace `packages = ["pipeline"]` with the current package list — the project is not intended to be distributed as a wheel.

**Blast radius:** `pyproject.toml` + `uv.lock` only. Zero source code changes.

**Rollback:** `git checkout pyproject.toml uv.lock`

**Validation:**
1. `python -c "import mlflow"` — must fail with `ModuleNotFoundError`.
2. `python -c "from dal.access import get_curated_spine"` — must succeed.
3. `pytest --collect-only -q | tail -1` — still 739.

**Expected test impact:** None. No test imports mlflow.
**Estimated time:** 10 minutes.

---

## Phase 4 — Test Governance

### S5 — Integration test marking

**Type:** test-only | **Priority:** P1 | **Execute:** Auto

**Objective:** All tests requiring a live database must carry `@pytest.mark.integration`. Running `pytest -m "not integration"` must produce a fully DB-free suite on any machine.

**Why this slice exists:** Thirteen test files hit `~/.fpl/fpl.db` without the `integration` marker. The marker is already declared in `pyproject.toml` and is correct for `test_registry_build_parity.py`. The pattern is established; it is simply underused. Without this, a developer without the DB gets confusing failures rather than a controlled exclusion.

**Exact files touched (13 files):**
- `tests/test_curated_spine.py`
- `tests/test_dal_bgw.py`
- `tests/test_dal_dgw.py`
- `tests/test_dal_completeness.py`
- `tests/test_dal_grain.py`
- `tests/test_dal_invariants.py`
- `tests/test_dal_nulls.py`
- `tests/test_dal_joins.py`
- `tests/test_integrated_pipeline.py`
- `tests/test_integrated_research.py`
- `tests/test_integrated.py`
- `tests/test_state_rolling_windows.py`
- `tests/test_state.py`

**Change pattern:** Add at module level, immediately after imports:
```python
import pytest
pytestmark = pytest.mark.integration
```

For files already using `@pytest.mark.skipif(not DB_PATH.exists(), ...)` on individual tests: replace those individual marks with the module-level `pytestmark` instead — do not stack both.

Read each file individually before applying — `pytestmark` marks ALL tests in the module. If any test in the file does not require the DB, it must not receive the marker.

**Blast radius:** 13 test files, one line added per file. No logic changes. Total test count unchanged.

**Rollback:** `git checkout tests/test_curated_spine.py tests/test_dal_bgw.py ...` (per file) or `git checkout tests/` (all).

**Validation:**
1. `pytest --collect-only -q | tail -1` — still 739.
2. `pytest -m "not integration" --collect-only -q` — reduced count, no DB-path references in collected set.
3. `pytest -m "not integration" -x` — exits 0 on a machine without a database.
4. `pytest -m integration --collect-only -q` — collects exactly the tests from the 13 files above plus `test_registry_build_parity.py`.

**Expected test impact:** Zero count change. Zero result change. Marker metadata only.
**Estimated time:** 35 minutes.

---

### S6 — conftest.py + db_path fixture

**Type:** test-only | **Priority:** P1 | **Execute:** Approve

**Objective:** Centralize live-DB path resolution in a single pytest fixture that respects the `FPL_DB_PATH` environment variable already implemented in `dal/config.py`.

**Why this slice exists:** `DB_PATH = Path.home() / ".fpl" / "fpl.db"` is hardcoded in 13 test files. The `FPL_DB_PATH` override from Wave 6 is not reflected in the test harness. Changing the DB path strategy requires touching all 13 files.

**Dependency:** S5 must be complete first.

**Exact files touched:**
- `tests/conftest.py` — new file
- 13 integration-marked test files from S5 — module-level `DB_PATH` constant replaced with fixture

**Scope of changes:**

`tests/conftest.py` (new):
```python
import os
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def db_path() -> Path:
    env = os.environ.get("FPL_DB_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".fpl" / "fpl.db"
```

Each integration test file: replace module-level `DB_PATH` constant. Tests using `DB_PATH` as a call-site argument must accept `db_path` as a fixture parameter. Assess each file — some may use `DB_PATH` in module-level contexts (parametrize decorators, class setup) that cannot directly receive a fixture; use `os.environ.get("FPL_DB_PATH")` inline for those.

**Blast radius:** New file + function signature changes in 13 test files. No logic changes. Moderate risk — test function signatures change.

**Rollback:** `git rm tests/conftest.py` + revert the 13 files — one commit.

**Validation:**
1. `pytest -m integration -x` — passes with `FPL_DB_PATH=/path/to/fpl.db`.
2. `FPL_DB_PATH=/nonexistent pytest -m integration --collect-only` — collects without error.
3. `pytest -m "not integration" -x` — still passes cleanly.
4. Test count remains exactly 739.

**Expected test impact:** Zero count change. Signature change only.
**Estimated time:** 60 minutes (per-file assessment required).

---

## Phase 5 — Execution Discoverability

### S7 — Makefile execution targets

**Type:** operational | **Priority:** P1 | **Execute:** Auto

**Objective:** A new engineer must be able to run `make help` and understand how to exercise every part of the system.

**Why this slice exists:** `make` currently exposes three linting targets and `make test`. The four operational runners have well-defined CLIs but are completely undiscoverable via `make`. The execution flow — DAL → registry build → scoring → weekly reporting — is invisible from the project root.

**Exact files touched:**
- `Makefile` — add targets; preserve all existing targets unchanged

**Scope of changes — targets to add:**

```makefile
.PHONY: help quickstart test test-unit prepare build-registry score weekly

## Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
	@echo ""
	@echo "Execution targets require FPL_DB_PATH or GW/REGISTRY args."

## Verify DAL end-to-end against real DB (DB_PATH= arg or FPL_DB_PATH env var)
quickstart:
	python examples/quickstart.py $(DB_PATH)

## Run full test suite
test:
	pytest

## Run DB-free tests only (no live database required)
test-unit:
	pytest -m "not integration"

## Build analytical dataset: make prepare GW=36
prepare:
ifndef GW
	$(error GW is required: make prepare GW=36)
endif
	python -m dal.prepared.analytical_dataset \
	  --gw $(GW) \
	  --output-path outputs/prepared_gw$(GW).csv

## Build governed registry artifact: make build-registry GW=36
build-registry:
ifndef GW
	$(error GW is required: make build-registry GW=36)
endif
	python -m signals.registry.runner \
	  --gw $(GW) \
	  --source-registry-path studies/eda/findings/eda_03_joint_registry.csv \
	  --output-dir outputs/registry/gw$(GW)

## Score players for a gameweek: make score GW=36
score:
ifndef GW
	$(error GW is required: make score GW=36)
endif
	python -m intelligence.scoring.runner \
	  --gw $(GW) \
	  --db-path $(or $(FPL_DB_PATH),$(HOME)/.fpl/fpl.db) \
	  --output-dir outputs/scorer \
	  --registry-path outputs/registry/gw$(GW)/registry.csv

## Generate weekly signal intelligence: make weekly GW=36
weekly:
ifndef GW
	$(error GW is required: make weekly GW=36)
endif
	python -m intelligence.reporting.runner \
	  --gw $(GW) \
	  --registry-path outputs/registry/gw$(GW)/registry.csv
```

**Blast radius:** Makefile only. All existing targets preserved. No source code changes.

**Rollback:** `git checkout Makefile`

**Validation:**
1. `make help` — prints all targets with descriptions.
2. `make test-unit` — exits 0 on any machine.
3. `make build-registry GW=36` — exits 0 when source registry exists.
4. `make score GW=36` — exits 0 when DB and `outputs/registry/gw36/registry.csv` exist.

**Expected test impact:** None.
**Estimated time:** 30 minutes.

---

## Phase 6 — Artifact Bootstrap

### S8 — Bootstrap registry artifact in `outputs/registry/`

**Type:** artifact-producing | **Priority:** P1 | **Execute:** Approve

**Objective:** `outputs/registry/gw36/` must exist so the lifecycle enforcement gate passes and the scorer and weekly runner can be run end-to-end from a fresh clone.

**Why this slice exists:** `signals/lifecycle/lifecycle.py:assert_operational_safe()` rejects registries from `studies/eda/`. The correct source is `outputs/registry/`. This directory does not exist. The scorer and weekly runner cannot be executed end-to-end without first producing this artifact.

**Command to produce:**
```bash
python -m signals.registry.runner \
  --gw 36 \
  --source-registry-path studies/eda/findings/eda_03_joint_registry.csv \
  --output-dir outputs/registry/gw36
```

**Exact files produced:**
- `outputs/registry/gw36/registry.csv`
- `outputs/registry/gw36/build_metadata.json`

**Dependency:** S7 (or run command directly). Requires `studies/eda/findings/eda_03_joint_registry.csv` — exists.

**Blast radius:** New directory + two files. No source code changes. Additive only.

**Risk note:** This commits a runtime artifact to the repo. The artifact is lifecycle-governed — `assert_operational_safe("outputs/registry/gw36/registry.csv")` must pass before committing.

**Rollback:** `rm -rf outputs/registry/gw36/`

**Validation:**
1. Command exits 0.
2. `cat outputs/registry/gw36/build_metadata.json` — shows `gw: 36`, `build_mode: "packaged"`.
3. `python -c "from signals.lifecycle.lifecycle import assert_operational_safe; assert_operational_safe('outputs/registry/gw36/registry.csv'); print('OK')"` — prints `OK`.
4. `make score GW=36` — scorer completes.
5. `make weekly GW=36` — weekly runner completes.

**Expected test impact:** None.
**Estimated time:** 15 minutes.

---

## Phase 7 — Explainability (First User-Facing Value)

### S9 — Rho weights + methodology callout in scorer HTML ⭐ FIRST EXPLAINABILITY SLICE

**Type:** operational + explainability | **Priority:** P1 | **Execute:** Auto

**Objective:** The scorer HTML must show users *why* each signal column exists and *how* the composite score was computed, using data already present in `ScorerOutput` but not currently rendered.

**Why this slice exists and why it is the first explainability slice:**

The renderer already shows confirmed signals as columns and excluded signals as a caveated list. What a reader cannot determine from the current HTML:

1. **Signal weights** — headers show `assists [core]` but not `ρ=0.48`. The rho value determines how much that signal contributes to the composite score; it is in `ConfirmedSignal.rho_pooled` but not rendered.
2. **Signal direction** — the bar visualizes direction but the header gives no textual cue that `goals_conceded` is a *negative* predictor. A reader assumes higher bar = better for all signals.
3. **Scoring formula** — the "Score" column shows a number with no explanation. A reader cannot determine what a score of 7.3 means or how it relates to the signals shown.

This slice requires **no changes to contracts, engine, runner, or tests**. `ConfirmedSignal.rho_pooled` and `ConfirmedSignal.direction` are already in the object passed to `_render_position_table()`. The renderer just does not display them.

**Exact files touched:**
- `intelligence/scoring/renderer.py` — only

**Scope of changes:**

**Change 1 — Signal column headers include rho and direction indicator:**

```python
# Before (in _render_position_table):
th_signals += (
    f'<th class="signal-col">'
    f'{html.escape(sig.signal)}{badge}'
    f'</th>'
)

# After:
direction_arrow = "↑" if sig.direction > 0 else "↓"
rho_display = f"{abs(sig.rho_pooled):.2f}"
th_signals += (
    f'<th class="signal-col">'
    f'{html.escape(sig.signal)}{badge}'
    f'<br><span class="signal-meta">{direction_arrow} ρ={rho_display}</span>'
    f'</th>'
)
```

Add `.signal-meta` to `_CSS`:
```css
.signal-meta {
  font-size: 0.70rem;
  font-weight: 400;
  color: var(--muted);
  letter-spacing: 0;
  text-transform: none;
}
```

**Change 2 — Methodology callout section:**

Add between `.scope-notice` div and `.tabs` div in the `render()` output:

```html
<div class="methodology-note">
  Score = weighted mean of normalised signal values, weight = |ρ| (Spearman rank correlation
  with GW total points). Signals shown are lifecycle-promoted (core_signal or review_signal)
  with |ρ| ≥ 0.15. Higher score = stronger historical signal alignment. Not a prediction.
</div>
```

Add `.methodology-note` to `_CSS`:
```css
.methodology-note {
  margin-top: 0.5rem;
  margin-bottom: 1rem;
  padding: 0.5rem 0.9rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 0.82rem;
  color: var(--muted);
}
```

The text is factually accurate: it mirrors `intelligence/scoring/signals.py:MIN_RHO = 0.15` and the engine's weighted-mean computation exactly.

**What this slice explicitly does NOT change:**
- `intelligence/scoring/contracts.py` — no new fields
- `intelligence/scoring/engine.py` — no logic changes
- `intelligence/scoring/runner.py` — no changes
- `intelligence/scoring/signals.py` — no changes
- Any test file

**Blast radius:** `intelligence/scoring/renderer.py` only. HTML output format changes. The rendered HTML is not a tested artifact — tests verify engine and signal loading, not HTML string content.

**Rollback:** `git checkout intelligence/scoring/renderer.py`

**Validation:**
1. `pytest tests/test_scorer_engine.py tests/test_scorer_signals.py -v` — pass unchanged.
2. `pytest -x` — baseline 738 passed, 1 skipped preserved.
3. Run scorer, open HTML in browser:
   - Signal headers show `↑ ρ=0.XX` or `↓ ρ=0.XX` below the signal name.
   - Methodology callout is visible between the scope notice and the position tabs.
   - Excluded signals section remains intact.
   - Dark mode toggle works correctly.

**Expected test impact:** Zero. Engine and signal tests are unaffected.
**Estimated time:** 45 minutes.

---

## Phase 8 — Polish

### S10 — Stale doc archival + dead directory removal

**Type:** doc-only | **Priority:** P2 | **Execute:** Auto

**Objective:** Remove or archive documents and directories that actively mislead or add navigation noise.

**Why this slice exists:** `docs/IMPLEMENTATION_BACKLOG.md` references sprint states against retired paths. `docs/repository-alignment-report.md` describes a pre-migration architecture. `tasks/active/` and `tasks/completed/` contain only `.gitkeep`. `docs/decisions/.gitkeep` lingers next to real decision files.

**Exact changes:**
- `docs/IMPLEMENTATION_BACKLOG.md` → `archive/IMPLEMENTATION_BACKLOG.md` (move)
- `docs/repository-alignment-report.md` → `archive/repository-alignment-report.md` (move)
- `tasks/` — remove directory (contains only `.gitkeep` files)
- `docs/decisions/.gitkeep` — remove file (real decision files exist alongside it)
- `signals/runs/` — add `signals/runs/README.md`: one line clarifying it holds operational run logs from the registry builder, distinct from study run artifacts in `studies/runs/`

**Blast radius:** File moves and deletions only. Nothing imports these documents.

**Rollback:** `git checkout` moved files; `mkdir -p tasks/active tasks/completed` + restore gitkeeps.

**Validation:**
1. `git log --oneline -1` on archive/ — files are present.
2. `ls tasks/` — directory absent from root.
3. `pytest -x` — baseline preserved.
4. `grep -r "IMPLEMENTATION_BACKLOG\|repository-alignment-report" . --include="*.md" --include="*.py" | grep -v archive/ | grep -v ".git/"` — zero results.

**Expected test impact:** None.
**Estimated time:** 20 minutes.

---

### S11 — `tests/integration/` → `tests/helpers/` rename

**Type:** test-only | **Priority:** P2 | **Execute:** Approve

**Objective:** The `tests/integration/` directory contains evaluation helper libraries, not integration tests. The name misleads new engineers.

**Why this slice exists:** `tests/integration/baselines.py`, `captain.py`, `features.py`, `metrics.py`, `transfers.py`, `value.py`, `windows.py` are library modules with no `test_` prefix. Pytest does not collect them. The directory name signals "integration tests"; the content is "evaluation helper library."

**Dependency:** S5 must be complete so there is no confusion between the directory name and the `@pytest.mark.integration` marker.

**Exact files touched:**
- `tests/integration/` → `tests/helpers/` (directory rename)
- All `from tests.integration.x import` → `from tests.helpers.x import` in approximately 8 files:
  - `tests/test_evaluation_captain.py`
  - `tests/test_evaluation_core.py`
  - `tests/test_evaluation_features.py`
  - `tests/test_evaluation_transfers.py`
  - `tests/helpers/captain.py` (self-referencing)
  - `tests/helpers/features.py`
  - `tests/helpers/transfers.py`
  - `tests/helpers/value.py`

**Blast radius:** Directory rename + import string changes in ~8 files. No logic changes. Python's import system fails immediately if any reference is missed — so validation is deterministic.

**Rollback:** Rename back + revert import strings — one commit.

**Validation:**
1. `grep -r "tests.integration" tests/ --include="*.py"` — zero results.
2. `pytest tests/test_evaluation_captain.py tests/test_evaluation_core.py tests/test_evaluation_features.py tests/test_evaluation_transfers.py -v` — all pass.
3. `pytest --collect-only -q | tail -1` — still 739.
4. `pytest -x` — baseline preserved.

**Expected test impact:** Zero count change. Import path change only.
**Estimated time:** 30 minutes.

---

## Stop Conditions

**Hard stops — abort slice, revert, investigate:**
1. `pytest` exits with fewer than 738 passed or changes the 1 skipped count.
2. `lint-imports` exits non-zero — layer boundary breached.
3. A slice requires touching more than 5 files outside its declared scope — re-plan before continuing.
4. Pre-flight scan for S3 reveals violations in `intelligence/` or `studies/` — fix violations before making the governance test change.

**Soft stops — pause and consult:**
1. S6 causes any currently-passing integration test to fail — fixture introduced a path regression; revert and investigate.
2. S8 produces a registry with 0 rows — check the lifecycle path and source registry before committing.
3. Any slice changes a file not listed in its "exact files touched" section.

**Never stop for:**
- A test that was already skipped before the stabilization session.
- Lint warnings on files not touched by the current slice.
- Import-linter passing on directories that don't exist (resolved by S3).

---

## High-Risk Anti-Patterns to Avoid

**1. Rewriting CONTEXT.md rather than correcting it**
CONTEXT.md has significant accurate content (sections 1, 2, 4, 8–10). Only change sections 3, 5, 6. Rewriting introduces new inaccuracies and breaks continuity.

**2. Bulk search-and-replace for integration markers**
`pytestmark = pytest.mark.integration` marks ALL tests in a module. If a file has tests that don't need the DB, bulk marking is wrong. Read each file before applying.

**3. Renaming `tests/integration/` before completing S5**
Apply S5 first. Without the marker, renaming the directory makes the naming confusion worse.

**4. Expanding `_STAGING_ALLOWLIST` when violations are found in S3 pre-flight**
Fix the violation. The allowlist is not a mechanism for normalizing violations.

**5. Adding `registry_source` to `ScorerOutput` inside S9**
This expands blast radius from 1 file to 3 files (contracts, runner, renderer). Keep S9 to `renderer.py` only. Registry provenance is a clean follow-up (S9b).

**6. Committing `outputs/` artifacts without verifying `assert_operational_safe` passes**
Run the check explicitly before committing any artifact to `outputs/registry/`.

**7. Moving docs to `archive/` without confirming no operational code references them**
Run `grep -r "IMPLEMENTATION_BACKLOG\|repository-alignment-report" . --include="*.py" --include="*.md" | grep -v archive/` first.

---

## Definition of Portfolio-Grade Operational Readiness

The repository reaches portfolio-grade operational readiness when all of the following hold simultaneously:

**Discoverability:**
- `CONTEXT.md` section 3 directory tree matches `ls` output exactly — zero phantom entries.
- `make help` prints all operational targets with descriptions and expected arguments.
- `README.md` contains a working 3-command sequence that runs without errors on a machine with `FPL_DB_PATH` set.

**Test hygiene:**
- `pytest -m "not integration"` runs clean on any machine in under 60 seconds.
- `pytest -m integration` runs all live-DB tests and only live-DB tests.
- No test file hits `~/.fpl/fpl.db` without `@pytest.mark.integration`.
- Architecture contract tests scan the actual source directories (`intelligence/`, `studies/`, `signals/`).

**Dependency hygiene:**
- `pyproject.toml` declares only dependencies that are imported in source.
- No reference to non-existent packages in the build system.

**Artifact lineage:**
- `outputs/registry/gw{N}/` exists with `registry.csv` + `build_metadata.json`.
- `assert_operational_safe` is the only path between EDA artifacts and operational consumers.

**Documentation accuracy:**
- No document at root or `docs/` level references a directory path, module path, or layer name that does not currently exist.
- Stale sprint and planning history lives in `archive/`, not in `docs/`.

---

## Definition of Explainability-Complete

The repository reaches explainability-complete when a reader of any output artifact can answer every question in the following chain without reading source code:

**Layer 1 — Signal selection:** "Which signals were used for this position, and which were excluded and why?"
→ Achieved by: scorer HTML caveated section (already exists) + confirmed signal headers (S9).

**Layer 2 — Score derivation:** "What does a score of 7.3 mean? How is it calculated?"
→ Achieved by: methodology callout in scorer HTML (S9). **Explainability-complete at this layer after S9.**

**Layer 3 — Registry provenance:** "Which registry produced this scoring? When was it built? What GW cutoff?"
→ Achieved by: adding `registry_source: str` to `ScorerOutput` and threading it to the renderer header. Follow-up slice (S9b) after S9 validates.

**Layer 4 — Signal characterization:** "Why is `assists` a core signal for MIDs? What was its ρ, stability, and population scope?"
→ Achieved by: `signals/registry/SIGNAL_REGISTRY.md` populated with EDA-characterized signals. Manual documentation pass — no code change.

**Layer 5 — Per-player contribution breakdown:** "Why is player X ranked 3rd? Which signals contributed most?"
→ Achieved by: per-player signal contribution table in scorer HTML using `PlayerScore.signal_normalised` × `ConfirmedSignal.rho_pooled`. Follow-up renderer slice after S9.

The system is **explainability-complete at Layer 2** after S9. Layers 3–5 represent progressive deepening, not a blocking threshold for operational readiness.
