# Statistical File Map

Every file classified by: statistical ladder rung, question addressed,
inputs, outputs, execution order, and known gaps.

Files are grouped by layer. Execution order runs top to bottom within each layer,
and layers run in order: kernels → foundation → families → model.

---

## How to read this

**Ladder rung** — where the file sits on the statistical ladder:
- `D` — Descriptive ("what happened in this data")
- `Dg` — Diagnostic ("why did this happen")
- `I` — Inferential ("what is likely true beyond this data")
- `H` — Hypothesis test / decision rule ("given the inference, what do I decide")
- `Dec` — Domain decision ("given the verdict, what do I do in FPL")
- `Pre` — Pre-statistical (data integrity, scope, design enforcement — before any stat)

---

## Layer 0 — Kernels (reusable statistical primitives)

These files contain no domain knowledge. They answer pure statistical questions.
They are called by foundation studies and family studies — never directly by
governance or model layers.

---

### `research/kernels/windows.py`
**Rung:** Pre  
**Question:** Are the temporal integrity contracts of the study design enforced?  
**What it does:** Enforces the lag-1 guarantee — confirms that rolling window
features at GW N contain only information from GW 1..N-1. Provides
`evaluation_gameweeks()` to filter the study population to valid GW ranges.  
**Input:** features DataFrame with a `gw` column  
**Output:** list of valid GW integers; validation errors if lag contract is violated  
**Run order:** First — called by study `run()` before any statistical computation  
**Gaps:**
- Lag enforcement is documented but not asserted in a test that would catch
  a mart change silently re-introducing leakage
- No explicit test that GW 1-2 exclusions propagate correctly to thin-position slices

---

### `research/kernels/distribution.py`
**Rung:** D  
**Question:** What does this signal's marginal distribution look like? How complete
is the data? What is the shape of the target variable?  
**What it does:** Completeness analysis (nulls, late joiners), atomic distribution
stats (mean, median, IQR, skew, tail percentiles), cohort aggregation, tail analysis.  
**Input:** mart DataFrame  
**Output:** distribution summary dicts / DataFrames  
**Run order:** Early — used in foundation profiling and explore-layer EDA  
**Gaps:**
- No classification of distribution shape (normal / skewed / bimodal) — callers
  infer this manually
- No formal check that the distribution is stable enough for downstream inference
  (stability.py handles that separately)

---

### `research/kernels/stability.py`
**Rung:** Dg  
**Question:** Is this signal's distribution consistent across GW blocks, or does
it shift materially mid-season?  
**What it does:** Computes per-block distribution stats (median, IQR) and classifies
the normalized median shift between blocks as `stable` / `moderate_shift` / `unstable`.
Maps that classification to a pooling decision.  
**Input:** player-GW DataFrame; list of signals, positions, GW block definitions  
**Output:** block_stats DataFrame; stability verdict; pooling decision  
**Run order:** After distribution.py — depends on having raw data, no inference yet  
**Assumptions:** Thresholds (STABLE_THRESHOLD, UNSTABLE_THRESHOLD) are operational
heuristics, not statistically derived. See module docstring.  
**Gaps:**
- Thresholds not power-justified — no formal sensitivity analysis
- Only median shift is used; mean shift and variance shift are not tested
- Pooling decision (`restrict_to_midseason`) is not yet enforced downstream in
  the study runner — it is computed but the study does not filter to midseason when
  this verdict is returned

---

### `research/kernels/resampling.py`
**Rung:** I  
**Question:** Is this signal's rank correlation with the target distinguishable
from zero, given the uncertainty in our limited sample?  
**What it does:** Bootstrap percentile confidence interval for Spearman rho.
Resamples rows with replacement N_BOOTSTRAP times, computes rho each time,
returns the CI_LEVEL percentile interval.  
**Input:** two aligned numpy arrays (signal values, target values)  
**Output:** dict — rho point estimate, ci_lower, ci_upper, n, ci_excludes_zero  
**Run order:** Called per (signal, position, GW window) inside the study run loop —
after data is prepared, before qualification gates  
**Assumptions:**
- Rows are exchangeable conditional on position (bootstrap assumption)
- Relationship is stationary within the study window
- Panel structure is tolerated but not corrected — bootstrap widens CIs naturally
  but does not formally account for within-player clustering
