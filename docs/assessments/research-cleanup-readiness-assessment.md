# Research Layer — Cleanup and Implementation-Readiness Assessment

**Date:** 2026-06-07
**Scope:** `research/` · `research/kernels/` · `research/families/` · `research/findings/` · `research/registry/`
**Authority:** Architecture Decision Log (ARCHITECTURE_DECISION_LOG.md)
**Status:** READY FOR CLEANUP — one conditional (Phase 8 FDR design doc)

---

## 1. Executive Summary

The research layer is structurally sound and its architecture is closed. All six recurring
architectural questions have been adjudicated. Cleanup and implementation work may begin
immediately.

The principal technical debt is concentrated in one place: the four validate study files
(`form`, `avail`, `market`, `fixture_gw`) share ~250 lines of near-identical implementation
that exists in four independent copies. This is the highest-leverage cleanup target in the
layer. Everything else is secondary.

Three reliability improvements matter before the next season of data: a DB fingerprint in
run provenance, write-time schema validation on `evidence.yaml`, and tests for validate study
classification logic. The kernel layer is well-tested and coherent, with two kernels that are
implemented and tested but not yet wired into any validate study (`multiplicity`, `windows`).

The platform is not at risk of architecture drift. The risks are narrower: a silent classification
bug in `_classify()` would propagate into governance without detection, and a study rerun on
stale data would update `evidence.yaml` without any alert. Both are fixable without structural
change.

**Maturity after cleanup:** The layer will move from L3 (Reusable Research Platform) to the
lower boundary of L4 (Governed Research Platform).

---

## 2. Confirmed Strengths

These are working well and should not be disturbed.

**S1 — Firewall is physically enforced and real.**
`explore/` and `validate/` are distinct directories with a committed `LENS_DESIGN.md` pre-registration.
The explore/validate split is consistently applied across all four families. The test suite has
412-line and 449-line test files for the explore runners — the firewall is tested at the explore
side.

**S2 — Kernel layer is cohesive and deterministic.**
Eleven kernel modules, each with clear scope, all using `np.random.default_rng(seed)`. Five
kernels have dedicated test files with metamorphic tests (`resampling`, `stability`, `redundancy`,
`multiplicity`, `conditioning`). The between/within decomposition (`panel.py`) and tail
concentration (`tail.py`) are tested via `test_relationship_computation.py`.

**S3 — Evidence generation pipeline is machine-traceable.**
`evidence_run.source: LENS-FORM-{ts}` in `evidence.yaml` links the committed evidence to an
ephemeral run directory. `run_metadata.json` captures all study parameters. The
`annotations.yaml` + `evidence.yaml` → `evaluation_metadata.yaml` pipeline is clean and the
architecture is ratified (ADR-010).

**S4 — Position-scoped verdicts throughout.**
Every evidence artifact, annotation, and governance output carries (signal, position) grain.
No position-blind verdict exists anywhere. This is enforced by the key structure and the
per-position loops in every study.

**S5 — Family structure is learnable.**
All four families follow identical physical layout: `explore/`, `validate/`,
`LENS_DESIGN.md`, `annotations.yaml`, `evidence.yaml`. A new contributor who reads one
family can immediately navigate any other.

**S6 — model/assemble correctly imports research kernels.**
`composition_study.py` imports `bootstrap_partial_rho`, `partial_spearman`,
`permutation_rho_baseline`, and `fraction_rank_order_changed` from `research.kernels`. This
cross-layer kernel reuse is explicitly permitted by the architecture and demonstrates the kernel
layer fulfilling its purpose.

---

## 3. Cleanup Findings

### CF-01 — Four private copies of `_bootstrap_spearman_ci`

**Classification:** Technical Debt
**Severity:** High
**Files:** `form/validate/study.py:133`, `avail/validate/study.py:57`, `market/validate/study.py:52`, `fixture_gw/validate/study.py:52`

All four validate studies implement a private bootstrap Spearman CI function. The four copies
are functionally identical in logic but differ in surface:

| Study | N_BOOTSTRAP | SEED | Type annotations |
|---|---|---|---|
| form | 2000 | 42 | Yes |
| avail | 2000 | 42 | Yes (partial) |
| market | 2000 | 42 | **No** |
| fixture_gw | 2000 | 42 | **No** |

`research/kernels/resampling.py` already provides `bootstrap_spearman_ci()` with `N=1000, seed=0`
and a dict return. The study copies use `N=2000, seed=42` and a tuple return — not the same
function called with different parameters, but a semantically identical function with different
defaults. The kernel's defaults are weaker (1000 samples, seed 0); the study defaults should
become the canonical defaults.

