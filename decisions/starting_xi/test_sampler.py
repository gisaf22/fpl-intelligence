"""Tests for the squad sampler — `DESIGN.md` §2.8.

§2.8 calls the four constraint tests "the floor, not the ceiling", and orders the rest of the
suite around what a wrong implementation would still pass:

* Each constraint is asserted **against the squad's own gameweek**. Three of the four have a
  wrong version that passes: keyed on GW2, the price and club tests pass squads that are over
  budget or over the club limit at their own week, and the membership test rejects legitimate
  later entrants instead of catching phantoms. The joins that key them are the part worth
  reviewing, so they are written once, explicitly, in `_joined`.
* Uniformity is tested on a **reduced universe** small enough to enumerate F exactly. This
  verifies the algorithm, not any real artefact: |F_g| on a real universe is unknown and
  unenumerable (§2.1), so uniformity of a real 300-squad set is inherited from §2.4's proof plus
  this test of the implementation.
* Determinism is tested as a property in both of its parts — same seed reproduces, and building
  a *subset* of the gameweeks reproduces those gameweeks exactly, which is what makes a partial
  re-run auditable.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations, product

import numpy as np
import pandas as pd
import pytest
from scipy.stats import chisquare, kstest

from decisions.starting_xi.sampler import (
    PILOT_PROPOSALS,
    AcceptanceRedLine,
    ProposalCapExceeded,
    SquadSample,
    _universes,
    sample_squads,
    week_seed,
)
from domain.fpl_squad import BUDGET_CAP, MAX_PER_CLUB, POSITIONS, SQUAD_SELECT, SQUAD_SIZE

pytestmark = pytest.mark.unit

SEED_SWEEP_ENV = "FPL_SEED_SWEEP"


# ---------------------------------------------------------------------------
# Synthetic marts. Small enough to run a real pilot over, shaped like the real one:
# a full cartesian (player_id, gw) spine, NULL minutes before a player's debut, and a
# forward-filled price on those pre-registration rows (INVENTORY.md §2.5, §2.7).
# ---------------------------------------------------------------------------


def _mart(
    counts: dict[str, int],
    gws: range,
    prices: Callable[[str, int], float],
    teams: Callable[[str, int, int], int],
    debuts: Callable[[str, int], int],
) -> pd.DataFrame:
    rows = []
    player_id = 0
    for position, n in counts.items():
        for slot in range(n):
            player_id += 1
            debut = debuts(position, slot)
            for gw in gws:
                rows.append(
                    {
                        "player_id": player_id,
                        "gw": gw,
                        "position": position,
                        "purchase_price": prices(position, slot),
                        "team_id": teams(position, slot, player_id),
                        "minutes": None if gw < debut else 90,
                    }
                )
    mart = pd.DataFrame(rows)
    mart["minutes"] = mart["minutes"].astype("Int64")
    return mart


@pytest.fixture
def mart() -> pd.DataFrame:
    """A season-shaped universe: 68 players over GW1-6, a third of them entering after GW2."""
    rng = np.random.default_rng(11)
    price: dict[tuple[str, int], float] = {}

    def prices(position: str, slot: int) -> float:
        return price.setdefault((position, slot), float(np.round(rng.uniform(4.0, 13.0), 1)))

    return _mart(
        counts={"GK": 10, "DEF": 22, "MID": 24, "FWD": 12},
        gws=range(1, 7),
        prices=prices,
        teams=lambda position, slot, player_id: (player_id % 8) + 1,
        debuts=lambda position, slot: 1 if slot % 3 else 4,
    )


def _joined(sample: SquadSample, mart: pd.DataFrame) -> pd.DataFrame:
    """Join each drawn player to his row **at his own squad's gameweek**.

    This join is the test. Keying it on a fixed gameweek instead would silently pass three of
    §2.8's four constraint tests.
    """
    joined = sample.squads.merge(mart, on=["player_id", "gw"], how="left", validate="many_to_one")
    assert joined["position"].notna().all(), "a drawn player has no mart row at his squad's gameweek"
    return joined


# ---------------------------------------------------------------------------
# §2.8 — the four constraint tests, each against the squad's own gameweek
# ---------------------------------------------------------------------------


def test_position_quota_is_exact(mart: pd.DataFrame) -> None:
    joined = _joined(sample_squads(mart, [2, 4, 6], 40, 0), mart)
    counts = joined.pivot_table(index="squad_id", columns="position", aggfunc="size", fill_value=0)
    for position in POSITIONS:
        assert (counts[position] == SQUAD_SELECT[position]).all()
    assert (counts.sum(axis=1) == SQUAD_SIZE).all()


def test_club_limit_holds_at_each_squads_own_gameweek(mart: pd.DataFrame) -> None:
    joined = _joined(sample_squads(mart, [2, 4, 6], 40, 0), mart)
    per_club = joined.groupby(["squad_id", "team_id"]).size()
    assert per_club.max() <= MAX_PER_CLUB


def test_budget_cap_holds_at_each_squads_own_gameweek(mart: pd.DataFrame) -> None:
    joined = _joined(sample_squads(mart, [2, 4, 6], 40, 0), mart)
    cost = joined.groupby("squad_id")["purchase_price"].sum()
    # In tenths: fifteen float prices can sum a hair above the cap and still be legal.
    assert (np.rint(cost * 10).astype(int) <= round(BUDGET_CAP * 10)).all()


def test_every_drawn_player_is_in_his_own_gameweeks_universe(mart: pd.DataFrame) -> None:
    """Set membership in U_g, per §2.8 — cheaper and stricter than re-deriving the prefix rule."""
    sample = sample_squads(mart, [2, 4, 6], 40, 0)
    universes = _universes(mart, [2, 4, 6])
    for gw, drawn in sample.squads.groupby("gw"):
        assert set(drawn["player_id"]) <= set(universes[gw].player_ids.tolist())


def test_a_gw2_keyed_membership_test_would_be_the_wrong_test(mart: pd.DataFrame) -> None:
    """The wrong version of the test above, pinned so the right one cannot drift into it.

    U_2 is a strict subset of U_6, so asserting membership in U_2 would reject legitimate later
    entrants rather than catch phantoms. This fixture has entrants, and they are drawn.
    """
    sample = sample_squads(mart, [2, 6], 40, 0)
    u2 = set(_universes(mart, [2])[2].player_ids.tolist())
    late = sample.squads.loc[(sample.squads["gw"] == 6) & ~sample.squads["player_id"].isin(u2)]
    assert not late.empty


# ---------------------------------------------------------------------------
# §2.1/§2.8 — registration restricts the pool, it never rejects a draw
# ---------------------------------------------------------------------------


def test_no_squad_contains_a_player_before_his_first_non_null_minutes_row(mart: pd.DataFrame) -> None:
    sample = sample_squads(mart, [2, 4, 6], 40, 0)
    debut = mart.loc[mart["minutes"].notna()].groupby("player_id")["gw"].min()
    assert (sample.squads["gw"] >= sample.squads["player_id"].map(debut)).all()


def test_a_pre_registration_row_carries_a_price_and_is_still_excluded(mart: pd.DataFrame) -> None:
    """The trap §2.1 names: a prefix row fails no null check on price, so a leak would be silent."""
    prefix = mart.loc[mart["minutes"].isna()]
    assert not prefix.empty and prefix["purchase_price"].notna().all()

    sample = sample_squads(mart, [2], 40, 0)
    drawn_at_gw2 = set(sample.squads["player_id"])
    not_yet_registered = set(prefix.loc[prefix["gw"] == 2, "player_id"])
    assert not (drawn_at_gw2 & not_yet_registered)


# ---------------------------------------------------------------------------
# §2.8 — a squad belongs to exactly one gameweek
# ---------------------------------------------------------------------------


def test_each_squad_id_appears_at_exactly_one_gameweek(mart: pd.DataFrame) -> None:
    """Not a tidiness check: §10.3's estimator is valid because a squad contributes one row, and
    an id reused across weeks would resample correctly by its own lights while reintroducing the
    dependence §0.14's U3 rejection is about."""
    sample = sample_squads(mart, [2, 4, 6], 40, 0)
    assert (sample.squads.groupby("squad_id")["gw"].nunique() == 1).all()
    assert sample.squads.groupby("squad_id").size().eq(SQUAD_SIZE).all()
    assert sample.squads["squad_id"].nunique() == 40 * 3