**Gaps:**
- `estimate_chance_correlation` (permutation baseline) is computed in
  `composition_study.py` but not in the family validate studies — no baseline
  comparison at the signal screening stage
- No power analysis: there is no documented minimum n to detect rho = 0.10 at
  CI_LEVEL = 0.95 with N_BOOTSTRAP = 1000
- MIN_N = 10 is a crash floor, not a power-justified threshold
- Zero-variance bootstrap trap: if a resample draws all-identical values,
  spearmanr returns NaN — silently dropped by np.nanpercentile. Rare but unlogged.

---

### `research/kernels/stratification.py`
**Rung:** H (Gate 2)  
**Question:** Is the signal's association with the target practically meaningful —
does higher signal rank correspond to higher (or lower) target mean in a
monotone, decision-relevant way?  
**What it does:** Splits the population into 5 equal-rank quintiles on the signal,
measures target mean per quintile, computes Q5-Q1 gap and monotonicity. Returns
`decision_relevant` boolean.  
**Input:** player-GW DataFrame, signal name, target name, position, gap_threshold,
bidirectional flag  
**Output:** dict — q1_mean..q5_mean, q5_q1_gap, is_monotonic, decision_relevant  
**Run order:** After resampling.py passes Gate 1 — called only when CI excludes zero  
**Assumptions:**
- Equal-sized quintile bins are meaningful (requires n ≥ 25 for ≥5 rows per bin)
- Monotonicity is assessed on raw means — no smoothing or trend test
- Gap threshold is domain-calibrated per family, not statistically derived
**Gaps:**
- No confidence interval on the Q5-Q1 gap itself — gap could be noise at low n
- Bidirectional=True for fixture signals uses abs(gap) — sign direction not
  explicitly verified against the signal's known expected direction
- MIN_N = 25 is a heuristic; no formal justification

---

### `research/kernels/multiplicity.py`
**Rung:** H (multiple comparison correction)  
**Question:** When testing many signals simultaneously, how many of our "passes"
are false positives by chance?  
**What it does:** Benjamini-Hochberg (FDR control) and Holm-Bonferroni
(FWER control) correction for families of p-values.  
**Input:** list of p-values from a hypothesis test family  
**Output:** adjusted p-values, reject/fail-to-reject array  
**Run order:** After all per-signal tests in a family are complete  
**Gaps:**
- **Not currently called by any family validate study.** The three-gate protocol
  uses CI exclusion of zero (no p-value) so this kernel has no integration point
  in the primary qualification pipeline. It exists but is unused in the main flow.
- When it would matter: if Gate 1 is ever converted to p-value form, or if a
  batch screening study runs all signals simultaneously, multiplicity correction
  becomes mandatory
- FDR here = False Discovery Rate; elsewhere in the repo FDR = Fixture Difficulty
  Rating. Name collision documented in module docstring.

---

### `research/kernels/conditioning.py`
**Rung:** Dg / I  
**Question:** Does the signal→target relationship hold uniformly across subgroups,
or is it a subgroup artifact?  
**What it does:** Tests rho consistency across strata of a moderator variable.
Classifies as `homogeneous` / `heterogeneous_magnitude` / `heterogeneous_sign` /
`insufficient`.  
**Input:** player-GW DataFrame stratified by a moderator; signal and target names  
**Output:** conditioning verdict dict per stratum  
**Run order:** After Gate 1 passes — used when a signal passes CI gate and you
want to understand whether the association is robust across subgroups  
**Gaps:**
- **Not currently called by any family validate study.** Exists as a kernel but
  has no integration point in the primary qualification pipeline.
