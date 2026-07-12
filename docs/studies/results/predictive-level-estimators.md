# Point-estimate stress test — is the mean the right "level"? (frozen)

**Plan:** [docs/predictive-layer-plan.md](../../predictive-layer-plan.md) — pre-Phase-1 experiment
**Produced:** 2026-07-05
**Code:** `model/forecast/level_estimators.py` · **Notebook:** `model/eval/notebooks/level_estimators.ipynb`
**Question:** we rank players by their season *mean*. Does a robust / recency / upside statistic rank
next-GW points better, within position? (Decides what Phase-1 shrinkage shrinks toward.)

Population/metrics inherited from Phase 0: `minutes > 0`, DGW excluded, GW > 3, common eval set,
leakage-checked, **within-position ranking only**, conditional on appearance.

## Per-position ranking (within-position Spearman, best per position in bold)

| position | mean (incumbent) | best alternative | verdict |
|---|---|---|---|
| GK | 0.041 | EW mean 0.076 | all ≈ chance — nothing to choose |
| DEF | 0.185 | median 0.189 / Huber 0.187 | **tie** — robust centers ≈ mean (≤0.004) |
| MID | 0.336 | EW mean 0.341 | **tie** — EW +0.005 (noise) |
| FWD | 0.349 | **EW mean 0.371** | EW **+0.022** — recency helps forwards |

Full table (spearman): GK/DEF/MID/FWD × {mean, median, trimmed, Huber, p75, p90, EW} is in the
notebook. Quantiles (p75/p90) rank the body worse everywhere; median is worst for FWD (discards upside).

## Findings

- **Robustification does not help.** Median / trimmed mean / Huber essentially *tie* the mean for DEF
  and MID (differences ~0.003–0.004, within noise). Hauls are **real signal**, not noise to trim — so a
  robust center gains nothing, and for FWD it *loses* (median worst) by throwing away real upside.
- **The one real edge is recency, concentrated in FWD.** The exponentially-weighted mean (half-life 5
  appearances) beats the plain mean for MID (+0.005) and notably **FWD (+0.022)** — consistent with
  Phase 0's finding that rolling-5 beats season-avg for forwards. DEF sees no recency benefit (pure level).
- **Quantiles are a different decision.** p75/p90 don't rank the body better, but p90's top-k precision
  is competitive for FWD — relevant to *captaincy upside*, not general ranking.
- **GK** is near chance for every estimator.

## Decision (feeds Phase 1)

**Shrink toward the mean.** No robust center beats it by a meaningful margin, so the value is in
**variance reduction (shrinkage)**, not robustification — confirming the pre-registered guardrail
"prefer shrinkage over robustification." One refinement worth carrying forward: a **position-specific
recency tilt for FWD** (an EW component), given the consistent forward-only recency edge here and in
Phase 0. Quantile estimators are parked for a future captaincy/upside study, not general ranking.
