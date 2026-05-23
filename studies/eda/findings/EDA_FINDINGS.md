# EDA Findings — Gate Decisions for Lens Studies

**Type:** Synthesis document — required by EVAL_DESIGN.md §4.1 before any lens study may run  
**Status:** COMPLETE  
**Produced:** 2026-05-22  
**Source data:** `studies/eda/findings/eda_02_*.csv` through `eda_07_*.csv`  
**Authoritative for:** All design decisions in `LENS_DESIGN.md` that reference an EDA finding

---

## How to use this document

Each gate decision is assigned a reference ID (`G-EDA{N}-{NN}`) that `LENS_DESIGN.md` cites
to justify its choices. If a design decision in a lens study cannot reference an ID from this
document or provide an explicit a priori rationale, it is not permitted.

---

## EDA-0 — Lag alignment and leakage check

**Status:** Verified by DAL contract. No EDA notebook was run for this layer — the lag
alignment guarantee is enforced structurally.

**Finding:** The DAL state layer enforces lag-1 minimum for all derived features. The
`STATE_CONTRACT.md` specifies that `xgi_roll3` at GW N reflects GWs N-3 through N-1
(not N-2 through N). Rolling window signals use `.shift(1)` before `.rolling()` application.
No future data leaks into any row of the spine.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA0-01 | Lag-1 alignment: signal at GW N predicts target at GW N+1. All lens studies must align predictor and target with this shift. |
| G-EDA0-02 | Rolling window warmup: GW 1-2 must be excluded from lens study windows. Rolling features are undefined or unreliable for these rows. |
| G-EDA0-03 | The DAL contract is the authoritative source for lag alignment. Lens study code must verify alignment via an assertion before any correlation runs. |

---

## EDA-1 — Target distribution and analytical method

**Status:** Locked in ADR-004 (`docs/adr/004-analytical-foundations.md`)

**Finding:** `total_points` is right-skewed across all positions (overall skew=1.58,
kurtosis=2.80). The distribution violates the normality assumption required for Pearson
correlation. Spearman rank correlation is justified at STRONG_EVIDENCE level.

**GW bounds:** Analysis uses GW 6-33 inclusive. GW 34 is excluded (only 14 of 20 teams
had a fixture — an unequal exposure slice). GW 31 (16 teams) is included because the
reduction is not systematic.

**Population:** Primary population is player-GW records with `minutes >= 60`. This filters
out non-participants and BGW rows (BGW rows have null minutes and are excluded naturally).
GW 1-5 are included in the primary dataset but lens studies may impose a tighter lower bound
due to rolling window warmup (see G-EDA0-02).

**DGW treatment:** Double gameweek rows must be flagged. DGW raw mean = 6.50 vs SGW 3.83
(+70%). Per-fixture normalised: DGW = 3.25 vs SGW = 3.83. Pooling DGW and SGW records
without an indicator is not permitted.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA1-01 | Use Spearman rank correlation throughout all lens studies and registry rho calculations. Pearson is not appropriate. |
| G-EDA1-02 | GW bounds: GW 6 to GW 33 inclusive for population construction. GW 34 excluded. |
| G-EDA1-03 | Lens study GW lower bound: GW 3 minimum due to rolling window warmup (GW 1-2 excluded per G-EDA0-02). |
| G-EDA1-04 | Primary population: `minutes >= 60` per player-GW record. |
| G-EDA1-05 | DGW rows must be explicitly flagged or excluded. Pooling DGW and SGW without accounting for the fixture multiplier is not permitted. |

---

## EDA-2 — Signal space and structural exclusions

**Status:** Locked in ADR-005 (`docs/adr/005-signal-exclusions.md`)

**Finding:** 15 signal-position pairs are structurally excluded from association analysis.
These are not data quality issues — they are structural: the signal cannot vary for that
position by construction, or the event is too rare to form a usable distribution.

The EDA characterised **29 base signals × 4 positions = 116 rows**. Of these:

- **9 eligible** — `downstream_status = eligible`
- **83 caveated** — `downstream_status = caveated`
- **24 blocked** — `downstream_status = blocked` (includes the 15 structural exclusions)

**Structurally excluded pairs (registry: `relationship_geometry = unassessable`,
`downstream_status = blocked`):**