The canonical implementation is `resampling.bootstrap_spearman_ci`. The study copies are
the debt. Resolution: align the kernel defaults to N=2000/seed=42 (or add them as parameters
with these as defaults), change the return to include both dict and named access, and delete
the four private copies.

**Note:** The fixture study's `_quintile_record` has a **functional difference** from the
other three — it checks bidirectional monotonicity (`is_monotonic_up or is_monotonic_down`)
because `fdr_avg` has a negative rho. This difference must be preserved as a parameter in any
consolidated implementation, not silently overwritten.

---

### CF-02 — Four private copies of `_quintile_record` with a hidden functional divergence

**Classification:** Technical Debt
**Severity:** Medium-High
**Files:** all four validate/study.py

`_quintile_record` is nearly identical across form, avail, and market. The fixture study
diverges silently at lines 89-91: it checks both upward and downward monotonicity (required
for `fdr_avg`). This divergence is not documented in a comment or parameter — a reader of
`fixture_gw/validate/study.py` would not know why the monotonicity check differs unless they
compare all four files.

The hidden divergence is the more serious problem than the duplication itself: it means the
four studies have quietly different classification semantics that are invisible from any one
file.

---

### CF-03 — Four private copies of `_evidence_row`

**Classification:** Technical Debt
**Severity:** Low-Medium
**Files:** all four validate/study.py

`_evidence_row` is byte-for-byte identical across form, avail, and fixture. The market study
does not define `_evidence_row` explicitly — it inlines the logic. These should be a single
shared function. There are no divergences here.

---

### CF-04 — Market and fixture validate studies have no type annotations

**Classification:** Technical Debt
**Severity:** Medium
**Files:** `market/validate/study.py:52-100`, `fixture_gw/validate/study.py:52-136`

```python
# market/validate/study.py:52
def _bootstrap_spearman_ci(x, y, n_samples, seed):
```

Form and avail validate studies have type annotations. Market and fixture do not — not on
the bootstrap function, `_correlation_record`, or `_quintile_record`. This inconsistency will
grow: future changes to untyped functions cannot be checked by mypy even once `research/` is
added to mypy scope.

---

### CF-05 — `research/kernels/__init__.py` exports only two of eleven kernels

**Classification:** Cleanup Candidate
**Severity:** Low
**File:** `research/kernels/__init__.py`

The package `__init__.py` exports only `decompose_rho` and `haul_concentration` (the two
correlation kernels). The other nine kernels are importable but unlisted. This creates an
asymmetry: a caller using `from research.kernels import bootstrap_spearman_ci` gets an
`ImportError` because it is not in `__init__.py`, even though `research.kernels.resampling`
is available. The `__init__.py` should either export all public-facing kernel functions or
export none and be explicit that kernels are imported by module path.

---

### CF-06 — `research/kernels/conditioning.py` has no production callers

**Classification:** Cleanup Candidate
**Severity:** Low
**File:** `research/kernels/conditioning.py`

`conditioning.py` provides `compute_conditional_rho` and `classify_heterogeneity`. It is
tested (`test_kernels_conditioning.py`) but has zero imports in any production code —
no validate study, no foundation helper, no registry module. The EDA notebook
`eda_03_joint.ipynb` likely used it interactively, but no committed Python module imports it.

It is not dead code — it is a valid kernel for heterogeneity analysis (Class 5 in the
STRATEGY.md taxonomy). The disposition is to document it explicitly as a kernel for future
Class 5 studies, not to delete it.

---

### CF-07 — `research/kernels/windows.py` is not used by validate studies

**Classification:** Documentation Gap
**Severity:** Low
**File:** `research/kernels/windows.py`

`windows.py` provides `assert_no_future_leakage()` and `evaluation_gameweeks()`. It is used
only in the two explore study files (`rolling_xgi_study.py`, `minutes_stability_study.py`)
and one integration test. Validate studies do not use it — they implement bespoke
`_assert_lag_alignment()` functions instead.

Architecture Decision 4 rules that research-layer checks are detective controls (advisory),
not enforcement authorities. `assert_no_future_leakage()` is the correct tool for validate
studies' pre-run provenance check; the bespoke `_assert_lag_alignment()` functions are
inferior substitutes. The validate studies should call `assert_no_future_leakage()` as a
first-class pre-run gate, not as an afterthought.

---

### CF-08 — LENS_DESIGN.md for `form` states GW 3-33; study runs GW 3-38

**Classification:** Documentation Gap
**Severity:** Medium
**File:** `research/families/form/LENS_DESIGN.md` (and potentially others)

