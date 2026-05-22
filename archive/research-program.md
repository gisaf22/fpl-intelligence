# Research Program

**Status:** Active  
**Authority:** This document is the canonical scoping authority for all research in this repository.  
**Supersedes:** Any local study rationale that conflicts with definitions here.

---

## 1. Research Mission

Research in this repository exists to determine whether FPL-derived signals can meaningfully
improve operational FPL decisions relative to naive approaches.

The governing question is:

> Do state-derived signals provide decision-support value that a simple naive strategy does not?

This question is bounded. It is not:
- "Can we predict football outcomes generally?"
- "Can we build a model that outperforms the market?"
- "What is the optimal FPL squad?"

Research informs the intelligence outputs. The intelligence outputs (`intelligence/`) are the
operational consumers. Research that does not connect to an operational output — captain ranking,
transfer targets, value identification, availability risk, fixture opportunity — is out of scope
for this phase.

### Relationship between layers

```
signal research   →   intelligence outputs   →   FPL decisions
(evidence layer)     (operational layer)        (human judgment)
```

ML is downstream and optional. The platform is not attempting to solve football prediction
generally. It is attempting to produce interpretable, reproducible evidence that specific
state-derived signals add marginal value to explicit decision types under historical conditions.

---

## 2. Research Scope Boundaries

### What research IS allowed

The following investigation types are in scope:

- **Rolling horizon comparisons** — does a 3-GW window outperform a 5-GW or 8-GW window for a
  specific signal and position?
- **Positional signal stability** — does a signal's rank correlation remain stable across GW
  windows within a season for a given position?
- **Fixture-context usefulness** — does fixture difficulty meaningfully interact with form signals
  for a specific decision type?
- **Minutes reliability characterisation** — how stable is playing time across positions and
  rolling windows?
- **Momentum persistence** — does form improvement (roll3 > roll5) predict near-term returns
  better than level form?
- **Feature lift over baselines** — does a rolling feature outperform a single-game lag signal
  for a specific operational decision?
- **Horizon sensitivity** — how does signal usefulness change as the lookahead window grows
  from 1 to 3 to 5 GWs?

Each of these investigation types is operationally motivated: they answer questions that affect
how the intelligence outputs should be configured or interpreted.

### What research is NOT attempting

The following are explicitly excluded:

- **Causal inference** — we are measuring association, not cause
- **Betting system design** — not the domain
- **Universal player prediction** — out of scope
- **Market simulation** — FPL price movement, ownership effects
- **Transfer market optimisation** — constrained squad selection is a separate problem
- **Reinforcement learning** — no sequential decision modeling
- **Probabilistic game simulation** — match outcome modeling
- **"Perfect prediction"** — the goal is operational usefulness, not predictive optimality
- **Cross-season signal generalisation** — single-season scope for now
- **Opponent defensive modeling** — not supported by current spine grain

---

## 3. Research Volume Limits

### The governing principle

More research is not better research. The repository has enough infrastructure to generate
hundreds of studies. That is not the goal.

The goal is a small number of high-quality, reproducible investigations with operational
relevance and interpretable outcomes.

### Mandatory justification gates

Every study must clear all three before it is started:

1. **Operational motivation** — which intelligence output does this study inform? (`captain.py`,
   `transfers.py`, `value.py`, `availability.py`, `fixtures.py`)
2. **Decision question** — what concrete FPL decision becomes better or worse based on the outcome?
3. **Non-duplication** — does a prior study already answer this question sufficiently?

A study that fails any gate is rejected, not deferred.

### Acceptable study volume

This repository does not need, and should not attempt:

- More than 2–3 active lens studies at any one time
- Exhaustive rolling-window permutations (e.g., all combinations of windows 2–12)
- Automated signal mining across the full signal registry
- Brute-force correlation grids
- Hyperparameter sweeps over scoring weights

**Examples of acceptable bounded research:**

| Study | Question | Decision |
|-------|----------|----------|
| `rolling-xgi-horizon-study` | Does roll3 outperform roll5 and roll8 xGI for forwards? | Captain weight on `involvement_score` |
| `minutes-stability-by-position` | How stable is `minutes_roll5` across GW windows for each position? | Eligibility threshold in captain and transfer functions |
| `fixture-signal-positional-interaction` | Does FDR usefulness vary by position? | `fixture_score` weight differentiation |

**Examples of excessive research:**

