# Representation Governance

**Status:** ACTIVE
**Version:** 1.1
**Produced:** 2026-05-24
**Scope:** Transformation governance for analytical representations in the FPL intelligence system

---

## 1. Core Architectural Philosophy

### Transforms must not be universally applied

Every signal in this system has a temporal type and a family. These classifications carry hard
constraints on what transformations are semantically meaningful. A rolling mean applied to
`ownership_count` (stock) is semantically invalid — it produces an "average level" that has no
coherent interpretation. A rolling mean applied to `fdr_avg` (Context, pre-match fixed) is
equally invalid — the fixture difficulty for GW20 is not a function of historical fixture
difficulty. Applying the same transform pipeline to every signal because it is convenient is
not an analytical choice. It is an absence of one.

### Semantics alone are insufficient

Temporal type defines what transforms are admissible — transforms that do not violate the
signal's fundamental nature. It does not define what transforms should be applied. Both
`penalties_saved` and `goals_scored` are Event family, count temporal type. A 5-game rolling
mean is semantically admissible for both. But `penalties_saved` is structurally sparse — near
zero for the large majority of player-gameweek rows. A rolling mean over a column that is
almost entirely zeros does not smooth signal; it dilutes the rare, potentially meaningful spike
with a sequence of near-zero values. EDA evidence on distribution, sparsity, and persistence is
required before an admissible transform is approved for materialization.

### EDA alone is insufficient

A positive correlation between a transformed signal and total_points in an EDA study is not
approval. If the transform is semantically inadmissible, a positive rho does not rehabilitate
it — it is an artifact of a mis-specified representation. A rolling delta applied to `was_home`
(indicator) may produce a non-zero correlation. That correlation has no analytical meaning
because `was_home` has no magnitude, no ordering, and no valid delta. EDA findings must be
interpreted within the admissibility boundary — not used to override it.

### The "can vs should" distinction

This document enforces two gates, not one:

- **Admissibility gate** — can this transform be applied to this signal type without violating
  semantic meaning? This is determined by temporal type and family. It is a hard gate: rejection
  here ends the pipeline regardless of EDA findings.

- **Justification gate** — given that the transform is admissible, does behavioral evidence from
  EDA support applying it? This is determined by signal distribution, sparsity, persistence,
  and decay characteristics. Passing the admissibility gate gives permission to evaluate. It
  does not grant approval.

Both gates must pass before a representation enters STATE.

---

## 2. Representation Decision Flow

```
RAW SIGNAL
    |
    v
ONTOLOGY CLASSIFICATION
    |
    v
SEMANTIC ADMISSIBILITY CHECK
    |
    v
EDA BEHAVIORAL ANALYSIS
    |
    v
REPRESENTATION VALIDATION
    |
    v
STATE MATERIALIZATION
    |
    v
EVALUATION
    |
    v
OPERATIONAL APPROVAL
```

**RAW SIGNAL**
The signal as recorded in the source data — per-player, per-gameweek counts, estimates,
indicators, or levels. No transformation applied. Ground truth for all downstream decisions.

**ONTOLOGY CLASSIFICATION**
Each signal is assigned a family, scope, temporal type, and semantic constraint in
`signal-ontology.yaml`. This classification is determined once and is stable across analytical
cycles. It is the reference point for all subsequent governance decisions.

**SEMANTIC ADMISSIBILITY CHECK**
The proposed transform is tested against the signal's temporal type and family. The rules in
Section 3 define what is admissible and what is a hard stop. If a proposed transform is
inadmissible, the pipeline terminates here. No EDA is run on inadmissible transforms; doing so
would imply the transform is under consideration.

**EDA BEHAVIORAL ANALYSIS**
For transforms that pass the admissibility check, EDA characterises the signal's behavioral
profile: distribution shape, sparsity, persistence, volatility, decay, and redundancy relative
to other signals. The behavioral profile framework in Section 4 defines what each characteristic
implies for representation decisions. A transform that is admissible but unsupported by
behavioral evidence is rejected at this gate.

**REPRESENTATION VALIDATION**
The decision matrix in Section 5 combines admissibility and behavioral evidence into a formal
outcome: APPROVED, REJECTED-SEMANTIC, REJECTED-BEHAVIORAL, or CONDITIONAL. Only APPROVED and
CONDITIONAL representations proceed. Rejected representations are documented with the gate
at which they failed and the reason.

