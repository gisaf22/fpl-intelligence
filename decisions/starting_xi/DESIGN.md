# Starting XI and Bench Order — the design

**Status:** Phase 2 design. `§0` makes the metric selections `METRIC.md` §8 leaves open; §1–§10
state how the harness is built.
**Scope:** this document answers one question — **given the evidence, what system should we
build?** `DECISION.md` states what is being decided, `METRIC.md` characterises candidate metrics
without selecting among them, and `INVENTORY.md` states what exists in the repository today.

This document is reasoning in prose. It carries no verdict tables, no reuse labels and no
capabilities table of its own; where a fact about the repository is needed it is **cited to
`INVENTORY.md`**, never restated as a first-hand finding.

Section numbers are used by all four documents in this folder. Every cross-reference here names the
document — `METRIC.md` §6, never a bare §6. Sections §1–§10 keep the numbers other documents
already cite; the metric selections were added afterwards and are numbered **§0** so that no
existing cross-reference moves.

---

## 0. The metric selections

`METRIC.md` is a survey that selects nothing, and its §8 lists sixteen selections a design must
make before the harness can be built. This section makes them. Each selection names the
`METRIC.md` candidate adopted, the candidates not adopted, and the reason — which is the only place
in this folder where those reasons are recorded.

Two of the sixteen cannot be settled here, and are stated as gaps rather than filled: **#10**, the
bench-order scoring rule, because `METRIC.md` §4.1 characterises no candidate to select from
(§0.10); and **#12**'s recent-form component, which is gated on a governance question outside this
folder (§0.12, §9.1).

### 0.1 The primary scoring metric — P1, counterfactual regret (#1)

**Selected: P1.** This selection is not open. `DECISION.md` §1 already fixes the cost model in
prose — the cost of a wrong call is the gap between what the chosen XI scored and what the best
available XI would have scored — and `METRIC.md` §0.4 records that commitment while noting the
tension it creates with a survey that is not permitted to select. The tension is real and stays on
the record; it does not reopen the choice, because `DECISION.md` governs `DESIGN.md`.

**What P1 buys, in `METRIC.md` §1's terms.** It prices the *decision* rather than one player's
outcome, it is bounded below at 0 when the counterfactual maximises over exactly the set the chosen
XI is drawn from, and it is a counterfactual over realised points rather than a forecast.

**Not selected, and why.**

- **P2, benched-player points.** It prices the outcome rather than the decision and charges a
  ranker for an unavoidable loss identically to an avoidable one (`METRIC.md` §1, P2). That is the
  distinction the whole slice exists to make.
- **P5, tail-weighted regret.** `METRIC.md` §1 records that it double-counts against P1, which
  already prices a benched haul by magnitude, and that no evidence available sets its coefficient.
  Every result would be conditional on an unmeasured judgement.
- **P6 and P7** are speculative in `METRIC.md`'s sense — P6 needs a manager objective the data does
  not record, P7 needs an objective function `DECISION.md` §5 puts out of scope.

**P3 is adopted as a companion, not as an alternative.** `METRIC.md` §1 records that P3 is a
presentation of P1's own quantity and that it produces no single comparable number. Both properties
are why it is reported alongside the scalar rather than instead of it: the regret *distribution* —
the count and size of the worst weeks per ranker — is what a mean hides, and §7.1 makes it
representable in the artefact.

**P4 is named as required and left undefined, deliberately.** `METRIC.md` §1 records that "signed
error" cannot be regret, which is non-negative, and that nothing in this folder defines what
quantity is signed or against what reference. This design does not invent a definition. It stores
P4's presumed inputs — both XI totals, not their difference — so that whatever definition is
eventually fixed is derivable without re-running the harness (§7.6). Flagged at §7.9.

### 0.2 Auto-substitution — the chosen side only (#2)

**Selected: `METRIC.md` §2.1's asymmetric option.** The chosen XI's total is what the rules
actually delivered; the counterfactual best legal XI is computed with **no** substitutions applied.

**Why.** `METRIC.md` §2.1 states the property that decides it: applying substitutions to **both**
sides lets the counterfactual bank points from a twelfth player where a formation minimum forces a
non-featuring player in, which lifts the benchmark above what any XI *selection* could realise and
turns it into a joint XI-and-bench-order optimum — `DECISION.md` §1's explicitly secondary decision
smuggled into the primary one. Applying them to **neither** side charges a ranker for a blank the
rules of the game already covered, which measures the game's mechanics rather than the ranking.

**What the selection costs, stated rather than glossed.** `METRIC.md` §2.1 is explicit that the
asymmetric option does **not** fully separate ranking quality from bench coverage, because the
chosen side's realised total depends on the ordering that supplied the replacement. §4.9 and §4.13
carry that residual coupling from the build side; the practical consequence — every primary regret
figure names the ordering that produced it — is enforced structurally at §5.4.

### 0.3 The substitution trigger — featured at all (#3)

**Selected: a starter triggers a substitution if he recorded no minutes, covering both
`minutes = 0` and `minutes` NULL.** `METRIC.md` §2.2 names these as two structurally distinct
states and cites `INVENTORY.md` §2.5 for their separate presence on the mart.

**Why both states.** Reading the trigger as `0`-only leaves a blank-gameweek player standing in the
XI scoring nothing, which lowers every ranker's realised total for a reason that has nothing to do
with ranking. There is no partial-appearance case to tune: `METRIC.md` §2.2 records that a player
who comes on for one minute is an appearance under any reading.

**The condition `METRIC.md` §2.2 attaches, and how it is discharged.** A NULL-inclusive trigger
requires the pre-registration population to be excluded upstream, or substitution events are
manufactured from players who did not yet exist. `INVENTORY.md` §2.5 records that the DAL spine is
a full player × gameweek cartesian product and that ~84% of NULL-`minutes` rows are a
pre-registration prefix rather than a blank. §2.1 discharges the condition by **constructing the
squad universe before drawing**, so no prefix row can enter a squad at all, and §2.8 makes that a
test rather than a convention.

### 0.4 The no-fixture ranking rule — ranked last, by the harness, for every ranker (#4)

**Selected: `METRIC.md` §2.3's first option.** A player whose club has no fixture is ranked last by
the harness, identically for every ranker, and remains legal to select.

**Why.** `METRIC.md` §2.3 records the asymmetry this removes: `INVENTORY.md` §2.6 measures that
`PlayModel`'s population drops rows with null `minutes`, so `p_play` has no value on those rows
while a PPG-style ranker scores them at 0. Under any per-ranker convention, one floor ranker would
carry an implicit fixture-awareness the other two lack — as a side-effect of how its **training
frame** was built, not of what its statistic measures. `METRIC.md` §2.3 is explicit that this is a
difference in preprocessing rather than in ranking; a margin partly sourced from it would be a
population artefact reported as a method result.

**Not selected.** *Each ranker uses its own coverage* would measure fixture-awareness as a real
capability, which `METRIC.md` §2.3 correctly notes is part of what separates methods — but it
cannot be separated here from the training-frame artefact, so the capability and the artefact would
be measured as one number. *Scoring `p_play` = 0 on those rows* is semantically correct and closes
`p_play`'s coverage hole, but `METRIC.md` §2.3 records that it **preserves** the asymmetry:
`p_play` would consult the fixture calendar and the PPG baselines still would not.

**What the selection costs, and the measurement that keeps it auditable.** `METRIC.md` §2.3 names
both: nothing then measures fixture-awareness, and the rule narrows the no-fixture substitution
path, lowering §4's substitution count *by construction*. So the harness stores, per ranker and per
squad-week, whether the rule changed the selected XI (§7.6), and §7.7 requires that count reported
beside any bench-order figure. That count is the size of the confound the rejected options would
have carried.

**`is_dgw` rows are not covered by this rule and are not resolved here.** `METRIC.md` §2.3 records
that `p_play` also drops double-gameweek rows, where P(play) is not 0 and no constant is correct,
and that `INVENTORY.md` §3.4 records the materiality as unmeasurable without a squad set. Those
rows fall to the unrankable-last rule of §6.5 and the measurement is owed on the first run.

### 0.5 Incoming-substitute eligibility — required to have featured (#5)

**Selected: `METRIC.md` §2.4's first option.** A bench player enters only if he himself recorded
minutes, under the same two-state predicate as the trigger (§0.3).

**Why.** `METRIC.md` §2.4 states the failure of the alternative precisely: a non-appearance replaces
a non-appearance, scores nothing, consumes the slot, and strands behind it a bench player who *did*
feature — so a bench-order comparison would turn on queue position rather than on ordering, which
is the one thing §4 is trying to measure. It also matches the real game.

**Cost: none against the metric's lower bound.** `METRIC.md` §2.4 records that under the asymmetric
option selected at §0.2 the counterfactual has no substitutions applied, so no eligibility rule can
lift the chosen side above it and regret ≥ 0 survives either choice. The selection is made on the
bench-order argument alone.

### 0.6 The three substitution mechanics — all three, as `METRIC.md` §2.5 states them (#6)

**Selected.** The GK slot is a **separate process** from the three outfield slots; a substitution
fires only if it **preserves a legal formation**; a **skipped player stays available** for a later
vacancy in the same gameweek.

**Why each.**

- **GK separate.** It follows from the quota rather than being a free choice: `INVENTORY.md` §2.2
  records `squad_select` = 2 for GK and `squad_min_play` = `squad_max_play` = 1, so a 15 holds two
  goalkeepers and every legal XI starts exactly one. Bench order is therefore two orderings, not one
  ranking of four (`METRIC.md` §2.5) — and the GK ordering is degenerate, which is what §4.2 builds
  on.
- **Legality required.** `METRIC.md` §2.5 names the consequence of not requiring it: the
  post-substitution XI would leave the set the counterfactual maximises over, and the chosen side
  could out-score its own counterfactual. That would break P1's lower bound (§0.1), which is the
  property the whole metric rests on.
- **Skipped stays available.** `METRIC.md` §2.5 records that a rule treating a skipped player as
  spent measures a **different** bench order. The priority-queue reading is the one that matches the
  game and the one under which an ordering is a genuine ranking rather than a consumption sequence.
  §4.3's loop implements it, and §4.3's worked example shows the case where it changes the answer.

### 0.7 Scope and window handling — GW2–38, per-ranker declared windows, comparisons on the intersection (#7)

**Selected: the study-level scope is GW2–38, and each ranker declares its own window with every
comparison run on the intersection.**

**The GW1 exclusion is forced, not chosen.** `METRIC.md` §2.6 records that season-long as-of PPG is
null at GW1 — no prior gameweek exists — so GW1 is scoreable under no as-of candidate.

**Why declared windows rather than one global window.** `METRIC.md` §2.6 states both costs. A
global window drags every ranker down to the most restricted one anyone adds and discards weeks the
others could score; declared windows mean no single span describes the study and every result must
carry its own. The second cost is payable and the first is not: `INVENTORY.md` §2.6 measures
`WARMUP_GW = 3` at `model/eval/walkforward.py:58` with predictions beginning at GW4, and records
that `WARMUP_GW` is shared by every term via `_binary_component` and `_poisson_component` — so it is
not adjustable for one ranker. Under a global window the whole study would be pinned to GW4–38 by a
constant that belongs to a different subsystem. Under declared windows the restriction binds only
comparisons that actually include `p_play`, and it binds visibly.

**The obligation this creates** is that the span travels with each figure rather than sitting in a
run header; §6.3 fixes how the intersection is computed and §7.2's T3 stores it per comparison.

### 0.8 Conditioning — C1 closeness, with zero-gap weeks excluded and counted (#8)

**Selected: C1**, the gap between the best and second-best legal XI totals, with weeks where every
legal XI ties **excluded** and the excluded count reported.

**Why C1 over C2.** `METRIC.md` §3.1 records that C2 — the gap between the 11th and 12th player by
the as-of statistic — is confounded: when the three best remaining players are all defenders it
measures the `≥3 DEF` minimum binding against the ordering, not how close the selection was, and it
labels structurally forced weeks close and balanced weeks clear. C1 measures the margin between
the two configurations that were actually in contention, which is the quantity the word "close"
names.

**Why not C3 (no conditioning).** C3 has the largest sample and `METRIC.md` §3.1 states the cost:
it mixes weeks where no method could have distinguished itself into the headline figure. `METRIC.md`
§1's own note on P1 — that it is not summarised by its mean, because a single average blends
variance on close calls with method failure on clear calls — is the same objection from the metric
side.

**Why zero-gap weeks are excluded rather than retained.** They carry no information by construction:
`METRIC.md` §3.1 defines them as weeks where every legal XI ties, so no method can distinguish
itself and every ranker scores 0 regret. Retaining them pulls every candidate's mean toward 0 in
proportion to how many there are, which makes all methods look equally good and the decision look
better-measured than it is. The excluded count is reported for the reason `METRIC.md` §3.1 gives —
a large one means a thinner conditioned sample than the headline span suggests.

**The property that makes the exclusion safe for the paired design.** `METRIC.md` §3.1 records that
closeness under C1 is a property of the **squad-week**, not of the ranker, so zero-gap weeks are
identical across rankers. The same rows therefore drop for both sides of every comparison and the
pairing is undisturbed (§10.4).

**C1's cost, and where it lands.** `METRIC.md` §3.1 records that C1 requires the same enumeration
P1 needs, run twice — the maximum and the runner-up. `INVENTORY.md` §2.4 measures that the
enumeration is 8 prefix-sum combinations over position-sorted realised points, and states that the
runner-up over the same enumeration is the second-best XI. The cost is one extra pass over eight
combinations, which is nothing.

### 0.9 The as-of denominator — gameweeks elapsed, blanks and no-fixture weeks at 0, pre-registration weeks excluded (#9)

**Selected: `METRIC.md` §3.2's first option**, with its three sub-choices resolved as: blanked weeks
count at **0**, no-fixture weeks count at **0**, and pre-registration weeks **do not count at all**.

**Why gameweeks rather than appearances.** `METRIC.md` §3.2 states the property that decides it: a
gameweek-denominated rate folds the probability of playing into the statistic implicitly, which
keeps it on the same footing as a metric scored in realised points, where a non-featuring player
contributes 0. Appearance-denominated PPG is a different quantity — comparable only after
multiplying by P(play) — and `METRIC.md` §3.2 gives the concrete failure: it orders an
8-per-appearance player who features a third of the time above a nailed 4-per-week one. That
ordering is wrong for a decision scored in points actually banked.

**Blanks and no-fixture weeks at 0.** `METRIC.md` §3.2 gives the reason for the first — a manager
selecting that week faced that 0 — and the second follows identically: a player whose club had no
fixture scored 0 for anyone who started him.

**Pre-registration weeks excluded.** `METRIC.md` §3.2 frames the alternative as charging a GW20
entrant with nineteen zeros he had no opportunity to avoid. That is not a property of the player;
it is an artefact of the spine. `INVENTORY.md` §2.5 records that those rows exist only because
`dal/fct/fct_player_gameweek.py` builds a full cartesian product, and that a player who debuts in
GW20 therefore *has* GW1–19 rows synthesised as BGW with NULL performance. Counting them would score
the DAL's construction.

**The coupling `METRIC.md` §3.2 names is honoured.** It warns that if the conditioning statistic and
the baseline ranker use different denominators, "close calls" label weeks that were close under a
measure no ranker uses. Here the conditioning statistic (§0.8) and both PPG floor rankers read the
**same** population — one construction, two windows over it — which is what §8.3 fixes and asserts.

**The separation `METRIC.md` §3.2 leaves open is carried by the ranker, not the denominator.**
`DECISION.md` §1 separates "will this player play" from "what does he score when he does";
`METRIC.md` §3.2 records that either the denominator or a standalone `p_play` ranker can carry it.
This design carries it with the ranker (F1, §0.12), and keeps the denominator on the
points-actually-banked footing above. Doing both would fold P(play) into the statistic *and* score
it separately, and the two floor rankers would no longer be measuring different things.

### 0.10 The bench-order scoring rule — no selection is possible (#10)

**This selection cannot be made, and inventing one would misrepresent the evidence.** `METRIC.md`
§4.1 states plainly that **no candidate scoring rule for bench order exists in this folder**, and
flags it as the largest genuine gap in the survey — `METRIC.md` §4 characterises candidate
*denominators* only.

There is therefore nothing to select from, and this document does not manufacture a candidate set
in order to appear to have selected from one.

**What §4 does instead, and what it is not.** §4.4 constructs a rule — *ordering regret*, the gap
between the realised total under the best available ordering and under the ordering being scored,
holding the XI fixed — by mirroring the shape of P1 rather than inventing a second vocabulary. That
is a design construction and it is `DESIGN.md`'s to make; what is missing is the survey it should
have been selected against. **No alternative bench-order scoring rule has been characterised, so
this rule has not been shown to be better than anything.** It is used because the harness cannot be
built without one, not because it won a comparison.

**Flagged for a separate `METRIC.md` pass**, which is where candidate characterisation belongs
under the file-purpose charter: the alternatives to ordering regret — for instance scoring an
ordering by the points of the player it brought on, or by rank-correlation against the realised
ordering — need characterising before §4.4's rule can be called a selection.

### 0.11 The bench-order denominator — B2, the ordering-relevant count (#11)

**Selected: B2** for every bench-order claim. **B1**, the substitution count, is reported alongside
it but denominates a different claim.

**Why B2 for bench-order claims.** `METRIC.md` §4.2 records that B1 counts weeks where every
candidate ordering brings on the same player and no ordering could have done better. Using B1 as
the denominator for a bench-order figure credits a method with evidence from weeks where it was
never distinguished from its rival. B2 counts only weeks that could discriminate — `METRIC.md` §4.2
notes this is the same reasoning C1's zero-gap exclusion applies on the primary side (§0.8), which
is the consistency argument as well as the correctness one.

**B1 is not discarded.** It sizes the headline regret figure under the asymmetric option selected at
§0.2, because those are exactly the weeks the chosen total departs from the eleven as selected
(`METRIC.md` §4.2). §4.7 fixes which count denominates which claim, and §4.6 adds a third quantity —
the uncovered-blank count — that falls out of the replay and belongs beside them.

**The caveat `METRIC.md` §4.2 attaches is carried, not dropped.** Neither count is purely empirical:
the rank-last rule selected at §0.4 bounds B1 below by construction, so a low count is partly a
consequence of that choice rather than a fact about the season. §7.7 requires the artefact to store
both counts alongside the no-fixture rule count so a reader can see how much of the narrowing was
design and how much was the season.

**One further narrowing is this document's own choice and is recorded as such.** §4.6 defines B2
over the orderings **actually compared**, not over all six permutations of the three outfield bench
players. The permutation reading is systematically larger and answers a different question — "could
ordering ever have mattered here?" rather than "did the methods under comparison differ here?" — and
only the second can support a claim about *those* methods. The permutation count is a legitimate
diagnostic of the decision's headroom and may be reported as one; it is not the denominator.

### 0.12 The floor rankers — F1 and F2 now, F3 gated, F4 not pre-registered (#12)

**Selected: F1 (`p_play` alone), F2 (season-long PPG-to-date) and F3 (3-gameweek recent form)
as the pre-registered floor set, with F3 conditional on the governance question below.**

**Why a set rather than one ranker.** `METRIC.md` §5.3 records that which naive ranker wins is
itself a result — if F1 is hard to beat, that says something about the decision no candidate
ranker's score would reveal. A single nominated floor forecloses that finding.

**F4 is not pre-registered.** `METRIC.md` §5.1 records that whether F3 and F4 are both baselines or
one is a sensitivity check is a design choice rather than a property of either. F4 is a window-length
variant of F3 and adds a second copy of the same statistic to the floor set; it is kept available as
a sensitivity check and excluded from the pre-registered set, so that the floor is not
half-populated by one family. `METRIC.md` §5.1's argument for the 3-gameweek length — short enough
to track rotation, long enough that one blank does not dominate, and matching the window the
platform already uses for lag-1 rolling signals — is the reason F3 rather than F4 is the member.

**F3 is gated, and the gate is outside this folder.** `METRIC.md` §5.2 records that
`INVENTORY.md` §2.1 measures **no `points_roll3` on the governed mart** — the feat layer omits
`total_points` from `_ROLL_COLS`, annotated as removed by lens evaluation for evaluation
circularity or G2-FAIL — and that what is unsettled is not the absence but its **scope**: whether
that exclusion binds a *baseline ranker* as well as a governed signal. `METRIC.md` §5.2 states what
settles it (the lens record behind the annotation) and where the answer belongs
(`research/families/form/validate/evidence.yaml`). This document cannot answer it and does not.
§9.1 carries it as the one item blocking Phase 4. If the verdict binds, F3 does not exist in its
present form and §6.4's construction is moot rather than wrong.

**A degeneracy that must be reported, not designed away.** `METRIC.md` §5.3 records that F2 and F3
return the same number for every player at GW2, GW3 and GW4, first diverging at GW5, with the
measurement in `METRIC.md` Appendix A.3. Under the common window that includes F1 — GW4–38 (§6.3) —
one of those weeks sits inside the study and cannot discriminate between two floor rankers. §7.1
makes the degeneracy representable in the artefact rather than a caveat in prose.

### 0.13 How the floor is determined — best-performing on the common window (#13)

**Selected: `METRIC.md` §5.3's first option.** The floor is whichever naive ranker carries the
lowest mean regret, re-determined **per comparison** on the intersection of every window involved,
candidate included.

**Why not the maximal-window option.** `METRIC.md` §5.3 states the defect: it compares means taken
over different spans, and the earliest gameweeks are the thinnest-history weeks of the season, so a
mean over GW2–38 and one over GW4–38 estimate different quantities. The comparison would partly
measure which weeks each ranker was allowed to count.

**Why not a nominated floor.** It is stable and simple, and `METRIC.md` §5.3 notes a candidate can
clear it while losing to another naive ranker — which is exactly the result that would be reported
as a pass. Against the strongest naive ranker on the shared window, a pass means something.

**The consequence, which is why §7 stores it per comparison.** `METRIC.md` §5.3 records that this
option makes the floor **window-relative** — which ranker wins may differ on a narrower window — so
the floor's identity has to be reported with every result. §7.2's T3 carries `floor_ranker` and the
window as comparison-level columns for that reason, and §7.3 records why neither is run-level
identity.

**The coupling to the success bar is honoured.** `METRIC.md` §5.3 states that a "reduction of X%
against the floor's own regret" is not interpretable if numerator and denominator were computed
over different gameweek sets, so the floor option and the bar are coupled choices. Under the option
selected here both are computed on the same intersection by construction, which is what makes
§0.15's relative threshold meaningful.

### 0.14 Design, resampling schemes and the resample count — paired at the squad-week, U1 and U2 as two intervals, U1 gameweek-stratified, n = 10,000 (#14)

**Paired.** `METRIC.md` §6.1 states the reason: squad-level variation — some squads are simply
deeper and have less to gain from any method — is common to all rankers and cancels in the
difference, so what is measured is the method difference rather than the absolute regret level.
The unpaired alternative admits that variation as noise for nothing in return. The requirement
`METRIC.md` §6.1 attaches — that §2.6's common-window handling be exact — is discharged by §6.3.

