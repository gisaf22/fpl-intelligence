"""Synthetic squad sampler — `DESIGN.md` §2, Method A (whole-draw rejection).

Draws `n_squads` synthetic FPL squads **per gameweek** from that gameweek's feasible set F_g, in
one of two squad modes (CARD.md §3), and returns them with a per-gameweek run record and a
run-level mart pin. Nothing is written to disk and no state is held between calls (§2.8/§2.9); storage is §7's.

The construction, and where each part is decided:

* **Squad modes** (CARD.md §3, #31). `uniform` is the neutral view and everything below is stated
  for it. `ownership` weights each player's proposal by his `ownership` (DATA.md: `selected` by
  the price rule, as `warehouse.served` derives it) and keeps the same whole-draw rejection, so its
  target is that weighted proposal distribution conditioned on F_g -- a realism assumption, read
  only alongside the uniform view, and not uniform on anything.
* **Target** (§2.1, uniform mode). Uniform on F_g — the 15-player subsets of the gameweek-*g* universe U_g that
  satisfy the 2/5/5/3 quota, the ≤3-per-club limit and the 100.0 budget cap *at gameweek g's
  prices and clubs*. Not uniform on U_g, not uniform per position, not uniform on Q_g.
* **Method** (§2.4/§2.5). Propose uniformly without replacement within each position — which is
  uniform on Q_g, the quota-satisfying supersets — then accept the whole 15 or discard the whole
  15 and redraw independently. Conditioning a uniform distribution on a subset gives the uniform
  distribution on that subset, so uniformity on F_g is a theorem here rather than a diagnostic.
  Three conditions carry that proof and each is load-bearing in the code below: the per-position
  draw is without replacement (`_propose`); registration restricts the pool rather than rejecting
  a draw (`_universes`); and rejection discards the entire 15 (`_build_week` keeps whole rows and
  never repairs one).
* **Registration** (§2.1). A player is in U_g iff he has a non-null `minutes` row at gameweek *g*
  or any earlier one. It is applied by building U_g before drawing, never as a rejection test:
  pre-registration rows carry a **forward-filled price** (`archive/INVENTORY.md` §2.7), so a leaked
  prefix row would not fail a null check — it would silently price a phantom against the cap
  using a value from later in the season.
* **Weekly resampling** (§0.16). Each gameweek in scope draws its own squads from its own
  universe at its own prices and clubs. A squad exists for exactly one gameweek; `squad_id` is
  unique across the whole set and belongs to exactly one `gw`, which is what §10.3's stratified
  estimator is valid under.
* **Acceptance measurement** (§2.6). Every gameweek runs a seeded pilot of `PILOT_PROPOSALS`
  before any gameweek's squads are built, and the ladder is applied per week. A red line in any
  one week stops the whole build — the rate is a falsification threshold for §2.3's slack-budget
  and slack-club arguments, and the first hypothesis for a rate that low is a bug in the
  feasibility predicate, not a surprising feasible set.
* **Seeding** (§2.9). `np.random.default_rng`, master seed required with no default, and one
  stream per gameweek derived from the master seed *and* the gameweek number. Building one
  gameweek in isolation reproduces exactly the squads that building all of them produces, and
  rebuilding GW7 does not perturb GW8.
* **Squad-set identity** (§5.3.2). The returned set carries a content hash of itself — one digest
  per gameweek in the run record, folded into a run-level `squad_set_id`. It is what §7.3's
  manifest lets a later run assert a replay against, and it catches what neither the mart pin nor
  the seed can: a change to `PROPOSAL_BATCH` or to the per-week derivation moves every squad in
  every week while every recorded *input* stays identical.

Import closure: `warehouse/`, `domain/`, `numpy`, `pandas` (§2.9). Tier A — never `model/`,
`research/`, `serve/`, `operational/` or `rankers.py` (§3.5).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from decisions.starting_xi.seeding import week_seed
from domain.fpl_squad import (
    BUDGET_CAP_TENTHS,
    MAX_PER_CLUB,
    POSITION_BY_ID,
    POSITIONS,
    SQUAD_SELECT,
    SQUAD_SIZE,
)
from warehouse import served

# ---------------------------------------------------------------------------
# Constants fixed by DESIGN.md §2.6
# ---------------------------------------------------------------------------

PILOT_PROPOSALS: int = 100_000
"""Proposals in each gameweek's pilot. Fixed by §2.6, not a parameter: p̂_g is only comparable
against the ladder — and only reproducible — at a fixed proposal count."""

LADDER_PROCEED: float = 1e-2
"""p̂_g at or above this needs no further record beyond the run record itself (§2.6)."""

LADDER_RED_LINE: float = 1e-4
"""p̂_g below this stops the entire build (§2.6). It is a falsification threshold for §2.3, not a
cost threshold: uniformity holds at any positive rate."""

PROPOSAL_CAP_PER_GW: int = 100_000_000
"""Cumulative proposals (pilot + build) allowed for one gameweek before the run aborts (§2.6).
Per-gameweek rather than shared across the season so the abort names the week that failed."""

PROPOSAL_BATCH: int = 4096
"""Proposals drawn per vectorised batch.

