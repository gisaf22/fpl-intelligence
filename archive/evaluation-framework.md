# Evaluation Framework

> **Archived note:** The module map in this document (`evaluation.windows`, `evaluation.baselines`,
> `evaluation.captain`, etc.) is historically preserved. These modules were moved to `tests/helpers/`
> as part of the S11 integration-test reorganisation. The philosophy, metrics, and baselines
> described here remain accurate; only the import paths are outdated.

## Purpose

This framework empirically evaluates whether state-derived operational heuristics
add decision-support value relative to naive baselines under historical conditions.

It exists to answer a specific question:

> Do state-derived operational signals meaningfully improve future FPL decisions?

This question cannot be answered by the DAL or governance layers alone. Validated
spine observations confirm that raw measurements are trustworthy. They do not
confirm that derived state constructs (rolling windows, trend logic, momentum)
are operationally useful predictors.

## The Core Distinction

**Validated raw observation ≠ validated operational feature.**

| Layer | What it validates |
|-------|-------------------|
| DAL spine | Raw observations are correct and complete |
| State layer | Derived constructs are computed correctly |
| **This framework** | Derived constructs are *useful* for decisions |

A spine observation `xgi = 0.72 in GW 14` means the measurement is trustworthy.
It does **not** mean that `xgi_roll3` (a derived average of the prior 3 GWs) is a
useful predictor of GW 15 performance. The evaluation framework tests that second
claim empirically.

## Operational Usefulness Philosophy

A heuristic is operationally useful if it produces better decisions than simpler
alternatives under historical conditions. "Better" is measured against explicit
naive baselines, not against abstract optimality.

This framework produces **evidence**, not certainty. A heuristic that outperforms
baselines historically may still fail in unusual seasons or against specific
opponent profiles. The outputs should inform, not guarantee.

### What counts as useful?

For captain selection:
- Higher mean top-1 return than the naive recent-form baseline
- Top-3 hit rate above the random baseline
- Lower downside rate than fixture-only selection

For transfer targets:
- Higher mean future cumulative return than the form baseline
- Improved consistency (lower variance) across evaluation windows

For feature lift:
- Rolling average Spearman rho > single-game Spearman rho
- Positive lift values for at least two of three comparison pairs

## Non-Goals

This framework does **not**:

- Train ML models or tune weights
- Forecast future performance probabilistically
- Optimise squad selection or simulate seasons
- Certify signals as universally predictive
- Replace governance or DAL validation
- Introduce Bayesian inference, Monte Carlo, or distributed tracking
- Auto-update heuristic parameters based on evaluation results

## Temporal Integrity

All evaluations must respect a strict temporal boundary: **rankings at GW N may
only use information available before GW N's deadline**.

### How this is enforced

The state layer (`build_player_gameweek_state`) applies a **lag-1 shift** to all
rolling window computations. Features at row `(player_id=P, gw=N)` encode:

```
points_roll3  = mean(total_points[N-3], total_points[N-2], total_points[N-1])
xgi_roll3     = mean(xgi[N-3], xgi[N-2], xgi[N-1])
```

The actual outcome (`total_points` at `gw=N`) is used **only as a post-hoc
evaluation target**. It never enters the ranking logic.

The `evaluation.windows.assert_no_future_leakage()` function verifies that any
features DataFrame passed to evaluation has the expected rolling columns in place
(confirming the state layer was not bypassed). If this assertion fails, the
evaluation aborts with a clear error.

### Explicit assumptions

- BGW rows have NULL performance columns (no imputed zeros that would bias rolls)
- Rolling windows with `min_periods=1` include partial history at season start
- The first 3 GWs of the season have limited rolling data — evaluation results
  from early-season GWs should be interpreted with caution

## Architecture

```
trusted spine observations
    ↓
stateful derived features      ← state layer (lag-1 guaranteed)
    ↓
operational heuristics         ← intelligence layer
    ↓
historical evaluation          ← this framework
    ↓
evidence of usefulness (or failure)
```