**STATE MATERIALIZATION**
Approved representations are materialized as columns in `dal/feat/feat_player_gameweek.py`.
Each column carries structured metadata: scope, causality, behavioral_reason, and the gate
decisions that produced it. Rules in Section 7 govern what may appear in STATE.

**EVALUATION**
Materialized representations are evaluated for analytical association with total_points across
gameweek blocks. Evaluation tests robustness — rho_pooled, 95% CI, and GW block stability —
not just aggregate correlation. Results determine lifecycle progression from
`lens-evaluated` toward `synthesis-eligible`.

**OPERATIONAL APPROVAL**
Representations that pass evaluation with sufficient robustness achieve `operationally-approved`
lifecycle state. Only these representations are consumed by scoring and decision modules.
Operational thresholds derived from evaluation findings must cite the specific study.

---

## 3. Temporal Type Admissibility Framework

### count

**Semantic meaning:** A discrete integer count of occurrences within a bounded period. Resets
each gameweek. Non-negative. Examples: `goals_scored`, `assists`, `saves`, `penalties_saved`,
`bonus`, `transfers_in`, `transfers_out`.

**Admissible transforms:**
- Rolling mean (smooths per-period counts; meaningful as average occurrence rate over a window)
- Rolling sum (cumulative count over window; appropriate for thin-signal contexts)
- Lag (prior-period value; point-in-time reference without aggregation)
- Raw (per-gameweek count is directly meaningful)
- log1p — admissible only where EDA confirms heavy-tail distribution or multiplicative behavior;
  compresses extreme values and makes relative differences visible; the +1 offset handles zeros
  but softens sparse spike structure — not appropriate for sparse event counts (see failure modes)
- Delta-log — admissible where log1p is admissible; log(x_t) - log(x_t-1) captures proportional
  change rather than absolute change; more meaningful than raw delta for signals where relative
  growth matters (e.g., `100k → 200k` vs `1.9m → 2.0m` — both +100k, but only the first
  represents a doubling)

**Inadmissible transforms:**
- Delta of a raw count where the signal is not heavy-tailed (difference between two independent
  period totals; interpretation unclear without proportional context)
- Cumulative season sum as a primary representation (confounds form with minutes played and
  BGW accumulation; use only with explicit exposure normalisation)
- log1p on sparse event counts (goals_scored, assists, penalties_saved) — log(0+1) = 0 for all
  zero rows; the transform collapses the zero mass to the same value while softening the rare
  non-zero spike; destroys burst structure without providing distributional benefit

**Common failure modes:**
- Applying rolling mean to every count signal without checking sparsity; sparse counts produce
  rolling columns that are nearly always zero with rare fractional values
- Treating rolling mean approval for one count signal (e.g., `goals_scored` for strikers) as
  transferable to structurally different count signals (e.g., `penalties_saved`)
- Ignoring BGW null values in rolling computations; these collapse effective window size
- Applying log1p to count signals without first verifying heavy-tail distribution in EDA;
  log transforms on roughly-symmetric or sparse signals add complexity without analytical benefit

---

### rate

**Semantic meaning:** A continuous measurement of a quantity bounded by a natural ceiling per
unit time. Changes within a gameweek; the ceiling scales with fixture count in DGW. Currently
one signal in the system: `minutes`.

**Admissible transforms:**
- Rolling mean (average minutes across a window; captures availability trend)
- Raw (direct per-gameweek minutes; appropriate for point-in-time availability)
- Threshold indicator (e.g., minutes >= 60 as an FPL bonus qualifier; this is a derived
  indicator, not a transform of the rate itself)

**Inadmissible transforms:**
- Delta on rate (week-to-week difference in minutes has no stable interpretation; whether a
  player went from 45 to 90 or 90 to 45 carries very different meaning, and the direction is
  not reliably informative)
- Cumulative season sum without normalisation (confounds fitness, rotation, and fixture count)

**Common failure modes:**
- Treating minutes rolling mean as an availability proxy without noting that high rolling mean
  may include DGW inflation
- Using raw minutes as an independent analytical candidate without controlling for fixture count

---

### stock

**Semantic meaning:** A point-in-time level that persists between periods and changes through
net flows. A stock is a level, not a period count. Taking the average of stock levels over time
is semantically invalid — you are averaging a level at multiple snapshots, not a quantity that
accumulates. Examples: `ownership_count`, `purchase_price`.

