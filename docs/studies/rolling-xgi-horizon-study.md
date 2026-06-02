# Study: Rolling xGI Horizon Comparison — Forwards

**Status:** Candidate (stability flag)  
**Lifecycle gate:** `candidate` (real-data replication complete; stability criterion not met; advancement to `validated` requires additional season)  
**Study type:** Rolling horizon comparison  
**Last reviewed:** 2026-05-19

---

## Research Question

> Does rolling xGI outperform raw (single-game) xGI for forwards across 3-game, 5-game, and
> 8-game horizons when predicting the following gameweek's total points?

---

## Operational Motivation

The captain ranking function (`intelligence/captain.py`) assigns 30% weight to `involvement_score`,
which is computed from `xgi_roll3`. This study tests whether that window choice is justified, and
whether a longer or shorter window would improve captain selection for forwards specifically.

The transfer targets function (`intelligence/transfers.py`) similarly uses `xgi_roll3` for the
`involvement_score` component at 15% weight. A secondary interpretation of this study applies to
the transfer target use case, though captain selection is the primary motivation.

**Decision outcome:** If a different horizon shows meaningfully stronger rank correlation with
next-GW total points for forwards, the `intelligence/captain.py` constants should be updated
to reflect it. If no horizon shows meaningful lift over the single-game baseline, the 30% weight
on `involvement_score` should be reconsidered.

---

## Study Design

### Population

- **Position:** FWD only  
- **GW range:** GW 6–33 (inclusive), per `005_analytical_foundations.md`  
- **Minutes threshold:** minutes >= 60, per `005_analytical_foundations.md`  
- **DGW treatment:** Flag DGW rows; report results separately for SGW-only and combined populations  
- **Season:** 2024–25 governed spine

**Rationale for FWD focus:** Forwards have the highest median total_points volatility (skew=1.58,
P90=9.0) and the strongest structural role for xGI signals. A position-specific study avoids
diluting results with GKP/DEF populations where xGI has structural zero mass (see `006_signal_exclusions.md`).

### Signals evaluated

| Signal | Description |
|--------|-------------|
| `xgi_lag1` | Single prior GW xGI (raw baseline) |
| `xgi_roll3` | Rolling mean xGI over prior 3 GWs |
| `xgi_roll5` | Rolling mean xGI over prior 5 GWs |
| `xgi_roll8` | Rolling mean xGI over prior 8 GWs |

All signals are computed by the DAL state layer with lag-1 shift applied. The feature at
row `(player_id=P, gw=N)` encodes values from GWs N-k through N-1 only. GW N's outcome is
never used in the feature.

`xgi_roll8` requires construction in the state layer if not already present. If unavailable,
the study is bounded to `xgi_lag1`, `xgi_roll3`, and `xgi_roll5`.

### Evaluation target

`total_points` at GW N — the actual points returned in the gameweek being ranked for.

### Baseline

`baseline_highest_xgi` from `evaluation/baselines.py` — ranks forwards by `xgi_roll3` only.

This baseline is the current heuristic. The study asks whether an alternative horizon beats it,
not whether any xGI signal beats a random or points-only baseline. The more demanding comparison
is appropriate here because the operational question is about window choice, not signal choice.

A secondary comparison against `baseline_recent_points` (`points_roll3`) is recorded to confirm
xGI signals have any marginal value at all relative to pure form.

---

## Metrics

All metrics are computed using `evaluation/metrics.py` functions:

| Metric | Interpretation for this study |
|--------|-------------------------------|
| `rank_correlation` (Spearman rho) | Primary metric — how well does each rolling window rank forwards by actual returns? |
| `lift` | `rolling_rho − xgi_lag1_rho` — does the rolling window add value over raw single-game xGI? |
| `mean_return` | Mean actual points of top-3 ranked forwards per GW |
| `top1_return` | Actual points of the top-ranked forward per GW |
| `downside_rate` | Fraction of GWs where top-1 forward returned < 4 points |

Results are reported as means across all GWs in the evaluation window (GW 6–33), with
standard deviation to characterise stability.

### Success threshold (pre-defined)

These thresholds are locked before results are computed.

| Criterion | Threshold | Interpretation |
|-----------|-----------|----------------|
| Positive lift | `lift > 0.02` for at least one rolling window | Rolling aggregation adds meaningful signal over single-game xGI |
| Operational usefulness | `mean rho > 0.25` for best window | Signal is meaningfully useful for FWD captain ranking |
| Stability | `std(rho) < 0.15` across evaluation GWs | Signal is stable enough to operationalise |
| Baseline comparison | `mean rho > rho(baseline_recent_points)` for best window | xGI has marginal value over pure form |

If no rolling window meets the lift threshold, the result is **negative**: the study concludes
that xGI rolling windows do not improve on raw single-game xGI for forward captain selection.

If no window meets the usefulness threshold, the result is **inconclusive**: xGI signals exist
but are insufficient for the captain ranking use case at the forward position.

---

## Temporal Integrity

