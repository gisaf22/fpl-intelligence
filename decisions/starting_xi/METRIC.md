# Starting XI and Bench Order — candidate metrics

**Status:** Survey. No metric selected.
**Scope:** this document answers one question — **how could the `starting_xi` decision be
measured?** It characterises candidate metrics: what each measures, what it rewards and punishes,
how it fails, and what it requires. **It selects none of them.** Which metric governs the harness,
and why, is `DESIGN.md`'s to decide and state.

`DECISION.md` states what is being decided. `INVENTORY.md` records what exists in the repository.
Read both first; this document restates neither.

---

## 0. How to read this document

### 0.1 No candidate is recommended here

There is no "chosen", "recommended" or "adopted" section, and no candidate is described as having
lost. A candidate that a later design rejects is still characterised here in full, because the
reason for rejecting it is only legible next to what it would have measured.

Where a property is genuinely a defect — a metric that cannot be computed, a coefficient nothing
can set, a definition that does not exist — it is stated as a property, not as a verdict.

### 0.2 The three tiers, and what they mean

Every candidate carries a tier.

- **Feasible now** — every input the metric needs is confirmed present, with the location cited to
  `INVENTORY.md`.
- **Speculative** — something it needs does not exist: a data field, a capability, or a defined
  form for the metric itself. Described conceptually and **not** compared against the feasible
  tier's properties, because the comparison would be false precision.

**An interpretation this rests on, stated because it decides most of the tiering.** "Feasible now"
means the *inputs* exist, not that the code exists. `INVENTORY.md` records that no routine selects
a best legal XI (§2.4), applies auto-substitutions (§2.3), or samples a constrained squad (§2.8) —
so under a strict reading nothing here would be feasible and the tier would carry no information.
The line drawn instead: code that must be written but whose every input is present is **feasible**;
a metric needing a field or capability that does not exist and cannot be derived from what does is
**speculative**. Anyone applying a stricter reading should re-tier accordingly.

### 0.3 What this document does not contain

- **No implementation direction.** Where a metric is computed, what it is cached as, which module
  supplies a function, how a call site names it — none of that is here.
- **No repository facts.** Row counts, verified mart statistics and capability locations belong in
  `INVENTORY.md` and are cited from there. Measurements that currently exist **only** here are
  quarantined in **Appendix A** with a flag on each; they have not been silently relocated.
- **No decision-domain argument.** Why a manager behaves one way, or what the decision is worth to
  them, is `DECISION.md`'s. Where such an argument was load-bearing for a candidate's
  characterisation it is marked and pointed at, not reproduced.

### 0.4 One upstream commitment this survey cannot undo

`DECISION.md` §1 already states the cost model in prose: "the cost of getting it wrong is not the
score of the player you benched — it is the gap between what your XI scored and what the best
available XI would have scored." That is candidate **P1** below, asserted upstream as settled.

This survey characterises P1 alongside its alternatives anyway, because a survey that omitted the
option its own upstream document had already taken would not be a survey. But the tension is real
and belongs on the record: **either `DECISION.md` §1 is stating a decision that is properly
`DESIGN.md`'s to make, or the selection among P1–P5 is already partly foreclosed.** Flagged for a
human; not resolved here.

### 0.5 Two objective-scope constraints inherited from `DECISION.md`

Both bound which candidates can be characterised at all, and neither is decided here.

- **A single fixed objective.** `DECISION.md` §2 establishes that the Goal — protect rank or chase
  — is an input to the decision, and that a metric fixed to one objective measures only part of it.
  Every candidate in §2 except **P6** scores against a single objective.
- **Competitive context out of scope.** `DECISION.md` §5 places it there. A points-maximising
  objective cannot express template-versus-differential reasoning **even in principle**: starting
  the player everyone owns and the player nobody owns score identically whenever they return the
  same points. No tuning inside such a metric recovers the distinction; it requires a different
  objective function, which is candidate **P7**.

---

## 1. Candidate metrics for the primary decision

The primary decision is which 11 of the 15 start (`DECISION.md` §1).

| | Candidate | Tier |
|---|---|---|
| **P1** | Counterfactual regret — best legal XI minus chosen XI | Feasible now |
| **P2** | Benched-player points — what was left on the bench | Feasible now |
| **P3** | The regret distribution — worst-week count and size | Feasible now |
| **P4** | Mean signed directional error across gameweeks | Feasible now, form undefined |
| **P5** | Tail-weighted regret — an explicit haul coefficient | Feasible now, unparameterised |
| **P6** | Goal-conditional regret — scored against the manager's stated objective | Speculative |
| **P7** | Competitive scoring — rank or differential against a pool | Speculative |

### P1 — Counterfactual regret

**What it measures.** The gap between the chosen XI's realised total and the best legal XI's
realised total, from the same 15, in the same gameweek.

```
regret(gw, squad, ranker) = points(best_legal_XI) − points(chosen_XI)
```

**Properties.**

- Bounded below at 0 by construction, provided the counterfactual maximises over exactly the set
  the chosen XI is drawn from. A perfect call scores 0.
- Prices the **decision**, not one player's outcome: benching a 15 when every alternative returned
  12 and benching the same 15 when they returned 1 are separated automatically.
- It is a **counterfactual, not a forecast** — the best legal XI is computed with hindsight over
  realised points, so the benchmark is what was achievable, not what was predictable.
- **It is not summarised by its mean.** A single average over all gameweeks mixes variance on
  close calls, method failure on clear calls, and systematic bias; §3 and P4 exist to separate
  those, and the conditioning scheme chosen in §3 determines what a mean regret even denotes.
- **Its value depends on choices that are not part of its formula** — auto-substitution treatment,
  no-fixture handling, scope. Those are §2, and P1 is underdetermined without them.

**Requirements.** Realised points per player-gameweek; the legal formation set; a squad; a
best-legal-XI routine. `INVENTORY.md` §2.2 records the formation bounds in the staging contract
and §2.4 records the 8 legal formations and that no selection routine exists; §2.4 also records a
same-named `regret` at `model/eval/decision/metrics.py:20` measuring a different quantity at a
different grain.

### P2 — Benched-player points

**What it measures.** The score of the highest-scoring player left on the bench, per squad-week.

**Properties.**

- Directly expresses the consequence `DECISION.md` §1 names as the one being avoided, in the terms
  a manager experiences it.
- **Prices the outcome rather than the decision.** It charges a ranker the full 15 whether or not
  any alternative was available, so it cannot distinguish a costly error from an unavoidable one.
- **It charges for unforeseeable events by construction** — a haul nothing in the prior data
  pointed to costs exactly as much as one every signal flagged.
- Requires no counterfactual XI, so it is cheaper to compute than P1 and has no formation-legality
  dependency at all.

**Requirements.** Realised points and the chosen XI only.

### P3 — The regret distribution

**What it measures.** Not a central tendency: the count and size of the worst weeks per ranker,
reported as a distribution rather than reduced to a single figure.

**Properties.**

- Prices the tail **by magnitude**, using regret itself — a benched haul that mattered is a
  large-regret event; one every alternative matched is not.
- Introduces no coefficient and therefore no unmeasured judgement (contrast P5).
- **Does not produce a single comparable number**, so it cannot on its own settle a
  ranker-versus-ranker comparison or feed a significance test. It is a companion to a scalar
  metric, not a substitute for one.

**Requirements.** Whatever P1 requires; it is a presentation of the same quantity.

### P4 — Mean signed directional error

**What it measures.** Systematic bias — whether a ranker's errors are small, same-signed and
repeated, rather than large and occasional.

**Properties.**

- Isolates the most fixable failure pattern, and the one a mean regret and a distribution both hide.
- **Its form is not defined.** Regret is non-negative, so "signed error" cannot be regret; what
  quantity is signed, and against what reference, is unspecified. **Nothing in this folder defines
  it**, which is a gap in the candidate, not a property of it. `DESIGN.md` §7.9 flags the same gap
  from the build side.

**Requirements.** Undeterminable until the form is defined; the inputs are presumably those of P1.

### P5 — Tail-weighted regret

**What it measures.** Regret with large-magnitude events up-weighted by an explicit coefficient, so
that benching a haul is charged more than its point value.

**Properties.**

- Makes the tail's priority explicit and tunable rather than implicit in the loss's shape.
- **Double-counts against P1**, which already prices a benched haul by magnitude — the coefficient
  sits on top of an effect the base quantity carries.
- **No evidence available here sets its value.** The coefficient would be a judgement layered on a
  measured quantity, and every result would be conditional on it.
- `DECISION.md`'s Provenance section records that an earlier promise of an explicit tail weight was
  withdrawn upstream; that withdrawal is recorded there, not re-argued here.

**Requirements.** P1's inputs, plus a coefficient and a stated basis for its value.

### P6 — Goal-conditional regret *(speculative)*

**The concept.** The same 15 has two different correct XIs depending on whether the manager is
protecting rank or chasing it; the metric scores each selection against its own declared objective
rather than against a single fixed one.

**Why it is speculative.** `DECISION.md` §2 establishes the Goal as an input to the decision, but
nothing in the data records a manager's goal at a gameweek — `DECISION.md` §3 records that no
squad, picks or bench-order history exists at all, so there is no manager whose objective could be
read. The metric also needs a second scoring rule (a ceiling-seeking objective) that has no
defined form here.

**What it would change if it existed.** Under any single-objective candidate, a ranker that
deliberately benches a nailed player for a higher-ceiling doubtful one scores badly, and that
result must be read as "it lost points", never as "it was wrong". P6 is the candidate that would
make that distinction measurable.

### P7 — Competitive scoring *(speculative)*

**The concept.** Score against a pool rather than against points — rank movement, or return
relative to a template XI, so that starting a differential and starting a template player are
different decisions even at equal points.

**Why it is speculative.** The objective function has no defined form in this folder, and
`DECISION.md` §5 places competitive context out of scope for the slice, so no pool or template
definition exists to score against.

**One input is closer to hand than the framing suggests, and this is flagged rather than relied
on.** The mart carries `ownership_count`, and `model/eval/captaincy_backtest.py:56` defines
`lagged_ownership`. **`INVENTORY.md` records neither**, so this cannot be cited to it and the tier
stays speculative on the strength of the missing objective, not the missing data. *Flagged: an
inventory gap worth closing.*

---

## 2. Variants inside a regret-style metric

These are not implementation detail and not separate metrics. Each is an axis on which a
regret-style candidate is underdetermined, and each **moves the measured value**. A design that
selects P1 has not finished selecting until it has resolved all of them.

No option below is marked correct.

### 2.1 Auto-substitution — which side it applies to

FPL replaces a starter who records no minutes with a bench player. Three treatments:

| Option | What the number becomes |
|---|---|
| **Chosen side only** | The chosen XI's total is what the rules actually delivered; the counterfactual is a pure XI-selection ceiling. A ranker rescued by the rules does not bank the rescue, and a well-ordered bench is not credited twice. Regret then measures ranking quality separately from bench coverage — and requires §4's bench metrics to carry that decision instead. |
| **Both sides** | The counterfactual may bank points from a twelfth player where a formation minimum forces a non-featuring player in, lifting the ceiling above what any XI *selection* could realise. The benchmark becomes a joint XI-and-bench-order optimum — a different and harder decision than the one `DECISION.md` §1 names as primary. |
| **Neither side** | The chosen total is the sum of the eleven as selected. Charges a ranker for a blank the rules of the game already covered. |

**A property of the asymmetric option worth naming:** it does not fully separate ranking quality
from bench coverage, because the chosen side's realised total depends on the bench order that
supplied the replacement. `DESIGN.md` §4.9 and §4.13 record the residual coupling from the build
side. Any claim of clean separation is stronger than the mechanics support.

**Tier: feasible now.** No auto-substitution logic exists (`INVENTORY.md` §2.3), and the two data
states the trigger must span both exist (§2.5).

### 2.2 What triggers a substitution

- **`minutes = 0`** — had a fixture, did not feature.
- **`minutes` NULL** — club had no fixture. `INVENTORY.md` §2.5 records that NULL and 0 are
  structurally distinct states on the mart, and that ~84% of NULLs are a pre-registration prefix
  rather than a blank.
- **A player who came on for one minute** is an appearance under any reading; the boundary is
  *featured at all*, with no partial-appearance case and no threshold to tune.

Reading the trigger as 0-only leaves blank-gameweek players standing in the XI and lowers every
ranker's realised total. Reading it as NULL-inclusive requires the prefix population to be excluded
upstream (§5.3), or substitution events are manufactured from players who did not yet exist.

### 2.3 How a no-fixture player is ranked

A player whose club has no fixture scores 0. **How each ranker orders him is a separate question,
and it is not neutral between rankers.**

`INVENTORY.md` §2.6 records that `PlayModel`'s population drops rows with null `minutes`, so a
no-fixture player has **no `p_play` value**; a PPG-style ranker scores him at 0 under §3.2's
convention. Under a "rank the unscoreable last" convention, one ranker benches him and the others
may not — a difference in **preprocessing**, not in ranking statistic.

| Option | What it measures, and what it costs |
|---|---|
| **Harness ranks him last for every ranker** | Removes the asymmetry at its source; the comparison isolates the statistic. Cost: **nothing then measures fixture-awareness** — no ranker is charged for starting a known-zero player, and a method whose own construction avoids them is not credited. Also narrows the no-fixture substitution path, lowering §4's substitution count *by construction*. |
| **Each ranker uses its own coverage** | Measures fixture-awareness as a real capability, which is part of what separates methods. Cost: part of any margin comes from a population artefact of how a training frame was built, not from the signal being better. |
| **Score `p_play` = 0 on those rows** | Semantically correct — no fixture means probability 0 of featuring — and needs no change to how the model is fit. Closes `p_play`'s coverage hole while **preserving** the asymmetry: `p_play` consults the fixture calendar, the PPG baselines still do not. |

**Not a leakage question.** The fixture calendar is known before the deadline, so consulting it is
legitimate for any method under any option.

**A measurement that keeps the choice auditable:** the count of squad-weeks in which the chosen
option changed the selected XI, per ranker. That count *is* the confound the other options carry.

**`is_dgw` rows are a separate open case.** `p_play` also drops double-gameweek rows, where P(play)
is not 0 and no constant is correct. `INVENTORY.md` §3.4 records that whether the exclusion is
material is unmeasurable without a squad set.

### 2.4 Whether an incoming substitute must himself have featured

- **Requiring it** — the entering player must have recorded minutes, under the same two-state
  predicate as the trigger. Otherwise a non-appearance replaces a non-appearance, scores nothing,
  consumes the slot, and leaves a bench player who *did* feature stranded behind it — making any
  bench-order comparison turn on queue position rather than on ordering. Matches the real game.
- **Not requiring it** — simpler, and renders "skipped players remain available" nearly vacuous,
  since the first formation-legal bench player is consumed regardless.

Neither option affects regret's lower bound: under §2.1's asymmetric option the counterfactual has
no substitutions applied, so no eligibility rule can lift the chosen side above it.

### 2.5 The substitution mechanics

Three mechanics whose settings change the realised total, all currently unimplemented
(`INVENTORY.md` §2.3):

- **Whether the GK slot is a separate process** from the three outfield slots. If it is, bench
  order is two orderings rather than one ranking of four.
- **Whether a substitution must preserve a legal formation.** Requiring it keeps the
  post-substitution XI inside the set the counterfactual maximises over, which is what holds regret
  ≥ 0 under §2.1's asymmetric option. Not requiring it lets the chosen side out-score its own
  counterfactual.
- **Whether a skipped player stays available** later in the same gameweek — a priority queue with
  legality checks, versus a fixed consumption sequence. A scoring rule that treats a skipped player
  as spent measures a different bench order than one that does not.

### 2.6 Gameweek scope, and how ranker windows are handled

- **A study-level bound.** Season-long as-of PPG is null at GW1 — no prior gameweek exists to
  compute it from — so GW1 can be scored under no as-of candidate.
- **One global window for every ranker**, versus **per-ranker declared windows with comparisons run
  on the intersection.** A global window drags every ranker to the most restricted one anyone adds
  and discards weeks the others could score; declared windows mean no single span describes the
  study and every result must carry its own.

The live instance: `INVENTORY.md` §2.6 records `WARMUP_GW = 3`, so `p_play` produces no output
before GW4, while the PPG-style baselines are defined from GW2. **`WARMUP_GW` is global to every
term** (§2.6), so it is not adjustable for one ranker.

---

## 3. Candidate schemes for conditioning the sample

Not every gameweek carries information about ranking quality. Conditioning selects which do.

### 3.1 Candidate closeness definitions

| | Definition | Properties | Tier |
|---|---|---|---|
| **C1** | Gap between the **best and second-best legal XI** totals, scored on an as-of statistic before outcomes are known | Measures the margin by which the leading configuration led on information available at the time. Requires the same enumeration P1 needs (`INVENTORY.md` §2.4) run twice — the maximum and the runner-up | Feasible now |
| **C2** | Gap between the **11th and 12th player** by the as-of statistic | Confounded: when the three best remaining players are all defenders, it measures the `≥3 DEF` minimum binding against the ordering, not how close the selection was. Labels structurally forced weeks close and balanced weeks clear | Feasible now |
| **C3** | **No conditioning** — every squad-week counts | Largest sample; mixes weeks where no method could have distinguished itself into the headline figure | Feasible now |

**Zero-gap weeks.** Under C1, weeks where every legal XI ties carry no information — no method can
distinguish itself. They can be excluded (and the excluded count reported, since a large one means
a thinner conditioned sample than the headline span suggests) or retained. Closeness under C1 is a
property of the **squad-week**, not of the ranker, so zero-gap weeks are identical across rankers;
a per-ranker count varies only through §2.6's window intersection.

### 3.2 The denominator of the as-of scoring rate

Whichever statistic conditions the sample, its denominator is a live choice.

- **Gameweeks elapsed** — total points before *t* over gameweeks before *t* in which the player was
  in the game, counting weeks he did not feature at 0. Folds the probability of playing into the
  statistic implicitly, keeping it on the same footing as a metric scored in realised points, where
  a non-featuring player contributes 0.
- **Appearances made** — points given that he played. A different quantity, comparable to the first
  only after multiplying by P(play). Orders an 8-per-appearance player who features a third of the
  time above a nailed 4-per-week one.

The two differ materially for rotation players, so the choice is not cosmetic. Sub-choices under
the first: whether blanked weeks count at 0 (a manager selecting that week faced that 0), whether
no-fixture weeks count at 0, and whether pre-registration weeks count at all — charging a GW20
entrant with nineteen zeros he had no opportunity to avoid, or opening his denominator at his first
week in the game.

**A coupling worth stating.** If the conditioning statistic and the baseline ranker use different
denominators, "close calls" label weeks that were close under a measure no ranker uses, and the
conditioning selects the sample on a quantity unrelated to the comparison it frames.

**`DECISION.md` §1 separates "will this player play" from "what does he score when he does".** That
separation can be carried either by the denominator or by keeping `p_play` a ranker in its own
right (§5.1). Which, is not decided here.

---

## 4. Candidate metrics for the bench-order decision

`DECISION.md` §1 makes bench order the secondary decision and states it is reported separately
rather than folded into the primary number.

### 4.1 The scoring rule — the gap this section used to record, and what a rule has to measure

**This section previously stated that no candidate scoring rule for bench order existed in this
folder, and flagged that as the largest genuine gap in the survey. §4.3 now characterises five.**
The former statement is superseded and is retained in the Provenance section with what replaced it.
§4.2 is unchanged and still characterises the candidate **denominators**; the numbering is held
fixed because downstream documents cite it.

**What a bench-order metric is measuring, stated before candidates are built on it.** The bench
order is a decision taken over the players a ranker did **not** select. So the quantity is not "did
the ranker choose well" — §3's C1/C2/C3 and §1's P1–P7 already scope that — but: **given the eleven
already fixed, and given that some of them then failed to feature, did the policy put the players
who turned out to be worth having earliest in the queue?**

**Three conditions narrow that sentence, and each of them changes what a candidate can claim.**

- **Usefulness is not a property of the player alone.** §2.4's eligibility setting, if taken,
  requires an entering substitute to have featured himself; §2.5's legality setting, if taken,
  requires the post-substitution XI to be a legal formation. Under both, the highest-scoring player
  on a bench may be unable to enter at all in the week in question. A metric that scores an ordering
  against raw realised points therefore rewards getting right an order that could never have been
  executed — a property, not a defect, but one that separates the candidates in §4.3 sharply.
- **The queue's length is set by §2.5's first mechanic and is not free.** If the GK slot is a
  separate process, the bench holds exactly one goalkeeper — a squad holds two and every legal
  formation starts one (`INVENTORY.md` §2.2) — an ordering over one element carries no information,
  and the decision is an ordering over **3** outfield players, 3! = 6 in all. If the GK slot is
  **not** separate, §2.5's own words apply and the decision is "one ranking of four". Every count in
  §4.3 is stated for the first setting, because that is the one under which the ordering is a
  decision at all; under the second every candidate below still computes, over four elements.
- **Which bench player actually enters depends on the order the vacancies are served in.** Where two
  or more starters blank, the rule that decides which vacancy is filled first decides which
  substitutions are legal when, and therefore who comes on. That rule is not characterised in this
  document and is not §4's to fix; the consequence for the candidates is stated per candidate in
  §4.3 and summarised at §4.3.1 below.

