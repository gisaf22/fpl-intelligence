# Starting XI and Bench Order — the decision

**Status:** Specified. Not built.
**Scope:** the weekly XI-selection decision from the FPL Decision Framework's Starting XI /
Bench Order entry.

This document states *what is being decided*. It is not the metric and not the design.
`METRIC.md` — how success is measured — exists, and governs the harness.

---

## 1. What is being decided

**PRIMARY: which 11 of the 15 start.**

This is the decision that matters. It is live every gameweek, and the cost of getting it
wrong is not the score of the player you benched — it is the gap between what your XI
scored and what the best available XI would have scored. Two cases with the same benched
haul are entirely different mistakes:

- You bench a player who scores 15. Every alternative you could have started also scored
  12 or more. You lost 3. The decision was close and it went slightly against you.
- You bench a player who scores 15 to start a player who blanks at 1. You lost 14. The
  decision was consequential and you got it wrong.

Losses are also unequal in ways beyond size. A large loss on a call where the evidence was
genuinely balanced beforehand is variance — the same call would be right often enough to be
worth making again. A large loss on a call where the evidence pointed clearly the other way
is a method failure. And a small loss repeated in one direction across many gameweeks is a
systematic bias, which is more fixable and more damaging than any single bad week.

This has a direct consequence for measurement: gameweeks where every reasonable method
picks the same XI carry no information about whether a method is any good. The informative
sample is the gameweeks where methods disagree, and it is smaller than 38. `METRIC.md` must
say how it separates these cases rather than reporting one averaged number over all of them.
It does, in `METRIC.md` §1's three-quantity table and §3's closeness conditioning.

**SECONDARY: the priority order of the remaining 4.**

Bench order pays out more rarely than it first appears, and the gap matters enough that
`METRIC.md` §4 names two separate counts. A starter failing to play and a substitution firing is
the **substitution count** — and that is a *primary*-path number, because the substitution changes
what the chosen XI actually scored. The **ordering** decision is live only in the subset of those
weeks where the orderings under comparison would have brought on **different** players; where every
candidate ordering answers the same way, the ordering could not have mattered. That narrower
**ordering-relevant count** is the sample this secondary decision is measured on.

That makes it a small-sample, small-stakes decision — smaller than the count of weeks in which a
starter missed, which is the number it is easy to mistake it for. It is reported **separately** and
not folded into the primary number, because averaging a rarely-live decision into a weekly one
hides both.

**A note on framing.** The consequence being avoided is benching a haul. But hauls are not
directly predictable, and this decision does not claim to predict them. What is being
selected on is **minutes-certainty and baseline scoring rate** — will this player play, and
what does he score when he does. The haul consideration belongs in **how success is
measured**, not in the selection rule itself — collapsing the two would make the rule chase a
quantity it cannot estimate.

**Correction.** An earlier version of this section said the metric would handle hauls by
*weighting the tail* — how often a large score sat on the bench — and that `METRIC.md` would
make that weighting precise. That promise predates the correction of the cost model to
counterfactual regret, and it is withdrawn. Regret already prices the tail by magnitude:
benching a 15 when every alternative returned 2 is a large regret, and benching the same 15
when the alternatives returned 12 is a small one. An explicit haul coefficient on top of that
would double-count the same effect, and no evidence available here would justify a value for
it. `METRIC.md` §1 reports the regret distribution instead.

## 2. Whose goal it serves

The framework attaches a stated objective to each decision — protect rank, or chase.
Starting XI is adjacent to Captaincy in the weekly sequence and typically inherits the same
Goal that week.

The goal changes which configuration is right. A manager protecting rank starts the nailed
player. A rank-chaser may bench a nailed player to start a higher-ceiling doubtful one,
accepting the minutes risk explicitly as the price of variance. Both can be correct
selections under their own objective, which means **the goal is an input to the decision,
not a commentary on it** — and a metric that scores one configuration against a single
fixed objective is measuring only half the decision.

The FPL Decision Framework itself is a separate thread and is not detailed in this
repository (`docs/PROJECT.md` §CRISP-DM ladder records it as such). This section states the
dependency; it does not restate the framework.

## 3. What is given, not decided here

The **15-man squad is fixed**. This decision takes the squad as an input and selects within
it.