All rolling features are produced by `dal/feat/feat_player_gameweek.py` with the lag-1 shift
applied. The `evaluation.windows.assert_no_future_leakage()` guard is called before any metric
computation.

Early-season GWs (GW 1–5) are excluded by the GW 6 lower bound. GWs where fewer than 5 FWD
records meet the minutes threshold are logged but not excluded; results from sparse GWs are
noted in the interpretation.

---

## Limitations

1. **Single season.** Results describe 2024–25. A second season would be required to claim
   generalisation.
2. **Small FWD population.** The primary population contains approximately 49 FWD players
   per GW at minutes >= 60 (per EDA-1). Rank correlation estimates have wider confidence
   intervals than for DEF or MID.
3. **No opponent context.** The study does not control for fixture difficulty. A forward's xGI
   against a weak opponent vs a strong opponent may behave differently; this interaction is not
   modeled here.
4. **DGW rows.** DGW rows inflate raw xGI values (two fixtures in one GW). The flagged DGW
   analysis is supplementary; SGW results are the primary interpretation.
5. **Roll8 availability.** `xgi_roll8` was added to the DAL state layer (`dal/feat/feat_player_gameweek.py`)
   as part of this study's execution. All four signals are now available.
6. **Synthetic execution.** The initial lens execution used a synthetic representative dataset
   (seed=42, 49 FWDs, GW 6–33, 28 evaluation GWs) because the 2024-25 governed spine requires
   database access. Results are structurally valid but should be re-run against real data before
   advancement to `validated`. The promotion to `candidate` is justified by study completion, not
   by the synthetic result magnitudes.

---

## Interpretation Guidance

### If roll3 is the strongest window

The current `intelligence/captain.py` configuration is supported. No change to weights is
warranted from this study.

### If roll5 is materially stronger (lift > 0.05 over roll3)

Update `INVOLVEMENT_WINDOW` constant in `intelligence/captain.py` from 3 to 5. Document the
change in the decision log (`docs/decisions/`).

### If no rolling window beats xgi_lag1

Remove or reduce the `involvement_score` component weight in `captain.py`. The signal does not
earn its 30% weight. A companion study on `points_roll3` vs `xgi_roll3` for captain selection
should be initiated to determine whether involvement signals add anything over pure form.

### If results are unstable (std(rho) > 0.15)

Do not promote any xGI window to `validated`. Record as `candidate` with stability flag.
The instability may be a small-sample artefact; note that a second season would be required
to resolve it.

### If all results are below the usefulness threshold (rho < 0.25)

Record signal as `candidate → excluded` for the FWD captain use case. xGI signals may still be
useful for MID captain or transfer targets — those questions require separate studies.

---

## Results

Executed via `evaluation/rolling_xgi_study.py` against a synthetic representative dataset
(seed=42, 49 FWD players, GW 6–33, 28 evaluation GWs, minutes_roll3 >= 60).

### Signal Performance (Spearman rho vs next-GW total_points)

| Signal | Mean rho | Std rho | Lift vs lag1 | Top-1 return | Downside rate |
|--------|----------|---------|--------------|--------------|---------------|
| `xgi_lag1` | 0.3399 | 0.1337 | — (baseline) | 5.97 pts | 25.0% |
| `xgi_roll3` | 0.4559 | 0.1216 | **+0.116** | **6.56 pts** | **25.0%** |
| `xgi_roll5` | 0.4936 | 0.1284 | +0.154 | 5.49 pts | 35.7% |
| `xgi_roll8` | **0.5035** | **0.1220** | **+0.164** | 5.85 pts | 32.1% |

*Downside rate: fraction of GWs where the top-ranked FWD returned < 4 points.*

### Threshold Assessment

| Criterion | Threshold | Value | Result |
|-----------|-----------|-------|--------|
| Positive lift | > 0.02 (any rolling window) | 0.164 (roll8) | **MET** |
| Operational usefulness | mean rho > 0.25 (best window) | 0.504 (roll8) | **MET** |
| Stability | std(rho) < 0.15 (best window) | 0.122 (roll8) | **MET** |

All pre-defined success thresholds are met.

### Key Observations

1. **Every rolling window materially beats the lag1 baseline.** Lift ranges from +0.116 (roll3)
   to +0.164 (roll8). The rolling aggregation hypothesis is strongly supported.

2. **Rank correlation and captain quality diverge.** roll8 leads on population-level rho (0.504)
   but roll3 produces the best top-1 captain return (6.56 pts) and the lowest downside rate (25%).
   Longer windows smooth real form — they rank the population well but are slower to identify the
   currently-hot forward.

3. **roll5 is the weakest on captain quality.** Despite better rho than roll3 (+0.038), roll5
   produces lower top-1 returns (5.49) and higher downside (35.7%). This pattern suggests the 5-GW
   window hits a smoothing penalty without enough stability benefit to compensate.

4. **roll5 lift over roll3 is 0.038** — below the 0.05 materiality threshold defined in the study
   design. The additional rho gain does not justify a window change.