**Admissible transforms:**
- Delta (change in stock between periods; converts a level into a flow for that interval)
- Raw point-in-time value (current level; appropriate for structural conditioning)
- Lag (prior-period level as a reference point)
- log1p of the raw level — admissible only where EDA confirms heavy-tail distribution;
  compresses the scale of a large-range stock into a space where relative position is
  visible; `ownership_count` is a plausible candidate given the likely skew between
  fringe and template players, but this requires distributional EDA to confirm
- Delta-log — admissible where log1p is admissible; captures proportional growth rate of
  the stock level between periods; for `ownership_count` this is analytically preferable
  to raw delta because proportional growth (doubling from 50k to 100k) is more meaningful
  than absolute growth (whether 50k or 500k net new owners)

**Inadmissible transforms:**
- Rolling mean (averaging a level over multiple periods is semantically invalid; the result
  has no coherent interpretation as either a stock or a flow)
- Rolling sum (summing point-in-time levels is dimensionally incoherent)

**Common failure modes:**
- Applying roll3/roll5 to `ownership_count` or `purchase_price` because "smoothing reduces
  noise" — this treats a stock as if it were a count, which it is not
- Conflating the delta of `ownership_count` (a flow, representing net transfer activity) with
  `transfers_in` and `transfers_out` (the underlying raw flows that drive the stock change)
- Applying log1p to `purchase_price` without checking whether price variation in this
  system is actually heavy-tailed or whether absolute price differences are the analytically
  relevant quantity

---

### indicator

**Semantic meaning:** A binary or categorical flag. No magnitude. No ordering beyond the
category boundary. No valid arithmetic between values. Examples: `was_home`.

**Admissible transforms:**
- Raw value as a binary moderator or grouping variable in analysis
- Categorical conditioning (e.g., stratifying evaluation by was_home = 1 vs 0)

**Inadmissible transforms:**
- Rolling mean (average of binary values produces a fraction; this is a new variable,
  not a transform of the indicator — it represents a "home-rate" concept that must be
  justified independently and classified with its own temporal type)
- Delta (difference between binary values in {-1, 0, 1} has no interpretable meaning for
  a fixture property)
- Any arithmetic aggregation that treats the flag as having magnitude

**Common failure modes:**
- Computing roll3 of `was_home` and treating it as a valid "recent home-load" feature without
  recognising this is a new derived variable requiring its own justification
- Treating a positive EDA correlation for an indicator transform as validation, when the
  transform has already violated admissibility

---

### estimate

**Semantic meaning:** A model-produced continuous approximation of an unobserved underlying
quantity. Non-negative real. Has magnitude and ordering. Accumulates meaningfully within a
period and across periods. Examples: `xg`, `xa`, `xgi`, `xgc`, `fdr_avg`, `fdr_max`,
`fdr_min`.

**Admissible transforms (for non-Context estimates):**
- Rolling mean (smooths noisy per-gameweek model estimates; captures form trend)
- Rolling sum (cumulative model output over a window)
- Lag (prior-period estimate as a reference)
- Raw (per-gameweek model output; meaningful on its own)

**Inadmissible transforms — Context family override:**
Context signals (`fdr_avg`, `fdr_max`, `fdr_min`) are fully determined pre-match. They describe
a fixture, not a player's temporal trajectory. Any rolling or delta transform is inadmissible
regardless of temporal type — there is no "recent form" in fixture difficulty that belongs to
the player.

**Common failure modes (estimate — non-Context):**
- Treating `xa` rolling mean as independent of `xgi` rolling mean; `xa` is a component of
  `xgi`, so both rolling means carry substantial shared information (G-EDA6-02: xa rolling mean
  found redundant with xgi rolling mean)
- Using `xgc` rolling mean as an individual player feature without annotating it as team-scope

**Common failure modes (estimate — Context):**
- Rolling or lagging `fdr_avg` as if it represents a form trend; fixture difficulty is a
  property of the upcoming fixture set, not the player's history

---

## 4. Behavioral Profile Framework

EDA characterises each signal's behavioral profile across the player-gameweek population.
The following profiles are the standard vocabulary for EDA findings and for representation
justification. Each profile has specific implications for what representations are supported
or discouraged.

### persistence

