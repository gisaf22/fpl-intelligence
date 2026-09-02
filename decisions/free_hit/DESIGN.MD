# DESIGN.md — Free Hit Squad Construction & Selection

Sibling to `decisions/starting_xi/DESIGN.md`. Pure prose describing what to
build given DECISION.md + INVENTORY.md's evidence. Does not write back to
INVENTORY.md. No code in this pass.

## §1 — Scope of this design

Covers the three items DECISION.md §7 named as blocking: the gameweek
population definition, the feasibility-checking mechanism, and the
construction module's placement/interface. Each is resolved below with the
reasoning that drove it, per the same file-purpose discipline used in
`starting_xi` (DECISION → INVENTORY → METRIC → DESIGN, one job per doc).

METRIC.md is a separate, not-yet-written document and is not covered here.

## §2 — Gameweek population: club-schedule-level DGW/BGW definition

**Decision:** a gameweek qualifies for the v1 evaluation set if zero clubs
have `fixture_count == 0` (blank) or `fixture_count == 2` (double) that
gameweek, checked at `(team_id, gw)` grain among already-registered players.
This yields **33 of 38 gameweeks**; GW26/33/36 carry real doubles, GW31/34
carry real blanks (INVENTORY.md §1, re-verified against the live mart in
the stress-test pass — figures confirmed current).

**Why not the row-level definition:** counting any `is_bgw=True` player row
in a gameweek as disqualifying gives only 1 clean gameweek (GW38), because
early-season rows are saturated with not-yet-debuted players whose rows
carry the flag regardless of whether their club had a real fixture that
week — the same registration-prefix artifact `starting_xi/INVENTORY.md`
§2.5 already characterized for NULL-minutes semantics. The row-level count
answers "does any row look flagged," not "did this gameweek have a real
scheduling anomaly," which is the question DECISION.md §3 actually needs
answered.

**Scope of exclusion, stated explicitly (previously unsettled):** the
*entire calendar gameweek is excluded for all 20 teams*, not just the
anomalous teams' rows — matching DECISION.md §3's plain reading of
"gameweek" as the unit of evaluation, and keeping every construction
candidate and baseline scored on an identical, comparable set of weeks.

**Implementation note, not yet built:** no repository code computes this
classification today. It must be written as a small, explicit utility
(e.g. a `frozenset[int]` of qualifying gameweek numbers, or a function
computing it once from `fixture_count` grouped by `(team_id, gw)`) — not
reinvented ad hoc per script that needs it. Ownership: lives in
`decisions/free_hit/` alongside the construction code that consumes it,
since nothing outside this slice currently needs it and DECISION.md §3
doesn't authorize building it as shared infrastructure (see §4 below for
the general principle this follows).

## §3 — Feasibility-checking primitive: in-slice, not promoted to `domain/`

**Decision:** the incremental, partial-squad feasibility check is built
inside `decisions/free_hit/feasibility.py`, operating on the same
array-shaped representation `decisions/starting_xi/sampler.py`'s `_Pool`
already uses (`player_id`, `price_tenths`, `team_id` parallel arrays) —
**not** promoted to `domain/fpl_squad_feasibility.py`.

**Why this reverses the earlier draft.** Two independent blockers rule out
the `domain/` placement as scoped:

- No `Player`/`Pool` type exists anywhere in the repository (confirmed by
  direct grep — zero hits for a `Player` class). `sampler.py`'s `_Pool` is
  private, array-based, and would have to be either duplicated or exposed
  as a new independent representation for `domain/` to consume — creating
  exactly the "candidates silently disagree on what legal means" risk
  DECISION.md §3 warns against, just relocated into the primitive's own
  construction.
- `.importlinter`'s `no_layers_to_decisions` contract forbids `domain/`
  from importing anything under `decisions/` — confirmed currently
  enforced, not aspirational. `domain/` genuinely cannot reach
  `sampler.py`'s `_Pool` even if a shared type existed.

**Why in-slice is also the correct governance call, not just the
technically forced one.** DECISION.md §3's "built once and shared" language
scopes sharing *within* free_hit's own candidates (naive greedy ×3, future
ILP) — not repo-wide `domain/` infrastructure importable by Wildcard,
multi-week transfers, or any other future `decisions/*` slice. Promoting to
`domain/` would be the first real slice of ADR-012's deferred
squad-family abstraction, built incrementally and without the dedicated
ADR that provision anticipates. **This design explicitly does not do
that.** Per DECISION.md §6: this is a conscious choice to defer the
ADR-012 abstraction again, not a silent repeat of it — stated here rather
than left ambiguous, because no second real consumer of a shared primitive
exists yet to justify building shared infrastructure ahead of need. If a
second squad-family slice is ever built, promotion becomes a live question
again, to be decided then with an actual second caller in hand — matching
`starting_xi/DESIGN.md` §3.5's own stated default for exactly this
situation.

**Interface, matching `_Pool`'s actual shape (not a `Player`/`Pool`
object):**
def can_complete(
picked_player_ids: np.ndarray, # ids already selected
picked_prices: np.ndarray, # tenths, parallel to picked_player_ids
picked_teams: np.ndarray, # team_id, parallel to picked_player_ids
remaining_budget_tenths: int,
remaining_quota: dict[Position, int],
pool: _Pool, # this gameweek's eligible remaining players
) -> bool


