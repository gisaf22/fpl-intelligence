# Study: Minutes Stability × Rolling xGI Conditional Robustness

**Status:** COMPLETE — executed 2026-05-19; results in results/minstab-01-results.md
**Study ID:** STUDY-MINSTAB-01
**Study type:** Conditional robustness study
**Prior study:** [rolling-xgi-horizon-study.md](rolling-xgi-horizon-study.md)
**Last reviewed:** 2026-05-19

---

## 1. Research Question

> Under what conditions do rolling xGI signals appear useful for forwards —
> and when do they fail?
>
> Specifically: does minutes stability condition the usefulness of rolling xGI
> signals more strongly than the player's involvement quality itself?

---

## 2. Operational Motivation

The rolling-xGI horizon study found on real 2024-25 data:

- Positive lift from rolling windows over lag1 replicated (+0.063 for roll3)
- But real-data downside rate was 64% for xgi_roll3 (top-ranked FWD returns < 4
  points in nearly 2 of 3 GWs)
- Real-data rho instability was high (std_rho ≈ 0.25 vs 0.12 synthetic)
- Signal remains `candidate` with stability flag — not advancing to `validated`

**Motivating hypothesis:** The instability and high downside rate may partially
reflect including minutes-unstable players in the FWD evaluation population. When
a player is on the fringe of the starting XI, their rolling xGI encodes rotation
risk, not production quality. Conditioning on minutes stability may reveal that the
signal is operationally useful for consistent starters but unreliable for rotation
candidates.

This is not a search for a better signal. It is a diagnostic study of when the
existing signal works and when it does not.

---

## 3. Bounded Hypothesis

**Primary hypothesis:**
Rolling xGI signals (xgi_roll3, xgi_roll8) show materially stronger rank
correlation with next-GW total_points for minutes-stable forwards (averaging >= 60
min/GW over 5 GWs) than for minutes-unstable forwards (< 30 min/GW average).

**Mechanism hypothesis:**
Minutes instability introduces two confounds into rolling xGI:

1. **Sparse window problem** — rolling averages computed over partial playing time
   underrepresent the player's production rate per 90. A player who plays 30 min
   in three consecutive GWs accumulates low xGI not because of poor form but
   because of insufficient exposure.

2. **Selection noise** — rotation players play when managers select them, often
   against specific opponents or in specific game states. Their xGI conflates
   managerial selection intent with player quality. This makes xGI a noisy predictor
   of whether they will play the following week, let alone how many points they
   will score.

**What this study does NOT hypothesize:**

- That minutes-stable forwards score more points on average
- That minutes stability is a useful signal in its own right
- That conditioned signals should enter synthesis
- That the current captain or transfer heuristics should change

---

## 4. Stability Segmentation Design

### Segmentation variable

`minutes_roll5` — 5-GW rolling mean minutes per gameweek, computed by the DAL
state layer with lag-1 shift applied.

At row (player_id, gw=N): `minutes_roll5` encodes mean(minutes[N-5 : N-1]).
GW N's minutes are never used in the feature — temporal integrity is guaranteed
by the state layer.

### Why `minutes_roll5`

- 5-GW window captures medium-term availability (not single-match noise)
- Already computed in the state layer — no new feature engineering required
- Operationally interpretable: average minutes per game over the past 5 games
- Not game-state sensitive: reflects genuine starting probability, not garbage-time
  minutes or single-match anomalies
- Longer than roll3 (avoids reacting to a single injury absence); shorter than
  roll8 (avoids smoothing out genuine mid-season role changes)

### Cohort definitions

| Cohort | Label | Criterion | Football interpretation |
|--------|-------|-----------|------------------------|
| HIGH | `STABLE` | `minutes_roll5 >= 60` | Near-regular starter: averaging 60+ min/GW. Expected to start most weeks. |
| MID | `ROTATION` | `30 <= minutes_roll5 < 60` | Rotation player: averaging 30-60 min/GW. Selected situationally. |
| LOW | `FRINGE` | `minutes_roll5 < 30` | Fringe/returning: averaging < 30 min/GW. Unreliable playing time. |
| N/A | `UNKNOWN` | `minutes_roll5 is NULL` | Excluded from cohort analysis. Logged in population accounting. |

### Threshold rationale

