# Starting XI and Bench Order — the metric

**Status:** Specified. Not built.
**Governs:** the harness for the `starting_xi` decision. Read `DECISION.md` first; this
document does not restate what is being decided.

---

## 0. Scope declaration

**This metric scores against expected points.** That is a deliberate scope decision, not a
default that fell out of convenience.

`DECISION.md` §2 establishes that the Goal — protect rank or chase — is an input to the
decision, and that a metric fixed to a single objective measures only part of it. The
response available to a first slice is to declare the objective explicitly rather than
leave it implicit, and that is what this document does. **Goal-conditional scoring** — the
same 15 producing two different correct XIs depending on whether the manager is protecting
rank or chasing it, and a metric that scores each against its own objective — is named here
as future work and is **not attempted**. A ranker that deliberately benches a nailed player
for a higher-ceiling doubtful one will score badly under this metric, and that result must
be read as "it lost points", never as "it was wrong".

**Competitive context is out of scope**, per `DECISION.md` §5. One consequence is worth
stating plainly because it is structural rather than a matter of build order: a
points-maximising metric **cannot express template-versus-differential reasoning even in
principle**. Starting the same player as everyone else and starting a player nobody owns
score identically here whenever the two return the same points. No amount of tuning inside
this metric recovers that distinction; it requires a different objective function.

---

## 1. Scoring — counterfactual regret

**The cost of a selection is the gap between the chosen XI's total and the best legal XI's
total, from the same 15, in the same gameweek.** Not the benched player's score.

```
regret(gw, squad, ranker) = points(best_legal_XI) − points(chosen_XI)
```

Regret is always ≥ 0 and is 0 for a perfect call. "Legal" means the XI satisfies the
formation constraints; the best legal XI is computed after the fact over realised points,
which is what makes it a counterfactual and not a forecast.

**Auto-substitution enters one side of this and not the other.**

- **The chosen XI is scored after auto-substitutions have fired**, per the mechanics fixed in
  §6. The realised total is *not* the sum of the eleven players the ranker selected: when a
  selected player records **no minutes** — whether that is a 0 or a no-fixture NULL, per §6 — a
  bench player replaces him under the substitution rules and the replacement's points are what
  count. Scoring the eleven as selected would charge a
  ranker for a blank the rules of the game already covered.
- **The best legal XI has no auto-substitution applied.** It is computed with hindsight over
  realised points, so it never *prefers* a player who did not feature. Where a formation minimum
  forces one in — a squad whose defenders mostly blanked still has to field three — applying
  substitutions would let the counterfactual bank points from a twelfth player, lifting the
  ceiling above what any XI *selection* could have realised and turning the benchmark into a
  joint XI-and-bench-order optimum. That is a different and harder decision than the one being
  scored.

**The consequence is deliberate.** Regret then measures **ranking quality**, not ranking quality
plus bench coverage. A ranker whose XI was rescued by the substitution rules does not bank that
rescue as a good selection, and one that ordered its bench well is not credited for it twice.
Bench coverage is a separate decision with a far smaller sample, which is exactly why §4 scores
bench order on its own and never folds it into this number.

Scoring the benched player instead would misprice every case where the alternatives also
returned well, and would credit a method for benching a blank it had no reason to foresee.
Regret prices the decision, not the outcome of one player.

**Regret is not summarised by its mean.** `DECISION.md` §1 establishes that losses of the
same size are different mistakes; the measurement consequence is that the report carries
three quantities and never collapses them into one:

| Quantity | What it isolates | How it is read |
|---|---|---|
| Regret on close calls (§3) | Variance | Large values here are the price of a call worth making again |
| Regret on clear calls (§3) | Method failure | Large values here are the ranker being wrong where the evidence was available |
| Mean **signed** directional error across gameweeks | Systematic bias | Small, same-signed, repeated — the most fixable and most damaging pattern |

A single averaged regret over all gameweeks mixes all three and is not reported as a
headline number.

