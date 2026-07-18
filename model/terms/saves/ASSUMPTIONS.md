# saves term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/saves/saves.py` → `SavesModel` / `SavesTerm`
**Shared shape:** `model/terms/_poisson_component.py` (goals / assists / saves are one Poisson-player model)
**Frozen record of the numbers:** [docs/studies/results/predictive-phase2-component-model.md](../../../docs/studies/results/predictive-phase2-component-model.md)

The saves term predicts **E[saves] one gameweek ahead for goalkeepers** (~18% of GK points), composed
into E[points] via the 3-saves-per-point rule. Same Poisson-player shape as goals/assists, with two
GK-specific deviations noted below.

## 1. GK-only population

Saves are a keeper term, so the population is overridden to `position == GK` (plus the usual
`minutes > 0`, DGW excluded). This is the one structural difference from goals/assists.

## 2. Reproduction — the effective gate is GK train ≥ 30

In the god-file the saves component is fit **inside the all-position walk-forward loop**, whose outer
guard (`len(all-position train) < 100`) is **non-binding for GW > 3** — hundreds of rows accrue by the
first eval gameweek. The real constraint is the inner **GK train ≥ 30** check. On a GK-only population
the base's `min_train_rows_total` would otherwise apply the 100 to GK rows alone (much stricter), so it
is lowered to **30** to reproduce the god-file's effective gate exactly (golden test: bit-identical).

## 3. Family — Poisson (per the frozen model; dispersion is a recorded lever)

The god-file fits saves Poisson. Saves may be **more over-dispersed** than goals/assists (shots faced
swing widely by fixture), so `check_assumptions` can report `family_ok = False` (material over-dispersion)
— that is an **honest diagnostic, not a block**; the frozen model is Poisson, and NB-for-saves is a
recorded future lever, mirroring the goals NB note.

## 4. xGC as the shots-faced proxy; minutes as a covariate

Shots faced (the save-chance driver) are not directly in the mart, so lagged `xgc_roll3`
(expected goals conceded) is the proxy. `minutes_roll3` enters as a covariate, not an offset. A genuine
**shots-faced** rate and the **opponent's attacking volume** are declared unmaterialized pool candidates
(`shots_faced_roll3`, `opp_shots_forward`) — the §3 forward agenda, built later, not in this migration.

## 5. Scope — an honest GK ceiling, not a fixable gap

GK ranking is near-chance for *every* model (echoes Phase 0); adding saves lifts GK to **parity** with
the incumbent, no better. The success threshold reflects that: saves is worth modelling for the points
contribution, but GK within-position ranking has a low ceiling regardless. Conditional on appearance
throughout (the term ranks keepers who featured).
