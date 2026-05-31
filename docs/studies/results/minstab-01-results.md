# STUDY-MINSTAB-01: Minutes Stability × Rolling xGI — Results

**Study ID:** STUDY-MINSTAB-01
**Status:** COMPLETE
**Executed:** 2026-05-19
**Design doc:** [minutes-stability-xgi-study.md](../archive/minutes-stability-xgi-study.md)
**Prior study:** [rolling-xgi-horizon-study-results.md](rolling-xgi-horizon-study-results.md)
**Interpretation:** `stability_does_not_condition_signal`

---

## 1. Execution Summary

Study executed deterministically using:

```python
features = load_mart().mart  # dal.pipeline.load().mart
results  = evaluate_minutes_stability_conditioning(features)
interp   = interpret_results(results)
```

- Evaluation window: GW 6–33 inclusive (28 GWs)
- Population: FWD rows only (93.0 mean per GW)
- All 31 validation tests passed before execution
- Population accounting closure verified: `n_stable + n_rotation + n_fringe + n_unknown == n_all_fwd` for all 28 GWs
- `minutes_roll5` coverage: 92.7% of FWD rows (190 UNKNOWN rows logged)
- Outputs: `outputs/minstab_01_detail.csv` (2,604 rows)

---

## 2. Cohort Summary

Cohorts assigned deterministically via fixed thresholds on `minutes_roll5` (5-GW rolling mean minutes, lag-1 shifted).

| Cohort   | Criterion              | Total rows | Mean n/GW | GWs with ≥5 players |
|----------|------------------------|-----------|-----------|---------------------|
| STABLE   | minutes_roll5 ≥ 60     | 452       | 16.1      | 28 / 28             |
| ROTATION | 30 ≤ minutes_roll5 < 60| 308       | 11.0      | 27 / 28             |
| FRINGE   | minutes_roll5 < 30     | 1,654     | 59.1      | 28 / 28             |
| UNKNOWN  | minutes_roll5 is NULL  | 190       | 6.8       | excluded            |
| **Total**| —                      | **2,604** | **93.0**  | —                   |

**Note on FRINGE population size:** The FRINGE cohort (59.1 mean per GW) is the largest by row count, comprising 63.5% of non-unknown FWD rows. This reflects the composition of the FPL FWD register: the majority of registered forwards average fewer than 30 minutes per gameweek, either as squad fillers, unused substitutes, or players returning from injury. This is a structural fact about the evaluation population, not an artefact of the threshold choice.

### Per-GW population accounting (GW 6–33)

| GW | n_all_fwd | n_stable | n_rotation | n_fringe | n_unknown |
|----|-----------|----------|------------|----------|-----------|
| 6  | 93 | 16 | 8  | 58 | 11 |
| 7  | 93 | 13 | 12 | 57 | 11 |
| 8  | 93 | 16 | 7  | 59 | 11 |
| 9  | 93 | 15 | 8  | 59 | 11 |
| 10 | 93 | 13 | 13 | 56 | 11 |
| 11 | 93 | 13 | 13 | 56 | 11 |
| 12 | 93 | 15 | 9  | 59 | 10 |
| 13 | 93 | 14 | 11 | 58 | 10 |
| 14 | 93 | 15 | 11 | 57 | 10 |
| 15 | 93 | 17 | 9  | 57 | 10 |
| 16–33 | — | — | — | — | — |

Full per-GW breakdown in `outputs/minstab_01_detail.csv`.

---

## 3. Signal Performance by Cohort

All metrics computed within-cohort. Rho = Spearman rank correlation between signal and next-GW total_points. Downside rate = fraction of GWs where top-ranked player returned < 4 pts. All signal values are lag-1 shifted by the state layer (no future leakage).

### Full FWD population (unfiltered baseline, replicates prior study)

| Signal    | mean_rho | std_rho | mean_top1_return | downside_rate | n_gws |
|-----------|----------|---------|-----------------|---------------|-------|
| xgi_lag1  | 0.768    | 0.052   | 4.25 pts        | 60.7%         | 28    |
| xgi_roll3 | 0.796    | 0.040   | 5.07 pts        | 64.3%         | 28    |
| xgi_roll8 | 0.785    | 0.030   | 4.21 pts        | 75.0%         | 28    |

### STABLE cohort (minutes_roll5 ≥ 60)

| Signal    | mean_rho | std_rho | mean_top1_return | downside_rate | n_gws |
|-----------|----------|---------|-----------------|---------------|-------|
| xgi_lag1  | 0.135    | 0.246   | 4.75 pts        | 50.0%         | 28    |
| xgi_roll3 | 0.176    | 0.249   | 4.89 pts        | 64.3%         | 28    |
| xgi_roll8 | 0.204    | 0.262   | 4.21 pts        | 75.0%         | 28    |

