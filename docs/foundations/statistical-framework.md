# Statistical Framework and Analytical Grounding

> **Status:** awareness document — gaps identified, not yet addressed.
> Captures the statistical architecture implicit in the codebase and benchmarks it
> against production analytical platform standards.

---

## 1. The Statistical Ladder

Every number this system produces sits at one of five rungs. The rung determines
what claim the number supports and what you are allowed to conclude from it.

```
Rung 1 — Descriptive
  "What happened in this data?"
  No claim beyond the rows you observed.
  Tools: mean, median, IQR, percentiles, block distributions.
  Code:  research/kernels/distribution.py
         research/kernels/stability.py → compute_signal_block_distributions

Rung 2 — Diagnostic
  "Why did this happen?"
  Still no inference — richer description of structure and cause within the data.
  Tools: block shift analysis, GW-window breakdown, panel decomposition.
  Code:  research/kernels/stability.py → assess_distribution_stability
         research/kernels/correlation/panel.py → split_between_within_player_rho

Rung 3 — Inferential
  "What is likely true beyond this data?"
  A claim that the pattern is not noise — requires an uncertainty estimate.
  Tools: bootstrap CI for Spearman rho.
  Code:  research/kernels/resampling.py → bootstrap_spearman_ci

Rung 4 — Hypothesis test / Decision rule
  "Given the inference, what decision do I make?"
  A binary verdict derived from a threshold applied to the inference.
  Tools: CI-excludes-zero gate, quintile decision relevance gate, GW stability gate.
  Code:  research/families/*/validate/study.py → _apply_signal_qualification_gates

  ── statistics ends here ──────────────────────────────────────────────────────

Rung 5 — Domain decision (lens)
  "Given the verdict, what do I do in FPL?"
  Not a statistical concept. The operationalisation of the verdict into action.
  Code:  evidence.yaml → governance → lens / decision_class
```

**Key rule:** you can only move up the ladder deliberately. A descriptive number
(median xgi_roll3) cannot be treated as an inferential number without running the
inference machinery. A predictive claim requires a lagged study design — the same
rho computed without a lag is descriptive/contemporaneous only.

---

## 2. Inference Frameworks

When you want to claim something is true beyond your observed data, you need an
inference framework. There are three.

### Frequentist — "how often would I be wrong?"

Imagine repeating your study many times with different data from the same process.
How often would your estimate be this far from zero if there were truly no
relationship? If rarely, conclude the association is likely real.

**Output:** p-value, confidence interval, reject/fail-to-reject null.

**What the CI means:** the range of rho values consistent with your data at the
chosen confidence level — NOT the probability that the true rho is in this range.

**This codebase uses frequentist inference throughout.**

Why: binary governance decisions (informative / uninformative) suit binary
frequentist verdicts. No prior knowledge needed. Auditable — every verdict follows
mechanically from data + threshold.

### Bayesian — "update your belief with evidence"

Start with a prior belief about how likely something is. Observe data. Update.
Output is a probability distribution over what is true.

**Output:** posterior distribution — e.g., "90% probability rho > 0.05".

**Where it would help here:** thin position slices (FWD, GK, ~40 rows). A
Bayesian approach could borrow strength from MID/DEF posteriors as a prior,
producing meaningful verdicts where the frequentist gate simply fails due to wide
CIs.

**Why not used:** requires justifiable, auditable prior choices. In a system that
ratifies verdicts into governance artifacts, the prior becomes a ratifiable
decision — who approved it, and why? That governance cost is currently avoided by
accepting that thin slices fail Gate 1 naturally.

### Analytical formulae — exact math under assumptions

Given known distributions and i.i.d. observations, derive exact CI formulas.
Faster than bootstrap, no simulation needed.

**Why not used here:** FPL panel data breaks the i.i.d. assumption. The same
player appears ~38 times per season. Analytical Spearman CI formulas assume
independent observations — using them would produce overconfident (too narrow) CIs.
Bootstrap bypasses this assumption by simulating uncertainty empirically.

---

## 3. Bootstrap — why it exists

Bootstrap (Efron, 1979) is a frequentist computational technique, not a separate
inference school.

**Core idea:** repeatedly resample your data with replacement, recompute your
statistic each time, observe how much it moves. The spread of that movement is
your uncertainty — no formula required.

**Why rho specifically triggers bootstrap, not mean:**

Describing a mean is a descriptive claim — no inference needed, no bootstrap.
Claiming a rho is non-zero and will generalise is an inferential claim — bootstrap
required. The trigger is the claim type, not the statistic type.

**Why MIN_N = 10:**

