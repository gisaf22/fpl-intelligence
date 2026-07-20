# P(play) + blank-tail slice — plan + decision doc (spec X1; unblocks the final god-file)

**Status:** plan to approve · **Type:** spec
**Parent:** [docs/model-redesign-spec.md](model-redesign-spec.md) (X1 P(play) blank-tail, deferred) · [god-file deletion slice](model-redesign-godfile-deletion-slice.md)
**Goal:** score the **ex-ante universe including potential blanks**, so `captaincy_backtest` no longer needs
`points_model.walk_forward_points(predict_all=True)` — the last consumer pinning the final god-file.

## Why this is real new work (not a repoint)

`compose` conditions on appearance: `_master_panel` keeps only `minutes>0`, and every term's `population`
filters `minutes>0`. So a player whose realized minutes turned out **0** has **no compose score at all**.
`captaincy_backtest` picks a captain *ex ante* over a lagged-availability gate; if blanks are dropped from
the candidate pool, the backtest only ever ranks players who *turned out* to play — **hindsight leakage**.
`walk_forward_points(predict_all=True)` exists precisely to avoid this: it **trains** components on
`minutes>0` but **predicts** them on **all** rows. Reproducing that is the core of this slice.

## What P(play) is, precisely (vs what we already have)

Appearance is a ladder: **P(play)** = P(minutes>0) · **p60** = P(minutes≥60 | played). We already have the
second — the `minutes` term. We do **not** have P(play) as a term: it exists only as a crude **pooled**
inline logistic in `captaincy_backtest._p_play` (features `minutes_roll3/5`, `starts_roll3`; target
`played=1{minutes>0}`). Its target requires `minutes==0` rows in the population, so **P(play) cannot share
the `minutes` term's `minutes>0` population** — it is inherently a different, wider population.

The unconditional score is then one clean factor out front:
```
E[points]_uncond(row) = P(play)(row) × E[points | played](row)
```
where `E[points | played]` is exactly today's compose output, evaluated on that row's lagged features.

## Forks

### Fork A — appearance-model shape
P(play) as its **own term** (population = all rows, target `played`), or extend `minutes` into a two-stage
hurdle emitting both P(play) and p60?
**Recommendation:** **own term.** P(play) needs the *all-rows* population while p60 needs *minutes>0*; a
single joint fit spans two row sets awkwardly. A new `terms/p_play/` on the existing
`BinaryPerPositionComponent` (pool = `minutes_roll3/5`, `starts_roll3`) is the clean shape; `minutes`
(p60) is untouched. Note: the new term is **per-position** (the base), an upgrade over captaincy's pooled
inline logistic — so it is a *replacement*, not a bit-identical reproduction (see Fork D).

### Fork B — the "predict on the wider panel" capability (the core new work)
Both term bases (`_poisson_component`, `_binary_component`) must gain: population optionally **retains
`minutes==0` rows**, while training stays filtered to `minutes>0`, and prediction covers all rows.
**Recommendation:** a `keep_all` flag threaded through `population(...)` + the `fit` loop's train filter
(`train = df[(df.gw<t) & (df.minutes>0)]`), mirroring `walk_forward_points(predict_all)` exactly. Minimal
contract change; default `keep_all=False` keeps every current golden bit-identical.

### Fork C — where de-conditioning lives
`compose` gains an unconditional mode (`compose_points(mart, keep_all=True)` → `P(play) × conditional`,
scoring all rows), **or** compose stays conditional and captaincy does the `× p_play` multiply itself.
**Recommendation:** **compose owns it.** `compose_parameters(mart, keep_all=True)` widens the panel and adds
a `p_play` column; an unconditional `compose_points` multiplies the conditional decomposition by `p_play`.
Then captaincy just consumes compose — which is what finally lets `points_model` die with nothing left
inline. (`base_season` helper + `starts_roll3` via the trivial `_lag_roll` move here too.)

### Fork D — no bit-identical reference (like simulate)
captaincy's inline `_p_play` is pooled + crude, so the new per-position P(play) term will **not** reproduce
it, and enabling blank scoring **changes captaincy numbers** (the universe grows). There is no shipped
golden to hold.
**Recommendation:** validate P(play) as a **normal term** — gate its per-position ranking vs a lagged
availability baseline (`minutes_roll3`); accept the captaincy-number shift (same class of deliberate change
as the GK p60 improvement); pin it with structural + seed tests, not a frozen-vs-god-file vector.

## Sequence (independently reviewable)

1. **Term-base `keep_all`** — add the flag to both bases (population retains `minutes==0`; train filters
   `minutes>0`). Every existing golden stays bit-identical (`keep_all=False` default). + a test that on a
   panel with blanks, `keep_all=True` scores the extra rows and trains on the same rows as `keep_all=False`.
2. **`terms/p_play/`** — `PlayModel(BinaryPerPositionComponent)` (population all-rows, target `played`,
   pool `minutes_roll3/5`+`starts_roll3`) + `PlayTerm` (gate vs `minutes_roll3`) + spec/ASSUMPTIONS/tests;
   register in `registry.py`.
3. **compose `keep_all` + unconditional** — `compose_parameters(mart, keep_all=True)` adds `p_play` and the
   wider panel; unconditional `compose_points` = `p_play × conditional`. + `base_season` helper.
4. **Repoint captaincy + delete points_model** — captaincy off `walk_forward_points`; delete
   `points_model.py` + `tests/test_model_forecast_points_model.py` + the `team_ga_cs_validation`
   `team_goals_against/notebook.ipynb` cell; drop the transient `unmodeled_points_share` dup. Final grep:
   no `model.forecast.*` imports remain.

## Invariant
Steps 1–3 keep every existing golden bit-identical (`keep_all=False` is the default path). P(play) is
gated as a term; captaincy numbers shift by design (Fork D). Import-linter 6/6; ruff clean; full `pytest`
green at each step. Step 4 removes the last god-file with nothing importing it.