**On tail weighting.** The tail — a large score left on the bench — is priced by the
magnitude of regret, not by a separate weight. A benched haul that mattered *is* a
large-regret event; one that every alternative matched is not. The tail is therefore reported
as the **distribution** of regret — the count and size of the worst weeks, per ranker — and
not folded into a weighted average. No haul-weighting coefficient is introduced: it would
double-count an effect regret already carries, and choosing its value would be an unmeasured
judgement sitting on top of a measured quantity. `DECISION.md` §1 records the withdrawal of
the earlier promise of an explicit tail weight.

---

## 2. Synthetic squad construction

**No real squad or picks history exists in this repository's data.** Every replay therefore
runs on **synthetic squads**. This is a modelling choice and is stated as such: all results
are explicitly conditional on the construction described here, and a different construction
may produce different rankings between methods. The conditionality covers every element of that
construction — uniform sampling over the feasible set, the 200–300 squad count, the build-once
rule, **and the squad universe being the players in the game at GW2**.

**Sampling is uniform over the feasible set.** A squad is feasible when it satisfies:

- the budget cap,
- 2 GK / 5 DEF / 5 MID / 3 FWD,
- at most 3 players per club,
- every player **already in the game** — no pre-registration rows.

**Feasibility is assessed in full at the build gameweek, and the build gameweek is GW2.** All four
conditions are evaluated together at that single point, against the prices, clubs and registrations
in force then. GW2 because it is the first in-scope week (§6): a squad built later could not be
scored across the full study scope, and every gameweek before its build date would drop out of
every result that squad contributes to.

**A squad feasible at GW2 remains valid for the rest of the season**, whatever happens to prices
and clubs afterwards. This is not a simplification made for convenience — it is how the game works.
A manager buys at the prices of the day; the ≤3-per-club limit binds when a squad *changes*, not
continuously; and this squad never changes, because it is built once and held (below) and
`DECISION.md` §3 puts transfers out of scope. Re-validating a held squad weekly against moving
prices would be modelling a manager who cannot exist.

**This closes two questions `INVENTORY.md` left open.** §5.2 asked whether the ≤3-per-club limit
binds at build time or per gameweek — 27 of 841 players change club across the season — and §5.5
asked the same of the budget cap, where 600 of 841 change price. Both are answered the same way and
for the same reason: assessed once at GW2, never re-checked.

**Why registration belongs in the feasibility definition rather than downstream of it.** Two
reasons, either sufficient alone. A pre-registration player is **not in the game**: his rows exist
only because the DAL spine is a full player × gameweek cartesian product, so admitting one would
put a phantom into a squad and count his zeros as real benchings (§6). And prefix rows carry a
**forward-filled price** — the value attributed to them is the player's eventual debut price rather
than one that existed at the time (`INVENTORY.md` §2.7) — so admitting one would import a leaked
valuation into the very budget cap that feasibility is assessed against. A squad priced against the
future is not a feasible squad in any useful sense.

**The predicate, written out.** Composing the condition above with §6's prefix test: a player is in
the squad universe **iff he has a non-null `minutes` row at GW1 or GW2**. The harness should read
this rather than derive it.

**What that composition rests on — and it is the more important half.** The predicate is
unambiguous only because GW1 and GW2 contain **no genuine no-fixture blanks** in this season, so
every NULL there is a pre-registration prefix. Verified against the mart: real no-fixture blanks
occur at **GW31 and GW34 only**. Were a blank gameweek to fall in GW1 or GW2, a *registered* player
could be NULL in both, the prefix test could not separate him from an unregistered one, and the
predicate would need a different form. **This is a property of the 2025-26 fixture calendar, not a
general fact.** It must be re-checked against any other season before this predicate is reused, and
it is recorded here because nothing else in the repository records it.