def test_no_player_is_drawn_twice_within_one_squad(mart: pd.DataFrame) -> None:
    sample = sample_squads(mart, [2, 4, 6], 40, 0)
    assert (sample.squads.groupby("squad_id")["player_id"].nunique() == SQUAD_SIZE).all()


# ---------------------------------------------------------------------------
# §2.8 — determinism, in both of its parts
# ---------------------------------------------------------------------------


def test_same_seed_reproduces_the_squad_table_exactly(mart: pd.DataFrame) -> None:
    first = sample_squads(mart, [2, 3, 4, 5, 6], 40, 0)
    second = sample_squads(mart, [2, 3, 4, 5, 6], 40, 0)
    pd.testing.assert_frame_equal(first.squads, second.squads)
    pd.testing.assert_frame_equal(first.run_record, second.run_record)
    assert first.mart_pin == second.mart_pin


def test_building_a_subset_of_gameweeks_reproduces_those_gameweeks_exactly(mart: pd.DataFrame) -> None:
    """§2.9's per-week streams, asserted rather than assumed: a partial re-run is auditable only
    if the derivation is independent of build order and of what other weeks consumed."""
    whole = sample_squads(mart, [2, 3, 4, 5, 6], 40, 0)
    part = sample_squads(mart, [5, 3], 40, 0)
    pd.testing.assert_frame_equal(
        part.squads,
        whole.squads.loc[whole.squads["gw"].isin([3, 5])].reset_index(drop=True),
    )


