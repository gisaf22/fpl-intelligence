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

## §8 — The second composite candidate (C5): specification

### §8.1 — C5 is a new candidate definition, not a revision of C4

C4 is closed. Its full record — §7.1 through §7.8, both tested weight vectors,
the ablation and the failed conjunctive verdict — stands unchanged and is not
reopened, amended or reinterpreted by this section. §7.2.1's terminal clause
forbids a third weight vector against C4's ingredients, and §7.8 restates the
only permitted route forward in its own words: "Changing the *ingredients*
would be a new candidate definition requiring its own pre-registration — not an
iteration of this one." That is exactly what this section is. C5 shares one
ingredient with C4 (`fdr_term`) and one arithmetic form (rank-normalized
additive weighted sum), and it is scored, run and judged as a separate
candidate against the same three naive baselines. Nothing measured about C5 can
retroactively pass or fail C4, and nothing in §7.8 pre-judges C5.

### §8.2 — The three ingredients

A follow-up assessment pass investigated `transfers_in` and minutes-rolling
signals as a genuinely different ingredient set. Its findings are cited here,
not re-derived; every number below comes from that pass.

**`recent_form_ppg` — DROPPED, replaced.** The assessment found
`minutes_roll3` is a near-duplicate of `recent_form_ppg` at Spearman **0.957**
— tighter than the **0.850** `recent_form_ppg`/`value` pair that §7.2.1
identified as C4's unintended double-count and §7.8 found contributed
essentially nothing. Head-to-head partial correlation against same-gameweek
`total_points` resolves the duplication in one direction only: `minutes_roll3`
**subsumes** `recent_form_ppg` (partial **0.224** vs **0.101**). Carrying both
would rebuild C4's exact failure mode at a worse correlation; carrying
`recent_form_ppg` instead of `minutes_roll3` would keep the weaker half of the
pair. So `recent_form_ppg` is dropped and `minutes_roll3` takes its place.

**`value` — DROPPED.** It is **0.855** collinear with `minutes_roll3`, i.e. it
reproduces against the new term the same near-duplication it already had with
`recent_form_ppg`, and §7.8's ablation under C4's final weights already found
C4's two points-derived terms "contribute essentially nothing" beyond the fdr
term. There is no measured basis for a third slot that is collinear with an
existing one and was already shown inert.

**`fdr_term` — CARRIED FORWARD UNCHANGED.** §7.2.1 confirmed the fdr term
orthogonal to both of C4's other terms in both populations (ρ ≈ 0.001), and
§7.8's ablation found it carrying the entire candidate's measured advantage.
The assessment confirms the same orthogonality against the new ingredient set:
approximately **0.00** with both `transfers_in` and `minutes_roll3`. Its
representation is unchanged from §7.2 — `fdr_avg` cut on `FDR_ORDINAL_BINS`,
scored as `6 − fdr_bin` — and §7.2's reasons for preferring the ordinal bin over
raw `fdr_avg` (the 59% DEF tie mass at `fdr_avg == 3.0`) apply here identically.

**`transfers_in` — NEW.** Partial Spearman against same-gameweek
`total_points`, controlling for C4's three existing terms: **+0.190**. It is
confirmed **leakage-safe**: it is pre-deadline crowd state, not a
forward-looking quantity. It is Tier-A accessible as a raw governed mart
column, with **0.000%** NaN at the eligible-candidate grain. One property must
be stated with it: its validated lens-study finding (DEF ρ 0.192, MID 0.184)
measures a **different question** than C5 asks — next-gameweek returns on a
`minutes >= 60` survivor population, not same-gameweek returns on the full
eligible pool. At Free Hit's actual timing and population the correlations are
materially weaker: **DEF 0.138, MID 0.109**. The lens result is therefore not
transferable evidence for C5 and is not cited as such; the +0.190 partial,
measured at C5's own timing and population, is.