- FDR conditioning (fixture difficulty as moderator) is explicitly listed as
  DEFERRED MATERIAL in composition_study.py — this is the kernel that would
  implement it
- No bootstrap CI on the stratum-level rhos — strata are often thin (n < 30)

---

### `research/kernels/geometry.py`
**Rung:** Dg  
**Question:** What is the shape of the signal→target relationship — monotone,
threshold, non-monotone? Is that shape stable across GW windows?  
**What it does:** Bin analysis (discrete, quantile, ordinal bucketing), shape
classification (`monotonic_positive`, `threshold_positive`, `non_monotonic`, etc.),
temporal stability classification on the bin-level gap.  
**Input:** player-GW DataFrame; signal and target names; bucketing scheme  
**Output:** bin_stats DataFrame; geometry classification string; stability verdict  
**Run order:** Used in foundation joint studies and registry assembly  
**Gaps:**
- Shape classification is rule-based (heuristic threshold comparisons), not
  statistical — no confidence on the shape assignment
- `stability_classify` uses gap variance across windows without a CI — could
  misclassify a stable signal as `moderate_shift` at low n

---

### `research/kernels/association.py`
**Rung:** Dec (bridges research → model)  
**Question:** Given all the relationship evidence (geometry, stability, panel
decomposition, tail dependence), what structural class does this signal belong to?  
**What it does:** Assigns `association_class` from a precedence-ordered rule set:
`unassessable` → `temporally_unstable` → `weak_association` → `upper_tail_dominant`
→ `continuous_monotonic`.  
**Input:** registry row dict with geometry, stability, rho_drop, low_confidence,
panel_class fields  
**Output:** association_class string  
**Run order:** Registry assembly — after all research evidence is collected  
**Gaps:**
- Rule ordering is editorial — no documented justification for why
  `temporally_unstable` outranks `weak_association`
- `low_confidence` flag source is not documented here — callers must know
  what threshold triggers it

---

### `research/kernels/correlation/panel.py`
**Rung:** Dg / I  
**Question:** How much of the pooled rho is driven by stable between-player
identity differences versus genuine within-player state changes?  
**What it does:** Decomposes pooled Spearman rho into between-player and
within-player components using player-mean-centering. Classifies as
`state_sensitive` / `mixed` / `identity_dominant` / `indeterminate`.  
**Input:** player-GW DataFrame with player_id; signal and target names  
**Output:** dict — rho_pooled, rho_between, rho_within, panel_class, n_players, n_records  
**Run order:** Used in foundation joint studies and registry sections  
**Gaps:**
- No bootstrap CI on rho_between or rho_within — only point estimates
- Panel class thresholds are heuristic
- Requires min_n_players=20 and min_n_shape=100 — thin positions (GK, FWD)
  often don't meet this, returning `indeterminate` without explanation

---

### `research/kernels/correlation/tail.py`
**Rung:** Dg  
**Question:** Is the signal→target association driven by haul events (very high
scoring GWs), or does it hold for typical weekly returns too?  
**What it does:** Measures rho drop when haul events (target > 12 points) are
removed. Flags `tail_sensitive=True` when the drop is material (≥ 0.20).  
**Input:** player-GW DataFrame; signal and target names; haul_threshold  
**Output:** dict — tail_sensitive, rho_full, rho_ex_haul, rho_drop, n_haul, haul_pct  
**Run order:** Used in foundation joint studies and registry sections  
**Gaps:**
- haul_threshold=12 is editorial — no documented justification
- No CI on rho_drop — a drop of 0.21 from n=80 hauls is not reliably different
  from 0.20

---

## Layer 1 — Foundation (whole-dataset characterisation, pre-screening)

These run once per season dataset to understand the data before any family study.
They are not part of the qualification pipeline — they inform design decisions.

---