| Signal | Position | Reason |
|---|---|---|
| `goals_scored` | GK | Structural zero. Goalkeepers do not score (std=0). |
| `saves` | DEF, MID, FWD | GK-only stat. Constant zero for outfield players. |
| `assists` | GK | Unassessable. Goalkeepers effectively never register assists. |
| `red_cards` | ALL | Event too rare to form a usable distribution at GW grain. |
| `starts` | FWD, GK | Unassessable. |
| `threat` | DEF, GK | Blocked — insufficient within-position variation. |
| `fixture_count` | FWD, GK | Unassessable. |
| `xa` | DEF, FWD | Insufficient data — blocked. |
| `xg` | DEF, GK, MID | Insufficient data — blocked. |
| `minutes` | ALL | Blocked as eligibility/access signal (not a quality signal). |

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA2-01 | The 24 blocked signal-position pairs are permanently excluded. No lens study may test an association for a blocked pair. |
| G-EDA2-02 | `minutes` is blocked as a quality signal across all positions. It characterises availability, not form. Any minutes-based signal belongs in LENS-AVAIL, not LENS-FORM. |
| G-EDA2-03 | `goals_scored` GK, `saves` DEF/MID/FWD, `assists` GK are structurally zero and are not candidates for rolling window analysis at any position. |

---

## EDA-3 — Joint registry: signal characterisation

**Status:** Primary evidence base. Source: `eda_03_joint_registry.csv` (116 rows).

### 3.1 Population and grain

All 116 rows use `preferred_population = both` — no signal required a population restriction
beyond the primary `minutes >= 60` filter. Population choice does not affect the preferred
analytical population for any signal.

Position sample sizes (records across GW 6-33, primary population):

| Position | N records | N players |
|---|---|---|
| DEF | ~2,213 | 162 |
| MID | ~2,410 | 192 |
| FWD | ~557 | 49 |
| GK | ~553 | 35 |

FWD and GK sub-populations are small. Signals with `insufficient_data` temporal stability
in these positions are structurally expected to be unresolvable by the EDA.

### 3.2 Association class distribution

- `continuous_monotonic` — strong, consistent rank ordering across the range
- `weak_association` — rank correlation present but not monotonically ordered
- `upper_tail_concentrated` — association driven primarily by high-scoring observations
- `unassessable` — structurally zero or insufficient variation

### 3.3 Panel decomposition

55/116 rows are `state_sensitive` — the within-player variation drives the pooled rho.
This confirms that temporal signal variation (game-to-game) is a primary source of
information, not just cross-sectional player quality differences.

51/116 are `indeterminate` — the decomposition could not resolve between state and
identity effects. 3/116 are `identity_dominant` (xgi GK, starts MID, starts DEF).

### 3.4 Key rho values — form-proxy signals

| Signal | Position | rho_pooled | Temporal stability | Downstream | Promotion |
|---|---|---|---|---|---|
| xgi | MID | 0.31 | stable | caveated | review_signal |
| xgi | FWD | 0.50 | insufficient_data | caveated | review_signal |
| xgi | DEF | 0.16 | insufficient_data | caveated | review_signal |
| xgi | GK | −0.03 | insufficient_data | caveated | review_signal |
| goals_scored | DEF | 0.32 | stable | eligible | core_signal |
| goals_scored | MID | 0.58 | stable | caveated | review_signal |
| goals_scored | FWD | 0.85 | stable | caveated | review_signal |
| assists | MID | 0.49 | stable | eligible | core_signal |
| assists | FWD | 0.36 | stable | eligible | core_signal |
| assists | DEF | 0.27 | moderate_shift | eligible | review_signal |
| creativity | MID | 0.19 | stable | eligible | core_signal |
| ict_index | DEF | 0.31 | stable | eligible | core_signal |
| ict_index | MID | 0.53 | stable | caveated | review_signal |
| ict_index | FWD | 0.73 | stable | caveated | review_signal |
| minutes | ALL | 0.11–0.20 | insufficient_data | blocked | — |

**Why goals_scored FWD/MID is caveated despite high rho:** `goals_scored` is a sparse event
signal. High pooled rho reflects the impact of haul observations (5-goal scores inflate the
relationship). The `caveated` classification reflects the concentration risk, not that the
association is absent.