**What it means:** The signal maintains analytical association with total_points across multiple
consecutive gameweeks. High autocorrelation and sustained information across time lags.

**Supports:** Rolling windows; the window aggregates a signal that carries forward. Longer
windows may be appropriate.

**Discourages:** Raw-only representation; a single gameweek observation captures less than the
accumulation. Overly short windows may underuse available information.

---

### sparsity

**What it means:** A high proportion of player-gameweek observations are zero. The signal
fires rarely in the population. Examples: `penalties_saved` (near-zero almost every gameweek
for all players), `goals_scored` for defenders.

**Supports:** Raw representation (preserves the rare non-zero event); lagged value; positional
stratification (the signal may be dense for a sub-population).

**Discourages:** Rolling mean (averages the rare event with a sequence of zeros; the resulting
column is structurally near-zero with rare fractional values, removing the spike distinction).
In practice, sparsity can make a semantically admissible rolling mean analytically inadmissible.

---

### burstiness

**What it means:** Signal values arrive in concentrated spikes rather than distributing
gradually over time. High per-event magnitude relative to background level. Related to
sparsity but distinct: a bursty signal may not be sparse if the player accumulates many events
over a season, but individual gameweeks show extreme values.

**Supports:** Raw or lag representations; the spike itself is the signal. Event-indicator
derived representations (did the event occur this gameweek).

**Discourages:** Rolling mean (smoothing disperses the spike value across surrounding zero or
low-value periods; the mean no longer identifies when the burst occurred).

---

### volatility

**What it means:** High week-to-week variance in the signal relative to its mean. The signal
fluctuates substantially across consecutive gameweeks.

**Supports:** Rolling mean (reduces high-frequency noise and exposes underlying level); median
over window (more robust to extreme values).

**Discourages:** Relying on the most recent single-gameweek value as representative of the
player's level. However, check whether volatility is regime-driven (see regime sensitivity)
before applying a long smoothing window.

---

### redundancy

**What it means:** The signal carries information that is substantially shared with another
signal already in the representation set. Removing the redundant signal does not reduce the
information available for decision support.

**Supports:** Exclusion of the redundant signal from the representation set. The surviving
signal covers the information content.

**Discourages:** Including both signals on the grounds that they are "different" at the
ontological level. `xa` and `xgi` are both Process estimates, but `xa` is a component of
`xgi`, and their rolling means share most of their shared information (G-EDA6-02).

Note: redundancy is a relationship between signals, not a property of a single signal. If a
signal is found redundant in EDA, its transforms are also excluded — re-introducing `xa_roll3`
under a different label does not escape the redundancy finding.

---

### decay

**What it means:** Analytical relevance degrades rapidly as the window extends beyond a short
lag. A 1-game lag may carry more information than a 5-game rolling mean.

**Supports:** Short windows (roll3 over roll5); recent-lag representations.

**Discourages:** Long rolling windows; these dilute the recent, relevant signal with older,
less relevant observations.

---

### exposure dependence

**What it means:** The signal value is partly a function of playing time (minutes) rather than
skill or performance quality. A player who played 90 minutes will accumulate more xgi than the
same player who played 20 minutes, all else equal.

**Supports:** Per-90-minute normalised representations; minutes-conditioned analysis;
stratification by appearance threshold.

**Discourages:** Raw count or sum representations used as direct quality proxies without
accounting for the minutes confound.

---

### regime sensitivity

**What it means:** The signal's behavioral characteristics change across season phases — early
gameweeks (GW1-10), mid-season (GW11-28), and late season (GW29-38) may show different
distribution shape, sparsity, or autocorrelation structure.

**Supports:** Phase-stratified analysis; awareness that rolling window performance evaluated
across the full season may not reflect performance in specific phases; shorter, more adaptive
windows when regime changes are identified.

**Discourages:** Single aggregate evaluation as sufficient evidence for a fixed-window rolling
representation; a roll5 that works well mid-season may underperform in GW1-5 due to cold-start
and in GW35+ due to rotation effects.

---

## 5. Representation Decision Matrix

A representation proposal has a formal outcome based on the combination of admissibility
gate and behavioral justification gate results.

### Outcomes

**APPROVED**
Semantically admissible (temporal type and family permit the transform) AND behavioral evidence
from EDA supports the transform (persistence, distribution density, and analytical relevance
justify the aggregation). The representation may be materialized in STATE.