**Players entering the game after GW2 are outside the study — 136 of 841 players, 16.2%.** The
squad universe is therefore **705 of 841 registered players**: 82 GK, 233 DEF, 315 MID, 75 FWD,
across all 20 clubs, with a cheapest legal 15 of 64.0 against the 100.0 cap — so the feasible set
remains large. All 136 excluded players **do** appear later in the season, which confirms they are
genuine late entrants rather than a data artefact. This is the **single largest exclusion in the
design** — and the only one of the four feasibility conditions that removes a player from the study
outright. Budget, quota and club limits constrain which *combinations* may be drawn; registration
constrains who may be drawn at all.

The exclusion follows from the build-once choice rather than being an oversight in it. A player who
enters in January was not available to be drawn at GW2, and a manager holding a single 15 all season
could not have acquired him without a transfer. Excluding him is the consistent reading of the
design, not a gap in it. The cost is real and is stated rather than hidden: mid-season entrants are
never selected, never benched, and never enter any regret figure, so nothing here measures how a
method would have handled them.

**Sampling is randomised independently of any ranker under test.** This is the load-bearing
property. A squad built by sorting on points-per-game would hand a PPG ranker a squad
already selected on its own criterion, and the harness would measure that circularity
rather than the method. Independence is what keeps the comparison honest.

**200–300 squads.** The precision of the comparison is bound by the gameweek dimension, not by
the squad count. That dimension is **window-dependent**: a comparison spans the study scope of §6
only if both rankers declare it, narrows to §5's window intersection otherwise, and narrows again
under §3's zero-gap exclusions — the mid-thirties at best, fewer for a ranker with a restricted
window. Beyond a few hundred squads the added squads buy very little, and the cost of the replay
grows linearly in them. The cap follows from *which dimension is scarce*, which holds at any window
length in this range, rather than from a particular gameweek count.

**Squads are built once and held for the whole season.** They are not resampled per
gameweek. This matches the paired design of §5, and it matches real manager behaviour,
where the same 15 persists across weeks and the XI decision recurs within it.

**Plausibility-weighted sampling is deferred.** Uniform sampling covers the feasible set
including squads no human would build. Weighting toward realistic squads is only worth its
added assumptions if the uniform results show that method rankings are **sensitive to squad
composition**. That sensitivity is measurable from the uniform run; until it appears, the
weighting is not introduced.

---

## 3. Conditioning on closeness

The informative sample is the gameweeks where reasonable methods would disagree. Closeness
is defined per squad-week, **before** outcomes are known:

**Closeness = the gap between the best and the second-best legal XI totals, scored in
season-long as-of PPG.** Both XIs are legal formations from the same 15; the gap is the margin by
which the leading configuration led, on information available at the time.

**"PPG" names one statistic throughout this document.** Two now appear in it — the season-long
baseline of §5 and its 3-gameweek counterpart — so every unqualified use means the **season-long**
one, and the shorter window is always named where it is meant.

**The denominator is gameweeks elapsed, not appearances.** A player's season-long as-of PPG at
gameweek *t* is his total points before *t*, divided by the number of gameweeks before *t* in which
he was already in the game — counting the weeks he did not feature as the zeros they were:

- weeks he had a fixture and blanked **count**, at 0;
- weeks his club had no fixture **count**, at 0 — §6 already scores a no-fixture player as 0 in the
  best-legal-XI computation, and a manager selecting that week genuinely faced that 0;
- **pre-registration weeks do not count** — a player who entered the game at GW20 is not charged
  with nineteen zeros he had no opportunity to avoid. His denominator opens at his first week in
  the game, which is also why GW1 counts toward a GW2 denominator even though GW1 is itself
  unscoreable (§6).

**Why gameweeks and not appearances.** The two differ materially for rotation players, so the
choice is not cosmetic. §0 declares that this metric scores against **expected points**, and §1
measures regret in realised points where a non-featuring player contributes 0. A per-appearance
rate estimates a different quantity — points *given that he played* — which becomes comparable only
after multiplying by the probability he plays. Dividing by gameweeks performs that folding
implicitly, and keeps the selection statistic on the same footing as the thing being scored.

