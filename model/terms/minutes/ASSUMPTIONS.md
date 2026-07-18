# minutes term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/minutes/minutes.py` → `MinutesHurdleModel` / `MinutesTerm`
**Shared shape:** `model/terms/_binary_component.py` (defensive_contribution + minutes are one logistic-per-position model)
**Frozen record of the numbers:** [docs/studies/results/predictive-phase3-points-model.md](../../../docs/studies/results/predictive-phase3-points-model.md)

The minutes term predicts **P(>=60' | played)** = `p60` one gameweek ahead. `p60` maps to appearance
points (`1 + p60`) and **gates the clean-sheet term** (CS is only awarded at >=60') — both compose-layer
uses, so the term emits the raw probability.

## 1. Minutes is a gate, not a smooth covariate

Appearance scores a step (1 for 1-59', 2 for >=60'), and CS is gated at >=60'. So the modelled quantity
is the **hurdle** `P(>=60')`, on the derived binary target `play60 = 1{minutes >= 60}` — logistic, the
same shape as defensive_contribution.

## 2. Conditional on appearance — P(play) is deferred (X1)

The population is `minutes > 0`, so this is P(>=60' **given the player featured**). Modelling P(play)
itself — the 0-minute **blank** tail — is X1, deferred (documented scope gap; it is the single biggest
missing tail for a full points distribution). Do not read `p60` as an end-to-end availability model.

## 3. GK override — a robust rate, not a logistic

Goalkeepers play >=60' ~99% of the time, so `play60` is near-constant for GK and a logistic is
**degenerate** (perfect-separation / unstable). GK are therefore **overridden** (`_fill_special`): a
prior-only expanding rate of `play60` per keeper, backfilled with the global GK rate, then `0.98` for a
keeper with no history. This is the one position-specific deviation the shared base exposes as a hook.

## 4. Outfield — per-position logistic on lagged minutes form

DEF/MID/FWD each get a separate logistic (expanding walk-forward) on lagged minutes at three windows
(`minutes_roll3/5/8`) + lagged starts (`starts_roll3`). Ranking is **~parity** with a raw lagged minutes
level — that is *expected and not a miss*: the value here is a **calibrated probability** for the
appearance/CS points, not a ranking win (a raw minutes level is not a probability).

## 5. Baseline + lag-safety

The per-term bar (spec §5) is `minutes_roll3` (lagged minutes level) ranking `play60`. `minutes_roll*`
are lag-safe mart columns; `starts_roll3` is built strictly-prior (shift(1) before rolling). Rotation /
availability signals (days-since-start, congestion) are declared unmaterialized `§3` pool candidates.

## 6. Structure note — the base is now confirmed

`minutes` is the **second** logistic term; together with defensive_contribution it confirmed the
per-position-logistic shape, so the shared `BinaryPerPositionComponent` base was extracted (rule of
three) and DC refactored onto it — with the GK deviation handled by the `_fill_special` hook rather than
a bespoke class.
