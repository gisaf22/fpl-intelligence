# INVENTORY.md — Free Hit Squad Construction & Selection

**Status:** Read-only pass. No code was written, moved, or refactored; `orderings.py`, `harness.py`,
`sampler.py`, `formations.py` and the rest of the `starting_xi` slice were read but not touched.
**Governs nothing, recommends nothing.** This document answers the four questions
`decisions/free_hit/DECISION.md` §7 names as blocking `DESIGN.md`, and states facts only. Every
claim below is cited to a real file/line or to a query run directly against the live mart
(`~/.fpl/fpl.mart.parquet`) or the live raw sqlite DB (`~/.fpl/fpl.db`); nothing here is inferred
from `decisions/starting_xi/INVENTORY.md` without being re-verified against current repo state,
though that document is cited directly where it is the fact of record (e.g. registration-prefix
semantics) and re-derivation would just repeat its own verification.

**Method.** Each of the four questions was checked directly: the mart was queried with pandas for
row counts and DGW/BGW structure; `.importlinter` was read in full; `sampler.py` was read in full
for its feasibility logic; `fpl-ingest`'s extract stages and the raw JSON/sqlite payloads were
grepped and loaded for team-value fields. Where a question cannot be answered without a definition
the repository does not itself provide, both the fact and the missing definition are stated, and
the choice is flagged as `DESIGN.md`'s rather than made here.

---

## 1. Gameweek population availability

**The mart, verified directly (2026-08-29):** 31,958 rows, 841 unique `player_id`, `gw` ∈ {1..38}
(38 gameweeks), 64 columns. This is the same figure `decisions/starting_xi/INVENTORY.md`'s header
records, re-run rather than assumed current. There is no `season` or `year` column on the mart, and
`dal/config.py:4` resolves a single `DB_PATH` (`~/.fpl/fpl.db`, one SQLite file) with no
season-selection parameter anywhere in `dal/pipeline.py`. `CONTEXT.md:8-9` and
`docs/system-purpose.md:9,84` both state the repository's scope directly: *"The 2025–26 season is
the development season"* and *"single-season scope for 2025-26."* `~/.fpl/raw/` holds one season's
worth of payloads (`bootstrap.json`, `fixtures.json`, `gw_1.json`…`gw_38.json`, and one
`players/{id}.json` per player). **There is exactly one season/GW range in this repository: GW1–38
of 2025-26.** No fixed-vs-sampled-vs-multi-season choice is available to make — the data physically
supports only one season, full stop.

**`is_bgw`/`is_dgw` access path, confirmed at the layer a construction/harness pass would query.**
Both are declared `pa.Column("boolean", nullable=False)` in the mart's fail-closed schema
(`dal/mart/mart_schema.py:79-80`) — not optional, not derivable-if-absent. They are reached via
`dal.pipeline.load(db_path).mart`, the exact call `decisions/starting_xi/sampler.py:59` and
`decisions/starting_xi/harness.py:50` both make (`from dal.pipeline import load`), i.e. the same
access path the existing sibling slice's construction (`sampler.py`) and replay (`harness.py`)
modules already use. A Free Hit module built the same way would reach the same two columns the
same way, verified rather than assumed.

**How many gameweeks are non-DGW/non-BGW under DECISION.md §3's scoping — two different counts
depending on definition, and the repository does not itself pick one.**

Row-level `is_bgw` is contaminated by the pre-registration prefix, not just genuine blanks.
`decisions/starting_xi/INVENTORY.md` §2.5 (independently re-verified above: `is_bgw` ⟺ `minutes`
NULL, exact) already established that most NULL-`minutes` rows are a player not yet having
debuted, not a real fixture blank. Counting **any** `is_bgw=True` row in a gameweek as
disqualifying gives:

```
n_dgw_rows, n_bgw_rows per gw (verified against the live mart):
gw 1..37 each carry ≥1 is_bgw row; only gw 38 carries zero of either flag.
```