**`minutes_roll3` — NEW.** Partial Spearman against same-gameweek
`total_points`, controlling for C4's three existing terms: **+0.185**. The
window is **roll3**, not roll5 or roll8, for two stated reasons from the
assessment: roll3 fits the single-gameweek framing of the Free Hit decision
best, and it has the strongest partial correlation of the three windows. It is
leakage-safe by construction under the lag-1 convention at
`dal/feat/feat_player_gameweek.py:98-107`. NaN rate at the eligible-candidate
grain is **0.554%** (138 of 24,918 rows, ~4.3 rows per gameweek), structural and
first-row cold-start only, arising from the cause §7.7 characterized for C4's
points terms (a player whose first row anywhere in the mart is their first
eligible candidate gameweek, leaving the shift no antecedent). It is handled the
same way §7.7 resolved that case: a NaN in any term makes the composite score
NaN, those rows fall to the unrankable tier, and the existing NaN-last tie-break
in `_sort_key` absorbs them.

**Correction.** This paragraph originally stated **2.827%** (~22 rows per
gameweek, "five times C4's rate"). That figure was *predicted* before
measurement, at the raw-mart grain, and is wrong at the grain this section
claims. The measured rate at the eligible-candidate grain is **0.554%**, i.e.
*identical* to C4's points-term rate rather than five times it. The cause of the
discrepancy is that `build_candidates`'s registration filter removes the
cold-start rows before the composite ever scores them, which the original
estimate did not account for. The measured figure is now pinned by
`test_the_two_new_c5_signals_hold_their_measured_nan_rates_on_the_live_mart` in
`test_candidates_integration.py`. `transfers_in`'s **0.000%** is unaffected and
was already correct. Nothing else in §8 depends on the magnitude of this rate —
the mechanism and its resolution are unchanged — so this is a figure correction
only.

### §8.3 — Normalization

All three terms use §7.2's **within-gameweek rank normalization**: ranked
ascending over the eligible candidate pool `candidates.build_candidates(mart, gw)`
returns, mapped to `[0, 1]` by `(rank − 1) / (n − 1)`, ties taking their average
rank. This is not a new decision — it is §7.2's established convention applied
to a new ingredient set, and §7.2's rejection of z-scoring carries with it.

`transfers_in` makes that rejection non-negotiable rather than merely preferred.
The assessment found the column spans **five orders of magnitude** across the
pool. Under z-scoring, a single heavily-transferred player would dominate a
fixed-weight sum outright — the failure §7.2 anticipated in the abstract for
heavy-tailed points distributions, here present in a much more extreme form.
Rank normalization removes it by construction, at §7.2's stated cost: magnitude
is discarded, so the most-transferred player in a gameweek scores as merely
first. That cost is accepted on the same grounds as in C4.

`fdr_term`'s reversed-sign convention carries forward unchanged: the term is
reversed *before* normalizing, as `6 − fdr_bin`, so all three normalized terms
are higher-is-better and every weight stays strictly positive. §7.2's rejection
of handling direction with a negative weight applies unchanged.

### §8.4 — The weight vector

**The collinearity structure.** It is the same shape that sank C4, with a
looser pair. `transfers_in` and `minutes_roll3` are approximately **0.75**
collinear with each other — meaningfully less than the 0.957 and 0.850 pairs the
assessment found, but not orthogonal. `fdr_term` is orthogonal to both (≈ 0.00).
So C5 has two correlated terms and one independent one: two effective signals
across three slots.

**The vector.** §7.2.1 established the derivation for exactly this structure —
treat the correlated pair as one combined signal, split one weight-slot's worth
of influence between them, and give the orthogonal term the other half. Applied
unchanged:

| term | weight |
| --- | --- |
| `transfers_in` | **0.25** |
| `minutes_roll3` | **0.25** |
| `fdr_term` | **0.50** |

This split is chosen, not merely offered as an example. It follows §7.2.1's
precedent exactly and is derived from the collinearity structure **alone** — not
from any partial-ρ magnitude, not from any regret outcome, and not from C4's
result. The two new terms' partials (0.190 and 0.185) are near-identical, so
even a magnitude-based argument would land in the same place; that coincidence
is noted but is not the derivation. The 0.75 collinearity is looser than C4's
0.850, which is an argument that the double-count being corrected is smaller —
not an argument for a different number, since any adjustment scaled to the
correlation would be a tuned parameter with no off-evaluation-set basis.