def test_a_different_master_seed_gives_different_squads(mart: pd.DataFrame) -> None:
    a = sample_squads(mart, [2, 4, 6], 40, 0)
    b = sample_squads(mart, [2, 4, 6], 40, 1)
    assert not a.squads.equals(b.squads)


def test_week_seed_is_a_function_of_the_master_seed_and_the_gameweek_only() -> None:
    assert week_seed(0, 7) == week_seed(0, 7)
    assert week_seed(0, 7) != week_seed(0, 8)
    assert week_seed(0, 7) != week_seed(1, 7)
    assert len({week_seed(0, gw) for gw in range(2, 39)}) == 37


def test_the_seed_is_required(mart: pd.DataFrame) -> None:
    """§2.9: no default, deliberately — so a run cannot inherit either of the repository's two
    competing seed constants by accident."""
    with pytest.raises(TypeError):
        sample_squads(mart, [2], 40)  # type: ignore[call-arg]


def test_the_sampler_holds_no_state_between_calls(mart: pd.DataFrame) -> None:
    """§2.8: no module-level RNG, no cached index, no accumulated counters."""
    first = sample_squads(mart, [2], 40, 0)
    _ = sample_squads(mart, [4, 6], 40, 3)
    again = sample_squads(mart, [2], 40, 0)
    pd.testing.assert_frame_equal(first.squads, again.squads)
    pd.testing.assert_frame_equal(first.run_record, again.run_record)


