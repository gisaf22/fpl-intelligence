# SIGNAL_SURVEY.md — Free Hit Squad Construction & Selection

**Status:** Read-only measurement pass, complete. **Governs nothing, recommends nothing, builds
nothing.** This document records what signal quality actually exists in the mart, measured
directly, and states an honest conclusion about it. It is not a build specification and takes no
candidate decision.

**Why this is a separate document rather than a `DESIGN.MD` section.** `DESIGN.MD` §1-§8 are
uniformly "what to build for candidate X" — each section specifies a construction candidate, its
ingredients, its weights and its verdict. This pass answers a question that sits *above* any
single candidate: **is there unexploited cheap signal left in the mart at all?** That is
fact-finding, closer in job to `INVENTORY.md` than to `DESIGN.MD`, and forcing it into a numbered
`DESIGN.MD` section would misrepresent it as a candidate specification. This follows the same
one-job-per-document discipline the slice already uses: `DECISION.md` states what is being decided
and why, `INVENTORY.md` states what exists, `METRIC.md` states how things are measured,
`DESIGN.MD` states what to build. This document's job is **what signal quality exists**.
`DESIGN.MD` carries a two-sentence pointer to it after §8.8 so a future reader of that document's
history knows this record exists.

**Prior context.** Two composite construction candidates — C4 (`DESIGN.MD` §7) and C5 (§8) — both
failed to beat the naive season-PPG baseline (C1). Both were hand-weighted linear combinations of
existing signals, and both were position-blind. §8.8 closed C5 and left open, as a
`DECISION.md`-level call, whether to pursue the deferred ILP/forecasting path. This survey was run
before that call, to answer a narrower and much cheaper question first: does **any** already-
available signal, on its own, predict next-gameweek points meaningfully better than season-PPG —
and does the answer vary by position, as prior work in this slice (`fdr_avg`, `transfers_in`) has
repeatedly shown it does.

---

## 1. Method

### 1.1 Population

The **exact** population Free Hit's construction step operates on: the output of
`build_candidates(mart, gw)` (`candidates.py:243`) for every one of the **32 qualifying
gameweeks** returned by `gameweek_population.qualifying_gameweeks` (`gameweek_population.py:113`)
— GW 2-25, 27-30, 32, 35, 37, 38.

**24,918 candidate rows**, ex-ante, **full pool, no minutes filter and no survivor
restriction.** This choice is deliberate and load-bearing. The `fdr_avg` assessment established
that population choice alone can swing a finding by an order of magnitude, and defaulting to a
`minutes >= 60` lens-study population out of convenience would have measured a different question
than the one the constructor actually faces. Every figure below is on the pool the greedy
constructor genuinely sees.

### 1.2 Target — lag-1, next gameweek

`total_points` at **GW N+1** for the same `player_id`, where the signal is measured at GW N.
Implemented by shifting the target frame's `gw` down by one before joining, yielding **24,077
paired rows** — the 841-row shortfall against the population is GW38's signals, which have no
successor gameweek.

This is the correction the `transfers_in` assessment's finding demanded. Same-gameweek
correlation answers a question no forecast can act on; a real forecast predicts now, acts now, and
is scored next week. That distinction is precisely what revealed `transfers_in`'s headline
lens-study number did not transfer to Free Hit's actual use, and it is applied here from the start.

**Leakage-safety confirmed, not assumed.** `season_ppg` at GW N is the expanding mean of that
player's points through GW N-1 (`candidates.py:225-227`, `shift(1).expanding().mean()`), verified
directly against a sampled player's rows: GW1's value is NaN and every later value excludes its own
gameweek's outcome. `recent_form_ppg` uses the same `shift(1)` construction, and `minutes_roll3`
is a governed FEAT column built by the same leakage-safe pattern (`DESIGN.MD` §8.6). No signal
below can see its own target.

### 1.3 Confidence intervals

**GW-cluster bootstrap** — resample the 32 gameweeks with replacement, taking all rows of each
drawn gameweek — **1,000 samples, seed 42**, 95% percentile interval. Reported as the primary
interval throughout, because rows within a gameweek are not independent (shared fixtures, shared
opponents, shared scoring environment) and an i.i.d. row bootstrap would understate the true width.

Cross-checked against the repository's standard i.i.d. row bootstrap
(`research/kernels/inferential/resampling.py:28`, the methodology established in the `availability`,
`fixture`, `form` and `market` family validate studies). **The two agree on every verdict in this
document** — no signal/position cell changes its pass/fail status between them. Where they differ
it is in interval width only, in the expected direction.