**REJECTED-SEMANTIC**
The transform is inadmissible based on temporal type or family classification. EDA findings are
not consulted. This is a hard stop. The decision is recorded with the specific admissibility
rule that applies.

**REJECTED-BEHAVIORAL**
The transform is semantically admissible but EDA evidence does not support it. The transform
does not improve over raw or an alternative representation, or the signal's behavioral profile
(sparsity, burstiness, redundancy) makes the transform counterproductive. The decision is
recorded with the specific behavioral finding.

**CONDITIONAL**
Approved with documented constraints. The transform is valid for a subset of the signal's
population (e.g., specific positions, specific window ranges, specific season phases). Usage
outside the conditional boundary is treated as REJECTED-BEHAVIORAL.

---

### Concrete Examples

**`xgi` rolling mean — APPROVED**
`xgi` is a Process family, estimate temporal type, individual scope. Rolling mean is
semantically admissible. EDA confirms persistence across consecutive gameweeks, sufficient
distribution density (xgi is non-zero in the majority of relevant player-gameweek rows for
attacking players), and association strength with total_points. Approved for materialization.
Conditional on position — expected to perform differently for GKPs vs outfield.

**`xa` rolling mean — REJECTED-BEHAVIORAL**
`xa` is a Process family, estimate temporal type. Rolling mean is semantically admissible.
However, G-EDA6-02 established that `xa_roll` is substantially redundant with `xgi_roll`,
since `xa` is a direct component of `xgi`. The rolling mean of `xa` contributes no independent
information beyond what `xgi_roll` captures. Rejected at the behavioral justification gate.
Applying this finding: `xa_roll3` and `xa_roll5` are excluded from STATE.

**`penalties_saved` rolling mean — REJECTED-BEHAVIORAL (expected)**
`penalties_saved` is an Event family, count temporal type. Rolling mean is semantically
admissible. However, the signal is structurally sparse — penalties occur rarely in the
population, and most player-gameweek rows for GKPs are zero. A 5-game rolling mean produces a
column that is near-zero for nearly all rows, with the rare penalty event dispersed across a
fractional value over the window. The rolling mean removes the spike distinction without
providing a stable level. Pending EDA confirmation, expected outcome is REJECTED-BEHAVIORAL.
Raw value and lag are the appropriate representations.

**`fdr_avg` rolling mean — REJECTED-SEMANTIC**
`fdr_avg` is a Context family signal. Context signals are fully determined pre-match and
describe a fixture property, not a player's temporal trajectory. Temporal aggregation of any
kind is inadmissible regardless of the estimate temporal type. A rolling mean of `fdr_avg`
would represent "average recent fixture difficulty," which is not a property of the upcoming
decision context. Hard stop at the admissibility gate.

**`ownership_count` rolling mean — REJECTED-SEMANTIC**
`ownership_count` is a Market family, stock temporal type. Rolling mean is inadmissible for
stock signals — averaging a point-in-time level over multiple periods has no coherent
interpretation as either a stock or a flow. The admissible transform for `ownership_count` is
the delta (change in level between periods), which represents net transfer flow and is
analytically meaningful as a market momentum signal. The rolling mean proposal is rejected at
the admissibility gate.

---

## 6. Representation Categories

The system produces several distinct classes of representations. Each class has a defined
purpose, allowed operational scope, and a defined location in the pipeline.

### State representations

Temporal transforms of Event, Process, and Participation signals. Rolling means, rolling sums,
and lags. These representations characterise a player's recent behavioral trajectory on
football-relevant signals.

**Purpose:** Capture form, persistence, and recent trend for decision support.
**Allowed usage:** Direct input to scoring and decision modules after evaluation.
**Belongs in STATE:** Yes, as derived columns with behavioral metadata.
**Directly operationally consumable:** Yes, after evaluation and lifecycle approval.

---

### Context labels

Fixture properties attached to a gameweek row: `fdr_avg`, `fdr_max`, `fdr_min`, `was_home`,
`fixture_count`. Fully determined pre-match. Not derived from player action.

**Purpose:** Provide match-context conditioning for evaluation and decision support; not
analytical features of player form.
**Allowed usage:** As moderators or conditioning variables; not as rolling analytical features.
**Belongs in STATE:** Yes, as raw labels — no temporal transforms applied.
**Directly operationally consumable:** Yes, in their raw form as fixture descriptors.