**One inversion this section cannot avoid, recorded on the same terms as §0.4.** Every candidate in
§4.3 has to be characterised against substitution mechanics that §2.5 leaves **open** — and those
mechanics have since been settled downstream, in the document that is supposed to select *from* this
one. So either the settings are properly this survey's to leave open and the candidates below are
characterised against premises that are not yet fixed, or the mechanics were never really open and
§2.5 overstates the choice available. The candidates are written to be legible under either reading,
and where a setting changes a candidate's properties that is said in the candidate's own row.
**Flagged for a human; not resolved here.**

### 4.2 Candidate denominators

| | Denominator | Properties | Tier |
|---|---|---|---|
| **B1** | **Substitution count** — squad-weeks in which a selected player recorded no minutes and a substitution fired | Sizes the headline regret figure under §2.1's asymmetric option, since those are exactly the weeks the chosen total departs from the eleven as selected. As a *bench-order* sample it counts weeks where every candidate ordering brings on the same player and no ordering could have done better | Feasible now |
| **B2** | **Ordering-relevant count** — the subset where the orderings compared bring on **different** players | Counts only weeks that could discriminate between orderings — the same reasoning C1's zero-gap exclusion applies on the primary side. Strictly smaller than B1, possibly much smaller | Feasible now |

**Neither count is purely empirical.** §2.3's rank-last option bounds B1 below by construction, so
a low count is partly a consequence of that choice rather than a fact about the season.
`DECISION.md`'s Provenance section flags that if B2 is small the secondary decision may not be
measurable on one season; that check has not been run and no number for it is asserted anywhere in
this folder.

### 4.3 Candidate scoring rules

Five candidates. **None is recommended, and none is described as having lost** (§0.1); where a
property is genuinely a defect it is stated as a property. Two of the five — **O1** and **O2** — are
the alternatives a downstream document asked this survey to characterise; they are set out here
alongside three others rather than as a pair, because a two-candidate survey would decide the
question by its own framing.

Throughout, σ is a candidate ordering of the bench, the XI is held **fixed** across the orderings
being compared, and `replay(σ)` is the realised XI total that results from applying §2.5's mechanics
under σ. Holding the XI fixed is not optional: the bench is the complement of the XI within the 15,
so two rankers selecting different XIs have different bench *sets*, and comparing their orderings
would compare selections wearing the clothes of an ordering comparison.

| | Candidate | Definition | Population | Tier |
|---|---|---|---|---|
| **O1** | **Ordering regret** | `replay(σ*) − replay(σ)`, σ* the best-scoring ordering in the comparison set, same squad, same XI, same realised minutes and points | B2 | Feasible now |
| **O2** | **Entrant points** | The realised points of the player or players the ordering actually brought on | B1 or B2 | Feasible now |
| **O3** | **Realised-order rank correlation** | Kendall τ (or Spearman ρ) between σ and the ordering of the same bench players by realised points | Every squad-week, or any subset | Feasible now |
| **O4** | **Reachable-set rank correlation** | O3 restricted to the bench players some ordering could actually have brought on that week | B2 | Feasible now |
| **O5** | **As-of expected-value ordering regret** | O1 with the counterfactual taken over expected rather than realised points | B2 | **Speculative** |

---

**O1 — Ordering regret.**

**What it measures.** The points forgone by ordering the bench the way this policy did, against the
best the comparison could have done, holding everything that is not the ordering constant.

**Properties.**

- **Bounded below at 0 and 0 for the best available call**, exactly as P1 is, and for the same
  structural reason: the counterfactual maximises over a set the scored option belongs to. It
  mirrors P1's shape, which means a study reporting both carries one vocabulary rather than two.
- **Prices the decision rather than the outcome.** An ordering that stranded a 12-point substitute
  behind a blank is charged; an ordering that brought on the only eligible player there was, who
  happened to score 2, is charged nothing — there was nothing else to do.
- **Its counterfactual is relative to the candidate set, not absolute, and this is the property that
  most distinguishes it from P1.** P1's counterfactual is the best legal XI, which is a fact about
  the squad-week. O1's σ* is the best ordering *among those being compared*, which is a fact about
  the study. Two studies comparing different policy sets produce O1 values that are not on the same
  scale, and adding a policy to a comparison can change every other policy's score without any of
  them changing behaviour. Taking σ* over all 6 permutations instead makes it absolute and
  comparable, at the cost of measuring headroom no candidate was competing for; both readings are
  live and neither is selected here.
- **It inherits every underdetermination P1 has** — §2.1 through §2.6 — and adds the vacancy-order
  dependence at §4.3.1.
- **It cannot be summarised by its mean without stating the denominator**, for the reason §4.2 gives:
  weeks where every ordering brings on the same player score 0 for all of them, and averaging those
  in dilutes every policy's mean equally toward 0. That is a denominator question (§4.2), not a
  property of the rule.

**Requirements.** Realised points and minutes per player-gameweek; a fixed XI; §2.5's mechanics
implemented. `INVENTORY.md` §2.5 records the minutes states and §2.3 records that no
auto-substitution logic exists anywhere in the repository, so the replay is code that must be
written; under §0.2's reading every input it consumes is present.

---

**O2 — Entrant points.**

**What it measures.** The realised points the ordering actually harvested — the score of whoever it
put on the pitch.

**Properties.**

- **Needs no counterfactual at all**, so it is the cheapest of the five and has no dependence on a
  best-ordering definition, which is exactly the definitional question O1's σ* leaves live.
- **Prices the outcome rather than the decision**, and this is the same relationship P2 bears to P1.
  It charges an ordering the full difference between a 2-point substitute and a 12-point one whether
  or not the 12-point one could ever have entered. A policy that faced no choice and a policy that
  faced one and got it wrong are not separated.
- **It is not comparable across squad-weeks without a normalisation nobody has defined.** A week in
  which two substitutions fire scores roughly twice a week in which one does, for a reason that is a
  property of how many starters blanked rather than of the ordering. Summing or averaging it across
  weeks therefore weights weeks by blank count. Dividing by the number of substitutions, or scoring
  only the first entrant, are both available and both change what is being measured; neither is
  selected here.
- **It is directional in a way the others are not:** higher is better, where O1 and O5 are losses and
  O3/O4 are correlations. A study reporting it alongside a regret-style figure carries two signs.

**Requirements.** Realised points; the replay's record of who entered. Strictly less than O1 needs.

---

**O3 — Realised-order rank correlation.**

**What it measures.** Whether the policy's ordering agrees with the order the bench players turned
out to deserve, ignoring magnitude entirely.

**Properties.**

- **It scores the ordering as an ordering.** The decision under study is a permutation, and this is
  the only candidate whose value is a function of the permutation and the realised ranking alone —
  a policy that puts a 12, a 4 and a 1 in that order scores identically to one that puts a 3, a 2
  and a 1 in that order. Whether that is the right invariance is precisely the question: it makes
  the metric insensitive to how much the ordering was worth, which is the quantity `DECISION.md` §1
  frames the primary decision in.
- **It is independent of §2.5's mechanics and of the vacancy-order rule entirely**, because it never
  runs the replay. That independence is its most consequential property and it cuts both ways.
  It means the metric is stable under changes to mechanics this survey leaves open — no other
  candidate here is — and it means the metric **credits a policy for ordering correctly a set of
  players who could not lawfully have entered**, or who were ineligible under §2.4, or who were
  never called on because nobody blanked.
- **It can be measured over every squad-week, not only over weeks where a substitution fired.** This
  is the only candidate with that property, and it is a large one: a bench-order comparison
  restricted to B2 may be too thin to resolve anything on one season, and O3 is not so restricted.
  The cost of that reach is stated in the bullet above — most of the weeks it gains are weeks in
  which the ordering had no consequence, so it buys sample size by measuring the decision in
  conditions where the decision did not matter.
- **Its resolution per squad-week is very coarse.** Over three elements with no ties, Kendall τ takes
  four values — −1, −⅓, ⅓, 1 — so a single squad-week carries roughly two bits. It is a quantity to
  aggregate, never to read one week at a time, and any interval on it has to respect that the
  per-week value is near-categorical.
- **Ties in the realised ranking are the live threat to it, not an edge case.** A bench player who
  blanks scores 0, two who blank tie, and the tie-handling convention then decides the metric's
  value on a large share of its own population. Whether that share is large is a repository fact
  nobody has measured — see §4.3.2.

**Requirements.** Realised points; the policy's ordering. No replay, no formation set, no minutes
predicate. *Whether a rank-correlation routine already exists in the repository is not recorded in
`INVENTORY.md` — §2.9 covers bootstrap and resampling conventions and says nothing about rank
correlation. That is an `INVENTORY.md` gap (§4.3.2) and not a fact this document may assert. It does
not bear on the tier either way: over three elements the statistic is arithmetic, and §0.2's reading
tiers on inputs rather than on code.*

---

**O4 — Reachable-set rank correlation.**

**What it measures.** O3, restricted to the choice the policy really faced: the bench players whom
*some* ordering would have brought on that week.

**Properties.**

- **It closes the gap §4.1 opens between "worth having" and "able to enter".** The players it scores
  over are exactly those the week made available, so it neither credits nor charges a policy for the
  order it placed players in who were never a live option.
- **It is the only candidate that is both magnitude-free and consequence-aware**, which places it
  between O3 and O1 rather than as a variant of either.
- **Its definition carries load the other four do not.** "Reachable" has to be defined, and the
  natural definition — the union over orderings of the players who enter — is a construction rather
  than a given, and one whose value depends on the vacancy-order rule (§4.3.1) in the same way O1's
  does. A stricter definition (reachable under the vacancy order actually used) and a looser one
  (reachable under any vacancy order) give different populations, and neither is selected here.
- **It degenerates where the reachable set has fewer than two members**, which §4.10-style reasoning
  suggests is the common case: with three outfield bench players, often only one is eligible. A
  correlation over one element is undefined, so those weeks are excluded — which returns O4 to
  roughly B2's population and forfeits the sample-size advantage O3 has. **O4 is therefore not a
  strictly better O3; it trades reach for relevance.**
- **It inherits O3's tie problem** over whatever population survives.

**Requirements.** O3's, plus the replay run once per ordering to determine reachability — the same
enumeration O1 needs.

---

**O5 — As-of expected-value ordering regret *(speculative)*.**

**What it measures.** O1 with the counterfactual taken over what the bench players were *expected* to
be worth at the time the order was set, rather than over what they turned out to be worth.

**Properties.**