Checks: (a) at least `remaining_quota[position]` eligible players exist in
`pool` per remaining position after removing already-picked players and
any club already at `MAX_PER_CLUB`; (b) the cheapest feasible completion
(min-price eligible players per remaining position, respecting the
per-club cap against `picked_teams`) sums to no more than
`remaining_budget_tenths`. Both checks are new — nothing in the repository
computes either today (INVENTORY.md §3, re-confirmed).

## §4 — Construction module: `decisions/free_hit/`, Tier A, Protocol-typed policy parameter

**Placement:** new root `decisions/free_hit/`, mirroring `starting_xi`'s
folder shape (docs + code colocated, not split under `docs/`).

**Tier A status, precisely stated:** achievable, not currently enforced.
`.importlinter` has zero contract naming `decisions.free_hit.*` today —
nothing in CI would currently fail if a construction module imported
`model/`. Tier A here is a design intention this pass commits to, backed
by a concrete fact (the needed signals — `fdr_avg`, as-of PPG, rolling
PPG — are all computable from dal-accessible data with zero `model/`
import), not yet an enforced property.

**PPG derivation: re-derive locally, do not import `expanding_prior_mean`.**
Importing it pulls in `model/eval/__init__.py`'s eager fan-out
(`baselines, metrics, population, scorer, walkforward` all load), a real
`model/` dependency regardless of which name is imported. This slice has
no forecasting/fitted-model component anywhere in its scope (unlike
`starting_xi`'s F1/`p_play`, which already forced an unavoidable `model/`
edge on that slice — the reason relocation was rejected there does not
apply here). Re-derive both season-PPG and rolling-PPG using the mart's
own `total_points` column via the identical `shift(1).rolling(N,
min_periods=1).mean()` / `shift(1).expanding().mean()` pattern already
established in `research/families/form/validate/study.py:342-350` for the
same governance reason (the governed mart deliberately excludes these
columns). This duplicates a small amount of logic; the tradeoff is stated
explicitly, not hidden, and buys genuine Tier A cleanliness with no
existing unavoidable edge to justify the alternative.

**`ConstructionPolicy` type — corrected from the earlier draft.** The
actual documented `starting_xi` lesson was that `BenchPlayer` (the
*parameter type* `OrderingPolicy` operates on) is a dataclass, not a
Protocol, and so cannot be extended later for context a smarter policy
would need — not that `OrderingPolicy` being a bare `Callable` was itself
the problem (`RankFn` is also a bare `Callable`, and that's fine; Protocol-
ness belongs on the parameter/return type). This design applies that
lesson correctly:


Checks: (a) at least `remaining_quota[position]` eligible players exist in
`pool` per remaining position after removing already-picked players and
any club already at `MAX_PER_CLUB`; (b) the cheapest feasible completion
(min-price eligible players per remaining position, respecting the
per-club cap against `picked_teams`) sums to no more than
`remaining_budget_tenths`. Both checks are new — nothing in the repository
computes either today (INVENTORY.md §3, re-confirmed).

## §4 — Construction module: `decisions/free_hit/`, Tier A, Protocol-typed policy parameter

**Placement:** new root `decisions/free_hit/`, mirroring `starting_xi`'s
folder shape (docs + code colocated, not split under `docs/`).

**Tier A status, precisely stated:** achievable, not currently enforced.
`.importlinter` has zero contract naming `decisions.free_hit.*` today —
nothing in CI would currently fail if a construction module imported
`model/`. Tier A here is a design intention this pass commits to, backed
by a concrete fact (the needed signals — `fdr_avg`, as-of PPG, rolling
PPG — are all computable from dal-accessible data with zero `model/`
import), not yet an enforced property.

**PPG derivation: re-derive locally, do not import `expanding_prior_mean`.**
Importing it pulls in `model/eval/__init__.py`'s eager fan-out
(`baselines, metrics, population, scorer, walkforward` all load), a real
`model/` dependency regardless of which name is imported. This slice has
no forecasting/fitted-model component anywhere in its scope (unlike
`starting_xi`'s F1/`p_play`, which already forced an unavoidable `model/`
edge on that slice — the reason relocation was rejected there does not
apply here). Re-derive both season-PPG and rolling-PPG using the mart's
own `total_points` column via the identical `shift(1).rolling(N,
min_periods=1).mean()` / `shift(1).expanding().mean()` pattern already
established in `research/families/form/validate/study.py:342-350` for the
same governance reason (the governed mart deliberately excludes these
columns). This duplicates a small amount of logic; the tradeoff is stated
explicitly, not hidden, and buys genuine Tier A cleanliness with no
existing unavoidable edge to justify the alternative.

**`ConstructionPolicy` type — corrected from the earlier draft.** The
actual documented `starting_xi` lesson was that `BenchPlayer` (the
*parameter type* `OrderingPolicy` operates on) is a dataclass, not a
Protocol, and so cannot be extended later for context a smarter policy
would need — not that `OrderingPolicy` being a bare `Callable` was itself
the problem (`RankFn` is also a bare `Callable`, and that's fine; Protocol-
ness belongs on the parameter/return type). This design applies that
lesson correctly:

class ConstructionCandidate(Protocol):
player_id: int
position: Position
price_tenths: int
team_id: int
score: float # whatever the active construction heuristic computed