# ---------------------------------------------------------------------------
# §2.8 — uniformity, on a universe small enough to enumerate F
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pool:
    """One enumerable universe for the uniformity test, with its own pinned arithmetic.

    Two are declared. §2.8 fixes the parameters of both, so the values here are specification
    rather than fixture convenience: `q` and `f_bounds` are pinned so a later edit to the prices
    or clubs cannot silently move the fixture to one where F is empty, or is all of Q, without
    failing.
    """

    label: str
    counts: dict[str, int]
    price: dict[str, list[float]]
    team: dict[str, list[int]]
    q: int
    f_bounds: tuple[int, int]

    def mart(self) -> pd.DataFrame:
        return _mart(
            counts=self.counts,
            gws=range(1, 3),
            prices=lambda position, slot: self.price[position][slot],
            teams=lambda position, slot, player_id: self.team[position][slot],
            debuts=lambda position, slot: 1,
        )


POOL_19 = _Pool(
    # 3 GK / 6 DEF / 6 MID / 4 FWD — |Q| = 3 x 6 x 6 x 4 = 432, with **both** rejectable
    # constraints biting: the budget cap admits 259 of the 432, the club limit 282, and F is the
    # 161 that satisfy both. A fixture where only one bit would leave the other untested.
    label="19-players",
    counts={"GK": 3, "DEF": 6, "MID": 6, "FWD": 4},
    price={
        "GK": [4.0, 4.5, 5.5],
        "DEF": [4.0, 4.5, 5.0, 6.0, 7.0, 8.0],
        "MID": [4.5, 5.5, 6.5, 7.5, 9.0, 11.5],
        "FWD": [5.5, 7.0, 8.5, 11.0],
    },
    team={
        "GK": [1, 2, 3],
        "DEF": [1, 2, 3, 4, 5, 6],
        "MID": [2, 3, 4, 5, 6, 7],
        "FWD": [1, 3, 5, 7],
    },
    q=432,
    f_bounds=(100, 432),
)

POOL_21 = _Pool(
    # 4 GK / 7 DEF / 6 MID / 4 FWD — |Q| = 6 x 21 x 6 x 4 = 3,024, |F| = 1,076. The second
    # measured point: it grows two of the four pools and multiplies |Q| by seven, which is what
    # turns §2.8's one-point assertion into a two-point pattern. Both constraints bite here too,
    # and the split runs the *other* way — the budget admits 1,471 of the 3,024 and the club limit
    # 2,349 — which is why §2.8 records the binding profile as a property of a fixture's prices
    # and clubs rather than of its pool size.
    label="21-players",
    counts={"GK": 4, "DEF": 7, "MID": 6, "FWD": 4},
    price={
        "GK": [4.0, 4.5, 5.0, 5.5],
        "DEF": [4.0, 4.5, 5.0, 5.5, 6.5, 7.5, 8.5],
        "MID": [4.5, 5.5, 6.5, 7.5, 9.0, 11.5],
        "FWD": [5.5, 7.0, 8.5, 11.0],
    },
    team={
        "GK": [1, 2, 3, 4],
        "DEF": [1, 2, 3, 4, 5, 6, 7],
        "MID": [2, 3, 4, 5, 6, 7],
        "FWD": [1, 3, 5, 7],
    },
    q=3_024,
    f_bounds=(700, 3_024),
)

POOLS = [POOL_19, POOL_21]

DRAWS_PER_FEASIBLE_SQUAD = 200
"""§2.8's pinned per-cell expected count. Held at both pool sizes, so the draw count scales with
|F| and the two points stay comparable."""

UNIFORMITY_ALPHA = 0.001
"""The chi-square threshold, used in both directions: a uniform sampler must clear it and the
deliberately biased one must fail it."""