### 1.4 The decision rule — committed before results were seen

A signal is flagged **"worth further investigation"** at a given position **iff both**:

- **(a)** its next-GW **|rho|** at that position exceeds `season_ppg`'s own next-GW |rho| **at that
  same position** by **>= 0.03 absolute**; and
- **(b)** its confidence interval excludes zero.

**This rule was stated and fixed before any position-level result was inspected, and has not been
adjusted since.** Two properties of it are worth stating explicitly:

- **0.03** matches the materiality bar used elsewhere in this repository's lens studies. With n in
  the thousands at every position, the CIs are narrow enough that criterion (b) admits almost
  anything non-zero — **criterion (a) is doing the real work**, and that is intended.
- **|rho|, not signed rho.** Judging on magnitude means a directionally-negative signal is assessed
  on strength rather than sign. Without this, `fdr_bin` and `fdr_rev` — the same information,
  sign-flipped — would receive opposite verdicts from an identical measurement.

### 1.5 Signals surveyed

Nine signals, fixed in advance, all confirmed already present on the governed mart. Nothing was
derived, nothing was sourced externally, and nothing outside the pre-agreed list was substituted
in: `season_ppg` (the baseline reference), `recent_form_ppg`, `value`, `fdr_bin`, `transfers_in`,
`minutes_roll3`, `minutes_roll5`, `minutes_roll8`, `was_home`.

`minutes_roll5` and `minutes_roll8` were confirmed trivially available beside `minutes_roll3` as
governed mart columns, so both untried windows were included. **`fdr_rev` is not a separate mart
column** — it is the sign-flip of `fdr_bin`, and is therefore fully covered by §1.4's decision to
judge on |rho|. No signal on the list turned out to be missing or expensive.

---

## 2. Results

All figures below are next-GW Spearman rho against `total_points` at GW N+1, with the **GW-cluster
95% CI**, and the margin against `season_ppg`'s rho **at the same position**.

**Sample sizes.** Derived signals (`season_ppg`, `recent_form_ppg`, `value`, `minutes_roll3/5/8`):
GK 2,743 / DEF 7,802 / MID 10,623 / FWD 2,611 / pooled 23,779. Mart-native signals (`fdr_bin`,
`transfers_in`, `was_home`) are non-null on a few rows where the derived signals are NaN: GK 2,757
/ DEF 7,841 / MID 10,687 / FWD 2,631 / pooled 23,916.

### 2.1 The reference row

Every other signal is measured against this, per position. **This is the number to beat.**

| | GK | DEF | MID | FWD | POOLED |
| --- | --- | --- | --- | --- | --- |
| **`season_ppg`** | **.7654** [.7396, .7931] | **.6074** [.5925, .6239] | **.6813** [.6637, .7000] | **.7187** [.7040, .7332] | **.6740** [.6617, .6867] |

The baseline is not uniform across positions: it is strongest at GK (.765) and FWD (.719), weakest
at DEF (.607). DEF is the hardest position to predict from season-PPG, and — see §3 — the position
where nothing available helps.

### 2.2 Full results — 9 signals x 4 positions x pooled

Margin is versus `season_ppg` at the same position. ✅ = clears §1.4's rule; ❌ = does not.