### `research/foundation/integrity/_integrity_helpers.py`
**Rung:** Pre  
**Question:** Is the mart data clean? Are rolling windows computed correctly?
Is the lag-1 contract respected in the raw data?  
**What it does:** Checks rolling column presence, lag alignment, activity filter
correctness, GW coverage.  
**Input:** raw mart DataFrame  
**Output:** integrity check results dict  
**Run order:** First of all — before any statistical work. Integrity failure
invalidates all downstream results.  
**Gaps:**
- No automated assertion that the lag is correct (only structural checks) —
  a mart change that shifts the lag would not be caught here

---

### `research/foundation/signals/profiling.py`
**Rung:** D  
**Question:** What do the signals look like marginally — distribution shape, zero
mass, variance, structural zeros by position?  
**What it does:** Per-signal, per-position distribution profiling. Identifies
structural zeros (e.g. saves for outfield players). Produces a signal status table.  
**Input:** player-GW DataFrame  
**Output:** profiling summary table; structural zero flags  
**Run order:** After integrity checks; before scoping or association studies  
**Gaps:**
- No formal test for bimodality (e.g. binary signals like `was_home`) — these
  are handled by binary-signal lists but not detected automatically

---

### `research/foundation/signals/scoping.py`
**Rung:** D / Dg  
**Question:** Are the signals' distributions stable across exposure scopes
(all players vs started players)? Which scope is the preferred population for
each signal?  
**What it does:** Dual-scope distribution summaries; exposure sensitivity
classification; preferred population assignment.  
**Input:** player-GW DataFrame; exposure filter definitions  
**Output:** dual-scope summary; population preference per signal  
**Run order:** After profiling.py  
**Gaps:**
- Preferred population choice is heuristic — no formal test of which scope
  produces more reliable downstream inference

---

### `research/foundation/scope/population.py`
**Rung:** Dg  
**Question:** Is the signal→target association stable across population scopes,
or does it change materially when we restrict to starters only?  
**What it does:** Dual-scope rho comparison; classifies population robustness as
`stable` / `scope_sensitive` / `untested`.  
**Input:** player-GW DataFrame; signal and target names; scope definitions  
**Output:** population_robustness verdict per (signal, position)  
**Run order:** After scoping.py — needs preferred population identified first  
**Gaps:**
- Rho shift threshold (0.10) and geometry-change criterion are heuristic
- No bootstrap CI on either scope's rho — the shift comparison is point-estimate only

---

### `research/foundation/joint/association.py`
**Rung:** Dg  
**Question:** What is the full structural characterisation of a signal→target
relationship across geometry, stability, panel composition, and tail dependence?  
**What it does:** Orchestrates geometry.py, panel.py, tail.py, stability_classify
into a single relationship evidence record per (signal, position).  
**Input:** player-GW DataFrame; signal and target names  
**Output:** relationship evidence dict (geometry, stability, panel_class,
tail_sensitive, association_class, support_flags)  
**Run order:** After scoping; before registry assembly  
**Gaps:**
- This is the richest characterisation layer but its verdicts don't flow into
  the family validate studies — they feed the registry separately. The two
  evidence streams (joint association + family validation) are not formally
  reconciled.

---

### `research/foundation/gap/eda_08_study.py`
**Rung:** D / Dg  
**Question:** Are specific signals that were excluded or gated in earlier EDAs
(saves, xgc, penalties_saved, assists rolling windows) actually viable?  
**What it does:** Targeted gap study — Layer 1 raw association + Layer 2
redundancy for specific signals. Produces gate decisions G-EDA8-01 through G-EDA8-10.  
**Input:** mart DataFrame  
**Output:** gate decisions YAML; run CSVs  
**Run order:** Standalone gap study — run when a signal family needs investigation  
**Gaps:**
- This is explore-stage, not validate-stage — findings need to be ratified by
  a family validate study before entering governance

---

## Layer 2 — Family validate studies (per-lens qualification)

