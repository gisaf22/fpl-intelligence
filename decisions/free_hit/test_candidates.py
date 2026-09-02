"""Tests for the naive greedy construction candidates -- `DESIGN.md` §4.

Builds a small synthetic mart (mirroring `decisions/starting_xi/test_sampler.py`'s `_mart`
helper) so registration filtering, NaN-score handling, and the infeasibility exception are
exercised without the live DB. `test_candidates_integration.py` runs all three policies against
the real mart across every one of the 32 qualifying gameweeks (`DESIGN.md` §2's 33, less
`METRIC.md` §3.3's excluded GW1), in its own
integration-only file -- `decisions/starting_xi`'s own unit test files never touch the live DB,
for the same reason this pass keeps that split as a separate file rather than a mixed marker on
one: a module-level `pytestmark = pytest.mark.unit` plus a per-function
`@pytest.mark.integration` both apply to that function at once, so `pytest -m unit` (what CI
actually runs) would still collect and run it.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from decisions.free_hit.candidates import (
    ABLATION_WEIGHTS,
    C5_ABLATION_WEIGHTS,
    C5_WEIGHTS,
    COMPOSITE_WEIGHTS,
    FDR_BIN_REVERSAL,
    ConstructionCandidate,
    ConstructionPolicy,
    InfeasibleGameweek,
    _c5_composite_scores,
    _Candidate,
    _composite_scores,
    _rank_normalize,
    _sort_key,
    build_candidates,
    greedy_by_c5_composite,
    greedy_by_c5_composite_nofdr,
    greedy_by_composite,
    greedy_by_composite_nofdr,
    greedy_by_recent_form,
    greedy_by_season_ppg,
    greedy_by_value,
)
from domain.fpl_squad import BUDGET_CAP_TENTHS, MAX_PER_CLUB, SQUAD_SELECT, SQUAD_SIZE

pytestmark = pytest.mark.unit

POLICIES = (
    greedy_by_season_ppg,
    greedy_by_value,
    greedy_by_recent_form,
    greedy_by_composite,
    greedy_by_composite_nofdr,
    greedy_by_c5_composite,
    greedy_by_c5_composite_nofdr,
)


def _mart(
    counts: dict[str, int],
    gws: range,
    prices: dict[tuple[str, int], float],
    debuts: dict[tuple[str, int], int],
    points: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    player_id = 0
    for position, n in counts.items():
        for slot in range(n):
            player_id += 1
            debut = debuts[(position, slot)]
            for gw in gws:
                played = gw >= debut
                rows.append(
                    {
                        "player_id": player_id,
                        "gw": gw,
                        "position": position,
                        "purchase_price": prices[(position, slot)],
                        "team_id": (player_id % 10) + 1,
                        "minutes": 90 if played else None,
                        "total_points": int(points.integers(0, 12)) if played else None,
                        # Integer FDR ratings 1-5, present for every row including pre-debut ones
                        # (a fixture's difficulty is a property of the club's schedule, not of
                        # whether the player has registered) -- matching the live mart, where
                        # `fdr_avg` is 0/24,918 null at the eligible-candidate grain
                        # (`DESIGN.MD` §7.7).
                        "fdr_avg": float(((player_id + gw) % 5) + 1),
                        # C5's two new terms (`DESIGN.MD` §8.2), both read straight off the
                        # governed mart rather than derived in `candidates.py`. `transfers_in`
                        # is `never_null` at this grain and deliberately spans several orders of
                        # magnitude, matching the live column's shape that §8.3 cites as making
                        # rank normalization non-negotiable.
                        "transfers_in": float(10 ** ((player_id % 5) + 1) + gw),
                    }
                )
    mart = pd.DataFrame(rows)
    mart["minutes"] = mart["minutes"].astype("Int64")
    mart["total_points"] = mart["total_points"].astype("Int64")
    # `minutes_roll3` mirrors the governed FEAT column's construction exactly
    # (`dal/feat/feat_player_gameweek.py:98-101`): lag-1 then a 3-gameweek rolling mean, so a
    # player's first row is NaN and lands in `_sort_key`'s unrankable tier -- the structural
    # cold-start §8.2 measures at 2.827% on the live mart.
    mart["minutes_roll3"] = (
        mart.sort_values(["player_id", "gw"])
        .groupby("player_id")["minutes"]
        .transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        .astype("float64")
    )
    return mart


@pytest.fixture
def mart() -> pd.DataFrame:
    """65 players (10 GK / 20 DEF / 20 MID / 15 FWD) over GW1-5, spread over 10 clubs. Every 4th
    slot debuts at GW3 instead of GW1, so registration filtering has something to exclude."""
    rng = np.random.default_rng(5)
    counts = {"GK": 10, "DEF": 20, "MID": 20, "FWD": 15}
    prices = {
        (position, slot): float(np.round(rng.uniform(4.0, 12.0), 1))
        for position, n in counts.items()
        for slot in range(n)
    }
    debuts = {(position, slot): (3 if slot % 4 == 0 else 1) for position, n in counts.items() for slot in range(n)}
    return _mart(counts, range(1, 6), prices, debuts, rng)


def _is_legal_squad(squad: Sequence[ConstructionCandidate]) -> None:
    assert len(squad) == SQUAD_SIZE
    assert len({c.player_id for c in squad}) == SQUAD_SIZE

    position_counts: dict[str, int] = {}
    club_counts: dict[int, int] = {}
    total_cost = 0
    for candidate in squad:
        position_counts[candidate.position] = position_counts.get(candidate.position, 0) + 1
        club_counts[candidate.team_id] = club_counts.get(candidate.team_id, 0) + 1
        total_cost += candidate.price_tenths

    assert position_counts == dict(SQUAD_SELECT)
    assert all(count <= MAX_PER_CLUB for count in club_counts.values())
    assert total_cost <= BUDGET_CAP_TENTHS


# ---------------------------------------------------------------------------
# Registration filtering
# ---------------------------------------------------------------------------


def test_a_not_yet_debuted_player_is_excluded_at_an_early_gameweek(mart: pd.DataFrame) -> None:
    total_players = mart["player_id"].nunique()
    candidates_gw1 = build_candidates(mart, gw=1)
    candidates_gw5 = build_candidates(mart, gw=5)
    assert len(candidates_gw1) < total_players  # the slot % 4 == 0 group hasn't debuted yet
    assert len(candidates_gw5) == total_players  # everyone has debuted by GW5


def test_every_candidate_carries_a_nan_score_before_a_policy_scores_it(mart: pd.DataFrame) -> None:
    for candidate in build_candidates(mart, gw=4):
        assert candidate.score != candidate.score  # NaN != NaN


def test_season_ppg_is_nan_for_every_candidate_at_gw1(mart: pd.DataFrame) -> None:
    """GW1 is the season's first row for every player -- `shift(1)` has nothing before it."""
    candidates = build_candidates(mart, gw=1)
    assert candidates  # some players are registered from GW1
    assert all(getattr(candidate, "season_ppg") != getattr(candidate, "season_ppg") for candidate in candidates)