| Signal | GK | DEF | MID | FWD | POOLED |
| --- | --- | --- | --- | --- | --- |
| **`season_ppg`** *(ref)* | .7654 [.7396,.7931] | .6074 [.5925,.6239] | .6813 [.6637,.7000] | .7187 [.7040,.7332] | .6740 [.6617,.6867] |
| `recent_form_ppg` | .8120 [.7843,.8400]<br>**+.0466 ✅** | .6003 [.5822,.6182]<br>−.0071 ❌ | .6987 [.6789,.7181]<br>+.0174 ❌ | .7436 [.7280,.7587]<br>+.0250 ❌ | .6841 [.6704,.6967]<br>+.0102 ❌ |
| `value` † | .7643 [.7377,.7922]<br>−.0011 ❌ | .6047 [.5897,.6210]<br>−.0027 ❌ | .6746 [.6566,.6931]<br>−.0067 ❌ | .7134 [.6985,.7276]<br>−.0052 ❌ | .6660 [.6541,.6786]<br>−.0080 ❌ |
| `fdr_bin` | .0035 [−.0104,.0196]<br>−.7619 ❌ | .0015 [−.0181,.0197]<br>−.6059 ❌ | .0086 [−.0047,.0216]<br>−.6726 ❌ | .0002 [−.0255,.0267]<br>−.7185 ❌ | .0052 [−.0052,.0157]<br>−.6688 ❌ |
| `transfers_in` | .6305 [.6093,.6528]<br>−.1349 ❌ | .5706 [.5558,.5868]<br>−.0368 ❌ | .6385 [.6146,.6598]<br>−.0428 ❌ | .6487 [.6270,.6710]<br>−.0700 ❌ | .6067 [.5895,.6235]<br>−.0672 ❌ |
| `minutes_roll3` | .8230 [.7949,.8517]<br>**+.0577 ✅** | .6317 [.6159,.6475]<br>+.0243 ❌ | .7142 [.6951,.7323]<br>**+.0329 ✅** | .7508 [.7314,.7677]<br>**+.0321 ✅** | .6995 [.6869,.7109]<br>+.0255 ❌ |
| `minutes_roll5` | .8073 [.7797,.8361]<br>**+.0420 ✅** | .6249 [.6083,.6418]<br>+.0174 ❌ | .7063 [.6863,.7249]<br>+.0250 ❌ | .7516 [.7336,.7666]<br>**+.0329 ✅** | .6926 [.6800,.7050]<br>+.0187 ❌ |
| `minutes_roll8` | .7922 [.7652,.8206]<br>+.0269 ❌ | .6226 [.6087,.6377]<br>+.0152 ❌ | .7020 [.6862,.7187]<br>+.0207 ❌ | .7445 [.7250,.7603]<br>+.0259 ❌ | .6883 [.6788,.6987]<br>+.0144 ❌ |
| `was_home` | −.0075 [−.0166,.0011]<br>−.7578 ❌ | −.0072 [−.0217,.0081]<br>−.6003 ❌ | −.0093 [−.0216,.0033]<br>−.6719 ❌ | .0011 [−.0310,.0318]<br>−.7175 ❌ | −.0077 [−.0171,.0012]<br>−.6663 ❌ |

† `value` is not an independent result — see §2.5.

### 2.3 Paired-delta supporting test — every cell that cleared

The §2.2 margin compares two separately-estimated rho values, each carrying its own sampling
noise. The stronger test computes the difference **on the same rows**, so the two estimates share
their noise, and bootstraps that difference directly (|rho_signal| − |rho_season_ppg|, GW-cluster,
1,000 samples, seed 42).

**Every one of the six clearing cells survives it**, with a CI excluding zero:

| Position | Signal | Paired Δ | 95% CI | n |
| --- | --- | --- | --- | --- |
| GK | `minutes_roll3` | **+.0577** | [+.0432, +.0722] | 2,743 |
| GK | `recent_form_ppg` | **+.0466** | [+.0333, +.0592] | 2,743 |
| GK | `minutes_roll5` | **+.0420** | [+.0286, +.0550] | 2,743 |
| MID | `minutes_roll3` | **+.0329** | [+.0178, +.0486] | 10,623 |
| FWD | `minutes_roll5` | **+.0329** | [+.0194, +.0459] | 2,611 |
| FWD | `minutes_roll3` | **+.0321** | [+.0172, +.0476] | 2,611 |

The margins are real, not artifacts of comparing two independently-noisy estimates. Note this
test confirms the margins **exist**; it says nothing about whether they **matter**, which is §4's
subject.

### 2.4 Sensitivity — restricting the target gameweek to schedule-clean weeks

The qualifying set governs the gameweek a signal is *measured* in, but says nothing about the
gameweek it is *scored* in. Six signal-gameweeks have a target in a DGW/BGW week (N+1 ∈ {26, 31,
33, 34, 36}), where a doubled or blank fixture distorts the points total. Excluding those targets
drops the sample to **n = 20,654** (derived signals; 20,780 for mart-native).

**The verdict set is identical.** No signal/position cell flips in either direction. Margins move
only in the third decimal place — FWD `minutes_roll5` +.0329 → +.0355, GK `minutes_roll3` +.0577 →
+.0531, MID `minutes_roll3` +.0329 → +.0332. DGW/BGW targets are not driving any result here.

### 2.5 `value` is a restatement of `season_ppg`, not an independent finding

**Stated explicitly so it is not miscounted as a real result.** `value` is defined as
`season_ppg / purchase_price` (`candidates.py:233`) — it is the baseline signal divided by price,
not an independent measurement of anything.

