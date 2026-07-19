# Phase 0 — Baseline benchmark (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) Phase 0
**Produced:** 2026-07-04
**Code:** `model/eval/baselines.py`, `model/eval/walkforward.py`
**Population:** `minutes > 0`, DGW excluded; evaluate GW > 3; per-GW metrics over GWs with ≥ 20 rows.

## Frozen benchmark (real mart, GW 1–38, common evaluation set)

**Ranking is within-position only.** Squads fill under position quotas, so ranking a keeper against a
forward is meaningless — **cross-position pooling is abolished** (no `spearman_mean`, no cross-position
top-K, and no pooled one-line summary — see the 2026-07-13 update below). All baselines scored on the
**same rows** (the common set where every baseline is defined; n = 8728). `coverage` = share of
post-warmup rows on which the baseline is defined at all. The target is zero-inflated/right-skewed, so
squared error is haul-dominated — **RMSE is omitted**, and **MAE is not a leaderboard metric** (too
haul-noisy to compare models by). Proper scoring (Poisson deviance, CRPS) arrives in Phase 4.

### Per-position bars (the decision-relevant gate for Phase 1)

Squads fill under position quotas, so ranking that matters is *within* position — there is **no pooled
number**. Ranking quality spans a ~5× spread across positions (`walk_forward_by_position`; `k` scaled
to each pool):

| position | ~players/GW | best baseline | spearman | precision@k |
|---|---|---|---|---|
| GK | 18 | rolling avg (5) | **0.06** (≈ chance) | 0.28 @4 |
| DEF | 94 | expanding season avg | 0.167 | 0.35 @20 |
| MID | 128 | expanding season avg | **0.311** | 0.30 @20 |
| FWD | 34 | rolling avg (5) | **0.334** | 0.48 @8 |

- **GK is near-unrankable from scoring history** (≈ chance) — clean-sheet/team/fixture driven, not
  player persistence. Corroborates the diagnostic layer's GK abstentions.
- **MID and FWD are the rankable positions**; FWD has the highest top-of-list precision (elite forwards
  reliably return). **FWD is the one position where rolling-5 beats season-avg** — recent form carries a
  little more for forwards.
- **Phase 1 is gated per position**, not on the pooled number: a model must beat **GK ~0.06 · DEF 0.167
  · MID 0.311 · FWD 0.334**. A pooled win can be an artifact of easy position-level structure.

### Framing — conditional on appearance (important)

The population is `minutes > 0`, so every metric is computed over players who **actually featured**.
Availability is treated as known: the benchmark is *"ranking accuracy given the player played"*, a
valid sub-problem, **not** end-to-end forecast accuracy. Jointly predicting who plays belongs to the
availability family (later phase). Read every downstream model's score under the same caveat.
`precision@20` is tie-aware on the actual side (36% of returns are exactly 1 point).

## What it establishes

- **"Level persists"** — season average is the best ranker → a player's cumulative level is the
  strongest simple signal. Confirmed.
- **"Deviations mean-revert"** — last-GW is the *worst* ranker and smoothing helps monotonically
  (roll3 < roll5 < season) → chasing last week's result hurts. Confirmed.
- **Identity dominates (corroborates Q1b)** — an identity-free position-mean predictor is constant
  within a position and so ranks at chance: the ranking signal *is* player identity. (That predictor
  has since been retired from the harness — see the 2026-07-13 update — because being constant it
  produces no rank signal; the finding it established stands.)

## v1 scope limits (documented; deferred to later phases)

These are deliberate simplifications of the Phase-0 floor, named here rather than hidden:

- **(C) Rolling over appearances, not calendar** — because `minutes > 0` is filtered first, rolling
  windows average the last N *appearances*, silently skipping blanks/injury gaps (1598 such gaps in
  the data). Absence carries no signal and a window can be stale. Revisit when availability is modelled.
- **(D) DGWs dropped entirely** — never predicted or evaluated (avoids double-points distortion in a
  floor). A high-value FPL event is out of scope until a DGW-aware target is defined.
- **(E) New-player / early-GW under-coverage** — insufficient history yields NaN features (see
  `coverage`); the common set restricts to players with enough history, so newly-arrived players are
  under-represented exactly where interest is high. A cold-start treatment is a later-phase concern.

## Phase 0 gate — PASSED

Baselines produce reproducible per-GW scores (deterministic); the walk-forward harness passes its
no-future-rows leakage assertion (`_smoke_check_first_row_leakage`); baselines compared on a
coverage-matched common set with ranking-appropriate, tie-aware, per-position metrics, framed as
conditional on appearance. Phase 1 (hierarchical/ICC) may open — its promotion test is to beat the
**per-position** bars above (GK ~0.06 / DEF 0.167 / MID 0.311 / FWD 0.334). There is no pooled number to
game.

> **Correction 2026-07-13a.** An earlier draft cited a pooled `spearman_mean 0.245` as a promotion
> target and named the leakage guard `_assert_no_leakage`. Cross-position pooling was abolished (see the
> top of this doc), so `spearman_mean` no longer exists; the real guard is
> `_smoke_check_first_row_leakage`. The per-position bars are unchanged — only the stale references are
> corrected.

> **Update 2026-07-13b — pooled summary + position-mean + MAE retired.** The pooled one-line leaderboard
> (`walk_forward_baselines`) and the identity-free `base_posmean` baseline were removed from the harness.
> Rationale: per-position ranking is the only decision-relevant metric; a pooled Spearman masks the ~5×
> cross-position spread, `base_posmean` is constant within a position (no rank signal), and MAE is too
> haul-noisy on this target to compare models by. `walk_forward_by_position` is now the sole benchmark;
> the per-position bars (GK ~0.06 / DEF 0.167 / MID 0.311 / FWD 0.334) are unchanged. Ad-hoc MAE for a
> single column is still available via `score_predictions`.

## Board stress-test (2026-07-05) — verified

Feature construction and leakage clean: `shift(1)` uses the prior gameweek (not row order), `posmean`
excludes the current GW, no `(player_id,gw)` duplicates, GW monotonic per player, no feature
suspiciously correlated with target, deterministic on re-run. Issues found and resolved: fair common
set (A), ranking/tie-aware/per-position metrics with RMSE dropped (B), conditional-on-appearance
framing (the benchmark selects on realised availability — a valid sub-problem, now documented).
Deferred with cause: joint availability modelling, DGW targets, calendar-vs-appearance windows,
cold-start coverage.
