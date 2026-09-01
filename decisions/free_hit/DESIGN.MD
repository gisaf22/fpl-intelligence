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