**60 min threshold** — Standard FPL eligibility threshold for "meaningful playing
time". A player averaging 60+ min/GW over five games is reliably starting. Below
this, playing time is conditionally dependent on opponent, game state, or manager
rotation decisions that are not captured in the xGI signal.

**30 min threshold** — Below 30 min/GW average, a player is unlikely to be
regularly in the starting XI. Appearances at this level are typically as a
substitute with insufficient time to accumulate meaningful xGI. Rolling averages
at this exposure level reflect sample size rather than production quality.

These thresholds are fixed a priori. They are not revised based on observed
distributions. Any post-hoc threshold adjustment would constitute optimization
and is explicitly prohibited by research governance.

### Leakage protections

1. `minutes_roll5` at row (player_id, gw=N) uses minutes from GWs N-5 to N-1
   only — the state layer enforces this via `.shift(1).rolling(5, min_periods=1).mean()`.
2. Cohort assignment is determined at evaluation time using only pre-GW information.
3. No cohort assignment uses `total_points` or any outcome variable.
4. Cohort boundary thresholds are fixed constants — no optimization or iteration.

### Temporal alignment (per evaluation GW)

```
GW N-5  GW N-4  GW N-3  GW N-2  GW N-1 │ GW N  (outcome)
min     min     min     min     min    │ total_points
                                       │
minutes_roll5 at GW N ─────────────────┘ → cohort assignment
xgi_roll3 at GW N = mean(xgi[N-3:N-1]) ─┘ → signal ranking
                                              ↑
                              all features produced by state layer
                              with lag-1 shift — never see GW N
```

---

## 5. Study Scope

### In scope

- FWD position only (GW 6–33 inclusive)
- All three stability cohorts evaluated in parallel
- Signals: `xgi_lag1`, `xgi_roll3`, `xgi_roll8`
- Cross-cohort differential analysis
- Downside rate comparison within and across cohorts

### Explicitly excluded

- MID, DEF, GKP positions
- DGW-specific analysis (DGW rows included but not separated as primary)
- Hypothesis testing or p-values
- Bootstrap confidence intervals
- Cohort threshold optimisation (thresholds are fixed a priori)
- Multi-dimensional segmentation (minutes × fixture difficulty, etc.)
- Signal combination across cohorts
- Any prescriptive output or heuristic change recommendation

### Why `xgi_roll5` is excluded from this study

The prior study found roll5 was the weakest on captain quality metrics on both
synthetic and real data (lowest top-1 return on both). Roll3 and roll8 represent
the key short-horizon vs long-horizon contrast. Including roll5 adds noise without
adding diagnostic clarity to the conditioning question.

---

## 6. Evaluation Design

### Metrics (per cohort, per signal)

| Metric | Source | Interpretation |
|--------|--------|---------------|
| `mean_rho` | `rank_correlation()` | Average Spearman rank correlation per GW |
| `std_rho` | — | Consistency of rho across GWs |
| `mean_top1_return` | `top1_return()` | Mean actual points of top-ranked FWD per GW |
| `downside_rate` | `downside_rate(threshold=4.0)` | Fraction of GWs where top-ranked FWD returned < 4 pts |

All metric functions from `evaluation/metrics.py`.

### Cross-cohort differential metrics

For each signal (roll3, roll8):

- `delta_stable_fringe = mean_rho[STABLE] - mean_rho[FRINGE]`
- `delta_roll8_vs_roll3[cohort] = mean_rho[roll8] - mean_rho[roll3]` per cohort

The horizon-stability interaction tests whether longer windows (roll8) benefit more
from stability conditioning than shorter windows (roll3). If longer windows require
more stable minutes to be useful, this has implications for window choice by player
type.

### Pre-committed success criteria (locked before execution)

These criteria are written before any code runs. They cannot be revised after
results are observed.

| Criterion | Threshold | Interpretation if met |
|-----------|-----------|----------------------|
| Cohort viability | STABLE cohort: >= 5 players in >= 15 GWs | STABLE has sufficient sample to interpret |
| Primary differential | `delta_stable_fringe (roll3) > 0.04` | Stability conditions roll3 signal usefulness |
| Horizon-stability interaction | `\|delta_roll8 - delta_roll3\| > 0.02` | Long vs short horizons respond differently to stability |
| Downside improvement | `downside_rate[STABLE, roll3] < full_fwd_downside - 0.10` | Stability filtering meaningfully reduces captain downside |