**Why xgi FWD is caveated despite rho=0.50:** Temporal stability is `insufficient_data` —
the within-half block analysis could not confirm cross-season consistency for FWD xgi.

### 3.5 Rho decomposition implications for rolling windows

`goals_scored`, `assists`, and `xgi` are all `state_sensitive` or `indeterminate`. The
within-player variation contributes meaningfully to pooled rho. This is the structural basis
for expecting that rolling window smoothing of these signals (reducing game-to-game noise)
may improve predictive power over raw lag-1 values. LENS-FORM tests this hypothesis directly.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA3-01 | xgi is a caveated review_signal for MID (rho 0.31, stable). It is the primary candidate for rolling window testing in LENS-FORM. |
| G-EDA3-02 | xgi FWD (rho 0.50) is a candidate but temporal stability is insufficient_data. LENS-FORM must confirm or classify as conditional. |
| G-EDA3-03 | goals_scored DEF is a core_signal (rho 0.32, stable). Its rolling window variant is a valid LENS-FORM candidate. |
| G-EDA3-04 | assists MID and FWD are core_signals (rho 0.49, 0.36, stable). They are established baselines — not the primary LENS-FORM focus, but context for interpreting xgi rolling windows. |
| G-EDA3-05 | The caveated classification for goals_scored FWD/MID reflects event sparsity and haul concentration risk, not absence of association. Rolling window smoothing reduces haul concentration sensitivity — this must be tested explicitly. |
| G-EDA3-06 | minutes is blocked across all positions and must not appear as a form signal candidate. |

---

## EDA-4 — Population validity

**Status:** Complete. Source: `eda_04_population_validity.csv` (116 rows) and
`eda_04_dual_rho_bounds.csv` (118 rows).

**Finding:** `rho_primary` = `rho_minimal` for all 110 tested signal-position pairs
(`delta_rho = 0` throughout). Population filter choice does not materially affect any rho
value in this dataset.

- 110/116 signal-position pairs: `population_robustness = stable`
- 6/116: `population_robustness = untested` (rho was NaN — structurally zero or unassessable)

**Implication for LENS-FORM:** The `minutes >= 60` filter can be applied consistently across
all positions without risk that it distorts the association relative to a more permissive
filter. No position-specific population override is required by EDA evidence.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA4-01 | Use `minutes >= 60` as the uniform qualified-start threshold across all positions. No position-specific threshold is warranted by EDA-4 evidence. |
| G-EDA4-02 | Population robustness is confirmed — rho values are stable across primary and minimal population definitions. |

---

## EDA-5 — Signal stability (GW block structure)

**Status:** Complete. Source: `eda_05_signal_stability.csv` (232 rows),
`eda_03_temporal_stability.csv` (107 rows).

**Finding:** The EDA used a two-block structure: `first_half` (GW 1-17) and `second_half`
(GW 18-38). This is coarser than the three-block structure LENS-FORM requires.

**Temporal stability classification (EDA-03 joint registry, 116 rows):**

| Classification | Count | Meaning |
|---|---|---|
| stable | 28 | Q5-Q1 gap consistent across both halves |
| insufficient_data | 76 | Block sample too small to assess — common for sparse event signals |
| unassessable | 10 | Structurally zero in both blocks |
| moderate_shift | 2 | Notable shift between halves (assists DEF, goals_conceded MID) |

**76/116 rows have `insufficient_data` temporal stability.** This is expected given:
- Sparse event signals (goals_scored, assists, red_cards) have near-zero median within any 17-GW block
- FWD (n=49) and GK (n=35) sub-populations produce small block samples
- The two-block cut at GW 17/18 is not calibrated to the signals' information density

**Stable temporal signals relevant to form:**

| Signal | Position | Block gap (pooled) |
|---|---|---|
| xgi | MID | 3.90 (stable) |
| xgi | FWD | 5.12 (stable) |
| goals_scored | DEF | 14.75 (stable) |
| goals_scored | MID | 14.08 (stable) |
| goals_scored | FWD | 11.36 (stable) |
| assists | MID | 8.13 (stable) |
| creativity | MID | 3.08 (stable) |

**Signals with insufficient_data stability:**

- xgi DEF, xgi GK: block sample too small
- assists DEF: moderate_shift (gap 5.21 early vs 11.39 late — seasonal shift in DEF assists)
- xa (all positions): insufficient_data

