# team_goals_against slice — plan (spec §10 step 4)

**Status:** plan to build against · **Type:** spec
**Parent:** [docs/model-redesign-spec.md](model-redesign-spec.md) (§2 Model/Term contract, §3 pool+grain, §5 baselines, §10 migration)
**Precedent:** the `goals` slice — [model/terms/goals/](../model/terms/goals/) (`spec.py` · `goals.py` · `ASSUMPTIONS.md` · `test_goals.py` · `notebook.ipynb`)
**Frozen record of the numbers:** [docs/studies/results/predictive-phase3-points-model.md](studies/results/predictive-phase3-points-model.md)

## Why this slice, early

This is the **joint model** the whole contract split was designed for (spec §2, resolved decision #2):
D-D proved `clean_sheet = 1{GA=0}` and the conceded penalty `-floor(GA/2)` are the **same random
variable** (team goals-against), so one model must emit **both**. Doing it now — right after `goals` —
proves the *Model-emits-many-Terms* shape before it bites later. The joint model already exists in
[points_model.py](../model/forecast/points_model.py) (`walk_forward_team_ga`), so this is a faithful
strangle, not a rewrite.

## Locked decisions (2026-07-17)

1. **B — minimal/selected are siblings.** Both are team-GA **Poisson at `team_gw` grain**:
   - `minimal` = `ga_roll3` only (mechanistic bar + fast smoke-test).
   - `selected` = regularized over the full pool (`ga_roll3/5, xgc_roll3/5, was_home, fdr_avg`).
   The old **player-Binomial** clean-sheet model (`clean_sheets ~ …`, Phase-2.1) is **not** a pool draw;
   it is an *external legacy comparator* the notebook may log beside the gate. This keeps "one pool,
   two draws, delta = what selection bought" intact (the `goals` precedent).
2. **`baseline_col` per term** (the naive incumbent, spec §5) — deliberately dumb, lagged rolling:
   - `clean_sheet.baseline_col = "clean_sheets_roll3"` (the frozen CS incumbent).
   - `conceded.baseline_col` = a team's **lagged GA** rolling mean mapped through `-floor(GA/2)`
     (built in the term, analogous to `goals`'s `goals_prior`). Both terms gated symmetrically.
3. **Faithful extract; defer team-xGC FE.** Extract with the **existing** features so `p_cs` /
   `e_conceded_pts` reproduce the frozen numbers to the bit. A proper **minutes-aware team xGC**
   (from per-player xGC) is a *separate* `features/build.py` step — declared here as an
   **unmaterialized pool candidate** (`team_xgc_minutes_aware`), not built in the migration. The
   "does lagged xGC beat lagged GA at predicting team GA" question is a discovery check / the model's
   inner selection (the `xg_vs_goals_forecast_skill` precedent), **never** the baseline.

## New infra required first

The one genuinely missing piece: a **`team_gw → player_gw` broadcast** in
[model/features/build.py](../model/features/build.py). Today `build.py` has `materialize` +
`assert_lag_safe`; the joint model fits at `team_gw` but its terms are consumed at `player_gw` (the
merge at [points_model.py:605](../model/forecast/points_model.py#L605)). Add:

```python
def broadcast(team_frame, mart, cols) -> pd.Series/DataFrame:
    """team_gw quantities -> player_gw rows via (team_id, gw) left-join (checked, not implicit)."""
```

This satisfies spec §3 decision #4 (explicit grain + join). It is small, general, and reused by every
future team-grain feature — write it as the first commit of this slice, with its own property test
(no row multiplication; NaN where a team-fixture is absent).

## What moves (extract → `model/terms/team_goals_against/`)

| From `points_model.py` | To |
|---|---|
| `build_team_ga_panel` | `TeamGoalsAgainstModel.population` (team_gw) + the FeaturePool grain |
| `TEAM_GA_FEATURES`, `MIN_TEAM_TRAIN_ROWS` | `spec.py` `TEAM_GA_POOL` + fit guards |
| `walk_forward_team_ga` (the Poisson fit loop) | `TeamGoalsAgainstModel.fit` (`minimal`/`selected`) |
| `_conceded_penalty_expectation`, `p_cs = exp(-λ)` | `emit -> {"clean_sheet": p_cs, "conceded": e_conceded_pts}` |
| `team_ga_cs_validation` | `CleanSheetTerm.validate` (vs `clean_sheets_roll3`) |
| *(new)* | `ConcededTerm.validate` (vs lagged-GA → `-floor/2`) |

## Folder (mirrors goals)

```
model/terms/team_goals_against/
  __init__.py        exports TeamGoalsAgainstModel, CleanSheetTerm, ConcededTerm
  spec.py            TEAM_GA_POOL (grain=team_gw; minimal=("ga_roll3",);
                     candidates + unmaterialized team_xgc_minutes_aware); GRAIN
  team_goals_against.py
                     TeamGoalsAgainstModel(minimal|selected):
                       population (team_gw aggregate), check_assumptions
                       (GA dispersion via count_models + detectability floor),
                       fit (expanding walk-forward Poisson on team_ga),
                       emit -> {clean_sheet: p_cs, conceded: e_conceded_pts}
                     CleanSheetTerm(model): baseline_col="clean_sheets_roll3";
                       validate broadcasts p_cs to player_gw, Spearman vs baseline
                       for GK/DEF/MID (FWD get no CS points); diagnose
                     ConcededTerm(model): baseline_col derived (lagged GA→-floor/2);
                       validate for GK/DEF; diagnose
  ASSUMPTIONS.md     D-D joint identity; Poisson-on-team-GA family; team_ga = max
                     goals_conceded among appeared players; team-grain aggregation
                     is minutes-entangled (recorded limit, motivates the xGC FE);
                     lag-safety; detectability; conditional on appearance
  test_team_goals_against.py
                     contract (Model + both Terms); joint emit returns BOTH terms
                     (the shape proof); golden: minimal/selected emit ≡
                     walk_forward_team_ga p_cs / e_conceded_pts to the bit; broadcast
                     property (no row multiplication); detectability floor
  notebook.ipynb     render-not-decide, output-stripped: pre-fit assumptions →
                     CS gate + conceded gate → diagnose; legacy player-Binomial
                     comparator logged, not decided on
```

## Consumer wiring (what is *not* removed)

Nothing is deleted outright. `assemble_points` ([points_model.py:412](../model/forecast/points_model.py#L412))
repoints to the extracted term (`model → model` imports are allowed; do **not** block on `compose.py`).
`points_model.py` shrinks by the team-GA block + its gate but stays (goals/assists/saves/DC/bonus/compose
remain). `component_forecast.py` / `signal_combination.py` keep their own CS copies for now — reconciling
the **three** clean-sheet implementations to this single source is a *follow-up* cleanup, tracked, not
part of this slice.

## Invariant (unchanged)

`minimal`/`selected` emit `p_cs` / `e_conceded_pts` **bit-identical** to `walk_forward_team_ga` on a
fixed panel (golden test) ⇒ frozen composed numbers reproduce to 4dp. Import-linter 6/6 green; ruff
clean. Each commit independently reviewable behind the reproducibility gate.

## Commit sequence

1. `features/build.py` `broadcast` + property test (the missing infra).
2. `spec.py` `TEAM_GA_POOL` + `team_goals_against.py` model (fit/emit) + golden reproduction test.
3. `CleanSheetTerm` + `ConcededTerm` (validate/diagnose) + baseline_cols + gate tests.
4. `ASSUMPTIONS.md` + output-stripped `notebook.ipynb`.
5. Repoint `assemble_points`; confirm 4dp repro + contracts green.
```