### Pre-committed failure criteria

| Failure condition | Interpretation |
|-------------------|---------------|
| STABLE cohort viable in < 10 GWs | Insufficient sample — result not interpretable; inspect minutes distribution |
| `delta_stable_fringe (roll3) <= 0` | Stability does not improve signal reliability; hypothesis rejected |
| All cohort rho values within 0.03 | Flat conditioning response — stability has no detectable effect |

---

## 7. Comparison Structure

```
ALL FWD (GW 6–33) — full-population baseline
│
├── STABLE   (minutes_roll5 >= 60)
│   ├── xgi_lag1  → rho, std_rho, top1_return, downside_rate
│   ├── xgi_roll3 → rho, std_rho, top1_return, downside_rate
│   └── xgi_roll8 → rho, std_rho, top1_return, downside_rate
│
├── ROTATION (30 <= minutes_roll5 < 60)
│   └── [same three signals]
│
└── FRINGE   (minutes_roll5 < 30)
    └── [same three signals]
```

The full-FWD baseline replicates the prior study's evaluation (without the
minutes_roll3 >= 60 filter used there). Differences between full-FWD and STABLE
cohort results indicate how much of the prior study's signal weakness was driven
by population composition.

---

## 8. Population Accounting

Every GW in the evaluation window produces one population accounting row:

| Column | Content |
|--------|---------|
| `gw` | Gameweek number |
| `n_all_fwd` | All FWD rows for this GW |
| `n_stable` | Forwards assigned to STABLE |
| `n_rotation` | Forwards assigned to ROTATION |
| `n_fringe` | Forwards assigned to FRINGE |
| `n_unknown` | Forwards with missing `minutes_roll5` |

Invariant: `n_stable + n_rotation + n_fringe + n_unknown == n_all_fwd` for every GW.

This table is part of the study output (`detail` DataFrame) and is checked by
the validation test suite before any result is interpreted.

---

## 9. Validation Requirements

Before any result is interpreted, all of the following must pass:

1. **No temporal leakage** — `assert_no_future_leakage()` passes for every
   evaluation GW (structural check on state layer columns).

2. **Cohort assignment determinism** — same `minutes_roll5` value always produces
   the same cohort label. Verified by unit tests on `_assign_stability_cohort`.

3. **Population accounting closure** — `n_stable + n_rotation + n_fringe + n_unknown
   == n_all_fwd` for every GW in `detail`.

4. **Rolling window coverage** — `minutes_roll5` available for >= 80% of FWD rows
   in GW 6–33. If not, the state layer has a data quality issue to resolve first.

5. **Reproducibility** — same input DataFrame produces identical results on two
   consecutive calls (no random state).

6. **Result structure** — output dict contains all required keys (`eval_gws`,
   `gw_count`, `cohort_gw_counts`, `cohorts`, `full_fwd`, `differential`,
   `threshold_assessment`, `detail`).

---

## 10. Known Limitations

1. **Single season.** 2024-25 only. Results describe one season's FWD population —
   not generalisable without replication.

2. **FWD position only.** Rotation dynamics differ by position. MID rotation players
   may show different patterns. Separate study required if warranted by these findings.

3. **No fixture conditioning.** A STABLE forward in a difficult fixture may behave
   differently than in an easy one. Fixture difficulty is not controlled here. The
   LENS-AVAIL study addresses availability × fixture conditioning separately.

4. **minutes_roll5 as stability proxy.** Average minutes is a blunt instrument. A
   player who plays 90 min in one GW and 0 min in the next averages 45 min/GW and
   lands in ROTATION. In terms of prediction utility, they are FRINGE. This
   limitation is documented and not corrected — correcting it would require variance-
   based features not currently in the state layer, and adding them would violate
   the feature scope constraint.

5. **Small FRINGE population.** Few FWD players average < 30 min/GW in the
   evaluation window — they are typically benched entirely or not in the squad.
   FRINGE rho estimates may be based on very small per-GW populations (< 5 players)
   in many GWs. Results for this cohort are directionally interpretable only.

