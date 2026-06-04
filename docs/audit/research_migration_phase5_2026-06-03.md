# Research Layer — Diff-Level Migration Plan (Phase 5) + Safety Review (Phase 6)

**Status:** executable migration plan, re-based onto the **object-primary** target tree in
[research_target_architecture_2026-06-03.md](research_target_architecture_2026-06-03.md).
**Precondition:** run **after** `phase6-composite-key-migration` lands on `main` (clean tree).
**Method:** `git mv` only (preserves history); each cluster = one PR; each PR independently green.

**Blast-radius facts** (measured): ~13 test files import `studies.*`; 2 notebooks import `studies.*`;
internal cross-imports within `studies/`; intelligence + guard tests reference `"studies/eda/"` as
**string literals**; `synth01` and the lenses are consumed **file-based** (no Python importer).

---

## 5.1 Migration phases (ordered by risk)

| Phase | Theme | PRs | Risk |
|---|---|---|---|
| 1 | Safe structural prep — create tree, no moves | 1 | 1/5 |
| 2 | Low-risk moves — no Python importers (file-based / docs only) | 1 | 1/5 |
| 3 | Medium-risk moves — internal + few test importers | 3 | 2–3/5 |
| 4 | High-risk moves — kernels breadth, promotions, governance exit | 3 | 4/5 |

---

## 5.2 Per-move specifications

### PHASE 1 — Safe structural prep (1 PR)

```
Action:       CREATE
Current:      —
Target:       research/{kernels, foundation/{integrity,target,signals,scope,joint,stability,
              redundancy,gap,boundary}, families/{form,market,fixture,availability}/{explore,validate},
              findings/records, runs}/__init__.py  +  model/{assemble,governance}/  +  archive/monitor/
Reason:       Empty destination tree so subsequent PRs are pure git-mv.
Risk:         1/5 — additive only.
Dependencies: none.
Tests impacted: none.
Rollback:     delete created dirs.
```
```
Action:       RENAME (parametrize guard)
Current:      tests/test_dal_architecture.py, test_intelligence_outputs.py — hardcoded "studies"
Target:       accept BOTH {"studies","research"} during transition (tuple constant)
Reason:       keep the "model/serve must not import research" guard green across the move window.
Risk:         1/5.
Dependencies: none. Tests impacted: the 2 guard tests (made transition-tolerant).
Rollback:     revert constant to "studies".
```

### PHASE 2 — Low-risk moves (1 PR; no Python importers)

```
Action:  MOVE        Current: studies/STRATEGY.md            Target: research/STRATEGY.md
Reason:  doctrine moves with layer.  Risk: 1/5.  Tests: none.  Rollback: git mv back.

Action:  MOVE+RENAME Current: studies/eda/findings/*         Target: research/findings/
         EDA_COVERAGE_MAP.md→COVERAGE_MATRIX.md · EDA_FINDINGS.md→FINDINGS.md · eda_0*.csv→records/
Reason:  first-class findings sink.  Risk: 1/5 (no importer).  Tests: none.  Rollback: git mv back.

Action:  MOVE        Current: studies/operational/phase9_backtest.py  Target: archive/monitor/
Reason:  monitor dropped.  Risk: 1/5 (doc refs only).  Deps: none.  Rollback: git mv back.

Action:  MOVE+RENAME Current: studies/synthesis/synth01_study.py  Target: model/assemble/composition_study.py
Reason:  combination/weighting is model.  Risk: 1/5 — verified no Python importer (writes yaml).
         KEEP its OUT_PATH (signals/governance/synth01_decisions.yaml) unchanged this PR.
Tests:   none.  Rollback: git mv back.

Action:  MOVE        Current: studies/runs/                  Target: research/runs/  (gitignored)
Reason:  run outputs follow the layer.  Risk: 1/5.  Rollback: git mv back.
```

### PHASE 3 — Medium-risk moves (3 PRs)

