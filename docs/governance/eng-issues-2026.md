# Engineering Issues — 2026/27 Pre-Season

**Issued:** 2026-05-31  
**Status:** OPEN  
**Owner:** Lead Platform Analytics Engineer  
**Archive when:** All Phase 1 and Phase 2 items closed; Phase 3 accepted or scheduled

Issues are ordered within each phase by blast radius — the highest-consequence item first.

---

## Phase 1 — High Risk (address before any live use)

---

### ENG-01 — No CI/CD pipeline

**Problem**  
There is no automated test runner. The 928-test suite only executes if someone runs it locally. No `.github/workflows/` exists.

**Why it is a problem**  
Any contributor can push a breaking change and not know. The test suite is the primary defence against regressions in a codebase with complex inter-layer contracts (DAL → signals → intelligence). A suite that only runs locally is a suite that frequently doesn't run. This risk compounds with every new collaborator.

**Acceptance criteria**
- GitHub Actions workflow runs `pytest` on every push and pull request to `main`
- Workflow fails the build on any test failure or import error
- Badge in README reflects current test status

**Files**  
`.github/workflows/` (does not exist — must be created)  
`Makefile` — existing `make test` target defines the test command

---

### ENG-02 — FWD × purchase_price reversal is live in the scorer

**Problem**  
Phase 9 holdout validation (GW 34–38) found `purchase_price` at FWD reverses: rho = −0.095 vs SYNTH-01 in-sample 0.155 (Δ = −0.250, p = 0.374 non-significant). The operational baseline classifies this P1 and recommends restricting to GW 1–30 or adding a phase-conditional caveat. Neither has been implemented. `purchase_price` remains active in `intelligence/transfers.py:39` and `intelligence/value.py` unconditionally across all gameweeks.

**Why it is a problem**  
End-of-season market signals decay as squads rotate and managers rest players. A reversed signal produces actively wrong recommendations — it ranks FWDs in the opposite order of expected returns in the final third of the season. Any live use of the transfers or value scorer after GW 30 would be harmed, not helped.

**Acceptance criteria**
- `purchase_price` at FWD is either gated by a `gw <= 30` condition or removed from FWD scoring entirely pending SYNTH-02 phase-conditional evaluation
- A threshold-registry entry is created for the phase cutoff (GW 30) with classification `EVALUATION-DEFERRED` and evidence required from SYNTH-02
- `outputs/operational-baseline.md` §P1 recommendation marked resolved with a reference to the fix

**Files**  
`intelligence/transfers.py:39`  
`intelligence/value.py:39,78,97,109,117`  
`outputs/operational-baseline.md:90,134` — P1 recommendation  
`signals/governance/weight_registry.yaml:85–90` — FWD composite signal using purchase_price  
`docs/governance/threshold-registry.md` — new entry needed

---

### ENG-03 — CONTEXT.md has stale module paths

**Problem**  
`CONTEXT.md` references `signals/evaluation/EVAL_DESIGN.md`, `signals/registry/SIGNAL_REGISTRY.md`, and `signals/evaluation/evaluation_metadata.yaml` on lines 97, 98, 116, and 122. These paths were deleted in Change 7 (signals package restructure). The current paths are `signals/governance/EVAL_DESIGN.md`, `signals/characterisation/SIGNAL_REGISTRY.md`, and `signals/governance/evaluation_metadata.yaml`.

**Why it is a problem**  
CONTEXT.md is the first document a new contributor reads to orient themselves. Broken paths on the first read destroy trust and send contributors chasing deleted files. It also means the import examples and module references in CONTEXT.md will produce `ModuleNotFoundError` if copy-pasted.

**Acceptance criteria**
- All four stale path references in CONTEXT.md corrected to current paths
- `grep -r "signals/registry\|signals/evaluation\|signals/lifecycle" CONTEXT.md` returns zero results

**Files**  
`CONTEXT.md:97,98,116,122`

---

## Phase 2 — Medium Risk (address before 2026/27 season start)

---

### ENG-04 — Six unvalidated operational thresholds

**Problem**  
Six thresholds in `intelligence/` are annotated `threshold not evaluation-derived` and classified `EVALUATION-DEFERRED` in `threshold-registry.md`. They are active in the production scorer:

| ID | File | Value | What it gates |
|----|------|-------|--------------|
| AVAIL-T-01 | `intelligence/availability.py:29` | 30.0 min | HIGH risk flag |
| AVAIL-T-02 | `intelligence/availability.py:30` | 60.0 min | MEDIUM risk flag |
| AVAIL-T-03 | `intelligence/availability.py:33` | 20.0 min | Divergence flag |
| CAPT-T-01 | `intelligence/captain.py:30` | 45.0 min | Captain eligibility |
| VAL-T-01 | `intelligence/value.py:32` | 30.0 min | Value eligibility |
| TRANS-T-01 | `intelligence/transfers.py:31` | 30.0 min | Transfer eligibility |
| FIX-T-01 | `intelligence/fixtures.py:31` | 30.0 min | Fixture eligibility |

**Why it is a problem**  
These thresholds determine which players appear in captain, transfer, and value recommendations. They are round numbers chosen editorially. A player averaging 28 minutes per game is excluded from transfer recommendations by TRANS-T-01. Whether 30 is the right cutoff has never been tested. Miscalibrated eligibility thresholds produce blind spots in the ranked output — systematically excluding or including players without evidence.

**Acceptance criteria**
- POPTHRESH-01 (`studies/experiments/population_threshold_study.py`) executed and documented; AVAIL-T-02 and REG-T-01 updated to `EVALUATION-DERIVED` or `GOVERNANCE-CONVENTIONAL`
- Remaining thresholds (AVAIL-T-01/03, CAPT-T-01, VAL-T-01, TRANS-T-01, FIX-T-01) each have a study design committed before 2026/27 season start, even if execution is deferred mid-season
- No threshold classified `EVALUATION-DEFERRED` remains in `intelligence/` without a linked study design

**Files**  
`docs/studies/popthresh-01-design.md` — POPTHRESH-01 design (written; study not yet executed)  
`docs/governance/threshold-registry.md` — all seven entries  
`intelligence/availability.py:29–33`  
`intelligence/captain.py:30`  
`intelligence/value.py:32`  
`intelligence/transfers.py:31`  
`intelligence/fixtures.py:31`

---

### ENG-05 — No FPL API schema guard

**Problem**  
The source data comes from the FPL bootstrap-static API, stored in `~/.fpl/fpl.db`. The DAL's staging layer validates columns against internal contracts (`dal/validation/`) but has no check that the upstream schema — FPL's column names, dtypes, and table structure — matches what the pipeline expects. If FPL renames a column or changes a type between seasons (which has happened), the pipeline fails at runtime with a `DALContractViolation` or silent null-fill, not a clear schema mismatch error.

**Why it is a problem**  
Pre-season data updates are the highest-pressure moment in the FPL engineering calendar. Discovering a schema change at 11pm by reading a cryptic contract violation, rather than a clear "column X was renamed to Y" message, costs hours and introduces risk of deploying incorrect data. There is currently no way to detect this before running the full pipeline.

**Acceptance criteria**
- A pre-flight schema check in `dal/pipeline.run()` that validates expected columns and dtypes against the source DB before any feat/mart computation begins
- On mismatch, the error message names the specific column and shows expected vs actual
- Check is covered by at least one test using a synthetic DB with a deliberate schema mismatch

**Files**  
`dal/pipeline.py` — `run()` entry point  
`dal/staging/` — where source schema expectations live

---

### ENG-06 — GK position is entirely unevaluated

**Problem**  
No lens study has been run for GK. There are no governed signals, no SYNTH-01 weights, and no evaluation metadata entries for the GK position. All GK scoring uses `PROVISIONAL-EDITORIAL` weights in `weight_registry.yaml`. The GK register in the source data contains ~65 players per season.

**Why it is a problem**  
GK is the cheapest position and a key differential — most managers pay the minimum for a GK, so the quality of GK recommendations affects value decisions for outfield players. More importantly, the system presents GK scores as if they were meaningful, but they are editorial guesses with no evidential basis. A user acting on a GK recommendation has no way to know it is unevaluated.

**Acceptance criteria**
- `LENS-GK` study design locked at `studies/lenses/gk/LENS_DESIGN.md`
- Lens executed and results in `signals/characterisation/SIGNAL_REGISTRY.md`
- GK entries in `signals/governance/evaluation_metadata.yaml` with lifecycle status
- Any GK signals that fail evaluation gates marked `excluded` in weight_registry.yaml; PROVISIONAL-EDITORIAL weights removed