The pre-registration document and the running study disagree on the study window. ADR-010
expanded the GW window to 38 (full season, holdout folded in). The study header docstring
acknowledges this; the LENS_DESIGN.md does not. The LENS_DESIGN.md is the locked design
document. It must reflect the study as-run, including any post-design amendments with their
ADR reference. This is a governance policy gap (GPG-04) whose resolution is a documentation
edit, not an architectural change.

Check all four `LENS_DESIGN.md` files for similar staleness.

---

### CF-09 — `RUNS_DIR = Path("research/runs")` in five files

**Classification:** Technical Debt
**Severity:** Low-Medium
**Files:** all four `validate/study.py` + `model/assemble/composition_study.py`

A relative path for run output is CWD-sensitive. Studies must be executed from the project
root or they silently write to incorrect locations. The fix is `Path(__file__).resolve().parent`
traversal to the project root, or a shared project-root config constant.

---

### CF-10 — `findings/records/*.csv` committed without run provenance

**Classification:** Technical Debt
**Severity:** Medium
**Files:** `research/findings/records/*.csv`

Ten committed CSV files (EDA outputs) carry no timestamp, run reference, or DB snapshot
identifier. They will silently age as the database is refreshed. Either they should be
regenerated in CI (making them live artifacts), added to `.gitignore` (making them ephemeral),
or given an accompanying `_provenance.json` sidecar file that records which run and DB
snapshot produced them.

The simplest resolution: add a `_provenance.json` to the directory on each EDA notebook run,
recording the DB path and row count. This costs one line of notebook code and provides a
minimum provenance anchor.

---

## 4. Testing Findings

### Current Coverage Inventory

| Area | Test file | Coverage |
|---|---|---|
| `kernels/resampling` | `test_kernels_resampling.py` | Strong — 8 tests including metamorphic |
| `kernels/stability` | `test_kernels_stability.py` | Adequate — 4 tests |
| `kernels/redundancy` | `test_kernels_redundancy.py` | Adequate — 5 tests |
| `kernels/multiplicity` | `test_kernels_multiplicity.py` | Strong — 7 tests |
| `kernels/conditioning` | `test_kernels_conditioning.py` | Adequate — 5 tests |
| `kernels/geometry` | `test_relationship_geometry.py` | Adequate — 6 tests |
| `kernels/association` + `panel` + `tail` | `test_relationship_computation.py` | Present |
| `kernels/metrics` | None | **Zero** |
| `kernels/distribution` | None | **Zero** |
| `kernels/windows` | Partial — `test_rolling_xgi_real_validation.py` | Thin |
| `form/explore/*` | `test_rolling_xgi_study.py`, `test_minutes_stability_study.py` | Strong — 412+449 lines |
| `form/validate/study.py _classify()` | None | **Zero** |
| `avail/validate/study.py _classify()` | None | **Zero** |
| `market/validate/study.py _classify()` | None | **Zero** |
| `fixture_gw/validate/study.py _classify()` | None | **Zero** |
| `evidence_record.write_evidence()` | None | **Zero** |
| `registry/*` | `test_registry_*.py` (multiple) | Present |

### TF-01 — Validate study `_classify()` is completely untested

**Priority:** HIGH — must be resolved before any modification to classify logic
**Effort:** Medium (1-2 days per study; shared fixtures reduce effort if studies are consolidated first)

`_classify()` in each validate study is the gate function that produces `lens_status`, which
flows directly into `evidence.yaml` and from there into `evaluation_metadata.yaml` and the
governed scorer. A bug in the gate sequence (e.g., gate 2 checked before gate 1, threshold
comparison inverted) would produce wrong verdicts that propagate silently into governance.

Minimum required tests per study:
1. Sufficient observations + CI crosses zero → `uninformative` (gate 1 fail)
2. CI excludes zero + fails decision relevance → `uninformative` (gate 2 fail)
3. CI excludes zero + decision relevant + ≥2/3 blocks → `informative`
4. CI excludes zero + decision relevant + <2/3 blocks → `unstable`
5. `full_corr is None` (insufficient n) → `uninformative`
6. `full_quint is None` (insufficient n for quintile) with CI passing → correct gate 2 path

The fixture study requires two additional tests: negative-rho monotonic signal produces
`decision_relevant=True` (bidirectional monotonicity), and bidirectional non-monotonic
produces `False`.

---

### TF-02 — `evidence_record.write_evidence()` is untested

**Priority:** HIGH
**Effort:** Low (half a day)

`write_evidence()` is the function that produces the committed governance input.
It maps position labels (`GKP` → `GK`), structures the YAML payload, and writes the file.
Zero tests exist for it. A position label mapping bug would produce an `evidence.yaml` with
the wrong position keys that the governance generator would silently misread.