**PR 3a — Foundation assembly** (cross-signal EDA → `foundation/<stage>/`)
```
Action:  MOVE (git mv, then update intra-foundation imports)
Current → Target:
  eda_00_integrity.ipynb + _integrity_helpers.py        → foundation/integrity/
  eda_01_target.ipynb + _target_distribution_helpers.py → foundation/target/
  eda_02_signals.ipynb + profiling.py + scoping.py + _signal_distribution_helpers.py → foundation/signals/
  eda_04_population_validity.ipynb + population.py       → foundation/scope/
  eda_03_joint.ipynb + _joint_helpers.py + association.py → foundation/joint/
  eda_05_signal_stability.ipynb                          → foundation/stability/
  eda_06_redundancy.ipynb                                → foundation/redundancy/
  eda_08_study.py + EDA_08_DESIGN.md                     → foundation/gap/
  eda_pop_boundary_scatter.ipynb                         → foundation/boundary/
Reason:  dataset-level characterization; the one place organize-by-stage is correct.
Risk:    3/5 — notebooks hardcode `from studies.eda…`; scoping←profiling; helpers←kernels.
Dependencies: Phase 4 kernel move NOT yet done → keep importing `studies.kernels.*` for now
              (transition shim, see Phase 4); OR sequence kernels before 3a. Chosen: shim.
Tests impacted: test_signals_population (studies.eda.population), test_relationship_geometry
              (studies.eda.association, _joint_helpers) → update import paths in same PR.
Rollback: revert PR.
```

**PR 3b — Families validate** (lenses → `families/<f>/validate/`)
```
Action:  MOVE + RENAME (lens dir → family/validate)
  studies/lenses/form/{study.py,__init__.py}      → families/form/validate/
  studies/lenses/form/LENS_DESIGN.md              → families/form/LENS_DESIGN.md
  (same: market→families/market, fixture_gw→families/fixture, avail→families/availability)
Reason:  confirmatory tier, object-primary.  Risk: 3/5 — string path refs.
Dependencies: none on 3a.
Tests impacted: test_composite_key_migration, test_registry_lifecycle (lens path STRINGS) → update.
Rollback: revert PR.
```

**PR 3c — Families explore + eda_07 exit**
```
Action:  MOVE
  studies/experiments/rolling_xgi_study.py     → families/form/explore/
  studies/experiments/minutes_stability_study.py → families/form/explore/   (conditioning)
  studies/eda/notebooks/eda_07_signal_synthesis.ipynb → model/assemble/      (exploratory combination)
Reason:  family-specific explore studies; eda_07 is combination (model).
Risk:    3/5 — direct test imports.
Tests impacted: test_rolling_xgi_study, test_rolling_xgi_real_validation, test_minutes_stability_study
              → update import paths.  Rollback: revert PR.
```

### PHASE 4 — High-risk moves (3 PRs)

**PR 4a — Kernels relocation** (`studies/kernels → research/kernels`, keep names)
```
Action:  MOVE (+ temporary shim)
  studies/kernels/** → research/kernels/**
  Leave studies/kernels/__init__.py as a thin re-export shim (`from research.kernels.* import *`)
  so Phase 3 importers keep working; delete shim in PR 4c.
Reason:  toolbox follows the layer.  Risk: 4/5 — widest importer set.
Dependencies: must precede deletion of studies/ (4c).
Tests impacted: test_signals_redundancy, test_signals_stability, test_relationship_computation,
              test_rolling_xgi_*, test_kernels_{conditioning,multiplicity,resampling} → repoint.
Rollback: revert PR (shim makes it isolatable).
```

**PR 4b — Geometry promotion + governance exit**
```
Action:  MOVE (promote) + DELETE duplicate
  studies/eda/geometry.py → research/kernels/geometry.py ; delete the study-layer copy.
Reason:  relationship-shape is a domain-agnostic kernel; removes inlined-constants duplication.
Risk:    4/5 — consumers: foundation/joint(_joint_helpers), registry_sections, test_relationship_geometry.

Action:  MOVE (governance exit)
  studies/experiments/registry_sections_study.py → model/governance/registry_sections.py
  domain/signal_layers.py  (NEW)                  ← hoist SIGNAL_LAYER_VALUES from semantics (do FIRST)
  studies/eda/semantics.py                        → model/governance/semantics.py  (after the hoist)
Reason:  registry build + governance-vocab enrichment are model/governance concerns; the vocab
         hoist to domain/ removes the foundation→model cycle (Phase-6 #1, RESOLVED).
Risk:    4/5 — order matters: hoist vocab to domain/ and repoint semantics BEFORE the move.
Dependencies: domain/signal_layers.py exists and semantics imports from it (no upward dep remains).
Tests impacted: test_registry_build_parity, test_relationship_computation, test_relationship_geometry → repoint.
Rollback: revert PR.
```

