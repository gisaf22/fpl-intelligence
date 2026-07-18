# assists term — ASSUMPTIONS

**Type:** spec (per-term assumptions) · **Model:** `model/terms/assists/assists.py` → `AssistsModel` / `AssistsTerm`
**Shared shape:** `model/terms/_poisson_component.py` (goals / assists / saves are one Poisson-player model)
**Frozen record of the numbers:** [docs/studies/results/predictive-phase2-component-model.md](../../../docs/studies/results/predictive-phase2-component-model.md)

The assists term predicts **E[assists] one gameweek ahead** and emits a single term (`assists`),
composed into E[points] via the flat assist weight. It is the same Poisson-player shape as `goals`, so
the assumptions largely mirror it; the assist-specific points are noted.

## 1. Family — Poisson (near-Poisson, Gate 1)

`assists` is a count, and even sparser than goals. The count-shape diagnosis
(`count_models.diagnose_overdispersion`) finds it **near-Poisson** (material dispersion ≈ 1); `family_ok`
keys off **material** over-dispersion, not the n-sensitive LRT (same rule as goals). NB is a recorded
future lever if a richer feature set surfaces genuine material dispersion.

## 2. Minutes as a covariate, not a proportional offset

Same as goals — the exposure test rejected proportionality, so `minutes_roll3` (expected minutes) enters
as a free covariate, never an `exposure=` offset.

## 3. xGI as the leading feature (creativity deferred)

The god-file feeds assists the same `xgi_roll3` as goals — xGI (xG + xA) carries the creative signal and
regresses to a truer rate than the very noisy realized-assist count. Faithful extraction keeps that.
**Assist-specific creation** (creativity / key passes) and **team attacking context** are declared as
unmaterialized pool candidates (`creativity_roll3`, `team_xg_roll3`) — the §3 forward agenda for assists,
built later in `features/build.py`, not in this migration. The naive **baseline** stays dumb (lagged
assists mean), never engineered.

## 4. Lag-safety, detectability, conditional on appearance

Identical to goals: inputs are the mart's lag-safe `*_roll3` columns (leakage property checked at
build/CI); the detectability floor requires ≥30 feature-complete rows **and** ≥10 positive-assist events
before the slice is `detectable` (a null below the floor is *inconclusive*); population is `minutes > 0`,
DGW excluded (ranking accuracy **given** the player featured).

## 5. Scope — MID is the position that matters

Assists concentrate at MID (creative midfielders) and to a lesser extent FWD/DEF; the success threshold
is set at MID. GK assists are vanishingly rare (near-chance ranking, like GK goals).
