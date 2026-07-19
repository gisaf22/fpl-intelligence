# EVAL_DESIGN.md
# Analytical Methodology — Evaluation Framework

**Status:** ACTIVE
**Last updated:** GW 34, April 2026
**Owned by:** research/evaluation/

---

## 1. Purpose

This document defines what success looks like for the fpl-intelligence
methodology. It is written before results are known. It cannot be
revised retrospectively to suit outcomes.

Every design decision in the lens studies, synthesis, and experiments
is evaluated against this document. If a finding does not connect to
a question here, it is not an evaluation finding — it is a descriptive
observation.

---

## 2. The system question

> What information, available before a gameweek, reliably associates
> with FPL returns in decision-relevant contexts — and how should
> that information be characterised to support transfer, captaincy,
> and chip decisions?

This is a descriptive and diagnostic question. The system does not
prescribe decisions in its current form. It characterises signals
and surfaces evidence. The manager decides.

---

## 3. What this season is and is not

### 2025-26 is the development season

The system was not used to make live decisions this season. All FPL
decisions were made independently of system outputs. This is an
honest constraint that shapes what evaluation can and cannot claim.

**What 2025-26 can tell us:**

- Whether confirmed signals associate with returns in the population
  (bivariate rank correlation analysis, Spearman)
- Whether signals combine to outperform individual signals
  (synthesis study — SYNTH-01)
- Whether signal behaviour is consistent across temporal regimes
  (GW block stratified analysis — early, mid, late season)
- Whether backtesting simulations show signal discrimination
  in decision-relevant contexts (captaincy, transfer simulations)
- Whether the methodology is internally valid and defensible
  at every design decision point

**What 2025-26 cannot tell us:**

- Whether using the system improves live decision quality
- Whether the system would have improved mini-league outcomes
- Whether signal associations will hold in 2026-27
- Whether the prescriptive layer, when built, will perform

These claims require a live evaluation season. That is 2026-27.

### 2026-27 is the first evaluation season

From GW 1 next season, decisions informed by system outputs are
logged. Evaluation is live and retrospective simultaneously.
The decision tracking protocol is defined in Section 7.

---

## 4. Success criteria — 2025-26 analytical validation

The methodology is considered analytically valid for 2025-26 if
all of the following are met.

### 4.1 System EDA completed

All seven EDA layers executed and findings documented in
research/eda/findings/EDA_FINDINGS.md.

EDA-0 data integrity passed — lag alignment confirmed, rolling
window construction verified, no leakage detected.

Each gate decision documented with the EDA finding that produced it.

### 4.2 Lens studies internally valid

Each lens study (LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW,
LENS-AVAIL) satisfies:

- Population defined and justified by EDA-3 findings
- Signal set pruned by EDA-2 and EDA-3 before correlation runs
- Method choice (Spearman rank correlation) justified by EDA-1
  and EDA-3 distributional findings
- Bootstrap 95% confidence intervals reported per signal
- Signal status (informative / uninformative) determined by
  whether CI crosses zero — not by rho magnitude alone
- Signal strength and temporal consistency described alongside
  binary classification — signals exist on a spectrum and
  rho magnitude, CI width, and GW block stability are all
  reported even when the binary gate is passed
- All design decisions traceable to a documented EDA finding
  or an explicit a priori decision with stated rationale
- Decision relevance confirmed — a signal is only considered
  decision-relevant if it demonstrates meaningful separation
  in outcome distributions across ranked groups (quintile bins
  or rank bins), not solely statistical association. A signal
  can pass the CI gate and still fail decision relevance if
  the outcome distributions across bins are not meaningfully
  separated.
- Practical meaningfulness confirmed — a signal is only
  considered practically meaningful if the effect size produces
  consistent and observable separation in decision-relevant
  bins across GW blocks, not just in aggregate. Separation
  that holds in one GW block but not others is flagged as
  conditionally informative, not practically meaningful.

### 4.3 Signal registry fully populated