### ROTATION cohort (30 ≤ minutes_roll5 < 60)

| Signal    | mean_rho | std_rho | mean_top1_return | downside_rate | n_gws |
|-----------|----------|---------|-----------------|---------------|-------|
| xgi_lag1  | 0.361    | 0.281   | 3.63 pts        | 63.0%         | 27    |
| xgi_roll3 | 0.256    | 0.411   | 5.04 pts        | 48.1%         | 27    |
| xgi_roll8 | 0.098    | 0.252   | 2.85 pts        | 77.8%         | 27    |

### FRINGE cohort (minutes_roll5 < 30)

| Signal    | mean_rho | std_rho | mean_top1_return | downside_rate | n_gws |
|-----------|----------|---------|-----------------|---------------|-------|
| xgi_lag1  | 0.786    | 0.053   | 1.93 pts        | 82.1%         | 28    |
| xgi_roll3 | 0.783    | 0.045   | 2.00 pts        | 82.1%         | 28    |
| xgi_roll8 | 0.750    | 0.043   | 1.50 pts        | 89.3%         | 28    |

---

## 4. Cross-Cohort Differentials

`delta_stable_fringe = mean_rho[STABLE] − mean_rho[FRINGE]`

| Signal    | STABLE rho | ROTATION rho | FRINGE rho | delta_stable_fringe |
|-----------|-----------|--------------|-----------|---------------------|
| xgi_lag1  | 0.135     | 0.361        | 0.786     | **−0.651**          |
| xgi_roll3 | 0.176     | 0.256        | 0.783     | **−0.606**          |
| xgi_roll8 | 0.204     | 0.098        | 0.750     | **−0.546**          |

All three signals show the same direction: FRINGE > ROTATION > STABLE in rank correlation. The hypothesis predicted STABLE > FRINGE. The result is the structural inverse.

**delta_roll8 − delta_roll3** (horizon interaction metric):
- |−0.546 − (−0.606)| = |0.060| = **0.060**

---

## 5. Evaluation Criteria Assessment

All four pre-committed criteria evaluated against fixed thresholds. No threshold adjustment. No reinterpretation.

| Criterion | Threshold | Observed value | Met? |
|-----------|-----------|----------------|------|
| Cohort viability: STABLE ≥ 5 players in ≥ 15 GWs | 15 GWs | 28 GWs | **YES** |
| Primary differential: delta_stable_fringe (roll3) > 0.04 | > 0.04 | −0.606 | **NO** |
| Horizon-stability interaction: \|delta_roll8 − delta_roll3\| > 0.02 | > 0.02 | 0.060 | **YES** |
| Downside improvement: STABLE roll3 downside < full_fwd − 0.10 | reduction > 0.10 | 0.000 | **NO** |

**Downside improvement detail:**
- STABLE xgi_roll3 downside_rate: 0.643
- Full FWD xgi_roll3 downside_rate: 0.643
- Difference: 0.000 (identical — the STABLE cohort top-ranked player returns < 4 pts in 18 of 28 GWs, the same rate as the full-population top-ranked player)

---

## 6. Interpretation

```
interpret_results() → "stability_does_not_condition_signal"
```

Mapped to study design Section 11 ("If primary differential is not met"):

> **Finding:** Minutes stability does not materially condition rolling xGI reliability at the FWD position.
>
> **Implication:** The instability observed in the prior study is not explained by rotation noise. The signal's unreliability is structural across this season's forward population and is not correctable by population filtering.
>
> **Secondary implication:** This discourages investment in more complex stability segmentation. If the simplest single-variable conditioning does not produce a differential, more complex conditioning is unlikely to yield a proportionate return.

---

## 7. Unexpected Finding

**FRINGE cohort shows substantially higher rho than STABLE across all three signals.**

This is the "structurally surprising result" addressed in study design Section 11 ("If FRINGE cohort shows stronger rho than STABLE").

Observed: FRINGE rho (xgi_roll3) = 0.783. STABLE rho (xgi_roll3) = 0.176.

Within the FRINGE cohort, xGI signals rank players well (rho ≈ 0.78). However, the practical consequence is different from what rho alone implies: the top-ranked FRINGE forward returns only 2.00 pts on average (82.1% downside rate). The signal ranks fringe forwards correctly — but the top-ranked fringe forward rarely plays enough to score meaningful points.

**Plausible mechanism (per study design):** Forwards who average < 30 min/GW accumulate xGI only during specific deployments. When they are deployed, they tend to play against weak defences or in high-scoring matches — conditions managers select for specifically. This managerial selection bias means that within the fringe sub-population, high-xGI players are disproportionately those in favourable deployment conditions. The within-cohort rank order is informative, but the signal cannot tell you whether the top-ranked fringe player will play at all next GW.

