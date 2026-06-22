# Phase C Readiness Assessment — Research Layer Consolidation

**Assessor roles:** Senior Software Architect · Analytics Engineer · Refactoring Specialist · Reliability Engineer
**Assessment date:** 2026-06-07
**Platform state at assessment:** 178 tests passing · 0 failures · mypy clean · ruff clean

---

## 1. Executive Summary

Phase A/B hardening produced a well-tested, governance-safe research layer.
Three consolidation opportunities remain (C1–C3).
Two are ready to proceed immediately. One requires a targeted precondition.

| Item | Subject | Decision | Condition |
|------|---------|----------|-----------|
| C1 | `_bootstrap_spearman_ci()` → `research.kernels.resampling` | **GO** | Callers must pass study-level constants explicitly |
| C2 | `_evidence_row()` → `research.families.evidence_record` | **GO** | None |
| C3 | `_quintile_record()` → `research.kernels` | **CONDITIONAL GO** | Add direct unit tests for `_quintile_record` first |

Recommended execution order: **C1 → C2 → C3**.

The primary rationale throughout is that all three consolidations are co-location moves, not methodology changes. No verdict, no governance artifact, and no authority boundary changes as a result.

---

## 2. Current State Assessment

### Four validate studies, five shared functions

All four validate studies (`availability`, `fixture`, `form`, `market`) carry local copies of the same five private functions:

| Function | Lines (per study) | Divergence |
|----------|-------------------|-----------|
| `_bootstrap_spearman_ci` | ~11 | None |
| `_correlation_record` | ~12–15 | Moderate (target column, arg surface) |
| `_quintile_record` | ~22–28 | Substantive (fixture bidirectionality) |
| `_evidence_row` | ~10 | None |
| `_classify` | ~18–24 | Small (form adds `naive_rho` param) |

**Scope note:** `_classify` and `_correlation_record` are out of scope for Phase C. `_classify` diverges meaningfully between form and the other three studies (the `naive_rho` / `clears_naive_baseline` path), and is already unit-tested per-study by `test_validate_study_classify.py`. Consolidating `_classify` would require a runner abstraction, which is explicitly deferred. `_correlation_record` diverges in target column (same-GW vs. lag-1) and is also out of scope.

### The kernel layer exists but is unused by the studies

`research.kernels` contains 13 modules including a production-grade `resampling.py` with `bootstrap_spearman_ci()`. None of the four studies import from it. The duplication is not caused by missing infrastructure — the infrastructure exists and was designed to absorb exactly this function.

---

## 3. C1 Assessment — `_bootstrap_spearman_ci()`

### 3.1 Current State

All four study files carry byte-for-byte identical implementations:

```
availability/validate/study.py   lines 57–67
fixture/validate/study.py        lines 52–62
form/validate/study.py           lines 151–162
market/validate/study.py         lines 52–62
```

The algorithm: compute observed Spearman rho, draw `n_samples` bootstrap resamples with replacement using a seeded RNG, return the `(alpha/2, 1-alpha/2)` percentiles.

A production-grade replacement already exists at `research.kernels.resampling.bootstrap_spearman_ci()`.

### 3.2 API delta between study impl and kernel

| Aspect | Study implementation | Kernel |
|--------|---------------------|--------|
| Return type | `tuple[float, float, float]` (rho, ci_lo, ci_hi) | `dict \| None` with keys `rho`, `ci_lower`, `ci_upper`, `n`, `excludes_zero` |
| Default n_samples | 2000 | 1000 |
| Default seed | 42 | 0 |
| Constant-array guard | None | Returns `None` if either array is constant |
| Minimum-n guard | In `_correlation_record`, not here | `MIN_N = 10` built in |
| Percentile function | `np.percentile` | `np.nanpercentile` |

The kernel is strictly more defensive. Default differences are intentional (kernel is a general-purpose library; studies have their own reproducibility contracts).

### 3.3 Consolidation Benefit

**HIGH**