**This is the ONE pre-registered vector for C5.** Weights are fixed a priori,
before any regret is computed, exactly as §7.2 requires and §7.2.1's terminal
clause enforces. If `0.25 / 0.25 / 0.50` fails `METRIC.md` §2's conjunctive
rule, the documented conclusion is that **this ingredient set does not beat the
naive baselines on the data available**. There is no second vector for C5. C4
was permitted two only because its first vector contained a demonstrable
structural error — an unintended double-count of a collinear pair under equal
thirds — which C5's vector corrects up front. C5 therefore starts where C4
ended, and gets one attempt.

### §8.4.1 — The ablation is part of C5's definition

C5 is run **twice** through the same harness, on the same qualifying gameweeks,
against the same three baselines:

- **C5** — §8.4's pre-registered vector: `w_transfers_in = 0.25`,
  `w_minutes_roll3 = 0.25`, `w_fdr = 0.50`.
- **C5-nofdr** — the fdr term dropped, its weight redistributed proportionally
  across the other two: `w_transfers_in = w_minutes_roll3 = 1/2`, `w_fdr = 0`.
  This is §7.3's rule applied unchanged, and it is the rule `candidates.py`'s
  `ABLATION_WEIGHTS` actually implements for C4-nofdr (proportional
  redistribution, which for an equally-weighted pair is an equal split of the
  freed weight). The two variants therefore differ in exactly one thing (fdr
  present or absent) rather than in fdr *and* the relative balance of the other
  two.

**Why this is definitional rather than optional.** `fdr_term` again carries half
the weight budget (§8.4), so C5's result is again load-bearing on a term whose
contribution has never been measured outside C4's ingredient set. Without the
ablation a C5 failure would be unattributable between two distinct
explanations: that fdr's contribution does not generalize beyond C4's
ingredients, or that the new collinear pair (`transfers_in` /
`minutes_roll3`) is simply weaker than C4's. The ablation separates them, and
costs one additional weight vector through machinery already built.

**How the ablation's result is reported.** C5-nofdr is a **diagnostic, not a
second candidate**. It does not compete for `METRIC.md` §2's verdict, does not
enter the Holm-Bonferroni family (which remains pre-registered as exactly
`{C5 vs C1, C5 vs C2, C5 vs C3}`, and adding a fourth arm post hoc would be the
multiplicity inflation §2 exists to control), and does not get a PASS/FAIL of
its own. Its regret figures are not tested for significance and not corrected
for multiplicity. It is reported as a paired difference between the two
variants' per-gameweek Combined-regret series, with its own mean and interval,
alongside C5's verdict — answering "did the fdr term move anything, and in which
direction" as context for reading C5's result.

Like C4-nofdr, C5-nofdr's zero fdr weight is an exemption from the
strictly-positive weight invariant, taken by construction along the existing
`ABLATION_WEIGHTS` pattern. The exact code mechanics belong to the build pass.

### §8.5 — The honest caveat

**The partial correlations justifying C5 are measured pool-wide, and that is a
materially easier question than the one the constructor faces.** Across the full
eligible candidate pool, the dominant source of variance in same-gameweek
`total_points` is whether a player features at all. A signal that predicts
play/don't-play will therefore show a substantial partial ρ against points
without carrying any information about how a player who does play will score.
Both new terms are exposed to this: `minutes_roll3` is a minutes signal
directly, and `transfers_in` is heavily driven by expected starters.

The greedy constructor's actual decisions do not happen in that pool. They
happen among roughly the **top ~15 candidates per position**, where the
play/don't-play separation has already largely resolved — the candidates in
contention are mostly players who will feature, and the discrimination C5 needs
is *among* them. The pool-wide partials say nothing directly about how much
signal survives into that regime.