These run once per lens per season. They are the primary qualification pipeline.
Each study calls kernels in a fixed sequence and emits evidence.yaml.

**Execution sequence within each study:**
```
1. windows.py       → filter to valid GWs (Pre)
2. resampling.py    → Gate 1: CI excludes zero (I)
3. stratification.py → Gate 2: quintile decision relevance (H)
4. resampling.py    → Gate 3: per-GW-window CI (H)
5. _apply_signal_qualification_gates → verdict (H)
6. evidence_record.py → write evidence.yaml (Dec)
```

---

### `research/families/form/validate/study.py`
### `research/families/availability/validate/study.py`
### `research/families/market/validate/study.py`
### `research/families/fixture/validate/study.py`

**Rung:** H (orchestrates I + H kernels, produces H verdict)  
**Question:** For each (signal, position), does the signal qualify as an
informative, uninformative, or unstable lens for next-GW total points prediction?  
**What each does:** Runs the three-gate protocol per signal per position per
GW window. Emits `lens_status` per row. Writes evidence.yaml.  
**Input:** mart DataFrame (joined to appropriate signal columns)  
**Output:** run CSVs (full_assoc_rows, window_assoc_rows, stratification_rows,
qualification_rows); evidence.yaml; run_metadata.json  
**Differences between studies:**
- `availability` uses a binary target (minutes ≥ 60) with gap_threshold=0.10
- `fixture` uses bidirectional=True for quintile (negative rho signals)
- `fixture` is same-GW design — no target lag (association only, not predictive)
**Gaps (all four studies):**
- No estimand document — the exact quantity each study estimates is not written down
- No assumption audit — bootstrap + quintile + window assumptions not listed
- No validity assessment — construct validity (does the signal represent the
  intended concept?) not formally evaluated
- `conditioning.py` not called — FDR conditioning is deferred
- `multiplicity.py` not called — no multiple-comparison correction across signals
- `estimate_chance_correlation` not called — no permutation baseline at
  qualification stage
- Gate thresholds (gap_threshold, min stable blocks) are not cross-referenced
  with a power analysis

---

### `research/families/evidence_record.py`
**Rung:** Dec (statistical → governance bridge)  
**Question:** What is the machine-readable verdict record for this (signal, position),
and is it in the format governance expects?  
**What it does:** Assembles `build_signal_verdict()` output into the evidence.yaml
schema. Maps `lens_status` to `decision_class` (unstable → uninformative).  
**Input:** corr_record, quint_record, block_records, signal, signal_id, position  
**Output:** evidence.yaml row dict  
**Run order:** Last step in each family validate study  
**Gaps:**
- `decision_class` collapse (unstable → uninformative) loses information — a
  governance reviewer cannot tell from decision_class alone whether a signal
  failed Gate 1 or failed Gate 3
- No schema validation on the output dict before writing — a malformed row
  would only be caught when governance reads it

---

## Layer 3 — Model / Composition

---

### `model/assemble/composition_study.py`
**Rung:** I / H / Dec  
**Question:** Which signals, at what weights, should enter the composition model?
Which are redundant? How stable are the weights?  
**What it does:** Partial Spearman rho controlling for same-position same-lens
candidates; redundancy resolution; bootstrap CIs on composition weights;
FDR moderation sensitivity (deferred); produces synth01_recommendations.yaml.  
**Input:** mart DataFrame; evidence.yaml verdicts from all four family studies  
**Output:** synth01_recommendations.yaml (recommendations, not decisions)  
**Run order:** After all four family validate studies complete  
**Gaps:**
- FDR conditioning explicitly DEFERRED — the most material gap in composition
- Module weights (lens-level aggregation) are still editorial
- `estimate_chance_correlation` is called here but not in family studies —
  the permutation baseline is available at composition but not at qualification

---