6. **No sub-frequency signal.** Whether a player typically starts or comes on as a
   substitute is not captured by `minutes_roll5` alone. A player who consistently
   starts and plays 70 min looks identical to one who consistently comes on for the
   final 70 min. This ambiguity exists in the current feature set and is not
   resolved here.

---

## 11. Operational Interpretation Guidance

### If primary differential is met (`delta_stable_fringe > 0.04`)

**Finding:** Minutes stability conditions rolling xGI usefulness for forwards.

**Implication for captain ranking:** The 64% downside rate observed in the prior
full-FWD study is partially attributable to including rotation and fringe forwards
in the ranking population. An operational filter on `minutes_roll5 >= 60` should
be considered when constructing the captain candidate pool — not as a new signal,
but as a population gate before the existing signal is applied.

This does not change the heuristic weight — it changes who is eligible to be
ranked by the signal.

**What this does not support:** Removing all rotation forwards from transfer
consideration. Transfer decisions involve expected minutes as a forward-looking
factor; this study is purely retrospective.

### If primary differential is not met (`delta_stable_fringe <= 0.04`)

**Finding:** Minutes stability does not materially condition rolling xGI
reliability at the FWD position.

**Implication:** The instability observed in the prior study is not explained by
rotation noise. The signal's unreliability is structural across this season's
forward population and is not correctable by population filtering.

**Secondary implication:** This discourages investment in more complex stability
segmentation. If the simplest single-variable conditioning does not produce a
differential, more complex conditioning is unlikely to yield a proportionate return.

### If FRINGE cohort shows stronger rho than STABLE

**Interpretation:** A structurally surprising result. Possible explanation: rotation
players who do appear are selected by managers in matchups where they are expected
to contribute — a form of managerial selection bias that inflates xGI predictiveness
for this subgroup. This should be reported as an unexpected finding and flagged for
confirmation in future seasons. It should not be acted on without confirmation.

### If ROTATION cohort shows the highest downside rate

**Interpretation:** Expected and consistent with the mechanism hypothesis. Rotation
players have the highest uncertainty in both playing time and production quality when
they do play. If the downside rate is highest in ROTATION, this supports the
segmentation design — the cohort captures a genuine risk tier.

---

## 12. Unsupported Claims

The following claims are NOT supported by this study regardless of outcome:

- "Minutes-stable forwards score more points." (This study evaluates signal
  usefulness within cohorts, not cross-cohort outcome distributions.)
- "The stability filter improves captain selection." (Descriptive study — not a
  captaincy simulation. A separate experiment would be required to make that claim.)
- "xgi_roll8 should replace xgi_roll3 for stable forwards." (Signal status cannot
  be changed based on a sub-population analysis alone. Registry change requires a
  full lens study.)
- "Unstable forwards should be excluded from transfer consideration." (Transfer
  evaluation is out of scope. Minutes stability has different implications for
  transfers than for captain selection.)
- "The STABLE threshold should be 70 minutes, not 60." (Post-hoc threshold
  adjustment is not permitted. The 60 min threshold is fixed a priori.)

---

## 13. Failure Interpretation

A study is a failure if it cannot produce an interpretable result — not if it
produces a negative result. A negative result is a valid finding.

**Cohort size failure:** If the STABLE cohort is viable in fewer than 10 GWs,
the population is too sparse for cohort analysis. Inspect the `minutes_roll5`
distribution across GW 6–33 before concluding the study cannot run — the prior
EDA established approximately 49 FWDs in the evaluation population, and most
should have `minutes_roll5 >= 60`.

**All-UNKNOWN failure:** If `minutes_roll5` is missing for > 20% of FWD rows in
the evaluation window, the state layer has a data quality issue. Resolve before
proceeding.

**Both failures indicate a data or implementation problem, not a research finding.**

---

## 14. Study Execution Architecture

### Directory structure

```
evaluation/
    minutes_stability_study.py      ← study execution module

tests/
    test_minutes_stability_study.py ← validation tests

docs/studies/
    minutes-stability-xgi-study.md  ← this document (design)
    results/
        minstab-01-results.md       ← written after execution (not yet)

outputs/
    minstab_01_detail.csv           ← written after execution (not yet)
```

### Execution flow