def _enumerate_feasible(mart: pd.DataFrame, gw: int) -> list[frozenset[int]]:
    """Every member of F_g, by brute force. Only possible because the universe is tiny."""
    rows = mart.loc[mart["gw"] == gw].set_index("player_id")
    price = rows["purchase_price"].to_dict()
    team = rows["team_id"].to_dict()
    per_position = [
        list(combinations(rows.index[rows["position"] == position], SQUAD_SELECT[position])) for position in POSITIONS
    ]
    feasible = []
    for parts in product(*per_position):
        squad = [player_id for part in parts for player_id in part]
        clubs: dict[int, int] = {}
        for player_id in squad:
            clubs[team[player_id]] = clubs.get(team[player_id], 0) + 1
        cost = round(sum(price[player_id] * 10 for player_id in squad))
        if cost <= round(BUDGET_CAP * 10) and max(clubs.values()) <= MAX_PER_CLUB:
            feasible.append(frozenset(squad))
    return feasible


def _observed_counts(sample: SquadSample, feasible: list[frozenset[int]]) -> np.ndarray:
    """Realised frequency per member of F, aligned to `feasible`."""
    drawn = sample.squads.groupby("squad_id")["player_id"].apply(frozenset)
    assert set(drawn) <= set(feasible), "an infeasible squad was drawn"
    assert set(drawn) == set(feasible), "some feasible squad was never drawn"
    counts = drawn.value_counts()
    return np.array([counts.get(squad, 0) for squad in feasible])


def _cheap_squad_tilt(mart: pd.DataFrame, feasible: list[frozenset[int]], n_draws: int) -> np.ndarray:
    """Frequencies a sampler tilted toward cheap squads would produce, at the same draw count.

    This is §2.2's failure mode made concrete — the bias a repair or constructive scheme produces,
    running along price, which is the axis the rankers are separated by. Weighting by 1/cost^4 is
    a stand-in for that family rather than a model of any particular scheme; what it buys is a
    definite alternative for the chi-square to have power *against*, so the test's sensitivity is
    asserted rather than assumed.
    """
    price = mart.loc[mart["gw"] == 2].set_index("player_id")["purchase_price"]
    cost = np.array([price[list(squad)].sum() for squad in feasible])
    weight = 1.0 / cost**4
    weight /= weight.sum()
    drawn = np.random.default_rng(0).choice(len(feasible), size=n_draws, p=weight)
    return np.bincount(drawn, minlength=len(feasible))


@pytest.mark.parametrize("pool", POOLS, ids=lambda pool: pool.label)
def test_draws_are_uniform_over_the_enumerated_feasible_set(pool: _Pool) -> None:
    """Method A's uniformity, measured where it can be: conditioning a uniform proposal over Q on
    membership in F gives the uniform distribution on F, so every member of F must come up equally
    often. Verifies the algorithm; the real artefact inherits the property from the proof (§2.8).

    Run at **two** pool sizes. One measured point cannot distinguish "the sampler is uniform" from
    "the sampler is uniform at the one size anyone checked", and §2.8's generalisation from a
    19-player fixture to an 841-player universe otherwise rests entirely on the argument that no
    branch in the sampler reads pool size. Two points do not reach 841 — §2.8 records why no
    enumerable test can — but they turn a one-point assertion into a two-point pattern.
    """
    mart = pool.mart()
    feasible = _enumerate_feasible(mart, 2)
    low, high = pool.f_bounds
    assert low < len(feasible) < high, f"fixture is degenerate: |F| = {len(feasible)} of |Q| = {pool.q}"

    n_draws = DRAWS_PER_FEASIBLE_SQUAD * len(feasible)
    sample = sample_squads(mart, [2], n_draws, 0)
    observed = _observed_counts(sample, feasible)

    assert chisquare(observed).pvalue > UNIFORMITY_ALPHA

    # The power is executed, not claimed: the same test, at the same draw count, must *reject* a
    # sampler biased along price. Without this the uniformity assertion above could be passing
    # because the test cannot tell anything apart.
    assert chisquare(_cheap_squad_tilt(mart, feasible, n_draws)).pvalue < UNIFORMITY_ALPHA

    # The pilot measures |F|/|Q| directly, which is a second and independent reading of the same
    # property: it holds only if the proposal really is uniform over Q *and* the predicate the
    # sampler applies is the one enumerated above. A 10^5-proposal pilot has SE ~ 0.0015 here.
    assert sample.run_record.loc[0, "pilot_acceptance_rate"] == pytest.approx(len(feasible) / pool.q, abs=0.005)