A crash floor to prevent degenerate edge cases (all-identical values → NaN from
`spearmanr`). It is not a power-justified sample size threshold. Signals with
genuine rho of 0.10 will fail Gate 1 reliably at thin positions because the CI is
too wide — this is the correct frequentist behaviour, not a bug. See gap #5 below.

---

## 4. Experimental Design — the layer before statistics

Experimental design determines whether the data you collect can actually answer
your question. No statistical method can fix a design flaw after the fact.

**Key design decisions in this codebase (made before any rho is computed):**

| Decision | Implementation | Justification |
|---|---|---|
| Lag | Signal at GW N, target at GW N+1 | Supports predictive claim — without lag, rho is contemporaneous only |
| Rolling window | 3-GW rolling average | Reduces single-GW noise; introduces lag artifact |
| GW exclusions | Exclude GW 1-2 for rolling signals | Rolling window undefined at season start |
| GW windows | Early (3-12), mid (13-26), late (27-38) | Tests temporal stability — repeated-measures analogue |
| Minutes filter | ≥ 60 min played | Reduces noise from bench appearances |
| Position stratification | Per-position study | Controls for structural point differences across roles |

**Critical:** the lag is a design decision, not a statistical one. Removing it
produces a valid rho that answers a different question — contemporaneous association
instead of predictive association. The lens verdicts would be arithmetically
correct but the predictive interpretation would be unsupported.

---

## 5. Where Hypothesis Testing Sits

Hypothesis testing is the decision rule layer between inference (rho + CI) and
action (lens verdict). It is not a separate inference framework.

**Classic form:**
- H₀ (null): rho = 0
- H₁ (alternative): rho ≠ 0
- Decision: reject H₀ if p < 0.05

**This codebase's equivalent — the three gates:**

```
Gate 1 — CI gate (= hypothesis test on rho)
  "ci_excludes_zero": bool(ci_lo > 0 or ci_hi < 0)
  Equivalent to: reject H₀ at the chosen confidence level.
  Fails → lens_status = uninformative

Gate 2 — Decision relevance gate (= hypothesis test on effect size)
  Quintile Q5–Q1 gap above threshold AND monotonic ordering.
  Asks: is the association large enough to matter for FPL decisions?
  Fails → lens_status = uninformative

Gate 3 — GW window stability gate (= repeated-measures consistency test)
  ≥ 2 of 3 GW windows show CI-excluding-zero association.
  Asks: is the signal reliable across the season, not just one phase?
  Fails → lens_status = unstable
```

The gates are hypothesis tests. They just don't use p-values — they use CI
exclusion of zero and threshold comparisons, which are more interpretable in a
governance context.

---

## 6. Where Lenses Sit

Lenses are above the statistical ladder entirely.

```
Statistics produces:  lens_status ∈ {informative, uninformative, unstable}
Governance produces:  decision_class ∈ {informative, uninformative}
                      (unstable collapses to uninformative)
Lens is:              the operationalisation of decision_class into FPL action
```

Statistics can confirm an association is real. It cannot determine whether a rho
of 0.18 is worth acting on given budget constraints, chip strategy, and 11
positions to fill. That is a domain decision — the lens layer's job.

---

## 7. Production Platform Standards — the benchmark

How teams at Netflix, Airbnb, Spotify, and similar organisations formalise their
analytical systems. Three layers:

### Layer 1 — Metric taxonomy

Every metric classified by the claim it supports before code is written:

| Type | Claim | Permitted conclusion |
|---|---|---|
| Descriptive | What happened in this data | None beyond the observed rows |
| Diagnostic | Why it happened | None beyond the observed rows |
| Predictive | What will happen | Requires lagged design + inference |
| Causal | What would happen if we intervened | Requires randomisation or causal identification strategy |

### Layer 2 — Study design specification (pre-analysis plan)

Written before results are seen, per study. Locks design choices so they cannot
be unconsciously shaped by results.

```
Estimand:         exact quantity being estimated
Estimator:        method and justification
Assumptions:      what must be true for the estimator to be valid
Failure modes:    what breaks if assumptions don't hold
Design decisions: lag, window, exclusion rules + rationale
```

### Layer 3 — Validity framework

Three validity types assessed per study:

| Validity | Question |
|---|---|
| **Internal** | Does the method correctly measure what it claims within this data? |
| **Construct** | Does the measure represent the concept it's intended to represent? |
| **External** | Does the finding generalise beyond this dataset / season? |

---

## 8. Gap Assessment — this codebase vs. production standards

**Strengths:**

