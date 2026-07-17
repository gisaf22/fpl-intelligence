# team_goals_against term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/team_goals_against/team_goals_against.py`
**Emits:** `clean_sheet` (P(GA=0)) + `conceded` (E[-floor(GA/2)]) — one model, two terms.
**Frozen record of the numbers:** [docs/studies/results/predictive-phase3-points-model.md](../../../docs/studies/results/predictive-phase3-points-model.md)
**Plan:** [docs/model-redesign-team-goals-against-slice.md](../../../docs/model-redesign-team-goals-against-slice.md)

The joint model predicts **expected team goals-against per fixture** and derives both defensive terms
from that one quantity. This file records the assumptions it rests on; they are checked pre-fit by
`TeamGoalsAgainstModel.check_assumptions`.

## 1. The D-D joint identity — one model, not two

`clean_sheet = 1{GA=0}` and the conceded penalty `-floor(GA/2)` are **functions of the same random
variable**, team goals-against (GA). Modelling them independently permits the impossible `CS=1 & GA>0`
state (observed 0% of the time). So we fit **one** Poisson mean per team-fixture (`lambda_ga`) and derive
`p_cs = exp(-lambda_ga)` and `e_conceded_pts = E[-floor(GA/2)]` from it — internally consistent by
construction. This is why the term folder holds one `Model` emitting two `Term`s (spec §2).

## 2. Family — Poisson on team GA

Team goals-against is a low-count integer per fixture. The dispersion diagnosis
(`count_models.diagnose_overdispersion`) drives the family; `family_ok` keys off **material**
over-dispersion (index ≈ 1), not the n-sensitive LRT (same rule as the goals term). Poisson gives the
clean `p_cs = exp(-lambda)` closed form the identity above depends on.

## 3. Grain + the team GA target

Fit at **`team_gw`** grain (one row per `(team_id, gw)`). Team GA is the **max `goals_conceded` among
the team's players who appeared** — a full-match player saw every goal, so the max recovers the team
total. DGW rows are excluded (the team-fixture grain is ambiguous under two fixtures). The terms then
**broadcast** `p_cs` / `e_conceded_pts` back to `player_gw` via `features.build.broadcast` (a checked
one-to-many left-join on `(team_id, gw)`; spec §3 decision #4).

## 4. Team xGC is minutes-entangled (recorded limit → the deferred FE)

The materialized `team_xgc` is the **mean per-player xGC over appeared players** — it mixes the team's
defensive rate with *who* played and for how long (a sub's xGC weights equally with a starter's). This is
a known limitation, not a bug: it is why the pool declares an **unmaterialized** `team_xgc_minutes_aware`
candidate. Building a minutes-aware team xGC (and testing whether lagged xGC out-predicts lagged GA) is a
separate `features/build.py` step + discovery check — deliberately **not** done in this migration, which
reproduces the frozen numbers with the existing features. The naive **baseline** stays dumb (lagged GA),
never engineered.

## 5. One pool, two draws — siblings (decision B)

`minimal` = `ga_roll3` only (mechanistic bar + smoke-test); `selected` = the full materializable pool
(`ga_roll3/5, xgc_roll3/5, was_home, fdr_avg` = the frozen `TEAM_GA_FEATURES`). Both are team_gw Poisson,
so the delta is a clean "what the extra features bought". The old **player-Binomial** clean-sheet model
(Phase-2.1) is a *different grain and family* — kept as an external legacy comparator (notebook), **not**
a pool draw.

## 6. Lag-safety, venue, and fixture difficulty

`ga_roll*` / `xgc_roll*` are strictly-prior (shift(1) before rolling), asserted NaN on a team's first
appearance by the build/CI leakage property. `was_home` and `fdr_avg` are **known-future** — the upcoming
fixture's venue and difficulty are known before kickoff, so they are legitimate predictors, not leakage.

## 7. Detectability floor + conditional on appearance

Pre-fit, `check_assumptions` requires ≥40 feature-complete team-fixtures **and** ≥20 with a positive GA
before the slice is `detectable`; below the floor a null is **inconclusive** (spec §0-B). All gates are
computed over players with `minutes > 0` (the term ranks who actually featured); the conceded gate is
GK/DEF only, the clean-sheet gate GK/DEF/MID (FWD score neither).