SIGNAL_REGISTRY.md contains every candidate signal with:

- Lifecycle stage current as of SYNTH-01 completion
- Lens status confirmed
- Synthesis status confirmed
- Known caveats documented
- No signal promoted to synthesis without a confirmed lens status

### 4.4 Synthesis study defensible

SYNTH-01 design must be locked and explicit before synthesis
runs. The SYNTH-01 design document must specify rank
normalisation method, weighting scheme, and whether signal
interactions are included or excluded. These decisions cannot
be made post-hoc. EVAL_DESIGN does not reproduce implementation
detail — that lives in research/synthesis/synth-01/SYNTH_DESIGN.md.
The requirement here is that the document exists and is locked
before any synthesis code runs.

SYNTH-01 answers the three core questions:

- Does combining form and fixture signals outperform either alone?
  (additive combination — rank normalised composite score)
- Does fixture difficulty condition the form signal?
  (stratified analysis by fixture tercile)
- Do market signals add independent information beyond form
  and fixture? (partial correlation analysis)

Each finding is traceable to the combined dataset EDA
(research/eda/notebooks/eda_sd_combined.ipynb).

Synthesis success requires consistency across GW blocks —
not just aggregate improvement. A combined signal that
outperforms individual signals in aggregate but is driven
by a single temporal segment is not considered a valid
synthesis finding. Block-level results must be reported
alongside aggregate results for every synthesis finding.

### 4.5 Backtesting simulations completed

Minimum two simulation experiments executed:

EXP-SIM-CAPTAIN — does top-ranked player by composite score
historically discriminate captaincy returns versus the most
owned player? Null condition: random positional selection.

EXP-SIM-TRANSFER — does form and fixture quintile combination
historically identify outperforming transfers? Null condition:
ownership-weighted selection.

Both reported with formal terminology — historical simulation,
null condition, observed return distributions, effect size.

Simulations must clear two thresholds to be considered
non-trivial. First, outperform random positional selection
(null condition). Second, outperform the naive baseline
defined in Section 6 — ownership-weighted or lag-1 raw
total_points depending on simulation type. Clearing random
alone is a weak result. Both thresholds must be cleared.

Simulation candidate selection must not be conditioned on
the evaluated signal in a way that inflates performance.
If the signal is used to select which players enter the
simulation, the simulation is circular. Candidate pools
are defined by population and position filters only —
not by signal values — before signal rankings are applied.

### 4.6 Limitations honestly documented

Every lens study, synthesis document, and experiment contains
an explicit limitations section covering:

- Known signal distortions (what the lens cannot see)
- Population constraints (what the filter excludes)
- Temporal scope (2025-26 only, not a generalisable claim)
- What the finding does not support

---

## 5. Success criteria — 2026-27 decision evaluation

This section is intentionally deferred.

2026-27 is the first live evaluation season — where decisions
are made using system outputs and tracked against outcomes.
The decision tracking protocol, transfer metric, captaincy
metric, and mini-league framing all belong in a separate
document written when the predictive layer is designed and
ready to use.

Document to be created: research/evaluation/EVAL_DESIGN_2627.md
Trigger: when SYNTH-01 is complete and the combined signal
score is validated for use as a ranking input.

Nothing in this document prejudges what 2026-27 evaluation
will look like. That design happens after this season's
analytical validation is complete.

---

## 6. Baseline definitions — 2025-26

Signal rho is compared against two baselines.

**Null baseline:** rho of zero. CI crossing zero means the
signal is uninformative — it cannot be distinguished from
noise in the population. This is the minimum gate.

**Naive baseline:** lag-1 raw total_points versus roll-5
smoothed signal. Does smoothing over five gameweeks add
information beyond the simplest possible form signal?
If roll-5 rho approximates lag-1 raw rho, the smoothing
adds complexity without adding signal.

Backtesting simulations use a null condition of random
positional selection. This is the floor the simulation
must clear to be considered non-trivial.