- Removes ~44 lines of duplicated algorithm code (4 × 11).
- Eliminates the local `scipy.stats.spearmanr` import duplication (kernel owns it).
- Studies gain the kernel's constant-array guard, reducing a silent failure mode where a pathological slice (all-identical signal values) would produce a degenerate bootstrap distribution.
- Single point to fix if a bootstrap correctness issue is found.

### 3.4 Consolidation Risk

**LOW**

- No behavioral divergence between study copies — they are identical. There is no risk of consolidating different implementations.
- The return-type change (tuple → dict) requires mechanical caller adaptation in `_correlation_record`, but the logic is trivial.
- The only genuine risk is accidentally relying on kernel defaults (seed=0, n_samples=1000) instead of the study's reproducibility constants (seed=42, n_samples=2000). This would silently alter CI values and could flip a verdict on the margin.
- The verdict freeze tests in `test_evidence_verdict_freeze.py` would catch any such flip before commit.

### 3.5 Preconditions

**Ready now**, with one required practice: each study's call site must pass `n_samples=N_BOOTSTRAP, seed=BOOTSTRAP_SEED, ci_level=CI_LEVEL` explicitly. The kernel's defaults must not be relied upon.

### 3.6 Recommended Design

- **Target module:** `research.kernels.resampling` (already exists, no new module required)
- **Public API:** `bootstrap_spearman_ci(x, y, n_samples, ci_level, seed) → dict | None`
- **Required parameters at call site:** `n_samples=N_BOOTSTRAP`, `seed=BOOTSTRAP_SEED`, `ci_level=CI_LEVEL` passed explicitly by each study
- **Caller adaptation:** `_correlation_record` in each study replaces the tuple unpack `(rho, ci_lo, ci_hi) = _bootstrap_spearman_ci(...)` with a kernel call and extracts `result["rho"]`, `result["ci_lower"]`, `result["ci_upper"]` from the returned dict. The `n` and `excludes_zero` fields the kernel also returns can replace the corresponding manual re-computations in `_correlation_record`.
- **Hidden divergence:** none — the study copies are identical.

---

## 4. C2 Assessment — `_evidence_row()`

### 4.1 Current State

All four study files carry byte-for-byte identical `_evidence_row()` implementations. Line ranges:

```
availability/validate/study.py   lines 119–132
fixture/validate/study.py        lines 111–124
form/validate/study.py           lines 282–295
market/validate/study.py         lines 107–120
```

The function takes `(signal, position, full_corr, block_corrs, cls)`, counts block passes, and returns the governance input dict. It calls `decision_class_for()` which already lives in `research.families.evidence_record`.

**Ownership observation:** `_evidence_row` constructs a row that `write_evidence()` serializes. Both deal in the same evidence vocabulary. The natural home for `build_evidence_row` is `research.families.evidence_record`, alongside `write_evidence` and `decision_class_for`.

### 4.2 Consolidation Benefit

**MEDIUM**

- Removes ~40 lines of identical code.
- More importantly, establishes a single authoritative definition of what constitutes a valid evidence row. If the evidence schema evolves (e.g., a new field is added), the change happens in one place.
- Creates a testable unit that currently has no isolated test. The function is exercised only through `run()` integration paths; a dedicated unit test would catch regressions directly.

### 4.3 Consolidation Risk

**LOW**

- Zero behavioral divergence across all four copies.
- The function is pure and stateless.
- All four studies already import from `research.families.evidence_record`; the import change is additive.
- `test_evidence_record.py` provides comprehensive structural and field-level coverage of the evidence output. The consolidated function would slot into the same test module without new dependencies.

### 4.4 Preconditions

**Ready now.** No additional safeguards required.

### 4.5 Recommended Design

- **Target module:** `research.families.evidence_record`
- **Public API:** `build_evidence_row(signal, position, full_corr, block_corrs, cls) → dict`
- **Required parameters:** unchanged from current study signature
- **Hidden divergences:** none — all four copies are identical.
- **Test:** add a `TestBuildEvidenceRow` class to `test_evidence_record.py` covering: `full_corr=None` path (all fields None), block_stability_count aggregation, and decision_class passthrough.