**PR 4c — String refs, guards, docs, cleanup**
```
Action:  RENAME (strings) + DELETE
  intelligence/reporting/weekly_report_runner.py, intelligence/scoring/scoring_runner.py:
      "studies/eda/" → "research/…" (error-message strings only)
  guard tests (test_dal_architecture, test_intelligence_outputs, test_weekly_runner):
      transition tuple → "research" only
  docs: adlc.md §2/§4, layer-boundaries.md, downstream-dependency-governance.md, navigation-map
  DELETE studies/kernels shim ; DELETE empty studies/.
Reason:  finalize; remove transition scaffolding.
Risk:    3/5 — string + doc churn; low logic risk.
Tests impacted: the 3 guard tests (flip to research-only).  Rollback: revert PR.
```

**Deferred (separate follow-up, not blocking):** retire `G-EDA*`/`LENS-*` IDs in `research/findings/`
in favour of composite keys; relocate lens verdict JSON outputs into `findings/records/`.

---

## 5.3 Constraints honored

- **git-move friendly:** every move is `git mv`; no copy-delete.
- **Import safety:** Phase 4a kernel **shim** decouples the broad kernel move from importer updates;
  every other cluster updates its importers atomically in the same PR.
- **No cross-phase coupling:** each PR leaves the suite green; shims (kernels) are the only
  inter-phase link and are removed in the final PR.

---

## Phase 6 — Execution Safety Review

**Checks:** circular dependencies · ownership-boundary breaks · catch-all reintroduction · ambiguous placement.

### Top 5 failure modes

1. **🟢 RESOLVED — `semantics.py` upward-import (was 🔴).** `foundation/joint/_joint_helpers`
   imports `semantics`, which inlines a *copy* of governance's `SIGNAL_LAYER_VALUES`. **Locked
   decision (2026-06-03): hoist the shared vocab to `domain/`** (below research, so both research
   and `model/governance` import it from there). This removes the cycle **and** the original
   duplication smell in one move. Mechanics for PR 4b: (a) create `domain/signal_layers.py` holding
   `SIGNAL_LAYER_VALUES` (the canonical copy, replacing the inlined one); (b) repoint `semantics`'s
   enrichment functions to import from `domain/`; (c) `semantics` enrichment then has **no** upward
   dependency and may move to `model/governance` safely. `domain/` is already a shared below-research
   home (`domain/fpl_scoring.py`), so this introduces no new layer.
2. **🟠 Kernel-move import misses.** Widest importer set; a missed path → `ImportError`. **Mitigation:**
   transition shim + a single grep-driven sed pass + full `pytest` per PR.
3. **🟠 Notebook import paths.** Notebooks hardcode `from studies.eda…` in JSON; moving breaks
   execution. **Mitigation:** update notebook source imports in PR 3a; smoke-run `nbconvert --execute`.
4. **🟡 Findings split persists.** If lens verdict JSON stays under families while the record-of-truth
   is `findings/`, the "single handoff" invariant breaks. **Mitigation:** the deferred follow-up must
   relocate verdict JSON into `findings/records/` or add a referencing index.
5. **🟡 Catch-all reintroduction.** `foundation/` (any cross-signal thing) and `families/<f>/explore/`
   (any prototype) can drift into dumps. **Mitigation:** `foundation/` constrained to the fixed stage
   list; `explore/` entry gated by the funnel template + `Mode:` tag review.

### Boundary / cycle verdict
- **DAL → research:** clean (research reads mart via `dal.pipeline.load`).
- **research → model/serve:** clean *except* failure mode #1, which the plan blocks until resolved.
- **No catch-all** survives if the stage list + explore-gate hold.

**Migration risk score: 3/5** (manageable, not a trivial rename — driven by FM#1 + kernel breadth + notebooks).
Per phase: P1–P2 = 1/5, P3 = 2–3/5, P4 = 4/5.

---

## FINAL OUTPUT

**READY FOR IMPLEMENTATION: YES** — *failure mode #1 is now RESOLVED (domain/ vocab hoist, locked
above). The only remaining gate is (a) `phase6-composite-key-migration` landing on a clean `main`.
Phases 1–3 are green-lit to start the moment the branch is merged; PR 4b carries the domain/ hoist
as its first step.*