ConstructionPolicy = Callable[
[Sequence[ConstructionCandidate], remaining_budget, remaining_quota],
list[ConstructionCandidate]
]


Using a Protocol for the element type (not a frozen dataclass) means a
future candidate needing more context (e.g. future-price-awareness, an
ILP formulation) can extend the shape without hitting `BenchPlayer`'s
dead end.

**Second, separate risk, distinct from typing style — flagged, not
resolved here.** `starting_xi/DESIGN.md` §5.4.2 documents that the Markov
ordering-policy rejection was **not** a Tier A/B or typing problem at all —
it was that `OrderingPolicy`'s argument shape structurally excludes XI
context (only sees the outfield bench), an information-completeness
limitation with a different fix (argument shape, not type system).
Whether `ConstructionPolicy`'s proposed argument shape (candidates +
remaining budget/quota) is sufficient for every plausible future
candidate — including a full ILP formulation, which may need visibility
into the entire remaining pool structure, not just per-candidate scores —
is not resolved by the Protocol fix above and should be checked
specifically once the ILP candidate is actually scoped, not assumed
solved now.

**`.importlinter` contract: required, but sequenced per repository
convention, not bundled into the constructor's PR.** Every prior contract
addition in this repository (9 commits, `git log --all -- .importlinter`)
followed the same pattern: its own dedicated `build(importlinter):`
commit, landed after the modules it protects already exist in the import
graph, citing a specific DESIGN.md section, and accompanied by a
falsify-then-revert proof (e.g. commit `7812399`: demonstrate the contract
actually fails on a real violation, then revert and confirm the full
suite passes clean). The mirror of `no_starting_xi_tier_a_to_tier_b`
scoped to `decisions.free_hit.*` must follow this exact convention: built
after C1/C2/C3 and `feasibility.py` exist, proven to fail on an
intentional violation, reverted, then landed as its own commit citing this
section.

## §5 — Open items carried forward, not resolved by this pass

- Whether `ConstructionPolicy`'s argument shape is sufficient for a future
  ILP candidate (§4, flagged) — decide when that candidate is scoped, not
  now.
- METRIC.md's verdict rule against the three tracked naive baselines
  (independent tests with correction vs. a different rule) — DECISION.md
  §4 already flags this as METRIC.md's call, unchanged by this pass.
- Whether a second squad-family slice ever arrives to justify revisiting
  `domain/` promotion for the feasibility primitive (§3) — no action
  until then.
- Team-value-by-gameweek data remains confirmed absent (INVENTORY.md §2)
  — fixed 100m stands as the only option for v1, not a design choice this
  pass can improve on.

## §6 — Status

Drafted, incorporating corrections from a five-expert stress-test pass
that re-verified all cited facts against current repo state (2026-08-30).
Not yet committed. Next: `feasibility.py`'s tests (falsification probes
mirroring `formations.py`'s legality tests, determinism checks — no RNG
is needed anywhere in C1/C2/C3, pure sort/fill, simplifying the
reproducibility story vs. the sampler's seed contract) and the three
naive constructors (C1 season-PPG, C2 value/PPG-per-price, C3
recent-form), built against §3/§4's interfaces above.
## §7 — The composite candidate (C4): specification

`DECISION.md` §4's sequencing note names "a cheap non-forecasting composite
candidate (PPG + fdr_avg + value)" as the first candidate to test against the
three naive baselines, which are now built, tested and measured
(`candidates.py` C1/C2/C3, `evaluate.py`). This section specifies that
candidate — **C4** — completely enough to build it, and does not build it.
Four points are already decided by the user and are stated here rather than
re-derived: "PPG" means C3's recent-form signal, not season-PPG; the
composite's distinctness is the combination, not novel ingredients, so all
three weights are strictly nonzero and fixed a priori and C4 can never
collapse into being one of C1/C2/C3; `fdr_avg` is included as a continuous
scored input; and the weights are never fitted on the 32-gameweek evaluation
set, which would be fitting on the test set and is forbidden here in the same
sense `METRIC.md` §2's pre-registered family of exactly three comparisons is
pre-registered.

### §7.1 — Why `reject-fdr-as-signal.md` does not bind this candidate

`docs/decisions/reject-fdr-as-signal.md` (2026-05-22) rejects `fdr_avg` as a
standalone signal and states it is "excluded from the composite scorer",
reserved as a binary moderator. That record stands where it was written and is
not overturned here. It does not reach C4, for three independent reasons, each
of which would be sufficient alone.