### `model/governance/promotion.py`
**Rung:** Dec  
**Question:** Given the governed registry, how should each signal be classified
for operational use?  
**What it does:** Assigns `promotion_class` ∈ {primary, supporting, contextual,
experimental, blocked} from registry fields.  
**Input:** governed registry DataFrame  
**Output:** registry with promotion_class column  
**Run order:** After governance enrichment (semantics.py)  

---

### `model/governance/semantics.py`
**Rung:** Dec  
**Question:** What semantic enrichment (signal layers, downstream status) should
be applied to the governed registry?  
**What it does:** Enriches registry rows with signal layer (signal_layer) and
downstream_status from domain rules.  
**Input:** raw registry DataFrame  
**Output:** enriched registry DataFrame  
**Run order:** Before promotion.py  

---

## Execution order summary

```
Pre-statistical
  integrity/_integrity_helpers.py   ← mart clean?

Descriptive / Diagnostic (foundation)
  kernels/distribution.py           ← signal shapes
  foundation/signals/profiling.py   ← marginal distributions
  foundation/signals/scoping.py     ← exposure sensitivity
  foundation/scope/population.py    ← dual-scope rho comparison
  foundation/joint/association.py   ← full structural characterisation

Inferential / Qualification (families)
  Per family, per (signal, position):
    kernels/windows.py              ← enforce GW range + lag contract
    kernels/resampling.py           ← Gate 1: bootstrap CI
    kernels/stratification.py       ← Gate 2: quintile decision relevance
    kernels/resampling.py (×3)      ← Gate 3: per-window CI
    families/*/validate/study.py    ← _apply_signal_qualification_gates
    families/evidence_record.py     ← write evidence.yaml

Composition (model)
  kernels/resampling.py             ← bootstrap CIs on weights
  model/assemble/composition_study.py ← recommendations

Governance (model)
  model/governance/semantics.py     ← enrich registry
  model/governance/promotion.py     ← assign promotion class

Not yet integrated into the main flow (gaps):
  kernels/multiplicity.py           ← multiple comparison correction
  kernels/conditioning.py           ← FDR moderation
```

---

## Cross-cutting gaps (affect multiple files)

| Gap | Affected files | Impact |
|---|---|---|
| No estimand registry | All four family studies | Design drift — lag removed, studies still run |
| No assumption audit | resampling, stratification, stability | Future contributor violates assumption silently |
| No construct validity assessment | All four family studies | Wrong signal, right method |
| multiplicity.py unused in qualification | All four family studies | False positive rate uncontrolled across signal family |
| conditioning.py unused | composition_study.py (deferred) | FDR moderation effect unknown |
| No power analysis | resampling, stratification | MIN_N thresholds not justified |
| foundation/joint evidence not reconciled with family evidence | evidence_record.py | Two separate evidence streams, no formal join |

---

## Pending structural cleanup

Decisions noted during review. Grouped by when they can be actioned.

---

### Group A — Do now (no EDA dependency, low risk)

| # | File | Action | Callers | Effort |
|---|---|---|---|---|
| A1 | `research/kernels/windows.py` | **Delete entire file** | 2 explore studies, 1 test file, `tests/helpers/windows.py` duplicate | S |
| A2 | `research/kernels/metrics.py` | **Move to `research/evaluation/metrics.py`** | 2 explore studies, tests only | S |
| A3 | `research/foundation/integrity/_integrity_helpers.py` | **Assess + move mart-level checks to DAL** | `eda_00_integrity.ipynb` only | M |

**A1 detail — `windows.py` deletion:**

Two functions exist in two places:
- `research/kernels/windows.py` — used by `rolling_xgi_study.py`, `minutes_stability_study.py`, `test_rolling_xgi_real_validation.py`
- `tests/helpers/windows.py` — used by test helpers (captain, transfers, value, features, evaluation_core)

