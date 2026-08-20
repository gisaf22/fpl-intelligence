# Starting XI and Bench Order — the decision

**Status:** Specified and designed. Not built.
**Scope:** the weekly XI-selection decision from the FPL Decision Framework's Starting XI /
Bench Order entry.

This document answers one question — **what decision are we trying to make?** It is not the
metric, not the evidence and not the design. `METRIC.md` characterises candidate metrics.
`INVENTORY.md` records what exists in the repository. `DESIGN.md` decides what is built.

---

## 1. What is being decided

**PRIMARY: which 11 of the 15 start.**

This is the decision that matters. It is live every gameweek, and the cost of getting it
wrong is not the score of the player you benched — it is the gap between what your XI
scored and what the best available XI would have scored. Two cases with the same benched
haul are entirely different mistakes: one where every alternative you could have started
scored about as much, and one where the player you started instead blanked.

**SECONDARY: the priority order of the remaining 4.**

This is a small-sample, small-stakes decision, and it is not live every week. Bench order is
reported **separately** and not folded into the primary number, because averaging a
rarely-live decision into a weekly one hides both. What sizes it, and how, is `METRIC.md` §4.2's.

**A note on framing.** The consequence being avoided is benching a haul. But hauls are not
directly predictable, and this decision does not claim to predict them. What is being
selected on is **minutes-certainty and baseline scoring rate** — will this player play, and
what does he score when he does. The haul consideration belongs in **how success is
measured**, not in the selection rule itself — collapsing the two would make the rule chase a
quantity it cannot estimate.

**A note on what a naive comparison proves.** No manager selects an XI on season-long
points-per-game. The real default is closer to recent form, fixture, and whether the player is
expected to start — so a method that beats a season-long PPG ordering has beaten something nobody
plays, and has not yet shown it improves the decision as anyone actually makes it. Clearing that
floor is a sanity check on the harness, not evidence about the decision; evidence about the
decision requires a floor a manager would recognise as their own habit.

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

**But no real squad exists in the data.** `INVENTORY.md` §2.8 records that the repository holds
no squad, picks, or bench-order history for any manager, and that the `starts` column is not that
record — it means the player started for *their club*, not that a manager started them in an FPL
XI. There is therefore nothing to look up: every replay of this decision runs on **synthetic squads**. That makes the input a
modelling choice rather than an observation, and it makes every result conditional on how
those squads were constructed. `METRIC.md` §7.1 states the same conditionality from the
metric's side.

Out of the decision entirely: budget arithmetic, transfers, and chip-status resolution.
Per the framework's dependency order, the XI decision is made **only after** the Transfer
and Chip decisions resolve for the week — those determine which 15 players are available to
select from, so they must settle first.

## 4. Context that bears on it

**Player-level.** Nailed versus rotation-risk status; fixture.

**Competitive context.** Template XI composition, evaluated per pool — mini-league versus
overall or top-10k. These pools can disagree about the same configuration, the same caveat
that the Captaincy work established when the choice of pool changed which strategy looked
best.

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

**Specified and designed. No code exists.** `METRIC.md` and `DESIGN.md` carry the metric and
the build. What has not started is the build.

**This document fixes neither the metric nor the design, and nothing in it should be read as
doing so.** Both were open when it was written; both are now addressed elsewhere.

**Where the harness code lives** was recorded here as a named input to the Phase 2 design
document rather than settled. `DESIGN.md` §3 settles it.

---

## Provenance

**Retired reasoning, kept so it is not re-proposed.** Each entry below records a framing this
document once carried, with the reason it was withdrawn. None of them states this document's
current position; §1–§6 do that.

**§6 — the sentence disclaiming authority over the harness.** §6 previously read: "The harness
design and the bench-order scoring rule remain open; nothing in this document should be read as
fixing them." The harness is now closed by `DESIGN.md`; the bench-order scoring rule is not —
`DESIGN.md` §0.10 records that no candidate set exists to select from — so the sentence is
retired as a status claim rather than because both halves resolved. The point it carried survives
and is restated in §6 as a standing disclaimer of authority rather than a status report: this
document never fixed the harness design, and never contained the injected-`rank_fn` constraint
that `DESIGN.md` §1.3 and §3.2 record as their own.

**§6 — the three pending data checks.** §6 previously said the metric was not yet defined and was
pending a data check on three things. Two of those checks are answered and the third was
miscategorised:

1. **Auto-substitution mechanics** — answered; `DESIGN.md` §0.3 fixes the trigger.
2. **How many gameweeks the bench-order decision was actually live** — **not a documentation
   dependency, and it never was.** It is a harness output, and no document can discharge it. The
   concern behind the item stands and is current: if the ordering-relevant count is small, the
   secondary decision may not be measurable on one season. That is a result to be read, not a
   check to be cleared beforehand.
3. **How to define "the call was close" from the data** — answered; `DESIGN.md` §0.8 fixes the
   definition and the exclusion rule.