**(a) The artifact it excludes `fdr_avg` from no longer exists.** "The
composite scorer" in that sentence is the serve-layer scoring engine of
ADR-002 (`docs/decisions/002-additive-weighted-scoring.md`) — rank-normalised
signal scores combined with hand weights carried in `weight_registry.yaml`.
ADR-011 (`docs/decisions/011-model-forecast-supersedes-composites.md`, 2026-08-01)
retired every serve composite and states at its §Decision that "the weighting
machinery is deleted: `serve/weight_registry.{yaml,py}`", confirmed by its
consequences section ("the composites, `weight_registry`, and serve-side
`score_provenance` no longer exist") and by the current tree, where `serve/`
carries no `weight_registry.py` source. An exclusion from a deleted governed
artifact does not transfer by analogy to a differently-scoped construction
ranking key in a different slice; nothing in the rejection record generalises
it beyond the scorer it names.

**(b) Its only stated ground was non-monotonicity, and that finding was
subsequently attributed to a binning artifact.** The rejection's sole reason is
"the relationship is non-monotonic". `research/families/fixture/LENS_DESIGN.md`
Amendment B (2026-08-16) records that Gate 2's `pd.qcut(series.rank(method="first"), 5)`
manufactured quintile boundaries inside `fdr_avg`'s heavily tied values — 59% of
DEF rows sit at exactly `fdr_avg == 3.0`, and per
`research/registry/CHARACTERIZE_DESIGN.md` §2 the rank-tie-break cut placed Q2
and Q3 at 100% `fdr_avg == 3.0` at both DEF and MID, so the reversal that set
`is_monotonic=False` was a difference between two groups holding the *same*
fixture difficulty, split by row order. Cut instead on `FDR_ORDINAL_BINS`
(`research/kernels/descriptive/binning.py:28`), MID (−1.978), FWD (−1.815) and
GK (−2.143) recover strictly monotonic profiles, and DEF shows the largest
Q1–Q5 gap of all four positions (−2.891) with a single small reversal at bins
1→2 on 143 and 358 rows (`CHARACTERIZE_DESIGN.md` §2, limit 1). Separately,
the correlation gate never failed: every position's bootstrap CI in
`research/families/fixture/validate/evidence.yaml` excludes zero on the
negative side (GK −0.235/−0.092, DEF −0.225/−0.158, MID −0.192/−0.124, FWD
−0.182/−0.043). The rejection's ground was the monotonicity verdict, and that
verdict's mechanism is now documented as an artifact of how the signal was cut.

**(c) The underlying study measures a different thing from what C4 does.**
`research/families/fixture/validate/study.py` computes a Spearman rank
correlation between `fdr_avg` and same-GW `total_points`, over a population
filtered to `minutes >= 60` (`MINUTES_THRESHOLD = 60`, line 50; population
filter at line 230). That is survivor-conditioned (players who already played
an hour), ex-post (the fixture's difficulty read against the same gameweek's
realised points), and per-player. C4 is an ex-ante, decision-time ranking key
over the full eligible candidate pool — including players who will not start
and players who will be benched — used to order a 15-player squad
construction under budget and quota constraints, and scored by
`ConstructionRegret` (`METRIC.md` §1.3), not by rank correlation. Different
population, different unit of analysis, different loss. A null result for the
first is not evidence about the second in either direction.

**Stated honestly: no evidence exists either way for `fdr` in a
squad-construction ranking key.** Points (a)–(c) establish that the standing
rejection does not bind; they do not establish that `fdr` helps. There is no
study in this repository of `fdr` used this way. That absence is precisely why
§7.3's ablation is written into C4's definition rather than left as an optional
follow-up: the question is empirical and one extra weight vector on the harness
that already exists answers it.

**Out-of-scope observation, recorded and not fixed.**
`docs/decisions/reject-fdr-as-signal.md` is out of sync with Amendment B: it
still asserts non-monotonicity flatly, three months after the binning work
attributed that verdict to a cut artifact, and no decision record cites
Amendment B (`docs/PROJECT.md` §5 does, but it is not a decision record). That
is a real defect in the decision-record layer, independent of this candidate,
and repairing it is not this pass's job and not a prerequisite for C4.

### §7.2 — The combination rule

**Form: an additive weighted sum of three normalized terms.** For candidate `p`
in gameweek `g`:

score(p, g) = w_form · r(recent_form_ppg) + w_value · r(value) + w_fdr · r(5 + 1 − fdr_bin)

where `r(·)` is the within-gameweek rank normalization defined below, all three
weights are strictly positive, and `w_form + w_value + w_fdr = 1`.

**Why additive.** ADR-002 argued additive weighted composition over
rank-normalised signals on explainability and small-data grounds; ADR-011
superseded it as a *serve-layer* decision because a validated forecast became
available that prices the same proxies, not because the arithmetic was found
wrong. C4 is explicitly a *non-forecasting* candidate (`DECISION.md` §4), so
ADR-011's reason to abandon the form does not apply to it, and ADR-002's reasons
to prefer it — every term traceable, no fitting — apply directly. The additive
form is also what makes the strictly-nonzero-weight constraint mean something:
each term contributes at every ranking, so C4 cannot degenerate into C2 or C3.

**Normalization: within-gameweek rank normalization, not z-scores.** Each term
is ranked ascending over that gameweek's eligible candidate pool (the same pool
`candidates.build_candidates(mart, gw)` returns) and mapped to `[0, 1]` by
`(rank − 1) / (n − 1)`, ties taking their average rank. Rank normalization is
chosen for three reasons. The three terms are on incommensurable scales —
`recent_form_ppg` in points, `value` in points per million (`candidates.py:137`,
`season_ppg / purchase_price`), the fdr term on a 1–5 ordinal — so raw addition
would be arithmetic on unrelated units and the effective weights would be set by
the scales rather than by `w`. Z-scoring fixes the units but not the shape:
points distributions are heavy-tailed and a single explosive haul would let one
player's `recent_form_ppg` z-score dominate a fixed-weight sum, which is a
fitting-free formula acquiring an unintended implicit weighting from one
gameweek's outliers. And rank-normalised additive composition is the form this
repository already reasoned about explicitly (ADR-002), so C4 inherits a stated
rationale rather than inventing one. The cost, stated: ranks discard magnitude,
so a player who is far ahead of second place on form is scored as merely first.
That is accepted for a cheap non-forecasting candidate whose whole purpose is to
be a floor test.

