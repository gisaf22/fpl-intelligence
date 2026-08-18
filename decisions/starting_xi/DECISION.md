# Starting XI and Bench Order — the decision

**Status:** Specified. Not built.
**Scope:** the weekly XI-selection decision from the FPL Decision Framework's Starting XI /
Bench Order entry.

This document states *what is being decided*. It is not the metric and not the design.
`METRIC.md` — how success is measured — is the next document and is not yet written.

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

**SECONDARY: the priority order of the remaining 4.**

Bench order only pays out when a starter does not play and auto-substitution fires. That
makes it a small-sample, small-stakes decision — it is only live in the gameweeks where a
starter actually missed. It is reported **separately** and not folded into the primary
number, because averaging a rarely-live decision into a weekly one hides both.

**A note on framing.** The consequence being avoided is benching a haul. But hauls are not
directly predictable, and this decision does not claim to predict them. What is being
selected on is **minutes-certainty and baseline scoring rate** — will this player play, and
what does he score when he does. The haul consideration belongs in **how success is
measured** — weighting the tail, i.e. how often a large score sat on the bench — not in the
selection rule itself. Collapsing the two would make the rule chase a quantity it cannot
estimate. `METRIC.md` makes this precise.

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

The metric is **not yet defined**. `METRIC.md` is the next document, and it is pending a
data check on three things:

1. **Auto-substitution mechanics** — the exact rules that govern when a bench player is
   substituted in, since the secondary decision's payout is defined entirely by them.
2. **How many gameweeks the decision was actually live** — the count of weeks in which a
   starter did not play. If that count is small, the secondary decision may not be
   measurable on one season of data, and the metric has to say so rather than report a
   number over a sample too thin to carry it.
3. **How to define "the call was close" from the data** — how to identify the gameweeks
   where reasonable methods would disagree, since those are the informative sample and the
   metric's conditioning depends on being able to name them.

Neither the metric, the baselines, the harness design, nor the scoring rules are decided.
Nothing in this document should be read as fixing them.