By that row-level definition, **1 of 38 gameweeks** (GW38 only) is clean — because early gameweeks
are saturated with not-yet-debuted players, whose rows are marked `is_bgw=True` regardless of
whether their club actually had a fixture that week.

Restricting to **already-registered** players only (per-player first non-null-`minutes` gw ≤ target
gw, `decisions/starting_xi/sampler.py:220-228`'s own registration predicate, re-applied here) and
checking, per `(team_id, gw)`, whether that team's registered players carry `fixture_count == 0`
(real blank) or `fixture_count == 2` (real double) — rather than whether any individual player row
carries the flag — gives a different, club-schedule-level count:

| Real BGW teams present | Real DGW teams present | GWs |
|---|---|---|
| >0 | — | GW31 (4 teams), GW34 (6 teams) |
| — | >0 | GW26 (2 teams), GW33 (6 teams), GW36 (2 teams) |
| 0 | 0 | the other **33** gameweeks |

**33 of 38 gameweeks** have zero clubs with a real blank or a real double, by this definition.

**Neither definition is implemented anywhere in the repository as a reusable "is this calendar
gameweek a DGW/BGW gameweek" classifier.** `decisions/starting_xi/sampler.py`, `harness.py`,
`formations.py` and `orderings.py` were grepped for `is_dgw`, `is_bgw`, `fixture_context` and
`fixture_count`: zero matches in all four. `decisions/starting_xi/INVENTORY.md`'s own citations for
these flags (§2.1, §2.6, §2.10) are all **row-level** filters inside `model/` terms
(`PlayModel.population`, `build_baseline_features`), never a whole-gameweek classification. The
33-gameweek figure above is therefore a fact this pass computed directly against the mart to answer
the question, not a citation to existing repository logic — **which of the two counts (or a third
definition) governs the v1 evaluation set is squarely `DESIGN.md`'s call, not resolved here.**

**Status: PARTIALLY RESOLVED.** Row counts, single-season scope, and the `is_bgw`/`is_dgw` access
path are RESOLVED with citation. The gameweek-count figure is data (33 vs. 1, depending on
definition) rather than a settled number, because no GW-level DGW/BGW definition exists in the
repository today — flagged for `DESIGN.md`.

---

## 2. Team-value-by-gameweek data

**Not on the mart.** The mart's full 64-column list (enumerated directly from the live parquet)
contains no `bank`, `team_value`, `squad_value`, or `entry`-prefixed column of any kind. The only
value-shaped column is `purchase_price` — a **per-player** price index (`player_histories.value ÷
10`, per `decisions/starting_xi/INVENTORY.md` §2.7, re-verified: 600/841 players carry more than
one distinct price across the season) — not a team-level or manager-level aggregate.

**Not in the staging contracts or `domain/`.** `grep -rln "bank\|team_value\|entry_history\|
squad_value\|overall_rank" dal/staging/contracts/*.yaml` and the same pattern against `dal/` and
`domain/` `*.py` files: zero matches, both times.

**Not in `fpl-ingest`'s extraction surface.** `fpl-ingest/src/fpl_ingest/extract/stages/` contains
exactly five stage modules: `bootstrap.py`, `event_status.py`, `element_summary.py`,
`gameweeks.py`, `fixtures.py`. There is no manager/entry-history stage. Grepping
`fpl-ingest`'s entire `src/` tree for `entry/`, `bank`, `team_value`, `squad_value`: zero matches.
The real FPL API's manager-entry endpoint (`/entry/{id}/history/`, which is where per-manager
`bank`/`value` by gameweek lives in the live API) is not one of the five ingested stages.