- 200 rolling-window permutations across all signals
- Correlation grids for all 136 signal-position pairs
- Automated signal promotion pipelines
- Exhaustive GW-by-GW sensitivity tables

---

## 4. Signal Promotion Philosophy

### Lifecycle

Signals advance through a strict gate sequence defined in [research-lifecycle.md](research-lifecycle.md):

```
exploratory → investigational → candidate → validated → operationalized
```

This document governs when a signal should or should not advance, and when investigation should stop.

### What advancement requires

A signal may not advance without satisfying all criteria at its current gate:

| Gate | Required evidence |
|------|------------------|
| `exploratory → investigational` | EDA registry entry with `promotion_class` populated |
| `investigational → candidate` | Completed lens study with locked `LENS_DESIGN.md` and recorded results |
| `candidate → validated` | Formal confirmation against `EVAL_DESIGN.md` success criteria |
| `validated → operationalized` | Inclusion in SYNTH-01 synthesis output consumed by the scorer |

### What is insufficient for advancement

The following are explicitly insufficient on their own:

- **High correlation alone** — rho > 0.3 is encouraging, not conclusive. Stability and
  reproducibility are equally required.
- **One-season evidence** — a single historical season is suggestive, not validated.
- **Subjective intuition** — "this signal makes sense" is not an advancement criterion.
- **Good performance in EDA notebooks** — EDA findings are preliminary by definition.

### Signals may remain investigational indefinitely

There is no pressure to promote a signal. If a lens study completes and results are ambiguous,
the signal stays at `candidate` or reverts to `excluded`. No signal is promoted because
investigation time was spent on it.

---

## 5. Study Design Standards

Every study, before results are recorded, must define and lock the following elements.
A study that lacks any of these is incomplete.

### Required elements

| Element | Description |
|---------|-------------|
| **Research question** | A single sentence ending in "?" — specific and falsifiable |
| **Operational motivation** | Which intelligence output does this inform, and why? |
| **Evaluated population** | Positions, GW range, minutes threshold (must respect `005_analytical_foundations.md`) |
| **Horizon/window assumptions** | Rolling window sizes and lookahead GWs being tested |
| **Baseline comparison** | Which baseline from `evaluation/baselines.py` is used, and why |
| **Metric definitions** | Which metrics from `evaluation/metrics.py` constitute a positive result |
| **Success threshold** | What value(s) define "useful" vs "not useful" (not determined after seeing results) |
| **Limitations** | Known constraints on interpretability or generalisability |
| **Interpretation guidance** | What a positive/negative/ambiguous result means for the operational output |

### Mandatory technical standards

All studies must:

- **Avoid temporal leakage** — ranking features at GW N may only use information available
  before GW N's deadline. The lag-1 shift in `dal/state/` enforces this by construction;
  studies must not bypass it.
- **Be reproducible** — same inputs produce same outputs, always. No random seeds that change
  between runs, no external data dependencies outside the DAL.
- **Use deterministic evaluation logic** — `evaluation/` module functions only; no ad hoc
  metric implementations in study notebooks.
- **Document assumptions explicitly** — DGW treatment, early-season GW handling, and BGW
  exclusions must all be stated, not implied.

### Disallowed practices

- Defining success criteria after observing results ("we saw rho=0.28 so let's say 0.25 is the threshold")
- Adding signals to a study after it has begun producing results
- Re-running a completed lens study with revised methodology without versioning it as a new study
- Sharing intermediate results with the intelligence layer before a study is complete

---

## 6. Relationship to ML

ML is not the next automatic step after signal validation.

The platform is currently in the signal-understanding phase, not the model-optimisation phase.

### When ML becomes justified

ML work becomes justified only when all of the following are true:

1. **Stable operational signals exist** — at least two signals have reached `validated` status
   through the lens study and confirmation process
2. **Heuristics demonstrate measurable usefulness** — the operational evaluation framework
   shows consistent positive lift over baselines across multiple GW windows
3. **Sufficient historical evidence accumulates** — results are consistent across at least
   one full season's worth of evaluation windows (GW 6–33)
4. **A bounded predictive question is identified** — not "build a model", but a specific
   question that heuristic methods cannot answer well enough

### What ML is not

- ML is not a way to avoid doing signal research rigorously
- ML is not a way to compress the signal lifecycle
- ML is not a substitute for interpretable heuristics where heuristics are sufficient
- ML experiments do not feed back into the intelligence layer without passing through the
  full lifecycle from `investigational` (see [research-lifecycle.md](research-lifecycle.md))