The data confirm the construction. `value`'s rho sits **0.001 to 0.008 below `season_ppg` at every
single position**, and the paired-delta intervals are microscopic and consistently negative
(DEF [−.0039, −.0015]; MID [−.0088, −.0049]; FWD [−.0093, −.0009]; GK [−.0025, +.0002]). Dividing
by price is a near-monotone perturbation of the ranking that costs a trace of rank information and
adds none.

**This row carries no information about `value` as a signal.** It functions as a consistency check
that the measurement pipeline reproduces a known-by-construction relationship, and it should be
read that way and no other. C2, the value-greedy candidate, is not evidenced for or against here.

---

## 3. Summary — what cleared and what did not

### 3.1 Cleared: 6 of 36 signal x position cells

| Position | Signals clearing §1.4's rule |
| --- | --- |
| **GK** | `minutes_roll3` (+.0577), `recent_form_ppg` (+.0466), `minutes_roll5` (+.0420) |
| **MID** | `minutes_roll3` (+.0329) |
| **FWD** | `minutes_roll3` (+.0321), `minutes_roll5` (+.0329) |
| **DEF** | **none** |

### 3.2 Did not clear — stated as plainly as the positives

A mostly-negative result is itself the useful finding here, exactly as C4's and C5's negative
results were.

- **`fdr_bin` — rho is zero.** .0035 / .0015 / .0086 / .0002 across GK/DEF/MID/FWD; the CI
  **includes zero at every position and pooled**. This is not a weak signal, it is an **absent**
  one. `fdr_rev` is the identical measurement sign-flipped and is equally absent. See §5 for the
  reconciliation with `DESIGN.MD` §8.8.
- **`was_home` — rho is zero.** −.0075 / −.0072 / −.0093 / +.0011; CI includes zero at every
  position. `DESIGN.MD` §7's C4 assessment flagged `was_home` as cheap, mart-native and untried.
  **It has now been tried, and it is empty.** That question is closed and needs no further pass.
- **`transfers_in` — strongly predictive, and strictly worse than the baseline everywhere.** rho
  .5706 to .6487, comfortably non-zero, easily clearing criterion (b) — and **below `season_ppg`
  at every single position** (−.0368 to −.1349, worst at GK). It fails on criterion (a), not (b).
  This is the `transfers_in` assessment's own lesson restated by an independent measurement: a
  signal can be genuinely informative and still add nothing over the baseline it has to beat.
- **`minutes_roll8` — clears nowhere, and the window decay is monotone.** At **every one of the
  four positions**, roll3 > roll5 > roll8. The longer windows are strictly worse, so the two
  untried windows resolve cleanly: roll5 is a weaker roll3, roll8 weaker still. GK roll8 at
  +.0269 is the near-miss; it does not clear, and the threshold is not being moved to admit it.
- **`recent_form_ppg` — GK only.** Negative at DEF (−.0071), short of the bar at MID (+.0174) and
  FWD (+.0250). C3's signal is not a general improvement on C1's.
- **DEF clears on nothing at all.** It has both the lowest baseline rho (.6074) and the flattest
  response to every signal tested — the largest single position block in the pool (7,802 rows) and
  the one where no available signal helps.

### 3.3 Threshold calibration note — not grounds for retroactive change

Had the threshold been pre-committed at **0.05** instead of 0.03, **only 1 of the 6 cells would
survive**: GK `minutes_roll3` (+.0577). GK `recent_form_ppg` at +.0466 would fall just short, and
every other clearing cell (+.0420 down to +.0321) by a wider margin.

**This is recorded as calibration, not as a reason to change anything.** The 0.03 threshold was
committed before results were seen and it stands. The point of stating this is to make the
thinness of the winning margins visible: five of the six positives sit in the .032-.047 band, and
the entire positive finding of this survey is sensitive to a materiality bar that could
defensibly have been set slightly higher. A reader should weight §3.1 accordingly.

### 3.4 The pooled column would have misled

`minutes_roll3` pooled is **+.0255 — below threshold, ❌** — while clearing at three of the four
positions. A pooled-only analysis would have reported this survey as a clean negative and hidden
the GK result entirely. This is the third time in this slice (`fdr_avg`, `transfers_in`, now this)
that position-blind aggregation would have misrepresented a position-dependent signal. The pooled
column is retained above for reference only and **is not sufficient to draw conclusions from**.

---

## 4. The reframing caveat — what a high rho is actually measuring here

**This section reframes every positive result in §3.1 and should be read before acting on any of
them.**