---

### Exposure representations

Minutes-based availability signals. Raw `minutes`, rolling mean of minutes, and threshold
derivatives (e.g., the >= 60 minutes FPL bonus threshold).

**Purpose:** Characterise playing time availability; condition other signal representations;
support availability forecasting.
**Allowed usage:** Directly as availability signals; as denominators for exposure-normalised
representations; as selection filters.
**Belongs in STATE:** Yes.
**Directly operationally consumable:** Yes, after evaluation.

---

### Market movement representations

Transfer flow signals: `transfers_in`, `transfers_out`, and delta of `ownership_count`.
Point-in-time counts or deltas.

**Purpose:** Characterise FPL manager sentiment and aggregate transfer behavior.
**Allowed usage:** As population-scope market signals; scope annotation required — these are
not individual football signals.
**Belongs in STATE:** Yes, with explicit population scope annotation.
**Directly operationally consumable:** Yes, after evaluation; scope annotation must accompany
any operational use.

---

### Structural labels

`purchase_price` and tier-derived representations. Static or slow-changing structural
system values.

**Purpose:** Provide structural conditioning for budget and selection constraints; not
analytically informative of performance.
**Allowed usage:** As categorical or ordinal conditioning; not as an analytical signal of
future points.
**Belongs in STATE:** Yes, as a label with stock type annotation.
**Directly operationally consumable:** Yes, as a constraint variable in selection logic.

---

### Leakage-risk representations

`bonus` and `bps`. Both are determined from in-match outcomes and computed after the match
concludes. Using these as analytical inputs for total_points in the same gameweek introduces
information leakage.

**Purpose:** Valid for historical pattern analysis when leakage is explicitly controlled;
not valid as pre-match decision inputs.
**Allowed usage:** Historical analysis only, with explicit leakage annotation. Must be excluded
from any study or operational use that simulates pre-match decision conditions.
**Belongs in STATE:** Yes, with leakage_risk annotation in column metadata.
**Directly operationally consumable:** No — excluded from operational scoring and decision
modules without explicit leakage-controlled study design.

---

## 7. STATE Materialization Rules

### No blanket transforms

Every column in STATE that represents a transform of a raw signal requires documented passage
through both the admissibility gate and the behavioral justification gate. A column that lacks
gate citations in its metadata is non-compliant.

### Mandatory column metadata

Every STATE column carries `_COLUMN_META` with the following fields:

- `scope` — Individual, Team, or Population
- `temporal_type` — the temporal type of the source signal
- `causality` — whether the value is pre-match determined or post-match computed
- `behavioral_reason` — the EDA finding that justifies the representation (or 'n/a' for
  raw labels)
- `source_gate_decisions` — citation to the admissibility ruling and behavioral validation
  study that approved the column
- `leakage_risk` — annotated if the column carries post-match information

### Team-scope signal attribution

`xgc`, `clean_sheets`, and `goals_conceded` are team-scope signals. They appear in
player-gameweek rows because all eligible players on the team share the value. The column
metadata must record `scope: Team`. Analytical use of these signals must account for the
within-team correlation structure.

### Leakage annotation

`bonus` and `bps` columns must carry `leakage_risk: in_match_allocation`. Any study design
or operational module that consumes these columns must explicitly acknowledge the leakage
annotation.

### Warmup documentation

Rolling window columns over a window of N gameweeks have undefined or unreliable values in
the first N-1 gameweeks of a season. Column metadata must document the warmup period. Analyses
that include early-season rows must either exclude warmup rows or explicitly account for reduced
window coverage. GW block stability evaluation should flag warmup-affected blocks.

### Redundant signal exclusion

If a signal is found redundant in EDA (e.g., `xa` relative to `xgi`), its transforms are also
excluded. Redundancy applies at the signal level and propagates to all derived representations
of that signal. Re-introducing a redundant signal's transform under a modified label (e.g.,
`xa_roll3` as "short-window assist proxy") is not permitted without a new gate decision that
explicitly revisits the redundancy finding.

---

## 8. Evaluation Governance

### Gate entry requirement

Representations enter evaluation only after both the admissibility gate and the behavioral
justification gate have been passed. Evaluating a semantically inadmissible or behaviorally
unjustified representation produces findings that cannot be acted upon and contaminates the
study record.