@pytest.mark.skipif(os.environ.get(SEED_SWEEP_ENV) is None, reason=f"set {SEED_SWEEP_ENV}=1 — takes ~35s")
@pytest.mark.parametrize(("pool", "n_seeds"), [(POOL_19, 20), (POOL_21, 12)], ids=lambda arg: getattr(arg, "label", ""))
def test_uniformity_p_values_are_uniform_across_seeds(pool: _Pool, n_seeds: int) -> None:
    """The check a single seed cannot make.

    Under a fair sampler the chi-square p-value is Uniform(0,1) **by construction**, so the
    distribution of p across seeds is itself testable — and it catches a bias too small to push
    any one seed below the threshold. It exists because the seed-0 p-values at both pool sizes
    (0.078 at 19, 0.021 at 21) sit low enough to be worth a second look, and the answer is that
    they are ordinary draws: 20 seeds at 19 players give KS-vs-uniform p = 0.734, and 12 seeds at
    21 give 0.262.

    **Opt-in, and why.** At §2.8's pinned 200-per-cell count this is ~35 seconds — half again the
    whole slice suite — and CI runs `pytest -m unit`, which the module-level mark would collect.
    Running it at a lower per-cell count would make it affordable but would no longer be the
    configuration §2.8 pins and reports. So it is gated on an environment variable rather than
    thinned, and the cost of that choice is that nothing runs it automatically:

        FPL_SEED_SWEEP=1 pytest decisions/starting_xi/test_sampler.py -k across_seeds
    """
    mart = pool.mart()
    feasible = _enumerate_feasible(mart, 2)
    n_draws = DRAWS_PER_FEASIBLE_SQUAD * len(feasible)

    p_values = np.array(
        [
            chisquare(_observed_counts(sample_squads(mart, [2], n_draws, seed), feasible)).pvalue
            for seed in range(n_seeds)
        ]
    )
    assert kstest(p_values, "uniform").pvalue > 0.01, f"p-values are not Uniform(0,1): {np.sort(p_values)}"


# ---------------------------------------------------------------------------
# §2.6 — the acceptance ladder, its red line, and the per-gameweek cap
# ---------------------------------------------------------------------------


def test_the_pilot_is_recorded_for_every_gameweek(mart: pd.DataFrame) -> None:
    record = sample_squads(mart, [2, 4, 6], 40, 0).run_record
    assert list(record["gw"]) == [2, 4, 6]
    assert (record["pilot_proposals"] == PILOT_PROPOSALS).all()
    assert (record["pilot_acceptance_rate"] == record["pilot_accepted"] / PILOT_PROPOSALS).all()
    assert (record["ladder"] == "proceed").all()
    assert (record["derived_seed"] == [week_seed(0, gw) for gw in (2, 4, 6)]).all()


def test_a_red_line_in_one_week_stops_the_whole_build() -> None:
    """A budget so tight that a uniform draw almost never fits. §2.6 stops the entire build — a
    rate this far below §2.3's expectation is more likely a predicate bug than a real feasible
    set, and skipping the week would silently change the population."""
    tight = _mart(
        counts={"GK": 12, "DEF": 20, "MID": 20, "FWD": 10},
        gws=range(1, 4),
        prices=lambda position, slot: 4.0 if slot < 3 else 12.0,
        teams=lambda position, slot, player_id: (player_id % 8) + 1,
        debuts=lambda position, slot: 1,
    )
    with pytest.raises(AcceptanceRedLine) as raised:
        sample_squads(tight, [2, 3], 40, 0)
    assert (raised.value.pilots["pilot_acceptance_rate"] < 1e-4).any()
    assert list(raised.value.pilots["gw"]) == [2, 3], "the pilot series is reported for every week"