**Files**  
`signals/governance/weight_registry.yaml` — all GK entries marked PROVISIONAL-EDITORIAL  
`signals/governance/evaluation_metadata.yaml` — no GK entries  
`signals/characterisation/SIGNAL_REGISTRY.md` — no GK evaluation rows

---

### ENG-07 — Single-season generalization risk (known, not fixable before 26/27)

**Problem**  
SYNTH-01 was trained and validated on a single season (25/26, GW 1–38). There is no cross-season validation. The Phase 9 holdout (GW 34–38) provides limited out-of-sample evidence but does not address inter-season distribution shift: squad changes, rule changes, new promoted clubs, or changes in FPL player pricing can all shift signal-target associations between seasons.

**Why it is a problem**  
The system cannot claim its signal quality or composition weights will hold in 26/27. SYNTH-01 findings are plausibly robust — 5/7 groups were stable or improved on holdout — but "plausibly robust" is not the same as validated. The first live season (26/27) is simultaneously the deployment and the test.

**Acceptance criteria (risk mitigation, not resolution)**
- Decision logging protocol implemented from GW 1 of 26/27: every captain and transfer recommendation that the system would have made is logged with the system's confidence score
- A mid-season (GW 20) and end-of-season retrospective is scheduled and documented in the research lifecycle
- `outputs/operational-baseline.md` notes this risk explicitly in the limitations section (currently implied, not stated)

**Files**  
`outputs/operational-baseline.md` — Phase 9 results and limitations  
`signals/governance/EVAL_DESIGN.md:57–64` — what 2025/26 cannot tell us  
`docs/decisions/002-additive-weighted-scoring.md` — seasonal re-validation requirement

---

### ENG-08 — Study code cannot run in CI or on a fresh machine

**Problem**  
Study files in `studies/` use hardcoded relative paths for output directories (`Path("studies/runs")`, `Path("outputs/")`). There is no CLI parameterisation, no environment variable override, and no isolation between concurrent study runs. The studies cannot be executed deterministically outside the developer's local directory.

**Why it is a problem**  
Studies are the primary analytical outputs of the system. If a study cannot be re-run by CI or a second contributor on their machine, reproducibility is a claim rather than a property. Output files from different studies can collide. Adding a second contributor immediately creates a reproducibility problem.

**Acceptance criteria**
- All study entry points accept `--output-dir` or equivalent CLI argument (or read from `FPL_OUTPUT_DIR` env var)
- All study files use absolute paths derived from the argument, not hardcoded relative paths
- At least one study (POPTHRESH-01 when written) is executable with `pytest --integration` in CI without local directory assumptions

**Files**  
`studies/eda/eda_08_study.py:31` — `MINUTES_THRESHOLD = 60`, hardcoded output  
`studies/synthesis/synth01_study.py:31`  
`studies/lenses/*/study.py` — each uses relative output paths  
`studies/operational/phase9_backtest.py`

---

### ENG-09 — Pandera FutureWarning is a pre-breakage signal

**Problem**  
`dal/feat/feat_schema.py:17` imports `import pandera as pa`. Pandera's deprecation warning states: "Importing pandas-specific classes from the top-level pandera module will be removed in a future version." The correct import is `import pandera.pandas as pa`. The warning appears on every test run (4 instances currently).

**Why it is a problem**  
FutureWarnings in test output are pre-announcements of breaking changes. When pandera drops the deprecated import path, `feat_schema.py` — which governs the Pandera schema for all feat layer outputs — will fail at import time, breaking the entire pipeline. Fixing it after the fact under time pressure is avoidable.

**Acceptance criteria**
- `import pandera as pa` replaced with `import pandera.pandas as pa` in all affected files
- Test run produces zero FutureWarning instances related to pandera
- `grep -r "import pandera as pa" --include="*.py"` returns zero results

**Files**  
`dal/feat/feat_schema.py:17`  
Any other files identified by `grep -r "import pandera as pa" --include="*.py"`

---

## Phase 3 — Low Risk (hygiene; address when convenient)

---

### ENG-10 — UNVERIFIED constants in domain/fpl_scoring.py are not yet guarded