**This is part of the reproducibility contract, not a tuning knob.** Proposals are drawn one
position at a time across a whole batch, so the batch size determines the order in which a
gameweek's stream is consumed. The *squads* are batch-size independent — they are the first
`n_squads` accepted proposals in proposal order either way — but the stream position is not, so
changing this constant changes every seeded artefact. It is fixed here for that reason."""

_PIN_COLUMNS: tuple[str, ...] = ("player_id", "gw", "position_id", "price", "team_id", "minutes")
"""The gameweek-frame columns the uniform mode reads, and therefore the columns its pin covers (§5.3)."""

SQUAD_MODES: tuple[str, ...] = ("uniform", "ownership")
"""CARD.md §3's two squad mixes. Required on every entry point, with no default: which view a run
reads is the call site's decision, and a default would inherit one by accident."""

_OWNERSHIP_COLUMN: str = "ownership"


def _read_columns(squad_mode: str) -> tuple[str, ...]:
    """The columns a mode reads. The weighted mode adds `ownership`, so only its pin covers it and
    the uniform pin stays exactly what it was before squad modes existed."""
    return (*_PIN_COLUMNS, _OWNERSHIP_COLUMN) if squad_mode == "ownership" else _PIN_COLUMNS


_ENTRANT_REFERENCE_GW: int = 2
"""The universe the cross-week diagnostic in §2.9 is stated against: U_2, the pool a build-once
construction would have frozen. Entrants are the players in U_g but not in U_2."""


class AcceptanceRedLine(RuntimeError):
    """Raised when any gameweek's pilot measures p̂_g < `LADDER_RED_LINE` (§2.6).

    Carries the full pilot series on `.pilots` so the shape across the season is readable
    without a re-run. §2.6 requires the feasibility predicate be audited before anything else;
    §2.7's Method C fallback is reached only if the predicate is confirmed correct and the rate
    still stands, and it would then apply to every gameweek rather than the offending one.
    """

    def __init__(self, message: str, pilots: pd.DataFrame) -> None:
        super().__init__(message)
        self.pilots = pilots


class ProposalCapExceeded(RuntimeError):
    """Raised when one gameweek's cumulative proposals reach `PROPOSAL_CAP_PER_GW` (§2.6)."""


@dataclass(frozen=True)
class MartPin:
    """What the frozen squad set is reproducible against (§5.3).

    Rejection consumes a data-dependent number of RNG draws, so the same seed against a different
    mart yields a different squad set. Under weekly resampling the exposure covers every gameweek
    in scope, not one slice: a mart rebuild touching any gameweek in scope invalidates the whole
    set (§2.8).
    """

    slice_sha256: str
    slice_rows: int
    gameweeks: tuple[int, ...]
    columns: tuple[str, ...]
    mart_rows: int
    mart_gw_span: tuple[int, int]


@dataclass(frozen=True)
class SquadSample:
    """The sampler's return value (§2.9): squads, the run record, the pin and the set's own id.

    `squads` is the frozen squad table at (`gw`, `squad_id`, `player_id`) — 15 rows per squad,
    `squad_id` unique across the set and belonging to exactly one `gw`. Everything else about a
    drawn player (position, price, club) is a join back onto the pinned mart rather than a
    denormalised column, which is what keeps the key the thing under test in §2.8.

    `run_record` is one row per build gameweek, and carries that week's `squad_sha256`.

    `mart_pin` and `squad_set_id` are both run-level and carried once, and they identify opposite
    ends of the same contract (§5.3.2): the pin says what the set is reproducible *against*, the
    id says what was *produced*. §7.3 makes both identity fields of a run, and neither substitutes
    for the other — when two ids differ, only the pin says whether the mart moved.
    """

    squads: pd.DataFrame
    run_record: pd.DataFrame
    mart_pin: MartPin
    squad_set_id: str