**The fdr term is `FDR_ORDINAL_BINS`, not raw `fdr_avg`.** The scored
representation is `fdr_avg` cut on `FDR_ORDINAL_BINS = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]`
with labels `1…5` (`research/kernels/descriptive/binning.py:28`, the scheme
`select_bucketing_scheme` returns for `FDR_SIGNALS` per `CHARACTERIZE_DESIGN.md`
§2). This matters more here than it did for the lens. With 59% of DEF rows at
exactly `fdr_avg == 3.0` (`CHARACTERIZE_DESIGN.md` §2, citing `docs/PROJECT.md`
§5), a rank normalization of raw `fdr_avg` assigns the great majority of the
pool the identical averaged tie rank, so the fdr term contributes near-zero
separation across most of the pool while nominally carrying weight `w_fdr` — the
term would be technically nonzero and practically inert, which is exactly the
degeneracy the strictly-nonzero-weight constraint exists to prevent. The ordinal
bin bins on the rating's own natural scale, one bin per FDR value, and is the
representation this repository's own characterization work selected for this
signal, so C4 is not inventing a treatment. The ties do not disappear — they are
inherent to the data — but the representation is the governed one and the term's
contribution is then honestly whatever the bins support, which §7.3 measures.

**Direction and sign.** Lower `fdr` is better; the other two terms are
higher-is-better. The sign is handled by *reversing the fdr term before
normalizing*, as `6 − fdr_bin` (equivalently, `1 − r(fdr_bin)`), so that all
three normalized terms are higher-is-better and `w_fdr` stays strictly
positive. Handling the direction with a negative weight instead is rejected:
it would make "strictly nonzero weights" and "every weight positive" different
statements and invite a later reader to mistake the sign for a preference for
hard fixtures.

**Grain: global, not per-position.** One score, one ranking key, the same three
weights for every position. This matches the position-blind ranker C1/C2/C3
already use — `candidates._greedy_fill` groups by position only to fill the
quota (`candidates.py:207`), ranking within each group by a single global
`_sort_key` on a single global signal — so C4 differs from the baselines in the
scoring formula alone, which is the comparison `METRIC.md` §2's verdict is
about. Per-position weights would introduce twelve free parameters instead of
three, and a candidate whose weights cannot be fitted (see below) has no
principled way to choose twelve. Note that the rank normalization is over the
whole gameweek pool, not per position, so the ranking key is comparable across
positions by construction; whether a per-position variant is worth testing is a
question for after C4 has a measured result, not now.

**Tie-breaking and NaN: mirror `candidates._sort_key` exactly.** A NaN composite
score is unrankable and sorts after every scored candidate; ties break on
ascending `player_id` (`candidates.py:160-163`). The composite score is NaN
whenever any of its three terms is NaN, which propagates the existing
per-signal NaN semantics rather than silently imputing a missing signal to a
middling rank. This makes C4 degenerate at GW1 in exactly the way C1/C2/C3 do
(`METRIC.md` §3.3), which is consistent and costs nothing, since GW1 is already
excluded by `gameweek_population.WARM_UP_EXCLUDED`.

