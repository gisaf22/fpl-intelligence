# Phase 11 — Operational Usability Stabilization: Status

**Branch:** `stabilization/dal-hardening`  
**Plan:** [STABILIZATION_EXECUTION_PLAN.md](STABILIZATION_EXECUTION_PLAN.md)  
**Baseline:** 738 passed, 1 skipped | import-linter clean

---

## Slice Status

| Slice | Name | Type | Status | Commit | Notes |
|---|---|---|---|---|---|
| S1 | CONTEXT.md truth alignment | doc-only | ✅ DONE | `a8c2a5a` | Sections 3/5/6 corrected; section 2 path fixed (signals/eda → studies/eda) |
| S2 | ROADMAP correction + 3-command fix | doc-only | ✅ DONE | `4ca425b` | IMPLEMENTATION_ROADMAP archived; EXECUTION_GUIDE.md created |
| S3 | Governance test real-directory fix | test-only | ✅ DONE | `be952fd` | Scans intelligence/, studies/; staging violation in reporting/db.py fixed |
| S4 | pyproject.toml dependency hygiene | metadata-only | ✅ DONE | — | mlflow removed; pipeline block replaced with dev-mode-dirs=[.]; pandas declared |
| S5 | Integration test marking | test-only | ✅ DONE | — | 13 files marked; 655 non-integration / 84 integration |
| S7 | Makefile execution targets | operational | ✅ DONE | — | 7 targets added; make help/test-unit/build-registry/score all pass |
| S9 | Rho weights + methodology callout | explainability | ✅ DONE | — | 35 signal-meta spans; methodology callout present; renderer.py only |
| S8 | Bootstrap registry artifact | artifact | ✅ DONE | — | outputs/registry/gw36/ committed; assert_operational_safe passes; .gitignore exception added |
| S6 | conftest.py + db_path fixture | test-only | ⬜ TODO | — | APPROVE required; needs S5 |
| S10 | Stale doc archival + dir cleanup | doc-only | ✅ DONE | — | 2 docs archived; tasks/ removed; decisions/.gitkeep removed; signals/runs/README added |
| S11 | tests/integration/ → tests/helpers/ | test-only | ✅ DONE | — | 8 files updated; zero tests.integration refs; 739 collected |

---

## Scope Deviations

| Slice | Deviation | Reason |
|---|---|---|
| S1 | Section 2 path also fixed (signals/eda → studies/eda) | Path was factually wrong; signals/eda/ does not exist |
| S2 | IMPLEMENTATION_ROADMAP archived rather than annotated | User decision; EXECUTION_GUIDE.md created as replacement |
| S3 | dal/access.py + intelligence/reporting/db.py also touched | Pre-flight found real staging violation; fixed per plan rule (no allowlist expansion) |
| S4 | `packages = ["pipeline"]` replaced by `dev-mode-dirs = ["."]`; pandas declared | Removing the entire `[tool.hatch.build.targets.wheel]` block breaks hatchling editable builds; `dev-mode-dirs` is the minimal fix. Pandas was undeclared (pip-installed outside lockfile); declared it explicitly. |

---

## Current Test Baseline

```
738 passed, 1 skipped
lint-imports: 6 kept, 0 broken
```