`DECISION.md` §1 separates "will this player play" from "what does he score when he does", and that
separation survives — but it is carried by keeping `p_play` a **ranker in its own right** (§5),
not by splitting this denominator. A per-appearance PPG ranker would start an 8-per-appearance
player who features a third of the time ahead of a nailed 4-per-week one. That is not a floor worth
clearing; it is a strawman, and beating it would demonstrate nothing.

**§3 and §5 take the same denominator, deliberately.** Closeness conditions the very sample the
rankers are judged on. If the conditioning statistic ordered the 15 differently from the baseline
ranker, "close calls" would be labelling weeks that were close under a measure no ranker uses — and
the conditioning would be selecting the sample on a quantity unrelated to the comparison it frames.
The 3-gameweek baseline of §5 uses the same convention over its shorter window: gameweeks, not
appearances, blanks at 0.

**The 11th-versus-12th PPG gap is not used.** It is confounded. When the squad's three best
remaining players by PPG are all defenders, that gap measures the `≥3 DEF` formation
minimum binding against the ordering, not how close the selection actually was. It would
label structurally forced weeks as close and genuinely balanced weeks as clear.

**Weeks with an exact zero gap carry no information** — every legal XI ties on season-long as-of
PPG, so no method can distinguish itself. They are **excluded from the conditioned analysis**, and
the excluded count is **reported**, per ranker and in total. The count is part of the result: a
large exclusion count means the conditioned sample is thinner than the headline gameweek span
suggests.

**What "per ranker" denotes.** Closeness is one fixed statistic, computed from season-long as-of
PPG and from the squad alone — it does not depend on the ranker being evaluated. Zero-gap weeks are
therefore a property of the **squad-week** and are identical across rankers. The per-ranker count
consequently varies only through §5's window intersection: a ranker with a restricted window sees
fewer squad-weeks and so excludes fewer of them. Reporting per ranker is what keeps each ranker's
conditioned sample size legible beside its result; it does **not** mean different rankers face
different closeness judgements on the same week.

---

## 4. Bench order

**Reported separately from XI selection, with its own event count.** Not folded into the
primary number, and not averaged against it.

**The substitution mechanics are not here — they are in §6.** They determine the chosen XI's
realised total and therefore the headline regret figure (§1), which makes them primary-path rules
rather than bench-order detail. This section neither owns nor restates them.

What remains here is the **ordering** — which bench player should come on first — and its sample.
Two counts matter, they are not the same number, and running them together is how a bench-order
result gets overstated. They are named separately and **both are reported**:

- **The substitution count** — squad-weeks in which a selected player recorded no minutes and a
  substitution fired. This is **primary path**: it sizes the headline regret figure, because those
  are exactly the weeks in which the chosen XI's realised total departs from the sum of the eleven
  selected (§1).
- **The ordering-relevant count** — the subset of those weeks in which the candidate orderings
  being compared would have brought on **different** players.

**The ordering-relevant count is the honest denominator for any bench-order claim.** A substitution
in which every candidate ordering brings on the same player carries no information about ordering:
the orderings were indistinguishable there, and no bench-order method could have done better or
worse. Reporting the substitution count as the bench-order sample would inflate the apparent
evidence for the secondary decision with weeks that could not have discriminated between methods —
the same error §3 avoids on the primary side by excluding zero-gap weeks. `DECISION.md` §6 flags
that if the ordering-relevant count is small, the decision may not be measurable on one season —
that check has not been run, and this document does not assume its answer.

**The scoring definition for bench order is an explicit TODO.** It is not invented here. A
plausible-looking rule written before the substitution mechanics were replayed would be a guess
wearing the clothes of a decision. Whatever rule is written must respect the mechanics fixed in §6
— in particular the two-orderings structure of the GK and outfield slots, and the priority-queue
semantics that keep a skipped player available.

---

## 5. Uncertainty