**Pairing is a property of the squad-week, not of the season-long squad.** This is worth stating
explicitly, because the selection §0.16 previously made rested on the contrary reading. `METRIC.md`
§6.1 requires every ranker to face the same squads in the same gameweeks. Under §0.16's weekly
resampling every ranker faces the identical 300 squads within each gameweek, so the pairing holds
exactly, at the grain the difference is taken at. §10.4 makes it structural rather than
disciplinary: the estimator consumes an already-differenced panel and never sees two rankers, so an
unpaired draw is unrepresentable regardless of how the squads were built.

**Two intervals, U1 and U2, reported as two.** `METRIC.md` §6.2 records that they answer different
questions: U1 (resample squads, gameweek set fixed) measures sensitivity to which squads were
drawn, U2 (resample gameweeks, squads fixed) measures sensitivity to which weeks the season
contained. Under the synthetic population selected at §0.16 both are live sources of variability —
the squads are drawn by this design and the season is one realisation — so collapsing them to one
number would suppress whichever question the chosen scheme did not answer. §7.2's T3 stores two
column pairs.

**U3 is rejected, and the reason is now one of its two halves rather than both.** `METRIC.md` §6.2
states the objection in two parts: the same squad recurs across every gameweek, **and** the same
gameweek recurs across every squad, so treating squad-week rows as independent draws inflates the
effective sample by roughly two orders of magnitude and manufactures precision the data does not
contain. Under §0.16's weekly resampling the **first half no longer holds** — a squad exists in
exactly one gameweek and recurs nowhere. The **second half stands unchanged**: squad-weeks sharing a
gameweek share that week's realised fixtures and player performances, so a flat row bootstrap over
the whole panel would still treat the gameweek dimension as though it supplied 300 independent draws
per week, which is the same manufactured precision under a different name. U1 is therefore computed
as a **bootstrap stratified by gameweek** — the gameweek margin held fixed, squads resampled only
within a week. §10.3 derives this and §10.5 states the estimator.

**U4's cluster structure no longer applies, because the panel no longer has clusters.**
`METRIC.md` §6.2 describes the cluster bootstrap as the structurally correct treatment of a panel
where one unit contributes many dependent rows — resample clusters, take all of a drawn cluster's
rows. That was the right structure under a held squad, which contributed one row per gameweek. Under
weekly resampling **each squad contributes exactly one row**, so "take all of a drawn cluster's rows"
and "draw one row" are the same operation, and U4 collapses into the within-stratum draw above. This
is not a relaxation of U4's requirement; it is that requirement evaluated on a panel whose dependence
structure the construction has removed. `INVENTORY.md` §2.9's finding that there is **no generic
cluster-bootstrap-of-a-mean** is unchanged in its consequence — U1 is still a build, since no
gameweek-stratified bootstrap of a mean exists in the repository either. §10 designs it.

**U2 is a reuse.** `INVENTORY.md` §2.9 records a moving-block bootstrap of the mean of a
per-gameweek series, motivated by consecutive-gameweek autocorrelation, tested and deterministic —
in two implementations. §8.2 chooses between them.

**The resample count: n = 10,000.** `METRIC.md` §6.2 records that a count acquired by import path is
acquired by accident, since `INVENTORY.md` §2.9 measures two same-named implementations at
`n = 1000` and `n = 3000`. It also states the argument that fixes the level: where a verdict turns
on whether an interval excludes zero — which §0.15's S2 does — a 2.5% endpoint at `n = 1000` rests
on the 25 most extreme draws and Monte Carlo jitter can flip it for a difference not itself near
zero, while at 10,000 it rests on 250, with percentile convergence ~1/√n putting simulation noise
below plausible effect sizes. The cost is negligible: the statistic resampled is a mean over dozens
of gameweeks or hundreds of squads, not a model fit.

**The count governs both intervals and every implementation.** `METRIC.md` §6.2 records that the
published-output constraint on the existing implementations does not require a *new* measurement to
inherit their count. So `n = 10,000` is passed explicitly at every call site in the slice, including
the one built at §10, and is frozen in the pre-registration (§7.4).

**`block = 4` for the gameweek interval, and no block for the squad interval.** `INVENTORY.md` §2.9
records that both existing implementations use `block = 4`, the `model/eval` one taking it from the
named `BLOCK_GWS`. Passing it explicitly records the value rather than fixing anything new. The
squad interval takes no block: blocking exists to preserve autocorrelation between consecutive
gameweeks, and squads have no order (§10.1).

**The estimand, which `METRIC.md` does not disambiguate.** "Mean regret" admits two readings that
differ here — the grand mean over surviving squad-weeks, and the unweighted mean of per-**gameweek**
means. (Under §0.16 a per-*squad* mean is not the live alternative: a squad has exactly one week, so
that reading collapses into the grand mean. §10.2 works this through.) They coincide only under
balance, and the zero-gap exclusions of §0.8 remove squad-weeks unevenly across weeks. **The grand mean over surviving squad-weeks is selected**, because §0.15's materiality
threshold is a fraction of the floor's own mean regret reported alongside an absolute magnitude in
points — a per-squad-week cost, which is what the grand mean estimates — and because `DECISION.md`
§1 frames regret the same way, as the cost of a weekly decision. §10.2 works the difference through.

### 0.15 The success bar — all three conditions, with S3 relative to the floor at 10% (#15)

**Selected: S1 and S2 and S3, all three. Any two is a fail.**

**Why all three.** `METRIC.md` §6.3 gives each condition's blind spot and they are not overlapping.
S1 alone (direction) says nothing about whether an improvement is distinguishable from noise. S2
alone (significance) is the one that bites hardest here: `METRIC.md` §6.3 records that under a
paired design over hundreds of squads an interval can exclude zero for a difference of a few
hundredths of a point per gameweek — real and worth nothing — and §0.16 selects exactly such a
design. S3 alone (materiality) can be met by noise of the right size. A bar dropping any of the
three admits a result the other two would have caught.

**S3's form: relative to the floor, at 10%.** `METRIC.md` §6.3 states the argument for the relative
form — it can be fixed honestly before the first run because it scales with whatever the floor turns
out to be, and the headroom in this decision is **unmeasured**, since nobody has computed how much
regret the floor carries. A fixed points threshold is more directly interpretable but, fixed before
the headroom is known, risks pre-registering a target no ranker can reach so that a real improvement
reads as a failure. On the level, `METRIC.md` §6.3 frames the trade directly: 10% guards against an
unreachable target set on unmeasured headroom, while a stricter bar guards against crediting an
improvement too small to justify its complexity and reintroduces the first risk. **10% is selected**
because the first risk is the one actually present — the headroom is unmeasured and this is the
first run — and because a bar that fails a genuine improvement teaches nothing, whereas a bar that
passes a marginal one is caught by the absolute figure reported beside it.

**The absolute magnitude is reported alongside the relative, always.** `METRIC.md` §6.3 records the
reporting property independent of the bar: a given percentage reduction on a large floor regret and
on a small one are different results, and only the absolute points figure says which is on the
table. §7.2's T3 stores both reductions for that reason.

**Which interval S2 turns on: both.** `METRIC.md` §6.3 states S2 in the singular — "the paired
resampled interval on the difference excludes zero" — while §6.2 supplies two intervals answering
different questions. **S2 is satisfied only if both the squad-resampled and the gameweek-resampled
intervals exclude zero.** The reason is that the two failure modes are not substitutes: an effect
that survives one season's weeks but not the squad draw is an artefact of the construction this
design chose (§0.16), and one that survives the squad draw but not the weeks is an artefact of the
season. A claim that a ranker beats the floor should survive both. **The cost is stated rather than
hidden:** requiring both is the stricter reading and will lose some real effects, which is the
direction of error this slice should prefer on its first run. `METRIC.md` §6.3's own S2 note — that
significance is cheap under a paired design over hundreds of squads — is the reason strictness is
affordable here.

**Pre-registration.** `METRIC.md` §6.3 records that pre-registration is a property of *when* a bar
is fixed, not of which, and that the `evidence.yaml` + freeze-test pattern `INVENTORY.md` §2.9
identifies is the only mechanism in the repository making such a fixing enforceable rather than
aspirational. §7.4 adopts it: the thresholds, counts, windows, seed and ordering selected in this
section are written to `PRE_REGISTRATION.yaml` and pinned by a test before the first run.

### 0.16 The population — N1, uniform synthetic squads, resampled weekly, 300 per gameweek (#16)

**Selected: N1**, synthetic squads drawn uniformly over the feasible set.

**Why N1.** `METRIC.md` §7 names the load-bearing property: independence from every ranker under
test. Its counter-example is exact — a squad built by sorting on PPG would hand a PPG ranker a squad
selected on its own criterion and measure the circularity rather than the method. §2.2 sharpens what
that independence has to mean here and why uniformity, not merely ranker-blindness, is what secures
it.

**Why not N2.** `METRIC.md` §7 records that plausibility weighting answers the narrower and more
relevant question — regret over squads a human would build — at the cost of the weighting's
assumptions, and that **whether it is worth them is measurable from an N1 run**: if method rankings
are insensitive to squad composition, the weighting buys nothing. So N1 is not merely the simpler
option; it is the one that produces the evidence for deciding whether N2 is needed. N2 is deferred
until that measurement exists, and §2 adds nothing toward it.

**N3 is unavailable.** `METRIC.md` §7 records that no squad, picks or bench-order history exists in
the data (`DECISION.md` §3) and that nothing samples a constrained squad either (`INVENTORY.md`
§2.8). It is not rejected on merit; it has no inputs.

**The choices inside the population, from `METRIC.md` §7.1.**

- **Feasibility conditions: budget cap, 2/5/5/3, ≤3 per club, registration.** All four.
  `INVENTORY.md` §2.2 records the quota and the XI bounds in `dal/staging/contracts/element_types.yaml`
  — `squad_select` 2/5/5/3 — and that no code validates any of them; §2.2 also records 20 teams and
  a non-null `purchase_price` on every mart row, with the cheapest legal 2/5/5/3 at GW1 costing 64.0
  against the 100.0 cap.
- **Feasibility assessed once per squad, at that squad's own gameweek.** `METRIC.md` §7.1 records
  that once-versus-per-gameweek genuinely differ, citing `INVENTORY.md` §2.2 for 27 of 841 players
  changing club and §2.7 for 600 of 841 changing price across the season. `METRIC.md` §7.1's own
  condition for assessing once is that it matches how the game works — a manager buying at the prices
  of the day, with the ≤3-per-club limit binding when a squad *changes* — **provided the squad
  genuinely never changes**. Weekly resampling satisfies that proviso more exactly than build-once
  did, not less: a squad exists for exactly one gameweek, is priced and club-checked at that
  gameweek, and never changes at all. The defect build-once had to accept and defend — a squad legal
  at GW2 holding four players from one club by GW38 — cannot arise, because no squad outlives the
  week in which it was assessed.
- **Resample per gameweek, rather than build once and hold.** Each gameweek in scope draws its own
  300 squads, from the universe registered as of that gameweek, at that gameweek's prices and clubs.
  `METRIC.md` §7.1's objection — that resampling per gameweek breaks the pairing — is **refuted**;
  the superseded record below states why and §10.4 carries the argument. What weekly resampling buys
  is what `METRIC.md` §7.1 itself names as its benefit: it admits later entrants. Every player
  registered by gameweek *g* can appear in a gameweek-*g* squad, so the entrants build-once excluded
  are in scope from the week they arrive. The cost is real and is carried: the sampler runs once per
  gameweek rather than once, and §2.6's acceptance measurement becomes a per-week measurement with a
  per-week trigger.
- **The build gameweeks: every gameweek in scope, GW2–GW38.** There is no longer a single build week.
  GW2 remains the earliest, for the reason it was chosen before — it is the earliest gameweek in
  scope (§0.7) and the earliest at which the registration predicate is evaluable at all — and
  `METRIC.md` Appendix A.2's measurement of the universe there, 705 of 841 players (82 GK, 233 DEF,
  315 MID, 75 FWD, across all 20 clubs), now characterises the **smallest** of the 37 universes
  rather than the only one. Each later gameweek's universe is a superset of it, and all 38 are now
  measured at `INVENTORY.md` §2.5 — monotone nondecreasing to 841 by GW38, all 20 clubs represented
  throughout. §2.1 states the series where the target is defined.
- **Registration as a feasibility condition, implemented as a restriction of the universe.**
  `METRIC.md` §7.1 records that registration is the only one of the four that removes a player from
  the study **outright** rather than constraining which combinations may be drawn, and gives the
  reason it must not be a rejection criterion: `INVENTORY.md` §2.5 records pre-registration rows
  existing only because the DAL spine is a cartesian product, and §2.7 records that they carry a
  **forward-filled price** — the player's eventual debut price — so admitting one prices a phantom
  against the cap using a value from later in the season. §2.1 builds the universe first for exactly
  this reason and §2.8 asserts it.
- **The squad count: 300 per gameweek.** `METRIC.md` §7.1 records that precision is bound by
  whichever dimension is scarcer, that the gameweek dimension is window-dependent and is the scarce
  one at any count in the low hundreds, and that added squads therefore buy little while replay cost
  grows linearly. 300 sits at the top of that range. **Under weekly resampling 300 is read per
  gameweek**, which is what holds the per-week comparison at the precision the count was chosen for.
  The alternative reading — 300 squads spread across 37 weeks, roughly eight a week — would thin the
  within-week dimension to the point where §10.3's stratified interval has almost nothing to
  resample, for no saving that matters. The consequence is that a run draws 11,100 squads rather than
  300. The **replay cost is unchanged**, because the replay is per squad-week and the squad-week
  count is identical (§7.2); what grows 37-fold is the sampler's proposal cost (§2.6) and the squad
  artefact itself (§7.2). Frozen in the pre-registration.

**Superseded: build once and hold, and the two reasons that matter.** Build-once was selected in an
earlier pass and is recorded here as superseded rather than deleted, so it is not re-proposed.

*The reason it was selected does not hold.* `METRIC.md` §7.1 states that resampling per gameweek
breaks the pairing of §6.1, and that objection is what build-once rested on — §0.14 depends on the
pairing, so an option said to break it was not really in contention. The objection is **refuted** by
§10.4. Pairing requires every ranker to face the same squads in the same gameweeks, and under weekly
resampling every ranker faces the identical 300 squads within each gameweek, which is the grain the
difference `d(s, gw)` is taken at. The estimator consumes an already-differenced panel and never sees
two rankers, so there is no second draw that could break the pairing. Weekly resampling satisfies
`METRIC.md` §6.1's pairing requirement **exactly**, not approximately.

*The genuine objection was never written down.* There **was** a real cost to weekly resampling, and
it is the one this pass had to work through: build-once gave the panel a cluster structure — one
squad contributing 37 dependent rows — which §0.14's U4 and §10.3's estimator were built around, and
weekly resampling destroys it. That is a change to the estimator, not a defect, and §10.3 derives
what replaces it. But it was never the stated reason. Build-once was therefore selected on a reason
that does not hold, while the reason that did hold went unrecorded; both facts are noted here because
the second is the one a later reader would otherwise rediscover as an objection to this pass.

*What build-once cost, sized — and corrected against the measurement.* It freezes the universe at
GW2, so a player first appearing at GW10 can never enter any squad in any week — not a reduced
chance, none. `METRIC.md` Appendix A.2 sizes the exclusion at **136 of 841 players (16.2%)**, all of
whom appear later in the season. That much is measured and stands.

**An earlier version of this paragraph went further and was wrong.** It asserted that the excluded
set skews toward **currently-active** players — reasoning that a player enters the data because he
has arrived and is being picked — and concluded that the frozen pool is tilted along
minutes-certainty, §2.2's forbidden axis, so that build-once would have had the harness measuring its
own frozen universe and reporting it as a method result. That claim was never measured. It has since
been measured, and **the direction is the reverse of what was asserted.** `INVENTORY.md` §2.5 records
the comparison: the 136 late entrants have a **median of 0 season minutes** against 565 for the GW2
universe, **52.2%** of them never played a minute against 33.0%, and **31.6%** ever recorded 60
minutes against 59.1% — with the rates computed over each player's own available weeks, so a shorter
career does not produce the gap. The late entrants are the **less**-played group, decisively and on
every measure taken. The sentence is withdrawn.

**What survives, stated at the strength the measurement supports and no higher.** A tilt along the
axis is still present, because the two groups differ on exactly the quantity §2.2 names; it simply
runs the other way. Removing a disproportionately non-playing group leaves the GW2 pool
**over-representing players who play**, relative to the full-season universe. So build-once still
draws its squads from a pool that is unrepresentative along minutes-certainty, and §2.2's argument
that this axis is the one to worry about is unaffected.

**But the cost is materially smaller than the withdrawn version claimed, and that is the honest
reading.** §2.2 separates two categories: a bias independent of the rankers, which limits
generalisation, and a bias correlated with the axis the rankers differ on, which corrupts the
comparison. The withdrawn claim placed build-once's exclusion firmly in the second. The measurement
moves it much closer to the first: over half the excluded players never played at all, and a player
who never plays is rarely decisive in an XI decision — he would be benched, or unrankable, in almost
any squad containing him. Excluding a group that mostly could not have changed a selection is closer
to a coverage limitation than to a corrupted comparison. **Whether the residual tilt is material to a
ranker comparison is unmeasured** — nothing measures how the pool's composition shifts the value of
minutes-certainty within a drawn squad, and this document does not assert that it does.

**What this does and does not do to the selection.** The minutes-certainty argument was **one of
several** reasons recorded for weekly resampling, and it is the weakest of them now rather than the
strongest. It does not by itself revisit the decision, and this pass does not reopen it. The
load-bearing justification is unchanged and untouched: `METRIC.md` §7.1's pairing objection — the
reason build-once was selected in the first place — is refuted at §10.4, and `METRIC.md` §7.1 now
records that both constructions satisfy §6.1's paired design. Weekly resampling also still admits
later entrants at all, still assesses feasibility at the gameweek a squad exists in, and still
carries the cluster-structure consequence §10.3 derives. What changes here is one supporting
argument's strength, not the selection it supported.

Weekly resampling removes the exclusion regardless of its direction: the universe at gameweek *g* is
every player registered by *g*, so no entrant is structurally absent from any week after his arrival.
`INVENTORY.md` §2.5 measures those universes at all 38 gameweeks. §2.2 records the consequence.

**A season-specific validity condition, inherited — and now in conflict.** `METRIC.md` §7.2 states
that the composed registration predicate — in the universe iff a non-null `minutes` row exists at or
before the build gameweek — is unambiguous **only because** the early gameweeks of this season
contain no genuine no-fixture blanks, with the measurement at `METRIC.md` Appendix A.1 placing them
at GW31 and GW34 only. That condition was stated for a **single** build week inside the early
gameweeks. Under weekly resampling **every gameweek is a build week, including GW31 and GW34**, so
the condition as written is violated by construction. Whether the predicate is actually ambiguous at
those weeks is a different question — the prefix test at GW31 spans thirty prior gameweeks, so a
player registered earlier has a non-null row long before the blank — but resolving it means restating
`METRIC.md` §7.2's condition for a set of build weeks, and this document may not write to
`METRIC.md`. **This is recorded as a conflict requiring a `METRIC.md` pass** (Provenance) and is not
resolved here. The standing requirement is unchanged in kind: it is a property of the 2025-26
calendar and must be re-checked against any other season.

### 0.17 What §0 does not select

- **The bench-order scoring rule** — §0.10; there is no candidate set.
- **P4's form** — §0.1; `METRIC.md` §1 records that nothing in this folder defines it. Its inputs
  are stored (§7.6) so it needs no re-run once defined.
- **Whether F3 may be built at all** — §0.12; a governance question outside this folder (§9.1).
- **Whether N2 is worth its assumptions** — §0.16; measurable only from an N1 run.
- **Anything about implementation.** §1–§10 own that, and they consume §0's selections rather than
  re-opening them.

---

## 1. Scope and relationship to the other documents

*Written last, so it describes what this document contains rather than what it was expected to.
It points; it does not summarise.*

### 1.1 What this document decides, and what it does not

**`DESIGN.md` answers one question: given the evidence, what system should we build?** It makes the
metric selections `METRIC.md` §8 leaves open (§0) and fixes how the harness is built (§1–§10).

**It gathers no first-hand evidence.** Every repository fact used here is cited to `INVENTORY.md`.
Where a fact is needed that `INVENTORY.md` does not carry, that is a gap requiring an
`INVENTORY.md` pass, and it is flagged rather than asserted locally — §11 lists the open instances.

**On precedence:** where this document and an upstream one appear to conflict, the upstream one
governs and the conflict is a defect here. Such conflicts are recorded rather than silently
reconciled.

### 1.2 Constraints inherited, named by source

Not restated here — each is used in place, in the section that depends on it.

| Constraint | Source | Used at |
|---|---|---|
| The 8 legal formations, and that the best-XI search is 8 prefix-sum combinations | `INVENTORY.md` §2.4, derived from `squad_min_play`/`squad_max_play` in the staging contract (`INVENTORY.md` §2.2) | §3.5, §5.1 |
| The auto-substitution asymmetry — chosen side scored after subs, counterfactual with none | Selected at §0.2 from `METRIC.md` §2.1 | §4.3, §4.9 |
| Regret ≥ 0, preserved by the formation-legality condition on every substitution | §0.1 and §0.6 | §4.3, §4.4 |
| Synthetic-squad conditionality — no real squad exists in the data, so every result is conditional on the construction | `DECISION.md` §3; `METRIC.md` §7 | §2 throughout, especially §2.2 |
| The success bar — direction, both paired intervals excluding zero, ≥10% materiality | Selected at §0.15 from `METRIC.md` §6.3 | §6.3, §7.2, §8.2, §10 |

### 1.3 One constraint that is this document's own, and is easy to mis-trace

**`harness.py` takes a ranking function as an argument and imports only from `dal/`.** This was
carried into Phase 2 as "already fixed by `DECISION.md`". **It is not in `DECISION.md`**, which at
§6 says the opposite about its own authority — "This document fixes neither the metric nor the
design, and nothing in it should be read as doing so" — and the phrase "ranking function" appears
nowhere in it.

The constraint was adopted because it is correct: it is what makes §3.6's transitive closure hold.
But it is recorded as **§3.2, a Phase 2 decision made there for the first time**. A reader tracing
it to `DECISION.md` will not find it, and §1 says so here because that is the trace a reader is most
likely to attempt.

**A correction to how its arity is usually stated.** §4.9 establishes that primary regret depends on
the bench ordering used, so §5.1 and §5.4 make `bench_order` a required argument alongside
`rank_fn` — **two arguments, not one**. Both are callables: §5.4 fixes `bench_order` as a non-empty
ordered sequence of named ordering **policies**, not a precomputed value, because the bench is the
complement of the XI and a value form would force the harness to expose XI selection as a second
entry point.

### 1.4 Section map