---

## 5. C3 Assessment — `_quintile_record()`

### 5.1 Current State

Four implementations exist with three behavioral variants:

**Variant A — unidirectional, parameterized (availability):**
```
availability/validate/study.py   lines 87–116
```
- `target` column passed as parameter
- `gap_threshold` passed as parameter
- `is_monotonic = all(means[i] <= means[i+1])`  (upward only)
- `decision_relevant = bool(gap >= gap_threshold and is_monotonic)`

**Variant B — unidirectional, hard-coded (form, market):**
```
form/validate/study.py           lines 190–224
market/validate/study.py         lines 80–104
```
- `target` hard-coded to `"total_points_next_gw"`
- `gap_threshold` from module constant (1.0)
- `is_monotonic = all(means[i] <= means[i+1])`  (upward only)
- `decision_relevant = bool(gap >= QUINTILE_GAP_THRESHOLD and is_monotonic)`
- Form and market are byte-for-byte identical on this function.

**Variant C — bidirectional, hard-coded (fixture):**
```
fixture/validate/study.py        lines 80–108
```
- `target` hard-coded to `"total_points"` (same-GW, no lag)
- `gap_threshold` from module constant (1.0)
- `is_monotonic_up = all(means[i] <= means[i+1])`
- `is_monotonic_down = all(means[i] >= means[i+1])`
- `is_monotonic = is_monotonic_up or is_monotonic_down`
- `abs_gap = abs(gap)`
- `decision_relevant = bool(abs_gap >= QUINTILE_GAP_THRESHOLD and is_monotonic)`

### 5.2 Divergence analysis

The fixture bidirectional monotonicity is a **deliberate domain decision**, not an accident. `fdr_avg` has a negative signal direction (higher difficulty → lower points), so monotone-decreasing is a valid and expected outcome. Using unidirectional logic on `fdr_avg` would incorrectly classify it as non-monotonic and thus fail the decision relevance gate. This is not a divergence to be papered over — it must become an explicit parameter in any shared implementation.

The `target` column difference (same-GW vs. lag-1) must also be parameterized. This is already the case in Variant A; Variants B and C hard-code it. A consolidated function should accept `target` as a parameter, making the lag relationship explicit at every call site.

### 5.3 Consolidation Benefit

**MEDIUM**

- Reduces ~100 lines to a single implementation.
- Forces the bidirectionality contract to be explicit (`bidirectional: bool`), making it visible and auditable rather than embedded in a copy.
- Reduces the risk of a future maintainer adding a new lens and forgetting to add bidirectionality support.

### 5.4 Consolidation Risk

**MEDIUM**

- The bidirectional flag must default to `False` to preserve existing behavior for availability, form, and market. A default of `True` would be a correctness regression for all three.
- `decision_relevant` uses `abs_gap` only in the bidirectional case. This must be preserved precisely.
- There are **no direct unit tests** for `_quintile_record` in any study. The classify tests (`test_validate_study_classify.py`) consume pre-built quintile dicts — they test the gate logic, not the quintile computation. A bug introduced during migration (e.g., wrong sign logic for `abs_gap`) would not be caught by the existing test suite unless it happened to flip a verdict that the freeze tests are watching.
- This gap is the primary risk for C3.

### 5.5 Preconditions

**Needs additional safeguards.**

Before proceeding with C3, add direct unit tests for `_quintile_record` covering:
1. Monotone-increasing series → `is_monotonic=True`, `decision_relevant=True` (gap sufficient)
2. Monotone-decreasing series, unidirectional → `is_monotonic=False`, `decision_relevant=False`
3. Monotone-decreasing series, bidirectional → `is_monotonic=True`, `decision_relevant=True` (abs_gap sufficient) — this is the fixture case
4. Zigzag series → `is_monotonic=False` in both unidirectional and bidirectional modes
5. Insufficient data (n < 25) → returns `None`
6. Binary-range target (gap=0.12, threshold=0.10) → `decision_relevant=True`