**Not in the raw payloads on disk.** `~/.fpl/raw/bootstrap.json` top-level keys: `chips`, `events`,
`game_settings`, `game_config`, `phases`, `teams`, `total_players`, `element_stats`,
`element_types`, `elements` — no manager-entry object. `events[i]`'s 27 keys (loaded directly) are
scoring/administrative (`average_entry_score`, `highest_score`, `most_captained`, etc.), never a
value/bank field. `~/.fpl/raw/gw_N.json` is `{"elements": [...]}` — per-player live stats only.
`~/.fpl/raw/players/{id}.json` is `{"fixtures", "history", "history_past"}`, where `history[i]`
carries `value` (that player's own price at that gameweek — the source of the mart's
`purchase_price`) and `selected` (ownership count) — no manager/team aggregate.

**The one adjacent-but-not-it signal that does exist:** the raw SQLite DB (`~/.fpl/fpl.db`) has an
`events` table (confirmed present: `sqlite3 ... "SELECT name FROM sqlite_master..."` lists it
alongside `players`, `teams`, `fixtures`, `fixture_stats`, `gameweeks`, `player_histories`,
`element_types`), and `docs/architecture/db-schema.md:300` documents its `average_entry_score`
column — the **average manager's points that gameweek**, not their squad value. It does not reach
the mart either way.

**Status: RESOLVED.** No team-value, squad-value, or bank-by-gameweek signal exists anywhere in
this repository's mart, staging contracts, `fpl-ingest` extraction code, or raw ingested payloads —
confirmed absent at all four layers. Per-player price (`purchase_price`) is not a substitute; it is
already distinguished as such by DECISION.md §3's own framing and confirmed here as the only
value-shaped field that does exist.

---

## 3. Incremental feasibility primitive

**`sampler.py`'s feasibility logic, exactly as it exists today.** The module docstring
(`decisions/starting_xi/sampler.py:1-45`) states its own method plainly: *"Method A (whole-draw
rejection)"* — propose a complete 15-player candidate, accept or discard the entire candidate, and
never repair or resample a subset of it. Three functions carry this:

- **`_universes(mart, gameweeks)` (lines 246-282).** Builds `U_g`, the registration-legal,
  gameweek-priced, position-split player pool, once per gameweek. Registration
  (`_registration_gw`, lines 220-228: first non-null-`minutes` gw per player) is enforced **here
  only** — by restricting the pool before any draw, not by rejecting an ineligible draw. Returns a
  `_Universe` (lines 177-190), a `dict[position, _Pool]`, where each `_Pool` (lines 164-173) is
  parallel arrays of `player_id`, `price_tenths`, `team_id` for one position's eligible players.
- **`_propose(rng, universe, size)` (lines 290-312).** Draws `size` complete proposals at once:
  for each position, `quota` players without replacement via an argpartition over random keys.
  Returns three `(size, 15)` arrays (player ids, prices in tenths, club ids), column-blocked by
  position — i.e. every call produces `size` **full 15-player candidates** in one shot, never a
  single position or a partial hand.
- **`_feasible(price_tenths, team_id)` (lines 315-327).** Call signature: two `(n, 15)` integer
  arrays in, one length-`n` boolean array out. Checks exactly two conditions per full row: budget
  (`price_tenths.sum(axis=1) <= BUDGET_CAP_TENTHS`) and the club cap, via
  `np.sort(team_id, axis=1)` then testing `ordered[:, MAX_PER_CLUB:] != ordered[:, :-MAX_PER_CLUB]`
  — a sorted-array trick that is only correct because every row has exactly `SQUAD_SIZE = 15`
  columns; quota and registration are not checked here because they hold by construction of
  `_propose`/`_universes`.