| Section | What it fixes |
|---|---|
| **§0 Metric selections** | The sixteen selections `METRIC.md` §8 leaves open, with the two that cannot be made stated as gaps |
| §2 Squad sampler | Uniform over the feasible set by whole-draw rejection; a measured acceptance-rate trigger with a numbered ladder; MCMC held as the fallback |
| §3 Import-graph home | `decisions/starting_xi/` becomes a package under a **two-tier** contract — a model-free core and a single ranker edge |
| §4 Bench-order scoring rule | Ordering regret; the replay algorithm and its multi-substitution semantics; the counts and which denominates what |
| §5 Module shapes and interfaces | The module table with per-module forbidden imports; the `__init__.py` rule and the subprocess isolation test that enforces it |
| §6 Ranker interface | One **panel-producing** signature that accommodates a fitted GLM; declared windows and their intersection; the `min_periods` decision |
| §7 Results shape and location | Five tables across four grains, so analysis never re-runs the harness; the pre-registration freeze, separate from the results |
| §8 Reuse and call-site specifics | What is reused and on what terms; the gameweek interval's call site, and why `research/kernels` is unreachable |
| §9 Open items | What is genuinely unresolved and what each blocks |
| §10 The squad-level interval | The build §0.14's U1 requires, which `INVENTORY.md` §2.9 records has no generic implementation |
| §11 Facts this document needs and `INVENTORY.md` does not carry | The gaps an `INVENTORY.md` pass owes, listed rather than asserted here |

### 1.5 What is open at the close of Phase 2

The slice's phase sequence is defined in `docs/implementation-plan.md` — "the slice's **build** and
**baseline** phases", Phase 3 and Phase 4 respectively — not in any of the four documents in this
folder.

**One thing changed since the previous pass and is recorded here rather than only where it landed.**
§0.16 now selects **weekly resampling** in place of build-once-and-hold. It changes §0.14's selection
#14, §2 throughout, §7.2–§7.4, and §10.3/§10.5, and it opens two conflicts against `METRIC.md`
(Provenance). It does not change what Phase 3 needs.

**Nothing blocks Phase 3.** The one item that did — where the harness can legally live — is decided
in §3, and the metric selections the replay needed are made in §0. What Phase 3 needs beyond this
document is two file edits, `pyproject.toml` and `.importlinter` (§3.9), and the new
`domain/fpl_squad.py` (§3.5).

| Open item | Where | What it blocks |
|---|---|---|
| The `points_roll3` governance verdict | §9.1 | **Phase 4.** F3 is one of three floor rankers and cannot be built until it is answered |
| No candidate bench-order scoring rule has been characterised | §0.10, §9.2 | **Nothing structural** — §4.4 supplies a working rule — but the rule is unsurveyed, so it cannot be reported as selected |
| `METRIC.md` §1's P4, "mean signed directional error", is named but undefined | §7.9 | **The results document.** Its inputs are stored, so no re-run is needed once it is defined |
| Uncertainty on the bench-ordering sample | §4.11 | **The bench-order claim**, not the harness |
| Facts §11 needs that `INVENTORY.md` does not carry | §11 | **Nothing structural**; each is a claim this document declines to make first-hand |
| Whether the residual minutes-certainty tilt in a frozen GW2 pool is material to a ranker comparison | §0.16, §2.2 | **Nothing** — build-once is superseded, so the question is now about a construction this design does not use. Recorded because §2.2's argument would need it if build-once were ever revisited. *(The unsourced claim previously listed here is withdrawn; the two `METRIC.md` conflicts are closed. See Provenance.)* |

**Measurements owed on the first run, which are outputs rather than blockers:** the sampler's
acceptance rate against §2.6's trigger; the vacancy-order invariance test (§4.3.1); the per-ranker
count of squad-weeks the no-fixture rule changed (§0.4); and the materiality of `p_play`'s DGW
exclusion, which `INVENTORY.md` §3.4 records as unmeasurable without a squad set.

---

## 2. Squad sampler

### 2.1 The target, stated before any method is argued

§0.16 fixes the target: **uniform over the feasible set of the gameweek**, with feasibility assessed
in full at **each gameweek in scope** against four simultaneous conditions — the budget cap,
2 GK / 5 DEF / 5 MID / 3 FWD, at most 3 players per club, and registration.

**What "uniform" is over, written out.** The target is defined **per gameweek**, and the whole
construction is indexed by *g*. Let **U_g** be the squad universe at gameweek *g* — every player with
a non-null `minutes` row at or before *g*. Let **Q_g** be the set of 15-player subsets of U_g
satisfying the position quota exactly. Let **F_g ⊆ Q_g** be those members of Q_g additionally
satisfying the budget cap and the ≤3-per-club limit **at gameweek *g*'s prices and clubs**.

**The target distribution is the uniform distribution on F_g: at gameweek *g*, every feasible 15 has
probability 1/|F_g|.** It is not uniform on U_g, not uniform per position, and not uniform on Q_g.
Those are three different distributions and only the last is a legitimate stepping stone to the
target (§2.4). There is no single target distribution across the season and none is wanted: each
gameweek's 300 squads are the population for that gameweek's comparison, and §10.3 resamples them
within the week for exactly that reason.

**Every U_g is measured.** `INVENTORY.md` §2.5 records |U_g| and its position and club composition at
all 38 gameweeks. U_2 is 705 of 841 — 82 GK, 233 DEF, 315 MID and 75 FWD across all 20 clubs,
reproducing `METRIC.md` Appendix A.2 — and it is the smallest universe in scope. The series is
monotone nondecreasing, reaching 841 by GW38, with all 20 clubs represented at every gameweek and the
largest later intakes at GW4 (28), GW17 (10) and GW20 (10). Nothing in §2 depends on the particular
numbers — the method is defined on U_g whatever it contains, and §2.3's expectations are a priori
arguments rather than measurements — but §2.6's acceptance ladder is now read against a measured
universe at every week rather than against one measured week and 36 unmeasured ones, which is what
makes a low rate at some later gameweek auditable.

**Registration is a restriction of the universe, not a rejection criterion.** It is applied by
constructing U_g first, so every member of Q_g is registration-legal by construction and no draw can
ever contain a player not yet registered **at that gameweek**. Under weekly resampling this is
enforced 37 times rather than once, at 37 different cut-offs, which is what makes later entrants
available without ever making a phantom available. This matters more than it looks: `INVENTORY.md` §2.7
records that prefix rows carry a **non-null, forward-filled price** — a not-yet-registered player's
GW1 price is his eventual debut price — so a prefix leak would not crash on a missing value, it
would silently price a phantom player against the cap using future information. Building U up front
is how §2 forecloses it, and §2.8 makes it a test rather than a convention.

**Scale.** |Q_2| is on the order of **10^28** — C(82,2)·C(233,5)·C(315,5)·C(75,3), an arithmetic
estimate from the GW2 position counts above, not a verified count. |F_2| is smaller and unknown, and
every later |Q_g| is larger, U_g being a superset. Two consequences follow and both are used later:
enumerating F_g is impossible at any gameweek, so no method may depend on having it; and the 300
squads §0.16 requires **per gameweek** — 11,100 across the season — remain a vanishing fraction of
even the smallest F_g, so whether squads are drawn with or without replacement is immaterial both
within a week and across weeks. The probability of drawing the same 15 twice is nil, and the
independence of one gameweek's draw from another's is a property of the construction rather than
something the scale has to rescue.

### 2.2 What a departure from uniformity would, and would not, invalidate

`METRIC.md` §7 already states that every result is conditional on the construction. §2 owes a
sharper statement than that, because "conditional on the construction" is compatible with both a
harmless departure and a fatal one, and they are not the same risk.

**What non-uniformity would not invalidate.** A bias that is *independent of every ranker under
test* changes **which population the mean regret is averaged over**. It makes the headline number
answer a slightly different question — regret over squads-of-this-shape rather than regret over
feasible squads — and it therefore limits **generalisation**. It does not corrupt the paired
comparison between two rankers, because both rankers face the identical squads and §0.14's paired
design differences out the squad-level variation. Under such a bias the slice's central claim —
ranker A beats the floor by X% — survives, with a narrower stated scope.

**What non-uniformity would invalidate.** A bias **correlated with the axis the rankers differ on**
is a different matter, and it is the realistic failure here. The plausible construction biases all
run along **price**: repair and constructive schemes shed expensive players to satisfy the cap, so
they over-sample cheap squads. Price correlates with quality, which correlates with both baseline
scoring rate and minutes-certainty — the two quantities `DECISION.md` §1 names as what the decision
selects on. A squad skewed toward cheap rotation players makes minutes-certainty systematically more
valuable than it is in a representative squad, which **differentially advantages F1 over F2 and
F3**. That is not a scope limitation; it is the harness measuring its own construction and reporting
it as a method result.

**The universe is the other place this axis can be tilted, and §0.16 closes it — though by less than
an earlier version of this paragraph claimed.** The argument above is about the *sampler*; the same
failure is available one level up, in the set the sampler draws from. Freezing the universe at GW2 —
the build-once construction §0.16 supersedes — excluded 136 of 841 players (16.2%, `METRIC.md`
Appendix A.2). The retained pool is therefore unrepresentative along **minutes-certainty**, this
section's forbidden axis, reached without any sampler bias at all.

**The direction is the opposite of what was previously written here, and the correction matters
because it changes which of this section's two categories the bias falls into.** `INVENTORY.md` §2.5
measures the excluded 136 as the **less**-played group — median 0 season minutes against 565, 52.2%
never playing against 33.0% — so freezing at GW2 removes disproportionately non-playing players and
leaves the pool over-representing those who play, rather than under-representing them. Since more
than half the excluded players never played at all, most of them could not have changed an XI
selection in any squad that held them, which places the exclusion nearer this section's
**generalisation-limiting** category than its comparison-corrupting one. The residual tilt is real
and runs along the named axis; its materiality to a ranker comparison is **unmeasured**, and §0.16
records that rather than assuming either way. Weekly resampling removes the exclusion at the source
regardless: U_g is every player registered by *g*, so no entrant is structurally absent from any week
after his arrival.

**So uniformity is load-bearing for a specific reason, and it is worth being precise about which.**
`METRIC.md` §7 names independence-from-the-ranker as N1's load-bearing property, and that is right —
but independence-from-the-ranker and uniformity-over-F are two different properties, and a scheme
can satisfy the first while violating the second. A price-biased sampler never consults a ranker and
is fully independent of one in the sense `METRIC.md` §7 means; it still tilts the comparison,
because the bias runs along an axis the rankers are separated by. **Uniformity is what closes that
residual gap**, and that is the argument for paying for it rather than settling for "random enough".

### 2.3 What actually binds — the a priori expectation, held loosely

Before comparing methods it is worth knowing which of the two rejectable constraints is tight,
because that determines whether a rejection scheme is cheap or hopeless. Two arguments, both
**a priori and neither a substitute for the measurement §2.6 requires**:

**The club limit is slack.** 15 players over 20 clubs (`INVENTORY.md` §2.2) is a mean of 0.75 per
club. A violation needs 4 or more from one club. Under a rough Poisson(0.75) approximation the
per-club violation probability is ~0.7%, and across 20 clubs the probability that *some* club
exceeds 3 is on the order of 10–15%. That is a mild rejection rate, not a binding one.

**The budget cap is probably slack too, for a reason specific to how FPL prices are distributed.**
`INVENTORY.md` §2.2 records the cheapest legal 2/5/5/3 at 64.0 against the 100.0 cap — the cap sits
56% above the floor, which is a lot of headroom. More to the point, `INVENTORY.md` §2.7 records the
price range as 3.7–15.1 across the season, and the distribution is strongly right-skewed: most of
the 705 are cheap squad players, so a *uniformly drawn* 15 is mostly cheap players and lands well
under the cap. The squads that violate the budget are the ones concentrating several premium
players, and those are rare under uniform draws precisely because premiums are rare in U.

**Neither argument is evidence.** Both are stated so that a measured acceptance rate can be read
against an expectation — if the measurement lands far below this, the first hypothesis is a bug in
the feasibility predicate, not a surprising feasible set (§2.6). They are recorded as reasoning, not
as a result.

### 2.4 Candidate methods

Three families, with the cost and the foreclosure of each stated before any recommendation.

#### Method A — whole-draw rejection over per-position uniform proposals

Draw uniformly without replacement within each position — 2 of 82 GK, 5 of 233 DEF, 5 of 315 MID,
3 of 75 FWD — which yields a draw uniform over **Q**. Test the drawn 15 against budget and club.
**Accept, or discard the entire 15 and draw again independently.**

**Uniformity: exact, and provable in one line.** The proposal is uniform over a superset Q ⊇ F, and
acceptance is the indicator of membership in F. Conditioning a uniform distribution on a subset
gives the uniform distribution on that subset. Every member of F has proposal probability 1/|Q| and
acceptance probability 1, so every member of F has posterior probability 1/|F|. This is textbook
rejection sampling and it needs no mixing argument, no diagnostics, and no asymptotics.

**It rests on three conditions, all of which must hold or the argument collapses:**

1. The per-position draw is uniform **without replacement within a position**, and positions
   partition the 15 (they do — a player holds one position).
2. **Registration is handled by restricting U before drawing**, never by rejection, so Q contains no
   pre-registration player.
3. **Rejection discards the whole 15 and redraws independently.** Repairing the offending position,
   resampling only the expensive player, or conditioning the next draw on the last one all break it.

**Cost:** an unknown number of wasted proposals. **Forecloses:** nothing.

**Condition 3 is the whole of the hazard `INVENTORY.md` §2.8 records.** `INVENTORY.md` §2.8 states
that whether per-position draws with rejection are uniform **depends on what is rejected** —
discarding the whole 15 and redrawing independently is uniform over the feasible set; redrawing only
the offending position while holding the rest is not. The difference is one line of implementation
and it is easy to get wrong in exactly the direction that loses the property, which is why condition
3 is stated as a condition rather than assumed as an obvious reading.

#### Method B — constructive or constraint-repair

Build a squad greedily or by position with a running budget, and repair violations as they arise —
swap out an expensive player when the cap is threatened, swap out a fourth club-mate when the club
limit trips.

**Uniformity: lost, and lost in an uncharacterised way.** Repair is not a symmetric operation. The
players it removes are the expensive ones and the ones from over-represented clubs, so the
stationary distribution is tilted toward cheap squads and toward clubs with more players in U — and
the size of that tilt is not calculable without knowing F, which §2.1 established is unavailable.
This is the precise bias §2.2 identifies as fatal: it runs along price.

**Cost:** cheap to run, and it always terminates — which is exactly what makes it tempting.
**Forecloses:** the uniformity claim, and with it any clean reading of a comparison between F1 and
the two PPG rankers. **Rejected**, and rejected on §2.2's grounds rather than on implementation
difficulty.

#### Method C — MCMC over the feasible set by swaps

Start from a known feasible squad. Propose a swap — remove one player, add another of the same
position from U — and accept if the result is feasible. Run to convergence, thin, and take samples.

**Uniformity: attainable, but earned rather than free.** A symmetric proposal (choose the outgoing
player uniformly from the 15, the incoming uniformly from the same-position remainder of U) combined
with accept-iff-feasible is a Metropolis chain whose stationary distribution is uniform on F,
*provided* F is connected under single swaps and the chain is run long enough. **Neither condition is
self-evident**, and the second is not checkable in the way the first is:

- **Connectivity is an assumption, not a fact.** If some region of F is reachable only by changing
  two players at once — plausible near the budget cap, where a single swap up in price may be
  infeasible while a paired swap is fine — the chain never visits it and the samples are uniform over
  a *component* of F rather than over F.
- **Convergence has no exact test.** Standard diagnostics bound nothing; they only fail to detect a
  problem.

**This is precisely where uniformity gets asserted rather than argued**, and §2 flags it as such. A
swap chain that "looks well mixed" is a claim of the form Method A does not need to make.

**Cost:** mixing diagnostics, a burn-in and thinning decision, a starting-squad choice, and a
correctness argument that rests on an unproven connectivity assumption. **Forecloses:** the ability
to state uniformity as a fact rather than as a supported belief.

### 2.5 Recommendation — Method A, whole-draw rejection

**Method A is recommended**, and the reason is that it is the only one of the three whose uniformity
is a theorem rather than a diagnostic. Given §2.2 — that the realistic biases run along price, the
same axis that separates the rankers — the correctness property is worth more here than the runtime
property, and Method A's only weakness is runtime.

Two supporting facts make its weakness cheap, and §0.16's weekly resampling weakens the first of them
without overturning the conclusion. The sampling cost is still a **one-off**, incurred before any
replay runs rather than repeatedly during it — but it is now 37 one-offs rather than one, since each
gameweek builds its own 300 (§0.16). And the target count is **300 per gameweek**, 11,100 in total,
which is still in the thousands rather than the millions. A method that wastes 99.9% of its proposals
still finishes: at §2.6's worst tolerated rate the whole season's build is on the order of 10⁸
proposals, which is arithmetic on integers and not a model fit.

**The honest form of the change: the runtime weakness got 37 times worse and is still not the binding
consideration.** Weekly resampling makes Method A's one real cost larger by exactly the factor the
build weeks multiplied by. It does not touch the correctness property the recommendation rests on —
uniformity on F_g is the same theorem at every gameweek — and §2.2's argument for preferring
correctness to runtime is unchanged. What does change is that §2.6's ladder now has 37 opportunities
to fire rather than one, which is why that section's trigger and abort semantics are per-week.

**Method B is rejected outright** on §2.2's grounds. **Method C is held as the named fallback**
(§2.7), not as a co-recommendation — its correctness argument is strictly weaker and it should be
reached for only if Method A is measured to be unusable.

### 2.6 The acceptance rate is measured, and the trigger has numbers

The acceptance rate p_g = |F_g|/|Q_g| is **unknown at every gameweek**. §2.3's expectation that it is
high is an argument, not a measurement, and the recommendation does not rest on it.

**The rate is now per gameweek, and so is everything below.** p is a property of F_g against Q_g,
and §0.16 changes both every week: the universe grows as entrants arrive and `INVENTORY.md` §2.7
records 600 of 841 players changing price across the season, which moves the budget constraint
directly. There is no single acceptance rate for the run and none is reported. p̂_g is measured,
laddered and recorded **once per build gameweek**, 37 times.

**A pilot runs first at each gameweek, before that gameweek's frozen build.** 10^5 independent
proposals at that gameweek's seed stream (§2.9). Let k_g be the accepted count and p̂_g = k_g/10^5.
Each pilot is a recorded artefact, not a throwaway — its seed, k_g and p̂_g are reported with that
gameweek's squads. The cost of running 37 pilots rather than one is 3.7 × 10^6 proposals, which is
smaller than the single-week red-line requirement below and is not a consideration.

**The ladder, applied per gameweek, with the expected proposal count for that gameweek's 300 squads:**

| Measured p̂_g | Expected proposals for that week's 300 squads | Action |
|---|---|---|
| **p̂_g ≥ 10⁻²** | ≤ 3 × 10⁴ | Proceed. That week's pilot has very likely already produced its 300. |
| **10⁻⁴ ≤ p̂_g < 10⁻²** | ≤ 3 × 10⁶ | Proceed, and record the realised proposal count alongside that week's squads. |
| **p̂_g < 10⁻⁴** | > 3 × 10⁶ | **Stop the whole build. Audit the feasibility predicate before anything else.** |

**A red line in any one week stops the entire build, not just that week.** This follows from what the
red line is for. It is a falsification threshold for §2.3, and §2.3's arguments — slack club limit,
slack budget — are seasonal properties that do not become false in a single gameweek. A rate two
orders of magnitude below expectation at GW17 and healthy either side of it is a stronger indication
of a bug — a price column read at the wrong gameweek is exactly the kind of defect that fires in some
weeks and not others — than a uniformly low rate would be. Skipping the offending week and continuing
would also silently change the population: the comparison window would lose a gameweek for a reason
unrelated to §6.3's scoreability, which is the one thing §0.7's window handling must not have
happening behind it.

