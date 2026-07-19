# god-file deletion slice — plan + decision doc (spec §10.5)

**Status:** plan to approve · **Type:** spec
**Parent:** [docs/model-redesign-spec.md](model-redesign-spec.md) (§10 strangler migration, §4 repro gate)
**Precedents:** [team-goals-against slice](model-redesign-team-goals-against-slice.md) · [simulate slice](model-redesign-simulate-slice.md)
**Strangled files (to delete):** `model/forecast/{component_forecast,points_model,signal_combination,simulator}.py`

## Where we are (scope-check, 2026-07-19)

The model layer already stands alone: **`terms/`, `compose`, `simulate`, `registry` import NOTHING from
the god-files** (the `model.forecast.*` strings in term `__init__.py` are docstring mentions, not imports).
Deletion is blocked only by *test references* and *two eval consumers*:

| Dependency | Scope | Kind |
|---|---|---|
| Term **goldens** import god-file fns as the reference | 7 test files, 13 sites | blocker (a) — freeze first |
| **Eval consumers** `calibration.py`, `captaincy_backtest.py` import `walk_forward_points` / `simulate_points` | 2 files | blocker (b) — the hard one |
| Legacy god-file tests `tests/test_model_forecast_{component,points_model,signal_combination,simulator}.py` | 4 files | die *with* the god-files |
| `signal_combination.py` | only its own test consumes it | near-standalone delete |
| `p21_pts` (Phase-2.1 4-component bar) | **only** `points_model`'s own test reads it | no external consumer |

**Repoint gap (blocker b):** `compose_parameters` already emits the eval `_REQUIRED` params under the
**same names** (`e_goals`, `e_assists`, `p_cs`, `p60`, `bonus_intercept`, `bonus_slope`), and
`model.simulate` already gives `p90`/`p_haul`. Only two columns `walk_forward_points` carries are missing:
- **`base_season`** — the expanding-prior incumbent (`expanding_prior_mean`); trivially recomputable on the compose panel.
- **`full_pts`** → replaced by compose **`e_points`** (differs at GK by design — the deliberate p60 improvement).

## Decisions (forks)

### Fork 1 — `p21_pts` fate
The Phase-2.1 four-component ranking bar. Read by **nothing** except the dying `points_model` test.
**Recommendation:** **drop it.** It is a legacy changelog comparator; `base_season` remains the incumbent
bar, and the `minimal`-variant of compose is the natural "component bar" if a partial-model comparison is
ever wanted again (spec §5 "the partial model as a bar"). Do not rehome dead code.

### Fork 2 — GK eval-number shift (sign-off)
Repointing `calibration`/`captaincy_backtest` onto compose means their outputs **change at GK** (compose's
robust `p60` replaces the flat-0.98 shortcut). This is the same deliberate improvement carried through the
compose + simulate slices.
**Recommendation:** **accept.** Log it in each eval file's docstring; the shift is the improvement, not a
regression. Any frozen eval-number test updates its GK expectations (non-GK unchanged).

### Fork 3 — golden-freeze style
**Recommendation:** **inline literal vectors** on a small fixed panel per term (consistent with the
seed-pinned regression vector just shipped in `test_simulate.py`) — not checked-in data files. Each term
already builds a deterministic synthetic panel in its test; freeze a handful of its emit/gate values to
4dp and drop the god-file import.

## Sequence (3 stages, independently reviewable)

### Stage A — golden-freeze (zero behavior change, do first)
Migrate all 7 term goldens off `from model.forecast.*` references onto inline frozen vectors. Pure test
refactor: each `test_*.py` currently computes `reference = <god_fn>(panel)` then asserts `emit == reference`;
replace with `assert round(emit[i], 4) == <frozen literal>` on the same fixed panel. Afterward **`model/terms`
imports nothing from `model/forecast`.** One commit per term (7) or grouped by base — TBD at build time.
Verify: `pytest model/terms model/features -q`, `lint-imports`, `ruff`.

Files: `goals`, `assists`, `saves` (Poisson base) · `team_goals_against` (2 goldens) · `defensive_contribution`,
`minutes` (binary base) · `bonus`.

### Stage B — eval repoint (behavior change at GK — Fork 2)
- Add a small `base_season` helper on the compose panel (reuse `expanding_prior_mean`).
- `calibration.py`: source the param panel from `compose_parameters` + `e_points` from `compose_points`;
  `simulate_points` from `model.simulate`. Drop `full_pts` → `e_points`.
- `captaincy_backtest.py`: same; `p90`/`p_haul` from `model.simulate`; drop `p21_pts` (Fork 1).
- Update the two eval tests' GK expectations; non-GK rows unchanged.
Verify: eval tests green; `lint-imports`; `ruff`.

### Stage C — delete + 3-CS reconciliation
- Delete `component_forecast.py`, `points_model.py`, `signal_combination.py`, `simulator.py`.
- Delete their 4 legacy tests `tests/test_model_forecast_{component,points_model,signal_combination,simulator}.py`.
- **3-CS reconciliation:** confirm the single clean-sheet source is the extracted `team_goals_against`
  model; the god-file player-Binomial CS (`component_forecast.walk_forward_component_points`) and the
  `signal_combination` CS go with the deletion.
- **Two live diagnostic fns must be relocated, not lost** (verified 2026-07-19 — both still live only in
  the god-files, each referenced by an eval notebook):
    - `component_forecast.xg_vs_goals_forecast_skill` (discovery check) → consumed by `phase2_ranking.ipynb`.
    - `points_model.unmodeled_points_share` (diagnostic) → consumed by `phase3_points_model.ipynb`.
  Also repoint/retire the `model/terms/team_goals_against/notebook.ipynb` cell that imports
  `points_model.team_ga_cs_validation` (a term-folder notebook, not eval) — it breaks on deletion too.
  Decide per fn: relocate to a proper home (discovery skill → `research`; diagnostic → `model/eval` or a
  diagnostics module) and repoint the notebook, **or** retire the notebook cell. Do NOT delete silently.
- `count_models.py`, `level_estimators.py`, `shrinkage.py` are **NOT** god-files — keep them + their tests.
Verify: full `pytest -q`; `lint-imports` 6/6; `ruff`; grep proves no remaining `model.forecast.{deleted}` imports.

## Invariant
Stage A changes no numbers (frozen vectors reproduce the god-file references to 4dp). Stage B changes only
GK eval numbers (logged, Fork 2). Stage C removes dead code with nothing importing it. Import-linter 6/6
green throughout; ruff clean; one reviewable commit per logical step.

## Pre-delete safety grep (Stage C gate)
```
grep -rln "model.forecast.\(component_forecast\|points_model\|signal_combination\|simulator\)" --include=*.py .
# must return ONLY the files being deleted in the same commit
```