---

## 7. What this evaluation cannot claim

This section exists so findings are not overstated.

**Signal associations are descriptive, not predictive.**
A rho of 0.33 for MID xgi_roll5 describes what happened in
the 2025-26 population. It does not guarantee the signal will
associate with returns in 2026-27 at the same magnitude.

**Backtesting does not prove forward performance.**
Historical simulations show what would have happened under
a signal-based selection rule. They do not prove what will
happen. Overfitting to 2025-26 conditions is a known risk.

**This season cannot evaluate decision quality.**
No live decisions were made using system outputs in 2025-26.
Any claim that the system would have improved transfer or
captaincy decisions is a retrospective simulation finding,
not a live evaluation result. The distinction matters.

**The methodology describes one season.**
2025-26 is the population. Findings are not generalisable
to future seasons without replication. Signal associations
may decay, player compositions change, and competitive
conditions differ year to year.

---

## 8. Failure definitions

The system is considered analytically or operationally failed
if one or more of the following conditions are met.

Failure conditions are stated here before results are known.
They cannot be revised retrospectively.

### 8.1 Analytical failure

**Catastrophic failure — no meaningful signal extracted:**
- No signals meet the informative threshold (CI excludes zero)
  across any position in any lens study
- Signals classified as informative fail redundancy checks
  (EDA-3 shows high inter-signal correlation — same construct
  reported twice under different names)
- Backtesting simulations fail to outperform both the null
  condition and the naive baseline in both simulations

**Practical failure — technically valid but decision-useless:**
- Signals pass the CI gate but effect sizes are small relative
  to within-population variance — rho values are non-zero but
  provide negligible discrimination
- Signal behaviour is inconsistent across GW blocks with no
  coherent explanation traceable to football structure
- Quintile bin analysis shows no meaningful separation in
  outcome distributions across ranked groups — signals pass
  the correlation gate but fail the decision-relevance gate
- Combined signals in SYNTH-01 do not outperform the best
  individual signal from any single lens

A system in practical failure is not analytically wrong —
it is analytically weak. Findings are reported honestly
as low-discrimination signals rather than suppressed.

Observable criteria for "indistinguishable from noise":
- Effect sizes small relative to population return variance
- No consistent directional pattern across GW blocks
- Outcome distributions across quintile bins overlap
  substantially with no clear monotonic separation

Interpretation: the methodology extracts signal that is
statistically detectable but practically non-discriminating.

### 8.2 Methodological failure

- EDA-0 fails — lag misalignment or leakage detected and
  not resolved before any study runs
- Key design decisions cannot be traced to EDA findings
  or documented a priori rationale
- Population definition introduces bias that invalidates
  cross-position or cross-GW comparisons
- Signal registry is incomplete or inconsistent with
  lens study outputs at time of SYNTH-01

Interpretation: the system is not internally valid
regardless of results.

### 8.3 System-level failure

- Signals do not survive synthesis — no additive or
  independent contribution confirmed in SYNTH-01
- Combined signal does not improve player discrimination
  beyond the best individual lens signal
- Evaluation cannot distinguish system performance from
  noise across the 2025-26 population

Interpretation: the system fails as an integrated methodology
even if individual lens components appear valid in isolation.

---

## 9. Signal registry feedback loop

Evaluation findings update signal status in SIGNAL_REGISTRY.md.
Three outcomes are possible per signal per evaluation stage.

**Promoted** — signal survives evaluation at this stage.
Advances to the next lifecycle stage. Lens status confirmed,
synthesis status confirmed, or decision-level value confirmed.

**Demoted** — signal fails evaluation at this stage.
Removed from active use. Reason documented. Signal is not
deleted from the registry — demotion is a finding, not an
erasure. Demoted signals require explicit re-entry justification
to return to active use. Re-entry requires a documented change
in signal definition, population, or evidence base. A demoted
signal cannot re-enter synthesis under a different name or
minor reformulation without this justification documented
in the registry. Undisciplined re-entry is treated as a
methodological failure.

