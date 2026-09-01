# METRIC.md — Free Hit Squad Construction & Selection

**Status:** Specification. One item below (§2) is a resolved decision, assigned to this document
explicitly by `DECISION.md` §4; everything else specifies measurement machinery without picking a
construction-candidate winner, without describing module interfaces, and without redesigning what
gets built. `DESIGN.md` comes after this document and is not read or anticipated here.

`DECISION.md` states what is being decided and why. `INVENTORY.md` records what exists in the
repository, facts only. This document restates neither in full — §0 below is a compact index of
what each is relied on for, not a substitute for reading them.

---

## 0. How to read this document

### 0.1 This document is not a survey, on one point

`decisions/starting_xi/METRIC.md` is written as a survey that recommends nothing (its own §0.1).
This document follows that convention everywhere **except §2**: `DECISION.md` §4 names the
naive-baseline verdict rule as the one item it deliberately leaves for METRIC.md to decide, not
merely characterise. §2 therefore contains an actual decision, argued and justified, in a document
that otherwise only specifies how measurement works. That asymmetry is stated here so it isn't
mistaken for house-style drift.

### 0.2 Tiering convention

Three tiers, not two, because `INVENTORY.md` resolved one question to a confirmed *absence* rather
than an open unknown:

- **Feasible now** — every input is confirmed present on the mart, confirmed derivable from the
  mart by a cited existing repository pattern, or confirmed to be an existing, already-proven
  routine (`DECISION.md` §4's "unchanged... reused identically" selection+bench layer). Code that
  must still be written does not move an item out of this tier, following
  `decisions/starting_xi/METRIC.md` §0.2's reading: tier on inputs, not on whether the code exists.
- **Open / DESIGN.md's call** — `INVENTORY.md` confirms the fact is currently undetermined by the
  repository (e.g. which DGW/BGW definition governs the evaluation set) and says so itself. Not a
  defect in either document; a question neither is positioned to close.
- **Infeasible under current data** — `INVENTORY.md` checked and confirmed an absence at every
  layer it inspected (only one case below: team-value-by-GW data). This is stronger than
  "speculative": nothing left to check would change the answer without new ingestion work.

### 0.3 What this document does not contain

No candidate-scoring formula for a forecasting/ILP construction candidate, no naive-baseline
winner, no legality-primitive design, no module or file placement, no import strategy. Those are
named in `DECISION.md`/`INVENTORY.md` as open and stay open here.

---

## 1. The three regret definitions

`DECISION.md` §4 sketches three quantities as forward pointers to this document, not as finished
formulas. This section operationalises each one precisely enough to compute by hand from mart data
and the (existing, unchanged) starting_xi selection+bench harness — and states one place where the
two source documents leave a genuine gap between "Construction regret" and "Combined regret,"
resolved here as an explicit interpretive choice rather than silently assumed.

### 1.1 Common notation

For a target gameweek `g` and a 15-player squad `S` (legal under §4 below's constraints):

- `Harness(S, g)` — the realized total points `S` actually returns at gameweek `g` when passed,
  unmodified, through the existing starting_xi selection+bench routine: it picks a legal XI using
  that routine's own (as-of, not hindsight) ranking, orders the bench, and applies the real
  auto-substitution outcome using `g`'s actual realized per-player minutes and points. This is the
  "standard harness" `DECISION.md` §1 and §4 both name as reused unchanged.
- `Oracle(S, g)` — the best realized total any legal XI-plus-bench-order drawn from `S` could have
  returned at gameweek `g`, computed with full hindsight over realized points and minutes (the same
  counterfactual-maximisation construction as starting_xi's P1, generalised to the bundled
  selection+bench unit `DECISION.md` §4 describes and cites at 0.108–0.116 pts/GW).

Both quantities require nothing beyond realized per-player-gameweek points/minutes and the existing
selection+bench routine — no construction-candidate code is a dependency of either definition.

**A naming distinction worth stating explicitly, to avoid it being misread.** `Oracle(S, g)` above
is an oracle over which *legal XI* to draw **from an already-fixed `S`** — it is starting_xi's own
P1 construct, already in scope and already reused per `DECISION.md` §4. It is not, and must not be
read as, the **global-oracle construction** benchmark `DECISION.md` §4 and §5 both defer (the best
possible *15*, over the full player pool, with full hindsight). That benchmark — an oracle over
which squad to build, not which XI to select from a given one — remains untouched and out of scope
here; nothing in this document scores against it.

### 1.2 Selection regret — a per-squad quantity, not a candidate-vs-baseline one

```
SelectionRegret(S, g) = Oracle(S, g) − Harness(S, g)
```

Computed identically for the candidate's own constructed 15 and for each baseline's own constructed
15, at every gameweek — four separate time series (candidate, and one per naive baseline), not a
single number and not a comparison between them. This is the direct, unmodified port `DECISION.md`
§4 names: "applies within any given 15 regardless of who built it."

**Properties.**

- Bounded below at 0 for the same structural reason as starting_xi's P1: `Harness` selects from
  exactly the set `Oracle` maximises over.
- It is **not** re-derived here as a new study. `DECISION.md` §4 cites 0.108–0.116 pts/GW as the
  existing, already-measured value from starting_xi's own dataset. That figure is imported as
  context for what magnitude to expect, not asserted as a transferable constant: starting_xi's
  figure was measured over randomly-sampled squads (`INVENTORY.md` §3's description of
  `sampler.py`'s whole-squad draws), and a greedy or composite constructor may produce 15s with
  systematically different "how close are the legal-XI options" structure than a uniform random
  draw. Free Hit's own `SelectionRegret(S, g)` series must still be computed on Free Hit's own
  constructed squads; the starting_xi figure is a sanity-check reference, not a substitute.
- It is the exact correction term connecting Construction regret to a squad-quality-only comparison
  — see §1.4.

### 1.3 Construction regret — candidate vs. one baseline, via the shared harness

```
ConstructionRegret_{C,B}(g) = Harness(S_C(g), g) − Harness(S_B(g), g)
```

where `S_C(g)` is the candidate's constructed 15 for gameweek `g` and `S_B(g)` is one specific
baseline's constructed 15 for the same gameweek — exactly `DECISION.md` §4's stated formula.
Positive values favor the candidate; this is a signed difference, not a nonnegative regret in P1's
sense.

**Properties.**

- **Not bounded below at zero and not guaranteed nonnegative in either direction** — unlike
  `SelectionRegret`, there is no structural reason `S_C` must outperform `S_B`. Calling it "regret"
  is `DECISION.md`'s vocabulary choice (a shortfall-vs-reference framing), not a claim of the P1
  shape.
- **It is not a pure measure of squad-construction quality**, because both sides are scored through
  `Harness`, not `Oracle`. Substituting the definitions from §1.1–§1.2:

  ```
  ConstructionRegret_{C,B}(g)
    = [Oracle(S_C, g) − SelectionRegret(S_C, g)] − [Oracle(S_B, g) − SelectionRegret(S_B, g)]
    = [Oracle(S_C, g) − Oracle(S_B, g)] − [SelectionRegret(S_C, g) − SelectionRegret(S_B, g)]
  ```

  A squad that happens to be "harder for the harness to select from" (larger `SelectionRegret`)
  will show a depressed `ConstructionRegret` against a squad that is "easier to select from," even
  when the two squads are of identical oracle quality. This is a genuine coupling, not a rounding
  concern, and it is the reason §1.2's four per-policy `SelectionRegret` series are reported
  alongside Construction/Combined regret rather than only as an FYI: a large, one-sided
  `SelectionRegret` gap between candidate and a given baseline is the diagnostic that explains an
  otherwise-puzzling Construction regret result.
- Computed once per (candidate, baseline, gameweek) triple. With three tracked baselines, this
  yields three separate paired time series per candidate — never collapsed, per `DECISION.md` §4's
  explicit instruction.

### 1.4 Combined regret — the same formula, a different purpose, and the one place this document interprets rather than quotes

`DECISION.md` §4's text for Combined regret ("realized total vs. baseline realized total, all-in")
is not a formula distinct from §1.3's — read literally, both are "candidate's harness-realized total
minus baseline's harness-realized total, same gameweek." **Neither `DECISION.md` nor `INVENTORY.md`
gives Combined regret a second formula**, and this document does not invent one. The reading taken
here:

- **Construction regret** and **Combined regret** are the same computed quantity
  (`ConstructionRegret_{C,B}(g)` as defined in §1.3), reported under two different framings for two
  different purposes:
  - *As Construction regret*: the per-baseline series feeding §2's verdict machinery, always kept
    disaggregated by baseline.
  - *As Combined regret*: the same series read as the single, undecomposed, real-world-relevant
    number — "how much better did the end-to-end candidate pipeline do," with no attempt to
    attribute the gap between construction quality and selection-layer execution. This is the
    number that answers `DECISION.md` §1's actual question ("is our candidate good"), since a
    manager experiences `Harness(S, g)`, never `Oracle(S, g)`.
- **This is an interpretive choice made here, flagged as such rather than silently assumed**,
  because the alternative reading — that Combined regret is meant to be a *sum* of Construction
  regret and a Selection-regret term (i.e., an explicit decomposition presented as its own labeled
  quantity) — is equally consistent with `DECISION.md`'s one-line description and cannot be ruled
  out from the text. §1.3's algebra already gives that decomposition in full; nothing is lost if
  `DESIGN.md` prefers to name the decomposed form "Combined regret" instead of treating it as
  identical to Construction regret. **Open item:** which reading `DESIGN.md` intends is not settled
  by either source document and is recorded as unresolved rather than picked by default.

---

## 2. The naive baseline verdict rule — resolved

`DECISION.md` §4 assigns this decision to METRIC.md explicitly, naming the tension it must survive:
the three baselines' relative strength may shift with time of season, and a rule that collapses them
into one number risks hiding that pattern.

### 2.1 The rule

For a construction candidate `C` against the three tracked baselines (season-PPG greedy, value
greedy, recent-form greedy):

1. Compute the Combined regret series `ConstructionRegret_{C,B}(g)` for each baseline `B`
   separately, over the qualifying gameweek set (§3).
2. Run three **independent, one-sided, paired** significance tests — `H0: mean regret ≤ 0` vs.
   `H1: mean regret > 0` — one per baseline, using the paired resampling scheme specified in §3.
3. Apply a **Holm–Bonferroni step-down correction** across the resulting three p-values, family-wise
   α = 0.05. Holm is chosen over uncorrected testing because three simultaneous "did we beat X"
   claims inflate the chance of at least one false positive; over Benjamini–Hochberg because a
   fixed, pre-registered family of exactly three comparisons feeding a single ship/no-ship question
   calls for family-wise error control, not a false-discovery-rate framework sized for large,
   exploratory comparison sets; over plain Bonferroni because Holm has equal or greater power while
   remaining valid under the correlation between the three tests (all three are computed from
   overlapping realized-outcome data for the same candidate and gameweek set, so the tests are not
   independent — Holm's guarantee does not require them to be).
4. **Verdict: PASS requires rejecting all three nulls in the favorable direction, after
   correction — i.e., the candidate must clear all three baselines, each judged on its own paired
   test, simultaneously.**

### 2.2 Why conjunctive-against-all-three, not best-of-three

`DECISION.md` §4's tension is specifically that a collapsed number could hide *which* baseline is
strong *when*. A best-of-three composite rule — pass if the candidate beats whichever baseline is
weakest in the comparison window — does not resolve that tension, it recreates it: it would let a
candidate "pass" by only ever clearing the currently-weak baseline, without the reported verdict
ever exposing that the two stronger baselines went unbeaten. A majority rule (beat 2 of 3) is a
softer version of the same defect. Requiring all three, each independently tested and independently
reported, is the rule that adds the least averaging on top of what `DECISION.md` already insists on
tracking separately: the verdict is a single boolean, but nothing about *how* it was reached is
collapsed — the three per-baseline series, their individual test results, and their behavior across
the season all remain fully visible in reporting. A candidate that narrowly fails against one
baseline while comfortably beating the other two is reported as "did not pass," but the report
itself still shows exactly where and (by inspecting the per-GW series) roughly when it fell short —
which is the information a best-of-three or majority rule would have discarded.

### 2.3 What this rule does not decide

The paired resampling scheme underlying step 2's tests, and the gameweek population step 1 sums
over, are §3's, not this section's. This rule is stated in terms of "the qualifying gameweek set"
without yet fixing what that set is.

---

## 3. Gameweek population and sample size

### 3.1 The resampling unit is gameweeks, not squads — and this is a first-principles departure from starting_xi, not a copy of it

`decisions/starting_xi/sampler.py`'s method (per `INVENTORY.md` §3) is **random**: it draws whole
squads by uniform rejection, deliberately generating multiple candidate squads per gameweek so that
"squad luck" — which random draw you happened to get — could be averaged out over repeated draws.
That is the reason starting_xi's uncertainty treatment resamples squads at all.

**None of Free Hit's v1 policies have that property.** `DECISION.md` §4 names the three baselines as
"greedy" constructors and the sequencing note's composite candidate as a deterministic scoring
formula (PPG + fdr_avg + value) fed into a greedy selection. A greedy construction over a fixed,
as-of-known player pool, prices, and signal values is a **deterministic function of the gameweek's
data** — there is exactly one squad `S_C(g)` a given policy produces for a given gameweek, full
stop. There is no squad-level random variable to marginalize for a fixed policy, because nothing
about picking `S_C(g)` was ever random in the first place. Resampling squads-within-a-gameweek for
these policies would resample nothing — every draw would return the same 15.

The variation that does exist in this design is entirely **across gameweeks**: different fixtures,
different price landscapes, different players in and out of form. The correct resampling unit is
therefore the qualifying gameweek set itself — a **paired bootstrap over the per-gameweek
`ConstructionRegret_{C,B}(g)` series**, structurally the closest analogue to starting_xi's own
"resample gameweeks, squads fixed" scheme (that document's U2), but for a different reason: there,
U2 was one of two legitimate views alongside squad-resampling; here, because no squad-level
randomness exists at all for a deterministic policy, gameweek-resampling is not an alternative view,
it is the only one available.

**A forward-looking caveat, not a v1 requirement.** `DECISION.md` §4 and §5 leave the eventual
ILP/forecasting candidate's design entirely open. If that candidate (when and if built) has its own
internal source of randomness — a stochastic solver, a sampling-based forecast — the "one
deterministic squad per policy per gameweek" premise this section rests on would need to be revisited
for that candidate specifically, and squad-level resampling could become live again for it alone.
Nothing named in `DECISION.md` §4's v1 scope (three naive baselines, one composite candidate) has
that property today.

### 3.2 The sample size this design needs is not settled, and this document cannot settle it

`INVENTORY.md` §1 states plainly that the "non-DGW/non-BGW gameweek" population `DECISION.md` §3
scopes v1 to has **two candidate definitions differing by more than an order of magnitude** — 1 of
38 gameweeks under a row-level reading, 33 of 38 under a club-schedule/registered-players reading —
and that the repository implements neither as a governing classifier. `INVENTORY.md` states this is
`DESIGN.md`'s call, not this document's, and this document does not attempt to make it.

What this document can and must state is the **consequence for its own machinery**: the paired
bootstrap in §3.1 operates over the qualifying gameweek set, and its meaningfulness scales with that
set's size.

- Under the 33-gameweek reading, a paired bootstrap over a season-length panel is the same kind of
  operation starting_xi's own U2 scheme performs, and §2's Holm-corrected tests have a workable
  sample to run on.
- Under the 1-gameweek reading, there is no panel to resample — a confidence interval computed from
  a single paired observation is not a confidence interval, and §2's entire verdict procedure
  degenerates to reporting whether one gameweek's outcome happened to favor the candidate over each
  baseline, which is an anecdote, not a verdict.

**This document does not choose between the two definitions** — that is `INVENTORY.md`'s own
deferral to `DESIGN.md`, unchanged here. But it records, as a constraint the eventual classifier
choice must satisfy for anything in §2 to be usable: **whichever DGW/BGW definition `DESIGN.md`
adopts must yield a qualifying-gameweek count large enough for the paired bootstrap in §3.1 to
produce a non-degenerate interval.** A definition that collapses the eligible set to a single
gameweek does not merely weaken this document's statistical design — it removes the basis for §2's
verdict rule to be computed at all, for v1's single season of data.

**Resolved, since this section was written: `DESIGN.md` §2 has adopted the club-schedule-level
definition** — a gameweek qualifies if zero clubs carry `fixture_count == 0` or `fixture_count == 2`
that week, checked at `(team_id, gw)` grain among already-registered players. This yields **33 of 38
gameweeks** (GW26/33/36 carry real doubles, GW31/34 carry real blanks), satisfying the condition this
section names: a season-length panel for the paired bootstrap, not a single-gameweek anecdote. The
reasoning above for why the row-level reading was the wrong choice is unaffected and remains the
justification for why 33 is correct, not merely convenient.

### 3.3 A related, separately-tracked exclusion this document does not resolve either

The three naive baselines require as-of statistics undefined at the start of a season: season-PPG-
to-date has no prior gameweek to average at gameweek 1, and recent-form PPG is thin for the same
reason at the season's start. This is a direct, structural consequence of `DECISION.md` §4's own
baseline definitions, not an imported starting_xi fact — but exactly where in Free Hit's own GW1–38
range each baseline's as-of statistic first becomes well-defined is not stated in either source
document and is not derived here. It is a second, independent exclusion axis layered on top of
§3.2's DGW/BGW question (both narrow the same 38-gameweek universe, for unrelated reasons), and both
must be confirmed — likely by `DESIGN.md`, against Free Hit's own mart facts rather than by carrying
over starting_xi's separately-measured warm-up figures — before the qualifying set in §3.2 has a
final count under either DGW/BGW reading.

---

## 4. Budget and external-reference handling

### 4.1 Budget — confirmed, not re-derived

`DECISION.md` §3 fixes the budget at 100m, applied identically to the candidate and to all three
naive baselines, for v1. `INVENTORY.md` §2 closes the "known limitation" `DECISION.md` §3 names
(whether team-value-by-GW data could someday support a variable-budget sensitivity pass) to a
confirmed absence at all four layers checked (mart, staging contracts, `fpl-ingest` extraction, raw
payloads). This is stronger than "deferred": there is currently no data path to build a
variable-budget variant from at all, without new ingestion work outside this repository's current
scope. `DECISION.md` §5 already places variable/live budget out of scope for v1; `INVENTORY.md`
confirms that scoping isn't merely a choice but the only option the data supports today. No metric
is specified for it here, consistent with §5's exclusion.

### 4.2 Top-10k average and overall average — reporting, not scoring

Per `DECISION.md` §4: both figures are reported as **unscored context alongside the pass/fail
comparison, never blended into it, and never read as a percentile or spread** (top-10k managers are
template-correlated, not independent draws). Operationally: each qualifying gameweek's report
carries these two figures as a labeled reference row or sidebar next to the scored
candidate/baseline regret table — visually and numerically separate from anything §2's verdict
computes over.

**A fact `INVENTORY.md` surfaces that materially affects feasibility here, incidentally, while
answering a different question.** In the course of resolving the team-value question,
`INVENTORY.md` §2 confirms the raw SQLite `events` table carries `average_entry_score` — the
overall average manager's realized score per gameweek — documented at
`docs/architecture/db-schema.md:300`, though not present on the mart. This is exactly the "overall
average" figure `DECISION.md` §4 wants as context. **Tier: Feasible now for the overall-average
figure**, with the caveat that accessing it requires a raw-database read path rather than the
mart-only path everything else in this document uses — a build-time detail, not a blocker under
§0.2's inputs-exist convention.

**Top-10k average has no equivalent confirmation.** `INVENTORY.md`'s four sections were scoped to
`DECISION.md` §7's four named questions, none of which asked whether a top-10k figure exists
anywhere in this repository's data surfaces. Its existence and source are **not addressed by either
source document** — an inventory gap, not a confirmed absence and not a confirmed presence. Open
item: `INVENTORY.md` must be extended to check for this before a report can include it; this
document does not invent a source for it.

---

## 5. Tiering

| Item | Tier | Basis |
|---|---|---|
| Construction / Combined regret (§1.3–1.4) | Feasible now | Every input — realized points/minutes, mart prices/positions/club, `fdr_avg`, and the existing unchanged selection+bench harness — is confirmed present or confirmed an existing routine. The greedy constructor and incremental-legality primitive that would *produce* `S_C(g)`/`S_B(g)` do not yet exist, but §0.2's convention tiers on inputs, not on unwritten code. |
| Selection regret (§1.2) | Feasible now | Identical basis to starting_xi's own P1; the routine itself is cited as already existing and reused unchanged, which is a stronger position than "inputs exist." |
| As-of PPG / rolling PPG as construction signals | Feasible now, with a corrected description | Not available as an existing zero-`model/`-import accessor (`INVENTORY.md` §4), but computable from the mart's own `total_points` via the `shift`/`expanding`-or-`rolling` pattern the repository already uses elsewhere for the same governance reason. Any report or downstream document should describe these as *derived*, not as pre-existing signals — correcting `DECISION.md` §3's looser phrasing per the gap noted above. |
| `fdr_avg` | Feasible now | Mart-native column, no derivation needed. |
| Naive-baseline verdict statistical form (§2) | Feasible now, conceptually | Paired one-sided tests with a Holm correction are arithmetic over a realized regret series; no project-specific data dependency. |
| Naive-baseline verdict — implementation reuse | Open — inventory gap | Whether a reusable paired/bootstrap significance-testing utility already exists anywhere accessible to this slice is not addressed by `INVENTORY.md`'s four sections. Not a blocker (the computation needs nothing beyond general-purpose statistics), but unconfirmed. |
| Gameweek population / sample size for §3's bootstrap | Open — `DESIGN.md`'s call, per `INVENTORY.md` §1 | Two candidate definitions differ by more than 30×; neither is implemented. §3.2 states the consequence for this document's machinery without resolving the definition. |
| Baseline as-of-statistic warm-up exclusion (§3.3) | Open | Not measured for Free Hit's own data by either source document. |
| Overall-average reference figure (§4.2) | Feasible now | Confirmed present in the raw SQLite `events` table (`INVENTORY.md` §2), off-mart. |
| Top-10k-average reference figure (§4.2) | Open — inventory gap | Existence/source never checked by `INVENTORY.md`. |
| Variable-budget sensitivity | Infeasible under current data | `INVENTORY.md` §2 confirms absence at all four checked layers; also out of scope per `DECISION.md` §5. No metric specified. |
| Incremental legality primitive (needed to produce any constructed squad at all) | Not this document's tier to assign | Belongs to the construction routine itself, which §1 explicitly treats as an input this document does not design. Recorded here only because every regret definition above is conditional on it existing; `INVENTORY.md` §3 and `DECISION.md` §3/§7 already track its status. |

---

## 6. Open items this document cannot resolve

Consolidated from above, each already flagged in place:

1. Whether "Combined regret" is identical to "Construction regret" or a separate decomposed sum —
   §1.4. Interpreted here as identical; not settled by either source document.
2. **Resolved.** Which DGW/BGW definition governs the v1 evaluation set, and therefore the
   qualifying-gameweek count §3's entire resampling and §2's entire verdict procedure depend on —
   §3.2. A one-gameweek population would have made this document's statistical machinery inoperable
   for v1's single season; `DESIGN.md` §2 has since adopted the club-schedule-level definition,
   yielding 33 of 38 qualifying gameweeks, which satisfies §3.2's non-degenerate-interval condition.
3. Where each baseline's as-of statistic first becomes well-defined within Free Hit's own GW1–38
   range — §3.3.
4. Whether a reusable paired/bootstrap significance-testing utility exists anywhere accessible to
   this slice — §5.
5. Whether a top-10k-average figure exists anywhere in this repository's data surfaces, and if so
   where — §4.2.