**GW block structure mismatch:** The EDA two-block structure (GW 1-17 / GW 18-38) is
not the same as the LENS-FORM three-block structure (early GW 3-12 / mid GW 13-26 /
late GW 27-38). Temporal stability evidence from EDA-5 provides a floor-level check
only. LENS-FORM block stability analysis is independent and more granular.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA5-01 | EDA temporal stability used a two-block structure (GW 1-17 / GW 18-38). LENS-FORM must define its own three-block structure — this is not derivable from EDA-5. |
| G-EDA5-02 | 76/116 signals have insufficient_data temporal stability. This is a structural feature of sparse event signals and small positional sub-populations, not a data quality failure. |
| G-EDA5-03 | xgi MID and xgi FWD are the only xgi-position pairs with confirmed temporal stability. xgi DEF and GK carry conditional classification risk from the outset. |
| G-EDA5-04 | assists DEF shows moderate_shift between EDA halves (gap 5.21 early → 11.39 late). This is flagged as a seasonal drift risk for any rolling assists signal at DEF. |

---

## EDA-6 — Redundancy and construct relationships

**Status:** Complete. Sources: `eda_06_construct_map.csv` (35 rows),
`eda_06_pairwise_rho.csv` (1,626 rows), `eda_06_partial_rho.csv` (35 rows).

### 6.1 Perfect statistical redundancies (rho = 1.0)

| Pair | Positions | Action |
|---|---|---|
| fdr_avg / fdr_max / fdr_min | ALL | All three are perfectly correlated (rho = 1.0). Use fdr_avg only as representative. fdr_max and fdr_min carry no independent information. |

### 6.2 Algebraic decompositions

| Pair | Positions | Partial rho (controlling for total_points) | Note |
|---|---|---|---|
| xa ↔ xgi | DEF (0.68), MID (0.67), FWD (0.20), GK (0.99) | Very high — xa is a component of xgi | xgi preferred as the broader concept. xa is not an independent signal where xgi is available. |
| xg ↔ xgi | MID (0.74), FWD (0.93–0.95), DEF (0.69) | Very high — xg is a component of xgi | xgi preferred. xg not independently useful when xgi is present. |
| creativity ↔ ict_index | MID (0.76), DEF (0.59), FWD (0.43) | Moderate-high | ict_index decomposes into creativity + influence + threat. |
| ict_index ↔ influence | MID (0.65), DEF (0.69), FWD (0.68) | High | influence is a component of ict_index. |
| ict_index ↔ saves (GK) | GK (0.88) | Very high | For GK, ict_index and saves are statistically redundant. |

### 6.3 Form signal redundancy implications

**xgi vs xa:** xa and xgi are highly correlated at MID (partial_rho 0.67) and GK (0.99).
xgi subsumes xa — using both would double-count chance creation quality. xgi is preferred.

**xg vs xgi:** xg and xgi are highly correlated at FWD (partial_rho 0.93) and MID (0.74).
xgi subsumes xg — using both would double-count chance quality. xgi is preferred.

**goals_scored vs assists:** These are structurally independent. Correlation at MID is 0.025
(pairwise rho) — nearly zero. They measure different event types and are not redundant.

**Implication for rolling windows:** If we test xgi_roll3 and also xa_roll3 or xg_roll3,
we are testing redundant constructs. LENS-FORM must not include xa_roll3 or xg_roll3 as
independent candidates where xgi_rollN is already tested.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA6-01 | fdr_avg, fdr_max, fdr_min are perfectly redundant. Use fdr_avg as the sole fixture difficulty representative. |
| G-EDA6-02 | xa is a component of xgi and is not an independent signal where xgi is present. xa_roll* variants must not be registered as independent LENS-FORM candidates. |
| G-EDA6-03 | xg is a component of xgi at FWD (partial_rho 0.93) and MID (0.74). xg_roll* variants must not be registered as independent LENS-FORM candidates. |
| G-EDA6-04 | goals_scored and assists are structurally independent (pairwise rho ≈ 0 at MID). Both may be registered as independent LENS-FORM candidates. |
| G-EDA6-05 | ict_index is a composite index (creativity + influence + threat). It should not be used alongside creativity or influence as independent signals. |