These tests must pass on the current per-study implementations before migration, and must continue to pass on the shared implementation after migration.

### 5.6 Recommended Design

- **Target module:** `research.kernels.distribution` (already houses distributional statistics; quintile stratification is a natural fit) or a new `research.kernels.stratification` if the distribution module is already logically full. A new module is acceptable here.
- **Public API:**

```
quintile_stratification(
    df: pd.DataFrame,
    signal: str,
    signal_id: str,
    position: str,
    block: str,
    target: str,
    gap_threshold: float,
    bidirectional: bool = False,
) -> dict | None
```

- **Required parameters:** `target` and `gap_threshold` must be explicit at every call site, not absorbed as defaults. This forces lens-specific policy to be visible in the study module.
- **Hidden divergences that must become explicit:**
  - `bidirectional=True` at the fixture call site (for `fdr_avg`; may be `False` for `was_home` and `fixture_count`)
  - `target="total_points"` for same-GW fixture vs. `"total_points_next_gw"` for lag-1 lenses
  - `gap_threshold=0.10` for binary target (availability) vs. `1.0` for continuous (all others)

---

## 6. Test Adequacy Review

### Classify tests (`test_validate_study_classify.py`)

Coverage is thorough for the gate sequence:
- All gate outcomes (insufficient, CI crosses zero, decision relevance fail, block stability fail, informative, unstable) are tested for all four studies.
- The fixture bidirectional monotonicity path is tested (`TestFixtureClassify.test_negative_rho_informative_with_bidirectional_monotone`).
- The form `clears_naive_baseline` path is tested.

**For C1:** These tests bypass `_bootstrap_spearman_ci` entirely (they operate on pre-built dicts). They do not protect against a change to CI computation. The kernel's own tests plus the verdict freeze tests provide the real protection.

**For C2:** These tests do not exercise `_evidence_row`. They verify that `cls["lens_status"]` is correct; the projection of that value into a governance row is untested here.

**For C3:** These tests consume pre-built quintile dicts. A bug in `_quintile_record`'s gap or monotonicity computation is not caught here.

### Evidence record tests (`test_evidence_record.py`)

Cover `write_evidence()` and `decision_class_for()` comprehensively. Do not test `_evidence_row` in isolation. Adding `build_evidence_row` to this module should be accompanied by a dedicated test class.

### Verdict freeze tests (`test_evidence_verdict_freeze.py`)

Provide the strongest end-to-end protection: any behavioral change that alters a ratified (signal, position) → decision_class mapping will be caught before commit. This is the safety net that makes C1 and C2 safe to proceed without additional preconditions. For C3, this net is present but would only catch a regression if it happened to flip a verdict on a currently ratified signal/position pair — it would miss a bug on a "uninformative" pair that remains uninformative for the wrong reasons.

### Remaining blind spots

1. **No unit tests for `_quintile_record`** — the primary gap for C3.
2. **No unit tests for `_correlation_record`** — out of scope for Phase C but noted.
3. **No unit tests for `_bootstrap_spearman_ci` in study modules** — moot once consolidated into the kernel, which is already tested.

---

## 7. Architecture Impact Review

### C1

No architecture change. `research.kernels.resampling` already exists within the research layer and is already owned by the research domain. Moving usage of a local function to this module is a caller-location change, not a layer boundary change.

No governance behavior changes. The kernel function is deterministic given the same inputs and explicit parameters.

No contract changes. The evidence.yaml schema is unaffected.

### C2

No architecture change. `research.families.evidence_record` already owns `write_evidence` and `decision_class_for`. Adding `build_evidence_row` to the same module co-locates all three evidence construction functions in one place — it is a consolidation within an existing owner, not a boundary change.

No governance behavior changes.

### C3

No architecture change. `research.kernels.distribution` (or a new `research.kernels.stratification`) is within the research layer. Quintile stratification is a statistical kernel function with no governance authority.