**The design is paired.** Every ranker faces the same synthetic squads in the same
gameweeks. Squad-level variation — some squads are simply deeper than others and have less
to gain from any selection method — is common to all rankers and cancels in the difference.
What is measured is the **method difference**, not the absolute regret level, and the
comparison is always ranker-versus-ranker on identical inputs.

**Every ranker declares the gameweek window over which it can produce output**, and any paired
comparison runs on the **intersection** of the windows of the rankers compared. That intersection
is reported alongside the result, as a span and a count.

The pairing requires both rankers to face the same weeks — that is what makes the difference a
method difference rather than a sampling artefact. It does not require every ranker in the study
to face the same weeks as every *other* ranker. Fixing one global window would drag every future
ranker down to the most restricted one anybody ever adds, discarding weeks the remaining rankers
can score for no reason beyond bookkeeping.

The first instance is already known. `p_play` inherits `WARMUP_GW = 3` from the term layer and
produces no output until **GW4**, while §6 scopes the study to GW2–38. The response is *not* to
narrow the study to GW4–38: the other naive rankers below can score GW2 and GW3, and those two
weeks are real evidence about them. Any comparison involving `p_play` runs on GW4–38 and reports
that span; comparisons not involving it run on the full GW2–38 scope.

**Resample over squads and over gameweeks separately.** Two intervals, reported as two:

- resampling squads holds the gameweek set fixed and measures sensitivity to which squads
  were drawn;
- resampling gameweeks holds the squads fixed and measures sensitivity to which weeks the
  season happened to contain.

**Squad-week rows are not independent and are never resampled as if they were.** The same squad
recurs across every gameweek in the comparison window and the same gameweek recurs across every
squad; treating the product as independent draws would inflate the effective sample by roughly two
orders of magnitude and manufacture precision that the data does not contain. The inflation is a
consequence of the panel structure, not of any particular window length — it holds whether a
comparison spans the full GW2–38 scope or a narrower intersection, and the correction is the same
either way. Any interval built that way is wrong regardless of how tight it looks.

**The bootstrap resample count is 10,000**, fixed here as this slice's own decision. It is part
of the pre-registration on the same terms as the 10% materiality threshold below: fixed before
the first run, not revised in response to results.

**Why it is stated rather than inherited.** The repository currently contains two
`block_bootstrap_ci` implementations — same name, same moving-block algorithm, different resample
counts (`n = 1000` in `research/kernels`, `n = 3000` in `model/eval`) — so a harness that merely
imports one acquires its resample count by accident of import path. Given that criterion 2 below
turns on whether an interval excludes zero, that is not an acceptable way to acquire the number.

**Why 10,000.** The verdict is a boundary test on a percentile endpoint. At `n = 1000` the 2.5%
endpoint rests on the 25 most extreme draws, and Monte Carlo jitter in that endpoint can flip the
significance verdict for a difference that is not itself near zero. At 10,000 it rests on 250,
and percentile convergence (~1/√n) puts the simulation noise well below the effect sizes this
metric is trying to resolve. The cost is negligible: the statistic being resampled is a mean over
a few dozen gameweeks or a few hundred squads — the exact count varies with the comparison window
— not a model fit.

**Departure from `INVENTORY.md`.** The inventory (§4, M1) recommends pinning the `research/kernels`
implementation at `n = 1000` to protect the reproduction anchors listed in
`docs/audits/phase1-audit.md` §4. That recommendation is **not adopted here**, and the reason is
scope: those anchors belong to previously published results, and this slice publishes nothing that
has to reproduce them. Anchor compatibility is a real constraint on changing the *existing*
implementations — which nothing here proposes — but it is not a reason for a new metric to inherit
their resample count.

**The duplication remains a known hazard.** Whichever implementation supplies the interval must be
named explicitly at the call site, by full module path, so it can never be selected by import
accident. The count fixed above governs regardless of which implementation supplies it.

**Pre-registered success criterion.** A candidate ranker has beaten the floor only when all
three of the following hold:

1. **Direction** — its mean regret is lower than that of the best naive baseline.
2. **Significance** — the paired resampled interval on that difference excludes zero.
3. **Materiality** — the reduction is at least **10%** of the floor ranker's own mean regret.

All three. Any two is a fail.

**Why the bar is relative and not a fixed number of points.** The headroom available in this
decision is unmeasured — nobody has yet computed how much regret the floor actually carries,
so nobody knows how much of it is removable. A bar fixed in absolute points, chosen before
that number exists, risks pre-registering a target no ranker can reach and calling a real
improvement a failure. A floor-relative minimum can be fixed honestly now, because it scales
with whatever the floor turns out to be.

**Why significance alone is not enough.** The paired design draws hundreds of independent
squads, and squad-level variation cancels in the difference. The squad-resampled interval on a
method difference can therefore be tight enough to exclude zero for a difference of a few
hundredths of a point per gameweek — a difference no manager would notice and no complexity
budget would justify. Significance answers "is it real"; it does not answer "is it worth
anything". Materiality is the second question, and it needs its own threshold.

**Why 10% and not more.** It is the weaker of the two thresholds considered, chosen
deliberately: the failure mode being guarded against is an unreachable bar set on unmeasured
headroom, and a stricter one reintroduces exactly that risk. It is fixed **before** the first
run and is **not** revised in response to results.

**Report the absolute magnitude alongside the relative figure.** A 10% reduction on a large
floor regret and a 10% reduction on a small one are different results, and only the points
figure says which one is on the table. The relative number decides whether the criterion is
met; the absolute number is what tells a reader whether the added complexity earned its
keep.

**Naive rankers run first, and there are three of them.** The floor is established before any
forecast-based ranker is measured. The order is deliberate: a forecast ranker evaluated
without a floor already on the board invites the floor to be chosen afterwards, and the
floor is the whole result — a sophisticated method that does not clear a one-line heuristic
has not earned its complexity.

| Naive ranker | What it ranks on | Window |
|---|---|---|
| `p_play` alone | Probability of featuring; scoring rate ignored entirely | GW4–38 |
| PPG-to-date | Season-long mean points over prior gameweeks | GW2–38 |
| **Recent form — PPG over the last 3 gameweeks** | The same statistic over a 3-gameweek lag-1 window | GW2–38 |

**Why a recent-form baseline was added.** Season-long PPG is a weak bar. No manager selects that
way — the entire folk practice of the game is to look at recent returns — so beating it
demonstrates very little about a method. A candidate that clears season-long PPG but loses to a
three-week rolling average has not beaten anything a human would actually have done, and
reporting it as having cleared the floor would be flattering the candidate rather than testing it.

**Why three gameweeks.** Short enough to track what the decision actually turns on — rotation and
form moving within a season — and long enough that a single blank or a single haul does not
dominate the ordering. It also matches the window the rest of the platform already uses for lag-1
rolling signals (`minutes_roll3`, `xgi_roll3`), so the baseline introduces no new convention. A
5-gameweek variant is worth running as a cheap sensitivity check; it is **not** a fourth
pre-registered baseline.

**The floor is the best-performing naive ranker, not a nominated one.** Whichever of the three
carries the lowest mean regret *is* the floor, and all three criteria above are evaluated against
it. A candidate that beats season-long PPG but loses to recent form has **not** cleared the floor.
Which of the three wins is itself a result worth reporting — if `p_play` alone is hard to beat,
that says something about the decision that no candidate ranker's score would reveal.

**Open — the mart does not carry a rolling points column, and that may be deliberate.** The
governed DAL mart excludes `points_roll3`: the feat layer omits `total_points` from its rolling
set, annotated as removed by lens evaluation for evaluation circularity. The recent-form baseline
therefore has to be computed **inside the harness**, following the same lag-1 convention the
minutes rolls use — `shift(1)` before the rolling window, within each player
(`dal/feat/feat_player_gameweek.py:99–106`) — rather than read off the mart.