In this population, **61.4% of paired rows record zero minutes in the target gameweek**:

| Position | Zero minutes at GW N+1 | Scored <= 0 points at GW N+1 |
| --- | --- | --- |
| GK | **77.6%** | 77.9% |
| DEF | 59.4% | 62.8% |
| MID | 59.8% | 60.7% |
| FWD | 56.9% | 57.6% |
| **Pooled** | **61.4%** | — |

Next-GW points over the full ex-ante pool is therefore **predominantly a binary will-he-play
variable, not a scoring-rate variable.** That is what a rho of .82 is measuring.

**This explains the direction of every positive result.** `minutes_roll3` beats `season_ppg`
because it is a **purer availability discriminator** — `season_ppg` conflates availability with
scoring rate (a benched player and a playing-but-poor player both accumulate low PPG, for
different reasons), whereas `minutes_roll3` isolates availability cleanly. GK's 77.6% zero-minutes
share is also why GK shows the largest margins: goalkeeper selection is very close to a pure
starter/backup classification problem, and the signal that classifies it best wins by the most.

**And it is why the win does not reach the squad.** The measured edge is real, and it is an edge
at correctly ranking the ~61% of the pool that a 15-man greedy constructor **never picks from**.
Under budget and club-cap constraints, the candidates at the top of the pool are near-certain
starters already — availability is precisely the dimension the constructor least needs help with.
The rho gain is concentrated in the discard region.

### 4.1 This directly explains C5's failure

`DESIGN.MD` §8.8 recorded C5 — which **already used `minutes_roll3`** — as beating C2 and C3 but
failing to separate from C1, at +3.13 pts/GW against sd 16.97. §8.8 correctly declined to
attribute the failure to fdr or to the new pair being weak, and concluded that "the season-PPG
floor is simply higher than a cheap composite of these signals reaches."

This survey supplies the mechanism. **Rho over the ex-ante pool and pts/GW over the selected squad
are not measuring the same thing**, and the gap between them is exactly the discard region
described above. C5 could carry a genuine, statistically solid rho advantage from `minutes_roll3`
and still fail on squad regret, with no contradiction between the two measurements — because the
advantage lives in a part of the pool the squad never reaches. Any future candidate that is
motivated by a rho improvement on this population is exposed to the same trap, and this is the
record of it.

---

## 5. Reconciliation with `DESIGN.MD` §8.8 on fdr

**The tension, stated plainly.** §8.8 concluded, reading C4's and C5's ablations together, that
"**fdr generalizes as a signal**." This survey measures `fdr_bin`'s rank correlation with next-GW
points as **essentially zero at every position** (§3.2), with CIs including zero throughout.

**The resolution: these are different questions, and this is not a contradiction.**

- **§8.8's claim came from a squad-level regret ablation** — remove the fdr term from a composite,
  rebuild the squad, and compare points-per-gameweek of the resulting squads. That measures fdr's
  marginal contribution *to a construction policy's output*, in combination with other terms,
  under budget and club-cap constraints.
- **This survey asks a rank-correlation question** — does `fdr_bin` alone order the ex-ante
  candidate pool by next-gameweek points, at the lag-1 forecasting horizon.

A term can shift squad composition in a useful direction — acting as a tie-breaker among
similarly-rated candidates, or shifting the club mix — without having any standalone rank
association with points. Nothing in §8.8 is invalidated, and no figure in it is amended here.

**But state the limit plainly: whatever the ablation was detecting, it was not a next-GW
point-prediction signal.** At the horizon Free Hit actually forecasts over, on the population it
actually selects from, `fdr_bin` carries no measurable rank information about points. Any future
argument that fdr should be included *because it predicts points* is not supported by this
measurement, and should cite §8.8's ablation mechanism explicitly rather than an unexamined
assumption of predictive power. §7.4's and §8.2's collinearity notes remain the other standing
caveats on fdr's role.

---

## 6. Honest assessment

**Signal quality is confirmed as the bottleneck, not combination method.**

Three findings drive that conclusion:

1. **The ceiling is low.** The best margin found anywhere is **+0.058 rho**, at one position, from
   a signal C5 already contained. Nothing available reaches a materially different regime, and
   five of the six positives sit in the +.032 to +.047 band (§3.3).
2. **The two genuinely untried signals are empty.** `was_home` and `fdr_bin` both measure zero at
   every position. The cheap, mart-native, Tier-A-accessible well that `DESIGN.MD` §7 flagged as
   possibly holding something unexploited **is now confirmed dry** — there is no untapped signal
   sitting in the mart waiting to be combined better.