@dataclass(frozen=True)
class _Pool:
    """One position's slice of a gameweek's universe, as parallel arrays in draw order."""

    player_id: np.ndarray
    price_tenths: np.ndarray
    team_id: np.ndarray
    weight: np.ndarray | None = None
    """Proposal weights in ownership mode; None draws uniformly."""

    @property
    def size(self) -> int:
        return int(self.player_id.size)


@dataclass(frozen=True)
class _Universe:
    """U_g, split by position and priced at gameweek *g*."""

    gw: int
    pools: dict[str, _Pool]

    @property
    def size(self) -> int:
        return sum(pool.size for pool in self.pools.values())

    @property
    def player_ids(self) -> np.ndarray:
        return np.concatenate([self.pools[position].player_id for position in POSITIONS])


# ---------------------------------------------------------------------------
# Universe construction (§2.1)
# ---------------------------------------------------------------------------


def _registration_gw(mart: pd.DataFrame) -> pd.Series:
    """Per player, the first gameweek carrying a non-null `minutes` row.

    This is the whole of the registration predicate: a player is in U_g iff this value exists and
    is ≤ *g*. Evaluated once over the panel rather than per gameweek — the prefix test needs the
    history, which is why §2.9 has the sampler take the whole panel and slice it itself.
    """
    played = mart.loc[mart["minutes"].notna(), ["player_id", "gw"]]
    return played.groupby("player_id")["gw"].min()


def _price_tenths(price: np.ndarray) -> np.ndarray:
    """Convert prices to integer tenths, the unit FPL quotes them in.

    The budget test is exact in tenths and only approximate in floats: fifteen float prices can
    sum to 100.00000000000001 and reject a squad that costs exactly 100.0. `purchase_price` is
    `player_histories.value ÷ 10` (`archive/INVENTORY.md` §2.7), so the conversion is lossless — and it is
    asserted rather than assumed, because a change of unit upstream would otherwise turn the
    budget predicate into a silently different one.
    """
    tenths = price * 10.0
    if not np.all(np.abs(tenths - np.rint(tenths)) < 1e-6):
        raise ValueError("price is null or not quoted in tenths; the budget predicate assumes tenths")
    return np.rint(tenths).astype(np.int64)


def _ownership_weight(at_position: pd.DataFrame, gw: int, position: str, quota: int) -> np.ndarray:
    """A position's proposal weights: `ownership`, with a player who has none weighted 0.

    Fails loudly when fewer players than the quota carry a positive weight: the weighted draw could
    then fill the quota only from zero-weight players, picked by a tie among infinite keys.
    """
    weight: np.ndarray = at_position[_OWNERSHIP_COLUMN].fillna(0).to_numpy(dtype=float)
    owned = int((weight > 0).sum())
    if owned < quota:
        raise ValueError(
            f"gameweek {gw} has {owned} {position} players with positive ownership, fewer than the quota of {quota}"
        )
    return weight


def _universes(mart: pd.DataFrame, gameweeks: Sequence[int], squad_mode: str) -> dict[int, _Universe]:
    """Build U_g for every gameweek in scope, priced and club-keyed at that gameweek.

    Registration enters **here and only here**. Every member of the returned pools is
    registration-legal at its own gameweek, so every proposal drawn from them is too, and no
    rejection test ever has to consider registration (§2.1).
    """
    registration_gw = _registration_gw(mart)
    universes: dict[int, _Universe] = {}

    for gw in gameweeks:
        rows = mart.loc[mart["gw"] == gw, list(_read_columns(squad_mode))]
        if rows.empty:
            raise ValueError(f"gameweek {gw} has no rows on the gameweek frame")
        if rows["player_id"].duplicated().any():
            raise ValueError(f"gameweek {gw} is not unique at player_id on the gameweek frame")

        registered = rows["player_id"].map(registration_gw)
        rows = rows.loc[registered.notna() & (registered <= gw)].sort_values("player_id")

        pools: dict[str, _Pool] = {}
        for position in POSITIONS:
            at_position = rows.loc[rows["position_id"].map(POSITION_BY_ID) == position]
            quota = SQUAD_SELECT[position]
            if len(at_position) < quota:
                raise ValueError(
                    f"gameweek {gw} has {len(at_position)} registered {position} players, "
                    f"fewer than the quota of {quota}: F_{gw} is empty"
                )
            pools[position] = _Pool(
                player_id=at_position["player_id"].to_numpy(dtype=np.int64),
                price_tenths=_price_tenths(at_position["price"].to_numpy(dtype=float)),
                team_id=at_position["team_id"].to_numpy(dtype=np.int64),
                weight=_ownership_weight(at_position, gw, position, quota) if squad_mode == "ownership" else None,
            )
        universes[gw] = _Universe(gw=gw, pools=pools)

    return universes