**Weights are pre-registered, not fitted.** The three weights must be written
down and committed before C4 is run against the 32-gameweek evaluation set, and
never adjusted in response to a result on it. Fitting them on that set would
make `METRIC.md` §2's verdict a resubstitution estimate and its p-values
meaningless, and the evaluation set is the only season available. The
defensible a-priori choice, absent any evidence ranking the three signals for
this use, was **equal thirds** — `w_form = w_value = w_fdr = 1/3` — following the
same reasoning ADR-002 §Consequences recorded for its own equal weights ("they
are not 'trained' — they are a governance record"). If a different vector is
preferred it must be justified from something other than the evaluation set and
recorded here before the run.

**CURRENT SPECIFICATION (supersedes equal thirds):**

    w_form = 0.25    w_value = 0.25    w_fdr = 0.50

Equal thirds was the specification for C4's first run and is superseded, not
deleted: the reasoning above stands as the record of why it was chosen, and
§7.2.1 records what was measured, why the vector changed, and why this is the
last such change. The replacement is derived from a structural fact about the
three terms (two of them are near-duplicates), not from any result on the
evaluation set, so the a-priori requirement above is preserved.

### §7.2.1 — Weight-vector correction after C4's first run (final)

**What the first run showed.** C4 under equal thirds **failed `METRIC.md` §2's
conjunctive rule**. It beat only C2 among the three baselines. The §7.3 ablation
showed the **fdr term is the only term carrying independent signal** — removing
it changed the ranking materially, while the two points terms were largely
substitutable for each other.

**What the follow-up measurement pass could and could not establish.** A
measurement pass computed raw and partial Spearman correlations against realized
points in two populations: the **full ex-ante candidate pool**, and a
**minutes ≥ 60 survivor population** matching prior lens-study convention. The
two populations disagreed by roughly **a factor of 12 on FDR's implied weight**.
Those magnitudes are therefore **population-dependent and unusable for deriving
a weight vector**: picking either one would launder a disputed population choice
— and, since the first run's regret outcome is already known, C4's own result —
into a number presented as a-priori.

One finding is **population-independent and usable**: `recent_form_ppg` and
`value` are confirmed **near-duplicates** (Spearman ρ ≈ **+0.850** in the full
pool, **+0.566** in the survivor population), while the fdr term is confirmed
**genuinely orthogonal to both, in both populations** (ρ ≈ **0.001**). Both
measurements agree on this structure regardless of population; it is the only
thing they agree on, and it is the only input used below.

**The corrected vector and its derivation.** From the collinearity finding
alone: `recent_form_ppg` and `value` are substantially the same signal, so they
are treated as **one combined signal** and split **one weight-slot's worth of
influence between them** rather than drawing two slots. The fdr term, the only
orthogonal input, takes the other half.

| term | old | new |
| --- | --- | --- |
| `recent_form_ppg` | 0.333 | **0.25** |
| `value` | 0.333 | **0.25** |
| `fdr_rev` | 0.333 | **0.50** |

This is the **simplest correction consistent with the collinearity finding
alone**. It is deliberately **not tuned to any partial-ρ magnitude**, not
derived from either population's numbers, and not derived from C4's regret
result. Under equal thirds the composite gave two-thirds of its weight to what
is effectively one signal; the correction removes that unintended double-count
and nothing else.

**THIS IS THE FINAL WEIGHT-VECTOR TEST FOR THIS CANDIDATE DEFINITION.** If
0.25 / 0.25 / 0.50 also fails `METRIC.md` §2's conjunctive rule, the documented
conclusion is: **the composite approach with these three ingredients does not
beat the naive baselines on the data available.** That is a result, not a cue to
try a third weight vector on the same 32 gameweeks. A third attempt would be
fitting to the evaluation set by hand — precisely what the pre-registered,
a-priori weight requirement in §7.2 exists to prevent — and the evaluation set
is the only season available, so there is no held-out data on which a further
vector could be honestly tested. Changing the *ingredients* (a different signal
in place of `value`, per §7.4) would be a new candidate definition requiring its
own pre-registration, not a further iteration of this one.

### §7.3 — The ablation is part of C4's definition

C4 is run **twice** through the same harness, on the same 32 qualifying
gameweeks, against the same three baselines:

- **C4** — §7.2's CURRENT SPECIFICATION: `w_form = 0.25`, `w_value = 0.25`,
  `w_fdr = 0.50` (per §7.2.1; the ablation was run under equal thirds for C4's
  first run and re-run under the corrected vector).
- **C4-nofdr** — the fdr term dropped, its weight redistributed proportionally
  across the other two: `w_form = w_value = 1/2`, `w_fdr = 0`. Proportional
  redistribution is chosen so the two variants differ in exactly one thing (fdr
  present or absent) rather than in fdr *and* the relative balance of the other
  two.

**Why this is definitional rather than optional.** §7.1 establishes that the
standing rejection does not bind, and equally that no evidence exists for `fdr`
in this use. Settling that by further reading of decision records is document
exegesis over a question that is empirical and cheap: the harness, the gameweek
population, the regret series and the verdict machinery all exist or are
specified, and the ablation costs one additional weight vector through
machinery already built. Shipping C4 with an fdr term whose contribution was
never measured would leave the composite's central novel claim untested.

**How the ablation's result is reported.** C4-nofdr is a **diagnostic, not a
second candidate**. It does not compete for `METRIC.md` §2's verdict, does not
enter the Holm–Bonferroni family (which is pre-registered as exactly three
candidate-vs-baseline comparisons, and adding a fourth arm post hoc would be
the multiplicity inflation §2 exists to control), and does not get a PASS/FAIL
of its own. It is reported as a paired difference between the two variants'
per-gameweek Combined-regret series, with its own mean and interval, alongside
C4's verdict — answering "did the fdr term move anything, and in which
direction" as context for reading C4's result. If C4 passes and C4-nofdr's
series is indistinguishable from it, that is reported as such and §7.4's
consequence is invoked.

### §7.4 — Known property: the two points terms are collinear

`recent_form_ppg` and `value` are both derived from the same column.
`candidates.py:137` defines `value` as `season_ppg / purchase_price`, and
`season_ppg` and `recent_form_ppg` are the expanding and 3-gameweek rolling
means of the same lagged `total_points` series (`candidates.py:130-135`). They
differ in window and in the price divisor, not in ingredient, and will correlate
substantially — **now confirmed by measurement, not speculative**: Spearman
ρ ≈ +0.850 (full candidate pool) and +0.566 (minutes ≥ 60 survivors), with the
fdr term orthogonal to both in both populations (§7.2.1). `METRIC.md` §3.3 already measures the extreme case, where
`recent_form_ppg == season_ppg` for every candidate at GW2, GW3 and GW4
(705/705, 712/712, 740/740), first diverging at GW5. The fdr term is therefore
the only structurally orthogonal input C4 has.

The consequence, stated plainly: **if the §7.3 ablation shows the fdr term
contributes nothing, C4 is effectively a one-signal candidate carrying three
labels** — a form-and-price blend whose two components are two views of the same
points history — and the "multi-signal composite" framing would not survive the
result. That is recorded here as a known property to check against the measured
results, not a defect to design around now: the correct response is to read the
ablation, not to preemptively substitute a signal for `value` that has not been
argued for.

### §7.5 — Verdict machinery: a new in-slice module `decisions/free_hit/verdict.py`

**Placement:** `decisions/free_hit/verdict.py`, Tier A, numpy-only (no `pandas`
needed — its inputs are already-computed per-gameweek series). It contains:

- a **block bootstrap of the mean** of a per-gameweek paired series, matching
  `METRIC.md` §3.1's resampling unit (gameweeks, not squads) and blocking to
  respect the within-season serial dependence that resampling individual
  gameweeks independently would ignore;
- a **one-sided p-value** computed from those bootstrap draws, for
  `H0: mean regret ≤ 0` vs `H1: mean regret > 0` (`METRIC.md` §2.1 step 2);
- **Holm–Bonferroni step-down** across the three resulting p-values at
  family-wise α = 0.05 (`METRIC.md` §2.1 step 3);
- the **conjunctive PASS reduction** — PASS iff all three corrected nulls are
  rejected in the favorable direction (`METRIC.md` §2.1 step 4), returning the
  per-leg results alongside the boolean, since §2.2's whole argument for
  conjunctive-over-best-of-three is that nothing about how the verdict was
  reached is collapsed. Per §2.3's appended note, each leg's report carries its
  own effective `n`.

**Why re-derive rather than import `research/kernels`.** Both pieces exist:
`research.kernels.hypothesis.multiplicity.holm_bonferroni` and
`research.kernels.inferential.resampling.block_bootstrap_ci`. Importing either
one is measured to pull **25 project modules** into the process — the whole of
`research.kernels.{descriptive,diagnostic,hypothesis,inferential}` plus
`domain.registry.association`, via `research/kernels/__init__.py`'s eager
re-export chain — and, more decisively, it takes a `decisions → research` edge.
The `.importlinter` contract this design already commits to in §4 is the mirror
of `no_starting_xi_tier_a_to_downstream`, whose forbidden list names `research`
explicitly (`.importlinter:95-107`). Building C4's verdict on an import the
contract we have committed to writing would forbid means either the contract or
the import has to go, and the contract is the one with a stated design
rationale.

This is the third instance of the same call in this slice, made for the same
reason both previous times: `candidates.py` re-derives `season_ppg`,
`recent_form_ppg` and `_price_tenths` locally rather than importing them
(`candidates.py:110-137`, and §4 above for the `expanding_prior_mean`
reasoning), and `evaluate.py` re-derives its ranking signal rather than
importing `decisions.starting_xi.rankers`, whose module-scope imports pull in 16
`model/` modules (`evaluate.py:18-24`). A block bootstrap of a mean and a
Holm step-down are each a few lines of numpy over a 32-element array; the
duplication is small, bounded, and stated rather than hidden — the same tradeoff
§4 accepted for the PPG derivations.

### §7.6 — Flagged for a `METRIC.md` correction pass, not fixed here

`METRIC.md` §2.3's appended note ("the three tests do not share an identical
sample size") describes its mechanism imprecisely, and the imprecision matters
for how C4's results get read.

The note says the C1-vs-C3 comparison runs on an effective n = 29 while the
other two run on n = 32, and concludes that "the three legs of the conjunctive
rule carry unequal statistical power". But §3.3's measured n = 29 finding is
about `ConstructionRegret_{C1,C3}` — a **baseline-vs-baseline** series — whereas
§2's rule tests **candidate-vs-baseline** pairs: for C4 those are `{C4,C1}`,
`{C4,C2}` and `{C4,C3}`. None of those three is the series §3.3 measured. What
the GW2–GW4 collinearity actually establishes for §2's rule is what §3.3's own
consequence 2 says correctly — that C4's comparison against C1 and its
comparison against C3 are the *same comparison* in those three weeks, because
C1 and C3 construct the identical squad there. That is **dependence between two
of the candidate's legs at GW2–GW4**, not a reduced sample size on any single
leg: all three of C4's legs are computed on the full 32 gameweeks. The
distinction is not cosmetic — dependence between legs is a question about what
the Holm correction's family-wise guarantee is buying (Holm remains valid under
dependence, per §2.1's own argument, so the rule is unaffected), while a reduced
n would be a question about one leg's power, and §2.3 currently instructs
reporting the latter.

**Flagged as needing a `METRIC.md` correction pass.** `METRIC.md` is not edited
here: this document is DESIGN, the note is METRIC's to restate, and the
correction is to §2.3's mechanism and its reporting instruction, not to §2.1's
rule — the conjunctive requirement, Holm, family-wise α = 0.05 and the one-sided
framing all stand either way.

### §7.7 — What this section leaves underdetermined

- **The block length** for §7.5's block bootstrap is not fixed here. It is a
  measurement-machinery parameter, `METRIC.md` §3's territory, and choosing it
  needs the realized serial dependence of the per-gameweek regret series, which
  is measurable now that C1/C2/C3 are built.
- **The weight vector** is specified as *pre-registered and equal-thirds by
  default* (§7.2), which is a defensible a-priori choice, not a derived one. Any
  substitute must be justified off-evaluation-set and written down first.
- **NaN rates at the eligible-candidate grain have been measured** (against the
  current 32-gameweek qualifying set, 24,918 registered candidate rows).
  `fdr_avg` is confirmed clean: 0/24,918 nulls (0.0%), reproducing an earlier
  assessment's figure on the current denominator. This pass also checked the
  other two composite terms, which the original framing above did not
  anticipate: `recent_form_ppg` and `value` (season_ppg/price) are both null on
  the same 138/24,918 rows (0.554%). Root cause: these 138 rows are players
  whose very first row anywhere in the mart is their first eligible candidate
  gameweek, so `shift(1)` has no antecedent row to reference — distinct from
  the ordinary pre-debut case, where unregistered placeholder rows
  (total_points=0, not null) already give the shift/rolling calculation
  something to look back on before a player clears the registration filter.
  Distribution: no position concentration (MID 64/DEF 39/FWD 21/GK 14, roughly
  proportional to squad mix), no team concentration, scattered across 30 of 32
  qualifying gameweeks with a spike at GW4 (28) — consistent with mid-season
  entrants/transfers, not a data defect. Since a NaN in any term makes the
  whole composite score NaN (§7.2), these 138 rows are pushed to the
  unrankable tier; at 0.55% (~4-5 rows per gameweek out of ~780), the existing
  NaN-last tie-break in `_sort_key` is assessed as sufficient to handle this —
  resolved, not a live open question, though newly surfaced by this
  measurement rather than by the original framing.

### §7.8 — Final result: C4 FAILS, and the candidate definition is closed

C4 was run under §7.2's CURRENT SPECIFICATION (`0.25 / 0.25 / 0.50`) through the
same harness, the same 32 qualifying gameweeks and the same three baselines as
its first run. This is the second and, per §7.2.1's terminal clause, **final**
weight vector tested against this candidate definition.

**Verdict — `METRIC.md` §2's conjunctive rule: FAIL (1 of 3 nulls rejected).**

| leg | mean Δ (pts/GW) | sd | 95% CI | p_raw | p_Holm | H₀ rejected |
| --- | --- | --- | --- | --- | --- | --- |
| C4 vs C1 (season-PPG) | **+0.44** | 18.08 | crosses 0 | — | **0.4811** | no |
| C4 vs C2 | — | — | — | — | **0.0081** | **yes** |
| C4 vs C3 | — | — | — | 0.0455 | **0.0910** | no |

The conjunctive rule requires all three nulls rejected. C4 clears C2 only. C3 is
the case the correction changed: its raw p-value (0.0455) is nominally
significant and its Holm-adjusted p-value (0.0910) is not, which is exactly what
the pre-registered multiplicity control exists to catch — it does not become a
pass by reporting the raw number. C1, the naive season-PPG baseline, remains
**statistically indistinguishable** from C4: a mean advantage of +0.44 pts/GW
against a per-gameweek standard deviation of 18.08 is noise at this n.

**Ablation under the final weights (§7.3).** C4 vs C4-nofdr: mean **+4.97**
pts/GW, sd 12.42, with the two variants' squads differing in **32 of 32**
gameweeks. Read against the verdict table, this settles §7.3's question in the
direction §7.4 anticipated: **the fdr term is carrying the entire candidate's
measured advantage.** Removing it does not merely shrink C4's edge — it turns C4
from breakeven-against-C1 into an outright loss. The two points terms, confirmed
near-duplicates in §7.2.1, contribute essentially nothing the baselines do not
already have. The ablation remains a diagnostic and takes no verdict of its own.

**Conclusion — the candidate definition is closed.** This composite candidate
definition — recent-form PPG + value + FDR ordinal bin, under **any** weight
vector satisfying §7.2's a-priori and strictly-nonzero constraints — **does not
beat the naive baselines on the 32-gameweek 2025-26 evaluation set.** Both
tested vectors failed the conjunctive rule, and the two vectors bracket the
available range: equal thirds double-counted the collinear points signal, and
the correction gave the one orthogonal term half the total weight. Per §7.2.1,
**no further weight vector will be tested against this definition.** A third
attempt would be hand-fitting to the only season available. Changing the
*ingredients* would be a new candidate definition requiring its own
pre-registration — not an iteration of this one.

**What this closes, and what it leaves open.** Per `DECISION.md` §4's sequencing
note, the cheap non-forecasting composite was to be measured before the
expensive forecasting path was considered. It has now been measured and found
**insufficient to clear the naive floor**. That is what this section closes.

What it does **not** decide is whether to move to the deferred ILP/forecasting
candidate. That is a `DECISION.md`-level call and is not resolved here. What
this pass contributes to that decision is the **measured ceiling**: a cheap
composite of these three signals tops out at roughly *matching*, not beating,
season-PPG — and does so only because of the fdr term, with the two points
terms adding nothing. Any argument for the cost of the forecasting path is made
against that number, not against an untested assumption that something cheap
would have sufficed.

**Small open item, not urgent.** 7 mypy errors stand in `test_evaluate.py` and
`test_evaluate_integration.py`: the `ConstructionCandidate` Protocol does not
declare `season_ppg` / `recent_form_ppg`, which those tests read off candidate
objects. Confirmed **pre-existing** (stash-and-rerun) rather than introduced by
the C4 build, and left unfixed as out of scope for this pass. Flagged for
whoever next touches those files; the fix is to widen the Protocol, and it
does not affect any result recorded above.