Minimum required tests:
1. GKP → GK label mapping applied correctly
2. Unknown position passes through unchanged
3. YAML structure matches expected schema
4. `evidence_run` metadata appears in output
5. Multi-signal, multi-position input produces correct nested structure

---

### TF-03 — `kernels/windows` pre-run assertion is undertested

**Priority:** Medium
**Effort:** Low (half a day)

`assert_no_future_leakage()` is tested indirectly in `test_rolling_xgi_real_validation.py`
but has no dedicated unit tests for its two failure modes: missing rolling columns, and empty
GW rows. These are exactly the failure modes that matter — they catch non-DAL-provenance data.

---

### TF-04 — `kernels/metrics` has no tests

**Priority:** Medium
**Effort:** Low (half a day)

`metrics.py` provides `rank_correlation`, `downside_rate`, `mean_return`, `top1_return`,
`hit_rate`, `regret`, `return_variance`. These are used in both explore studies. `rank_correlation`
in particular is a thin wrapper around `scipy.stats.spearmanr` with None-safety; its None-return
path is untested.

Minimum required tests:
1. `rank_correlation` returns None for constant arrays
2. `rank_correlation` returns None when either array is None
3. `downside_rate` returns 0.0 for an all-positive array
4. `regret` returns the correct opportunity cost

---

### TF-05 — `kernels/distribution` has no tests

**Priority:** Low
**Effort:** Low (half a day)

`distribution.py` provides `compute_distribution_stats`, `analyze_by_group`,
`analyze_tail_frequency`. Used only in `_target_distribution_helpers.py`. Not used in any
validate study. Tests would improve confidence if this kernel is later promoted to validate
study use.

---

### TF-06 — No snapshot test freezes `evidence.yaml`

**Priority:** Medium
**Effort:** Low (a few hours)

STRATEGY.md §5 mandates a "verdict golden-freeze" snapshot test. None exists. A snapshot
test that fails when `evidence.yaml` changes would implement the governance policy gap (GPG-02)
identified in the Architecture Decision Log: it would enforce that evidence.yaml changes
trigger a governance generator re-run before commit.

Implementation: a pytest fixture that reads the committed `evidence.yaml` for each lens,
runs `study.run()` against the test DB, and asserts the resulting evidence matches the
committed snapshot (or that the developer has explicitly acknowledged the change).

---

### TF-07 — No test for `_assert_lag_alignment` wider than player_id=1

**Priority:** Medium
**Effort:** Low (a few hours)

The player_id=1 coverage limit is documented (RED-03 in the ADR Classification Pass). A
supplementary test with a synthetic multi-player dataset, where player 2 has a deliberate
lag mismatch, would validate that the check catches population-level misalignment — not just
player-1-specific alignment.

---

## 5. Research Engineering Findings

### REF-01 — No DB fingerprint in `run_metadata.json`

**Classification:** Reliability Improvement
**Severity:** Medium

`run_metadata.json` records `db_path` but not the data state at that path. Two runs on
the same path with different data are indistinguishable from their metadata.

**Minimum fix:** Add `db_row_count` (a `SELECT COUNT(*) FROM mart` or the mart DataFrame's
`len()`) to `run_metadata.json` at study start. This costs one line and provides a
discriminating fingerprint. A full SHA256 of the DB file is stronger but expensive for large
databases.

---

### REF-02 — `multiplicity.py` is implemented, tested, and unused in validate studies

**Classification:** Reliability Improvement
**Severity:** High (analytically)

Every validate study tests 6-24 hypotheses (signal × position combinations) without
multiplicity adjustment. `multiplicity.py` provides production-ready BH and Holm-Bonferroni
implementations. The tools are built; they are not wired in.

This is not an architecture change — multiplicity adjustment is a study-level decision within
the research layer's authority. What is needed is a `multiplicity_summary` section in each
study's `classification_summary.csv`, and an explicit note in `evidence.yaml` that verdicts
are unadjusted. This makes the limitation visible rather than invisible.

**Immediate actionable item:** Add a multiplicity adjustment pass to each validate study's
`run()` function. The adjusted reject column should appear in `classification_summary.csv`
as `bh_reject` and `holm_reject` alongside the existing `lens_status`. The unadjusted
`lens_status` remains the operative gate (for continuity with committed evidence artifacts),
but the adjusted columns provide an auditable record of where unadjusted verdicts would be
overturned.

---

### REF-03 — `_assert_lag_alignment` checks player_id=1 only

**Classification:** Reliability Improvement
**Severity:** Medium

A broader check — e.g., a sample of 5-10 players across positions — would provide
meaningful coverage at minimal cost. The assertion should also verify the lag
direction (GW N's `total_points_next_gw` equals GW N+1's `total_points`) for players
with sparse attendance, not only for the player who happened to get ID 1.