3. **Everything that clears is an availability proxy**, and per §4 availability is the dimension a
   squad constructor operating near the top of the pool least needs help with.

### 6.1 The position-dependence caveat, named fairly

The combination-method reading is **not baseless**, and it would be dishonest to dismiss it.

GK genuinely behaves differently from the other three positions: it carries the highest baseline
rho (.7654), the three largest margins in the survey (+.0420 to +.0577), and it is the only
position where `recent_form_ppg` beats `season_ppg` at all. A position-blind composite — which is
what both C4 and C5 were — **would** have diluted any GK-specific weighting. §3.4's pooled-column
finding demonstrates the dilution concretely. **A position-aware recombination of existing signals
is a legitimate, cheap experiment**, and this survey is the evidence that would motivate it.

### 6.2 Why that caveat cannot carry the weight

**It is explicitly not a credible path to closing the gap.** C5 fell short of C1 by +3.13 pts/GW
against a per-gameweek sd of 16.97. Recovering that shortfall would have to come from position-
aware weighting of a signal C5 already contained, whose entire measured edge sits in the region of
the pool the constructor discards (§4). The arithmetic does not plausibly work, and this document
does not claim it does.

**The reading the evidence actually supports:** no cheap, already-available signal, at any
position, predicts next-gameweek points meaningfully better than season-PPG **in a way that
reaches the selected squad.** The one genuine position-specific effect (GK) is real, small, and
concentrated in exactly the dimension that constrains the constructor least.

---

## 7. What this leaves open

Two paths remain. **Neither is decided here** — both are `DECISION.md`-level calls for a future
session, and this document's only contribution to them is the measured evidence above.

1. **Source genuinely new signal not currently in the mart.** This survey establishes that the
   cheap mart-native options are exhausted: the untried ones are empty, and the ones that work are
   already in use. Any further improvement from *signal* has to come from data the repository does
   not currently hold. The cost of acquiring, governing and validating external data is not
   assessed here.
2. **Restructure the prediction problem — separate "will play" from "will score well" as two
   distinct predictions** rather than one blended signal. §4 is the direct argument for this: every
   signal surveyed collapses those two questions into a single number, and the 61.4% zero-minutes
   base rate means the availability component dominates the blended measurement while contributing
   least at the point of selection. A two-stage formulation (P(play) x E[points | play]) would
   measure and use them separately. This is a structural change to the prediction problem, closer
   in cost to the deferred ILP/forecasting candidate than to a new composite, and is **not**
   specified, designed or costed here.

What this survey removes from the decision is the cheapest option: **"try harder to combine what
we already have" is no longer an open hypothesis with evidence behind it.** Both remaining paths
carry real cost, and the argument for either is now made against the numbers in §2 and §3 rather
than against an untested assumption that something cheap would have sufficed.

---

## 8. Provenance

**Read-only throughout.** No tracked file was created, modified or deleted by the measurement
pass itself. All measurement code was written to a session scratchpad directory outside the
repository and is not part of the repository; no code file in `decisions/free_hit/` or anywhere
else was touched to produce these figures. `decisions/starting_xi/` was not read from or written
to.

**Working tree confirmed unchanged** by `git status` before and after the pass: the same **42
pre-existing items** (40 modified, 2 untracked), with nothing added, staged or removed by the
measurement work.

**What the write-up pass added, separately from the measurement.** This document itself (new,
untracked) and a twelve-line pointer paragraph appended to the end of `DESIGN.MD` — an addition at
EOF only, no deletions, no change to §1-§8's substance. That brings the tree to 44 items. Nothing
else was created or modified, and no code file was touched by either pass.

**Nothing was re-run or re-derived for this write-up.** This document transcribes a completed
measurement pass; the figures are as measured.

**One correction applied during transcription.** The original spoken report stated that a 0.05
threshold would leave "2 of 6" cells surviving. That was wrong — GK `recent_form_ppg`'s margin is
+.0466, below 0.05, so **1 of 6** survives (§3.3 records the corrected figure). No other figure
required correction.

**Environment note.** The measurement ran under heavy machine contention (load average >45 from 51
leaked editor-spawned CLI processes, 6.2 GB of 7 GB swap in use). Thirty stale processes were
cleared with explicit approval before the pass completed. This affected **wall-clock runtime only**
— the bootstrap is seeded (seed 42) and deterministic, and no figure above depends on it.