`evaluation_gameweeks` is a one-line filter — inline at call sites.
`assert_no_future_leakage` should have one canonical home: `tests/helpers/windows.py` (it's a test/evaluation contract, not a production kernel). The explore studies can import from there or inline the check.
`_REQUIRED_ROLLING_COLS` is dead — DAL already enforces this via Pandera.

Migration steps:
1. Update explore studies (`rolling_xgi_study.py`, `minutes_stability_study.py`) to inline `evaluation_gameweeks` and import `assert_no_future_leakage` from `tests/helpers/windows.py`
2. Update `test_rolling_xgi_real_validation.py` to import from `tests/helpers/windows.py`
3. Delete `research/kernels/windows.py`
4. Remove from `research/kernels/__init__.py` comment
5. Delete `tests/test_kernels_windows.py` (testing a deleted file)

**A2 detail — `metrics.py` move:**

Functions: `mean_return`, `top1_return`, `hit_rate`, `regret`, `return_variance`, `downside_rate`, `rank_correlation`.
All are backtesting/evaluation metrics — measure decision quality post-hoc, not statistical primitives.
`rank_correlation` is domain-agnostic but its only callers are evaluation helpers and explore studies.

Migration steps:
1. Create `research/evaluation/` directory with `__init__.py`
2. Move `metrics.py` to `research/evaluation/metrics.py`
3. Update callers: `rolling_xgi_study.py`, `minutes_stability_study.py`, `test_kernels_metrics_distribution.py`
4. Update `research/kernels/__init__.py` comment
5. Verify `tests/helpers/metrics.py` — check if it imports from kernels (it may already be independent)

**A3 detail — `_integrity_helpers.py` assessment:**

Functions: `build_findings_template`, `check_rolling_windows`, `check_lag_alignment`, `check_activity_filter_gate`, `select_verification_players`.

These are EDA-0 study construction audits — they verify the DAL's rolling window algebra is analytically correct. They are NOT duplicates of DAL structural checks — they verify correctness of derived values, not schema presence.

Assessment outcome: keep in `research/foundation/integrity/` but rename to clarify they are analytical correctness checks, not DAL schema validators. No move needed.

---

### Group B — Do after full-season re-open EDA (EDA dependency)

| # | File | Action | Reason for deferral |
|---|---|---|---|
| B1 | `research/kernels/stability.py` — block boundaries | **Analytical evaluation in `eda_05_signal_stability.ipynb`** | Need full 2025-26 data to verify editorial block boundaries against actual signal change points |
| B2 | `research/kernels/stability.py` — `resolve_pooling_strategy` enforcement | **Enforce `restrict_to_midseason` in study runners** | Blocked on B1 — boundary validation must precede enforcement |

---

### Group C — Completed ✓

| File | What was done |
|---|---|
| `research/kernels/distribution.py` | `analyze_by_group` deleted; FPL domain functions moved to `research/foundation/target/` (split into `fixture_context.py`, `haul_analysis.py`, `visualisation.py`); `analyze_data_completeness` moved to `dal/fct/validation/completeness.py`; file now owns only `compute_distribution_stats` + `compare_cohorts` |
| `research/kernels/association.py` | Deleted — moved to `domain/registry/association.py` as governance decision logic, not a kernel |
| `research/foundation/joint/association.py` | Deleted — workaround copy eliminated |
| `research/kernels/stability.py` | `moderation_instability_rate` moved to `model/assemble/composition_study.py` as `_moderation_instability_rate`; `stability_classify` moved in from `geometry.py` |
| `research/kernels/geometry.py` | `stability_classify` moved out; `PANEL_CLASS_THRESHOLDS`, `HAUL_THRESHOLD_PTS`, `HAUL_DROP_MATERIAL` moved to `domain/registry/association.py` |
| `domain/registry/association.py` | Created — canonical home for `assign_association_class`, `consolidate_flags`, `PANEL_CLASS_THRESHOLDS`, `HAUL_THRESHOLD_PTS`, `HAUL_DROP_MATERIAL` |
