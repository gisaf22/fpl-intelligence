# Research Lifecycle

## Overview

Every signal in fpl-intelligence passes through a defined lifecycle from first consideration
to operational use. The signal registry (`signals/characterisation/SIGNAL_REGISTRY.md`) is the
single source of truth for signal status at any point in time.

Gate order is strict:

```
exploratory → investigational → candidate → validated → operationalized
                                                              ↓
                                                    experimental ML (parallel track)
```

No signal advances to synthesis without a confirmed lens study. No experiment runs without
confirmed synthesis outputs.

---

## States

### 1. Exploratory

**Purpose.** Characterise the dataset structure and the space of candidate signals. Identify
what signal groups exist, what correlations are plausible, and what analytical scope makes
sense given the data.

**Expected stability.** None. Findings are provisional and may be revised before any signal
is named.

**Allowed consumers.** System EDA notebooks only (`studies/eda/`). No lens study, registry
entry, or code outside EDA may depend on exploratory findings.

**Promotion criteria.** The system EDA produces a governed signal registry with populated
`promotion_class` values. This closes the exploratory state. The EDA is non-repeatable; its
registry output is the authoritative output. No future work may re-open or revise it.

---

### 2. Investigational

**Purpose.** Characterise a specific signal group against the system question. A lens study
with a locked `LENS_DESIGN.md` is active. The study measures Spearman rank correlation with
bootstrap confidence intervals across defined analytical scopes.

**Expected stability.** Low. Methodology is being executed; results are not final. The
`LENS_DESIGN.md` is locked and cannot be revised once the study has begun producing results.

**Allowed consumers.** The active lens study only (`studies/lenses/[lens-name]/`). No
synthesis or experiment may consume a signal in investigational status.

**Promotion criteria.** Lens study completes with confirmed methodology and recorded results.
Signal status in the registry is updated to `candidate` or `excluded` based on the study
outcome.

---

### 3. Candidate

**Purpose.** The lens study is complete. The signal has demonstrated sufficient correlation
strength and stability in the study results but has not yet been formally confirmed for
synthesis. The signal is in the registry with `promotion_class` and lens study status
populated.

**Expected stability.** Medium. The methodology is fixed. The open question is whether the
signal meets the confirmation threshold defined in `EVAL_DESIGN.md`.

**Allowed consumers.** Registry tooling and `signals/governance/` for classification. No
synthesis or operational use.

**Promotion criteria.** Formal confirmation that the signal meets the success criteria in
`signals/governance/EVAL_DESIGN.md`. Status updated to `validated` in the registry. A
confirmed signal cannot be re-evaluated under different success criteria.

---

### 4. Validated

**Purpose.** The signal has passed lens study and formal confirmation. It is cleared for use
in synthesis (SYNTH-01) and the governed registry builder.

**Expected stability.** High. The characterisation is fixed. New evidence from future seasons
may prompt re-evaluation, but validated status within the 2025–26 methodology is stable.

**Allowed consumers.** `studies/synthesis/`, the registry builder
(`signals/characterisation/registry_build_runner.py`), and `signals/characterisation/` for signal
computation utilities.

**Promotion criteria.** Inclusion in SYNTH-01 synthesis output that is consumed by the
scorer. Once a signal contributes to a scored synthesis output it advances to
`operationalized`.

---

### 5. Operationalized

**Purpose.** The signal is active in the synthesis pipeline and contributes to weekly
intelligence outputs.

**Expected stability.** Locked. An operationalized signal is part of the live methodology.
Changes require a new signal version and explicit registry governance, not in-place
modification.

**Allowed consumers.** `intelligence/scoring/`, `intelligence/reporting/`, and any downstream
intelligence layer. This is the only lifecycle state from which intelligence outputs may be produced.

**Promotion criteria.** None. Operationalized is the terminal production state.

---

### 6. Experimental ML

**Purpose.** A validated or operationalized signal is used as a feature in an ML experiment
(`studies/experiments/`). This is a parallel track — it does not change the signal's primary
lifecycle status.

**Expected stability.** Experimental. ML experiments are sandboxed. Results inform future
research directions but do not feed back into the signal registry unless a new lens study
is initiated.

**Allowed consumers.** `studies/experiments/` only. ML experiment outputs do not become
intelligence inputs without passing through the full lifecycle from `investigational`.

**Promotion criteria.** ML experiments produce findings that may motivate new candidate
signals. Those candidates enter the lifecycle at `investigational`. Experimental results do
not bypass the lens → confirmation gate.