```
1. Load features via get_state_features(get_curated_spine(db_path))
2. Call evaluate_minutes_stability_conditioning(features)
3. Inspect threshold_assessment — all criteria have explicit met: bool
4. Call interpret_results(results) → canonical interpretation string
5. Save results["detail"] to outputs/minstab_01_detail.csv
6. Write docs/studies/results/minstab-01-results.md
7. Update SIGNAL_REGISTRY.md with conditional status if warranted
```

### Study lifecycle

```
DESIGN LOCKED  →  VALIDATION PASS  →  EXECUTION  →  RESULTS WRITTEN  →  REGISTRY UPDATED
2026-05-19         tests all pass     run module     minstab-01-results.md   SIGNAL_REGISTRY.md
```

### Config structure

There is no external config file. All study parameters are constants in
`evaluation/minutes_stability_study.py`:

```python
_STABLE_THRESHOLD   = 60.0   # minutes_roll5 >= 60 → STABLE
_ROTATION_THRESHOLD = 30.0   # minutes_roll5 >= 30 → ROTATION; < 30 → FRINGE
_MIN_GW             = 6
_MAX_GW             = 33
_DOWNSIDE_THRESHOLD = 4.0    # captain outcome below this is "damaging"
```

No YAML, no JSON, no CLI arguments. Constants are in the module and reviewable
without tooling.

---

## 15. Expected Artifacts

| Artifact | Path | Produced by |
|----------|------|-------------|
| Design document | `docs/studies/minutes-stability-xgi-study.md` | This document |
| Study module | `evaluation/minutes_stability_study.py` | Implementation |
| Validation tests | `tests/test_minutes_stability_study.py` | Test suite |
| Results document | `docs/studies/results/minstab-01-results.md` | Written after execution |
| Per-GW detail CSV | `outputs/minstab_01_detail.csv` | Saved after execution |

---

## 16. Recommended Implementation Order

1. This design document (complete — written before code)
2. `evaluation/minutes_stability_study.py` — study execution module
3. `tests/test_minutes_stability_study.py` — validation tests
4. Run tests: all must pass before any execution against real data
5. Execute study against real spine: `get_state_features(get_curated_spine(db_path))`
6. Write `docs/studies/results/minstab-01-results.md`
7. Update `SIGNAL_REGISTRY.md` with conditional status if warranted

---

## 17. Anti-patterns to Avoid

| Anti-pattern | Why excluded |
|--------------|-------------|
| Optimizing cohort thresholds (60/30) post-hoc | Constitutes overfitting — thresholds are fixed a priori |
| Adding `xgi_roll5` to the signal set | roll5 showed weakest captain quality in prior study; inclusion adds noise |
| Multi-dimensional cohorts (minutes × FDR) | Combinatorial explosion; each sub-population becomes too small |
| Bootstrap CIs per cohort | Out of scope for this conditional study phase |
| Comparing cross-cohort point returns | Confounds position-tier effects with signal effects |
| Writing results before tests pass | Temporal validity is a prerequisite, not an assumption |
| Adjusting thresholds after seeing results | Explicitly prohibited by EVAL_DESIGN.md Section 13 |
| Adding ML-derived stability scores | Prohibited by research governance (NO ML constraint) |

---

## 18. Success Criteria

The study is considered successfully completed when:

1. All validation tests pass (`tests/test_minutes_stability_study.py`)
2. Execution completes without error on real spine data
3. Each threshold criterion has a definitive `met: True` or `met: False` value
4. `interpret_results()` returns a canonical string (not `insufficient_data`)
5. `docs/studies/results/minstab-01-results.md` is written with all four threshold
   assessments reported, regardless of direction
6. SIGNAL_REGISTRY.md is updated to reflect the study's conditional finding

**A negative result (stability does not condition signal) is a valid success.**
The study succeeds by being executed correctly and interpreted honestly.

---

## 19. Related Documents

- [rolling-xgi-horizon-study.md](rolling-xgi-horizon-study.md) — prior study; motivates this one
- [EVAL_DESIGN.md](../../signals/evaluation/EVAL_DESIGN.md) — evaluation framework and governance
- [adr/004-analytical-foundations.md](../adr/004-analytical-foundations.md) — population and method decisions
- [adr/005-signal-exclusions.md](../adr/005-signal-exclusions.md) — structural xGI exclusions
- `signals/lenses/avail/LENS_DESIGN.md` — availability lens (separate study; related topic)