### Robustness standard

Evaluation validates robustness across three dimensions:

1. **rho_pooled** — Spearman correlation with total_points across the full evaluation sample.
2. **95% CI** — Confidence interval around rho_pooled; a representation with a wide CI
   centered near zero does not meet the standard.
3. **GW block stability** — rho computed separately across early, mid, and late season blocks.
   A representation that performs well in aggregate but collapses in specific phases is
   conditionally approved at best.

Aggregate rho alone is not sufficient for evaluation approval.

### Supplementary evaluation outputs

rho_pooled captures whether association exists across the population. It does not reveal
where in the rank distribution the discriminative power sits — a representation can achieve
rho=0.30 by separating median performers while providing near-zero discrimination at the
tails where FPL decisions concentrate. Two supplementary outputs are required alongside
rho for every lens study evaluation:

**Quintile EV lift** — E[total_points | quintile] ± SD for Q1 through Q5, per signal per
position. Reports expected return and within-bin variance per quintile. Required because two
representations with identical rho can have radically different within-bin variance and
Q5-Q1 absolute gaps — both of which matter operationally.

**Haul identification rate** — fraction of top-10%-within-position outcomes falling in the
top signal quintile versus the 20% base rate. Threshold is position-relative (top 10% of
DEF returns, top 10% of MID returns separately) — not an absolute points cutoff. A
representation that correctly places haul outcomes in the top quintile at a rate meaningfully
above base rate demonstrates tail discrimination that rho cannot surface.

### Lifecycle states

Representations progress through a defined lifecycle:

`candidate` → `lens-evaluated` → `synthesis-eligible` → `operationally-approved` → `deprecated`

- **candidate**: admissibility and behavioral gates passed; awaiting evaluation.
- **lens-evaluated**: evaluation study complete; findings recorded.
- **synthesis-eligible**: evaluation robustness sufficient for inclusion in synthesis studies.
- **operationally-approved**: sufficient evaluation evidence to permit operational consumption.
- **deprecated**: previously approved but no longer current; must be formally deprecated with
  a gate decision documenting the reason.

### Deprecation

A representation that passed evaluation but loses relevance in new data — or is superseded by
a better representation — must be formally deprecated. Silent removal (deleting a STATE column
without a gate decision) is not permitted. The deprecation record must state why the
representation was removed and what, if anything, replaces it.

### Evaluation findings do not redefine ontology

If a representation fails evaluation, that is a behavioral finding about the signal's
analytical relationship with total_points. It is not evidence that the ontology classification
was wrong. `xa` failing as an independent representation does not mean it should be
reclassified from Process to a different family. Ontology and evaluation findings are separate
layers with separate concerns.

---

## 9. Operational Governance

### Consumption restriction

Operations — `intelligence/scoring/` and `intelligence/decision/` — consume only representations
with `operationally-approved` lifecycle state. Consuming a `lens-evaluated` or
`synthesis-eligible` representation operationally is a governance violation.

### Threshold provenance

Every hardcoded threshold in operational modules must either:

1. **Cite an evaluation finding** — the specific study, the rho_pooled and CI, and the block
   stability result that informed the threshold.
2. **Be labeled explicitly as provisional-editorial** with the date it was set and an owner.

A threshold without a source is operationally non-compliant. Provisional-editorial thresholds
require periodic review and cannot persist indefinitely as if they were evaluation-derived.

### No ad hoc representations

Operational modules cannot create analytical representations that have not passed through the
governed pipeline. If a developer determines that a new transform would improve a decision
module, the correct path is: ontology check → admissibility check → EDA → representation
validation → STATE materialization → evaluation → operational approval. Shortcutting this
pipeline by computing a transform inline within an operational module is not permitted.

### Editorial weighting

Where scoring or decision logic applies weights that are not derived from evaluation findings,
those weights must be explicitly marked with `editorial` status and the date of last review.
Editorial weights are distinguished from evaluation-derived weights in all documentation and
in code comments. Mixing the two without labeling creates ambiguity about what the system
actually knows vs what it has assumed.

---

## 10. Anti-Patterns

**Blanket rolling windows**
Applying `roll3` and `roll5` to every signal in the pipeline without checking temporal type,
family, or behavioral profile. `roll5` of `ownership_count` and `roll5` of `fdr_avg` are both
inadmissible. `roll5` of `penalties_saved` is admissible but behaviorally unjustified. The
fact that a rolling function is easy to apply is not a reason to apply it uniformly.