**Conditional** — signal shows value in specific contexts
but not universally. Marked with conditions for use.
Example: xgi_roll5 informative for MID and FWD but not GK.
Conditional signals enter synthesis and experiments with
explicit scope constraints documented in the registry.

Registry update timing:
- After each lens study completes — lens status updated
- After SYNTH-01 completes — synthesis status updated
- After each experiment completes — experiment finding logged
- After 2026-27 season ends — decision-level status updated

**Provenance (ADR-009 Phase C).** `evaluation_metadata.yaml` — the scoring
decision-of-record — is **machine-generated, not hand-authored**. Each lens
study emits `evidence.yaml` (computed statistics) next to its
hand-authored `annotations.yaml` (judgment: lifecycle/leakage/behavioral_reason/
not_applicable) under `research/families/*/validate/`;
`model/governance/generate_evaluation_metadata.py` merges those with
`model/assemble/synth01_decisions.yaml` to (re)produce the YAML. Do not edit the
YAML by hand — change the verdict records and regenerate; a drift-guard test
(`tests/test_generate_evaluation_metadata.py`) fails if they diverge.

---

## 10. Evolution path

```
2025-26   Descriptive and diagnostic
          Signal characterisation, synthesis, backtesting
          Evaluation: analytical validity only

2026-27   Predictive layer added
          Combined score becomes a ranking
          Ranking surfaces captaincy and transfer candidates
          Evaluation: decision metric tracking begins

2027-28   Prescriptive layer if predictive validates
          Explicit recommendations with confidence signals
          Chip timing model if evidence base supports it
          Evaluation: full decision attribution analysis
```

No layer is skipped. Each earns the next through documented
evidence, not ambition.

---

## 12. Residual risks — post-design lock

This document removes design-level ambiguity and bias. However,
no analytical system is risk-free. The following residual risks
remain and are acknowledged explicitly so that failures are
correctly interpreted.

These risks do not invalidate the methodology. They define where
failure can still occur despite a sound design.

### 12.1 Execution risk

**What it is:** Risk that implementation does not faithfully
reflect the documented methodology.

**Why it exists:** This document specifies what should be done,
not what the code actually does. Errors can occur in lag
alignment, rolling window construction, population filter
application, and dataset joins and spine construction.

**Impact:** Can produce incorrect results that appear valid
unless explicitly checked. Mitigated by EDA-0 but not
eliminated. EDA-0 is a gate, not a guarantee.

### 12.2 Measurement risk

**What it is:** Risk arising from interpretation of partially
subjective evaluation criteria.

**Why it exists:** Some evaluation concepts are intentionally
not reduced to hard thresholds — meaningful separation in
quintile analysis, small relative to variance, distributional
pattern assessment. These require analytical judgement rather
than binary rules.

**Impact:** Different analysts could reach slightly different
conclusions from the same evidence. This is a known limitation
of descriptive statistical evaluation, not a design flaw.

### 12.3 Signal reality risk

**What it is:** Risk that the underlying data does not contain
strong, stable, or decision-useful signals.

**Why it exists:** The methodology tests for signal existence.
It does not assume it.

**Impact:** Signals may be weak, unstable, or non-existent.
The system may enter practical failure despite being correctly
built and correctly executed. This is a valid outcome, not a
methodological failure. A null result is informative.

### 12.4 Under-exploration risk

**What it is:** Risk that strict design constraints limit
discovery of niche or context-specific signals.

**Why it exists:** The system prioritises pre-commitment,
avoidance of overfitting, and controlled signal entry.
This reduces flexibility for exploratory discovery.

**Impact:** Signals valid only in narrow contexts may be
missed. Weak global signals with strong local behaviour
may be underutilised. Partially mitigated by the conditional
signal status in the registry — signals with context-specific
value are documented rather than discarded.

### 12.5 Data scope risk