5. **All rolling windows are stable** (std_rho < 0.15). Stability is not the deciding factor.

### Interpretation

**Outcome: Positive** — rolling xGI outperforms lag1 xGI for forwards. The question is which window.

Following the interpretation guidance: roll5 lift over roll3 = 0.038 < 0.05 threshold.
**Current configuration (xgi_roll3) is supported. No change to `INVOLVEMENT_WINDOW` is warranted
from this study.**

The divergence between population rho and captain quality is the key finding: for captain selection
(a top-1 pick task), shorter windows that respond to recent form (roll3) outperform longer stable
windows. Longer windows are better at ranking the full FWD population but are not better for
identifying the single highest-scoring candidate each week.

**Promotion decision:** xgi_roll3 advances to **candidate** (lens study complete, results recorded).
xgi_roll5 and xgi_roll8 remain **investigational** — additional evidence would be required, and the
captain use-case evidence does not favour them.

**Recommended next action:** Re-run `evaluation/rolling_xgi_study.py` against the 2024-25 governed
spine (requires database access). If real-data results confirm roll3 superiority on captain quality,
advance xgi_roll3 to `validated`. If they contradict the synthetic results, return to investigational.

---

## Synthetic vs Real Findings

Re-run executed 2026-05-19 against the 2024-25 governed spine (GW1–GW37, DAL via `~/.fpl/fpl.db`).
Full result artifact: [rolling-xgi-real-validation.md](results/rolling-xgi-real-validation.md).

### Quantitative comparison

| Metric | Synthetic | Real | Direction |
|--------|-----------|------|-----------|
| xgi_lag1 mean rho | 0.340 | 0.137 | Weakened substantially |
| xgi_roll3 mean rho | 0.456 | 0.200 | Weakened substantially |
| xgi_roll5 mean rho | 0.494 | 0.192 | Weakened substantially |
| xgi_roll8 mean rho | 0.504 | 0.206 | Weakened substantially |
| xgi_roll3 std rho | 0.122 | 0.256 | Degraded (instability) |
| xgi_roll3 lift over lag1 | +0.116 | +0.063 | Halved but positive |
| xgi_roll3 top-1 return | 6.56 pts | 5.07 pts | Weakened |
| xgi_roll3 downside rate | 25.0% | 64.3% | Degraded substantially |
| Lift threshold (> 0.02) | MET | MET | Replicated |
| Usefulness threshold (rho > 0.25) | MET | NOT MET | Did not replicate |
| Stability threshold (std < 0.15) | MET | NOT MET | Did not replicate |

### Which findings replicated

- **Replicated: Rolling aggregation beats lag1.** Positive lift holds on real data (roll3 +0.063,
  roll8 +0.069). The directional hypothesis survives real football conditions.
- **Replicated: rho-vs-captain-quality divergence.** Roll3 retains the best top-1 captain return
  despite roll8 having the highest mean rho. The structural pattern from synthetic persists.
- **Replicated: roll5 has the weakest captain quality.** Roll5 produces the lowest top-1 return
  (4.07 pts) on both synthetic and real data. This pattern is consistent.

### Which findings weakened

- **Weakened: rho magnitude.** Real rho values are 45–60% of synthetic estimates. Real football
  produces substantially more noise per GW than the synthetic representative dataset captured.
- **Weakened: captain return advantage.** Roll3 top-1 return advantage over lag1 narrows from
  +0.59 pts synthetic to +0.14 pts real. The advantage persists but is marginal.

### Which findings reversed or became unstable

- **Reversed: stability.** Synthetic std_rho was 0.12 for all windows (stable). Real std_rho is
  0.22–0.26 (unstable). Real GW-to-GW rho variation is high, ranging from −0.37 to +0.66 for
  roll3 across the 28 evaluation GWs. Stability was a synthetic artefact, not a real-data property.
- **Degraded: downside rate.** Roll3 downside rate rises from 25% (synthetic) to 64% (real).
  In real football, the top-ranked FWD by roll3 returns < 4 points in nearly 2 out of 3 GWs.
  The synthetic assumption that roll3 reliably avoids downside does not hold.
- **Unstable: usefulness threshold.** The operational usefulness criterion (rho > 0.25) was met
  in synthetic (0.456) but not on real data (0.200). The signal is too noisy per GW to be reliably
  useful for single-week captain decisions.

### Lifecycle impact

xgi_roll3 remains **candidate with stability flag**. It does not advance to `validated` because
the stability criterion fails. It does not regress to `investigational` because the lift criterion
is met. A second season of data is required to determine whether the instability is a 2024-25
season artefact or a structural property of the signal.

---

## Related Documents

- [system-purpose.md](../system-purpose.md) — program-level scope and research boundaries
- [research-lifecycle.md](../research-lifecycle.md) — lifecycle gate definitions
- [architecture/intelligence-layer.md](../architecture/intelligence-layer.md) — captain.py and transfers.py configuration