- **It scores the ordering against the information the decision was actually taken on**, which is the
  same reasoning §3.1's C1 rests on and the reason the conditioning statistic there is as-of rather
  than realised. If a bench order is meant to inform an in-week decision, the case for the same
  treatment here is structural rather than stylistic — see §4.4, where the tension is stated and
  deliberately left open.
- **It would make a good ordering one that was right in expectation and a bad one that was wrong in
  expectation**, so a policy is not charged for a substitute who was correctly ranked last and then
  hauled. Whether that is desirable depends on what the metric is for, which is a `DECISION.md`
  matter and is not argued here.
- **It is speculative on definitional grounds first, and input grounds second.** There is no defined
  as-of counterfactual for an *ordering*: σ* under O1 is "the ordering that scored best", and the
  as-of analogue would have to be "the ordering that was best in expectation", which requires a
  per-player expected-points quantity for bench players and a rule for combining it across a queue
  whose members enter conditionally. Neither exists in defined form, and §0.2 tiers a metric without
  a defined form as speculative regardless of what data is present.
- **A second, weaker form is available and is not the same metric:** score the ordering by rank
  correlation between σ and an as-of statistic, which is nearly vacuous, since a policy ordering on a
  ranker's scores would be scored against the thing it ordered on. It is recorded so it is not
  mistaken for a cheap version of O5.

**Requirements.** An as-of expected-points quantity per bench player, and a probability of featuring.
`INVENTORY.md` §2.1 records as-of scoring-rate machinery and §2.6 records `p_play` with
`WARMUP_GW = 3`. *Whether a per-player expected-points-conditional-on-playing forecast usable at
as-of time exists is not recorded in `INVENTORY.md` in a form this candidate could cite* — an
`INVENTORY.md` gap (§4.3.2). The tier does not turn on it: the definitional gap above is sufficient
on its own.

#### 4.3.1 Which candidates depend on the vacancy-order rule, and which do not

*This subsection characterises a **dependency of the candidates above**. It does not state what the
vacancy-order rule is or should be — that is a mechanic, it sits with §2.5's three, and like them it
is not fixed in this document. A downstream document numbers its own vacancy-order section similarly;
bare section numbers here mean this document's, per the charter.*

Where two or more starters blank in the same week, the order the vacancies are served in determines
which substitutions are legal when, and therefore which bench player enters. **Any candidate whose
value is read off the replay is defined relative to that rule, and its values are not comparable
across a change to it.** That splits the five:

| Candidate | Depends on the vacancy-order rule? |
|---|---|
| **O1**, **O2** | **Yes, fully** — both read who entered, or what the resulting total was |
| **O4** | **Yes, through its definition of "reachable"** — and differently depending on which of the two definitions above is taken |
| **O3** | **No** — it never runs the replay |
| **O5** | **Yes**, on whatever replay its counterfactual is defined over |

**Two consequences worth stating, neither of them resolved here.** A change to the vacancy-order rule
that causes more substitutions to fire — by salvaging a vacancy an earlier rule left unfilled —
mechanically changes **B2**, §4.2's ordering-relevant count, and therefore the population every
replay-based candidate is measured over. Nobody has measured that effect and no number for it is
asserted anywhere in this folder. And a metric with **no** such dependence, which is O3 alone, buys
that stability by not measuring the consequence — the property is not free in either direction.

#### 4.3.2 Facts these candidates need that `INVENTORY.md` does not carry

Flagged rather than asserted, per the charter; each requires an `INVENTORY.md` pass, not a sentence
here.

1. **How often the realised points of a squad-week's bench outfielders tie.** O3 and O4 are
   rank-correlation metrics over three elements, and their behaviour is decided by the tie
   convention on whatever share of weeks carries ties. `INVENTORY.md` §2.5 records that 17,977 mart
   rows carry `minutes == 0`, which suggests the share is not small, but the quantity that matters is
   ties **within a squad-week's bench**, and that is a different measurement over a population that
   does not exist until squads are sampled. No number for it is asserted here.
2. **Whether a rank-correlation routine exists in the repository, and with what tie convention.**
   §2.9 records the bootstrap and resampling conventions and is silent on rank correlation. This
   bears on the tie convention above rather than on any candidate's tier.
3. **Whether an as-of expected-points-conditional-on-playing forecast exists per player-gameweek.**
   §2.1 records as-of scoring rates and §2.6 records `p_play`; neither is the same quantity. Bears on
   **O5**, though not on its tier.

### 4.4 As-of or realised — an unresolved tension, stated not settled

**Four of the five candidates score an ordering on what happened. The question this section refuses to
answer is whether they should.**

**Why the question is live rather than academic.** §3.1's C1 was corrected on exactly this axis: it
had read as scoring on realised points, and the correction to an as-of statistic was made on the
ground that the realised reading conditioned the sample on the outcome. A bench order is a decision a
manager takes **before** the gameweek resolves, on information available then, and if the metric is
meant to say whether the policy was a good way to order a bench, the same argument applies with the
same force.

**Why it does not simply follow.** C1 is a **conditioning** statistic — it selects which weeks carry
information, and conditioning on the outcome selects the sample on the thing being measured, which is
a bias with a name. A bench-order **scoring rule** is not doing that job. P1, the primary metric, is
frankly counterfactual and scores on realised points by construction, and this survey records that as
a property rather than a defect: "the benchmark is what was achievable, not what was predictable". An
ordering metric that mirrors P1's shape inherits that posture legitimately. So the C1 correction is
not automatically precedent here, and treating it as one would be an argument by analogy across two
different jobs.

**What turns on it.** If the ordering metric is realised, it answers "how much did this ordering cost
in points", and a policy is charged for outcomes nothing could have foreseen — the same property P2
carries and P1 partially avoids. If it is as-of, it answers "was this a well-reasoned ordering", a
policy is charged only for being wrong about what was knowable, and the metric stops being
expressible in points, which is the unit `DECISION.md` §1 states the cost model in.

**Both framings are represented above** — O1, O2, O3 and O4 realised, O5 as-of — so a design
selecting from this survey is choosing between them rather than inheriting one. **This document does
not resolve it.** It is a selection, and selections are `DESIGN.md`'s.

### 4.5 What §4 still does not contain

- **A selection.** None of O1–O5 is recommended, and §4.2's B1 and B2 are likewise unselected.
- **A rule for combining a scoring rule with a denominator.** O2 is listed against "B1 or B2" because
  both are defensible for it and the choice changes what it measures; the other candidates' natural
  denominators are listed but not fixed.
- **Uncertainty treatment on the ordering sample — no longer absent; see §6.4.** This bullet
  formerly read that §6's candidate designs are written for a squad-week unit, that an
  ordering-relevant squad-week is "a different and much rarer unit", and that whether §6.2's schemes
  transfer to it is not characterised here for any of the five. **The premise was wrong**, and §6.4
  supersedes it: §6.2's schemes are characterised over a *panel*, by which margin they resample, and
  the ordering sample is the same panel under a different exclusion predicate rather than a different
  unit. What genuinely does not transfer is a set of occupancy assumptions, which §6.4 names and
  characterises candidates against. The withdrawn text is recorded in Provenance.
- **The substitution mechanics.** §2.5 holds them, and §4.1 records that they are open here and
  settled downstream.

---

---

## 5. Candidate comparison floors

Any of §1's candidates yields a number that means little alone. A floor is what it is measured
against.

### 5.1 Candidate naive rankers

| | Ranker | What it ranks on | Defined from | Tier |
|---|---|---|---|---|
| **F1** | `p_play` alone | Probability of featuring; scoring rate ignored entirely | GW4 (`INVENTORY.md` §2.6) | Feasible now |
| **F2** | Season-long PPG-to-date | Mean points over prior gameweeks | GW2 | Feasible now |
| **F3** | Recent form — PPG over the last 3 gameweeks | The same statistic over a 3-gameweek lag-1 window | GW2, thinly | See 5.2 |
| **F4** | A 5-gameweek variant of F3 | As F3, longer window | GW2, thinly | See 5.2 |

**On F3's window length.** Three gameweeks is short enough to track rotation and form moving within
a season, long enough that one blank or one haul does not dominate the ordering, and matches the
window the platform already uses for lag-1 rolling signals (`minutes_roll3`, `xgi_roll3`), so it
introduces no new convention. Whether F3 and F4 are both pre-registered baselines or one is a
sensitivity check is a design choice, not a property of either.

**The argument that a season-long floor is too weak** — that no manager selects that way, so
beating F2 demonstrates little about a method — is **decision-domain reasoning about manager
behaviour**, and `DECISION.md` is its proper home. It is recorded there, in `DECISION.md` §1
("A note on what a naive comparison proves").

### 5.2 The requirement F3 and F4 carry — measured, and what it constrains

*This section formerly read "One requirement that is not yet satisfied". The requirement has since
been measured against the record, by an `INVENTORY.md` §2.1 pass. The question it posed is unchanged
and is restated below; what changed is that the record now answers it. Selecting F3 on that answer is
`DESIGN.md`'s (§0.12) and is not done here. The withdrawn "where an answer would be recorded" claim
is in Provenance with its reason.*

`INVENTORY.md` §2.1 records that **no `points_roll3` and no `points_roll5` exist on the governed
mart**: the feat layer omits `total_points` from its rolling set, under an annotation at
`dal/feat/feat_player_gameweek.py:94–96` covering eight columns on the disjunctive grounds
"evaluation_circularity or G2-FAIL".

**What was unsettled was not the absence but its scope** — whether that exclusion is a governance
decision that also binds a *baseline ranker*, or an omission specific to the signal registry's
purposes. The circularity concern was about a governed signal predicting a target derived from
itself, which is not what a baseline ranker does; but that argument had to be made and accepted
rather than assumed.

| | |
|---|---|
| **Question** | Does the governed mart's exclusion of `points_roll3` bind a baseline ranker in this harness? |
| **What settles it** | The lens record behind the annotation on `_ROLL_COLS` in `dal/feat/feat_player_gameweek.py`. Reading the record is the whole task |
| **Where the answer already sits** | Not in a single file. `INVENTORY.md` §2.1 measures the rule as carried across five committed files, each stating the exclusion **with its scope attached** — `docs/foundations/representation-rules.md` §8, `research/families/form/LENS_DESIGN.md`, the form study, its `annotations.yaml`, and ADR-010 |
| **Status** | **Measured.** `INVENTORY.md` §2.1 records what each of the five says. F3 and F4 are no longer speculative on this ground; whether either is *selected* is `DESIGN.md` §0.12's |