**Can any part of this be reused as-is for an incremental, partial-squad check? No — confirmed by
reading the code, not inferred from the docstring.** `_feasible`'s club-cap test is written for a
fixed row width of exactly 15 (`MAX_PER_CLUB:` / `:-MAX_PER_CLUB` slicing assumes that width); it
has no notion of "quota remaining" or "budget remaining," only "total spent" and "total per-club
count" over a row that is already complete. `_propose` draws a full per-position quota in a single
vectorised call; it has no mechanism to draw one player at a time against a partially-filled
squad. `_universes` is the one piece doing a job an incremental constructor would also need — it
builds the same "eligible, priced, club-tagged pool at gameweek g" any construction candidate
requires as a starting point — but it is a pool-builder, not a feasibility check, and it is
`decisions/starting_xi`-module-private (leading underscore; `test_sampler.py:34`,
`test_harness.py:54` and `test_rankers.py:55` do import it directly by name across module
boundaries within the same package, so the underscore is a documentation convention here, not a
Python-enforced boundary — but it is not exported as part of `sampler.py`'s public surface, which
is `AcceptanceRedLine`, `ProposalCapExceeded`, `MartPin`, `SquadSample`, `week_seed`,
`sample_squads`, `build_squads`).

A grep of the whole repository for `remaining_budget`, `partial.squad`, `incremental.*feasib`, and
`greedy` (as a squad-construction concept, not the unrelated matroid-greedy proof cited in
`decisions/starting_xi/harness.py:269-270` about bench-order selection) returns nothing that
implements an incremental or partial-squad feasibility check anywhere in the repository. **No such
primitive exists today, in `sampler.py` or elsewhere — DECISION.md §3's premise is confirmed
rather than merely asserted.**

**What a new incremental primitive would need to check, stated exactly.** Given (a) the players
already picked and their club/price, (b) the remaining per-position quota, (c) the remaining budget,
and (d) the per-gameweek `_Universe`/`_Pool`-shaped eligible pool minus already-picked players and
minus any club already at the cap: whether at least `quota_remaining[position]` eligible players
exist per remaining position, **and** whether the cheapest feasible completion (min-price players
at each remaining position, respecting the per-club cap against players already picked) sums to no
more than the remaining budget. Nothing in the repository computes a "cheapest N remaining at this
position" query or a running per-club count against a partial selection; both would be new.