This is stated plainly because it is the load-bearing limit on what this pass
established. The partials (`transfers_in` +0.190, `minutes_roll3` +0.185)
justify **one pre-registered test** of C5 — they are evidence that these
ingredients carry incremental information beyond C4's, which is enough to be
worth spending a test on. **They are not evidence that C5 will beat C1.** No
claim to that effect is made here, and none should be read into §8.4's
derivation.

### §8.6 — What this pass establishes, and what is left to the build

Confirmed by this pass, not assumed:

- **Tier A holds for all three inputs together.** `transfers_in`,
  `minutes_roll3` and `fdr_avg` are all reachable from a single
  `dal.pipeline.load` call, with zero `model/` import and no local
  re-derivation. This is a simplification relative to C4, whose `season_ppg` /
  `recent_form_ppg` terms required local derivation specifically to avoid
  `model/eval`'s fan-out (§4).
- **`evaluate.py` needs no structural change.** `construction_regret` already
  emits every ordered pair in `POLICIES`; adding C5 is one dict entry.
- **`verdict.py` supports C5 unmodified.** Its verdict family is
  **per-candidate** — C5 against C1/C2/C3, its own three legs, its own
  family-wise alpha — not a global family across all candidates. This was
  confirmed by reading `verdict.py` directly rather than inferred from §7.5's
  description, and it means C5's addition does not alter §2's rule or C4's
  recorded multiplicity control.

Deliberately left to the build pass, not decided here: confirmation of the exact
tie-break behavior under the higher unrankable-tier population §8.2 flags for
`minutes_roll3` (the mechanism is settled, the observed per-gameweek count is
not verified), and any test-fixture updates C5's addition requires. Both are
build-time verification, not specification.

### §8.7 — Where this specification is underdetermined

- The **exact column name and grain** of `transfers_in` in the governed mart is
  cited from the assessment as a raw column at eligible-candidate grain but is
  not pinned to a file and line here, unlike `minutes_roll3`
  (`dal/feat/feat_player_gameweek.py:98-107`). The build pass should pin it.
- The **~0.75 collinearity** figure between the two new terms is stated by the
  assessment as approximate. §8.4's derivation does not depend on its precise
  value — it depends only on the pair being correlated and `fdr_term` being
  orthogonal — so this is recorded as a documentation imprecision, not a live
  parameter choice.

### §8.8 — Final result: C5 FAILS, and the candidate definition is closed

C5 was run under §8.4's single pre-registered vector (`0.25 / 0.25 / 0.50`)
through the same harness, the same 32 qualifying gameweeks and the same three
baselines as C4. Per §8.4's terminal clause this is the **only** weight vector
tested against this candidate definition.

**Verdict — `METRIC.md` §2's conjunctive rule: FAIL (2 of 3 nulls rejected).**

| leg | mean Δ (pts/GW) | sd | 95% CI | p_raw | p_Holm | H₀ rejected |
| --- | --- | --- | --- | --- | --- | --- |
| C5 vs C1 (season-PPG) | **+3.13** | 16.97 | crosses 0 | 0.1900 | **0.1900** | no |
| C5 vs C2 | **+11.34** | — | excludes 0 | 0.0002 | **0.0006** | **yes** |
| C5 vs C3 | **+8.22** | — | excludes 0 | 0.0028 | **0.0056** | **yes** |

The conjunctive rule requires all three nulls rejected. C5 clears C2 and C3 and
does not clear C1: a mean advantage of **+3.13** pts/GW against a per-gameweek
standard deviation of **16.97** is not separable from noise at n=32.

**Against C4's recorded result (§7.8), C5 improves on every leg.** C1
+0.44 → **+3.13**; C2 +8.66 → **+11.34**; C3 +5.53 → **+8.22**, which converts
C3 from §7.8's near-miss (p_Holm 0.0910, not rejected) into a clean rejection
(p_Holm 0.0056). The ingredient swap §8.2 argued for did what it was argued to
do. It was not enough: C1 remains unbeaten by both candidates at the same n=32.