- Statistical ladder implemented correctly in code (descriptive → inferential → hypothesis test → domain decision)
- Three-gate protocol is a valid multi-stage hypothesis test
- ADRs document major design decisions
- Governance layer correctly separates statistical verdict from operational decision
- Lag is present and correct
- Signal vocabulary (lens_status, decision_class) maps statistical output to domain decisions

**Gaps:**

| # | Gap | What's missing | Risk |
|---|---|---|---|
| 1 | No metric taxonomy | No document classifying each output by claim type | Descriptive metric used as predictive silently |
| 2 | No estimand registry | Exact quantity each study estimates is not written down | Design drift — lag removed, study still runs, answers different question |
| 3 | No assumption audit | Bootstrap, quintile, panel assumptions not documented | Future contributor violates assumption without knowing it exists |
| 4 | No validity assessment per family | Internal / construct / external validity not evaluated per signal family | Construct validity failure undetectable — rho valid but signal mis-specified |
| 5 | No power analysis | MIN_N=10 is a crash floor, not power-justified | Signals with real rho=0.10 fail Gate 1 at thin positions with no documented explanation |
| 6 | Statistical ladder not written down | Exists in code, not as a specification | Onboarding gap — analytical architecture invisible to new contributors |
| 7 | Causal claim hierarchy absent | No explicit distinction between association and predictive claims in governance artifacts | A finding gets interpreted as causal without causal identification |
| 8 | Gate 1 uses pooled rho — between-player variance dominates | `bootstrap_spearman_ci` operates on pooled player-GW rows. Pooled rho conflates between-player identity (Salah always has high xgi AND always scores) with within-player state (Salah is in better form than his own baseline). A signal can pass all three gates on between-player variance alone and have near-zero within-player predictive value. `split_between_within_player_rho` (kernels/correlation/panel.py) decomposes this but its output does not feed the qualification gates. | A signal qualifies as `informative` but only reflects stable player quality differences, not form changes. FPL decisions require within-player signal — you are selecting between a player's good week vs bad week, not between elite vs non-elite players. |
| 9 | Block boundaries in stability are editorial, not data-driven | GW windows (3-12, 13-26, 27-38) were chosen by judgment. If a signal shifts at GW 20, boundaries split at 12 and 27 average the shift away and classify the signal as `stable`. No change-point detection has been run to verify boundaries align with actual distributional change points. KS test + per-GW visualization needed — see `eda_05_signal_stability.ipynb`. | A signal with real mid-season drift gets classified `stable` and pooled incorrectly, inflating Gate 3 stability counts. |
| 10 | `restrict_to_midseason` pooling verdict never enforced | `resolve_pooling_strategy` returns `restrict_to_midseason` for unstable signals but study runners do not filter their population based on this verdict. The entire pipeline from block definition → stability classification → pooling decision → study scoping is broken at the last step. | Unstable signals are studied on full-season data even when the stability verdict says not to. Gate 3 stability counts may be artificially low for these signals. |

**Highest priority gaps to address when revisiting:**

1. **Gap 8 (between vs within-player rho)** — most likely source of signals that look qualified but have no FPL decision value. Requires adding `panel_class` from `split_between_within_player_rho` as a Gate 1 co-criterion or a Gate 4.
2. **Gap 2 (estimand registry)** — cheapest to fix, highest protection against silent design drift
3. **Gap 4 (validity per family)** — construct validity is the silent failure mode most likely to produce confident-looking wrong verdicts
4. **Gaps 9 and 10 (block boundaries + enforcement)** — address together when running `eda_05_signal_stability.ipynb` on full 2025-26 data

---

## 9. Template — Study Design Specification

To be completed per signal family when gaps are addressed:

```
Study:
Estimand:         Spearman rho between [signal] at GW N and [target] at GW N+1
                  for [position] players with ≥ 60 min played, [season]
Estimator:        Bootstrap percentile CI (n=2000)
Why bootstrap:    Panel structure (~38 rows per player) violates i.i.d. required
                  by analytical Spearman CI formula
Assumptions:      Rows exchangeable conditional on position
                  Signal→target relationship stationary within season
Failure modes:    Thin positions (GK, FWD) — CI wide, Gate 1 fails naturally
                  End-GW exclusions — late-season signals underrepresented
Validity:
  Internal:       CI gate + GW stability gate address this
  Construct:      [assessed per signal — does this metric represent the concept?]
  External:       Not assessed — full-season re-open is the planned address
Design decisions:
  Lag:            1 GW — supports predictive claim
  Windows:        GW 3-12, 13-26, 27-38 (GW 1-2 excluded, rolling undefined)
  MIN_N:          10 (crash floor only, not power-justified)
  Metric type:    Predictive
```