**Where it could live, given the existing Tier structure — this pass does not decide, but the
options are concrete.** `decisions/starting_xi/DESIGN.md` §3.5 records the precedent the repository
already used for an analogous constants-vs-routine split: squad-legality constants
(`SQUAD_SELECT`, `MAX_PER_CLUB`, `BUDGET_CAP`, etc.) went to `domain/fpl_squad.py` because
`domain/` is model-free by `.importlinter` enforcement (`no_domain_to_anything`, `.importlinter:10-19`)
and the constants have no dependency on `dal/`; the formation-search *routine* itself stayed inside
`decisions/starting_xi/` rather than being promoted to `domain/`, on the stated reasoning that
promotion is "the right move when a second squad-family decision needs it, made deliberately then,
not speculatively now" (`DESIGN.md` §3.5). An incremental feasibility primitive is exactly the kind
of "second squad-family decision" that precedent contemplates — it could live inside
`decisions/free_hit/` alone, or be promoted next to `domain/fpl_squad.py` as a primitive shared
across both slices. `DECISION.md` §3 already names this exact tension ("built once and shared...
or... each candidate hand-rolling its own") as open; this pass confirms the code-level fact backing
it (nothing reusable exists yet) but does not pick a home.

**Are `domain/fpl_squad.py`'s existing constants sufficient inputs?** Read in full
(`domain/fpl_squad.py`, 80 lines): `POSITIONS`, `SQUAD_SELECT` (2/5/5/3), `SQUAD_SIZE` (15),
`XI_MIN_PLAY`/`XI_MAX_PLAY`, `XI_SIZE`, `MAX_PER_CLUB` (3, annotated UNVERIFIED — not staged from
any FPL endpoint), `BUDGET_CAP` (100.0, same UNVERIFIED annotation), `BUDGET_CAP_TENTHS` (1000).
These cover every **static rule** an incremental check needs (quota per position, the club cap, the
budget ceiling). They do **not** cover the **live pool data** a "remaining quota still fillable"
check needs — the cheapest available players per remaining position at gameweek g — which is not a
constant and is not currently exposed publicly; it would have to come from something
`_Universe`/`_Pool`-shaped, today private to `sampler.py`.

**Status: RESOLVED** that no reusable incremental/partial-squad feasibility primitive exists today
and that `_feasible`/`_propose` are structurally whole-squad (not merely under-used for the partial
case). **PARTIALLY RESOLVED / flagged** on placement: `domain/fpl_squad.py`'s constants are
necessary but not sufficient (live-pool access is also needed and isn't currently public); which
module should own the new primitive is `DESIGN.md`'s call, per the precedent cited above.

---

## 4. Tier-A buildability of a naive greedy constructor

**`.importlinter`, read in full: no contract governs `decisions.free_hit` today.** `root_packages`
(`.importlinter:2-8`) lists `dal, domain, research, model, serve, decisions` — `decisions` as a
whole is a root package, but every two-tier contract that actually restricts imports
(`no_starting_xi_tier_a_to_downstream`, `.importlinter:95-107`;
`no_starting_xi_tier_a_to_tier_b`, `:132-143`; `no_starting_xi_tier_b_to_tier_a_or_downstream`,
`:149-162`) names `decisions.starting_xi.*` submodules explicitly and only those. No
`decisions.free_hit.*` module is named anywhere in the file. **This means: as the repository
stands today, nothing in `.importlinter` would fail CI if a `decisions/free_hit/*.py` module
imported `model/`.** Whether a constructor *can* be written with zero `model/` import is therefore
a property of what code it contains, not something the current import-linter graph enforces one way
or the other for this slice — a wall would have to be added (a wiring/DESIGN task), not one that
already blocks anything.

**The three named signals, checked individually.**

- **`fdr_avg`** is a first-class mart column (confirmed in the live mart's 64-column list) — reached
  via `dal.pipeline.load().mart` like every other mart field. Dal-accessible, no `model/` involved,
  no open question.
- **As-of PPG (season-PPG-to-date).** The only existing implementation is `expanding_prior_mean`
  (`model/eval/baselines.py:58`, verified: `mart.groupby("player_id")["total_points"].transform(
  lambda s: s.shift(1).expanding().mean())`). Its own module imports only `pandas` (verified:
  `model/eval/baselines.py` imports nothing else project-internal), but importing
  `model.eval.baselines` at all executes `model/eval/__init__.py`, which eagerly imports
  `baselines, metrics, population, scorer, walkforward` (verified directly by reading
  `model/eval/__init__.py:1-19`) — real `model/` fan-out, regardless of which name is imported from
  it. **Importing this existing function would violate "zero import of `model/`."** The computation
  itself does not require it: `total_points` is on the mart directly, so the same one-line
  `shift(1)`/`expanding()` expression is computable with `dal/`-only data. A precedent for exactly
  this "derive locally instead of importing across the wall" move already exists in this repository
  — `research/families/form/validate/study.py:342-350` computes `points_roll3`/`points_roll5` with
  `state.groupby("player_id")["total_points"].transform(lambda x, w=window:
  x.shift(1).rolling(w, min_periods=1).mean())` specifically **because** the governed column is
  excluded, rather than importing a Tier-crossing source (verified by reading lines 335-353
  directly, including the comment *"deliberately not materialised in the governed DAL mart
  (ADR-010)... Research derives them here using the DAL's exact lag-1 convention"*).
- **Rolling PPG (`points_roll3`/`points_roll5`).** Confirmed absent from the mart: the feat layer's
  `_ROLL_COLS` (`dal/feat/feat_player_gameweek.py:16-22`, verified directly: `["minutes", "xgi",
  "xgc", "clean_sheets", "goals_conceded"]`) does not include `total_points`, and the annotation at
  lines 94-96 (verified directly) reads *"Excluded cols (total_points, xg, goals_scored, assists,
  saves, penalties_saved, bonus, bps): removed by lens evaluation (evaluation_circularity or
  G2-FAIL)."* `_GOVERNED_ROLLING_COLS` (`:31`) is asserted to match `FEATURE_REGISTRY` exactly
  (`:124-127`), so this column cannot silently reappear on the mart. It is reachable neither via the
  mart nor via any `dal/domain` accessor — but, as above, it is computable with the same
  `shift(1).rolling(N, min_periods=1).mean()` expression over the mart's own `total_points` column,
  with the identical `research/families/form/validate/study.py:342-350` precedent already
  establishing that pattern for this exact column.

**A directly relevant precedent that was already decided once — for a different reason that does
not carry over.** `decisions/starting_xi/DESIGN.md` §3.4 records that relocating
`expanding_prior_mean` out of `model/eval/baselines.py` (to avoid a `model/` dependency) was
considered and rejected for that slice — but the stated reason was that `rankers.py`'s F1 ranker
(`p_play`, a fitted GLM at `model/terms/p_play/p_play.py:40`) already forces a real, unavoidable
`model/` dependency on that slice's Tier B regardless, so relocating the one function "would buy no
structural property." **That reason is specific to `starting_xi` having a Tier B ranker at all.**
`DECISION.md` §4's naive greedy constructor (PPG + fdr_avg + value) has no forecasting/fitted-model
component named anywhere in its scope — no analogue of F1/`p_play` exists in what §4 describes. The
condition that closed off relocation for `starting_xi` does not apply here on its face; whether that
means the free_hit slice should relocate/re-derive rather than import is exactly the kind of call
`DESIGN.md` — not this document — makes.

**Status: PARTIALLY RESOLVED, and the open part is named precisely.** Buildable as pure Tier A with
zero `model/` import **is achievable**: `fdr_avg` is already dal-accessible, and both PPG signals
are computable from the mart's own `total_points` column via the exact local-derivation pattern the
repository already uses elsewhere for the same governance reason (`research/families/form/
validate/study.py:342-350`). It is **not** achievable by importing the existing canonical
`expanding_prior_mean` helper, because of `model/eval/__init__.py`'s fan-out. Which of those two
paths (reimplement locally vs. import and accept a `model/` edge) the constructor should take, and
where the resulting module should live (per the same `domain/`-vs-in-slice placement precedent
`decisions/starting_xi/DESIGN.md` §3.5 sets, cited in §3 above — no literal "decision-vs-wiring
placement test" of that name was found anywhere in the repository by that search string; §3.5's
constants-vs-routine reasoning is the closest actual precedent and is cited as such rather than
under an invented name), is `DESIGN.md`'s decision, not this document's.

---

## What this pass did not do

No file besides this one was created, moved, or edited. `orderings.py`, `harness.py`, `sampler.py`,
`formations.py`, `domain/fpl_squad.py` and every other module cited above were read only.
`decisions/free_hit/DESIGN.md` does not exist yet and nothing here proposes its content, a sampling
scheme, a value-signal proxy, a primitive's home, or an import strategy — each place a judgment call
was reachable, it is named and left to `DESIGN.md` rather than made here.

---

## Addendum (2026-09-01): top-10k-average reference figure

Not one of `DECISION.md` §7's original four questions; added because `METRIC.md` §4.2 flags the
top-10k-average figure as an open inventory gap distinct from the overall-average figure (confirmed
present via `events.average_entry_score` in §2 above) — `METRIC.md` §4.2's own words: *"Its existence
and source are not addressed by either source document... `INVENTORY.md` must be extended to check
for this before a report can include it."* This addendum does that check only; it does not revisit
or re-verify §1–§4 above.

**Mart** (`~/.fpl/fpl.mart.parquet`, read via the project venv's `pyarrow`, 64 columns total): no
column name contains `top`, `10k`, `percentile`, or any rank-threshold-like term. Full column list
checked: `player_id, gw, player_name, position_code, position_label, team_id, purchase_price,
ownership_count, transfers_in, total_points, minutes, goals_scored, assists, clean_sheets,
yellow_cards, red_cards, saves, bonus, bps, goals_conceded, xg, xa, xgi, xgc, fdr_avg, fixture_count,
is_bgw, is_dgw, home_count, away_count, was_home, starts, penalties_saved, own_goals,
penalties_missed, tackles, clearances_blocks_interceptions, recoveries, defensive_contribution,
influence, creativity, threat, ict_index, transfers_out, deadline_time, finished, is_previous,
is_live, is_next, minutes_roll3/5/8, xgi_roll3/5, xgc_roll3/5, clean_sheets_roll3/5,
goals_conceded_roll3/5, fixture_context, minutes_trend, is_warmup_gw, position`. All player-grain;
no manager-aggregate column of any kind exists on the mart, not just no top-10k one.

**Raw sqlite (`~/.fpl/fpl.db`), `events` table — full column list:** `id, name, deadline_time,
deadline_time_epoch, deadline_time_game_offset, release_time, released, average_entry_score,
highest_score, highest_scoring_entry, ranked_count, finished, data_checked, is_previous, is_current,
is_next, can_enter, can_manage, cup_leagues_created, h2h_ko_matches_created, most_selected,
most_transferred_in, most_captained, most_vice_captained, top_element, top_element_points,
transfers_made, chip_plays_json, ingested_at`. No top-10k or percentile column. Note:
`top_element`/`top_element_points` name the single highest-scoring *player* of the gameweek — an
unrelated concept to a top-10k-*managers* average, worth flagging only because the name invites
confusion. The DB's full table list (`_runs, sqlite_sequence, _metadata, players, teams, fixtures,
fixture_stats, gameweeks, player_histories, events, element_types, _stage_lineage`) has no
leagues/standings/manager-aggregate table of any kind.

**`fpl-ingest` extraction stages** (`bootstrap.py`, `event_status.py`, `element_summary.py`,
`gameweeks.py`, `fixtures.py`): grepped for `top.?10k`, `top_10k`, `top10k`, `percentile`,
`top.?ten.?thousand` (case-insensitive) — zero matches in code or comments across all five files.
Separately grepped the whole `extract/` tree for `leagues-classic`, `leagues_classic`, `standings`,
`entry/` — zero matches. This is the only live FPL API surface (the classic-league "Overall"
standings endpoint, paginated to rank ≈10,000) publicly known to make a top-10k figure derivable at
all; the pipeline never calls it.

**Raw JSON payloads** (`~/.fpl/raw/bootstrap.json`, `~/.fpl/raw/gw_1.json`): `bootstrap.json`'s
`events[]` objects carry the same field set as the sqlite `events` table (`average_entry_score`,
`highest_score`, `top_element`, `top_element_info`, no top-10k/percentile field). `gw_1.json` is
`{"elements": [...]}`, player-grain only, no manager-aggregate fields. One genuine near-hit on a
literal grep for `10k`/`percentile`: `game_settings.percentile_ranks` and (duplicated)
`game_config.rules.percentile_ranks`, each `[1, 5, 10, 15, ..., 95]` — this is FPL's static UI
percentile-bucket configuration (the boundaries the app buckets a manager's rank into for display),
not a computed score/average at any percentile. It is a false positive for this question, not a
partial answer, and is named here only so it isn't rediscovered and misread as the target figure in
a future pass.

**Conclusion: PARTIALLY RESOLVED.** No top-10k-average figure, or any manager-aggregate figure
besides `average_entry_score`/`highest_score`, exists anywhere in this repository's ingested data —
mart, raw sqlite, or raw JSON — confirmed absent at all three layers. This is not the same as
"doesn't exist at all": per public FPL API documentation/community knowledge (not independently
re-verified against the live API in this pass, since only already-ingested artifacts were checked),
a top-10k-average figure is derivable from the classic-league "Overall" standings endpoint by reading
the entry at rank ≈10,000 — a real, separate live API surface from anything `fpl-ingest` currently
calls, not a single ready-made field the way `average_entry_score` is. Whether to add that endpoint
to the ingest pipeline is a future `INVENTORY`/`DESIGN` question and is explicitly not addressed
here.