**But no real squad exists in the data.** The repository holds no squad, picks, or bench-order
history for any manager. The `starts` column is not that record — it means the player started
for *their club*, not that a manager started them in an FPL XI. There is therefore nothing to
look up: every replay of this decision runs on **synthetic squads**. That makes the input a
modelling choice rather than an observation, and it makes every result conditional on how
those squads were constructed. `METRIC.md` §2 fixes the construction and states the same
conditionality from the metric's side.

Out of the decision entirely: budget arithmetic, transfers, and chip-status resolution.
Per the framework's dependency order, the XI decision is made **only after** the Transfer
and Chip decisions resolve for the week — those determine which 15 players are available to
select from, so they must settle first.

## 4. Context and evidence that bear on it

**Player-level.** Nailed versus rotation-risk status; fixture.

**Competitive context.** Template XI composition, evaluated per pool — mini-league versus
overall or top-10k. These pools can disagree about the same configuration, the same caveat
that the Captaincy work established when the choice of pool changed which strategy looked
best.

**Evidence carries confidence, and the levels are not interchangeable.** An official "75%
chance of starting" statement from a manager is a positive signal of a known strength. A
bare absence of injury news is not the same thing — it is the absence of a signal, which is
weaker and can mean nothing was said rather than nothing is wrong. Neither is certainty,
but they should be weighed differently, and a rule that treats "no news" as equivalent to
"declared fit" is discarding the distinction.

## 5. Explicitly out of scope for this slice

Named here so their absence is deliberate rather than an oversight.

- **Predicting hauls directly.** The decision selects on likelihood of playing and baseline
  scoring rate, not on ceiling. Ceiling-chasing — starting a doubtful high-variance player
  over a nailed steady one — is a goal-dependent variant (§2). Noted, not built first.
- **Chip interaction.** Bench Boost turns bench order into a scoring-stakes decision,
  because bench points count. That changes the secondary decision from a rarely-live
  ordering into a live scoring one. Out of scope for the first build; a known variant.
- **Squad construction, transfers, and multi-week planning.** Given, per §3.
- **Competitive context as an *active* input.** §4 lists it as context that bears on the
  decision. The first build evaluates against **points scored**, not against rival
  differentials or template divergence. Making the competitive frame an input is a
  different objective and would need a different metric.

## 6. Status

**Specified. Not built.** No code exists for this decision.

**The metric is defined.** `METRIC.md` carries it, and names the naive baselines that
establish the floor. The harness design and the bench-order scoring rule remain open; nothing
in this document should be read as fixing them.

**Named input to the Phase 2 harness design: where the harness code lives.** `decisions/starting_xi/`
has no legal home in the import graph. `serve/` may not import `model` or `research`, and
`research/` may not import `model`, while the harness needs both `p_play` (model) and the resampling
kernels (research) — so none of the existing layers can host it as they stand. `INVENTORY.md` §4
(M4) proposes making this folder an importable package with its own import contract, at a cost of
two edited files and no moved call sites. It is recorded here as a **named input to the Phase 2
design document**, not settled here: it is a design question rather than a documentation one, and
it blocks Phase 3 the moment code is written.

**Correction.** This section previously said the metric was not yet defined and was pending a
data check on three things. Two of those checks are answered and the third was miscategorised:

1. **Auto-substitution mechanics** — answered. `METRIC.md` §6 fixes the trigger.
2. **How many gameweeks the bench-order decision was actually live** — **not a documentation
   dependency, and it never was.** It is a harness output, and `METRIC.md` §4 now separates two
   counts that this item originally ran together. Squad-weeks in which a starter recorded no
   minutes and a substitution fired are the **substitution count**, and that number sizes the
   *primary* figure rather than this one. What sizes the secondary decision is the narrower
   **ordering-relevant count** — the subset of those weeks in which candidate orderings would have
   brought on different players; a substitution every ordering answers the same way says nothing
   about ordering. Neither count can exist until the harness runs, so no document can discharge
   them. `METRIC.md` §4 requires both to be reported alongside every bench-order figure, which is
   the correct home for them. The concern behind this item stands — if the **ordering-relevant**
   count is small, the secondary decision may not be measurable on one season — but it is a result
   to be read, not a check to be cleared beforehand.
3. **How to define "the call was close" from the data** — answered. `METRIC.md` §3 fixes the
   definition and the exclusion rule.