**What it is:** Risk arising from reliance on a single-season
population.

**Why it exists:** 2025-26 is treated as the full population
for this study. One season is one regime.

**Impact:** Findings may reflect season-specific dynamics.
Signal behaviour may not replicate in future seasons.
External validity is not established by this methodology
alone. Acknowledged in Section 7 and repeated here because
it is the most likely source of misinterpretation when
results are communicated.

---

### Summary

The methodology is designed to eliminate hindsight bias,
metric manipulation, and ambiguous success criteria.

The remaining risks are implementation correctness,
interpretive judgement, and inherent signal strength in
the data.

If the system fails under this framework, the failure can
be correctly attributed to one of three sources: the data,
the signal space, or the implementation. Not to a flaw
in evaluation design.

---

## 13. Document control

This document is written before results are known.
It is not revised to suit outcomes.

Permitted updates:
- Correcting factual errors in methodology description
- Adding limitations discovered during study execution

Not permitted:
- Changing success criteria after results are known
- Removing criteria that were not met
- Adding criteria retrospectively that were met

Any structural revision requires a new version with a
changelog entry and date.

| Version | Date | Change |
|---|---|---|
| 1.0 | April 2026 | Initial document — pre-results |
| 1.1 | April 2026 | Added failure definitions, registry feedback loop, signal strength nuance, decision metrics hierarchy, system question refined |
| 1.2 | April 2026 | Scoped to 2025-26 only — 2026-27 evaluation deferred to EVAL_DESIGN_2627.md. Title corrected. Removed decision tracking protocol and 2026-27 baselines |
| 1.3 | April 2026 | Strengthened backtesting thresholds. Added decision-relevance gate. Added synthesis reproducibility requirement. Split analytical failure into catastrophic and practical. Operationalised noise criteria |
| 1.5 | April 2026 | Four targeted gaps closed: practical meaningfulness threshold added to 4.2, synthesis GW block consistency required in 4.4, backtesting selection bias guard added to 4.5, signal re-entry control added to Section 9 |
---

## Appendix — code layout (predictive layer, 2026-07)

The predictive layer separates by role: **`model/eval/` measures, `model/forecast/` predicts.**

**`model/eval/`** — everything that *measures*, in three roles:
- **harness** (model-agnostic scorer): `population` (canonical / full_universe), `baselines`
  (naive reference bar + `base_season`), `metrics`
  (`grouped_spearman`, `block_bootstrap_ci`, `precision_at_k`, `ndcg_at_k`, `spearman_with_ci`),
  `scorer` (`GateResult` + `score_gate`/`score_gates` — within-position Spearman **with a
  block-bootstrap CI + coverage** — plus `best_baseline_per_position`, the per-position incumbent bar),
  `walkforward` (orchestration + `walk_forward_by_position`,
  the sole per-position benchmark; `score_predictions` for ad-hoc single-column metrics).
- **eval studies** (compose a model + the harness to answer one gated question): `calibration`,
  `captaincy_backtest`, `captaincy_diagnostics`.
- **notebooks/** — the runnable, question-driven per-stage walkthroughs.

**`model/forecast/`** — everything that *predicts* (fitted models): `component_forecast`,
`signal_combination`, `points_model`, `simulator`, plus the Phase-1 estimators
`level_estimators`, `shrinkage`.

**Load-bearing rule:** the **harness must stay model-agnostic** — it must not import
`model.forecast`. Eval studies *may* import forecast; `model/eval/__init__` exports only the
harness/baselines/scorer (never a study), which keeps `eval` and `forecast` free of an import cycle.

**Baselines vs models:** *baseline* = naive aggregate that defines the bar (lives in `eval`);
*model* = fitted predictor that tries to beat it (lives in `forecast`). Strength is irrelevant to
the split — `base_season` is a baseline even though it wins captaincy. Every ranking gate reports a
block-bootstrap CI so "beats the baseline" is always qualified by whether the CIs separate.