---

### REF-04 — EDA notebooks are not cleared; CSVs in `findings/records/` lack provenance

**Classification:** Technical Debt
**Severity:** Medium

The committed EDA CSVs in `research/findings/records/` have no embedded run reference.
The notebooks that produced them are not cleared (execution outputs embedded).

**Minimum actionable fix:** Add a one-cell notebook epilogue to each EDA notebook that
writes a `_provenance.json` sidecar to `research/findings/records/`. The sidecar should
record the notebook name, execution timestamp, and DB path (and row count, per REF-01).
This requires no CI changes and gives future maintainers a minimum anchor for "what data
produced these findings."

**Notebook clearing** is a separate and larger decision. If EDA notebooks are to be treated
as committed code artifacts (clearable, re-executable), they need a CI gate to run them.
If they are treated as historical narratives (output-embedded), they should be documented as
such. The current state is ambiguous — neither declared nor enforced.

---

### REF-05 — Validate study run artifacts accumulate with no rotation policy

**Classification:** Documentation Gap
**Severity:** Low

`research/runs/` contains timestamped directories from every study run. There is no
declared retention policy. Over multiple seasons and repeated reruns, this directory will
grow unboundedly. A `.gitignore` entry or a cleanup script (retain last N runs per lens)
would prevent accumulation.

---

## 6. Technical Debt Register

Full register of all cleanup findings in priority order.

| ID | Finding | Classification | Severity | Effort | Dependency |
|---|---|---|---|---|---|
| CF-01 | Four copies of `_bootstrap_spearman_ci` | Technical Debt | High | Medium | None |
| TF-01 | `_classify()` untested in all four validate studies | Technical Debt | High | Medium | None |
| TF-02 | `evidence_record.write_evidence()` untested | Technical Debt | High | Low | None |
| REF-02 | `multiplicity.py` unused; verdicts unadjusted | Reliability Improvement | High | Medium | None |
| CF-02 | Hidden functional divergence in `_quintile_record` | Technical Debt | Medium-High | Low | CF-01 |
| CF-04 | Market/fixture validate studies untyped | Technical Debt | Medium | Low | None |
| CF-08 | LENS_DESIGN.md stale (GW 3-33 vs 3-38) | Documentation Gap | Medium | Low | None |
| CF-10 | `findings/records/*.csv` committed without provenance | Technical Debt | Medium | Low | None |
| REF-01 | No DB fingerprint in `run_metadata.json` | Reliability Improvement | Medium | Low | None |
| REF-03 | `_assert_lag_alignment` covers player_id=1 only | Reliability Improvement | Medium | Low | None |
| TF-06 | No snapshot test for `evidence.yaml` | Reliability Improvement | Medium | Low | TF-02 |
| TF-03 | `windows.assert_no_future_leakage()` undertested | Technical Debt | Medium | Low | None |
| CF-07 | Validate studies don't call `windows.assert_no_future_leakage()` | Technical Debt | Medium | Low | TF-03 |
| CF-09 | CWD-sensitive `RUNS_DIR` in five files | Technical Debt | Low-Medium | Low | None |
| CF-03 | Four copies of `_evidence_row` | Technical Debt | Low-Medium | Low | CF-01 |
| CF-05 | `kernels/__init__.py` exports only 2 of 11 kernels | Cleanup Candidate | Low | Low | None |
| CF-06 | `kernels/conditioning.py` has no production callers | Cleanup Candidate | Low | None | None |
| TF-04 | `kernels/metrics` untested | Technical Debt | Low | Low | None |
| TF-05 | `kernels/distribution` untested | Technical Debt | Low | Low | None |
| TF-07 | `_assert_lag_alignment` test covers only player_id=1 | Reliability Improvement | Low | Low | None |
| REF-04 | EDA notebooks not cleared; CSVs lack provenance | Technical Debt | Medium | Medium | None |
| REF-05 | No run artifact rotation policy | Documentation Gap | Low | Low | None |
| CF-11 | STRATEGY.md §5 known-gap list is stale | Documentation Gap | Low | Low | Phase B |

---

## 7. Prioritized Roadmap

### Phase A — Immediate Cleanup (Safe, low risk, no abstractions changed)

These items require no new abstractions and cannot break any existing behavior.

**A1 — Type-annotate market and fixture validate study functions**
Add type annotations to the four untyped private functions in `market/validate/study.py` and
`fixture_gw/validate/study.py`. No logic changes.
- Benefit: Enables mypy coverage once `research/` is added to scope; catches future parameter drift.
- Risk: None — annotations are non-executable.
- Effort: Low (2-3 hours)
- Dependency: None