# ---------------------------------------------------------------------------
# Each policy produces a legal squad
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_each_policy_produces_a_legal_squad(policy: ConstructionPolicy, mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    squad = policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    _is_legal_squad(squad)


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_each_policy_still_produces_a_legal_squad_at_gw1_with_every_score_nan(
    policy: ConstructionPolicy, mart: pd.DataFrame
) -> None:
    """The degenerate case DECISION.md §4 names: at GW1 every PPG-derived signal is NaN for
    every player, so all three policies fall back to the tie-break order alone -- construction
    must still succeed."""
    candidates = build_candidates(mart, gw=1)
    squad = policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    _is_legal_squad(squad)


# ---------------------------------------------------------------------------
# Infeasibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("policy", POLICIES, ids=lambda p: p.__name__)
def test_an_impossibly_small_budget_raises_infeasible_gameweek(policy: ConstructionPolicy, mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(InfeasibleGameweek):
        policy(candidates, 1, dict(SQUAD_SELECT))


def test_an_impossible_quota_raises_infeasible_gameweek(mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(InfeasibleGameweek):
        greedy_by_season_ppg(candidates, BUDGET_CAP_TENTHS, {"GK": 99, "DEF": 5, "MID": 5, "FWD": 3})


# ---------------------------------------------------------------------------
# C4 -- the composite candidate (`DESIGN.MD` §7.2)
# ---------------------------------------------------------------------------


def test_rank_normalize_maps_ascending_ranks_onto_the_unit_interval() -> None:
    got = _rank_normalize(np.array([10.0, 20.0, 30.0, 40.0, 50.0]))
    np.testing.assert_allclose(got, [0.0, 0.25, 0.5, 0.75, 1.0])


def test_rank_normalize_gives_tied_values_their_average_rank() -> None:
    """`DESIGN.MD` §7.2's "ties taking their average rank" -- and, crucially, a tie's value must
    not depend on the order the tied entries appear in the pool."""
    got = _rank_normalize(np.array([1.0, 2.0, 2.0, 3.0]))
    # ranks 1, (2+3)/2 = 2.5, 2.5, 4 -> (r - 1) / 3
    np.testing.assert_allclose(got, [0.0, 0.5, 0.5, 1.0])
    np.testing.assert_allclose(_rank_normalize(np.array([2.0, 3.0, 1.0, 2.0])), [0.5, 1.0, 0.0, 0.5])


def test_rank_normalize_propagates_nan_without_letting_it_shift_the_scored_ranks() -> None:
    got = _rank_normalize(np.array([10.0, np.nan, 30.0]))
    assert np.isnan(got[1])
    np.testing.assert_allclose(got[[0, 2]], [0.0, 1.0])  # ranked over n = 2, not n = 3


def test_the_fdr_term_is_reversed_so_an_easy_fixture_scores_higher() -> None:
    """Lower fdr is better; §7.2 handles that by reversing the bin before normalizing, so
    `w_fdr` stays strictly positive."""
    easy_last = _rank_normalize(FDR_BIN_REVERSAL - np.array([1.0, 3.0, 5.0]))
    np.testing.assert_allclose(easy_last, [1.0, 0.5, 0.0])


def test_fdr_bin_is_the_ordinal_scheme_not_raw_fdr_avg(mart: pd.DataFrame) -> None:
    """The bins are right-closed on `(i - 0.5, i + 0.5]`, so each integer rating maps to itself."""
    for candidate in build_candidates(mart, gw=4):
        assert getattr(candidate, "fdr_bin") in {1.0, 2.0, 3.0, 4.0, 5.0}


def test_the_composite_score_is_nan_whenever_any_of_its_three_terms_is_nan(mart: pd.DataFrame) -> None:
    """§7.2: a NaN term propagates rather than being imputed to a middling rank."""
    candidates = build_candidates(mart, gw=1)  # every PPG-derived signal is NaN at GW1
    assert candidates
    assert all(c.score != c.score for c in _composite_scores(candidates, COMPOSITE_WEIGHTS))


def test_the_composite_scores_a_candidate_with_a_partially_nan_term_as_nan(mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    scored = _composite_scores(candidates, COMPOSITE_WEIGHTS)
    for original, out in zip(candidates, scored, strict=True):
        any_nan = any(getattr(original, f) != getattr(original, f) for f in ("recent_form_ppg", "value", "fdr_bin"))
        assert (out.score != out.score) == any_nan


def test_the_composite_weights_match_the_current_specification_and_sum_to_one() -> None:
    """Pre-registered, never fitted (§7.2). This test is the record that they were not moved.

    The vector is §7.2's CURRENT SPECIFICATION, which supersedes the equal thirds of C4's first
    run per §7.2.1: the two collinear terms (`recent_form_ppg`, `value`) split one weight-slot
    between them and the orthogonal fdr term takes the other half. §7.2.1 marks this as the final
    weight-vector change for this candidate definition, so this test guards against a third."""
    assert COMPOSITE_WEIGHTS == {"recent_form_ppg": 0.25, "value": 0.25, "fdr": 0.50}
    assert sum(COMPOSITE_WEIGHTS.values()) == pytest.approx(1.0)


def test_a_zero_weight_is_rejected_unless_it_is_the_declared_fdr_ablation(mart: pd.DataFrame) -> None:
    """§7.2's strictly-nonzero invariant, asserted rather than left an accident of the default."""
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(ValueError, match="strictly positive"):
        _composite_scores(candidates, {"recent_form_ppg": 0.5, "value": 0.5, "fdr": 0.0})
    with pytest.raises(ValueError, match="strictly positive"):
        _composite_scores(candidates, {"recent_form_ppg": 0.0, "value": 0.5, "fdr": 0.5}, allow_zero_fdr_weight=True)
    # The one declared exemption is accepted.
    assert _composite_scores(candidates, ABLATION_WEIGHTS, allow_zero_fdr_weight=True)


def test_weights_that_do_not_sum_to_one_are_rejected(mart: pd.DataFrame) -> None:
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(ValueError, match="sum to 1"):
        _composite_scores(candidates, {"recent_form_ppg": 0.5, "value": 0.5, "fdr": 0.5})


def test_the_ablation_weights_redistribute_the_fdr_weight_proportionally() -> None:
    """§7.3: the two variants must differ in exactly one thing -- fdr present or absent -- not in
    fdr *and* the relative balance of the other two."""
    assert ABLATION_WEIGHTS["fdr"] == 0.0
    assert ABLATION_WEIGHTS["recent_form_ppg"] == ABLATION_WEIGHTS["value"]
    assert sum(ABLATION_WEIGHTS.values()) == pytest.approx(1.0)
    kept = COMPOSITE_WEIGHTS["recent_form_ppg"] / COMPOSITE_WEIGHTS["value"]
    assert ABLATION_WEIGHTS["recent_form_ppg"] / ABLATION_WEIGHTS["value"] == pytest.approx(kept)


def test_the_ablation_ignores_the_fdr_term_entirely(mart: pd.DataFrame) -> None:
    """Perturbing every fdr bin must not move a single C4-nofdr score, and must move C4's."""
    candidates = build_candidates(mart, gw=4)
    # Rebuilt rather than `dataclasses.replace`d: `build_candidates` is typed as returning the
    # `ConstructionCandidate` Protocol, and `replace` requires a concrete dataclass type.
    perturbed: list[ConstructionCandidate] = [
        _Candidate(
            player_id=c.player_id,
            position=c.position,
            price_tenths=c.price_tenths,
            team_id=c.team_id,
            season_ppg=getattr(c, "season_ppg"),
            recent_form_ppg=getattr(c, "recent_form_ppg"),
            value=getattr(c, "value"),
            fdr_bin=FDR_BIN_REVERSAL - getattr(c, "fdr_bin"),
            transfers_in=getattr(c, "transfers_in"),
            minutes_roll3=getattr(c, "minutes_roll3"),
            score=c.score,
        )
        for c in candidates
    ]

    base_nofdr = [c.score for c in _composite_scores(candidates, ABLATION_WEIGHTS, allow_zero_fdr_weight=True)]
    perturbed_nofdr = [c.score for c in _composite_scores(perturbed, ABLATION_WEIGHTS, allow_zero_fdr_weight=True)]
    assert base_nofdr == perturbed_nofdr

    base_c4 = [c.score for c in _composite_scores(candidates, COMPOSITE_WEIGHTS)]
    perturbed_c4 = [c.score for c in _composite_scores(perturbed, COMPOSITE_WEIGHTS)]
    assert base_c4 != perturbed_c4


@pytest.mark.parametrize("policy", (greedy_by_composite, greedy_by_composite_nofdr), ids=lambda p: p.__name__)
def test_the_composite_policies_are_deterministic(policy: ConstructionPolicy, mart: pd.DataFrame) -> None:
    """No RNG anywhere in construction: the same pool must give byte-identical squads."""
    candidates = build_candidates(mart, gw=4)
    first = policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    second = policy(build_candidates(mart, gw=4), BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))
    assert [c.player_id for c in first] == [c.player_id for c in second]


def test_the_composite_cannot_collapse_into_one_of_the_baselines(mart: pd.DataFrame) -> None:
    """§7.2's point of the strictly-nonzero weights: every term contributes at every ranking, so
    C4's ordering is its own, not a relabelling of C2's or C3's."""
    candidates = build_candidates(mart, gw=4)
    composite = [c.player_id for c in greedy_by_composite(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))]
    for baseline in (greedy_by_value, greedy_by_recent_form, greedy_by_season_ppg):
        assert composite != [c.player_id for c in baseline(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))]


# ---------------------------------------------------------------------------
# C5 -- the second composite candidate (`DESIGN.MD` §8)
# ---------------------------------------------------------------------------


def test_the_c5_weights_match_the_one_pre_registered_vector_and_sum_to_one() -> None:
    """`DESIGN.MD` §8.4's table -- pre-registered, never fitted, and the **only** vector C5 gets.

    §8.4's terminal clause is explicit that there is no second vector for C5: if this one fails
    `METRIC.md` §2's conjunctive rule, the documented conclusion is that the ingredient set does
    not beat the naive baselines on the data available. This test is the record that the vector
    was not moved after seeing a result.
    """
    assert C5_WEIGHTS == {"transfers_in": 0.25, "minutes_roll3": 0.25, "fdr": 0.50}
    assert sum(C5_WEIGHTS.values()) == pytest.approx(1.0)
    assert all(w > 0.0 for w in C5_WEIGHTS.values())


def test_the_c5_ablation_redistributes_the_fdr_weight_proportionally() -> None:
    """§8.4.1: the fdr term dropped, its weight redistributed proportionally across the other two,
    so the two variants differ in exactly one thing rather than in fdr *and* the relative balance
    of the remaining pair."""
    assert C5_ABLATION_WEIGHTS["fdr"] == 0.0
    assert sum(C5_ABLATION_WEIGHTS.values()) == pytest.approx(1.0)
    kept = C5_WEIGHTS["transfers_in"] / C5_WEIGHTS["minutes_roll3"]
    assert C5_ABLATION_WEIGHTS["transfers_in"] / C5_ABLATION_WEIGHTS["minutes_roll3"] == pytest.approx(kept)


def test_c5_reads_both_new_signals_straight_off_the_mart(mart: pd.DataFrame) -> None:
    """§8.6's Tier A confirmation, at the candidate grain: `transfers_in` and `minutes_roll3` are
    carried through `build_candidates` unchanged from the mart's own columns -- no local
    re-derivation of the kind C4's `season_ppg`/`recent_form_ppg` needed."""
    week = mart.loc[mart["gw"] == 4].set_index("player_id")
    candidates = build_candidates(mart, gw=4)
    assert candidates
    for candidate in candidates:
        row = week.loc[candidate.player_id]
        assert getattr(candidate, "transfers_in") == pytest.approx(float(row["transfers_in"]))
        expected = float(row["minutes_roll3"])
        got = getattr(candidate, "minutes_roll3")
        assert got == pytest.approx(expected) or (got != got and expected != expected)


def test_transfers_in_is_never_nan_at_the_candidate_grain(mart: pd.DataFrame) -> None:
    """§8.2's 0.000%: `transfers_in` is declared `never_null` in the FCT contract
    (`dal/fct/fct_contracts.py:237`), so it never lands a candidate in the unrankable tier."""
    for gw in range(1, 6):
        for candidate in build_candidates(mart, gw):
            assert getattr(candidate, "transfers_in") == getattr(candidate, "transfers_in")


def test_the_c5_score_is_nan_whenever_any_of_its_three_terms_is_nan(mart: pd.DataFrame) -> None:
    """§8.2's stated NaN handling: a missing term propagates to a NaN composite rather than being
    imputed to a middling rank, and `_sort_key`'s existing NaN-last tier absorbs it."""
    candidates = build_candidates(mart, gw=4)
    scored = _c5_composite_scores(candidates, C5_WEIGHTS)
    for original, out in zip(candidates, scored, strict=True):
        any_nan = any(
            getattr(original, field) != getattr(original, field)
            for field in ("transfers_in", "minutes_roll3", "fdr_bin")
        )
        assert (out.score != out.score) == any_nan


def test_a_nan_c5_score_sorts_after_every_scored_candidate(mart: pd.DataFrame) -> None:
    """The unrankable tier §8.2 relies on, checked through `_sort_key` itself rather than assumed
    from `_composite_scores`'s NaN propagation."""
    scored = _c5_composite_scores(build_candidates(mart, gw=2), C5_WEIGHTS)
    ranked = sorted(scored, key=_sort_key)
    unrankable = [i for i, c in enumerate(ranked) if c.score != c.score]
    if unrankable:
        assert unrankable == list(range(len(ranked) - len(unrankable), len(ranked)))


def test_c5_rank_normalization_is_invariant_to_the_transfers_in_magnitude_skew(mart: pd.DataFrame) -> None:
    """§8.3's non-negotiable: `transfers_in` spans five orders of magnitude, so under z-scoring a
    single heavily-transferred player would dominate a fixed-weight sum. Rank normalization removes
    that by construction -- inflating the pool's top `transfers_in` value by 1000x is a monotone
    transform and must not move a single C5 score.
    """
    candidates = build_candidates(mart, gw=4)
    top = max(getattr(c, "transfers_in") for c in candidates)
    inflated: list[ConstructionCandidate] = [
        _Candidate(
            player_id=c.player_id,
            position=c.position,
            price_tenths=c.price_tenths,
            team_id=c.team_id,
            season_ppg=getattr(c, "season_ppg"),
            recent_form_ppg=getattr(c, "recent_form_ppg"),
            value=getattr(c, "value"),
            fdr_bin=getattr(c, "fdr_bin"),
            transfers_in=(
                getattr(c, "transfers_in") * 1000.0 if getattr(c, "transfers_in") == top else getattr(c, "transfers_in")
            ),
            minutes_roll3=getattr(c, "minutes_roll3"),
            score=c.score,
        )
        for c in candidates
    ]
    base = [c.score for c in _c5_composite_scores(candidates, C5_WEIGHTS)]
    after = [c.score for c in _c5_composite_scores(inflated, C5_WEIGHTS)]
    np.testing.assert_allclose(base, after, equal_nan=True)


def test_the_c5_ablation_ignores_the_fdr_term_entirely(mart: pd.DataFrame) -> None:
    """Perturbing every fdr bin must not move a single C5-nofdr score, and must move C5's."""
    candidates = build_candidates(mart, gw=4)
    perturbed: list[ConstructionCandidate] = [
        _Candidate(
            player_id=c.player_id,
            position=c.position,
            price_tenths=c.price_tenths,
            team_id=c.team_id,
            season_ppg=getattr(c, "season_ppg"),
            recent_form_ppg=getattr(c, "recent_form_ppg"),
            value=getattr(c, "value"),
            fdr_bin=FDR_BIN_REVERSAL - getattr(c, "fdr_bin"),
            transfers_in=getattr(c, "transfers_in"),
            minutes_roll3=getattr(c, "minutes_roll3"),
            score=c.score,
        )
        for c in candidates
    ]

    base_nofdr = [c.score for c in _c5_composite_scores(candidates, C5_ABLATION_WEIGHTS, allow_zero_fdr_weight=True)]
    after_nofdr = [c.score for c in _c5_composite_scores(perturbed, C5_ABLATION_WEIGHTS, allow_zero_fdr_weight=True)]
    assert base_nofdr == after_nofdr

    base_c5 = [c.score for c in _c5_composite_scores(candidates, C5_WEIGHTS)]
    after_c5 = [c.score for c in _c5_composite_scores(perturbed, C5_WEIGHTS)]
    assert base_c5 != after_c5


def test_a_zero_c5_weight_is_rejected_unless_it_is_the_declared_fdr_ablation(mart: pd.DataFrame) -> None:
    """The strictly-positive invariant, shared with C4 through `_validate_weights` -- §8.4.1's
    ablation is its one named exemption and must still be taken explicitly, not inferred."""
    candidates = build_candidates(mart, gw=4)
    with pytest.raises(ValueError, match="strictly positive"):
        _c5_composite_scores(candidates, {"transfers_in": 0.5, "minutes_roll3": 0.5, "fdr": 0.0})
    with pytest.raises(ValueError, match="strictly positive"):
        _c5_composite_scores(candidates, {"transfers_in": 0.0, "minutes_roll3": 0.5, "fdr": 0.5})
    with pytest.raises(ValueError, match="must sum to 1"):
        _c5_composite_scores(candidates, {"transfers_in": 0.5, "minutes_roll3": 0.5, "fdr": 0.5})
    with pytest.raises(ValueError, match="missing"):
        _c5_composite_scores(candidates, {"transfers_in": 0.5, "fdr": 0.5})


def test_c5_reads_a_different_ingredient_set_than_c4(mart: pd.DataFrame) -> None:
    """§8.1: C5 is a new candidate definition, not a revision of C4. Perturbing C4's two dropped
    points terms must leave every C5 score untouched -- the one shared ingredient is `fdr_bin`."""
    candidates = build_candidates(mart, gw=4)
    perturbed: list[ConstructionCandidate] = [
        _Candidate(
            player_id=c.player_id,
            position=c.position,
            price_tenths=c.price_tenths,
            team_id=c.team_id,
            season_ppg=-getattr(c, "season_ppg"),
            recent_form_ppg=-getattr(c, "recent_form_ppg"),
            value=-getattr(c, "value"),
            fdr_bin=getattr(c, "fdr_bin"),
            transfers_in=getattr(c, "transfers_in"),
            minutes_roll3=getattr(c, "minutes_roll3"),
            score=c.score,
        )
        for c in candidates
    ]
    base = [c.score for c in _c5_composite_scores(candidates, C5_WEIGHTS)]
    after = [c.score for c in _c5_composite_scores(perturbed, C5_WEIGHTS)]
    np.testing.assert_allclose(base, after, equal_nan=True)


@pytest.mark.parametrize("policy", (greedy_by_c5_composite, greedy_by_c5_composite_nofdr), ids=lambda p: p.__name__)
def test_c5_is_deterministic_across_repeated_calls(policy: ConstructionPolicy, mart: pd.DataFrame) -> None:
    """No RNG anywhere in `candidates.py` -- the same pool must yield the identical squad, in the
    identical order, every time."""
    candidates = build_candidates(mart, gw=4)
    first = [c.player_id for c in policy(candidates, BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))]
    second = [c.player_id for c in policy(build_candidates(mart, gw=4), BUDGET_CAP_TENTHS, dict(SQUAD_SELECT))]
    assert first == second
