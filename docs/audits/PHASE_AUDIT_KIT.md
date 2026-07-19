# Phase Audit Kit — reusable per-phase code-quality assessment

Purpose: evaluate each predictive-layer phase through the same three lenses (platform SWE, analytics
engineer, data scientist) to **clean up, reuse, delete redundancy, and set boundaries between
concerns** — consistently and *safely*.

## How to use
1. Open a **fresh chat window** per phase.
2. Copy the **Reusable prompt** below, replacing the `{PHASE ...}` placeholders from the
   **Per-phase parameter table**.
3. The run produces `docs/audits/{phase}-audit.md` — a **findings report + a sequenced,
   behavior-preserving plan**. It **stops there** (assessment + plan only; no code changes).
4. After all phases: run the **Cross-phase synthesis** prompt to fold the six audit docs into one
   program plan (catches redundancy *between* phases).
5. Execute an approved plan as a *separate* step, on a branch, behavior-preserving, per the
   reproduction oracle.

Keep progress in `docs/audits/README.md` (an index: phase → audit doc → status → top actions).

---

## Reusable prompt (copy; fill the `{...}`)

```
ROLE: You are three reviewers auditing ONE phase of FPL Intelligence (research-first, NOT production):
a platform software engineer, an analytics engineer, and a data scientist. Produce an honest,
grounded assessment + a sequenced, behavior-preserving cleanup plan. ASSESSMENT + PLAN ONLY — do NOT
change code this run.

PHASE: {PHASE NAME}
READ (ground everything in real code, not memory):
  - Modules: {PHASE MODULES}
  - Frozen results (the REPRODUCTION ORACLE — any future change must reproduce these numbers to 4dp):
    {PHASE RESULTS DOCS}
  - Notebook(s): {PHASE NOTEBOOKS}
  - Shared eval API it SHOULD reuse: model/eval/ (population, baselines, metrics, scorer) +
    domain/fpl_scoring.py. Read model/governance/EVAL_DESIGN.md appendix (eval=measures/forecast=predicts;
    harness stays model-agnostic).
  - Conventions: ASCII-only; population = population.canonical/full_universe; within-position ranking;
    every gate should carry a block-bootstrap CI (metrics/scorer); import-linter dal->research->model->serve
    (6 contracts, kernels exempt); per-change pytest + ruff + lint-imports (when executing later).

THE THREE LENSES (what each looks for)
  - Platform SWE: reuse/DRY, coupling, dead code, private cross-package imports, hand-rolled loops that
    duplicate a shared component, missing/duplicated helpers, naming consistency, dataclasses where
    appropriate, testability (pure functions, hermetic tests), public vs private API.
  - Analytics engineer: single source of truth for POPULATION and METRICS; consistent scoring GRAIN;
    the eval-set/contract; whether the phase re-derives what a shared component already provides;
    reproducibility.
  - Data scientist: is there a BASELINE to beat and is it the RIGHT one (per position)? Does every
    comparison carry a CONFIDENCE INTERVAL? Is the METRIC right for the goal (rank vs top-K vs
    calibration vs decision)? Leakage (shift(1) before windows; strictly-prior features)? Power / honest
    scope limits? Any untested empirical claim stated as fact?

SHARED-COMPONENT REUSE CHECKLIST (flag each the phase reinvents instead of importing)
  [ ] population filter `minutes>0 & DGW`   -> should be `population.canonical` (or `full_universe`)
  [ ] `base_season` inline lambda            -> `baselines.base_season`
  [ ] per-position incumbent = base_season   -> `scorer.best_baseline_per_position` (GK!)
  [ ] hand-rolled `for pos: grouped_spearman` gate loop -> `scorer.score_gate/score_gates` (adds CI+coverage)
  [ ] private cross-import (`_grouped_spearman`, `_block_bootstrap_ci`, ...) -> public `metrics.*`
  [ ] block-bootstrap CI reimplemented       -> `metrics.block_bootstrap_ci`
  [ ] lagged-roll helper (`_lag_roll`/`_add_lagged_process`) duplicated across modules -> single source
  [ ] scoring multipliers / POSITION_SCORING re-hardcoded -> `domain.fpl_scoring`
  [ ] feature-roster / walk-forward `_fit_predict` patterns duplicated across component/signal/points

KNOWN REDUNDANCY PATTERNS (from prior audits — check if this phase has them)
  - the `minutes>0 & DGW` filter was inline in 8 files before extraction; check this phase's copy.
  - `_fit_predict` (walk-forward GLM) and Poisson/logistic fit helpers recur across forecast modules.
  - feature-list constants duplicated; per-GW eval-set dropna logic duplicated.
  - notebooks that pivot on a gate's output may ignore new CI/coverage columns.

OUTPUT (write to docs/audits/{phase}-audit.md)
  1. **What it is / what it touches** — purpose, modules, how used, against what (grounded, with file:line).
  2. **Findings by lens + severity** (HIGH = correctness / missing CIs / leakage / cross-cutting
     redundancy; MED = reuse/boundary/naming; LOW = cosmetic). Each finding: grounded evidence + fix.
     Separate DEFINITIONAL facts from UNTESTED hypotheses (do not assert unverified claims).
  3. **Action list by verb**: GO (delete/wrong choice) · MODIFY · HARDEN · RENAME · RESTRUCTURE ·
     REUSE (replace-with-shared). One line each, grounded.
  4. **Reproduction anchors** — the exact frozen numbers this phase must still reproduce after any change.
  5. **Sequenced plan** — behavior-preserving order (additive/reuse first, then structure, then naming),
     each step a "green + numbers-reproduced" checkpoint. Note what's OUT OF SCOPE.
  6. **Update the index** — set this phase's row in `docs/audits/README.md` to done, with its top-3
     actions, so the program stays trackable.
  End with a 5-line changelog-style summary + the single highest-leverage move.

GUARDRAILS: assessment + plan only (no code changes); behavior-preserving mindset (frozen numbers are
sacred); ground every claim in real code; recommendations not option-dumps; honest scope limits.
```

