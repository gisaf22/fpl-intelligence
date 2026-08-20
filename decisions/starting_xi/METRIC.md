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

### 4.1 The scoring rule is undefined

**No candidate scoring rule for bench order exists in this folder.** Whatever rule is written has
to respect §2.5's mechanics — the GK/outfield split and the priority-queue semantics — and those
are themselves unresolved. A rule written before them is a guess in the shape of a decision.

*Flagged: this is the largest genuine gap in the survey. §4 characterises candidate
**denominators** only.*

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

### 5.2 One requirement that is not yet satisfied — F3 and F4

`INVENTORY.md` §2.1 records that **no `points_roll3` exists on the governed mart**: the feat layer
omits `total_points` from its rolling set, annotated as removed by lens evaluation for evaluation
circularity or G2-FAIL.

**What is unsettled is not the absence but its scope** — whether that exclusion is a governance
decision that also binds a *baseline ranker*, or an omission specific to the signal registry's
purposes. The circularity concern was about a governed signal predicting a target derived from
itself, which is not what a baseline ranker does; but that argument has to be made and accepted
rather than assumed.

| | |
|---|---|
| **Question** | Does the governed mart's exclusion of `points_roll3` bind a baseline ranker in this harness? |
| **What settles it** | The lens record behind the annotation on `_ROLL_COLS` in `dal/feat/feat_player_gameweek.py`. Reading the record is the whole task |
| **Where an answer would be recorded** | A governance verdict belongs in `research/families/form/validate/evidence.yaml`, the durable verdict-of-record |
| **Status** | Open. F3 and F4 are **speculative until it is answered** — not because the statistic is hard to compute, but because whether it may be computed here is undetermined |

**The same divergence has been observed from the other side.** `INVENTORY.md` §3.7 records that
`assert_no_future_leakage` requires `points_roll3` and that the existing decision-backtest path is
unrunnable against the governed mart for that reason. Whichever way the question is answered, the
guard and the mart contract cannot both stay as they are.

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
| **U3** | Resample **squad-week rows** as independent draws | The same squad recurs across every gameweek and the same gameweek across every squad; treating the product as independent inflates the effective sample by roughly two orders of magnitude and manufactures precision the data does not contain. Holds at any window length | Feasible now |
| **U4** | **Cluster** bootstrap — resample clusters, take all of a drawn cluster's rows | The structurally correct treatment of the panel. `INVENTORY.md` §2.9 records a cluster resampler hard-wired to a rho statistic and **no generic cluster-bootstrap-of-a-mean** | Feasible now |

U1 and U2 answer different questions and can be reported as two intervals rather than one.

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
- **Build-once versus resample-per-gameweek.** Holding one 15 all season matches the paired design
  of §6.1 and the recurrence of the XI decision within a fixed squad; it also fixes the universe at
  the build week and excludes everyone who enters later. Resampling per gameweek admits later
  entrants and breaks the pairing.
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
**iff he has a non-null `minutes` row at or before the build gameweek**.

That composition is unambiguous **only because the early gameweeks of this season contain no genuine
no-fixture blanks**, so every NULL there is a prefix. Were a blank gameweek to fall in the build
window, a *registered* player could be NULL throughout it, the prefix test could not separate him
from an unregistered one, and the predicate would need a different form.

**This is a property of the 2025-26 fixture calendar, not a general fact**, and must be re-checked
against any other season. The supporting measurement is in **Appendix A**.

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

Two of these are **blocked on something outside `DESIGN.md`**: #12 depends on the `points_roll3`
governance question (§5.2), and #10 has no candidate to select from.

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
are genuine late entrants rather than a data artefact. Under a build-once population (§7.1) they
are never selected, never benched, and enter no figure — so nothing measures how a method would
have handled them.

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

**What was not reconciled.** §0.4 records that `DECISION.md` §1 already commits to a cost model this
document is no longer permitted to select. That is a live inconsistency between two documents in
this folder, and it is recorded rather than resolved.