What is **not** settled is whether that exclusion is a governance decision that also binds here,
or an omission specific to the signal registry's purposes. The distinction matters. If the
exclusion is deliberate, materialising the column inside this harness requires a stated
justification — the circularity concern was about a *governed signal* predicting a target derived
from itself, which is not what a **baseline ranker** does, but that argument has to be made and
accepted rather than assumed. If it is an omission, there is nothing to justify. Materialising the
column quietly, without putting the governance question, would be the wrong way to close it — so
the question is **routed rather than noted**:

| | |
|---|---|
| **Question** | Is the governed mart's exclusion of `points_roll3` a governance decision that binds this harness, or an omission specific to the signal registry's purposes? |
| **Owner** | The Phase 4 baseline implementation. It cannot proceed without an answer: the recent-form ranker is one of the three baselines it exists to build. |
| **Status** | **Prerequisite to Phase 4** — a gate, not a note. Phase 4 does not begin with this open. |
| **What settles it** | The lens record behind the annotation on `_ROLL_COLS` in `dal/feat/feat_player_gameweek.py`, which removes `total_points` for "evaluation_circularity or G2-FAIL". That verdict either does or does not extend to a *baseline ranker*, which is not a governed signal predicting a target derived from itself. Reading the record is the whole task. |
| **Where the answer is recorded** | If the answer is a governance verdict, `research/families/form/validate/evidence.yaml` — the durable verdict-of-record. If the answer is that the exclusion does not bind here, an amendment to this subsection, carrying the reasoning that licensed it. |

**The same divergence has now been observed from the other side, by measurement.**
`assert_no_future_leakage` requires `points_roll3`, and running
`operational.backtest.backtest_decision` against the live mart raises `ValueError` on the first
evaluated gameweek — the existing decision-backtest path is **unrunnable against the governed
mart**, and its coverage rests entirely on fixtures that fabricate the column
(`INVENTORY.md` §5.7, executed 2026-08-18). Whichever way the question above is answered, the guard
and the mart contract cannot both stay as they are. This harness must not adopt that guard before
it is settled.

**Partial availability at the start of the season.** The 3-gameweek window inherits the same
situation as `p_play`, in milder form: one prior observation at GW2, two at GW3, three from GW4
on. It is defined throughout GW2–38 and declares that window, with the early thinness visible in
the reported span rather than hidden behind a minimum-observations cut. Nothing special is needed
— should a minimum-observations rule later be imposed, the ranker declares the narrower window and
the intersection mechanism above handles every comparison automatically.

---

## 6. Harness rules that change the numbers

These are not implementation detail. Each one moves the measured values, so they belong in
the metric definition and are fixed here.

**Gameweek scope is GW2–38.** Season-long as-of PPG is null at GW1 by construction — there is no
prior gameweek to compute it from — so GW1 cannot be scored or conditioned and is excluded
outright rather than defaulted to zero.

**That is the study-level bound, not the span of any particular comparison.** Rankers declare their
own windows, and a paired comparison runs on the intersection of them (§5) — so no single
comparison necessarily spans GW2–38, and some will not. The scope here bounds what any ranker may
declare; §5 governs what each comparison actually covers, and the span reported with a result is
the authoritative figure for that result.

**A player with no fixture scores 0 in the best-legal-XI computation.** He remains legal to
select and simply contributes nothing **on that side**. Treating him as unselectable would silently
change the feasible formation set and make the counterfactual easier than the real decision. **On
the chosen side he is not left standing:** having recorded no minutes he fires an auto-substitution
(the rule below), so what he effectively contributes there is the replacement's score. The
asymmetry is deliberate and is exactly the one §1 fixes — substitutions apply to the chosen XI and
never to the counterfactual.