---

## Per-phase parameter table

| PHASE NAME | PHASE MODULES | PHASE RESULTS DOCS | PHASE NOTEBOOKS |
|---|---|---|---|
| Phase 0 — baselines + harness | `model/eval/{baselines,walkforward,metrics,population,scorer}.py` | `docs/studies/results/predictive-phase0-baselines.md` | `model/eval/notebooks/phase0_baselines.ipynb` |
| Phase 1 — ICC / shrinkage / level | `model/forecast/{level_estimators,shrinkage}.py`, `research/kernels/inferential/variance_components.py` | `predictive-phase1-icc-shrinkage.md`, `predictive-level-estimators.md` | `phase1_icc_shrinkage.ipynb`, `level_estimators.ipynb` |
| Phase 2 — ranking (component + combination) | `model/forecast/{component_forecast,signal_combination,count_models}.py` | `predictive-phase2-component-model.md`, `predictive-phase2-signal-combination.md`, `predictive-phase2-overdispersion.md`, `predictive-phase2-minutes-exposure.md` | `phase2_ranking.ipynb` |
| Phase 3.0 — points-equation closure | `model/forecast/points_model.py`, `domain/fpl_scoring.py`, `research/diagnostic/*` | `predictive-phase3-points-model.md`, `predictive-phase3-scoring-diagnostics.md` | `phase3_points_model.ipynb` |
| Phase 3.1 — simulator | `model/forecast/simulator.py` | `predictive-phase3-simulator.md` | `phase3_simulator.ipynb` |
| Phase 4 — calibration | `model/eval/calibration.py` | `predictive-phase4-calibration.md` | `phase4_calibration.ipynb` |
| Phase 5 — decisions + diagnostic | `model/eval/{captaincy_backtest,captaincy_diagnostics}.py` | `predictive-phase5-decisions.md`, `predictive-phase5-captaincy-diagnostic.md` | `phase5_decisions.ipynb`, `captaincy_ceiling_diagnostic.ipynb` |

(Notebooks live under `model/eval/notebooks/`; results docs under `docs/studies/results/`.)

---

## Cross-phase synthesis prompt (run last)

```
ROLE: platform analytics engineer. Read all docs/audits/*-audit.md. Produce docs/audits/PROGRAM_PLAN.md:
(1) redundancy that appears in >=2 phases (the same helper/pattern reinvented) — the highest-value
targets; (2) a de-duplicated, dependency-ordered, behavior-preserving execution plan (which shared
component absorbs each dupe; which frozen numbers gate each step); (3) any boundary violations
(eval<->forecast, private cross-imports) to fix globally. Assessment + plan only.
```

## Recommended sequence
Audit **2, 3.0, 5 first** (the biggest, most-reinvented modules — highest yield), then **1, 3.1, 4**,
then the **cross-phase synthesis**. Phase 0 is already audited (this kit is its output); re-run it only
if you want it in the same format. Execute approved plans one phase at a time, on a branch, verifying
the reproduction anchors before each merge.