**The property this fixes for both candidates, and it is a construction constraint rather than a
permission.** Whatever `DESIGN.md` selects, `INVENTORY.md` §2.1 measures that no mart column exists
to read and that the enforcement is over `build_player_gameweek_state`'s **output columns**. So F3
and F4 are candidates whose statistic must be **derived by the consumer over a population the
consumer supplies** — which makes the population a metric-affecting choice rather than an
implementation detail, since the same statistic over appearances and over gameweeks elapsed are
different numbers. §2.6 and §3 characterise the denominator candidates; the choice between them is
`DESIGN.md`'s.

**A second property, which distinguishes F3 and F4 from each other on this axis and did not before.**
`INVENTORY.md` §2.1 records `docs/foundations/representation-rules.md` §8 carrying two different
statuses: `total_points_roll3` is REJECTED-BEHAVIORAL outright, while `total_points_roll5 at MID` is
CONDITIONAL "as evaluation baseline … not a feature". Both rows are about *feature* status and
neither is about floor-ranker use, so neither ranks the two candidates for this harness. It is
recorded because a reader meeting the two rows out of context could take the roll5 row as the more
permissive one and prefer F4 on that basis, which would not follow.

**The same divergence has been observed from the other side.** `INVENTORY.md` §3.7 records that
`assert_no_future_leakage` requires `points_roll3` and that the existing decision-backtest path is
unrunnable against the governed mart for that reason. That divergence is **not resolved** by the
measurement above: it is a property of `model/eval/decision/backtest.py`'s path, and the guard and
the mart contract still cannot both stay as they are. Whether *this* harness adopts that guard is a
separate question and `DESIGN.md`'s — Provenance already records it as implementation direction that
left this document.

### 5.3 Candidate ways to determine the floor from the naive rankers

| Option | Properties |
|---|---|
| **Best-performing of the set, on the common window** | The floor is whichever naive ranker carries the lowest regret, re-determined per comparison on the intersection of every window involved. Makes the floor **window-relative** — which ranker wins may differ on a narrower window — so the floor's identity has to be reported with every result |
| **Best-performing, each on its own maximal window** | Compares means taken over different spans. The earliest gameweeks are the thinnest-history weeks of the season, so a mean over GW2–38 and one over GW4–38 estimate different quantities, and the comparison partly measures which weeks each ranker was allowed to count |
| **A nominated floor** | One ranker fixed in advance. Stable and simple; a candidate that beats the nominated ranker while losing to another naive one is reported as having cleared the floor |

**A consequence for any relative success bar.** A "reduction of X% against the floor's own regret"
is not interpretable if numerator and denominator were computed over different gameweek sets — so
the floor option and the bar in §6.3 are coupled choices, not independent ones.

**A degeneracy affecting F2 and F3 jointly.** At GW2, GW3 and GW4 the two statistics return the
same number for every player: at gameweek *t* a player has *t*−1 prior in-game gameweeks, and while
that is 3 or fewer the 3-gameweek window covers all of them. They first diverge at GW5. Under any
common window binding at GW4, one of those weeks sits inside it and cannot discriminate between two
of the floor rankers. (Measurement in **Appendix A**.)

**Which naive ranker wins is itself a result.** If F1 is hard to beat, that says something about
the decision that no candidate ranker's score would reveal.

---

## 6. Candidate treatments of uncertainty, and candidate success bars

### 6.1 Candidate designs

- **Paired** — every ranker faces the same squads in the same gameweeks. Squad-level variation
  (some squads are simply deeper and have less to gain from any method) is common to all rankers
  and cancels in the difference. What is measured is the **method difference**, not the absolute
  regret level. Requires the common-window handling of §2.6 to be exact.
- **Unpaired** — rankers evaluated on independently drawn squads. Squad variation enters the
  comparison as noise.

### 6.2 Candidate resampling schemes

| | Scheme | Properties | Tier |
|---|---|---|---|
| **U1** | Resample **squads**, gameweek set fixed | Measures sensitivity to which squads were drawn | Feasible now |
| **U2** | Resample **gameweeks**, squads fixed | Measures sensitivity to which weeks the season contained. A moving-block bootstrap over a per-gameweek series exists (`INVENTORY.md` §2.9) | Feasible now |
| **U3** | Resample **squad-week rows** as independent draws | Two sources of dependence make the product non-independent: the same squad recurs across every gameweek, and the same gameweek recurs across every squad. Treating the product as independent inflates the effective sample by roughly two orders of magnitude and manufactures precision the data does not contain. Holds at any window length. **The first source is present only under a held squad (§7.1)**; the second is present under either construction | Feasible now |
| **U4** | **Cluster** bootstrap — resample clusters, take all of a drawn cluster's rows | The structurally correct treatment of a panel in which one unit contributes many dependent rows. `INVENTORY.md` §2.9 records a cluster resampler hard-wired to a rho statistic and **no generic cluster-bootstrap-of-a-mean**. **Applicable only where the panel has clusters**: under resample-per-gameweek (§7.1) a squad contributes exactly one row, so drawing a cluster and drawing a row are the same operation and U4 carries no structure U1 does not already have | Feasible now |

U1 and U2 answer different questions and can be reported as two intervals rather than one.

**These schemes are characterised against a population, and §7.1's held-versus-resampled choice
changes what they mean.** U3's and U4's properties above were previously stated unconditionally,
which was only correct under a held squad. The dependence structure of the panel is a consequence of
the construction, so a design selecting a scheme here has to select a population first; §8's table
lists them as #14 and #16 without ordering them, and the ordering is noted here rather than imposed.
Where the held-squad recurrence is absent, holding the gameweek margin fixed while resampling within
it is the treatment that addresses the second source of dependence without resampling a dimension U1
holds fixed by definition — a variant of U1 rather than a fifth scheme, and not separately tiered.

**The resample count is a live choice, not an inherited one.** `INVENTORY.md` §2.9 records two
`block_bootstrap_ci` implementations — same name, same algorithm, `n = 1000` and `n = 3000` — so a
count acquired by import path is acquired by accident. Where a verdict turns on whether an interval
excludes zero, the count bears on the verdict: at `n = 1000` a 2.5% endpoint rests on the 25 most
extreme draws and Monte Carlo jitter can flip it for a difference not itself near zero; at 10,000
it rests on 250, with percentile convergence ~1/√n putting simulation noise below plausible effect
sizes. The cost is negligible either way — the statistic resampled is a mean over dozens of
gameweeks or hundreds of squads, not a model fit.

**A constraint that does not apply to a new metric.** `INVENTORY.md` §2.9 records that the
`model/eval` implementation's outputs are published and carry reproduction anchors. That constrains
changing the **existing** implementations; it does not require a new measurement to inherit their
count.

### 6.3 Candidate success bars

Three conditions, separable — a bar may require any one, any two, or all three.

| | Condition | What it answers | What it misses alone |
|---|---|---|---|
| **S1** | **Direction** — the candidate's mean regret is lower than the floor's | Did it improve at all | Says nothing about whether the improvement is distinguishable from noise |
| **S2** | **Significance** — the paired resampled interval on the difference excludes zero | Is it real | Under a paired design over hundreds of squads, an interval can exclude zero for a difference of a few hundredths of a point per gameweek — real and worth nothing |
| **S3** | **Materiality** — the reduction is at least some fraction of the floor's own mean regret | Is it worth anything | Needs a threshold, and the threshold needs a basis |

**Candidate forms for S3's threshold.**

- **Relative to the floor** — fixable honestly before the first run, because it scales with whatever
  the floor turns out to be. The headroom in this decision is **unmeasured**: nobody has computed
  how much regret the floor carries, so nobody knows how much is removable.
- **A fixed number of points** — directly interpretable, but fixed before the headroom is known it
  risks pre-registering a target no ranker can reach, so that a real improvement reads as a failure.
- **On the level of the threshold**: a lower bar (10%) guards against an unreachable target set on
  unmeasured headroom; a stricter one guards against crediting an improvement too small to justify
  its complexity, and reintroduces the first risk.

**A reporting property independent of the bar chosen.** A given percentage reduction on a large
floor regret and on a small one are different results, and only the absolute points figure says
which is on the table. The relative figure decides whether a criterion is met; the absolute one
tells a reader whether added complexity earned its keep.

**Pre-registration is a property of *when* a bar is fixed, not of which.** Any threshold and any
resample count can be fixed before the first run and not revised in response to results; the
`evidence.yaml` + freeze-test pattern `INVENTORY.md` §2.9 records is the only mechanism in the
repository that makes such a fixing enforceable rather than aspirational.

### 6.4 Uncertainty on an exclusion-filtered subpanel — the bench-order sample

*This subsection exists because §4.5 sent the question here. It was previously routed the other way:
a downstream document asked §4 to characterise uncertainty for O1–O5, and §4.5 replied that §6's
designs assume a squad-week unit and the ordering sample is a different one. **That reply rested on a
false premise about §6.2 and is superseded.** The correction is made here rather than in §4 because
the gap is §6's — it is about what §6.2's schemes are indexed by, which is not a property of any
candidate scoring rule. §4.5 now points here.*

#### 6.4.1 What §6.2's schemes are actually indexed by — a margin, not a unit

**§6.2 does not assume a squad-week unit, and nothing in it ever did.** Read against §6.2's own
table, the four schemes are distinguished by **which margin of a squad × gameweek panel is
resampled**:

| Scheme | What moves | What is held |
|---|---|---|
| **U1** | the **squad** margin | the gameweek set |
| **U2** | the **gameweek** margin | the squads |
| **U3** | rows, treated as independent | nothing — which is the objection |
| **U4** | clusters | whatever the cluster is a cluster *of* |

The squad-week is the panel's **row**, and it is the unit only of U3 — the scheme §6.2 characterises
as manufacturing precision the data does not contain. So "§6 is written for a squad-week unit" was a
description of the one scheme §6.2 rejects. U1 and U2 are indexed by margins, and §6.2's closing
paragraph already says as much when it records that the schemes are "characterised against a
population" whose dependence structure §7.1's construction decides.

#### 6.4.2 The ordering sample is the same panel under a different exclusion predicate

**B2 (§4.2) is a filter over the panel, not a redefinition of it.** The ordering-relevant count is
"the subset where the orderings compared bring on different players" — a predicate evaluated on
squad-weeks that were already drawn, at gameweeks that were already in scope. It removes rows. It
does not change what a row is, what was randomised to produce one, or which margins the panel has.
The same holds for B1.

**This document already contains the precedent, and it is not a loose analogy.** §3.1's conditioning
scheme excludes zero-gap squad-weeks from the *primary* sample, so the primary comparison is itself
run on an exclusion-filtered subpanel rather than on the raw draw. §6.2's schemes were never
characterised against an unfiltered panel; they were characterised against the panel that survives
§3.1. B2 is a second predicate of the same kind, differing in **how much** it removes rather than in
kind.