**Ablation (§8.4.1), diagnostic only.** C5 − C5-nofdr: mean **+1.94** pts/GW,
sd 15.22, 95% CI **[−4.63, +6.91]** — crossing zero. And C5-nofdr *alone*
beats C1 by **+1.19** pts/GW, which is more than C4 managed (+0.44) *with* its
fdr term. This is the **opposite** finding from C4's ablation, where stripping
fdr turned C4 from breakeven-against-C1 into an outright loss and §7.8 concluded
fdr was carrying the entire measured advantage. Read across both candidates:
**fdr generalizes as a signal** — its contribution is not an artifact of C4's
specific ingredients, and it moves C5 in the right direction — but **C5's
failure is not attributable to fdr.** The new pair (`transfers_in` /
`minutes_roll3`), collinear as §8.2 conceded, nonetheless carries real
independent signal on its own, and it still is not sufficient. §8.4.1 posed
exactly this question and it is now answered: the explanation for C5's failure
is neither "fdr does not generalize" nor "the new pair is weaker than C4's" —
the new pair is *stronger*, and the season-PPG floor is simply higher than a
cheap composite of these signals reaches.

**Conclusion — the candidate definition is closed.** This candidate definition
— `transfers_in` + `minutes_roll3` + FDR ordinal bin, under **any** weight
vector satisfying §8.4's a-priori and strictly-nonzero constraints — **does not
beat the naive baselines on the 32-gameweek 2025-26 evaluation set.** Per §8.4's
terminal clause, **no further weight vector will be tested against this
definition.** Changing the ingredients would again be a new candidate definition
requiring its own pre-registration, not an iteration of this one.

**The pattern now established across two candidates.** C4 and C5 are
structurally different ingredient sets — C4's two points-derived terms were
near-duplicates that §7.8's ablation found inert, C5's pair is a genuinely
stronger, less-collinear pair that this section's ablation finds carries real
signal — and **both fail to clear the season-PPG floor**, on the same 32
gameweeks, under the same conjunctive rule. Two independent attempts at the
cheap non-forecasting composite have now been measured, and the better of the
two clears two of three baselines but not the one that matters.

This is recorded as the **evidence available** to any future decision about
whether to pursue the deferred ILP/forecasting candidate per `DECISION.md` §4's
sequencing note. That sequencing decision is **not made here** — it is a
`DECISION.md`-level call for a future session. What this section contributes to
it is the measured ceiling: two cheap composites, the second built specifically
to repair the first's diagnosed weakness, top out at **+3.13 pts/GW against
season-PPG with sd 16.97** — statistically indistinguishable from doing nothing
clever. Any argument for the cost of the forecasting path is made against those
numbers.

**Why this verdict was cheap to compute.** `derive_signals` was hoisted out of
`build_candidates` (`candidates.py`) and called once at `evaluate.py`'s harness
level rather than per gameweek, taking the integration suite from **1795s to
108s**. That refactor is verified separately as behaviour-preserving —
byte-identical output across **274,098** field comparisons plus full CSV
snapshot hashes — and is not re-argued here. It is the reason C5, C5-nofdr and
the re-measurement of §8.2's NaN rate could all be run and re-verified in one
pass.

**Pointer — a signal survey was run after this section, and lives outside this document.**
Following C5's closure, a standalone read-only pass measured whether any unexploited cheap signal
remains in the mart at all: nine already-available signals against next-gameweek points (lag-1),
per position, over `build_candidates`'s full ex-ante pool across the same 32 qualifying gameweeks.
Its record is `decisions/free_hit/SIGNAL_SURVEY.md` — kept separate because it answers a question
above any single candidate and is fact-finding rather than a build specification, so it does not
belong as a §9 here. **Its conclusion:** no cheap signal beats season-PPG at any position in a way
that reaches the selected squad, which leaves two paths open for a `DECISION.md`-level call —
sourcing genuinely new data, or restructuring the prediction problem to separate "will play" from
"will score well". Nothing in §1-§8 above is amended by it; see `SIGNAL_SURVEY.md` §5 for how its
`fdr_bin` measurement reconciles with §8.8's ablation finding.