---

## EDA-7 — Synthesis gate decisions

**Status:** Complete. Source: `eda_07_signal_synthesis.csv` (116 rows).

### 7.1 Summary

| Downstream status | Count | Registry meaning |
|---|---|---|
| eligible | 9 | Core signal; meets all EDA criteria without caveat |
| caveated | 83 | Some criteria met with reservations; requires lens validation |
| blocked | 24 | Not available for association analysis |

| Promotion class | Count |
|---|---|
| core_signal | 9 |
| review_signal | 47 |
| context_control | 18 |
| market_context | 16 |
| exposure_control | 2 |
| blocked (NaN) | 24 |

### 7.2 Eligible core signals (9 total)

| Signal | Position | rho_pooled |
|---|---|---|
| assists | DEF | 0.27 |
| assists | FWD | 0.36 |
| assists | MID | 0.49 |
| bonus | DEF | 0.54 |
| bonus | GK | 0.54 |
| bps | GK | 0.91 |
| creativity | MID | 0.19 |
| goals_scored | DEF | 0.32 |
| ict_index | DEF | 0.31 |

**Note on bonus and bps:** These are `points_component` and `contribution_index` signals —
they are components of the scoring system itself. They are eligible for characterisation but
carry target leakage risk in any predictive model. They are excluded from feature use by the
scorer (`layer_role` filter). They are not candidates for LENS-FORM.

### 7.3 Form-proxy signals advancing to LENS-FORM

The following raw signals have EDA evidence sufficient to justify rolling window candidacy
in LENS-FORM. They are review_signal or core_signal, not blocked, and associate with
`total_points` at a level that makes smoothing hypothesis-testable:

| Signal | Positions with non-blocked status | Strongest rho | Notes |
|---|---|---|---|
| xgi | MID (stable), FWD (insufficient), DEF (insufficient), GK (insufficient) | 0.50 (FWD) | Primary LENS-FORM focus |
| goals_scored | DEF (stable), MID (stable), FWD (stable) | 0.85 (FWD) | Core form event |
| assists | MID (stable), FWD (stable), DEF (moderate_shift) | 0.49 (MID) | Core form event |
| total_points | ALL (not in EDA as predictor) | — | Naive baseline: must be included per EVAL_DESIGN.md §6 |

### 7.4 Signals not advancing from EDA to LENS-FORM

| Signal | Reason |
|---|---|
| minutes | Blocked all positions — eligibility signal, not form |
| xa | Component of xgi; blocked at DEF and FWD |
| xg | Component of xgi; blocked at DEF, GK, MID |
| creativity | Eligible at MID but component of ict_index; test ict_index instead |
| ict_index | Composite index; not a raw form signal — context control |
| threat | Blocked DEF and GK; redundant with xgi at FWD/MID |
| bonus, bps | Points components — target leakage risk |
| clean_sheets | Defensive context signal — LENS-FIXTURE-GW territory |
| goals_conceded | Defensive context signal — LENS-FIXTURE-GW territory |
| fdr_avg/max/min | Fixture signals — LENS-FIXTURE-GW territory |

### 7.5 Rolling window signals were not characterised in the EDA

**Critical constraint:** The EDA characterised 29 raw base signals. No rolling window signals
(`xgi_roll3`, `points_roll3`, `minutes_roll3`, etc.) appear anywhere in the EDA registry.
These are DAL state-layer features that the EDA did not examine.

LENS-FORM's scope is to test whether rolling window smoothing of raw form proxies improves
predictive quality over lag-1 raw signals. The EDA establishes that the raw signals associate
with returns — LENS-FORM tests whether smoothing adds information.

The candidacy basis for each rolling window signal must trace to a raw signal finding in this
document. Rolling window signals without a raw signal finding basis may not be registered.

**Gate decisions:**