**A2 — Fix `RUNS_DIR` relative path in all five files**
Replace `RUNS_DIR = Path("research/runs")` with a root-relative path via `Path(__file__).resolve().parents[N]`.
- Benefit: Study runs from any working directory produce correct output.
- Risk: Low — one-line change per file.
- Effort: Low (1 hour)
- Dependency: None

**A3 — Update all LENS_DESIGN.md files to reflect ADR-010 GW window**
Audit all four `LENS_DESIGN.md` files against their running `study.py`. Add an ADR-010
amendment section where the window was expanded. Do not rewrite the original locked design —
append an amendment.
- Benefit: Pre-registration documents match the running studies; firewall audit integrity restored.
- Risk: None — documentation only.
- Effort: Low (1-2 hours)
- Dependency: None

**A4 — Add DB row count to `run_metadata.json`**
In each `run()` function, add `"db_row_count": len(state)` (or equivalent) to the metadata
dict before writing `run_metadata.json`.
- Benefit: Run provenance can distinguish same-path / different-data runs.
- Risk: None.
- Effort: Low (30 minutes)
- Dependency: None

**A5 — Document `findings/records/` provenance gap**
Add a `_provenance.json` sidecar template and instructions for EDA notebook authors to
emit it on each run. Do not add CI enforcement yet — just establish the pattern.
- Benefit: Anchors the committed CSVs to a specific DB state.
- Risk: None.
- Effort: Low (1 hour)
- Dependency: None

**A6 — Clarify `kernels/__init__.py`**
Either extend the exports to include all public kernel functions, or add a module docstring
that explicitly states kernels are imported by module path (not via the package `__init__`).
Choose one policy and apply it consistently.
- Benefit: Removes import confusion; prevents `from research.kernels import bootstrap_spearman_ci`
  silently failing.
- Risk: If extending exports, verify no circular imports.
- Effort: Low (1 hour)
- Dependency: None

---

### Phase B — Reliability Improvements (Testing, typing, provenance)

These require new test code but no changes to production logic.

**B1 — Test `_classify()` in all four validate studies**
Write dedicated unit tests for the gate sequence in each validate study's `_classify()`
function. Use synthetic `full_corr`, `full_quint`, and `block_corrs` dicts — no DB needed.

Priority order:
1. `form/validate/study.py` (most complex — has `naive_rho` param, most gate paths)
2. `avail/validate/study.py` (binary target, different gap threshold)
3. `fixture_gw/validate/study.py` (bidirectional monotonicity — highest divergence risk)
4. `market/validate/study.py` (same as form without naive_rho)

- Benefit: Classification bugs caught before they reach governance artifacts.
- Risk: None — tests are additive.
- Effort: Medium (3-4 days total; 1 day per study including fixture edge cases)
- Dependency: None; can begin immediately

**B2 — Test `evidence_record.write_evidence()`**
Write unit tests covering position label mapping, YAML structure, and multi-signal output.
- Benefit: Governance input correctness verified.
- Risk: None.
- Effort: Low (half a day)
- Dependency: None

**B3 — Snapshot test for `evidence.yaml`**
Add a pytest fixture that loads the committed `evidence.yaml` for each lens and asserts it
matches the output of `write_evidence()` called with the test DB. Fail when the two diverge
and the developer has not explicitly committed the new evidence.

This implements the "verdict golden-freeze" mandate from STRATEGY.md §5 and closes GPG-02
from the Architecture Decision Log.
- Benefit: Prevents silent evidence overwrite without governance re-run.
- Risk: Low — test-only addition. The test itself must use the test DB, not the production DB.
- Effort: Low-Medium (1 day including fixture setup)
- Dependency: B2

**B4 — Test `windows.assert_no_future_leakage()` failure modes**
Write unit tests for: (1) empty GW rows → `ValueError`, (2) missing rolling columns → `ValueError`,
(3) all required columns present → passes. These are the only three behaviors the function has.
- Benefit: The provenance gate has verified behavior.
- Risk: None.
- Effort: Low (2 hours)
- Dependency: None

**B5 — Widen `_assert_lag_alignment` coverage beyond player_id=1**
Refactor the check to sample 5-10 player IDs and verify lag-1 alignment for each. Maintain
the "WARN not FAIL" behavior for check 3 (roll3 at GW4 = mean of GW 1-3), but make checks
1 and 2 population-level rather than player-specific.
- Benefit: A systematic lag error across the population would now be caught.
- Risk: Low — the check writes to a file and raises on failure; widening the sample doesn't
  change the contract.