**So U1 and U2 transfer to the ordering sample unchanged in form**, and no fifth scheme is required.
A design selecting an uncertainty treatment for a bench-order figure selects from §6.2's existing
table, on §6.1's existing paired/unpaired axis, against §6.3's existing bars. **Building a parallel
framework for the ordering sample would be building a second vocabulary for one question** — the
objection §4.3's O1 rests on in the scoring-rule case, applied here.

#### 6.4.3 What does not transfer — three occupancy assumptions, stated as the conditions they are

What separates the two samples is **occupancy**: how many rows survive the predicate, and how they
distribute across the gameweek margin. §4.10-style reasoning is a downstream document's, but this
survey's own §4.2 records B2 as "strictly smaller than B1, possibly much smaller" and records that
the check has not been run. Three assumptions that are harmless on a dense panel become load-bearing
on a sparse one, and each is a property of the *panel*, so each is §6's.

- **A1 — U1's within-stratum draw needs more than one row per stratum to contribute any variance.**
  Where the schemes are applied with the gameweek margin held fixed (§6.2's closing paragraph, the
  U1 variant that resamples within a fixed gameweek margin), a gameweek contributing exactly one
  surviving row is redrawn identically in every replicate. It carries its full weight into the mean
  and **zero** variance into the interval. On a dense panel singleton strata are a curiosity; under
  B2 they are an expected case, and the resulting interval is too narrow by an amount that grows
  with how many there are.
- **A2 — U2's block structure assumes a contiguous ordered series.** §6.2 records U2 as a
  moving-block bootstrap over a per-gameweek series, and `INVENTORY.md` §2.9 records the available
  implementation as a moving-block bootstrap of the mean of such a series, motivated by consecutive
  gameweeks autocorrelating. A gameweek in which **no** row survives the predicate has no
  per-gameweek mean, so the series is **punctured** rather than merely shorter, and adjacency in the
  surviving series is no longer adjacency in the season. Blocking is the one scheme whose validity
  turns on that distinction.
- **A3 — the series must be long enough to contain a block.** A block bootstrap over a series
  shorter than one block is not a weaker version of the scheme; it has no resampling structure left.
  The binding count for a bench-order figure is the number of gameweeks carrying at least one
  ordering-relevant row, which is bounded above by, and may be well below, the scoreable-gameweek
  count a primary comparison runs on.

**None of the three is a defect in U1 or U2.** They are preconditions those schemes always carried,
which a dense panel satisfies silently and a sparse one may not. Stating them as conditions is what
lets a design check them rather than discover them.

#### 6.4.4 Candidate treatments where A1 fails — the squad margin

Characterised, not selected (§0.1). Each holds the gameweek margin fixed, per U1.

| | Candidate | What it does | Tier |
|---|---|---|---|
| **W1** | **Stratify unchanged, and report the occupancy profile beside the interval** | Applies U1's within-gameweek draw as-is. Singleton strata contribute no variance; the count of them is reported so a reader can see how much of the interval's narrowness is structural | Feasible now |
| **W2** | **Pool adjacent gameweeks into strata until each meets a minimum occupancy** | Restores a within-stratum draw with something to draw from | Feasible now |
| **W3** | **Drop the stratification; bootstrap surviving rows flat** | The sparse case makes this tempting, which is why it is listed | Feasible now |

- **W1's property, stated as a property.** The understatement is not unknown — it is a computable
  function of the occupancy profile, since a stratum of size 1 contributes exactly zero and a
  stratum of size *n_g* contributes in proportion to its own within-stratum variance. So W1 produces
  an interval whose defect is **measurable from the same output that produced it**. What it does not
  do is correct it, and an interval reported without the profile beside it is not distinguishable
  from a well-occupied one.
- **W2's property, and the thing it gives up.** Stratifying by gameweek is justified in §6.2 and
  §7.1 by the fact that squad-weeks sharing a gameweek share that week's realised fixtures and
  results — the stratum is the shared realisation. A pooled stratum spanning several gameweeks is no
  longer that object, so W2 buys variance contribution by weakening the conditioning that motivated
  stratifying at all. It also introduces a pooling rule — how many weeks, chosen how — which is a
  new parameter with the pre-registration obligation §6.3's closing paragraph describes.
- **W3 is U3 under another name, and the sparse case does not rehabilitate it.** §6.2's objection to
  U3 has two halves, and §7.1 records that the first — a squad recurring across gameweeks — is
  present only under a held squad. The second, rows sharing a gameweek, is present under either
  construction. Sparsity **weakens** that half without removing it: a gameweek contributing three
  rows induces less shared-realisation dependence than one contributing three hundred, but the rows
  are still not independent draws from a season-level distribution. W3 is recorded so that the
  narrowing it produces is recognised as the U3 signature rather than mistaken for the sparse
  panel's own behaviour.

#### 6.4.5 Candidate treatments where A2 or A3 fails — the gameweek margin

| | Candidate | What it does | Tier |
|---|---|---|---|
| **V1** | **Compact the series**, blocking over surviving gameweeks only | Blocks span non-adjacent real gameweeks; the adjacency the block exists to preserve is partly fictional, and the distortion grows with how punctured the series is | Feasible now |
| **V2** | **Keep the season index**, carrying empty gameweeks as missing | Preserves true adjacency. Replicate means are taken over blocks with varying numbers of defined values, and an all-empty block contributes nothing — so the effective resample count is below the nominal one by an amount the occupancy profile determines | Feasible now |
| **V3** | **Report U1 only**, and decline the gameweek interval for this figure | §6.2 already records that U1 and U2 answer different questions and "can be reported as two intervals rather than one", so reporting one is coherent rather than a truncation. What is forgone is sensitivity to which weeks the season contained | Feasible now |

**V3 is not the null option it looks like.** Under A3 — a surviving series shorter than one block —
V1 and V2 are both unavailable in substance, and V3 is what remains. Whether that state obtains is
an occupancy question, not a design preference.

#### 6.4.6 The precondition is unmeasured, and the measurement is cheap

**Which of §6.4.4's and §6.4.5's candidates is even applicable is decided by two numbers**: the count
of gameweeks carrying at least one surviving ordering-relevant row, and the distribution of surviving
row counts across them. **Neither exists.** §4.2 owns this and records both halves: that the B2
check has not been run and no number for it is asserted anywhere in this folder, and that
`DECISION.md`'s Provenance section flags that if the ordering-relevant count is small the secondary
decision may not be measurable on one season.

**Both fall out of the first run rather than requiring one of their own** — they are counts over the
same rows the bench-order figure is computed from. So the honest form of this section's contribution
is a **conditional characterisation**: the schemes transfer, the preconditions are named, and which
treatment is applicable is determined by an occupancy profile that the run producing the figure also
produces. A design may therefore pre-register the treatment **as a rule over the profile** rather than
as a fixed choice, which §6.3's closing paragraph permits — pre-registration constrains *when* a bar
is fixed, not whether it may be conditional on a measured quantity.

**This bears on §6.3's bars, and the connection is not decorative.** S2 is "the paired resampled
interval on the difference excludes zero". Under A1 an interval can exclude zero *because* singleton
strata suppressed its width, and under A2 because compaction treated distant weeks as adjacent. So
on a sparse subpanel S2 is only as trustworthy as the occupancy profile behind it, and S1 and S3 —
direction and materiality — carry no such dependence. A bar composed for a sparse subpanel may
reasonably weight them differently from one composed for the primary comparison; §6.3 characterises
the three conditions as separable and this is one of the cases that separability exists for.

#### 6.4.7 What §6.4 does not decide

- **The selection.** None of W1–W3 or V1–V3 is recommended, and §6.2's U1 and U2 remain unselected
  for this figure as for the primary one. §8's table carries the obligation.
- **The occupancy numbers themselves.** They are measurements, and this document does not assert
  measurements it has not taken; §6.4.6 states where they come from.
- **Whether a downstream estimator's contract admits a filtered subpanel at all.** A treatment
  selected here is a *characterisation*; whether the module that computes it can be called on a
  sample shorter than the primary comparison's is a property of that module's interface, which this
  document neither owns nor can see. It is named as a consequence in Provenance so it is not
  discovered from the build side.

---

## 7. Candidate populations to measure over

A metric is a number **averaged over something**. What that something is changes what the headline
figure means, and it is a metric question, not only a construction one.

**How squads are sampled — the algorithm, its uniformity argument, and its acceptance rate — is
`DESIGN.md` §2's, not this document's.** What follows is only the choice of population.

| | Population | Properties | Tier |
|---|---|---|---|
| **N1** | **Synthetic squads, uniform over the feasible set** | Covers the feasible set including squads no human would build; the figure answers "regret over feasible squads". Independence from every ranker under test is the load-bearing property — a squad built by sorting on PPG would hand a PPG ranker a squad selected on its own criterion and measure the circularity rather than the method | Feasible now |
| **N2** | **Plausibility-weighted synthetic squads** | Answers "regret over squads a human would build" — narrower and more relevant, at the cost of the weighting's assumptions. Whether it is worth them is measurable from an N1 run: if method rankings are insensitive to squad composition, the weighting buys nothing | Feasible now |
| **N3** | **Real squads and picks history** | Removes the conditionality entirely. **Speculative**: `DECISION.md` §3 records that no squad, picks or bench-order history exists in the data, and `INVENTORY.md` §2.8 records that nothing samples a constrained squad either | Speculative |

**Under N1 or N2 every result is conditional on the construction**, and the conditionality covers
each element of it: the feasibility conditions, the squad count, whether squads are held or
resampled, and the universe the squad is drawn from.

### 7.1 Choices inside a synthetic population

- **Feasibility conditions** — budget cap; 2/5/5/3; ≤3 per club; registration. `INVENTORY.md` §2.2
  records the quota and the XI bounds in the staging contract, and that no code validates any of
  them.
- **When feasibility is assessed.** Once at a build gameweek, or re-checked per gameweek.
  `INVENTORY.md` §2.2 records 27 of 841 players changing club and §2.7 records 600 of 841 changing
  price across the season, so the two differ. Assessing once matches how the game works — a manager
  buys at the prices of the day, and the ≤3-per-club limit binds when a squad *changes* — provided
  the squad genuinely never changes.