**Ontology as documentation-only**
The signal-ontology.yaml exists but the admissibility constraints encoded in temporal type and
family are not consulted during transform decisions. Code materializes columns based on
engineering convenience rather than semantic governance. The ontology must be the first
reference for any transform proposal — not an artifact that sits in docs/ and is read once.

**Transform-first architecture**
Designing the full transform pipeline (roll3, roll5, lag1, delta) before studying signal
behavior. Behavioral evidence must precede transform selection, not follow it. Transform-first
architecture produces columns that are technically computable but analytically unjustified.

**EDA-as-justification without admissibility**
Running an EDA study on a semantically inadmissible transform (e.g., rolling mean of
`ownership_count`) and treating a positive rho as approval. Admissibility is assessed before
EDA. A correlation result does not override a semantic constraint.

**Smoothing sparse burst events**
Computing rolling mean on `penalties_saved`, low-frequency assists for non-attacking players,
or other structurally sparse signals. The rolling mean is dominated by zeros. The result does
not smooth noise — it dilutes the rare meaningful observation into a column that is effectively
zero most of the time, with occasional fractional values that no longer mark when the event
occurred.

**Mixing context labels with state**
Treating `fdr_avg`, `was_home`, or `fixture_count` as form signals subject to temporal
transforms. These are fixture properties. Rolling `fdr_avg` does not represent a player trend.
Context labels belong in STATE as raw labels, not as inputs to rolling transform pipelines.

**Operational bypass**
Hardcoded weights, thresholds, or signal combinations in `intelligence/scoring/` or
`intelligence/decision/` that have no evaluation provenance and no editorial label. These
represent analytical assumptions that are invisible to governance. Any value that affects a
decision output must be traceable.

**Redundant signal re-entry**
`xa` removed from independent representation because it is redundant with `xgi` (G-EDA6-02).
Subsequently, `xa_roll3` introduced under the framing "short-window assist proxy." This is the
same signal, with the same redundancy, under a different name. Redundancy findings apply to
all transforms of the signal, not only the specific form tested in the study.

**Warmup blindness**
Using `roll5` values from GW1 through GW4 without flagging that these values are computed
over fewer than 5 observations. In GW2, a `roll5` is actually a `roll1`. Treating these as
equivalent to mid-season roll5 values in analysis or scoring introduces a systematic early-
season bias that is invisible without warmup documentation.

---

## 11. Minimal Viable Governance

### Must exist now

- **Ontology YAML** (`docs/foundations/signal-ontology.yaml`) — done; 23 signals classified.
- **EDA coverage map** with behavioral classifications per signal — in progress; findings
  accumulated in `studies/eda/findings/` as studies are completed.
- **Representation governance document** (this document) — done.
- **Representation rules per signal family** (`docs/foundations/representation-rules.md`) —
  Phase 3; specifies per-family admissible transform sets and common conditional constraints.
- **STATE column metadata** (`_COLUMN_META`) — every materialized column must carry scope,
  causality, behavioral_reason, and source_gate_decisions. This is the minimum traceability
  requirement.
- **Schema guard** — a test or validation layer that enforces only approved columns are
  present in STATE; rejects columns without metadata; prevents operational bypass.

### Can wait

- Formal lifecycle state machine implementation — the lifecycle vocabulary is defined; a
  formal implementation (state transition enforcement in code) can follow once the
  representation set stabilises.
- Automated admissibility checking from ontology — the YAML encodes the constraints; automated
  enforcement against proposed transforms is valuable but requires tooling investment that can
  follow after governance discipline is established manually.
- Full evaluation metadata per signal-position pair — Phase 6; currently aggregate rho is
  sufficient for initial gates; positional stratification follows.

### Do not overengineer

This is not a feature store. There is no automated transform generation pipeline. There is no
orchestration layer that produces representations on a schedule. There is no ML training loop
consuming these representations. This is a governed analytical representation system for
decision support. The governance exists to keep analytical decisions traceable and defensible.
Infrastructure beyond what is needed for that purpose is waste.

---

## Changelog

| Version | Date | Notes |
|---|---|---|
| 1.0 | 2026-05-24 | Initial document |