### Current position

The platform has not yet demonstrated that any signal is stable enough, or that heuristics
outperform baselines consistently enough, to justify ML investment.

---

## 7. Research Stopping Conditions

This section defines explicit rules for ending investigation. Without stopping rules, research
expands indefinitely.

### Signal-level stopping conditions

Stop investigating a signal when any of the following is true:

| Condition | Action |
|-----------|--------|
| Repeated instability across GW windows (rho variance > 0.15 within season) | Archive — signal is too noisy to operationalise |
| No meaningful improvement over naive baseline across two independent evaluation windows | Archive — signal adds no marginal decision value |
| Inability to explain the signal's behavior in plain operational terms | Archive — unexplainable signals cannot be operationalised safely |
| Structural mismatch with the target population (e.g., a position-signal pair marked `excluded` in the registry) | Reject — do not investigate excluded pairs |
| Results are consistent but the operational impact is trivial (lift < 0.02 rho vs baseline) | Stop — marginal cost exceeds marginal value |

### Study-level stopping conditions

Stop adding to a study when any of the following is true:

| Condition | Action |
|-----------|--------|
| The original research question is answered | Close the study — do not expand scope |
| Results are consistent across the defined population and GW range | Record findings and close — do not add more windows |
| Two attempts at the same question produce conflicting results | Document conflict and escalate to research review — do not run a third attempt |
| The study has exceeded 3 months without producing a promotion decision | Review whether the question was well-formed; close or archive |

### What stopping does NOT mean

- A stopped study is not a failed study — negative evidence has operational value
- An archived signal may be re-evaluated in a future season if new evidence warrants it, but
  it must re-enter the lifecycle from `investigational`, not resume from where it stopped
- Stopping a study does not block other studies on different signals

---

## 8. Research Integrity Constraints

These constraints exist to prevent common failure modes: academic drift, over-fitting the
research process to look good, and infinite deferral of operational commitment.

### No retrospective success criteria

Success thresholds must be defined in the study design document before results are computed.
A study that defines "useful" only after seeing rho values is invalid.

### No scope expansion mid-study

A lens study with a locked `LENS_DESIGN.md` may not add signals, positions, or GW windows after
it has begun producing results. If a new question emerges, it becomes a new study.

### No promotional pressure

There is no organisational incentive to promote signals. The registry must reflect actual
evidence, not investment in investigation. A signal that stays at `investigational` for an
extended period because evidence is ambiguous is correctly classified.

### No parallel operationalisation

A signal may not be used in the intelligence layer while simultaneously being under active
investigation. The lifecycle gates enforce this: only `validated` signals may be consumed by
`signals/synthesis/`, which is the path to `operationalized`.

---

## 9. What Justifies Escalation to ML

For completeness: the specific evidence threshold that would justify opening ML track work.

| Requirement | Threshold |
|-------------|-----------|
| Validated signals in registry | ≥ 2 with `status = validated` |
| Baseline lift (evaluation framework) | Mean Spearman rho > 0.30 for at least 2 signals across GW 6–33 |
| Seasonal consistency | Lift positive in ≥ 70% of evaluation GWs |
| Operational question identified | A specific decision where heuristic methods are demonstrably insufficient |
| Research volume | ≥ 3 completed lens studies with recorded outcomes |

Until these thresholds are met, ML work is premature and will not be approved.

---

## Appendix: Intentionally Excluded Research Categories

The following research types are permanently out of scope for this repository in its current phase.
They are listed here to prevent recurrence of scope discussions, not to dismiss their general value.

| Category | Reason excluded |
|----------|----------------|
| Causal inference (e.g., instrumental variables, DAGs) | Requires experimental variation not available in FPL observation data |
| Betting market analysis | Different domain, different objectives |
| Cross-season generalisation | Single-season spine; multi-season data not currently governed |
| Opponent defensive modeling | Spine does not expose opponent team ID at player-GW grain |
| Transfer market dynamics | Price and ownership not in the governed DAL |
| Ensemble model comparisons | ML track not yet justified |
| Automated EDA / signal mining | Produces research sprawl without operational anchoring |
| Reinforcement learning | No sequential decision environment defined |
| Probabilistic match simulation | Different domain, different data requirements |

---

*This document is the research scoping authority. Changes require explicit review and must not
narrow or expand scope informally. All studies must cite this document and demonstrate compliance
with its scope, volume, and design standards before results are recorded.*