def test_the_per_gameweek_proposal_cap_names_the_week(mart: pd.DataFrame, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("decisions.starting_xi.sampler.PROPOSAL_CAP_PER_GW", PILOT_PROPOSALS)
    with pytest.raises(ProposalCapExceeded, match="gameweek 4"):
        sample_squads(mart, [4], 40, 0)


# ---------------------------------------------------------------------------
# §2.9 — the run record and the mart pin
# ---------------------------------------------------------------------------


def test_the_diversity_diagnostics_describe_the_returned_squads(mart: pd.DataFrame) -> None:
    sample = sample_squads(mart, [2, 4, 6], 40, 0)
    joined = _joined(sample, mart)
    for row in sample.run_record.to_dict("records"):
        week = sample.squads.loc[sample.squads["gw"] == row["gw"], "player_id"]
        assert row["distinct_players"] == week.nunique()
        assert row["most_selected_count"] == week.value_counts().max()
        cost = joined.loc[joined["gw"] == row["gw"]].groupby("squad_id")["purchase_price"].sum()
        assert row["cost_min"] == pytest.approx(cost.min())
        assert row["cost_max"] == pytest.approx(cost.max())
        assert row["cost_median"] == pytest.approx(cost.median())
        assert row["accepted"] == 40
        assert row["acceptance_rate"] == 40 / row["proposals"]


def test_the_entrant_diagnostic_counts_players_outside_the_gw2_universe(mart: pd.DataFrame) -> None:
    sample = sample_squads(mart, [2, 6], 40, 0)
    u2 = set(_universes(mart, [2])[2].player_ids.tolist())
    record = sample.run_record.set_index("gw")
    assert record.loc[2, "entrants"] == 0
    assert record.loc[6, "entrants"] > 0
    week = sample.squads.loc[sample.squads["gw"] == 6, "player_id"]
    assert record.loc[6, "entrant_selections"] == (~week.isin(u2)).sum()
    assert record.loc[6, "entrant_selection_share"] == pytest.approx((~week.isin(u2)).mean())


def test_the_mart_pin_covers_every_gameweek_in_scope(mart: pd.DataFrame) -> None:
    """§2.8: under weekly resampling a mart rebuild touching *any* gameweek in scope invalidates
    the whole frozen set, so a pin keyed on one week would understate the exposure."""
    baseline = sample_squads(mart, [2, 4, 6], 40, 0).mart_pin

    edited = mart.copy()
    edited.loc[edited["gw"] == 6, "purchase_price"] += 0.1
    assert sample_squads(edited, [2, 4, 6], 40, 0).mart_pin.slice_sha256 != baseline.slice_sha256

    untouched = mart.copy()
    untouched.loc[untouched["gw"] == 1, "purchase_price"] += 0.1
    out_of_scope = sample_squads(untouched, [2, 4, 6], 40, 0).mart_pin
    assert out_of_scope.slice_sha256 == baseline.slice_sha256
    assert out_of_scope.mart_rows == baseline.mart_rows


# ---------------------------------------------------------------------------
# §3.5/§5.6 — the sampler is Tier A, and stays Tier A
# ---------------------------------------------------------------------------


def test_importing_the_sampler_pulls_in_no_downstream_layer() -> None:
    """Run in a subprocess, and it has to be: `pyproject.toml`'s `testpaths` imports `model` — and
    through it `statsmodels` — before this test runs, so an in-process `sys.modules` assertion
    could not tell the module under test from what the session already imported (§5.6)."""
    program = (
        "import sys; import decisions.starting_xi.sampler; "
        "leaked = [m for m in sys.modules if m.split('.')[0] in {'model', 'research', 'serve', 'statsmodels'}]; "
        "assert not leaked, leaked"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0