**Problem**  
`domain/fpl_scoring.py` marks `RED_CARD_POINTS = -3` and `BPS_MINUTES_CONTRIBUTION_RATE = 0.0` as `UNVERIFIED`. These constants are not currently imported by any production module. The risk is future: a contributor wiring up the scoring domain module may not notice the UNVERIFIED annotation and use these constants in production logic.

**Why it is a problem**  
The annotation system only works if UNVERIFIED constants are structurally prevented from entering production code, not just documented. Currently there is no enforcement — the annotation is a comment, not a guard.

**Acceptance criteria**
- UNVERIFIED constants verified against FPL bootstrap-static for 2025/26 and reclassified, OR
- A CI check added that fails if any UNVERIFIED constant in `domain/fpl_scoring.py` appears in an import in `intelligence/`, `signals/`, or `dal/`

**Files**  
`domain/fpl_scoring.py:57–58`

---

### ENG-11 — No upper bounds on dependencies

**Problem**  
`pyproject.toml` pins `numpy>=1.26.0`, `pandas>=2.3.3`, `pandera>=0.19`, `pydantic>=2.13.1` with no upper bounds. A breaking major-version release installs automatically on a fresh environment.

**Why it is a problem**  
`pandas` already produces a `Pandas4Warning` in the current test suite — evidence that a minor version bump changed dtype behaviour. A `pandas 3.x` or `numpy 2.x` release with breaking changes will produce silent incorrect results or hard failures on fresh installs, typically discovered when onboarding a new contributor or setting up a new machine.

**Acceptance criteria**
- Upper bounds added for major versions of `pandas`, `numpy`, `pandera`, `pydantic`, `scipy`
- `uv.lock` updated to reflect the pinned range
- Comment added explaining when upper bounds should be bumped (annually, after testing)

**Files**  
`pyproject.toml:7–17`

---

### ENG-12 — DAL error messages lose layer context

**Problem**  
`DALContractViolation` exceptions raised inside staging, feat, and mart layers are caught and re-raised without a layer prefix. A failure in staging produces the same error class and a similar message format as a failure in feat.

**Why it is a problem**  
When a pipeline fails in production (or in a CI run), the first question is "which layer failed?" The current error format requires reading the full stack trace to determine this. For a pipeline with three sequential layers, the time-to-diagnosis is unnecessarily high.

**Acceptance criteria**
- `DALContractViolation` raised in staging includes prefix `"staging: "` in the message
- `DALContractViolation` raised in feat includes prefix `"feat: "`
- `DALContractViolation` raised in mart includes prefix `"mart: "`
- Existing tests updated to match new message format

**Files**  
`dal/pipeline.py` — `run()` layer orchestration  
`dal/staging/`, `dal/feat/`, `dal/mart/` — layer-level raise sites

---

## Summary table

| ID | Phase | Title | Primary file |
|----|-------|-------|-------------|
| ENG-01 | 1 — High | No CI/CD pipeline | `.github/workflows/` (missing) |
| ENG-02 | 1 — High | FWD × purchase_price reversal live in scorer | `intelligence/transfers.py:39` |
| ENG-03 | 1 — High | CONTEXT.md stale module paths | `CONTEXT.md:97,98,116,122` |
| ENG-04 | 2 — Medium | Six unvalidated operational thresholds | `intelligence/availability.py:29–33` |
| ENG-05 | 2 — Medium | No FPL API schema guard | `dal/pipeline.py` |
| ENG-06 | 2 — Medium | GK position entirely unevaluated | `signals/governance/weight_registry.yaml` |
| ENG-07 | 2 — Medium | Single-season generalization risk | `outputs/operational-baseline.md` |
| ENG-08 | 2 — Medium | Study code cannot run in CI | `studies/*/study.py` |
| ENG-09 | 2 — Medium | Pandera FutureWarning pre-breakage | `dal/feat/feat_schema.py:17` |
| ENG-10 | 3 — Low | UNVERIFIED constants unguarded | `domain/fpl_scoring.py:57–58` |
| ENG-11 | 3 — Low | No dependency upper bounds | `pyproject.toml:7–17` |
| ENG-12 | 3 — Low | DAL error messages lose layer context | `dal/pipeline.py` |
