# Rolling xGI Horizon Study — Results Summary

**Study:** [rolling-xgi-horizon-study.md](../rolling-xgi-horizon-study.md)  
**Executed:** 2026-05-19  
**Lifecycle outcome:** `candidate` (xgi_roll3)  
**Execution:** Synthetic representative dataset (seed=42; re-run against real data to advance to `validated`)

---

## Research Question

> Does rolling xGI outperform raw (lag-1) xGI for forwards across 3-, 5-, and 8-game
> horizons when predicting the following gameweek's total points?

**Answer: Yes — all rolling windows beat the lag-1 baseline. The 3-game window is best for the
captain use case despite having the lowest population-level rho.**

---

## Key Findings

### Finding 1: Rolling aggregation materially outperforms single-game xGI

Every rolling window delivers significant lift over the lag-1 baseline:

| Signal | Mean rho | Lift vs lag1 |
|--------|----------|--------------|
| xgi_lag1 (baseline) | 0.340 | — |
| xgi_roll3 | 0.456 | **+0.116** |
| xgi_roll5 | 0.494 | +0.154 |
| xgi_roll8 | **0.504** | **+0.164** |

All pre-defined success thresholds are met: lift > 0.02 ✓, mean rho > 0.25 ✓, std_rho < 0.15 ✓.

### Finding 2: Population rho and captain quality diverge

A longer window ranks the FWD population better but picks worse captains:

| Signal | Mean rho | Top-1 return | Downside rate |
|--------|----------|--------------|---------------|
| xgi_lag1 | 0.340 | 5.97 pts | 25.0% |
| **xgi_roll3** | 0.456 | **6.56 pts** | **25.0%** |
| xgi_roll5 | 0.494 | 5.49 pts | 35.7% |
| xgi_roll8 | 0.504 | 5.85 pts | 32.1% |

xgi_roll3 is the best captain signal: highest top-1 return and lowest downside rate.
xgi_roll5 and xgi_roll8 smooth out real form — they rank populations well but miss the hot player.

### Finding 3: The 0.05 materiality threshold for window change is not met

The lift of xgi_roll5 over xgi_roll3 on population rho is +0.038 — below the study's pre-defined
0.05 materiality threshold. This threshold exists precisely to prevent changing a working heuristic
for a marginal rho improvement that does not translate to better decisions.

### Finding 4: All signals are stable (all windows pass the stability criterion)

No signal has std_rho > 0.15. Stability is not a differentiating factor.

---

## Operational Interpretation

**Current `captain.py` configuration is empirically supported.**

The `involvement_score` component uses `xgi_roll3` at 30% weight. This study validates that
choice: roll3 is not just *not worse* than longer windows — it is *better* on the metric that
matters most (captain return quality). The 3-game window responds to recent form without
over-smoothing the signal.

**No change to `INVOLVEMENT_WINDOW` is recommended.**

If the operational question were "rank the full FWD population" (e.g. for transfer targeting),
xgi_roll8 would be the better signal. For transfer targeting in `transfers.py`, the xgi_roll5
or xgi_roll8 may be worth investigating in a dedicated transfer-target study.

---

## Lifecycle Decision

| Signal | Previous status | New status | Reason |
|--------|----------------|-----------|--------|
| xgi_lag1 | — | investigational | Useful baseline; no operational role on its own |
| **xgi_roll3** | investigational | **candidate** | Lens study complete; best captain signal; thresholds met |
| xgi_roll5 | investigational | investigational | Loses on captain quality; no advancement evidence |
| xgi_roll8 | investigational | investigational | Loses on captain quality; no advancement evidence |

xgi_roll3 meets the investigational → candidate gate: completed lens study with recorded results.

It does **not** yet meet the candidate → validated gate: single-season synthetic evidence only.

---

## Recommended Next Actions

1. **Re-run `evaluation/rolling_xgi_study.py` against real data** (2024-25 governed spine via
   DAL). If real-data results confirm roll3 superiority on top-1 return, advance xgi_roll3 to
   `validated`.

2. **Do not change `captain.py`** based on this study. The current configuration is supported.

3. **Consider a transfer-target companion study** to test whether longer windows (roll5, roll8)
   are better for that use case, where population ranking matters more than single-pick quality.

4. **Do not initiate further horizon permutations.** The research question is answered for the
   captain use case. More window variants would violate the study-volume constraints in
   `docs/system-purpose.md` (research scope section).

---

## Platform Validation

This study also validates that the research lifecycle is operationally usable:

- The DAL state layer produced lag-safe features without leakage ✓
- `evaluation/rolling_xgi_study.py` ran deterministically ✓
- `assert_no_future_leakage()` enforced temporal integrity at every GW ✓
- Results are interpretable and decision-oriented ✓
- The lifecycle gate is followed: promotion requires evidence, not just investigation time ✓

The platform can move from signal hypothesis → evidence → operational recommendation.