**One precision point on C3:** the `bidirectional` parameter makes implicit fixture-family knowledge explicit in the study module. This is a clarification of existing authority, not a transfer. The fixture study retains full ownership of which signals are bidirectional — it now states that fact at the call site rather than encoding it silently in a private copy of the function.

---

## 8. Recommended Refactoring Sequence

### Recommended: C1 → C2 → C3

**Rationale:**

**C1 first** because:
- It requires the fewest judgment calls (kernel exists, algorithm is identical, no parameter design decisions needed).
- It establishes the pattern: a study replaces a local private function with an explicit kernel call, passing study-level constants explicitly. C3 will follow the same pattern.
- Any unexpected friction in the migration idiom surfaces on the lowest-risk item.

**C2 second** because:
- It is zero-risk and zero-judgment. A pure co-location move.
- It benefits from having just seen the C1 migration pattern (same study files, same import structure).
- Completing it before C3 clears all zero-divergence duplication, leaving C3 as the sole remaining task with a design decision.

**C3 third** because:
- It requires a precondition (new unit tests) that does not exist yet.
- It has the most complex parameter design (`bidirectional`, explicit `target`, explicit `gap_threshold`).
- Completing C1 and C2 first means that by the time C3 is executed, the study files are cleaner and the change surface is smaller.

An alternative sequence of C2 → C1 → C3 is also safe but slightly sub-optimal: C2 first means the first migration does not establish the kernel-call pattern that C1 and C3 share.

---

## 9. Go/No-Go Decisions

### C1 — `_bootstrap_spearman_ci()`

**GO**

- The target module exists and is already tested.
- The study implementations are identical; there is nothing to reconcile.
- The one required practice (explicit parameter passing) is a normal code hygiene expectation, not a special safeguard.
- The verdict freeze tests provide end-to-end protection.

### C2 — `_evidence_row()`

**GO**

- Zero behavioral divergence.
- Natural co-location within an existing module the studies already depend on.
- No new dependencies introduced.
- Should be accompanied by direct unit tests for the extracted function (low effort, high value).

### C3 — `_quintile_record()`

**CONDITIONAL GO**

The consolidation is justified and the design is clear. The condition is:

> Direct unit tests for `_quintile_record` must be written and passing on the current per-study implementations before migration begins.

The tests must cover, at minimum: unidirectional monotone increasing, unidirectional monotone decreasing (→ fails), bidirectional monotone decreasing (→ passes), zigzag (→ fails in both modes), insufficient-n (→ returns None), and the binary-target threshold (0.10 gap).

Without these tests, a subtle bug in the `bidirectional` / `abs_gap` path could be introduced silently. With them, C3 carries LOW residual risk and should proceed.

---

## 10. Final Recommendation

The Phase A/B hardening has produced a test suite capable of safely supporting all three Phase C consolidations. The classify tests, evidence record tests, and verdict freeze tests together form a three-layer safety net that covers the governance-critical output paths.

**Proceed with C1 and C2 immediately.**

Both are pure co-location moves with no behavioral change, no parameter design decisions, and clear target modules. The cost of delay is increasing maintenance burden with no offsetting benefit.

**Proceed with C3 after adding `_quintile_record` unit tests.**

The precondition is modest (one test class, ~6 focused test cases). Once satisfied, C3 follows the same kernel-call pattern established by C1 and carries LOW residual risk. The explicit `bidirectional` parameter is a correctness improvement, not just a maintenance improvement — it removes a hidden assumption from four private function copies and makes it auditable.

**Do not proceed with any Phase C item concurrently.** Execute C1 as a standalone PR, verify tests pass, then execute C2, then execute C3. This keeps the per-item change surface small and makes any regression straightforward to attribute.

### What Phase C does not address

- `_correlation_record` remains per-study (target column divergence, out of scope).
- `_classify` remains per-study (form `naive_rho` divergence, runner abstraction deferred).
- Any new lens added after Phase C will still need to define its own `_correlation_record` and `_classify` but can import the consolidated `bootstrap_spearman_ci`, `build_evidence_row`, and `quintile_stratification` from their respective kernel/family modules.