# ---------------------------------------------------------------------------
# The draw (§2.4 Method A)
# ---------------------------------------------------------------------------


def _propose(rng: np.random.Generator, universe: _Universe, size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Draw `size` independent proposals, uniform over Q_g -- or weighted, in ownership mode.

    Within each position, `size` independent uniform draws **without replacement**: a random key
    per candidate, then the `quota` smallest keys. Ties have probability zero in float64, so the
    selected set is exactly the quota smallest and every subset of the pool is equally likely.

    Positions are drawn in `POSITIONS` order, which is fixed in `domain/fpl_squad.py` because the
    order determines how the gameweek's stream is consumed.

    Ownership mode draws the same keys and maps each to `-log(u) / weight` before taking the smallest
    (Efraimidis-Spirakis weighted sampling without replacement). The stream is consumed identically
    in both modes, and a zero weight gives an infinite key, so that player is never chosen.

    Returns three (size, 15) arrays — player ids, prices in tenths, and club ids — column-blocked
    by position in that same order.
    """
    player_id, price_tenths, team_id = [], [], []
    for position in POSITIONS:
        pool = universe.pools[position]
        quota = SQUAD_SELECT[position]
        keys = rng.random((size, pool.size))
        if pool.weight is not None:
            with np.errstate(divide="ignore"):
                keys = -np.log(keys) / pool.weight
        chosen = np.argpartition(keys, quota - 1, axis=1)[:, :quota]
        player_id.append(pool.player_id[chosen])
        price_tenths.append(pool.price_tenths[chosen])
        team_id.append(pool.team_id[chosen])
    return np.hstack(player_id), np.hstack(price_tenths), np.hstack(team_id)


def _feasible(price_tenths: np.ndarray, team_id: np.ndarray) -> np.ndarray:
    """The two rejectable conditions, per proposal (§2.1).

    The quota holds by construction and registration holds by construction of the pools, so only
    the budget cap and the club limit are tested here. The club test sorts each row and looks for
    any value repeated `MAX_PER_CLUB + 1` times: in a sorted row that is exactly the condition
    `s[j + 3] == s[j]` for some j. It is a per-*squad* test over all 15, not a per-position one —
    applying it per position is one of the predicate bugs §2.6's red line exists to catch.
    """
    within_budget = price_tenths.sum(axis=1) <= BUDGET_CAP_TENTHS
    ordered = np.sort(team_id, axis=1)
    within_club_limit = (ordered[:, MAX_PER_CLUB:] != ordered[:, :-MAX_PER_CLUB]).all(axis=1)
    return within_budget & within_club_limit  # type: ignore[no-any-return]


def _pilot_week(rng: np.random.Generator, universe: _Universe) -> int:
    """Run one gameweek's pilot: `PILOT_PROPOSALS` proposals, returning the accepted count k_g.

    The pilot's squads are discarded; its *count* is the artefact (§2.6). The stream continues
    into that gameweek's build, so the pilot is not a separate draw from the build — it is the
    first `PILOT_PROPOSALS` proposals of the one stream the gameweek owns.
    """
    accepted = 0
    remaining = PILOT_PROPOSALS
    while remaining > 0:
        size = min(PROPOSAL_BATCH, remaining)
        _, price_tenths, team_id = _propose(rng, universe, size)
        accepted += int(_feasible(price_tenths, team_id).sum())
        remaining -= size
    return accepted


def _build_week(
    rng: np.random.Generator,
    universe: _Universe,
    n_squads: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Draw until `n_squads` proposals have been accepted.

    Returns the accepted squads as an (n_squads, 15) array of player ids, their total costs in
    tenths, and the number of proposals drawn up to and including the one that produced the last
    accepted squad.

    **Whole draws only.** An accepted proposal is kept as an entire row and a rejected one is
    discarded as an entire row; nothing resamples the offending position, swaps the expensive
    player, or conditions the next draw on the last. That is condition 3 of §2.4, and it is the
    single line whose violation would cost the uniformity claim while still producing squads that
    pass every constraint test in §2.8.
    """
    kept_ids: list[np.ndarray] = []
    kept_cost: list[np.ndarray] = []
    accepted = 0
    proposals = 0

    while accepted < n_squads:
        if PILOT_PROPOSALS + proposals + PROPOSAL_BATCH > PROPOSAL_CAP_PER_GW:
            raise ProposalCapExceeded(
                f"gameweek {universe.gw}: {PILOT_PROPOSALS + proposals} cumulative proposals reached the "
                f"per-gameweek cap of {PROPOSAL_CAP_PER_GW} with {accepted} of {n_squads} squads accepted"
            )

        player_id, price_tenths, team_id = _propose(rng, universe, PROPOSAL_BATCH)
        hits = np.flatnonzero(_feasible(price_tenths, team_id))
        needed = n_squads - accepted

        if hits.size >= needed:
            taken = hits[:needed]
            proposals += int(taken[-1]) + 1
        else:
            taken = hits
            proposals += PROPOSAL_BATCH

        kept_ids.append(player_id[taken])
        kept_cost.append(price_tenths[taken].sum(axis=1))
        accepted += taken.size

    return np.vstack(kept_ids), np.concatenate(kept_cost), proposals


# ---------------------------------------------------------------------------
# Diagnostics (§2.9)
# ---------------------------------------------------------------------------


def _diversity(squads: np.ndarray, cost_tenths: np.ndarray, universe: _Universe, entrants: np.ndarray) -> dict:
    """The four diagnostics §2.9 puts in the run record.

    They describe the *set*, where the acceptance fields describe the *sampler*. §2.1 disposes of
    exact duplicates; what these answer is near-copies — 300 squads differing in two or three
    slots would pass every constraint test, report a healthy acceptance rate, and still carry
    roughly one squad's worth of information about how rankers behave across squad composition.

    **They gate nothing** (§2.9). No threshold is attached to any of them, §0 selects no diversity
    criterion, and a number invented here would be a criterion smuggled in as reporting. A value
    that looks wrong is a finding to route through `archive/DECISION.md` and `archive/METRIC.md`.
    """
    selected, counts = np.unique(squads, return_counts=True)
    most_selected = int(np.argmax(counts))  # ties resolve to the lowest player_id — np.unique sorts
    is_entrant = np.isin(squads, entrants)
    cost = cost_tenths / 10.0

    return {
        "distinct_players": int(selected.size),
        "most_selected_player_id": int(selected[most_selected]),
        "most_selected_count": int(counts[most_selected]),
        "cost_min": float(cost.min()),
        "cost_median": float(np.median(cost)),
        "cost_max": float(cost.max()),
        "entrants": int(entrants.size),
        "entrant_distinct_selected": int(np.intersect1d(selected, entrants).size),
        "entrant_selections": int(is_entrant.sum()),
        "entrant_selection_share": float(is_entrant.mean()),
    }


def _mart_pin(mart: pd.DataFrame, gameweeks: Sequence[int], columns: tuple[str, ...]) -> MartPin:
    """Hash the slice actually read, and record what it was read from (§5.3).

    Emitted as data rather than noted in prose beside the artefact, so a later run can *verify*
    it is reproducing against the same input rather than assume it. The hash covers every
    gameweek in scope — §2.8's statement of the exposure under weekly resampling — over exactly
    the columns the sampler reads.
    """
    read = (
        mart.loc[mart["gw"].isin(list(gameweeks)), list(columns)]
        .sort_values(["gw", "player_id"])
        .reset_index(drop=True)
    )
    digest = hashlib.sha256(read.to_csv(index=False).encode("utf-8")).hexdigest()
    return MartPin(
        slice_sha256=digest,
        slice_rows=len(read),
        gameweeks=tuple(int(gw) for gw in gameweeks),
        columns=columns,
        mart_rows=len(mart),
        mart_gw_span=(int(mart["gw"].min()), int(mart["gw"].max())),
    )


def _week_digest(week: pd.DataFrame) -> str:
    """One gameweek's squads, as a content digest (§5.3.2).

    Taken over the `(squad_id, player_id)` pairs in ascending order, **not** over the emitted row
    order. §2.9 keys the squad table on those two plus `gw` and states that everything else about a
    drawn player is a join, so the identity of the set *is* the key; a digest sensitive to the order
    players happen to appear in within a squad would move on a change that altered no squad — the
    same false alarm §5.3 rejects when it restricts the mart pin to the columns actually read.

    `squad_id` is hashed, which is a different question with the opposite answer: T1, T2 and T5 all
    key on it (§7.2), so the same squads under permuted ids are a different artefact.
    """
    canonical = week.loc[:, ["squad_id", "player_id"]].sort_values(["squad_id", "player_id"])
    return hashlib.sha256(canonical.to_csv(index=False).encode("utf-8")).hexdigest()


def _squad_set_id(run_record: pd.DataFrame) -> str:
    """Fold the run record's per-week digests into the run-level squad-set id (§5.3.2, §7.3).

    A fold rather than one pass over the whole squad table, because §7.3 asks the id to do two
    things and only the second constrains its shape. A flat digest covers all 37 weeks and cannot be
    checked week by week: a rebuild of GW7 alone yields nothing from which one can be recovered, so
    the check would mean rebuilding the other 36 — the re-run the id exists to avoid. Composing it
    out of the per-week digests makes that check the recomputation of a single digest, which is what
    §5.3.1's order-independent derivation is worth in the artefact rather than only in a test.

    Each digest carries its gameweek, so two weeks' digests cannot be swapped without moving the id,
    and the weeks are sorted here rather than inherited from the caller's ordering.
    """
    ordered = run_record.sort_values("gw")
    payload = "\n".join(
        f"{int(gw)}:{digest}" for gw, digest in zip(ordered["gw"], ordered["squad_sha256"], strict=True)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ladder(acceptance_rate: float) -> str:
    """§2.6's ladder, applied to one gameweek's measured p̂_g."""
    if acceptance_rate >= LADDER_PROCEED:
        return "proceed"
    if acceptance_rate >= LADDER_RED_LINE:
        return "proceed_with_record"
    return "red_line"


# ---------------------------------------------------------------------------
# Public interface (§2.9, §5.1)
# ---------------------------------------------------------------------------


def sample_squads(
    frames: served.Frames,
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    *,
    squad_mode: str,
) -> SquadSample:
    """Draw `n_squads` feasible squads at each gameweek in `gameweeks`, in `squad_mode`.

    Args:
        frames: the pinned warehouse frames — `build_squads` is the entry point that loads them.
            Only the gameweek frame is read: price (in tenths), club, `position_id` and minutes.
            The whole season is needed rather than one gameweek's slice, because U_g's prefix
            definition needs the history (§2.9).
        gameweeks: the build gameweeks, **explicitly**. Not inferred from the frame's span: the
            scope is §0.7's and the sampler must not silently widen or narrow it by taking
            whatever the frame happens to hold.
        n_squads: squads per gameweek (300 per §0.16).
        seed: the master seed. **Required, no default** (§2.9) — which of the repository's two
            competing seed constants a run uses is the call site's decision (§8.4), and a default
            here would inherit one by accident.
        squad_mode: one of `SQUAD_MODES`. **Required, no default**, for the seed's reason.

    Returns:
        A `SquadSample`. Pure function of its arguments; holds no state and writes nothing.

    Raises:
        AcceptanceRedLine: if any gameweek's pilot measures p̂_g below `LADDER_RED_LINE`. Every
            pilot runs before any gameweek's squads are built, so a red line anywhere stops the
            whole build with nothing half-built (§2.6).
        ProposalCapExceeded: if one gameweek's cumulative proposals reach the per-week cap.
    """
    if squad_mode not in SQUAD_MODES:
        raise ValueError(f"squad_mode must be one of {SQUAD_MODES}, got {squad_mode!r}")
    if n_squads < 1:
        raise ValueError(f"n_squads must be at least 1, got {n_squads}")
    weeks = [int(gw) for gw in gameweeks]
    if not weeks:
        raise ValueError("gameweeks must be non-empty")
    if len(set(weeks)) != len(weeks):
        raise ValueError(f"gameweeks contains duplicates: {weeks}")
    gameweek = frames.gameweek
    columns = _read_columns(squad_mode)
    missing = [column for column in columns if column not in gameweek.columns]
    if missing:
        raise ValueError(f"gameweek frame is missing columns the sampler reads: {missing}")
    unknown = sorted(set(gameweek["position_id"].dropna().astype(int)) - set(POSITION_BY_ID))
    if unknown:
        raise ValueError(f"gameweek frame carries position_id(s) with no label: {unknown}")

    weeks = sorted(weeks)
    universes = _universes(gameweek, weeks, squad_mode)
    # The entrant reference is a membership set, so it is built unweighted in either mode.
    reference = _universes(gameweek, [_ENTRANT_REFERENCE_GW], "uniform")[_ENTRANT_REFERENCE_GW].player_ids

    # Every pilot first, then the ladder, then the builds. §2.6 stops the entire build on a red
    # line in any one week, so measuring all 37 before building any is what makes that stop clean:
    # nothing is built, rather than every week before the offending one.
    streams = {gw: np.random.default_rng(week_seed(seed, gw)) for gw in weeks}
    pilots = pd.DataFrame(
        [
            {
                "gw": gw,
                "derived_seed": week_seed(seed, gw),
                "universe_size": universes[gw].size,
                "pilot_proposals": PILOT_PROPOSALS,
                "pilot_accepted": (k := _pilot_week(streams[gw], universes[gw])),
                "pilot_acceptance_rate": k / PILOT_PROPOSALS,
                "ladder": _ladder(k / PILOT_PROPOSALS),
            }
            for gw in weeks
        ]
    )

    red = pilots.loc[pilots["ladder"] == "red_line", "gw"].tolist()
    if red:
        raise AcceptanceRedLine(
            f"pilot acceptance rate below {LADDER_RED_LINE:g} at gameweek(s) {red}. §2.6: audit the "
            f"feasibility predicate before anything else — a rate this far below §2.3's expectation is "
            f"more likely a bug in the predicate than a surprising feasible set. The whole build is "
            f"stopped, not just the offending week(s).",
            pilots=pilots,
        )

    week_squads: list[pd.DataFrame] = []
    records: list[dict] = []
    for row in pilots.to_dict("records"):
        gw = int(row["gw"])
        universe = universes[gw]
        entrants = np.setdiff1d(universe.player_ids, reference)
        squads, cost_tenths, proposals = _build_week(streams[gw], universe, n_squads)

        squad_ids = np.array([f"gw{gw:02d}-{i:04d}" for i in range(n_squads)])
        week = pd.DataFrame(
            {
                "gw": np.repeat(gw, n_squads * SQUAD_SIZE),
                "squad_id": np.repeat(squad_ids, SQUAD_SIZE),
                "player_id": squads.ravel(),
            }
        )
        week_squads.append(week)
        records.append(
            row
            | {
                "proposals": proposals,
                "accepted": n_squads,
                "acceptance_rate": n_squads / proposals,
                "squad_sha256": _week_digest(week),
            }
            | _diversity(squads, cost_tenths, universe, entrants)
        )

    # The id is folded from the record's own column rather than recomputed from the squad table, so
    # the two can never disagree about what a week's squads were (§5.3.2).
    run_record = pd.DataFrame(records)
    return SquadSample(
        squads=pd.concat(week_squads, ignore_index=True),
        run_record=run_record,
        mart_pin=_mart_pin(gameweek, weeks, columns),
        squad_set_id=_squad_set_id(run_record),
    )


def build_squads(
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    *,
    squad_mode: str,
    season: str,
    pin: served.Pin | None = None,
    snapshot_root: Path = served.SNAPSHOT_ROOT,
) -> SquadSample:
    """Load the pinned warehouse frames and sample squads from them (§2.9, §5.1).

    The one line of the sampler that reads data. `sample_squads` is the same construction over
    frames already in hand — which is what the §2.8 tests exercise, against universes small
    enough to enumerate F.
    """
    frames = served.load(season, pin=pin, snapshot_root=snapshot_root)
    return sample_squads(frames, gameweeks, n_squads, seed, squad_mode=squad_mode)