For STABLE forwards (60+ min/GW), xGI ranks players along a dimension that is less predictive of next-GW points variance within this sub-population. Among consistent starters, points variance is driven by match-specific outcome noise (goal opportunities converted vs. not, clean sheets, bonus) that xGI does not capture.

**This unexpected finding must be flagged for confirmation in future seasons.** It should not be acted on without replication.

---

## 8. Bounded Conclusion

Minutes stability (as measured by `minutes_roll5`) does **not** condition the within-cohort rank correlation of rolling xGI signals for forwards in 2024-25.

Specifically:
- The primary differential (STABLE rho − FRINGE rho for xgi_roll3) is −0.606, strongly negative, meaning STABLE forwards are ranked **less well** by xgi_roll3 than FRINGE forwards — the opposite of the hypothesis.
- The FRINGE cohort has high within-cohort rho but catastrophically low actual returns (top-ranked forward averages 2.0 pts, 82% downside rate).
- The STABLE cohort has low within-cohort rho (0.176) and captain-quality returns similar to the full population (mean_top1_return 4.89 pts, 64% downside rate).
- The horizon-stability interaction criterion is met (0.060 > 0.02), but this is in the direction of roll8 outperforming roll3 slightly among stable players — not operationally meaningful given the low absolute rho values.

**The motivating hypothesis is rejected.** Minutes filtering does not improve the operational usefulness of rolling xGI signals for captain ranking.

---

## 9. Unsupported Claims

Per study design Section 12, the following claims are NOT supported by this study:

- "Minutes-stable forwards score more points." (This study evaluated signal rank correlation within cohorts, not cross-cohort outcome distributions. Cross-cohort point means are confounded by population size and selection effects.)

- "The stability filter improves captain selection." (This is a descriptive study. No captaincy simulation was run. The STABLE cohort downside rate (64%) equals the full-population downside rate.)

- "xgi_roll8 should replace xgi_roll3 for stable forwards." (Signal status cannot be changed based on a sub-population analysis alone. Registry change requires a full lens study. The roll8 advantage among STABLE players is small and rho is low in absolute terms.)

- "Unstable forwards should be excluded from transfer consideration." (Transfer evaluation is out of scope. The FRINGE high-rho finding has no direct transfer implication.)

- "The STABLE threshold should be 70 minutes, not 60." (Post-hoc threshold adjustment is not permitted. The 60-min threshold is fixed a priori.)

- "The FRINGE high-rho finding is a tradeable signal." (The top-ranked FRINGE forward returns 2.0 pts on average with 82% downside. High within-cohort rank correlation does not imply captain-worthiness when absolute returns are this low.)

---

## 10. Registry Update

**Primary differential criterion: NOT met** (delta = −0.606, threshold = +0.04).

Per study design Section 15 ("Registry Update — conditional"):

> If (and only if) the primary differential condition is met, then update SIGNAL_REGISTRY.md.

**No update to SIGNAL_REGISTRY.md is made.** The signal remains in its current registry state. The conditional annotation ("conditionally informative for STABLE players") is not warranted because stability conditioning did not improve signal usefulness for that cohort.

---

## 11. Validation Checklist

| Validation requirement | Status |
|------------------------|--------|
| All 31 unit tests pass | PASS |
| Cohort assignment is deterministic | PASS — `_assign_stability_cohort` is pure function with fixed constants |
| No future leakage | PASS — `assert_no_future_leakage` checked for all 28 eval GWs; all rolling features confirmed from state layer |
| Population accounting closure | PASS — `n_stable + n_rotation + n_fringe + n_unknown == n_all_fwd` for all 28 GWs |
| minutes_roll5 coverage ≥ 80% | PASS — 92.7% coverage (190 UNKNOWN rows excluded from cohort analysis, logged) |
| Reproducibility | PASS — identical results on consecutive calls (no random state) |
| Result structure complete | PASS — all 8 required keys present |
| No post-hoc threshold adjustment | PASS — thresholds locked a priori in module constants |
| No silent row filtering | PASS — UNKNOWN rows logged; all rows accounted in population accounting |

---

## 12. Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Results document | `docs/studies/results/minstab-01-results.md` | This file |
| Per-row detail CSV | `outputs/minstab_01_detail.csv` | Written (2,604 rows) |
| SIGNAL_REGISTRY update | `signals/registry/SIGNAL_REGISTRY.md` | Not updated (criterion not met) |

---

## 13. Related Documents

- [minutes-stability-xgi-study.md](../archive/minutes-stability-xgi-study.md) — design document
- [rolling-xgi-horizon-study-results.md](rolling-xgi-horizon-study-results.md) — prior study (motivating context)
- [rolling-xgi-real-validation.md](rolling-xgi-real-validation.md) — real-data validation referenced in design
- `evaluation/minutes_stability_study.py` — study execution module
- `tests/test_minutes_stability_study.py` — 31 validation tests