| ID | Decision |
|---|---|
| G-EDA7-01 | xgi, goals_scored, and assists are the raw form proxies with sufficient EDA evidence to justify rolling window candidacy in LENS-FORM. |
| G-EDA7-02 | total_points (lag-1 raw) must be included as the naive baseline per EVAL_DESIGN.md §6. If no rolling window signal outperforms lag-1 raw total_points, all rolling form signals fail the naive baseline gate. |
| G-EDA7-03 | Rolling window signal candidates must each trace to a raw signal EDA finding. No rolling variant of a blocked or redundant raw signal may be registered. |
| G-EDA7-04 | xa_roll* and xg_roll* are excluded as independent candidates (G-EDA6-02, G-EDA6-03). |
| G-EDA7-05 | minutes_roll* is an availability signal. If registered for LENS-FORM, it must be flagged as a LENS-AVAIL candidate and not classified as a form signal. |
| G-EDA7-06 | creativity, ict_index, bonus, bps are not LENS-FORM candidates. creativity is a component of ict_index; bonus/bps are target-component signals. |

---

## Summary: gate decision index

| ID | EDA layer | Decision summary |
|---|---|---|
| G-EDA0-01 | EDA-0 | Lag-1 alignment — signal at GW N predicts GW N+1 |
| G-EDA0-02 | EDA-0 | GW 1-2 excluded from rolling window analysis (warmup) |
| G-EDA0-03 | EDA-0 | Lag alignment verified via DAL contract; lens code must assert |
| G-EDA1-01 | EDA-1 | Spearman rank correlation throughout |
| G-EDA1-02 | EDA-1 | GW bounds: 6-33 inclusive |
| G-EDA1-03 | EDA-1 | Lens GW lower bound: GW 3 (warmup adjustment) |
| G-EDA1-04 | EDA-1 | Population: minutes >= 60 |
| G-EDA1-05 | EDA-1 | DGW rows must be flagged or excluded |
| G-EDA2-01 | EDA-2 | 24 blocked signal-position pairs permanently excluded |
| G-EDA2-02 | EDA-2 | minutes blocked all positions — AVAIL lens only |
| G-EDA2-03 | EDA-2 | Structural zeros excluded (GK goals, GK/DEF/FWD saves) |
| G-EDA3-01 | EDA-3 | xgi MID: primary LENS-FORM candidate (rho 0.31, stable) |
| G-EDA3-02 | EDA-3 | xgi FWD: candidate with conditional risk (rho 0.50, insufficient_data stability) |
| G-EDA3-03 | EDA-3 | goals_scored DEF: core_signal candidate (rho 0.32, stable) |
| G-EDA3-04 | EDA-3 | assists MID/FWD: established baselines for comparison |
| G-EDA3-05 | EDA-3 | goals_scored FWD/MID: caveated reflects event sparsity, not absent association |
| G-EDA3-06 | EDA-3 | minutes blocked — not a form quality signal |
| G-EDA4-01 | EDA-4 | minutes >= 60 uniform across all positions |
| G-EDA4-02 | EDA-4 | Population robustness confirmed (delta_rho = 0 for 110/116) |
| G-EDA5-01 | EDA-5 | EDA used two-block structure; LENS-FORM must define its own three-block structure |
| G-EDA5-02 | EDA-5 | 76/116 insufficient_data is structural, not a quality failure |
| G-EDA5-03 | EDA-5 | xgi MID and FWD are the only xgi pairs with confirmed temporal stability |
| G-EDA5-04 | EDA-5 | assists DEF shows moderate_shift — seasonal drift risk for rolling variants |
| G-EDA6-01 | EDA-6 | fdr_avg/max/min perfectly redundant — use fdr_avg only |
| G-EDA6-02 | EDA-6 | xa component of xgi — xa_roll* not an independent candidate |
| G-EDA6-03 | EDA-6 | xg component of xgi (FWD/MID) — xg_roll* not an independent candidate |
| G-EDA6-04 | EDA-6 | goals_scored and assists are structurally independent |
| G-EDA6-05 | EDA-6 | ict_index is composite — not alongside creativity or influence |
| G-EDA7-01 | EDA-7 | Form proxy raw signals: xgi, goals_scored, assists |
| G-EDA7-02 | EDA-7 | total_points lag-1 is the mandatory naive baseline |
| G-EDA7-03 | EDA-7 | Rolling variants must trace to a raw signal EDA finding |
| G-EDA7-04 | EDA-7 | xa_roll* and xg_roll* excluded as independent candidates |
| G-EDA7-05 | EDA-7 | minutes_roll* is AVAIL candidate if registered — not a form signal |
| G-EDA7-06 | EDA-7 | creativity, ict_index, bonus, bps not LENS-FORM candidates |