- Effort: Low (2 hours)
- Dependency: None

**B6 — Add type annotations to `research/` and include in mypy**
Add `research` to `pyproject.toml`'s `[tool.mypy] files` list. Fix any mypy errors that
surface (expected to be concentrated in the validate study files, primarily the untyped
market/fixture functions addressed in A1).
- Benefit: Future changes to `_classify()` and study logic are statically checked.
- Risk: Low — mypy is additive to the build; it does not change runtime behavior.
- Effort: Medium (1-2 days to fix all typing errors that surface)
- Dependency: A1

**B7 — Add multiplicity adjustment output to validate studies**
In each study's `run()` function, after the classify loop, compute BH and Holm-Bonferroni
adjustments over the full family of p-values (using 1 - rho_ci_lower/upper as a proxy, or
the observed rho as an effect size). Emit `bh_reject` and `holm_reject` columns in
`classification_summary.csv`. Add an `adjusted_verdicts_note: "unadjusted"` field to
`run_metadata.json` until the adjusted verdicts are formally adopted.
- Benefit: Multiplicity adjustment is computed and visible; the analytical gap becomes auditable.
  Verdicts are not changed (continuity preserved) but the gap is no longer invisible.
- Risk: Low — these are additional output columns; existing columns are untouched.
- Effort: Medium (1 day across all four studies)
- Dependency: None

**B8 — Test `kernels/metrics` and `kernels/distribution`**
Add dedicated test files for the two currently untested kernels.
- Benefit: Complete kernel test coverage.
- Risk: None.
- Effort: Low (1 day total)
- Dependency: None

---

### Phase C — Framework Consolidation (Shared abstractions, study deduplication)

These items reduce the four-copy duplication and create a shared study framework. They carry
the highest refactor risk in the layer.

**C1 — Consolidate `_bootstrap_spearman_ci` into `kernels/resampling`**

Align `resampling.bootstrap_spearman_ci` defaults to N=2000, seed=42. The return signature
already returns a dict with `excludes_zero` — the study callers currently destructure to a
tuple. The callers must be updated to use the dict return.

Steps:
1. Add `n_samples` and `seed` keyword arguments with defaults matching the studies.
2. Update the four study callers to use the kernel.
3. Delete the four private copies.

The fixture study's `_quintile_record` bidirectional monotonicity is unaffected — it is a
quintile function, not a bootstrap function.

- Benefit: Single implementation; kernel tests cover all study uses; parameter drift eliminated.
- Risk: Medium — each study caller must be updated and verified. The dict vs tuple return
  is a breaking change for the callers; verify there are no other callers.
- Effort: Medium (1 day)
- Dependency: B1 (classification tests) — do not consolidate before the tests exist, so
  a regression is immediately detectable.

**C2 — Consolidate `_evidence_row` into `evidence_record`**

`_evidence_row` is identical across three studies (form, avail, fixture). The market study
inlines the same logic. This function belongs in `research/families/evidence_record.py`
alongside `write_evidence()`.

- Benefit: One definition of the evidence row structure; schema changes propagate automatically.
- Risk: Low — the function has no divergences.
- Effort: Low (2 hours)
- Dependency: B2 (evidence_record tests)

**C3 — Extract shared `_quintile_record` with a `bidirectional` parameter**

Consolidate the three identical `_quintile_record` implementations (form, avail, market)
into a shared function in a new `research/families/study_helpers.py` (or in `evidence_record.py`).
The fixture study's version takes a `bidirectional: bool = False` parameter.

The shared signature:
```
def quintile_record(df, signal, signal_id, position, block, target, gap_threshold,
                    bidirectional=False) -> dict | None
```

- Benefit: Monotonicity logic in one place; bidirectional divergence is explicit and
  documented via parameter, not hidden.
- Risk: Medium — the bidirectional flag must be correctly threaded to the fixture study.
  B1 tests for fixture must exist before this consolidation.
- Effort: Medium (1 day)
- Dependency: B1, C2

**C4 — Evaluate a shared LensRunner base for `run()` orchestration**

The four `run()` functions share the following pattern:
1. Generate timestamp, create output directory
2. Load DAL mart, apply population filter
3. Loop over signals × positions
4. For each: compute full corr, full quint, block corrs, classify
5. Append to result lists
6. Write CSVs and `run_metadata.json`
7. Call `write_evidence()`
8. Print summary table

The differences between studies are concentrated in steps 2 (form derives extra columns,
fixture skips lag shift), 4 (avail passes `target` param; form has naive_rho comparison;
fixture has same-GW target), and 6 (metadata dict contents differ per study).