**Why the red line is at 10⁻⁴, and what it actually means.** Not cost: even at p̂ = 10⁻⁴ the expected
3 × 10⁶ proposals are a one-off run of trivial size, and uniformity holds mathematically no matter
how low p goes. The red line is a **falsification threshold for §2.3**. A rate that low would
contradict the slack-budget and slack-club arguments by orders of magnitude, and the most probable
explanation for that contradiction is **a bug in the feasibility predicate**, not a surprising
feasible set — a price column read at the wrong gameweek, prefix rows leaking into U
(`INVENTORY.md` §2.7's trap), or the club limit applied per position instead of per squad. So
p̂ < 10⁻⁴ triggers an audit of the predicate first. **The fallback fires only if the predicate is
confirmed correct and the rate still stands.**

**A hard cap, so the failure is loud — and it is per gameweek, not per run.** Each gameweek's build
aborts at **10⁸ cumulative proposals for that gameweek** rather than looping, and an abort in any
week aborts the run. At the red-line rate that cap is 25 times a single week's expected requirement,
so hitting it means something is wrong rather than slow. Making the cap per-week rather than a
10⁸ budget shared across 37 weeks is deliberate: a shared budget would let 36 healthy weeks absorb
one pathological one until the run died at some arbitrary later gameweek, which converts a loud
failure into a confusing one. The per-week cap names the week that failed.

**Determinism of the trigger.** Each pilot is a fixed seed stream and a fixed proposal count, so
every p̂_g is a reproducible number, not a running impression. "The rate seemed low" is not a trigger;
k_g < 10 in a seeded 10^5-proposal pilot at gameweek *g* is. That 37 triggers are now evaluated
rather than one raises the chance that at least one fires by chance; it is not treated as a
multiple-comparison problem, because the red line is set two orders of magnitude below the a priori
expectation of §2.3 and a 10^5-proposal pilot has negligible sampling error at that distance.

### 2.7 If the trigger fires — the fallback, and the burden it carries

The fallback is **Method C**, with a condition attached: it may not inherit Method A's uniformity
claim, and it may not assert its own.

**If it fires, it fires for every gameweek.** The trigger is per-week (§2.6) but the fallback is not,
and the reason is homogeneity of the population rather than convenience. If some weeks were built by
rejection and others by a chain, the squads at different gameweeks would be drawn from constructions
carrying materially different uniformity claims, and every cross-week quantity — the grand mean over
the window, §10.5's stratified interval, §6.3's window intersection — would be a mixture of two
populations with no way to attribute a difference between weeks to the method under test rather than
to the builder. So a confirmed trigger at any gameweek switches the whole run to Method C, and the
weaker claim below attaches to all 37 weeks.

**What would have to be established, not assumed:**

1. **A symmetric proposal and accept-iff-feasible**, written and reviewed as such — this is what
   makes uniform-on-F the stationary distribution, and it is the part most easily broken by an
   optimisation.
2. **Connectivity of F under single swaps** — either argued from the structure of the constraints, or
   the proposal widened to paired swaps, which changes the symmetry argument and so must be
   re-derived rather than patched.
3. **Empirical evidence on a reduced problem.** Construct a scaled-down universe — a few dozen
   players, tight cap — where F is small enough to **enumerate exactly**, run the chain, and test the
   realised sample frequencies against uniform with a goodness-of-fit test. This is the evidence that
   would show uniformity, and it is the only form of it available: on the real universe |F| is
   unknown and unenumerable (§2.1), so no direct test exists there.

**What would be reported if the fallback fires.** That the squads are uniform *by construction of a
chain whose stationary distribution is uniform*, that connectivity is assumed with the argument
given, and that the evidence is the reduced-problem test rather than a test on the real set. That is
a materially weaker claim than Method A's and every result carrying it should say so.

### 2.8 Testability, and the costs as well as the benefits

**The constraint tests are the floor, not the ceiling.** Across **all** generated squads, assert, for
each squad **against its own gameweek *g***: exactly 2/5/5/3 by position; ≤3 per club at *g*; total
price at *g* ≤ 100.0; and every player in U_g. The fourth is the one §2.1's registration argument
turns on, and it is cheapest to assert as set membership — every drawn `player_id` ∈ U_g — rather
than by re-deriving the prefix rule at test time.

**Three of the four now have a wrong version that would still pass.** Asserting the price, club and
membership conditions against GW2 rather than against the squad's own gameweek would pass on the GW2
squads and would be vacuously satisfiable elsewhere — GW2 membership is a *subset* of U_g, so a
GW2-keyed membership test would reject legitimate later entrants rather than catch phantoms, and a
GW2-keyed price test would pass squads over budget at their own week. The tests must be keyed on the
squad's gameweek, and the joins that key them are the part worth reviewing.

**One new test the old construction had no need for: a squad belongs to exactly one gameweek.**
Assert that each `squad_id` appears at exactly one `gw` in the squad table. This is not a tidiness
check. §10.3's estimator is valid precisely because a squad contributes one row, and a build bug that
reused ids across weeks would produce a panel that looks correct, resamples correctly by its own
lights, and silently reintroduces the dependence §0.14's U3 rejection is about.

**The determinism test.** Same seed, same universes, byte-identical squad table across all 37
gameweeks — and, because §2.9 derives per-week streams from one master seed, the additional property
that **building a subset of the gameweeks reproduces those gameweeks' squads exactly**. That second
property is what makes a partial re-run auditable and it is a consequence of the seed derivation
being independent of build order, so it is worth asserting rather than assuming. `INVENTORY.md` §2.8
records that determinism is already tested as a property elsewhere in the repository
(`tests/test_kernels_inferential_resampling.py`, `model/terms/p_play/test_p_play.py`, and the whole
of `tests/stabilization/test_wave3_determinism.py`) rather than assumed, and this follows that
convention.

**The uniformity test, and an honest statement of what it does not cover.** Uniformity is tested on
a **reduced universe** small enough to enumerate F exactly — draw many squads, compare realised
frequencies against uniform. **This verifies the algorithm, not the artefact.** Uniformity of each
gameweek's 300-squad set is inherited from §2.4's proof plus this test of the implementation; it is
not independently measurable, because |F_g| on any real universe is unknown. Weekly resampling does
not multiply this test by 37 — the algorithm is one algorithm and the reduced-universe test covers
it — but it does widen what is inherited from one artefact to 37, which is worth recording as the
scope of the inheritance rather than left implicit. Recording that gap is part of
the design, not an admission against it.

**State, and its cost — reported rather than only its benefit.** Method A holds **no** state between
calls. There is no cached feasibility index (U has 705 members; an index would be premature and would
be state), no module-level RNG, and no accumulated counters. The acceptance diagnostics are
**returned as data alongside the squads**, not held in the sampler — which is the whole reason they
are testable: a returned count can be asserted on, a counter inside a module can only be inspected.

Two costs are incurred anyway and are stated:

- **The RNG stream depends on the data.** Rejection consumes a data-dependent number of draws, so the
  same seed against a *different* mart yields a different squad set. The frozen artefact is therefore
  reproducible only against a **pinned mart**, and the pin has to be recorded with the squads. A
  non-rejection method would not have this property. This is a real cost of the recommendation and it
  is not offset by anything. Under weekly resampling the pin covers **every gameweek's** slice of the
  mart rather than GW2's alone, so a mart rebuild that touches any gameweek in scope invalidates the
  whole frozen set — a wider exposure than build-once had, and the honest statement of it.
- **The per-week seed derivation is what stops this compounding.** Were the 37 builds run off one
  sequential stream, a data change at GW7 would shift the RNG for every later gameweek, so a
  localised mart correction would perturb 31 weeks of squads for no reason. §2.9's per-week streams
  confine the perturbation to the weeks whose data actually changed. The reproducibility exposure
  above is real; this keeps it proportionate.
- **The pilots are 37 further seeded artefacts** that must be kept with the squads, or §2.6's
  per-week trigger becomes unauditable after the fact. This is a genuine growth in what the run
  record has to carry, and §2.9 states the shape it takes.

### 2.9 Interface

Stated at the level §2 owns — what goes in, what comes out, what state is held, how the seed enters.
Exact names and signatures are §5's to fix.

**Takes:**

- the mart across **every gameweek in scope**, supplying `player_id`, `position`, `purchase_price`,
  `team_id` and `minutes` per gameweek, and what is needed to build each U_g — read via `dal/`. This
  is the one interface change weekly resampling forces on the input side: the sampler reads a panel
  rather than a single-gameweek slice, and it is the sampler that slices it per week, because U_g's
  prefix definition needs the history and not just the row;
- **the gameweek list**, explicitly, rather than inferred from the mart's span — the scope is §0.7's
  and the sampler must not silently widen or narrow it by taking whatever the mart happens to hold;
- the squad quota (2/5/5/3) and the budget cap — from `domain/`, per §3.5's new `domain/fpl_squad.py`,
  so the quota traces to FPL's own `element_types` declaration (`INVENTORY.md` §2.2) rather than to a
  hardcode in the slice;
- the number of squads **per gameweek** (300 per §0.16);
- **a master seed, as a required argument with no default.**

**Returns:** the frozen squad set — 15 rows per squad, keyed by `gw`, `squad_id` and `player_id`,
with `squad_id` unique across the whole set and belonging to exactly one `gw` (§2.8) — plus a **run
record that is now per gameweek**: one row per build week carrying that week's derived seed, |U_g|,
the pilot's k_g and p̂_g, the proposals drawn, the accepted count, the realised acceptance rate, and
the three **diversity diagnostics** of that week's 300 squads — the count of distinct `player_id`s
appearing anywhere in them, stated against |U_g|; the selection frequency of the most-selected
player, as a count out of 300; and the spread of total squad cost at that gameweek, as min, median
and max. The mart pin is run-level, not per week, and is carried once. The run record is returned,
not logged and not stored (§2.8).

**Why the record is per week rather than aggregated.** An aggregate acceptance rate across 37 weeks
would average away exactly what §2.6's ladder is read on, and the diversity diagnostics are worse
under aggregation than useless: distinct players across all 11,100 squads would approach |U_38| for
arithmetic reasons alone and would read as healthy no matter how narrow each individual week was. The
three diagnostics answer a within-week question — does this week's 300 touch its own universe — and
they have to be reported at that grain to answer it. A reader wanting one number per season can take
one; the record does not compute it, because §2.9 has no criterion for what it would mean.

**One cross-week diagnostic is added, and it is the only genuinely new one.** Report, per gameweek,
the count of players in U_g **not** in U_2 — the entrants build-once excluded — and their selection
frequency across that week's 300 squads. This is the diagnostic that shows the change in §0.16 doing
what it was made for. Like the other three it **gates nothing**: no threshold is attached, §0 selects
no criterion over it, and a number invented here would be a criterion smuggled in as reporting. It is
read by a person alongside the squads, and if it looks wrong that is a finding to route through
`DECISION.md` and `METRIC.md`.

**Why the diversity diagnostics are in the record, given §2.1.** The first four fields describe the
*sampler*; they say nothing about the *set*. §2.1 disposes of exact duplicates — at |Q| ≈ 10^28 the
probability of drawing the same 15 twice is nil — but that is not the concern these three answer. The
live risk is near-copies: 300 squads that differ in two or three slots while sharing the same cheap
enablers would satisfy every constraint test in §2.8, report a healthy acceptance rate under §2.6,
and still carry roughly one squad's worth of information about how rankers behave across squad
composition. Nothing currently reported would show that. Distinct-players-against-|U| shows how much
of the universe the set actually touches; the most-selected player's frequency shows whether one
player is in nearly every squad; the cost spread shows whether the set sits in a narrow band of the
budget rather than across it. Each is a single pass over the returned squad table and needs nothing
the sampler does not already hold.

**They gate nothing, and that is deliberate.** No threshold is attached to any of the three. §0
selects no diversity criterion, there is no evidence base fixing what value would be too low, and a
number invented here would be a criterion smuggled in as reporting. Unlike §2.6's acceptance ladder —
which has a stated falsification argument behind its 10⁻⁴ red line — these are read by a person
alongside the squads. If a run makes one of them look wrong, that is a finding to take back through
`DECISION.md` and `METRIC.md`, not a condition this section may impose. Adding them changes no
method, no acceptance criterion, and no selection in §0. Whether they are persisted with the frozen
set or only returned is §7's, per §2.10.

**Holds:** no state. Pure function of its arguments.

**The seed, and the per-week streams it derives.** `np.random.default_rng(seed)`, matching the
convention `INVENTORY.md` §2.8 records as uniform across the repository — no `np.random.seed`, no
global state. Weekly resampling needs 37 streams from one master seed, and **how they are derived is
part of the contract, not an implementation detail**: each gameweek's stream is derived from the
master seed **and the gameweek number**, so that a week's squads are a function of that week alone.
Running one gameweek in isolation must reproduce the same squads as running all 37, and rebuilding
GW7 must not perturb GW8. A single sequential stream consumed across the weeks in order has neither
property, because rejection consumes a data-dependent number of draws (§2.8), so any change at an
early week shifts every later one. Requiring the master seed as an explicit argument with **no
default** deliberately avoids inheriting either of the two competing seed constants `INVENTORY.md`
§2.8 records (`BOOTSTRAP_SEED = 0` at
`research/kernels/inferential/resampling.py:20–22`, and a local `42` in the four family studies).
Which constant the *harness* passes is a global convention question, fixed at §8.4; the sampler's own
contract is simply that it never picks one for itself.

**Import closure — checked against §3, not assumed.** §3.5 permits `sampler.py` to import `dal/`,
`domain/`, and `formations.py`. Method A needs `dal/` (prices, clubs, registration), `domain/` (quota
and cap), `numpy` and `pandas`. **It needs nothing outside that closure**, and in particular no
solver — `INVENTORY.md` §2.2 records that no optimisation dependency is declared in `pyproject.toml`,
and Method A introduces no reason to declare one.

**One permission goes unexercised, and that is worth recording.** §3.5 permits `sampler.py` to import
`formations.py`; **Method A does not use it.** A 2/5/5/3 squad always admits at least one legal
formation — 5 DEF ≥ 3, 5 MID ≥ 2, 3 FWD ≥ 1 against the XI bounds `INVENTORY.md` §2.2 records — so
XI-legality is implied by the quota and needs no check at sample time. The permission is left in
place (it costs nothing), but nothing in §2 relies on it.

**No method was ruled out on import-contract grounds.** Methods B and C also close under
`dal/`+`domain/`; B was rejected on uniformity (§2.4) and C is held as the fallback on the strength of
its correctness argument (§2.7), not on where it may import from. Had a method required widening §3's
contract — a solver dependency, or reading a ranker to guide the draw — that would have been a reason
to reconsider the method, not the contract. The second of those is foreclosed twice over: by §3.5 and
by §0.16's independence requirement.

### 2.10 What §2 does not decide

- **The exact derivation function for the per-week streams** — §5; §2.9 fixes only that it must be a
  function of the master seed and the gameweek, and order-independent.
- **How squads are stored and where the frozen set lives** — §7.
- **The sampler's exact function and column names** — §5.
- **Which seed constant the harness passes** — §8.4; §2 only refuses to default it.
- **Plausibility-weighted sampling** — deferred at §0.16 until an N1 run shows whether method
  rankings are sensitive to squad composition. §2 builds the uniform sampler that measurement
  requires and adds nothing toward the weighted variant.

---

## 3. Import-graph home

### 3.1 What is decided here

`decisions/starting_xi/` becomes an **importable Python package with an explicit import contract**,
and that contract is **two-tier**: a model-free core that may never import `model/`, and a single
ranker edge module that must.

`INVENTORY.md` §2.11 records the starting point: the directory holds only markdown, no Python and no
`__init__.py`, and nothing in the tree imports from it. `DECISION.md` §6 named the package question a
**named input to the Phase 2 design document**, explicitly not settled there. It is settled here.

### 3.2 The constraint this section is built around

**`harness.py` takes a ranking function as an argument and imports only from `dal/`, never
`model/`.**

This is treated as fixed and is not revisited below. It is the constraint that makes the whole
contract work: a harness that receives its ranker rather than importing one is a harness whose import
set is independent of which rankers exist, now or later.

**Attribution, recorded rather than smoothed over.** This constraint was supplied to this pass as
"already fixed by `DECISION.md` and not up for revision". **`DECISION.md` does not contain it**
(§1.3). The constraint is adopted, it is correct, and it is the right call; but it is a **Phase 2
design decision recorded here for the first time**, not an inheritance.

It is also consistent with prior art: `INVENTORY.md` §2.11 records that `decisions/README.md:22`
traces ADR-012 §4's restriction of the `DecisionSpec` family to per-player ranking, with
`starting_xi/` named as the squad family that sits outside it. The pattern of a decision folder
consuming the layers rather than being consumed by them is established; only its application to a
squad-family harness is new.

### 3.3 The two tiers

Every Python module in `decisions/starting_xi/` is in exactly one tier. A module that cannot be
classified is not written until it can be.

**Tier A — the model-free core.** The replay machinery. May import `domain/`, `dal/`, and other Tier
A modules. **May not import `model/`, `research/`, `serve/`, `operational/`, or any Tier B module.**

**Tier B — the ranker edge.** Ranker implementations and the uncertainty estimators. May import
`model/`, `dal/`, `domain/`. **May not be imported by any Tier A module.** Reaches the harness only
by being passed in as an argument at the call site that owns both (§3.6).

The asymmetry is the point. Tier B's `model/` dependency is real and unavoidable (§3.4); the
contract's job is to stop it propagating, not to pretend it away.

### 3.4 Why `rankers.py` imports `model/` regardless — and why that is settled

The three floor rankers selected at §0.12 are F1 (`p_play` alone), F2 (season-long PPG-to-date) and
F3 (3-gameweek recent form).

`p_play` is a fitted GLM. `INVENTORY.md` §2.6 locates it at `model/terms/p_play/p_play.py:40`
(`PlayModel`) and `:83` (`PlayTerm`), and **measures** its transitive import reach into `model/` by
importing it in a clean interpreter: `model.terms._base`, `model.terms._binary_component`,
`model.terms.p_play.spec`, `model.features.spec`, `model.features.build`, and — because
`model/eval/__init__.py` imports eagerly — the whole of `model.eval` (`baselines`, `metrics`,
`population`, `scorer`, `walkforward`), plus `statsmodels` and `pandas`. Nothing from `research/` or
`serve/`.

`INVENTORY.md` §2.6 also records a citation worth not repeating wrongly:
`model/terms/_binary_component.py:144` is the **shared walk-forward loop of the base class**,
inherited by `p_play`, `minutes` and `defensive_contribution` alike. It is correct evidence that the
fit is as-of; it is **not** `p_play`'s implementation, and should not be cited as such.

**Therefore `rankers.py` imports `model/` whatever else is decided.** One of the three floor rankers
is a fitted per-position GLM, there is no shallow path to it, and no version of this slice omits it —
§0.13 measures the candidate against the **best** naive ranker on the shared window, and F1 is one of
the three.

**The move that is not proposed, and will not be re-proposed.** `expanding_prior_mean`
(`model/eval/baselines.py:58`) is genuinely portable: `INVENTORY.md` §2.1 records it as a one-line
`groupby.transform` taking one argument, and §2.1's fan-out note confirms it imports only `pandas`.
It is therefore a standing temptation to relocate it — into `domain/` or into the slice — so that the
naive floor would carry no `model/` dependency.

**That argument does not survive the `p_play` finding, and §3 records the closure so it is not raised
again.** Moving it would remove a `model/` import from *one* of three floor rankers while F1 keeps
`rankers.py` in `model/` anyway. It would buy no structural property, would break the
single-source-of-the-statistic invariant `INVENTORY.md` §2.1 records its docstring declaring, and
would touch the four call sites `INVENTORY.md` §2.1 lists (`model/compose.py:225`,
`model/forecast/level_estimators.py:80`, `model/forecast/shrinkage.py:87`,
`model/eval/baselines.py:54`) in service of a slice that publishes nothing depending on them. It is
**rejected**, because it does not achieve its own stated goal.

`expanding_prior_mean` is instead reused **as-is, in place, imported from `model/eval/baselines.py`
by `rankers.py`** — Tier B, where a `model/` import is legal by construction.

**Its wrapper is not reusable and must not be imported.** `INVENTORY.md` §2.1 records that
`build_baseline_features` (`model/eval/baselines.py:31`) computes the same statistic behind
`mart[(mart["minutes"] > 0) & (~mart["is_dgw"])]`, and states directly that the filter drops rows for
a player with no fixture. §0.4 keeps such a player selectable and ranked last at 0 points, so that
filter would silently change the feasible formation set and make the counterfactual easier than the
real decision. **Take `expanding_prior_mean`; never `build_baseline_features`.** The harness supplies
its own population, per §0.9 and §8.3.

### 3.5 The per-module contract

Module names below are **placeholders for the roles they name**; fixing the actual file names and
their interfaces is §5's job. What §3 fixes is the **tier of each role and its permissions**, which
hold under any naming.

| Module | Tier | May import | May be imported by |
|---|---|---|---|
| `formations.py` — the shared 8-formation routine | **A** | `domain/` only (plus stdlib, `numpy`, `pandas`) | `harness.py`, the sampler, tests |
| `sampler.py` — the squad sampler | **A** | `domain/`, `dal/`, `formations.py` | `harness.py`, tests |
| `harness.py` — the replay engine | **A** | `dal/`, `domain/`, `formations.py`, `sampler.py` | the composition root, tests |
| `rankers.py` — ranker implementations | **B** | `model/`, `dal/`, `domain/` | the composition root, tests — **never a Tier A module** |

**The 8-formation routine is the most constrained module in the slice, deliberately.** It may import
`domain/` and nothing else project-internal. `INVENTORY.md` §2.4 records that the search is trivial —
sort each position's realised points descending, take the max over 8 prefix-sum combinations, no
solver and no new dependency.

**The constants go to a new `domain/fpl_squad.py`; the routine stays in the slice.** This is a design
decision, and its basis is what `INVENTORY.md` §2.2 records: the quota, the per-position XI bounds and
the cap exist only in `dal/staging/contracts/element_types.yaml` and the staged frame, **never reach
the mart**, and there is no `domain/fpl_squad.py` today; `domain/` is where sourced FPL rule constants
live, annotated per constant; and `.importlinter`'s `no_domain_to_anything` contract forbids `domain`
importing anything project-internal. The split follows: constants in `domain/`, model-free by
enforcement rather than convention, sourced from `element_types` with a drift test rather than
hardcoded in the slice. The routine stays in the slice because `decisions/README.md` makes each
decision folder self-contained; promoting it to `domain/` is the right move **when a second
squad-family decision needs it**, made deliberately then, not speculatively now.

**The routine takes realised points as an argument and reads no data.** That is what keeps it at
`domain/`-only. A version that loaded its own frame would need `dal/`, and a version that scored its
own candidates would need `model/` — the second of those is the failure this section exists to
prevent.

**`harness.py` never imports `rankers.py`.** It receives a ranking function (§3.2). This is not a
style preference: it is the single edge whose absence makes the rest of the table hold.

### 3.6 The transitivity guarantee — worked through

This is the property §3 exists to establish, so it is checked rather than asserted.

`harness.py` must be able to use the 8-formation routine and the sampler **without either of them
reaching `model/`**, or the `dal/`-only constraint of §3.2 breaks by transitivity and the contract is
decorative.

Walking the closure of `harness.py`'s imports:

```
harness.py  →  dal/            (mart, prices, registration)
            →  domain/         (quota, formations, scoring constants)
            →  formations.py   →  domain/                      ✔ closed
            →  sampler.py      →  dal/, domain/, formations.py  ✔ closed
```

No path reaches `model/`. `formations.py` terminates at `domain/`, which `INVENTORY.md` §2.11 records
`.importlinter` already forbidding from importing `dal`, `research`, `model` or `serve`. `sampler.py`
terminates at `dal/` and `domain/`; `INVENTORY.md` §2.11 records the same file's contracts forbidding
`serve → model`, `serve → research` and `research → model`, with `dal` at the base of the declared
root packages. **Both Tier A leaves therefore terminate in layers that are already enforced**, which
means the guarantee does not rest on this document being obeyed — it rests on contracts already in
CI.

The only module in the slice that reaches `model/` is `rankers.py` (and `uncertainty.py`, §8.2), and
nothing in Tier A imports either. The `model/` dependency exists, is named, and is contained.

### 3.7 The `__init__.py` rule — the way this contract actually fails

Making the directory a package requires `__init__.py` files. **They must stay empty of
project-internal imports. No re-exports, no convenience surface.**

The failure mode is concrete and `INVENTORY.md` §2.11 records a live instance of it:
`model/eval/baselines.py` imports only `pandas`, but importing it executes `model/eval/__init__.py`,
which eagerly imports `baselines`, `metrics`, `population`, `scorer` and `walkforward`. That fan-out
happens to stay inside `model.eval` and reaches no forecast component, so nothing is wrong today — but
it is wrong **by luck of what `__init__.py` omits**. `INVENTORY.md` §2.11 records which modules the
omission is doing the work for: `calibration.py`, `captaincy_backtest.py` and `scoring_conformance.py`
reach `model.compose` / `model.simulate` **directly**, plus `captaincy_diagnostics.py` **transitively**
via `captaincy_backtest` — three direct and one transitive, none of them named in `__init__.py`.

Applied here: a single `from decisions.starting_xi.rankers import ...` line in
`decisions/starting_xi/__init__.py` would give **every importer of any module in the package** a
transitive `model/` and `statsmodels` dependency, including `harness.py`. §3.6's closure would be
false, and it would be false at *runtime* while still looking correct in every individual file.

**This will not be caught by import-linter.** `INVENTORY.md` §2.11 records why: import-linter analyses
the static import graph, in which a module importing a sibling submodule is not an edge to the parent
package's own imports, even though Python executes the parent's `__init__.py` at runtime. The rule
therefore needs an **explicit test**, not a linter contract. Writing that test is §5.6's, and its
absence is the single highest-risk gap in this section.

### 3.8 What may import the slice

**Only the composition root, and tests.** Nothing in `dal/`, `domain/`, `research/`, `model/` or
`serve/` may import `decisions/` at all.

This direction matters more than the internal tiers. `decisions/` is a consumer of the layers, and an
import in the other direction would make a decision folder a dependency of the stack that serves it —
inverting the layering `.importlinter` exists to hold and making the folder impossible to delete or
replace independently. `INVENTORY.md` §2.11 records that `operational/` is **not** a root package and
so is covered by no contract, which is why it is the legal place to wire a Tier B ranker into a Tier A
harness.

**The composition root is the only place where Tier A and Tier B meet.** That is the whole shape:
`operational/` imports `rankers.py`, imports `harness.py`, and passes the first into the second.

### 3.9 How the contract is written, and why it must be per-module

**The permission Tier B needs is `model`, not a subpackage allow-list.** A contract permitting only
`model.terms` would fail on the first ranker: `INVENTORY.md` §2.6 measures that importing
`model.terms.p_play.p_play` pulls the whole of `model.eval` — because `model/eval/__init__.py` imports
eagerly (§3.7) and because `model.eval.metrics` and `model.eval.walkforward` are reached directly from
`model/terms/_binary_component.py:23-24` — and F2 imports `model.eval.baselines.expanding_prior_mean`
outright (§3.4). Containment is achieved by the tier split, not by narrowing which parts of `model/`
are legal.

**A single contract for the package as a whole cannot express §3.6's property**, because the package
as a whole *must* be allowed to import `model/` (for `rankers.py`) while `harness.py` *must not*. The
contract has to be written per-module: in `.importlinter` terms, two `forbidden` contracts with
`decisions.starting_xi.harness`, `decisions.starting_xi.sampler`, `decisions.starting_xi.formations`
and `decisions.starting_xi.results` as `source_modules` against `model`/`research`/`serve`, plus one
with the five existing root packages (`INVENTORY.md` §2.11: `dal, domain, research, model, serve`) as
sources against `decisions`. Neither is exotic.

**`research/` is admitted to neither tier, and the exclusion is deliberate.** §0.14 selects `n =
10,000` at the call site, so nothing is inherited from either bootstrap implementation's defaults, and
§8.2 establishes that the symbol the slice would have imported from `research/kernels` has an
equivalent in `model/eval` that Tier B already reaches. The cluster bootstrap `INVENTORY.md` §2.9
records is hard-wired to the rho statistic and has to be built regardless (§10.3). **Granting a
permission nothing uses is not free:** it would widen the contract by a whole layer to serve a call
site that does not exist, and the next module to need an interval would reach for whichever
implementation it imported first — which is the hazard `METRIC.md` §6.2 names when it says a count
acquired by import path is acquired by accident. So `research/` stays out of both tiers, and a future
need for it is a reason to revisit this deliberately rather than a permission already lying around.

**The cost of the whole contract: two files edited** — `pyproject.toml` and `.importlinter` — plus the
new `__init__.py` files. Nothing breaks; re-testing is an import-linter run already in CI.

### 3.10 Does this contract force any file to move?

**No. It forces no file to move, and no call site to be repointed.**

- `expanding_prior_mean` stays at `model/eval/baselines.py:58`, unmoved and unmodified, imported by
  Tier B (§3.4). `INVENTORY.md` §2.1's four call sites are untouched.
- `p_play` stays at `model/terms/p_play/`, unmoved (§3.4).
- Both `block_bootstrap_ci` implementations stay where they are; §0.14 fixes the resample count as a
  call-site argument and §8.2 names the chosen implementation by full module path, so neither needs to
  move for either to be used.
- `domain/fpl_squad.py` (§3.5) is a **new** file, not a move — `INVENTORY.md` §2.2 records that the
  constants it carries exist today only in the staging contract and never reach the mart.

The additions are: `__init__.py` files, an entry in `.importlinter`, an entry in `pyproject.toml`. No
existing module changes.

### 3.11 What §3 does not decide

- **How F3's rolling statistic is computed.** All candidate sources sit inside Tier B, so the import
  contract is indifferent between them. Decided at §6.4.
- **Module names and interfaces.** §5.
- **Where results are written.** §7.

---

## 4. Bench-order scoring rule

### 4.1 What this closes, and what it deliberately leaves open

§0.10 records the standing gap: `METRIC.md` §4.1 characterises **no** candidate bench-order scoring
rule, so there is nothing to select from. §4 constructs one, because the harness cannot be built
without it, and §0.10 states plainly that this is a construction rather than a selection.

**The split of authority.** §0.2–§0.6 fix the substitution *mechanics* — the trigger, the GK/outfield
split, the legality condition, the priority-queue semantics, incoming eligibility. §4 owns the
*algorithm* that implements them and the *scoring rule* built on top.

One thing remains genuinely open at the end of this section and is marked as such rather than
resolved: how uncertainty is quantified on the ordering sample (§4.11).

### 4.2 Only one of the two orderings carries a decision

§0.6 fixes that the GK slot is a separate process from the three outfield slots, so bench order is
two orderings rather than one ranking of four.

**The GK ordering is degenerate, and this is worth stating because it halves the secondary decision's
apparent scope.** `INVENTORY.md` §2.2 records `squad_select` = 2 for GK and
`squad_min_play` = `squad_max_play` = 1, so a 15-man squad holds exactly 2 goalkeepers and every legal
formation starts exactly 1. The bench therefore holds **exactly one** goalkeeper, and an ordering over
one element carries no information. The GK process still fires or fails to fire, and it still moves
the realised total — but **no bench-order method can differ from another on it**.

**The bench-order decision is therefore an ordering over 3 outfield players: 3! = 6 possible
orderings.** Every count, every comparison and every claim in this section is about those three slots.
The GK slot enters the replay (§4.3) and the substitution count (§4.6), and contributes identically
zero to the ordering-relevant count.

### 4.3 The replay algorithm — how an ordering becomes a realised total

The scoring rule needs one deterministic function: given a squad, a chosen XI, an ordering over the
outfield bench, and the realised minutes and points, return the realised total.

**Vacancies are processed one at a time, and each is filled before the next is considered.** This is
the design choice that keeps the multi-substitution case well defined. Every intermediate state is a
full 11-man XI, so §0.6's legality condition is evaluated against a complete formation every time. The
alternative, removing all blanked starters first and refilling from a 9-man state, would require
checking legality of a partial XI, which the formation constraints do not define.

```
GK slot (separate process, per §0.6):
  if the starting GK recorded no minutes and the bench GK is eligible:
      swap them.                       # single slot; no ordering choice exists

Outfield slots:
  vacancies := blanked outfield starters, in canonical order (§4.3.1)
  queue     := the 3 outfield bench players, in the ordering under test
  for each vacancy v:
      remove v from the XI                          # XI now has 10
      for each bench player b in queue, in order:
          if b is eligible and XI + b is a legal formation:
              add b to the XI; remove b from queue; break
          else:
              skip b — b REMAINS in queue for later vacancies   # §0.6
      # if no b qualifies, the vacancy stays unfilled and the XI finishes short
realised total := sum of points over the final XI
```

`eligible` is §0.5's predicate — the entering player must himself have recorded minutes — which is the
same two-state predicate as §0.3's trigger, covering both `minutes = 0` and `minutes` NULL.

**The skip semantics are the priority-queue reading §0.6 selects**, and the loop structure is what
implements them: skipping `b` advances the inner scan but does not consume `b`, so `b` is still at his
position in `queue` when the next vacancy opens. A rule that consumed a skipped player would measure a
different bench order, which is exactly what `METRIC.md` §2.5 says of the alternative.

**The multi-substitution case, worked.** Chosen XI is 1-3-5-2; a DEF and a MID both blank; the
outfield bench in priority order is [FWD_a, DEF_b, MID_c]. Processing the DEF vacancy: FWD_a would
give 1-2-5-3, which fails the 3-DEF minimum `INVENTORY.md` §2.2 records, so FWD_a is **skipped and
retained**; DEF_b enters, restoring 1-3-5-2. Processing the MID vacancy: the queue is still
[FWD_a, MID_c], FWD_a now gives 1-3-4-3, which is legal, so FWD_a enters. Both substitutions fire, and
FWD_a comes on **because he was retained rather than consumed** at the first vacancy.

#### 4.3.1 The vacancy order is pinned, and the invariance is a test rather than an assumption

The loop above iterates vacancies, so the order of that iteration is part of the rule. It is **fixed
as: DEF, then MID, then FWD; ties broken by ascending `player_id`.**

Two properties motivate the choice. It is **deterministic**, so a replay reproduces. And it is
**independent of the ranker**, so no ranker's scoring can influence which vacancy is served first —
the same independence principle §0.16 applies to squad construction.

**Whether the final XI is invariant to this order is an open empirical question, and the design does
not rely on it.** Worked examples suggest the outcome set is order-independent — the legality
constraint depends only on the multiset of positions in the final XI, not on which vacancy a player
nominally filled — but that is an observation across a handful of cases, not a proof, and the
constraint structure near the formation bounds is where it would fail if it fails. Pinning the order
makes the rule correct regardless. **The invariance claim is stated as a test obligation** — replay
each ordering under all vacancy permutations and assert an identical realised total — and not as a
premise. If the test fails, the pinned order is still the rule and the failure is a finding to report.

### 4.4 How a bench ordering is scored

**Ordering regret**, mirroring the shape of P1 (§0.1) rather than inventing a second vocabulary:

```
ordering_regret(gw, squad, XI, σ) = realised_total(best σ*) − realised_total(σ)
```

over the same squad, the same chosen XI, the same realised minutes and points, with σ* the
best-performing ordering among the candidates being compared. It is ≥ 0 and 0 for the best available
call, exactly as P1 is.

**This is a construction, not a selection** — §0.10 states why, and that no alternative rule has been
characterised for it to have been chosen over.

**The counterfactual is the best *ordering*, holding the XI fixed — not the best XI.** That is what
makes this the secondary decision rather than a restatement of the primary one. It is also strictly
weaker than a joint optimum, which is correct: `METRIC.md` §2.1 records that a joint
XI-and-bench-order optimum is "a different and harder decision" than the one `DECISION.md` §1 names as
primary, and §0.2 declines it on that ground.

**Bench-order evaluation is conditioned on a fixed XI, and this is not optional.** The bench is the
**complement** of the XI within the 15. Two rankers that select different XIs therefore have different
bench *sets*, and comparing their orderings would compare selections wearing the clothes of an
ordering comparison. So for each squad-week the XI is held fixed and the candidate orderings are
compared over **that** bench. The natural fixing is each ranker's own XI — hold ranker r's XI, compare
candidate orderings of r's bench — which measures what a manager could actually change once the XI is
settled, and matches the dependency order in `DECISION.md` §3, where the XI decision resolves before
what follows it.

### 4.5 How two orderings are compared

Paired, on the same squads and gameweeks, exactly as §0.14 pairs the primary comparison:

```
Δ(σ1, σ2) = mean ordering_regret(σ1) − mean ordering_regret(σ2)
```

taken over the **ordering-relevant weeks only** (§0.11), with both orderings replayed against
identical squads, identical XIs, identical blanks, and identical realised points. Every term that is
not the ordering is held constant, so the difference isolates it.

### 4.6 The counts, and how each is computed

**The substitution count (B1).** Squad-weeks in which a selected player recorded no minutes **and a
substitution fired**. Computed by running §4.3 and counting the squad-weeks with at least one executed
swap, GK or outfield. This is primary-path: it sizes the headline regret figure, because those are
exactly the weeks where the chosen XI's realised total departs from the sum of the eleven selected
(`METRIC.md` §4.2).

**A third quantity falls out of the algorithm and should be reported with it.** A starter can record
no minutes and **no substitution fire** — every bench player ineligible, or every swap
formation-illegal. Those weeks are in neither count above, and the gap between "a starter blanked" and
"a substitution fired" is itself informative: it measures how often the bench failed to cover at all.
Call it the **uncovered-blank count**. It costs nothing to emit, since §4.3 already distinguishes the
case. It is this document's addition; `METRIC.md` §4.2 characterises B1 and B2 only.

**The ordering-relevant count (B2).** Squad-weeks in which at least one substitution fired **and the
candidate orderings actually being compared would bring on a different set of players**. Computed by
replaying §4.3 once per candidate ordering against the same fixed XI, and counting the squad-weeks
where the resulting sets of entering players are not all identical. Each replay is a row in §7.2's T5,
and the count is **derived** from those rows at assembly rather than emitted by the harness (§7.2.1) —
relevance is a comparison between orderings and has no single-ordering home.

**Defined over the orderings actually compared, not over all 6 permutations** — §0.11 states the
choice and its reason. The permutation count is a legitimate diagnostic of the decision's *headroom*
and may be reported as such; it is not the denominator.

### 4.7 Which count denominates which claim

| Claim | Denominator |
|---|---|
| Headline regret, and every primary figure under §0.1 | All squad-weeks in scope, after §0.8's exclusions |
| "The chosen XI's realised total departed from the eleven selected this often" | Substitution count (B1) |
| "The bench failed to cover a blank this often" | Uncovered-blank count |
| **Any bench-order claim** — mean ordering regret, or one ordering beating another | **Ordering-relevant count (B2)** |

No bench-order figure is ever reported against the substitution count. That is the specific
overstatement `METRIC.md` §4.2 names when it observes that B1 counts weeks where every candidate
ordering brings on the same player, and the table exists to make it unavailable.

### 4.8 The three squad-week cases, stated explicitly

**No substitution fires.** The ordering was not live. The week contributes to the primary regret
figure and to nothing else. **Ordering regret is undefined, not zero.** Recording it as 0 would pull
every candidate's mean toward 0 in proportion to how rare substitutions are, making all orderings look
equally good and the decision look better-measured than it is. The week is excluded from the ordering
denominator entirely.

**A substitution fires, but every candidate ordering brings on the same player.** The week counts
toward B1 and is **excluded from B2**. Ordering regret is genuinely 0 for every candidate — but it is
0 *because the orderings were indistinguishable*, not because each chose well, and averaging those
zeros in would dilute the mean toward 0 for every method equally. This is the same exclusion §0.8
applies on the primary side to zero-gap weeks, applied for the same reason — and `METRIC.md` §4.2
draws exactly that parallel in characterising B2.

**A substitution fires and the candidate orderings differ.** The week enters B2 and carries the
bench-order comparison. These weeks are the entire evidence base for the secondary decision.

### 4.9 Separate or folded — separate, and the alternative costs more than it saves

**Bench-order performance is reported as its own quantity, never folded into a single number with XI
regret.** `DECISION.md` §1 makes bench order the secondary decision and states it is reported
separately; `METRIC.md` §4 opens by recording that. §4 adds the design-level reason.

**What folding would cost.** A single combined number would average a decision live in a small subset
of weeks against one live every week. `DECISION.md` §1 states the consequence — it "hides both" — and
the arithmetic is unforgiving: with ordering-relevant weeks plausibly a small fraction of the sample
(§4.10), a combined figure would be roughly the primary number plus noise, and a real bench-order
effect would be undetectable inside it. The saving — one number instead of two — is not worth an
undetectable secondary result.

**A coupling that the separation does not remove, and that §4 will not paper over.** §0.2 scores the
chosen XI **after** substitutions fire, and §4.3 shows the realised total depends on the ordering. So
the primary regret figure is **not** independent of bench order: on precisely the ordering-relevant
weeks, changing the ordering changes the chosen side's total and therefore the primary number. The
dependence is bounded — at most the ordering regret, on at most the ordering-relevant weeks, zero
everywhere else — but it is real. `METRIC.md` §2.1 records the same property from the metric side and
warns that any claim of clean separation is stronger than the mechanics support. The practical
consequence for the design: **every primary regret figure must name the bench ordering used to produce
it**, or it is not reproducible. §5.4 makes that structural.

### 4.10 Liveness — the ordering-relevant count is likely small, and that is a finding

**The substitution count is likely large.** Uniform squads (§2) are drawn mostly from cheap players,
who rotate and blank more often than premiums; across 11 starters, at least one blank in a given
gameweek should be common rather than rare.

**The ordering-relevant count is likely much smaller**, and three independent narrowings compound: the
GK slot contributes nothing (§4.2); with only 3 outfield bench players, often only one is eligible,
and every ordering then brings on the same man; and where two are eligible, the candidate methods must
additionally *disagree* about their relative order. Weeks where two outfield starters blank are where
ordering genuinely bites, and those are a subset of a subset.

**What follows is a reporting posture, not a design change.** If B2 comes back small, the bench-order
comparison is reported as **underpowered** — the count, the point estimate, and the explicit statement
that one season does not resolve it — and no significance claim is made from it. `DECISION.md`'s
Provenance section already anticipates this, and `METRIC.md` §4.2 records that the check has not been
run and no number for it is asserted anywhere in this folder.

**Nothing in this design is adjusted to make the number bigger.** Widening the trigger, counting
permutation-relevant weeks instead of comparison-relevant ones, or folding indistinguishable weeks
back in would each inflate the apparent evidence without adding any.

### 4.11 The one item §4 leaves open

**Uncertainty on the ordering sample.** §0.14 fixes the paired-interval machinery for the primary
comparison, resampling squads and gameweeks separately at n = 10,000. Whether the same treatment
transfers to a much smaller, differently-structured ordering sample — where the unit is an
ordering-relevant squad-week rather than a squad-week — is not settled by that selection and is not
settled here. It is a metric-level question about a metric (§4.4) that has itself never been surveyed,
so it belongs with §0.10's flagged `METRIC.md` pass rather than being answered inside the build.

It is not filled with a plausible-looking rule, for the same reason `METRIC.md` §4.1 gives for leaving
the scoring definition open: a rule written before the thing it quantifies has been characterised is a
guess in the shape of a decision.

### 4.12 What §4 does not decide

- **The substitution mechanics.** §0.2–§0.6 fix them; §4 implements them.
- **How results are stored and reported.** §7.
- **The ranker interface that produces an ordering.** §6. §4 assumes only that a ranker scores all 15
  and that the bench ordering is the induced order over the 4 non-selected players, GK separated — it
  does not fix how.
- **Bench Boost.** `DECISION.md` §5 puts chip interaction out of scope; under Bench Boost every bench
  player scores and the ordering decision disappears entirely rather than changing form.

### 4.13 The residual coupling, stated once so it is not mistaken for clean separation

`METRIC.md` §2.1 records that the asymmetric auto-substitution option does not fully separate ranking
quality from bench coverage, and points at this section from the build side. The statement of record
is §4.9's: the chosen side is scored after substitutions and those depend on the ordering, so on the
ordering-relevant weeks the primary number is a function of the ordering used. The coupling is
bounded, it is real, and the design's response is structural rather than rhetorical — §5.4 makes
`bench_order` a required argument with no default, and §7.2's T2 carries the primary ordering's replay
and no other, with the manifest naming it (§7.3). A reader who takes "regret measures ranking quality,
not ranking quality plus bench coverage" as exact will be wrong on those weeks and only those.

---

## 5. Module shapes and interfaces

### 5.1 The module table

One row per module. The **forbidden imports** column restates §3's per-module contract; it invents
nothing. No module below needs an import §3 forbids, and §5.2 records the one place that was checked
rather than assumed.

| Module | Tier | Takes | Returns | Forbidden from importing |
|---|---|---|---|---|
| `formations.py` | A | a 15's realised points with each player's position; or a candidate XI | the best legal XI total and the runner-up (§0.8's C1), and a legality predicate over a candidate XI | everything project-internal except `domain/` — no `dal/`, no `model/`, no `research/`, no `serve/`, no sibling slice module |
| `sampler.py` | A | mart across the gameweeks in scope (`dal/`); the **gameweek list**, explicitly; quota + cap (`domain/`); `n_squads` **per gameweek**; **master `seed` — required, no default** (§2.9) | frozen squad table (`gw`, `squad_id`, `player_id`), one `gw` per `squad_id` **plus a per-gameweek run record**: derived seed, \|U_g\|, pilot k_g and p̂_g, proposals drawn, accepted count, realised acceptance rate, four diversity diagnostics — and the run-level **mart pin** (§5.3) | `model/`, `research/`, `serve/`, `operational/`, `rankers.py` |
| `harness.py` | A | squad table; **`rank_fn`**; **`bench_order` — required, no default**: a non-empty ordered sequence of named ordering **policies** (callables), element 0 primary (§5.4); mart (`dal/`); comparison window | per-squad-week records — chosen XI, realised total, best-legal-XI total, runner-up total, regret, substitution and uncovered-blank flags — **plus one replay record per candidate ordering** (§7.2's T5). Ordering-relevance is derived at assembly, not emitted (§7.2.1) | `model/`, `research/`, `serve/`, `rankers.py` — it receives a ranker, never imports one |
| `rankers.py` | B | the mart | a `RankerOutput` per ranker — name, declared window, score panel (§6.1) | `harness.py`, `sampler.py`, `formations.py` — no Tier A module. `model/`, `dal/`, `domain/` are permitted |
| `results.py` | A | the harness's per-squad-week and per-ordering records, the comparison results, and the manifest fields (§7.3) | nothing — writes T1–T5 to `results/` and returns the `run_id` | `model/`, `research/`, `serve/`, `rankers.py` |
| `uncertainty.py` | **B** | **(a)** an ordered per-gameweek series of paired differences, plus `n`, `block`, `ci_level`, `seed`; **(b)** a `(gw, squad_id, value)` panel of paired differences, plus `n`, `ci_level`, `seed`; stratified by `gw` (§10.3). Two functions, not one (§10.6) | a `(lo, hi)` percentile interval per call, unrounded | `research/`, `serve/`, `operational/`, and every Tier A module — `harness.py`, `sampler.py`, `formations.py`, `results.py`. `model/`, `dal/`, `domain/` are permitted |

**`rankers.py` may not import `formations.py`, and does not need to.** §3.5 lists its permitted
imports as `model/`, `dal/`, `domain/`, and a ranker scores *players*, never squads or XIs — the
formation routine belongs to the scoring side of the harness, not the ranking side. The one thing that
would have needed it, an XI-aware ranker, is out of scope: §0.16 requires squad construction be
independent of the ranker, and a ranker that reasoned about legal XIs would be reaching into the
harness's half of the problem.

### 5.2 No module's shape needs an import §3 forbids

Checked rather than assumed, since this is the section where a shape could quietly force one.

The only candidate was `formations.py`. §0.1's counterfactual is computed over **realised points**,
which live on the mart — so a version of the routine that *loaded* its own frame would need `dal/`,
which §3.5 forbids it. It does not load: it takes the realised points as an argument, per §2.9's
statement of the same constraint from the sampler's side. The routine is a pure function of what it is
handed, and stays at `domain/`-only.

`harness.py` reads the mart and therefore imports `dal/`, which §3.5 permits. It never imports
`model/`, because it receives `rank_fn` rather than constructing one — §3.2's constraint, and the
reason the transitive closure in §3.6 holds.

### 5.3 The mart pin is part of the sampler's output, not a note beside it

§2.8 established that rejection sampling consumes a **data-dependent** number of RNG draws, so the
same seed against a different mart yields a different squad set. The frozen squad table is therefore
reproducible only against the mart it was drawn from, and a seed alone does not identify it.

**The sampler returns the pin in its run record**, alongside the seed and the acceptance diagnostics.
It is emitted as data — a content hash of the GW2 slice actually read, plus the mart's row count and
gameweek span — so that a later run can *verify* rather than assume it is reproducing against the same
input. A pin recorded only in prose beside the artefact would not survive the artefact being moved,
and could not be asserted on.

**What §5 does not fix:** where that record is written. §7 owns storage. §5 fixes that the pin is
returned, which is what makes storing it possible.

### 5.4 The harness takes the bench ordering explicitly

§4.9 established that primary regret is **not** independent of bench order. A harness with an implicit
or defaulted ordering would therefore emit a primary regret figure whose value could not be
reconstructed from its stated inputs.

**`bench_order` is a required argument with no default**, on the same terms as the sampler's seed
(§2.9). Every regret figure the harness emits carries the ordering that produced it in its own record,
so "the primary number" is always "the primary number under this ordering".

**What `bench_order` *is*: an ordered, non-empty sequence of named ordering policies, each a callable
— not a value.**

```
OrderingPolicy = (bench_outfield, scores) -> ordered list of the 3 outfield bench players
bench_order    : Sequence[(name, OrderingPolicy)]     # non-empty; element 0 is the primary
```

Element 0 is the **primary** ordering: it produces the realised totals behind the reported regret. The
remainder are the candidate orderings of §4.6. The GK slot takes no policy — with exactly one bench
goalkeeper the ordering is degenerate (§4.2).

**Why a callable rather than a value.** The bench is the **complement of the XI** within the 15
(§4.4), and the XI is produced by `rank_fn` *inside* the harness. A caller supplying a precomputed
ordering would first have to know the bench, which means knowing the XI, which means running selection
— so the harness would have to expose XI selection as a **second entry point**, and the caller would
run selection, build orderings, then re-enter for the replay. That splits one run into two halves that
must be trusted to reproduce an identical XI between them, which is exactly what §4.5 requires be
guaranteed rather than trusted. A policy callable removes the split: the harness derives the bench and
asks the policy to order it.

**Why a sequence rather than a single callable.** §4.6 computes B2 "by replaying §4.3 once per
candidate ordering **against the same fixed XI**". With one policy per call that comparison would need
two harness runs and a post-hoc join, and the identical-XI guarantee would again rest on
reproducibility rather than construction. It would also refit the expensive part for nothing:
`INVENTORY.md` §2.6 records that `p_play`'s fit re-estimates per position per gameweek, so re-running
the harness to vary a bench ordering would refit it once per ordering while changing nothing about the
selection. The sequence form replays only §4.3 — the cheap substitution step — per policy, against one
XI computed once.

**A note on arity.** §3.2 fixes the constraint as "harness.py takes a ranking function as an
argument". §4.9's obligation makes that two arguments rather than one. This is a consequence of §4,
not a departure from §3: the import contract §3.2 exists to protect is about what `harness.py`
**imports**, and it is unaffected by how many callables it receives.

### 5.5 Where the block bootstrap is called

**`uncertainty.py`** — a module whose *shape* §5 fixes. It takes paired per-gameweek or per-squad
differences and returns an interval, at `n` and `seed` passed explicitly by the caller (§0.14).

What §5 contributes is the constraint that already followed from §3.2: **this cannot be `harness.py`**,
which is `dal/`-only. §8.2 establishes that §3.3 admits `research/` to **neither** tier, which makes
the slice's bootstrap call site `model/eval/metrics.py:79` and places `uncertainty.py` in **Tier B**;
§10.6 fixes that the two intervals take **two functions with deliberately non-interchangeable input
shapes**, not one shared signature.

### 5.6 The `__init__.py` rule, and the test that enforces it

§3.7 routed this here. The rule is stated as **what `__init__.py` may contain**, not only as what the
package may import, because the failure is a file's contents rather than a module's dependency.

**The rule.** `decisions/__init__.py` and `decisions/starting_xi/__init__.py` contain a module
docstring and nothing else. **No `import` statement of any kind, no `from … import`, no re-exports, no
`__all__` naming submodules, no convenience aliases.** A caller reaches a module by its full path —
`from decisions.starting_xi.harness import …` — always.

**Why the rule is about contents.** §3.7 established the mechanism from `INVENTORY.md` §2.11's
measured instance: one `from decisions.starting_xi.rankers import …` line in the package
`__init__.py` gives **every** importer of **any** module in the package a transitive `model/` and
`statsmodels` dependency, `harness.py` included, because Python executes the parent package's
`__init__.py` before the submodule. §3.6's closure would be false at runtime while every individual
file still read correctly, and `INVENTORY.md` §2.11 records that **import-linter cannot catch it** —
parent-package `__init__` execution is not an edge in its static graph.

**The test.** A `sys.modules` isolation test, and it **must run in a subprocess**.

- **What it asserts.** After importing `decisions.starting_xi.harness` — and, separately,
  `decisions.starting_xi.sampler` and `decisions.starting_xi.formations` — the interpreter's
  `sys.modules` contains no key equal to or prefixed by `model`, `statsmodels`, `research`, or
  `serve`.
- **What it imports to do so.** `subprocess` and `sys`, from the standard library, and nothing from
  the slice. The test spawns `sys.executable` with a `-c` program that performs the import and the
  assertion inside the child, and asserts the child exited zero.
- **Why a subprocess and not an in-process assertion.** `INVENTORY.md` §2.11 records that
  `pyproject.toml:34` sets `testpaths = ["tests", "model"]`, so a pytest session imports `model` — and
  through it `statsmodels` — before any test outside those paths runs, and states the consequence
  directly: an in-process `sys.modules` assertion cannot distinguish the module under test from what
  the session already imported, and establishing that requires a subprocess. The subprocess is the
  whole mechanism, not an implementation detail.

**One positive assertion belongs with it.** The same test asserts that importing
`decisions.starting_xi.rankers` **does** bring `model` into a clean interpreter. That is the Tier B
edge §3.4 says is unavoidable, and pinning it means the test fails loudly if the ranker edge ever
moves — which would mean §3's two-tier split had quietly changed shape.

### 5.7 What §5 does not decide

- **Results storage and the run manifest** — §7.
- **Which `block_bootstrap_ci` implementation is called** — §8.2.
- **Exact function names within each module.** The table fixes each module's role, inputs, outputs and
  forbidden imports; naming a function `run` versus `replay` changes nothing the contract depends on.
- **No helper module is created for F3's rolling computation.** §6.4 places it inside `rankers.py`.

---

## 6. Ranker interface

### 6.1 One signature, and it is panel-producing

```
RankerOutput:
    name    : str
    window  : (first_gw, last_gw)                  # inclusive; declared, not inferred
    scores  : frame of (player_id, gw, score)      # higher score = more preferred

rank(mart) -> RankerOutput
```

**Called once per ranker per run, over the whole mart — not once per gameweek.** This is the decision
that makes the interface work for every ranker rather than only for the easy ones, and it is worth
stating why rather than leaving it implicit in the type.

**The stateful ranker is the one that matters, and the panel shape is what accommodates it.**
`INVENTORY.md` §2.6 reads the fit loop directly: `model/terms/_binary_component.py:144–145` trains on
`gw < t` and predicts `gw == t`, expanding, per position, for every `t > WARMUP_GW`, re-estimating the
model at each gameweek from strictly prior rows. The as-of guarantee therefore lives **inside** the
ranker's own fit, and one call returns predictions for the whole panel.

A per-gameweek signature — `rank(gw, candidates) -> scores` — would break on exactly this ranker. Each
call would have to re-run the entire expanding walk-forward from the start of the season to produce one
gameweek's predictions, making the run quadratic in gameweeks and re-fitting the same GLMs 35 times
over. F2 and F3 would not care, because they are vectorised transforms. **A signature chosen against
the cheap rankers would have been unusable for the one the floor most depends on**, and that asymmetry
is invisible until you look at how `p_play` actually fits.

**Construction-time configuration is the ranker's own business.** The interface is satisfied by a plain
function *or* by a configured callable object, and does not require rankers to be stateless — only that
whatever state exists is fixed before `rank` is called and is not mutated by it.

### 6.2 What a ranker is forbidden from doing

- **Reading `status` or `chance_of_playing`.** `INVENTORY.md` §2.6 records that these are staged in the
  `players` table and **do not reach the mart**, confirmed against its full 64-column list, so they are
  unavailable to any mart consumer — and `p_play` derives entirely from lagged `minutes` and `starts`.
  The rule is stated anyway, because it binds every future ranker and because a ranker reaching outside
  the mart for them would be reading a post-season snapshot against every gameweek.
- **Reading any row at gameweek ≥ t when scoring gameweek t.** Lag-1 by construction — `shift(1)`
  before any rolling or expanding window, within player. `INVENTORY.md` §2.1 records the repository's
  existing guard of this shape, the `assert_lag_safe` property at `model/features/build.py:190`.
- **Reading realised outcomes for the gameweek being scored**, including its own target.
- **Reading the squad table or anything the sampler produced.** §0.16's independence property runs in
  both directions: a ranker that saw which squads it would be scored on could tune to them. §5.1
  enforces the structural half — `rankers.py` may not import `sampler.py`.
- **Mutating the mart it is given.** The same frame is handed to every ranker in a paired comparison;
  an in-place edit would silently change what a later ranker sees.
- **Adopting `assert_no_future_leakage` as its leakage guard.** `INVENTORY.md` §3.7 records, verified
  by execution, that this guard requires `points_roll3` — a column the governed mart deliberately
  excludes (§2.1) — so it fails closed against the very data this harness reads, and that its own
  remediation advice names the source the failing call already used. A ranker needing a leakage
  assertion writes one against the columns it actually uses.

### 6.3 Windows, intersections, and what happens when the intersection is thin

**Every ranker declares its window; the harness does not infer it** (§0.7). The three floor
declarations: F1 GW4–38, F2 GW2–38, F3 GW2–38. F1 starts at GW4 because `INVENTORY.md` §2.6 records
`WARMUP_GW = 3` at `model/eval/walkforward.py:58` with predictions beginning at GW4.

**How the intersection is computed.** For a comparison over a set of rankers R:

```
window(R) = [ max over r in R of first_gw(r) ,  min over r in R of last_gw(r) ]
            ∩ GW2–38                                    # §0.7's study-level scope
```

then narrowed by §0.8's zero-gap exclusions, which remove squad-weeks rather than truncating the span.
For the three naive rankers this yields **GW4–38** — F1 binds, and the two PPG rankers' earlier
availability is not usable in any comparison that includes it.

**Where it is recorded.** With every figure, not once per run — that is the obligation §0.7's declared
windows create. Each emitted comparison carries the declared window of every ranker in it, the computed
intersection, and the count of scoreable gameweeks surviving §0.8's exclusions. §7 owns where that
lands; §6 fixes that it travels with the figure rather than sitting in a run header.

**If the intersection is empty**, the comparison is not run and is reported as **not evaluable** — not
as a tie, not as a fail, and not silently omitted. An empty intersection is a statement about the two
rankers' coverage, and dropping it would hide a ranker whose window makes it incomparable with the
floor.

**If the intersection is too short.** §0.14 fixes the gameweek interval as a moving-block bootstrap
with `block = 4`, so a comparison window shorter than one block cannot support the estimator and §0.15's
S2 cannot be evaluated. Such a comparison is reported as **underpowered, with its point estimate and
its span**, and no success claim is made from it. **The threshold is stated as four scoreable gameweeks;
what the two existing implementations return below that length is a repository fact this document does
not carry** — §11 flags it as an `INVENTORY.md` gap. The design does not depend on the answer: the
comparison is reported underpowered either way, and the only thing at stake is whether the harness must
guard the call or may rely on the estimator's own behaviour.

### 6.4 F3's `min_periods` — 1, via `add_lagged_rolls`, over a harness-built population

**Selected: `min_periods = 1`**, computed via `add_lagged_rolls` (`model/features/build.py:37`,
`INVENTORY.md` §2.1) inside `rankers.py`, over a population the harness builds. No new helper module
(§5.7).

**The choice is real, and `INVENTORY.md` §2.1 measures why.** It records **two coexisting
conventions**: `build_baseline_features` computes its rolling points columns inline at
`model/eval/baselines.py:53` with `min_periods=k`, so warmup rows are **NaN**, while `add_lagged_rolls`
and every `_lag_roll` use `min_periods=1`, so warmup rows are **partial-window means**. The two yield
different values over the warmup rows of any window, which makes this a metric-affecting choice — it
defines one of the three floor rankers, and therefore the floor mean regret the §0.15 bar is measured
against.

**Two arguments decide it, both from what the floor should measure.**

1. **`min_periods = k` would make availability a per-player property, which the window abstraction
   cannot express.** It yields NaN for any player with fewer than *k* prior observations — not only in
   early gameweeks, but all season for a fringe player with two appearances by GW30. §0.7's declared
   windows and §6.3's intersection machinery operate on **windows**; a ranker whose coverage is
   player-dependent cannot declare one honestly.
2. **It would make the floor weak in exactly the way §2.2 warns about.** Uniform squads are drawn
   mostly from cheap, rotation-prone players (§2.3). Under `min_periods = k` a large share of any drawn
   15 would be unscoreable and fall to §6.5's tie-break, so F3 would degenerate toward arbitrary
   ordering — and degenerate *correlated with price*, the same axis §2.2 identifies as the one that
   tilts comparisons. A floor that is weak because it cannot score the squads it is given is not a
   floor.

**What the selection costs.**

- **The statistic is not literally a 3-gameweek mean early on.** At GW2 it is a one-gameweek mean, at
  GW3 a two-gameweek mean. That thinness must be visible in the reported span rather than hidden behind
  a minimum-observations cut, and it should be **stated in the results**: `METRIC.md` §5.3 records that
  F2 and F3 are the identical statistic at GW2, GW3 and GW4, with the measurement at `METRIC.md`
  Appendix A.3.
- **A second package enters `rankers.py`'s import set** (`model.features`). This costs nothing under
  §3: `rankers.py` is Tier B and already imports `model/` unavoidably (§3.4), and `INVENTORY.md` §2.1
  measures the fan-out as two leaf modules — `build` imports only `model.features.spec` plus `pandas`,
  and `spec` imports nothing project-internal.
- **The codebase keeps two `min_periods` conventions.** `model/eval/baselines.py` stays at `k` for the
  forecast harness; the slice adopts `1`. Nothing is unified — which mirrors §0.14's handling of the
  duplicated bootstrap: name the value you need explicitly at your own call site rather than
  re-baselining someone else's published numbers.

**Why `add_lagged_rolls` rather than the two-line expression, and the honest size of that choice.**
Both produce the same statistic. `INVENTORY.md` §2.1 records that `add_lagged_rolls` is the one helper
in the repository that materialises a rolling window of an arbitrary mart column, that it is guarded by
the `assert_lag_safe` property, and that the `base_roll{k}` alternative is an **expression inside**
`build_baseline_features` rather than a separately callable helper — and §3.4 rules out importing that
enclosing function. So the real comparison is `add_lagged_rolls` against a fresh two-line expression in
the slice, and that part **is** a tidiness question, and a small one. The part that is not about
tidiness is the population.

**The precondition that carries the real risk.** Neither candidate computes the required statistic on
its own: both roll over **whatever rows they are handed**, and §0.9 fixes the denominator as gameweeks
elapsed, not appearances, with blanks and no-fixture weeks at 0 and pre-registration weeks excluded. So
the ranker must first build the population — the full player-gameweek spine restricted to each player's
post-registration window, with null `total_points` filled to **0** — before any rolling call. §8.3
states the assertion that protects it.

**Interaction with the declared window.** `min_periods = 1` is what lets F3 declare **GW2–38**
honestly: every player in the squad universe has at least GW1 in the game under §0.16's registration
predicate, so every player has at least one prior gameweek from GW2 onward and no player is
unscoreable. Under `min_periods = k` the declared window would have to move to GW5 at the earliest —
and, per point 1 above, even that would be a false declaration, because per-player holes would persist
beyond it. *A qualification: GW2–GW3 fall outside any comparison that includes F1, which binds the
common window to GW4–38 (§6.3), so the two gameweeks this paragraph buys are not used there. The
selection is unaffected — it rests on the two grounds above, both independent of the span.*

### 6.5 Unscoreable rows

**The mechanical rule.** A ranker that cannot score a `(player, gw)` row inside its declared window
emits it as **unrankable** rather than as a number. The harness places unrankable players **below every
scored player**, ties broken by ascending `player_id`. Deterministic, and it never invents a score.

**Where the rule bites: `is_dgw` rows.** `INVENTORY.md` §2.6 records that `PlayModel.population` filters
`~mart["is_dgw"]` at line 78, so F1 produces no score for double-gameweek rows while F2 and F3 do. No
constant can fill the hole — P(play) in a double gameweek is not 0 and is not a fixed number — so those
rows stay unrankable and this rule governs them. `INVENTORY.md` §3.4 records that whether the exclusion
is material is unmeasurable without a squad set, which makes it a first-run measurement (§1.5).

**The case this rule was written for — no-fixture rows — is handled upstream instead.**
`INVENTORY.md` §2.6 records that `PlayModel`'s population also drops rows with null `minutes`, which
would have produced an asymmetry: the unrankable-last rule would bench every no-fixture player for F1
and only for F1, handing one floor ranker an implicit fixture-awareness the other two lacked. §0.4
selects the rule that applies **identically to every ranker** for exactly that reason, so those rows
never reach this one. The measurement §0.4 attaches — the per-ranker count of squad-weeks in which the
rule changed the selected XI — is stored at §7.6.

### 6.6 What §6 does not decide

- **The `points_roll3` governance verdict.** §0.12 gates F3 on it and §9.1 carries it. §6.4 decides
  *how* the column is computed if it may be computed; it does not decide *whether*. If the verdict
  binds, F3 does not exist in its current form and §6.4 is moot rather than wrong.
- **Which bootstrap implementation is called** — §8.2.
- **The as-of denominator** — §0.9 fixes it; §6 consumes it.

---

## 7. Results shape and location

### 7.1 The purpose, and the granularity it forces

**Analysis never re-runs the harness.** The Phase 5 results document must be producible from the
artefact alone. That is a constraint on *granularity*, not only on content, and it is the constraint
that decides the schema below.

Three findings this slice already knows it must report cannot be represented at comparison grain:

- **The GW4 degeneracy.** `METRIC.md` §5.3 records that F2 and F3 return the same number for every
  player at GW2–GW4, with the measurement at `METRIC.md` Appendix A.3. It is a **per-gameweek,
  per-ranker-pair** fact; a table of mean regrets and intervals cannot show it.
- **The GW5–38 agreement rate.** `METRIC.md` Appendix A.4 records that the two statistics still return
  equal values on 38.6% of player-gameweek rows across GW5–38, 98.3% of those being players whose
  entire in-game history is zero points. It is a **per-player-row** fact. *(`METRIC.md` Appendix A.4
  flags itself as the one measurement in that appendix not independently re-verified in its pass.)*
- **The regret distribution.** §0.1 adopts P3 as a companion to P1, and `METRIC.md` §1 records that P3
  is the count and size of the worst weeks per ranker rather than a central tendency. A distribution is
  not derivable from a mean.

A fourth follows from the secondary objective: **§4.4's ordering regret is a per-ordering fact**, and
§4.6's B2 is a comparison *between* orderings at one squad-week. Neither is expressible at any of the
grains above.

So the artefact is written at **four grains** — per player, per squad-week, per squad-week-ordering,
per comparison — and the atomic one is per-player. A schema storing only means and intervals would
force the results document to re-run the harness to say anything about the findings above, which is the
exact failure this section exists to prevent.

### 7.2 The tables

*Numbered by order of introduction, not by reading order. T5 was added after the first four and is
presented below between T3 and T4, because T4 is the manifest and reads last. "T1–T5" is already the
settled name for the set, so the ordinal is left as it is.*

**T1 — `selections`. One row per (run, squad, gameweek, ranker, player).** The atomic table.

`run_id, squad_id, gw, ranker, player_id, position, score, rank, is_unrankable, no_fixture,
selected, bench_slot, entered_as_sub, minutes_recorded, points`

This is what makes the three findings representable: the **GW4 degeneracy** is score equality between
two rankers at `gw = 4`; the **agreement rate** is the same equality over `gw ≥ 5`, with "zero-history"
readable off F2's own score being 0; the **regret distribution** comes from T2, which T1 reconstructs
and audits. The auto-substitution trace (`entered_as_sub`, `bench_slot`, `minutes_recorded`) makes
§4.3's replay re-checkable without re-running it.

**Size, since per-player grain invites the objection.** 300 squads × 15 players × 35 gameweeks × 4
rankers ≈ **630,000 rows** — single-digit megabytes in parquet.

**§0.16's move to weekly resampling does not change this count, and the old affordability argument was
the wrong one anyway.** The count is unchanged because T1's grain is the *squad-week*, and weekly
resampling redistributes squads across weeks without changing how many squad-weeks there are: 300
squads held for 35 weeks and 300 fresh squads in each of 35 weeks both yield 10,500 squad-weeks. What
grows is the number of **distinct squads**, 300 → 11,100 over GW2–38, and therefore the squad table
itself, from 4,500 rows to 166,500 — still trivially small, and not a table T1's size argument was
ever about. The rationale previously given here — that it is affordable *because* squads are built
once and held — is withdrawn: it did not support the number it was attached to, since the row count
never depended on squad reuse. The correct statement is simply that 630,000 rows at single-digit
megabytes is affordable on its face, for a small number of one-off runs rather than an artefact that
accumulates weekly. Under the previous construction the withdrawn rationale happened to reach the
right conclusion, which is why it survived unexamined.

**T2 — `squad_weeks`. One row per (run, squad, gameweek, ranker).**

`run_id, squad_id, gw, ranker, chosen_xi_points, best_legal_xi_points, second_best_xi_points,
regret, closeness_gap, is_zero_gap, substitution_fired, uncovered_blank, no_fixture_rule_changed_xi`

This is the level P1's quantities are computed at and the level §0.8's zero-gap exclusions are applied
at. `closeness_gap` is C1 — the gap between the best and second-best legal XI totals — which is why
both totals are stored rather than only the maximum. **Both XI totals are stored, not just their
difference**: see §7.6.

**Every figure in T2 is the *primary* ordering's.** §5.4 makes `bench_order` an ordered sequence with
element 0 the primary, and §4.9 established that `regret` depends on which ordering produced it. T2
carries element 0's replay and no other; the alternatives live in T5. The manifest names element 0
explicitly (§7.3) so the attribution does not rest on positional convention alone.

**T3 — `comparisons`. One row per (run, comparison).**

`run_id, comparison_id, rankers, window_first_gw, window_last_gw, n_scoreable_gw, floor_ranker,
floor_mean_regret, candidate_mean_regret, abs_reduction, rel_reduction, ci_squads_lo/hi,
ci_gw_lo/hi, crit_direction, crit_significance, crit_materiality, passed, status, status_reason,
n_zero_gap_excluded, substitution_count, uncovered_blank_count, ordering_relevant_count,
no_fixture_rule_count`

**T3 is stored rather than derived, and the reason is specific.** Mean regret is derivable from T2;
**the intervals are not** — they are resampled and seed-dependent, so re-deriving them without the run's
seed would produce different numbers. Persisting them while keeping their inputs in T2 is what makes
them auditable rather than merely reported.

§0.14 requires **two** intervals reported as two — hence two column pairs — and §0.15 requires the
absolute magnitude alongside the relative, hence both reductions. `crit_significance` is satisfied only
when **both** pairs exclude zero (§0.15).

**T5 — `ordering_replays`. One row per (run, squad, gameweek, ranker, ordering).**

`run_id, squad_id, gw, ranker, ordering_name, is_primary, substitution_fired, realised_total,
entered_gk, entered_outfield`

**The key includes `ranker`, and the obvious four-part key is wrong.** `(run, squad, gw,
ordering_name)` is the natural-looking key and it does not survive §4.4: bench-order evaluation is
**conditioned on a fixed XI**, the bench is the *complement* of the XI within the 15, and the XI is the
ranker's. Two rankers at the same squad-week have **different bench sets**, so a key without `ranker`
would collapse replays of different benches into one cell and silently compare selections while
appearing to compare orderings.

**A new table rather than columns on T2.** The policy set is a **runtime argument of variable length**
(§5.4), so a wide layout would need one column per policy and could not be schematised ahead of the
run. A new grain also keeps T2 at one row per squad-week, which is the grain P1's distribution and
§0.8's exclusions are defined at.

**`entered_gk` and `entered_outfield` are separate**, and that is not cosmetic: §4.2 establishes the GK
ordering is degenerate, so **no two policies can differ on it**. Splitting the column makes that
degeneracy auditable rather than assumed, and it means a squad-week where only a GK substitution fired
is visibly a member of B1 that can never be ordering-relevant.

**Size:** 300 squads per gameweek × 35 gameweeks × 4 rankers × the policy count — roughly **126,000
rows** at three policies, unchanged by §0.16 for the reason T1's count is (T5's grain is the
squad-week). T5 varies only in the substitution outcome, which is why it is a handful of fields rather
than a re-issue of T1's fifteen player rows per ordering.

**T4 — `manifest`. One row per run**, written as JSON rather than parquet because it is the thing a
human reads first and a reviewer diffs.

### 7.2.1 What T5 stores, and what is derived from it

The principle — persist what cannot be recomputed, derive the rest — decides each of these rather than
storing both.

| Quantity | Stored or derived | Why |
|---|---|---|
| Per-ordering `realised_total` | **Stored** | A §4.3 replay output. Deterministic, but re-deriving it means re-running the replay, which is what §7.1 forbids |
| Per-ordering entering players | **Stored** | Same, and §4.6 needs the *sets*, not the totals (below) |
| **Ordering regret** (§4.4) | **Derived** | `max(realised_total) − realised_total(σ)` within `(run, squad, gw, ranker)`. A group-max over stored values: deterministic, seed-free, one join |
| **Ordering-relevant flag** | **Derived** | `substitution_fired` **and** the `entered_outfield` sets are not all identical within the group |
| `ordering_relevant_count` in T3 | **Stored** | T3 is the report row: §0.11 requires both counts reported with every bench-order figure, and T3 denormalises what it is required to report. A derived quantity is computed **once, at assembly**, and written only where it must be reported |

**Relevance is defined on the entering *sets*, not on the totals, and storing only the totals would not
have been enough.** §4.6 counts squad-weeks "where the resulting sets of entering players are not all
identical". Two orderings can bring on **different** players who happen to score the same: the totals
match, the sets do not, and the week is ordering-relevant. Deriving relevance from equal totals would
silently undercount it.

### 7.3 What identifies a run

**`run_id` is a deterministic hash** of the identifying fields below. Deterministic so that re-running
identical inputs yields the same `run_id`.

| Field | Why it is identity, not metadata |
|---|---|
| **Mart pin** — content hash + row count + gameweek span (§5.3) | §2.8: rejection sampling consumes a **data-dependent** number of RNG draws, so the same seed against a different mart yields a **different squad set**. Seed alone does not identify the squads |
| **Bench ordering — the whole ordered policy set, with element 0 named as primary** | §4.9: the chosen XI is scored **after** substitutions fire, so primary regret is a function of element 0 and a regret figure without it is not reproducible. The **rest of the set is identity too**: §4.6 defines B2 over the orderings actually compared, so two runs sharing a primary but comparing different candidates produce different counts in T3 |
| **Window** — per comparison, in T3 | §0.13: the floor is determined on the intersection of **every** ranker in the comparison, candidate included, so the window is a property of the comparison and not of the run |
| **Floor ranker** — per comparison, in T3 | Same selection: the floor is **window-relative and re-determined per comparison**, so recording "the floor" once at run level would be wrong |
| **Master seed + squad-set id** | The squad set is drawn per gameweek (§0.16), so the id covers all 37 weeks' squads and the seed is the master seed §2.9's per-week streams derive from. Together they are what lets a later run assert it is replaying the same squads rather than new draws — and, because §2.9's derivation is order-independent, what lets a partial rebuild be checked week by week |
| **The build gameweek set** | Weekly resampling makes the set of build weeks a property of the run rather than a constant. Two runs over the same window but different build weeks — a re-run after §0.7's scope moved — produce different squads at the same `gw`, and nothing else in this table would distinguish them |

The manifest also carries, for completeness rather than identity: each ranker's **declared** window
(§6.3), the sampler's acceptance diagnostics (§2.6), and the bootstrap parameters actually passed —
**recorded per interval, because there are two sets and they differ**. The gameweek interval carries
`n`, `block`, `ci_level`, `seed` (§8.2); the squad interval carries `n`, `ci_level`, `seed` and **no**
`block`, squads being unordered (§10.1). Recording one merged set would leave a reader unable to tell
which parameters produced which of T3's two column pairs.

### 7.4 Where it is written, and what is frozen

**`decisions/starting_xi/results/`** — T1–T3 and T5 as parquet, T4 as JSON. This follows
`decisions/README.md`: the decision statement, its metric, its harness, its baselines and its frozen
results live together.

**Separately: `decisions/starting_xi/PRE_REGISTRATION.yaml`, pinned by a freeze test.**
`INVENTORY.md` §2.9 surveys the repository's five result-writing surfaces and states that none of them
is a convention for "a harness result read back programmatically", while identifying the
`evidence.yaml` + freeze-test pattern as the only one of the five whose values a test pins so that a
later run which moves them fails. §0.15 adopts it as the mechanism that makes pre-registration
enforceable rather than aspirational.

**What is frozen is the pre-registration, not the results.** Results legitimately change when the mart
is rebuilt; the *parameters fixed before the first run* must not. So the frozen file carries: the three
naive rankers and their declared windows, `n = 10000`, `block = 4`, the 10% materiality threshold, the
requirement that both intervals exclude zero, the three success criteria, the squad count of **300 per
gameweek**, the build gameweek set (GW2–38), the **resampling scheme** — weekly resampling, and U1
stratified by gameweek (§10.3) — the master seed, and the bench ordering. A test pins those values.

**The scheme is in the frozen file, and that is a consequence of this pass rather than a tidy-up.**
Under build-once the construction was a constant and needed no pinning. It is now a **choice** that
a later run could silently reverse — build-once and weekly resampling produce artefacts of identical
shape and identical row counts (§7.2), differing only in whether `squad_id` recurs across `gw`. That
is precisely the kind of difference a freeze test exists to catch, and it would otherwise be
detectable only by inspecting the squad table. Freezing the *results* instead would fail on
every legitimate re-run and teach the team to regenerate the fixture, which is how freeze tests die.

### 7.5 What a run emits when the comparison cannot be run

**A row is always written. Absence is never the signal.** §6.3 defines two cases and T3 carries them in
`status`:

| `status` | When | What is written |
|---|---|---|
| `evaluated` | Normal | All fields populated |
| `underpowered` | Fewer than four scoreable gameweeks — below one bootstrap block, so §0.15's S2 cannot be evaluated (§6.3) | Point estimates and counts populated; intervals null; `crit_significance` null, **not** false; `passed` null |
| `not_evaluable` | Empty window intersection | Identity, rankers and window populated; every estimate null |

**Null is not false.** A comparison that could not be evaluated must not read as one that failed —
§0.15's bar is all three conditions, and a null criterion is not a failed one. Omitting the row entirely
would be worse still: it would make "not evaluable" indistinguishable from "never run".

**The same rule governs T5's degenerate cases**, which §4.8 defines and which the artefact must be able
to tell apart. T5 is a harness output rather than a comparison output, so its rows exist whatever a
comparison's `status` turns out to be.

| §4.8 case | What T5 holds | What derives from it |
|---|---|---|
| **No substitution fires** | One row per policy, all with `substitution_fired = false`, `realised_total` identical across them, both entered fields empty | **Ordering regret is undefined, not zero.** The derivation in §7.2.1 is gated on `substitution_fired`, so these rows yield null rather than 0. Not ordering-relevant |
| **A substitution fires; every policy brings on the same player** | One row per policy, `substitution_fired = true`, identical `entered_outfield` | Ordering regret derives to **0 and is defined** — genuinely 0, because the orderings were indistinguishable. **Not ordering-relevant**, so excluded from the denominator that carries any bench-order claim (§4.7) |
| **A substitution fires; policies differ** | One row per policy, differing `entered_outfield` | Ordering regret ≥ 0, ordering-relevant true. These weeks are the entire evidence base for the secondary decision |
| **GK-only substitution** (§4.2) | `entered_gk` populated and identical across policies; `entered_outfield` empty | In B1, and **never** ordering-relevant, since relevance compares `entered_outfield` only. The degeneracy is visible in the artefact rather than argued from the text |

**The discriminator is `substitution_fired`, not an empty entered-set.** A week where no substitution
fired and a week where one fired but brought on nobody legal — §4.6's uncovered blank — both leave the
entered fields empty. Only the flag separates "the ordering was never live" from "the ordering was live
and the bench could not cover it", and §4.8 gives those two cases different treatments.

### 7.6 Two things stored defensively, and why

**This section applies a different rule from §7.2.1, and the difference is deliberate.** §7.2.1 governs
quantities whose definition is **settled**: those are computed once at assembly and written only where
they must be reported, because a second copy of a defined quantity can only diverge from the first.
§7.6 governs **inputs to a quantity that is not yet defined**. There is no duplication to avoid, and
the cost of *not* storing them is a re-run of the harness once the definition lands — the failure §7.1
exists to prevent.

**Both XI totals, not just regret.** §0.1 adopts P4 as required and records that `METRIC.md` §1 leaves
its form undefined — signed error cannot be regret, which is non-negative, and nothing in this folder
says what quantity is signed or against what reference. Rather than invent a definition, T2 stores
`chosen_xi_points` and `best_legal_xi_points` separately so that whatever definition is eventually
fixed is derivable from the artefact without a re-run. Neither is recoverable from `regret` alone,
which is their difference. Flagged at §7.9.

**`no_fixture_rule_changed_xi` at squad-week grain.** §0.4 requires the per-ranker count of squad-weeks
in which the rank-last rule changed the selected XI. It is stored per row rather than as a total so the
count can be cut by gameweek and by ranker — the form in which it is actually informative, since it is
the size of the confound the rejected options would have carried.

### 7.7 Bench-order liveness is bounded below by design, and the artefact says so

B1 and B2 are reported in T3. **Both carry a caveat that belongs beside the number, not in a footnote
elsewhere**, and `METRIC.md` §4.2 states it directly: neither count is purely empirical.

**Auditing either count is one hop further than T3 suggests.** B1 aggregates T2's `substitution_fired`;
B2 is **derived from T5**, by comparing each squad-week's `entered_outfield` sets across orderings
(§7.2.1). T3 carries them because §0.11 requires both reported with every bench-order figure, not
because T3 is where they are computed.

Two design choices push B2 down before any football happens:

1. **§0.4's no-fixture rank-last rule** reduces B1 *by construction* — no-fixture players are ranked
   last, so they are rarely started, so they rarely fire the substitution the rule describes.
   `METRIC.md` §2.3 names this cost when characterising the option. The reduction is bounded by the
   no-fixture share: substitutions from `minutes = 0` players, who had a fixture and did not feature,
   are unaffected.
2. **§4.6 defines B2 over the orderings *actually compared***, not over all six permutations —
   deliberately, as the honest denominator, and necessarily smaller.

**So a low count is not purely a finding about football.** The artefact therefore stores both counts
alongside `no_fixture_rule_count`, so a reader can see how much of the narrowing was design and how
much was the season.

### 7.8 The results module

`results.py`'s row is carried in §5.1's table. It is **Tier A**: it serialises frames it is handed and
reads no data of its own, so it needs neither `dal/` nor `model/`.

### 7.9 What §7 does not decide

- **The `points_roll3` governance verdict** — §9.1.
- **The definition of P4's signed directional error** — §7.6 stores its inputs; §0.1 records that
  defining it is a `METRIC.md` question and `METRIC.md` §1 records the same gap from the survey side.
- **Whether results are committed or git-ignored.** `INVENTORY.md` §2.9 records that `research/runs/`
  is git-ignored while `outputs/` and `docs/studies/results/*.md` are not. The artefact is small and
  one-off, which argues for committing it, but the repository has no single convention and this slice
  should not invent one unilaterally.

---

## 8. Reuse and call-site specifics

Consolidating what the slice reuses and on what terms, so Phase 3 does not rediscover it. Every fact
below is `INVENTORY.md`'s; this section states what the design does with it.

### 8.1 What is reused, and what is deliberately not

**`expanding_prior_mean` (`model/eval/baselines.py:58`) is used, called directly on the harness
population (§8.3).** `INVENTORY.md` §2.1 records it as a one-argument `groupby.transform` importing
only `pandas`, with `shift(1)` before `expanding()` and no population of its own — its meaning follows
the rows passed. That last property is precisely what makes it reusable here, since §0.9 fixes a
population no wrapper in the repository supplies.

**`build_baseline_features` (`model/eval/baselines.py:31`) is not used, and must not be.**
`INVENTORY.md` §2.1 records its filter, `(mart["minutes"] > 0) & (~mart["is_dgw"])`, and states
directly that it drops rows for a player with no fixture. §0.4 keeps such a player legal to select and
scored at 0, so the filter would silently change the feasible formation set and make the counterfactual
easier than the real decision.

**`add_lagged_rolls` (`model/features/build.py:37`) is used for F3, with an assertion.** Called as
`add_lagged_rolls(pop, sources=["total_points"], windows=(3,))` at `min_periods = 1` per §6.4, with the
no-nulls assertion of §8.3 immediately before the call.

**`block_bootstrap_ci` at `model/eval/metrics.py:79` supplies the gameweek interval**, with every
argument passed explicitly: `block=4, n=10000, ci_level=0.95, seed=0` (§8.2). Its counterpart at
`research/kernels/inferential/resampling.py:224` is **unreachable** under §3's contract, and §8.2
records that it would also have lost on merit.

**`assert_no_future_leakage` (`research/kernels/evaluation.py:46`) is not adopted.** `INVENTORY.md`
§5.7 records, verified by execution, that it requires `points_roll3` — which the governed mart
excludes — so it raises on the first evaluated gameweek, and that its own remediation message names the
source the failing call already used. A ranker needing a leakage assertion writes one against the
columns it actually uses (§6.2).

**`regret` at `model/eval/decision/metrics.py:20` is not imported.** `INVENTORY.md` §2.4 records it as
a **name collision**: best-scoring-player-in-the-league minus your single pick, at per-player top-1
grain, against P1's best-legal-XI minus chosen-XI at squad-week grain within one 15. The word
transfers; the code does not.

**`PlayModel` / `PlayTerm` (`model/terms/p_play/p_play.py:40`, `:83`) are used as F1.**
`INVENTORY.md` §2.6 records that `model/terms/_binary_component.py:144` is the shared base-class
walk-forward loop rather than `p_play`'s own implementation, and it should not be cited as the latter
(§3.4).

**`domain/fpl_squad.py` is a new file** (§3.5), carrying the quota, the per-position XI bounds, the 8
legal formations and the 100.0 cap, sourced from `element_types` with a drift test rather than
hardcoded in the slice. `INVENTORY.md` §2.2 records that no such file exists today and that these
constants never reach the mart.

**`np.random.default_rng(seed)` is the convention**, which `INVENTORY.md` §2.8 records as uniform
across the repository. The seed is a required argument with no default (§2.9), fixed at 0 at every call
site (§8.4).

### 8.2 The `block_bootstrap_ci` call site — settled by the import contract, and confirmed on merit

**Under §3 as written, `decisions/` may not import `research/kernels`** — and this is a reading of the
contract rather than a new decision. §3.3 defines the two tiers exhaustively: Tier A may not import
`model/`, `research/`, `serve/` or `operational/`, and Tier B's permitted list — `model/`, `dal/`,
`domain/` — does not contain `research/`. Neither tier admits it. §3.9 records why the exclusion is
deliberate rather than an oversight.

**`uncertainty.py` is therefore Tier B**: Tier A would forbid `model/` too and leave it unable to reach
*either* implementation, and §3.3 forbids leaving a module unclassified. Tier B may not be imported by
Tier A, which is consistent with §3.11 and §5.5 — the bootstrap cannot live in `harness.py`. The
composition root imports `harness.py`, `rankers.py` and `uncertainty.py` and wires them together.

**The contract is not widened to reach the kernels implementation.** §2.9 set the precedent: had a
method required widening §3's contract, that would have been a reason to reconsider the method, not the
contract.

**On merit it lands the same way, which is worth recording so the choice does not rest on the contract
alone.** §0.14 fixes `n = 10,000`, and `INVENTORY.md` §2.9 records both implementations taking the
count as an argument (defaults 1000 and 3000), so the resample count is a call-site argument either way
and cannot decide it. What decides it is `INVENTORY.md` §2.9's rounding row: the kernels implementation
returns through `_percentile_ci`, which **rounds both endpoints to 4 decimal places**, while
`model/eval/metrics.py:79` applies **no rounding** and takes its block from the named `BLOCK_GWS`.
§0.15's S2 is a **boundary test** — does the interval exclude zero — and rounding an endpoint can move
a genuinely non-zero bound onto exactly 0. A rounding step that can flip the significance verdict is
the wrong primitive for a criterion defined by whether a bound crosses zero.

**Every argument is passed explicitly**, including `block=4` and `ci_level=0.95`. `METRIC.md` §6.2
gives the reason for `n` — a count acquired by import path is acquired by accident — and it applies
unchanged to the block length and the coverage. Passing `block=4` records the value `INVENTORY.md` §2.9
shows both implementations already use; it fixes nothing new.

**One thing this does not settle.** `INVENTORY.md` §2.9 records that resampling **squads** needs a
*cluster* bootstrap of a mean, that the repository's one cluster resampler is hard-wired to the
rho / partial-rho statistic, and that there is **no generic cluster-bootstrap-of-a-mean** — nor, as
§10.3 now needs instead, any gameweek-stratified bootstrap of one. This section
fixes the **gameweek** interval's call site only. The squad interval is a build, designed at §10.

### 8.3 One population, two statistics — and the assertion that protects it

Both PPG rankers read the **same** frame: the full player-gameweek spine restricted to each player's
post-registration window, with null `total_points` filled to **0**. That is §0.9's denominator, and it
is the harness's own construction — `INVENTORY.md` §2.1 records that `expanding_prior_mean` carries no
population of its own and that its meaning follows the rows passed.

**This is also *why* the two are identical through GW4** (`METRIC.md` §5.3, Appendix A.3): they are two
windows over one population, and while a player has three or fewer prior in-game gameweeks the shorter
window covers all of them.

**The assertion.** A pandas rolling mean skips NaN rather than treating it as 0, so a frame whose blanks
were left null would produce an **appearance-denominated** statistic — the quantity §0.9 rejects, and
one that would look entirely plausible in the output. The precondition is invisible at the call site,
so it is asserted at the call site: **`total_points` has no nulls across the population, immediately
before the call.** Without it, the reuse is a silent-wrong-answer risk rather than a saving.

*One supporting detail this document does not assert first-hand: whether `add_lagged_rolls` coerces its
source in a way that converts non-numeric entries to NaN. `INVENTORY.md` does not record it, and the
assertion above does not depend on it — a no-nulls precondition is required regardless. Flagged at §11.*

### 8.4 Two conventions this section fixes because they were left dangling

**The seed constant: `0`.** `INVENTORY.md` §2.8 records two competing conventions —
`BOOTSTRAP_SEED = 0` at `research/kernels/inferential/resampling.py:20–22` and a local `42` in the four
family studies — and states that which one a caller gets depends on which module it imports from. §2.9
required the sampler's seed be an explicit argument with no default and left the *choice of constant*
to the call site. It is fixed here: **`seed = 0` at every call site in the slice**, recorded in the
pre-registration (§7.4). The value matters less than that it is passed explicitly and frozen once.

**The position vocabulary: `position`.** `INVENTORY.md` §2.12 records three position columns on the
mart — `position` (GK/DEF/MID/FWD), `position_label` (GKP/DEF/MID/FWD) and `position_code` (1–4) —
differing only at goalkeeper, with `position_label` the canonical name in the staging contract and the
one `serve/` and the research families key on, while `model/terms/_binary_component.py` fits per
`position`. **The slice uses `position` throughout**, because it is the vocabulary the F1 ranker's own
fit uses and therefore the one that needs no translation at the ranker boundary; a translation there
would be a per-row transformation on the hot path of the only expensive ranker, for no gain. Any
`position_label` value entering from elsewhere is normalised at the harness boundary.
`INVENTORY.md` §2.12 records that GKP→GK normalisation is already tested as intended behaviour
elsewhere in the repository, so the direction chosen here is the established one.

### 8.5 What §8 does not decide

- **The `points_roll3` governance verdict** — §9.1. If it binds, F3 does not exist in its present form
  and the `add_lagged_rolls` reuse is moot rather than wrong.
- **The squad-level interval** — a build, not a reuse; designed at §10. It is a bootstrap stratified by gameweek (§10.3), not the cluster bootstrap an earlier pass planned, because §0.16's weekly resampling leaves the panel with no clusters to draw.

---

## 9. Open items

### 9.1 The `points_roll3` governance verdict — blocking slice Phase 4

`INVENTORY.md` §2.1 records that `total_points` is excluded from the feat layer's `_ROLL_COLS` by lens
decision (`dal/feat/feat_player_gameweek.py:16–22`, "removed by lens evaluation (evaluation_circularity
or G2-FAIL)"), verified against the mart's 64 columns. `METRIC.md` §5.2 states what is actually
unsettled — not the absence but its **scope**, whether the exclusion binds a *baseline ranker* as well
as a governed signal — and names both what settles it (the lens record behind the annotation) and where
the answer belongs (`research/families/form/validate/evidence.yaml`).

Whichever way it lands, it governs whether F3 exists (§0.12). `INVENTORY.md` §3.7 records the same
divergence from the other side: `assert_no_future_leakage` requires the column the mart excludes, so the
guard and the mart contract cannot both stay as they are. Carried forward unresolved; blocks Phase 4.

### 9.2 No candidate bench-order scoring rule has been characterised

`METRIC.md` §4.1 records that no candidate rule exists in this folder and flags it as the survey's
largest gap. §0.10 states the consequence for this document: §4.4's ordering regret is a construction
rather than a selection, and has not been shown better than any alternative because no alternative has
been characterised. Resolving it is a `METRIC.md` pass, not a `DESIGN.md` one. §4.11's open question —
how uncertainty is quantified on the ordering sample — belongs with it.

---

## 10. The squad-level interval

§0.14 selects U1 alongside U2, and requires U1 be computed as a bootstrap **stratified by gameweek**
over §0.16's weekly-resampled panel. `INVENTORY.md` §2.9 records that the repository has no generic
cluster-bootstrap-of-a-mean; it has no gameweek-stratified bootstrap of a mean either. This section
builds it.

### 10.1 The resample count and the absent block parameter

**`n = 10,000` governs both intervals**, selected at §0.14 with `METRIC.md` §6.2's reasoning, and
`ci_level = 0.95`, `seed = 0` follow §8.4. `METRIC.md` §6.2 also records that the published-output
constraint on the existing implementations does not bind a new measurement, so a newly built estimator
inherits nothing.

**The squad interval takes no `block` parameter**, and that is the one genuine difference: blocking
exists to respect autocorrelation between *consecutive gameweeks*. Within a stratum the squads have
no order — they are independent uniform draws from F_g (§2) — so there is nothing for a block to
preserve. Across strata the gameweeks are ordered and autocorrelated, but U1 does not resample across
strata: the gameweek margin is held fixed (§10.3), which is a stronger treatment of that
autocorrelation than blocking, because it does not resample the dimension at all. U2 is where the
gameweek dimension is resampled, and that is where `block = 4` lives.

### 10.2 The estimand

The quantity is the **paired difference in mean regret** between two rankers over one comparison
window, after §0.8's zero-gap exclusions.

§0.14 selects the **grand mean over surviving squad-weeks** rather than the unweighted mean of per-week
means. Under §0.16's weekly resampling the alternative reading is a per-*gameweek* one, not a per-squad
one — each squad has exactly one week, so a per-squad mean is the row itself and the two readings would
be trivially identical. The live distinction is between the grand mean and the unweighted mean of
per-gameweek means, and they coincide only when every gameweek has the same number of surviving rows.
§0.8's zero-gap exclusions remove squad-weeks unevenly across weeks, so the strata are **unbalanced**
and the readings differ. The grand mean weights a gameweek by how many of its squads survived, which is
the reading §0.14's argument selects: it is a per-squad-week cost, and a week that contributed fewer
decisions should carry proportionately less of the average. That is the per-squad-week cost §0.15's
materiality threshold and its absolute companion figure are expressed in, and it is how `DECISION.md`
§1 frames regret — the cost of a weekly decision.

### 10.3 The resampling unit

**"A cluster is a squad" no longer applies, and the reason is structural rather than a change of
mind.** That rule earned its place because a held squad contributed one row per gameweek, 35 or so
dependent rows tied together by the composition of one 15. Under §0.16 a squad exists in exactly one
gameweek and contributes **exactly one row**. A rule that groups rows by squad now produces 10,500
groups of size one, and grouping by a key that is unique per row is not a cluster bootstrap — it is a
row bootstrap wearing the vocabulary of one. The rule has to be rederived, not reworded.

**Derive it from what was actually sampled.** `METRIC.md` §6.2 fixes U1's question: sensitivity to
which squads were drawn, with the gameweek set held fixed. So the derivation asks two things — what
was drawn, and what was not.

*What was drawn.* At each gameweek *g*, §2 draws 300 squads independently and uniformly from F_g.
That draw is the sampling variability the construction introduces, and it is the object U1 must
resample. Each drawn squad becomes one surviving squad-week row (or none, if §0.8 excludes it), so
**the unit resampled is the squad-week, and this time that is not a proxy for anything** — a
squad-week *is* one realised draw.

*What was not drawn.* The gameweek set is not a draw at all under U1's question; §6.2 says U1 holds
it fixed and U2 is where it varies. And within a gameweek, the 300 squad-weeks share that week's
realised fixtures, opponents and player performances, so they are **not** independent of one another
in the unconditional sense.

**Both facts point at the same estimator: resample squad-weeks with replacement, independently within
each gameweek, holding each gameweek's row count fixed.** One replicate draws, for every gameweek *g*
in the window, `n_g` squad-week rows uniformly with replacement from that gameweek's surviving rows,
where `n_g` is the number of surviving rows that gameweek actually has. The replicate is the union
across gameweeks; the statistic is the grand mean over it (§10.2). A row drawn twice counts twice.

**Why this is valid, stated as the two conditions it turns on.** A bootstrap is valid when it
resamples exchangeable units from the distribution that generated them. Within a stratum both hold:
the 300 squads at gameweek *g* are i.i.d. draws from a single distribution (uniform on F_g, §2.1), so
they are exchangeable **conditional on the gameweek**, and the empirical distribution of that week's
rows is the right thing to resample from. The week's shared realisation — its fixtures and results —
is a property of the stratum, not of the rows within it, and stratification conditions on it rather
than pretending it away.

**And why this is not the U3 error, which is the question this section exists to answer.** U3's
objection has two halves (§0.14). The first — the same squad recurring across every gameweek — is
**gone by construction**: §2.8 asserts that a `squad_id` appears at exactly one `gw`, so no unit is
double-counted across the panel. The second — the same gameweek recurring across every squad — is
**neutralised by the stratification rather than ignored**. A flat, unstratified row bootstrap over
all 10,500 rows would resample the gameweek composition as a side effect, treating each week as
though it contributed 300 independent draws to a season-level quantity; that is exactly U3, and it is
the error this design must not commit. Holding `n_g` fixed per stratum means **no replicate ever
changes which gameweeks are represented or in what proportion**, so the gameweek dimension
contributes no sampling variability to U1 at all. It is answered by U2 instead, which is the division
of labour §0.14 already selected.

**The distinction worth keeping in view.** Under build-once, 10,500 rows carried only 300 independent
squad draws, and the cluster bootstrap existed to stop the estimator from believing otherwise. Under
weekly resampling those 10,500 rows carry **10,500 independent squad draws** — 300 in each of 35
weeks, each an actual independent draw from its week's feasible set. The interval this estimator
produces will be narrower than the cluster bootstrap's, and that narrowing is **earned by extra
sampling rather than manufactured by a modelling assumption**. It is worth naming the resemblance to
U3's failure mode explicitly, because "the interval got narrower when we changed the resampling unit"
is the signature of exactly the error §0.14 rejects, and here the construction changed underneath it.

**Nothing is patterned on the existing cluster resampler any more.**
`INVENTORY.md` §2.9 identifies `research/kernels/inferential/resampling.py:252
cluster_bootstrap_minutes_adjusted_rho` as the repository's example of the cluster structure. Under
build-once that was the pattern to copy. It is no longer relevant: this estimator has no clusters to
resample. It remains **unreachable** in any case — §3.3 admits `research/` to neither tier (§8.2) —
so nothing is lost. The estimator below is written from the derivation above rather than from an
existing shape.

### 10.4 How the pairing survives — made structural, not disciplinary

**The estimator takes a panel that has *already* been differenced.** Its input is one value per
surviving squad-week:

```
d(s, gw) = regret_A(s, gw) − regret_B(s, gw)
```

computed once by the caller from T2, before any resampling. The estimator sees a single
`(gw, squad_id, value)` panel and never sees two rankers.

**This is what refutes `METRIC.md` §7.1's objection to weekly resampling**, and it is worth stating
here because this is where the argument lives rather than in §0.16 where the selection is recorded.
Pairing is the requirement that both rankers face the same squads in the same gameweeks. Weekly
resampling changes *which* squads are faced at each gameweek; it does not create a second draw. At
gameweek *g* the 300 squads are drawn once and every ranker is run on all of them, so `d(s, gw)` is
defined for every surviving squad-week under exactly the same conditions build-once provided. The
pairing is satisfied exactly.

**This is deliberately structural.** Resampling squads independently per ranker is not forbidden by
convention here; it is **unrepresentable**. There is only one series, so there is nothing that *could*
be drawn twice. A guardrail that depends on the implementer remembering to share an index vector is a
guardrail that will eventually fail; one that depends on there being only one vector will not.

**What breaking the pairing would have cost.** Two independent draws would estimate `var(A) + var(B)` in
place of `var(A − B) = var(A) + var(B) − 2·cov(A, B)`. The covariance is large and positive, because
squad depth is common to both rankers — `METRIC.md` §6.1's own point about the paired design. Dropping
the pairing puts that variation back in.

**The direction of that error is worth naming, because it is the opposite of the other one.** The point
estimate would be unchanged; only the interval would widen. So breaking the pairing is **conservative**
on §0.15's S2 — it loses real effects rather than manufacturing false ones — whereas the flattened
squad-week error `METRIC.md` §6.2 names under U3 manufactures precision. Two ways to get this wrong, in
opposite directions, and neither is detectable by inspecting the output interval alone.

**And this is why the loss of the cluster structure costs the pairing nothing.** The two are
independent properties: pairing is about the *columns* of the panel — one differenced series rather
than two — and the cluster structure was about its *rows*. §10.3 changes the rows. The differencing
above is unaffected, which is why §0.16's change lands in §10.3 and §10.5 and nowhere else in §10.

**Zero-gap exclusion does not disturb the pairing.** `METRIC.md` §3.1 records that closeness under C1 is
a property of the **squad-week**, not of the ranker, so zero-gap weeks are identical across rankers. The
same rows drop for both, `d(s, gw)` is defined on exactly the surviving set, and the panel stays
balanced *between rankers* even while unbalanced *across gameweeks* — §0.8's exclusions remove
different numbers of rows from different weeks, so `n_g` varies, which is why §10.3 takes each
stratum's row count from the data rather than assuming 300.

### 10.5 The estimator

```
squad_stratified_ci(panel, n=10000, ci_level=0.95, seed=0) -> (lo, hi)

  panel : rows of (gw, squad_id, value)  # value = d(s, gw), already differenced
                                         # exactly one row per (gw, squad_id)
  strata = group panel rows by gw
  rng    = np.random.default_rng(seed)
  for b in 1..n:
      rows  = for each gw: rng.choice(strata[gw].value, size=len(strata[gw]),
                                      replace=True)          # n_g fixed per stratum
      Δ*_b  = mean(concatenate(rows))                        # grand mean, per §10.2
  return percentile(Δ*, 100·α/2), percentile(Δ*, 100·(1−α/2))
```

**`size=len(strata[gw])` is the whole of the stratification**, and it is the line that would be wrong
if written as `size=n_squads` or if the loop were dropped in favour of one draw over the flat panel.
The first would rebalance the panel §10.4 establishes is unbalanced across weeks; the second is U3.

**`squad_id` is carried but not drawn on.** The estimator resamples values within a stratum and never
needs the id, because §2.8 guarantees one row per squad. It is in the signature so the function can
**assert** that guarantee — one row per `(gw, squad_id)` — rather than trusting the caller. A panel
that violates it is a build bug (§2.8) whose only symptom downstream would be a wrongly narrow
interval, so the assertion is where it is cheapest to catch.

**No rounding.** The interval is returned as raw floats. §8.2 rejected the `research/kernels`
implementation partly because `INVENTORY.md` §2.9 records `_percentile_ci` rounding endpoints to 4 dp
and §0.15's S2 is a boundary test on whether the interval excludes zero; a new estimator must not
reintroduce the defect the other one was rejected for.

**No minimum-stratum threshold, and the reason is upstream.** §6.3 gives the gameweek interval a hard
floor at four scoreable gameweeks — below one block. The squad interval needs no analogue: §0.16 fixes
300 squads **per gameweek**, so no stratum is thin unless §0.8's exclusions empty one, and an empty
stratum is simply a gameweek absent from the panel rather than a degenerate draw. A stratum reduced to
a handful of rows is possible in principle and needs no special handling — it contributes proportionate
weight to the grand mean and proportionate noise to the replicate, which is the correct behaviour.

**A test oracle falls out of the stratification.** When every stratum has the same row count, the
stratified draw and a flat draw over the pooled rows have the same expectation for the grand mean but
different variances — the stratified one is smaller by exactly the between-gameweek component, since
that component is held fixed. A balanced synthetic panel with a large, deliberately induced
between-gameweek offset therefore gives a closed comparison: the stratified interval must be **strictly
narrower** than a flat bootstrap on the same rows, and the gap must grow with the offset. This is a
sharper oracle than the one the cluster estimator had, because it tests the property the estimator
exists for rather than a case in which the estimator degenerates.

**A second oracle, for the single-stratum case.** With one gameweek in the window the stratified draw
*is* an ordinary bootstrap of a mean over that week's rows, which any reference implementation can be
checked against directly. §6.3's four-gameweek floor means no real comparison runs there, but the
degenerate case is the cheapest place to verify the percentile machinery.

### 10.6 Home, and why the two intervals cannot share a signature

**Both live in `uncertainty.py`, Tier B.** §8.2 placed that module in Tier B because the gameweek
interval needs `model/eval/metrics.py`. The squad estimator needs nothing from `model/` — it is `numpy`
and `pandas` — so it *could* have been Tier A.

**The cost of housing it in Tier B is real and is stated rather than waved past:** a Tier A module can
never call it (§3.3 forbids Tier A from importing Tier B). Nothing currently wants to — intervals are
computed after the harness, at the composition root — but if that changes, the squad estimator has to
move rather than the contract widening, on §2.9's precedent. The alternative, splitting the two halves
of one requirement across two modules so that one of them could be Tier A, buys a permission nothing
uses at the cost of a reader having to know which interval lives where.

**They genuinely cannot share one signature.** The two resample different objects: an **ordered** series
of gameweeks in blocks of 4, where adjacency is the whole point, versus a panel of **independent draws
within a fixed gameweek margin**, where adjacency is irrelevant and the margin is what must not move. A merged signature would carry a `block` meaningless to one caller and a
stratum key meaningless to the other — and, worse, would admit the call §0.14 rejects as U3: a
flattened squad-week series passed with neither parameter set, which would type-check and return a
confidently wrong interval.

**So the input shapes are deliberately non-interchangeable** — a 1-D ordered array versus a
three-column `(gw, squad_id, value)` panel — and the gameweek function additionally **asserts its input
length equals the comparison's scoreable-gameweek count**, which the caller already knows from T3. A
flattened panel has `n_squads × n_gw` entries and fails that assertion rather than silently producing a
number.

**Weekly resampling makes the squad estimator's own guard load-bearing in a way it was not before.**
Under build-once, dropping the `squad_id` column would have collapsed the panel into an unusable shape.
Under §10.3 the estimator's draw is *within* stratum, so a caller who passed the panel without `gw` —
or with a constant `gw` — would get a flat bootstrap that runs cleanly and returns a wrongly narrow
interval. The `gw` column is therefore required, not optional, and the estimator asserts that the panel
contains more than one distinct `gw` whenever the comparison window does (§10.7 supplies both).

### 10.7 What it consumes from the artefact — present at the grain needed

The estimator needs, per comparison: a paired difference per surviving squad-week, keyed by gameweek
and by squad.

| Needed | Source | Present |
|---|---|---|
| `regret` per (squad, gw, ranker) | §7.2, T2 `squad_weeks` | ✓ — that is T2's exact grain |
| The stratum key | T2 `gw` | ✓ — T2 is keyed on it |
| The one-row-per-squad guarantee | T2 `squad_id`, §2.8 | ✓ — asserted by the estimator (§10.5), not assumed |
| Zero-gap exclusion | T2 `is_zero_gap` | ✓ — and ranker-independent, per §10.4 |
| The comparison window | §7.2, T3 `window_first_gw` / `window_last_gw` | ✓ |
| Somewhere to persist the result | T3 `ci_squads_lo` / `ci_squads_hi` | ✓ |

**The differencing is the caller's step**, not the artefact's: pivot T2 on `ranker`, subtract, drop
zero-gap rows, restrict to the window. The pivot is unchanged by §0.16 — at each gameweek every ranker
faces the same 300 squads, so `(squad_id, gw)` still identifies a cell present for every ranker, which
is the same property build-once supplied and the concrete form of §10.4's pairing. Nothing needs storing at a finer grain than T2 already is, and T1
is not needed for this at all.

### 10.8 Pre-registration entry

Added to `PRE_REGISTRATION.yaml` (§7.4), pinned by the freeze test:

| Parameter | Gameweek interval | Squad interval |
|---|---|---|
| `n` | 10000 | 10000 |
| `ci_level` | 0.95 | 0.95 |
| `seed` | 0 | 0 |
| `block` | 4 | **n/a** — within a stratum the squads are unordered (§10.1) |
| Resampling unit | blocks of consecutive gameweeks | squad-weeks, drawn within gameweek |
| Stratification | **n/a** | by `gw`, each stratum's row count held fixed (§10.3) |
| Implementation | `model/eval/metrics.py:79` | built in `uncertainty.py` (§10.5) |

The stratification row is pinned for the reason §7.4 gives: it is the parameter that distinguishes
this estimator from the U3 error, and it is not recoverable from the output.

Both are required to exclude zero for §0.15's S2 to be satisfied.

### 10.9 What §10 does not decide

- **The `points_roll3` governance verdict** — §9.1.
- **P4's "mean signed directional error"** — §7.9.
- **Uncertainty on the bench-ordering sample** — §4.11, §9.2.

---

## 11. Facts this document needs that `INVENTORY.md` does not carry

Under the charter this document reads `INVENTORY.md` and never writes to it, so a fact it needs and
`INVENTORY.md` lacks is a gap requiring a separate `INVENTORY.md` pass — not something to assert
locally. Three such gaps now stand, all predating the weekly-resampling change. None changes a decision above.

1. **What the two `block_bootstrap_ci` implementations return for a series shorter than one block.**
   §6.3 sets the underpowered threshold at four scoreable gameweeks, which follows from `block = 4`
   regardless. Whether the estimators return `(nan, nan)`, raise, or produce a degenerate interval
   decides only whether the harness must guard the call. `INVENTORY.md` §2.9 characterises the two
   implementations but not this behaviour.
2. **Whether `add_lagged_rolls` coerces its source column in a way that maps non-numeric values to
   NaN.** §8.3's no-nulls assertion is required regardless — the failure it prevents is a rolling mean
   skipping NaN, which is pandas behaviour, not the helper's. `INVENTORY.md` §2.1 records the helper's
   `min_periods` and its `assert_lag_safe` guard but not its coercion.
3. **`PlayModel`'s construction-time configuration surface.** §6.1 states that the ranker interface
   accommodates a configured callable object as well as a plain function. That is a property of the
   interface, and it holds whether or not `PlayModel` takes constructor arguments; `INVENTORY.md` §2.6
   records the model's features, target and population but not its constructor.

A fourth item is a *documented* gap rather than a missing one: `METRIC.md` Appendix A holds four
repository measurements — the no-fixture blank gameweeks, the GW2 universe composition, and the two PPG
agreement measurements — which `METRIC.md` itself flags as belonging in `INVENTORY.md` under the
file-purpose charter. This document cites them to `METRIC.md` Appendix A because that is where they
currently live; if a later pass relocates them, §2.1, §0.16 and §7.1 are the citations to repoint.

**Two gaps opened by §0.16's weekly resampling are now closed**, by an `INVENTORY.md` pass, and are
recorded here as closed rather than removed so the routing stays legible.

- **The composition of the squad universe at each gameweek after GW2 — closed.** §0.16 builds squads
  at every gameweek and §2.1 defines the target on U_g, so each U_g's composition bears on §2.3's a
  priori acceptance-rate arguments, read against §2.6's per-week ladder 37 times rather than once.
  `INVENTORY.md` §2.5 now measures |U_g| and its position and club composition at all 38 gameweeks.
  §0.16 and §2.1 cite it.
- **What the 136 excluded players have in common beyond arriving late — closed, and it contradicted
  what this document had asserted.** `INVENTORY.md` §2.5 measures them as the less-played group on
  every measure taken. The claim §0.16 carried has been withdrawn there and at §2.2 in this pass;
  Provenance records the withdrawal.

---

## Provenance

**The policy this document operates under.** `DESIGN.md` **cites `INVENTORY.md` and never writes to
it** — not to add a fact, not to correct one. Where this document needs a repository fact
`INVENTORY.md` does not carry, that requires a separate `INVENTORY.md` pass first; it is not resolved
by asserting the fact here. §11 lists the open instances rather than filling them.

The same direction holds toward `METRIC.md` and `DECISION.md`: this document **selects from**
`METRIC.md`'s candidates (§0) and consumes `DECISION.md`'s framing, and where either leaves a gap the
gap is recorded and routed rather than closed locally — §0.10 and §9.2 for the bench-order scoring
rule, §0.1 and §7.9 for P4's undefined form.

**Two conflicts with `METRIC.md` were opened by §0.16's weekly resampling. Both are now closed.**
Under the charter this document selects from `METRIC.md` and never writes to it, so where this pass
found `METRIC.md` wrong the finding was recorded and routed rather than fixed. A `METRIC.md` pass has
since run and resolved both on that document's own terms. The entries are kept as a record of what
was routed and what came back, not as live items.

1. **`METRIC.md` §7.1's pairing sentence — resolved; withdrawn there.** It stated that "resampling per
   gameweek … breaks the pairing", which §10.4 refutes. `METRIC.md` §7.1 now records that **both**
   constructions satisfy §6.1's paired design, and that what distinguishes them is the dependence
   structure of the resulting panel — a §6.2 matter, not a §6.1 one. The withdrawal is recorded in
   `METRIC.md`'s Provenance with its reason. **The charter departure this entry previously recorded
   has ended**: there is no longer an upstream sentence this document declines to treat as governing,
   and §0.16's selection now rests on an upstream characterisation that agrees with it.

2. **`METRIC.md` §7.2's validity condition — resolved; restated there for a set of build weeks.** It
   was written for one build week and did not generalise to §0.16's construction. `METRIC.md` §7.2
   now states the condition per build gameweek — no registered player NULL throughout the prefix — of
   which the old form is the special case, and records that it is monotonically easier to satisfy as
   the prefix lengthens, so the earliest build weeks bind rather than GW31 and GW34. The
   `INVENTORY.md` gap this entry named is unchanged in substance and has been given a sharper form by
   that pass; it is carried at §11 rather than here.

**One claim of this document's own, withdrawn on measurement.** §0.16's superseded record and §2.2
both asserted that the 136 players excluded by a frozen GW2 universe skew toward **currently-active**
players, and so tilt the frozen pool along minutes-certainty in the direction that would corrupt a
ranker comparison. The assertion was made first-hand and was never measured — which is itself the
charter breach, since it is a repository fact and `INVENTORY.md` is its owner. `METRIC.md` Appendix
A.2 flagged the gap; an `INVENTORY.md` pass then measured it.

**The measurement contradicts the claim.** `INVENTORY.md` §2.5 records the 136 as the **less**-played
group: median 0 season minutes against 565 for the GW2 universe, 52.2% never playing against 33.0%,
31.6% ever recording 60 minutes against 59.1%, on rates computed over each player's own available
weeks. The sentence is withdrawn at both sites and replaced by what the measurement supports — that
the tilt exists but runs the other way, and that because over half the excluded players never played,
the exclusion sits nearer §2.2's generalisation-limiting category than its comparison-corrupting one.
Its materiality to a ranker comparison remains unmeasured and is not asserted.

**What this changes in the record, stated so it is not overread.** It weakens one of several
supporting arguments for §0.16's weekly resampling; it does not revisit the selection, and this pass
did not reopen it. The load-bearing justification is untouched: `METRIC.md` §7.1's pairing objection,
which is what build-once was selected on, is refuted at §10.4 and withdrawn in `METRIC.md`'s own
Provenance. The withdrawn claim is retained above rather than deleted so it is not re-proposed, per
the charter.

**One departure from `CLAUDE.md`, recorded rather than made silently.** *(This is the only standing
departure. The charter departure recorded under conflict 1 above ended when that conflict closed.)* `CLAUDE.md` requires every
design document to carry a capabilities table. This document does not carry one, because the
file-purpose charter governing this folder specifies that `DESIGN.md` is pure prose reasoning with no
label or verdict tables of its own. The two rules conflict; the charter is followed here and the
conflict is flagged for a human rather than resolved by this document.