- **Build-once versus resample-per-gameweek.** Two constructions, characterised in full because the
  difference between them is not where an earlier version of this section placed it.

  **Both satisfy §6.1's paired design, and neither has an advantage there.** Pairing requires every
  ranker to face the same squads in the same gameweeks. Under either construction there is one squad
  set at each gameweek and every ranker is run on all of it, so the per-squad-week difference between
  two rankers is defined on identical conditions in both cases. The claim previously made here — that
  resampling per gameweek *breaks* the pairing — was wrong, and is withdrawn to Provenance rather than
  quietly amended.

  **What actually separates them is the dependence structure of the resulting panel**, which bears on
  §6.2's schemes rather than on §6.1's design. Build-once gives each squad one row per gameweek, so a
  squad is a unit contributing many dependent rows and the panel has clusters. Resample-per-gameweek
  gives each squad exactly one row, so the panel has no clusters and the recurrence half of U3's
  objection does not arise; what survives is that squad-weeks sharing a gameweek share that week's
  realised fixtures and results. §6.2 records how the schemes read under each.

  **Build-once: what it buys and what it costs.** It matches the recurrence of the XI decision within
  a fixed squad — the same 15 faced week after week, which is the decision as a manager meets it. It
  fixes the universe at the build week, so every player entering later is excluded from every
  gameweek, not merely from the weeks before he arrived. Appendix A.2 sizes that exclusion at the GW2
  build week and records what the excluded set has in common.

  **Resample-per-gameweek: what it buys and what it costs.** It admits later entrants — the universe
  at gameweek *g* is everyone registered by *g*, so no arrival is structurally absent from any week
  after it. It satisfies the proviso in the bullet above exactly, a squad being priced and
  club-checked at the one gameweek it exists in and never changing thereafter. It does not represent
  the recurrence of the decision within a fixed squad, since no squad recurs; whether that matters
  depends on whether the metric is read as a per-squad-week cost or as a per-squad season outcome,
  which §1's candidates differ on. It multiplies the sampling work by the number of build gameweeks,
  and it makes §7.2's predicate a condition on a **set** of build weeks rather than on one.
- **The squad count.** The precision of a paired comparison is bound by whichever dimension is
  scarcer. The gameweek dimension is **window-dependent** — narrowed by §2.6's intersection and
  again by §3.1's exclusions — and is the scarce one at any count in the low hundreds, so added
  squads buy little while replay cost grows linearly in them.
- **Whether registration is a feasibility condition or a downstream filter.** As a feasibility
  condition it is the only one that removes a player from the study **outright** — the others
  constrain which combinations may be drawn. `INVENTORY.md` §2.5 records that pre-registration rows
  exist only because the DAL spine is a full player × gameweek cartesian product, and §2.7 records
  that they carry a **forward-filled price** — the player's eventual debut price — so admitting one
  prices a phantom against the cap using a value from later in the season.

### 7.2 A predicate whose validity is season-specific

If registration is enforced by a prefix test, the composed predicate is: a player is in the universe
at build gameweek *g* **iff he has a non-null `minutes` row at or before *g***.

**The condition is stated per build gameweek, because §7.1's two constructions differ in how many
there are.** Build-once evaluates the predicate at one gameweek; resample-per-gameweek evaluates it
at every gameweek in scope, each with its own universe. The condition below is written so that it
applies to a **set** of build gameweeks and reduces to the single-week case when the set has one
member. An earlier version of this section was written for one build week and does not generalise;
the withdrawal is recorded in Provenance.

**The general form of the condition.** The predicate misclassifies a player at build gameweek *g*
exactly when he is **registered at or before *g* and NULL at every gameweek up to and including *g***.
Such a player is indistinguishable in the data from one who has not yet registered, and the prefix
test excludes him. So the condition the predicate needs, at each build gameweek *g* in the set, is:
**no registered player is NULL throughout GW1..*g***.

**How the condition behaves as *g* grows, which is the property that matters here.** It is
**monotonically easier to satisfy**, because the prefix lengthens: a player NULL throughout GW1..*g*
is a strictly stronger requirement than one NULL throughout GW1..*g*−1. The binding cases are
therefore the **earliest** build gameweeks, where the prefix is shortest, and adding later build
gameweeks cannot make a condition satisfied at an earlier one fail. The single-week form this
section previously carried — "no blank falls in the build window" — was the special case of this at a
short prefix, where a blank is the only realistic way to produce an all-NULL prefix for a registered
player.

**A related property of the same predicate: the universe is monotone nondecreasing in *g*.** Once a
player has a non-null row he satisfies the predicate at every later gameweek, so U_*g* ⊆ U_*g*+1 and
per-gameweek evaluation never removes a player it has already admitted. Nothing in the condition
above turns on this, but it is the reason a misclassification at *g* is a deferral rather than a
permanent exclusion when the predicate is evaluated at more than one gameweek.

**How it resolves at GW31 and GW34, this season's two blank gameweeks.** Appendix A.1 places genuine
no-fixture blanks at GW31 (161 rows) and GW34 (248 rows) and nowhere else. Taking those as build
gameweeks, the condition asks whether any registered player is NULL throughout GW1..31, or throughout
GW1..34. A player registered before GW31 whose team blanks at GW31 has thirty non-blank prior
gameweeks in which to have accrued a non-null row, so the blank alone cannot produce an all-NULL
prefix for him. The blank is not, by itself, a source of misclassification at a prefix that long —
which is the general property above in its concrete form.

**The residual case, and the measurement that would close it.** One case is not settled by A.1 and
should not be presented as if it were: a player whose **first** gameweek is itself a blank one — he
registers at GW31, his team does not play, and he is NULL throughout GW1..31. He is excluded from the
GW31 universe and admitted at GW32 when a non-null row appears. **Appendix A.1 cannot observe this
case**, because its counting rule is "`minutes` is NULL and an earlier non-null row exists for that
player", and this player has no earlier non-null row by construction. The measurement that would
close it is a count of players whose first non-null `minutes` row falls immediately after GW31 or
GW34 and whose club blanked in that gameweek. That measurement does not exist; taking it is
`INVENTORY.md`'s, and this document records the requirement rather than asserting an answer.

**What the residual case costs depends on §7.1's construction, and differs sharply between them.**
Under build-once at a blank build gameweek the misclassification is **permanent** — the player is
absent from every gameweek of the study. Under resample-per-gameweek it is a **one-week deferral** —
he is absent from that gameweek's universe and present in every later one, by the monotonicity
property above. The same defect in the predicate therefore has a different magnitude under each, and
neither reading is selected here.

**This is a property of the 2025-26 fixture calendar, not a general fact**, and must be re-checked
against any other season — as the general condition above, evaluated at whichever gameweeks the
construction makes build gameweeks, not as the blank-in-the-window shorthand. The supporting
measurement is in **Appendix A**.

---

## 8. What a design selecting from this survey must decide

Listed so the gap left by removing this document's verdicts is explicit rather than silent.
`DESIGN.md` currently cites `METRIC.md` for several of these as settled; after this rewrite they
are **not settled anywhere**, and `DESIGN.md`'s own pass must select and justify each.

| # | Selection required | Candidates |
|---|---|---|
| 1 | The primary scoring metric | §1, P1–P7 |
| 2 | Auto-substitution treatment | §2.1 |
| 3 | Substitution trigger semantics | §2.2 |
| 4 | No-fixture ranking rule | §2.3 |
| 5 | Incoming-substitute eligibility | §2.4 |
| 6 | The three substitution mechanics | §2.5 |
| 7 | Scope and window handling | §2.6 |
| 8 | Conditioning scheme and zero-gap handling | §3.1 |
| 9 | The as-of denominator | §3.2 |
| 10 | A bench-order scoring rule — **no candidate exists** | §4.1 |
| 11 | The bench-order denominator | §4.2 |
| 12 | Which naive rankers form the floor | §5.1 |
| 13 | How the floor is determined | §5.3 |
| 14 | Paired or unpaired; which resampling schemes; the resample count | §6.1, §6.2 |
| 15 | Which success conditions, and any threshold | §6.3 |
| 16 | The population, and the choices inside it | §7 |
| 17 | The uncertainty treatment on an exclusion-filtered subpanel, and the occupancy conditions it is selected against | §6.4, W1–W3 and V1–V3 |

**Two of these were formerly blocked on something outside `DESIGN.md`; neither is now.** #12 depended
on the `points_roll3` governance question, which §5.2 records as **measured** — the record answers it,
and `DESIGN.md` §9.1 draws the verdict. #10 had no candidate to select from until §4.3 characterised
O1–O5.

**#17 is new, and it is not blocked — it is *conditional*.** §6.4 characterises the candidates and
names the occupancy profile they are selected against; §6.4.6 records that the profile is unmeasured
and falls out of the first run. So #17 may be selected as a rule over the profile before the run, or
as a choice after it, and §6.4.6 states what pre-registration permits in each case.

*Row #10 is stale as written: §4.3 characterises five candidates, O1–O5. It is left standing in this
pass, which is §6's, and its correction belongs to the pass that owns §4.*

---

## Appendix A — measurements recorded only in this document

**These are repository facts, and under the file-purpose charter they belong in `INVENTORY.md`.**
They are held here rather than moved because each is load-bearing for a candidate above and
relocating them silently would be the wrong way to do it. **Flagged for a human decision.**

All four were re-verified against `~/.fpl/fpl.mart.parquet` on 2026-08-20.

**A.1 — Genuine no-fixture blanks fall at GW31 and GW34 only.** Counting rows where `minutes` is
NULL and an earlier non-null row exists for that player: 161 rows at GW31, 248 at GW34, none in any
other gameweek. This is what makes §7.2's prefix predicate unambiguous over the early gameweeks,
and it is a property of the 2025-26 calendar.

**A.2 — The squad universe at GW2 is 705 of 841 players.** 82 GK, 233 DEF, 315 MID, 75 FWD, across
all 20 clubs. The 136 excluded players (16.2%) all appear later in the season, which confirms they
are genuine late entrants rather than a data artefact.

*What follows from the count depends on §7.1's construction.* Under **build-once at GW2** these 136
are never selected, never benched, and enter no figure at any gameweek — so nothing measures how a
method would have handled them, and the retained pool is a population defined by having arrived by
GW2. Under **resample-per-gameweek** the figure characterises the smallest of the per-gameweek
universes rather than the only one: each of the 136 enters the universe at the gameweek he registers
and is available from then on. The count is the same measurement under both; only its consequence
differs, and neither construction is selected here.

*Two things this measurement does not establish.* It does not characterise the universe at any
gameweek after GW2 — no per-gameweek universe count has been taken, so the composition of the later
universes is unmeasured. And it does not characterise **what the 136 have in common beyond arriving
late**; whether the excluded set differs systematically from the retained one on any quantity a
ranker is sensitive to would need a separate measurement, and none has been taken.

**A.3 — Season-long and 3-gameweek PPG are identical at GW2, GW3 and GW4.** On the population §3.2
describes (in-game window, blanks and no-fixture weeks at 0): identical for 100% of players at all
three gameweeks, first divergence at GW5. Bears on §5.3.