**`minutes` NULL means no fixture — but not always.** Approximately 84% of NULL `minutes`
values are a **pre-registration prefix**: rows for gameweeks before the player existed in
the dataset, rather than a genuine blank in an active player's season. The two are
distinguished by checking whether a **non-null row exists earlier in the season for that
player**. If one does, the NULL is a real no-fixture blank; if none does, the row is prefix
and the player was not selectable at all. Conflating them would put phantom players into
synthetic squads and count their zeros as real benchings.

**Auto-substitution fires when a selected player recorded no minutes.** It determines the chosen
XI's realised total (§1), so it is primary-path machinery, not a bench-order detail. **Two data
representations both mean "recorded no minutes"** and the harness must treat them identically:

- `minutes` **= 0** — the player had a fixture and did not feature.
- `minutes` **NULL** — the player's club had no fixture. No fixture means no minutes, and FPL
  auto-subs such a player exactly as it does an unused one. Reading the trigger as 0-only would
  leave blank-gameweek players standing in the XI and understate every ranker's realised total.

**A player who came on for a minute is not auto-subbed.** One minute is an appearance. This is the
carve-out the rule exists to protect: there is no partial-appearance case and no threshold to tune
— the boundary is *featured at all*, not *featured enough*.

**The pre-registration prefix is not an auto-substitution case.** The other NULL population above —
rows for gameweeks before a player entered the game — is a **squad-construction** exclusion, owned
by **§2 as the fourth feasibility condition**: such a player is never drawn into a squad in the
first place, so no substitution question can arise for him. The two NULL populations must not be
conflated in the harness. Treating a prefix row as a substitution event would manufacture bench
events out of players who did not yet exist, and inflate the §4 **substitution count** with them.

**The substitution mechanics.** These were previously recorded in §4 as constraints on a future
bench-order rule. They are prerequisites for the headline number, so they are fixed here:

- **The GK slot is a separate process from the three outfield slots.** A benched goalkeeper can
  only replace the starting goalkeeper; the outfield bench order does not apply to it. Bench order
  is therefore two orderings, not one ranking of four.
- **A substitution fires only if it preserves a legal formation.** This is what keeps the
  post-substitution XI a legal XI drawn from the same 15 — and therefore what keeps regret ≥ 0 in
  §1, since the best legal XI is the maximum over exactly that set. Without it the chosen side
  could out-score its own counterfactual.
- **Skipped players remain available later in the same gameweek.** If a bench player cannot come on
  because the substitution would break the formation, he is passed over for that substitution but
  is still eligible for the next one in the same gameweek. The ordering is a priority queue with
  legality checks, not a fixed consumption sequence — and a scoring rule that treats a skipped
  player as spent will misprice it.

**No per-gameweek availability field exists in this data.** `bootstrap.json`'s `status` and
`chance_of_playing` fields are a **post-season snapshot** — they carry end-of-season values
against every gameweek — and using them leaks outcome information backwards into the
selection. **They must not be used** by any ranker or by any part of the harness. Minutes
certainty has to be estimated from history that was actually available at the time.

---

## 7. Where this sits against `DECISION.md`

Recorded rather than reconciled.

- **§2, single-objective scoring.** `DECISION.md` §2 states that a metric scoring one
  configuration against a fixed objective measures only half the decision. It frames this as
  a limitation and does not offer declaring-the-objective as a way out. §0 above declares
  expected points anyway. The limitation stands, unresolved and named; the declaration makes
  it explicit rather than removing it.
- **§6, the three pending data checks.** Checks 1 and 3 are answered here — auto-substitution
  triggers whenever a selected player recorded no minutes, in either data representation (§6),
  and closeness is the best-versus-second-best legal XI gap in season-long as-of PPG (§3). Check 2 — how many gameweeks the secondary decision was actually
  live — is **not** answered. It is a harness output (§4), not an input to this document, and
  no number for it is asserted anywhere here.

Two entries recorded here previously are now resolved, by corrections to `DECISION.md` rather
than by changes to this document: §1's promise of an explicit tail weight, withdrawn as
double-counting what regret already prices; and §3's silence on the absence of real squads,
which now states the synthetic-squad caveat itself.