A shared `LensRunner` could absorb steps 1, 3, 5, 6 (CSV writing), and 7 (evidence write),
with study-specific hooks for steps 2 and 4. This is the "StudyContract" gap identified in
STRATEGY.md §5.

**Assessment:** The consolidation is justified but the benefit is primarily maintenance (adding
a fifth family would be much cheaper). The migration risk is medium — the four `run()` functions
have enough structural variation that a naive extraction would silently change behavior.
Recommend deferring to Phase D unless a fifth family is imminent.

- Benefit: Adding a new family reduces to implementing two hooks rather than copying 200 lines.
- Risk: Medium-High — `run()` differences are in the most sensitive parts of the study.
- Effort: High (2-3 days including migration of all four studies and verification)
- Dependency: B1, C1, C2, C3

---

### Phase D — Optional Future Enhancements

These are non-essential improvements. Defer unless a specific trigger event makes them timely.

**D1 — Clear EDA notebooks and add CI execution gate**

If EDA notebooks are to be treated as reproducible artifacts (not narrative records), clear
their outputs and add a CI step that re-executes them against a test DB. This is a significant
workflow change.

Trigger: only if a committed EDA notebook output is found to be incorrect in a review.
- Effort: High
- Dependency: CI DB fixtures must be representative of EDA queries.

**D2 — Promote `conditioning.py` into a Class 5 study template**

`kernels/conditioning.py` is production-ready but has no production callers. If a future
study requires heterogeneity analysis (STRATEGY.md Class 5), this kernel is the right tool.
Add a usage example in the module docstring and a reference in STRATEGY.md's kernel table.

Trigger: when a Class 5 study is added.
- Effort: Low (documentation only)

**D3 — Implement `LensRunner` base (Phase C4)**

See C4. Deferred unless a fifth signal family is added to the platform.

Trigger: addition of a fifth signal family.
- Effort: High (if undertaken with all four migrations)

**D4 — Run artifact rotation policy**

Add a `.gitignore` for `research/runs/` (already likely present) and a `scripts/clean_runs.sh`
that retains the last 3 runs per lens prefix and deletes older ones.

Trigger: when `research/runs/` directory becomes large enough to affect CI performance.
- Effort: Low

**D5 — Machine-readable findings artifact**

Replace or supplement `research/findings/FINDINGS.md` (narrative) with a structured YAML
that maps `G-EDA{N}-{NN}` gate ID → decision → evidence basis. This would enable automated
audit traceability.

Trigger: when the number of gate IDs grows large enough that manual lookup becomes unreliable,
or when an automated audit tool is being built.
- Effort: High (requires re-encoding existing FINDINGS.md content)

---

## 8. Recommended Next Actions

### Actions before any further feature development

These are the minimum reliability requirements before implementing new signal families or
modifying validate study logic.

| Priority | Action | Effort | Why now |
|---|---|---|---|
| 1 | **B1** — Test `_classify()` in all four studies | Medium | Any change to classify logic without tests is a governance risk |
| 2 | **B2** — Test `write_evidence()` | Low | The committed governance input has no verification |
| 3 | **A3** — Update LENS_DESIGN.md files to reflect ADR-010 | Low | Pre-registration documents must match running studies |
| 4 | **A4** — Add DB row count to run_metadata.json | Low | Minimum provenance for study reruns |

### Actions that unblock Phase C consolidation

| Priority | Action | Effort | Why now |
|---|---|---|---|
| 5 | **A1** — Type-annotate market/fixture functions | Low | Required for mypy; required for safe consolidation |
| 6 | **B6** — Add `research/` to mypy scope | Medium | Enables static checking before consolidation |
| 7 | **C1** — Consolidate `_bootstrap_spearman_ci` | Medium | Highest-leverage duplication; requires B1 first |
| 8 | **C2** — Consolidate `_evidence_row` | Low | Low risk; requires B2 first |

### Actions that address analytical gaps

| Priority | Action | Effort | Why now |
|---|---|---|---|
| 9 | **B7** — Add multiplicity adjustment output | Medium | Makes the documented gap auditable |
| 10 | **B3** — Snapshot test for `evidence.yaml` | Medium | Closes GPG-02 from Architecture Decision Log |

### Actions that can be deferred

- A2 (CWD-sensitive paths) — low risk, do when convenient
- A5 (findings/records provenance) — do with next EDA run
- A6 (kernels `__init__.py`) — do at start of Phase B
- B4, B5, B8 — include in any testing sprint
- C3, C4, D1-D5 — defer to Phase C/D schedule

---

*This assessment is scoped to the research layer only. The governance layer (`model/governance`)
and composition layer (`model/assemble`) are not assessed here. The Architecture Decision Log
governs all cross-layer authority questions.*