**A.4 — Across GW5–38 the two statistics still return equal values on 38.6% of player-gameweek
rows.** 98.3% of those ties are players whose entire in-game history is zero points, where both
correctly report 0 and neither can rank; among rows with any scoring history the two agree on 1.1%.
This is a property of the player universe — 38.0% of rows carry a zero season-to-date PPG — not a
degeneracy of the statistics. *A.4 is the one measurement here that was not independently
re-verified in this pass; the GW2–GW4 identity (A.3) was.*

---

## Provenance

**What this document was, and what changed.** It previously specified a single metric as settled —
counterfactual regret, with fixed substitution mechanics, a fixed floor rule, a fixed 10%
materiality threshold and a fixed resample count — and described alternatives as rejected. Under the
file-purpose charter that content is `DESIGN.md`'s. It has been reorganised into candidates with
their properties and requirements, and every verdict removed. **No characterisation was deleted; the
selections attached to them were.**

**Content that left this document.**

- **Implementation direction** — that the harness should read a predicate rather than derive it,
  that a bootstrap implementation must be named at the call site by full module path, that the
  recent-form statistic must be computed inside the harness, and that this harness must not adopt
  `assert_no_future_leakage`. All are `DESIGN.md`'s. None is recorded elsewhere yet.
- **Decision-domain argument** — that no manager selects on season-long PPG, so beating it
  demonstrates little. `DECISION.md`'s territory; **recorded there in `DECISION.md` §1** (§5.1).
- **Repository facts** — those already in `INVENTORY.md` are now cited to it; those recorded only
  here are in Appendix A.

**Two characterisations withdrawn, on a pass prompted by `DESIGN.md`.** Both were filed as conflicts
in `DESIGN.md`'s Provenance — that document may cite this one but not write to it — and both are
recorded here with the reason so they are not re-proposed. Neither withdrawal selects anything; each
replaces a wrong property statement with a correct one.

- **Withdrawn: "resampling per gameweek … breaks the pairing" (§7.1).** The claim was false. §6.1's
  paired design requires every ranker to face the same squads in the same gameweeks, and under
  resample-per-gameweek there is one squad set at each gameweek on which every ranker is run, so the
  requirement is met exactly. The property that does distinguish the two constructions is the
  dependence structure of the resulting panel, which bears on §6.2 rather than §6.1; §7.1 now states
  it there. The consequence of the error is worth recording, because it was not confined to this
  document: a pairing objection is decisive against any construction that carries it, so while the
  sentence stood, resample-per-gameweek was not a live candidate for a design to select, and
  `DESIGN.md` selected build-once partly on its authority. `DESIGN.md` §10.4 works the refutation
  through; the correction here is stated on this document's own terms and does not depend on it.
- **Withdrawn: §7.2's condition in its single-build-week form.** "The composed predicate is
  unambiguous only because the early gameweeks contain no genuine no-fixture blanks" is a correct
  statement about one build week at a short prefix, and does not generalise to a construction in
  which every gameweek is a build gameweek. §7.2 now states the condition per build gameweek — no
  registered player NULL throughout the prefix — of which the withdrawn form is the special case, and
  records that the condition is monotonically easier to satisfy as the prefix lengthens. **A
  measurement requirement was surfaced in the process and is not closed**: Appendix A.1's counting
  rule cannot observe a player whose first gameweek is itself a blank, which is the one residual
  misclassification case. A.1 is not corrected here — it accurately reports what it counted — and the
  new measurement is `INVENTORY.md`'s to take.

**The bench-order gap, closed on a pass prompted by `DESIGN.md` §0.10.** §4.1 formerly stated that
**no** candidate scoring rule for bench order existed in this folder and flagged it as the largest
genuine gap in the survey; §4 characterised candidate *denominators* only. `DESIGN.md` §0.10 recorded
that it had constructed a rule rather than selected one, named two alternatives it wanted
characterised — scoring an ordering by the points of the player it brought on, and rank correlation
against the realised ordering — and routed the work here. **That statement is now superseded.** §4.3
characterises five candidates, **O1** through **O5**, with tiers; §4.4 records an unresolved framing
question; §4.2's B1 and B2 are unchanged, and the section numbering was held fixed so downstream
citations still land.

**What this pass did not do, deliberately.** It selected nothing. It did not rank the five, describe
any of them as preferred, or treat the rule a downstream document already constructed as having an
incumbent's standing — that rule is characterised as **O1**, on the same footing as the other four
and with the properties that tell against it stated as plainly as the ones that tell for it. The
handling follows §0.4's precedent for P1: a candidate an upstream or downstream document has already
committed to is still characterised alongside its alternatives, because a survey that omitted it
would not be a survey.

**Three consequences of this pass that are not this document's to fix.**

1. **Downstream citations of the superseded sentence.** `DESIGN.md` §0.10 and §4.1 both cite §4.1's
   "no candidate exists" statement as the reason a construction was made instead of a selection, and
   §4.4 there rests on the same ground. Those citations were accurate when written and are not now.
   Whether §4.4's constructed rule survives contact with O2–O5 is a **selection**, so it is a
   `DESIGN.md` pass; nothing here presumes its outcome. This document does not write to `DESIGN.md`
   and has not.
2. **A charter inversion, recorded at §4.1 and repeated here.** Characterising a bench-order rule
   requires §2.5's substitution mechanics, which this document holds **open** and which have been
   settled downstream. Either the mechanics are properly open here and §4.3's candidates rest on
   unfixed premises, or they were never open and §2.5 overstates the choice. This is the same shape
   as §0.4's unreconciled item, and it is flagged on the same terms rather than resolved.
3. **Three `INVENTORY.md` gaps, listed at §4.3.2 rather than filled.** Tie frequency within a
   squad-week's bench, whether a rank-correlation routine exists and with what tie convention, and
   whether an as-of expected-points-conditional-on-playing forecast exists. Each is a repository fact
   and `INVENTORY.md` is its owner; none is asserted here, and none changes a tier.

**Nothing was added to Appendix A on this pass, and that is a decision rather than an omission.**
Appendix A holds *measurements* — repository facts recorded only in this document because they are
load-bearing for a candidate. This pass took no measurement. The quantities §4.3.2 names are
**unmeasured**, which makes them `INVENTORY.md` gaps rather than Appendix A entries, and filing an
unmeasured quantity there would misrepresent what the appendix contains.

**The §4.11 uncertainty question, resolved in §6 after being wrongly routed to §4.** A downstream
document routed uncertainty-on-the-ordering-sample to the bench-order survey pass. §4.5 came back
with: *"§6's candidate designs are written for the primary comparison, where the unit is a
squad-week. An ordering-relevant squad-week is a different and much rarer unit, and whether §6.2's
resampling schemes transfer to it is not characterised here for any of the five."* **That is
withdrawn.** Its premise misreads §6.2: the schemes there are indexed by which **margin** of the
squad × gameweek panel is resampled — U1 the squad margin, U2 the gameweek margin — and the
squad-week is the *row*, which is the unit of U3 alone, the scheme §6.2 rejects. The ordering sample
is the same panel under a different exclusion predicate (B2, §4.2), in the same way the primary
sample is the panel under §3.1's zero-gap exclusion. §6.4 carries the resolution.

**Why the original routing could not have worked, which is worth recording so it is not repeated.**
The question was sent to §4 as though it were a property of the scoring rule, and it is not: every
one of O1–O5 is a mean over surviving rows of the same panel, so none of them can differ from
another in which margins exist to be resampled. A pass aimed at §4 would have had to answer it five
times and would have got the same answer each time. The gap was in §6's own characterisation —
specifically, that §6.2's preconditions on occupancy were left implicit because the primary panel
satisfies them silently. §6.4.3 names them A1, A2 and A3.

**What this pass added, and what it deliberately did not.** §6.4 characterises three candidate
treatments on the squad margin (W1–W3) and three on the gameweek margin (V1–V3), with tiers, and
records the connection to §6.3's S2. **It selected none of them**, and §8 carries the obligation as
new row #17. It also took no measurement: §6.4.6 names the two occupancy quantities the selection
turns on and records that neither exists, which makes them a gap rather than an Appendix A entry —
the same reasoning the bench-order pass applied to §4.3.2's three.

**One consequence for a downstream document, named rather than left to be found from the build
side.** A treatment selected from §6.4 is computed by some estimator, and a filtered subpanel is
**shorter than the primary comparison's sample by construction** — fewer surviving gameweeks, fewer
rows within each. Any estimator whose interface is written against the primary comparison's
dimensions, whether by asserting a series length or by assuming a stratum is well-occupied, will
therefore reject or mis-handle a bench-order call **even where the treatment selected here is
perfectly well defined**. Whether that is so is a property of that module's contract, which this
document cannot see and does not own; it is flagged here so the selection is not made in the belief
that the computation is already available.

**What was not reconciled.** §0.4 records that `DECISION.md` §1 already commits to a cost model this
document is no longer permitted to select. That is a live inconsistency between two documents in
this folder, and it is recorded rather than resolved.

**One claim withdrawn from §5.2 on a pass prompted by `DESIGN.md` §9.1 (2026-08-23).** §5.2's
requirement table carried a row reading: *"Where an answer would be recorded — A governance verdict
belongs in `research/families/form/validate/evidence.yaml`, the durable verdict-of-record."* **That
is withdrawn**, and the reason is a property of the file rather than a change of view about where
governance verdicts belong. `INVENTORY.md` §2.1 now measures `evidence.yaml`'s per-(signal, position)
fields as `rho_pooled`, `rho_ci_lower`, `rho_ci_upper`, `block_stability_count` and `decision_class`,
with **no field expressing a scope, membership or applicability rule**. The question §5.2 poses is
about the *scope* of an exclusion, so the named file could not have carried the answer in any form.
The row is replaced by one recording where the answer actually sits — distributed across five
committed files, each stating the exclusion with its scope attached, per `INVENTORY.md` §2.1. The
withdrawal selects nothing; it replaces a wrong property statement about a file with a correct one.

**A second correction in the same pass, inherited rather than originated here.** §5.2 cited the
annotation at `dal/feat/feat_player_gameweek.py:16–22`. It is at `:94–96`; `:16–22` is the bare
`_ROLL_COLS` list and carries no comment. The citation came from `INVENTORY.md` §2.1, which has
corrected it at source, and §5.2 now cites the corrected line range. Recorded because `DESIGN.md`
§9.1 carried the same inherited citation and needed the same correction — one error, three copies,
and the copies are not independent evidence of anything.

**What this pass did not do.** It did not select F3, did not describe F4 as having lost, and did not
convert the measured requirement into a verdict. §5.2's status line reads *measured*, which is a
property of the candidates; whether either is built is `DESIGN.md` §0.12's, and this document has not
written to it. It also took no measurement of its own — every fact in the rewritten §5.2 is cited to
`INVENTORY.md` §2.1 or §3.7 — so Appendix A is unchanged.
