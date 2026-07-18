# bonus term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/bonus/bonus.py` → `BonusModel` / `BonusTerm`
**Frozen record of the numbers:** [docs/studies/results/predictive-phase3-points-model.md](../../../docs/studies/results/predictive-phase3-points-model.md)

The bonus term predicts **E[bonus]** (top-3 BPS in a match → 3/2/1). It is the **only** term that is not
a lagged forecast — the assumptions below are why it is shaped differently from all the others.

## 1. Contemporaneous scoring-map, NOT a lagged forecast

Bonus is **caused by the same-match performance** (BPS is computed from that match's actions). So bonus is
not forecast from history — it is a **map from returns to bonus**, applied at composition/simulation time
when the returns are expected (or sampled). The predictor is `returns_pts` = the FPL point value of the
modelled returns (goals/assists/CS/GK-saves), a **same-match composite**, not a `*_roll` lagged feature.
Its `FeatureSpec` is therefore `known_future` (a scoring map), not strictly-prior.

## 2. Lag-safety lives in the coefficients, not the input

The per-position OLS **coefficients** are fit on prior gameweeks (`gw < t`) — that is the leakage-safe
part. They are then applied to the **contemporaneous** `returns_pts`. This is legitimate: we are not
peeking at the future, we are calibrating "given these returns, how much bonus?" using only past
calibration data. The input being same-match is the definition of the term, not a leak.

## 3. Family — OLS (a magnitude calibration), not a GLM

D-B found `returns_pts` is a **strong BPS proxy** (Spearman 0.50–0.77) that a per-component GLM does
**not** beat, and adding DC **hurts** (D-C's small partial correlation does not survive as a linear term).
So the model is deliberately a single-predictor per-position **OLS** of realized bonus on `returns_pts`,
clipped to `[0, 3]`. It preserves the `returns_pts` **ranking** (a monotone calibration) and only sets the
**magnitude** — which is what composition needs.

## 4. The gate is a calibration check, not a ranking win

Because the calibration is monotone in `returns_pts`, the proxy's within-position ranking **equals** the
`returns_pts` signal's by construction (`passed` uses ≥, so parity is a pass). The gate confirms the
magnitude is right and nothing regressed — it is **not** claiming to out-rank the signal.

## 5. Exposes calibration coefficients for the simulator

Beyond `e_bonus`, `fit` exposes the per-(position, gw) **intercept + slope** in `Fitted.meta`. The
simulator needs them to apply bonus **per draw** so bonus **co-moves** with the sampled returns (a fixed
`e_bonus` would break that dependence in the points distribution).

## 6. Depends on the other terms (a composition-time input)

`returns_pts` is built from goals/assists/CS/saves. At **validation** (and the golden) these are the
**realized** mart components — so reproduction is exact and self-contained. At **composition** they are
the **expected** components emitted by the other terms — a cross-term dependency that is a compose-layer
wiring step, deferred here (like the other consumer repoints), not part of this slice.

## 7. Standalone — a terminal one-off shape

Bonus is OLS + contemporaneous, unlike the Poisson-player and binary-per-position families, and it is the
**last** term — no second instance is coming, so there is no rule-of-three trigger. It is written
standalone; abstracting an OLS base off one terminal instance would be premature.