### Module map

| Module | Responsibility |
|--------|---------------|
| `evaluation.windows` | Temporal window utilities, leakage guard |
| `evaluation.baselines` | Naive benchmark strategies |
| `evaluation.metrics` | Reusable operational metrics |
| `evaluation.captain` | Captain heuristic evaluation |
| `evaluation.transfers` | Transfer target heuristic evaluation |
| `evaluation.value` | Value player heuristic evaluation |
| `evaluation.features` | Stateful feature lift vs raw spine signals |

## Baselines

Baselines are the mandatory comparison floor. A heuristic that cannot beat
`baseline_recent_points` on average captain return provides no marginal value
over the simplest possible strategy.

| Baseline | Signal used | Use case |
|----------|-------------|----------|
| `baseline_recent_points` | `points_roll3` only | Captain, transfer comparison |
| `baseline_highest_xgi` | `xgi_roll3` only | Captain involvement comparison |
| `baseline_fixture_only` | inverted `fdr_avg` | Schedule-only selection |
| `baseline_random_top_n` | random (seed=42) | Stochastic floor |

All baselines are:
- Deterministic (stable sort or fixed seed)
- Transparent (single-signal ranking, no composite weights)
- Reproducible (same inputs = same outputs always)

## Metrics

| Metric | Interpretation |
|--------|---------------|
| `mean_return` | Mean actual points of selected players |
| `top1_return` | Actual points of the top-1 pick |
| `hit_rate` | Whether the actual best player was in the selection set |
| `regret` | Opportunity cost: actual_best − pick (0 = optimal) |
| `rank_correlation` | Spearman rho: ranking alignment with actual returns |
| `return_variance` | Standard deviation of returns (consistency proxy) |
| `downside_rate` | Fraction of GWs below a threshold (catastrophic miss rate) |

For captain evaluation specifically:
- **FPL context**: a captain returning < 4 points is a damaging outcome
- **Downside rate < 0.2** is operationally acceptable for a captain strategy
- **Top-3 hit rate > 0.5** suggests the heuristic captures plausible candidates

For feature lift:
- **rho > 0.3** is meaningfully useful for operational decisions
- **rho 0.1–0.3** is a weak signal, use cautiously
- **Rolling rho > lag1 rho**: state construction adds lift over raw single-game

## Stateful Feature Evaluation

The `evaluation.features` module directly tests the state layer's core claim:
that rolling-window aggregations are better predictors of future performance than
raw single-game observations.

Three paired comparisons:

| Rolling signal | vs | Single-game signal | Question |
|----------------|----|--------------------|----------|
| `points_roll3` | vs | `points_lag1` | Does 3-GW form beat last game? |
| `xgi_roll3` | vs | `xgi_lag1` | Does rolling xGI beat last-game xGI? |
| `minutes_roll5` | vs | `minutes_lag1` | Does 5-GW minutes beat last-game minutes? |

A positive **lift** value (rolling_rho − lag1_rho) confirms that the state
construction step adds operational signal. A negative lift value is a signal
that the rolling average may be smoothing out useful information.

## Limitations

1. **Historical only**: results describe past seasons. Future seasons may differ.
2. **Population size**: the eligible player pool varies by GW (injuries, BGWs).
3. **No transfer costs**: transfer evaluation ignores price and budget constraints.
4. **No squad context**: captain and value evaluations assume unconstrained choice.
5. **Early-season bias**: GWs 1–3 have limited rolling history; metrics are noisy.
6. **BGW handling**: BGW GWs reduce available outcomes, shrinking evaluation pools.
7. **Single-GW captain**: captain evaluation measures one-GW outcome only.

## Related Documents

- [DAL Contract](../dal/DAL_CONTRACT.md) — spine column definitions and null rules
- [DAL README](../dal/README.md) — DAL architecture and layer boundaries
- [CONTEXT.md](../CONTEXT.md) — project context and research boundaries
