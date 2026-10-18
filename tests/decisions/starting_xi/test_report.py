"""#32 -- Stage 3 regret reporting (CARD.md §3, "Report per rule").

Every panel here is hand-built, so each expected figure is worked out in the test rather than read
back from the module. Descriptive only: nothing here asserts a pass/fail verdict, because the
report carries none.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import pytest

from decisions.starting_xi import report
from decisions.starting_xi.uncertainty import gameweek_block_ci

pytestmark = pytest.mark.unit

POSITION_COLUMNS = ("regret_gk", "regret_def", "regret_mid", "regret_fwd")


def _xi(first: int) -> str:
    return ",".join(str(p) for p in range(first, first + 11))


def _row(
    squad_id: str,
    gw: int,
    ranker: str,
    regret: float,
    *,
    xi: str | None = None,
    flagged: bool = False,
    positions: Sequence[float] | None = None,
) -> dict[str, object]:
    """One T2 row. The ideal scores 60; the chosen XI scores 60 - regret with and without subs,
    so XI and no-subs regret agree unless a test says otherwise, and no substitution fired."""
    split = positions if positions is not None else (0.0, 0.0, 0.0, regret)
    return {
        "squad_id": squad_id,
        "gw": gw,
        "ranker": ranker,
        "chosen_xi": xi if xi is not None else _xi(0),
        "chosen_xi_points": 60.0 - regret,
        "no_subs_xi_points": 60.0 - regret,
        "best_legal_xi_points": 60.0,
        "regret": regret,
        **dict(zip(POSITION_COLUMNS, split, strict=True)),
        "is_zero_information": flagged,
        "substitution_fired": False,
        "best_permutation_total": 60.0 - regret,
    }


def _artefact(rows: Sequence[dict[str, object]], *, squad_mode: str = "uniform", zero_information: int = 0) -> dict:
    """The shape `results.read` returns, reduced to what reporting reads."""
    return {
        "squad_weeks": pd.DataFrame(rows),
        "manifest": {
            "identity": {"squad_mode": squad_mode},
            "metadata": {"zero_information_squad_weeks": zero_information},
        },
    }


def _two_rule_panel(gameweeks: Sequence[int] = tuple(range(4, 16)), squads: int = 2) -> list[dict[str, object]]:
    """`random` and `D1_season` over every gameweek; D1 picks a different XI and regrets 1 less."""
    rows = []
    for gw in gameweeks:
        for index in range(squads):
            base = float((gw * 7 + index * 3) % 5) + 2.0
            rows.append(_row(f"s{index}", gw, "random", base, xi=_xi(0)))
            rows.append(_row(f"s{index}", gw, "D1_season", base - 1.0, xi=_xi(1)))
    return rows


# ---------------------------------------------------------------------------
# AC1 -- the statistics, and the empty segment
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC1")
def test_mean_median_and_p90_match_a_hand_built_panel() -> None:
    # 1..10: mean 5.5, median 5.5, P90 by linear interpolation 1 + 0.9 * 9 = 9.1.
    summary = report.summarise(pd.Series([float(v) for v in range(1, 11)]))
    assert summary == {"n": 10, "mean": 5.5, "median": 5.5, "p90": pytest.approx(9.1)}


@pytest.mark.covers("#32 AC1")
def test_an_empty_segment_is_reported_as_empty_not_nan() -> None:
    assert report.summarise(pd.Series([], dtype=float)) == {"n": 0, "mean": None, "median": None, "p90": None}


@pytest.mark.covers("#32 AC1")
def test_the_rule_table_carries_xi_bench_order_and_no_subs_regret_as_separate_columns() -> None:
    rows = _two_rule_panel()
    rows[0] = _row("s0", 4, "random", 5.0, xi=_xi(0)) | {"no_subs_xi_points": 50.0}  # no-subs regret 10
    table = report.build([_artefact(rows)]).rules
    random = table.loc[("uniform", "random")]

    expected_xi = pd.Series([r["regret"] for r in rows if r["ranker"] == "random"])
    assert random["xi_mean"] == pytest.approx(expected_xi.mean())
    assert random["xi_median"] == pytest.approx(expected_xi.median())
    assert random["xi_p90"] == pytest.approx(expected_xi.quantile(0.9))
    assert random["no_subs_mean"] != random["xi_mean"]
    assert {"bench_order_mean", "bench_order_median", "bench_order_p90"} <= set(table.columns)


@pytest.mark.covers("#32 AC1")
def test_an_empty_phase_is_listed_with_no_squad_weeks() -> None:
    phases = report.build([_artefact(_two_rule_panel(gameweeks=range(4, 13)))]).phases
    late = phases.loc[("uniform", "random", "27-38")]
    assert late["n"] == 0
    assert late["mean"] is None


# ---------------------------------------------------------------------------
# AC2 -- the random (0%) -> hindsight-ideal (100%) scale
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC2")
def test_random_reads_zero_and_the_hindsight_ideal_reads_one_hundred() -> None:
    assert report.scale_position(rule_mean=4.0, random_mean=4.0) == 0.0
    assert report.scale_position(rule_mean=0.0, random_mean=4.0) == 100.0
    assert report.scale_position(rule_mean=1.0, random_mean=4.0) == 75.0


@pytest.mark.covers("#32 AC2")
def test_the_rule_table_places_random_at_zero_percent() -> None:
    table = report.build([_artefact(_two_rule_panel())]).rules
    assert table.loc[("uniform", "random"), "xi_scale_pct"] == 0.0
    assert 0.0 < table.loc[("uniform", "D1_season"), "xi_scale_pct"] < 100.0


# ---------------------------------------------------------------------------
# AC3 -- position segments decompose the total (the harness half is in test_harness.py)
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC3")
def test_mean_position_regrets_sum_to_mean_xi_regret_and_may_be_negative() -> None:
    rows = [
        _row("s0", 4, "D1_season", 9.0, positions=(0.0, 0.0, -1.0, 10.0)),
        _row("s1", 4, "D1_season", 3.0, positions=(1.0, 2.0, 0.0, 0.0)),
    ]
    artefact = _artefact(rows)
    positions = report.build([artefact]).positions.xs(("uniform", "D1_season"))

    assert positions.loc["MID", "mean"] == -0.5
    assert positions["mean"].sum() == pytest.approx(
        report.build([artefact]).rules.loc[("uniform", "D1_season"), "xi_mean"]
    )


# ---------------------------------------------------------------------------
# AC4 -- phase edges are inclusive
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC4")
@pytest.mark.parametrize(
    ("gw", "phase"), [(4, "4-12"), (12, "4-12"), (13, "13-26"), (26, "13-26"), (27, "27-38"), (38, "27-38")]
)
def test_gameweeks_fall_in_their_inclusive_phase(gw: int, phase: str) -> None:
    assert report.phase_of(gw) == phase


@pytest.mark.covers("#32 AC4")
@pytest.mark.parametrize("gw", [3, 39])
def test_a_gameweek_outside_the_scored_season_raises(gw: int) -> None:
    with pytest.raises(ValueError, match="phase"):
        report.phase_of(gw)


# ---------------------------------------------------------------------------
# AC5 -- paired block-bootstrap ranges
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC5")
def test_a_rule_offset_by_a_constant_has_its_range_offset_by_exactly_that_constant() -> None:
    """Paired resamples draw the same gameweek blocks for every rule, so a rule whose regret is
    another's minus 1 on every squad-week has a range exactly 1 lower. Independent draws would not."""
    ranges = report.paired_ranges(pd.DataFrame(_two_rule_panel()), "regret")
    (random_lo, random_hi), (d1_lo, d1_hi) = ranges["random"], ranges["D1_season"]
    assert d1_lo == pytest.approx(random_lo - 1.0)
    assert d1_hi == pytest.approx(random_hi - 1.0)


@pytest.mark.covers("#32 AC5")
def test_ranges_resample_the_per_gameweek_mean_with_the_pre_registered_block_bootstrap() -> None:
    panel = pd.DataFrame(_two_rule_panel())
    series = panel.loc[panel["ranker"] == "random"].groupby("gw")["regret"].mean().to_numpy()
    expected = gameweek_block_ci(series, n_scoreable_gw=len(series))
    assert report.paired_ranges(panel, "regret")["random"] == pytest.approx(expected)


@pytest.mark.covers("#32 AC5")
def test_rules_covering_different_gameweeks_cannot_be_paired() -> None:
    panel = pd.DataFrame(_two_rule_panel())
    panel = panel.loc[~((panel["ranker"] == "D1_season") & (panel["gw"] == 4))]
    with pytest.raises(ValueError, match="paired"):
        report.paired_ranges(panel, "regret")


# ---------------------------------------------------------------------------
# AC6 -- zero-information squad-weeks
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC6")
def test_flagged_rows_are_excluded_from_every_statistic_and_segment() -> None:
    clean = _two_rule_panel()
    flagged = [
        _row("z", gw, ranker, 1000.0, xi=_xi(0), flagged=True, positions=(1000.0, 0.0, 0.0, 0.0))
        for gw in (4, 30)
        for ranker in ("random", "D1_season")
    ]
    with_flags = report.build([_artefact(clean + flagged, zero_information=2)])
    without = report.build([_artefact(clean, zero_information=2)])

    pd.testing.assert_frame_equal(with_flags.rules, without.rules)
    pd.testing.assert_frame_equal(with_flags.positions, without.positions)
    pd.testing.assert_frame_equal(with_flags.phases, without.phases)
    pd.testing.assert_frame_equal(with_flags.agreement, without.agreement)


@pytest.mark.covers("#32 AC6")
def test_the_manifests_zero_information_count_is_reported_with_its_squad_mode() -> None:
    built = report.build([_artefact(_two_rule_panel(), squad_mode="ownership_weighted", zero_information=7)])
    assert built.zero_information == {"ownership_weighted": 7}


@pytest.mark.covers("#32 AC6")
def test_an_artefact_whose_manifest_lacks_the_count_raises() -> None:
    artefact = _artefact(_two_rule_panel())
    del artefact["manifest"]["metadata"]["zero_information_squad_weeks"]
    with pytest.raises(KeyError, match="zero_information_squad_weeks"):
        report.build([artefact])


# ---------------------------------------------------------------------------
# AC7 (proposed) -- rule agreement from chosen_xi
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC7 (proposed)")
def test_agreement_is_the_mean_share_of_xi_picks_two_rules_have_in_common() -> None:
    # s0: XIs 0-10 vs 1-11 share 10 of 11; s1: identical XIs share 11 of 11. Mean 21/22.
    rows = [
        _row("s0", 4, "random", 2.0, xi=_xi(0)),
        _row("s0", 4, "D1_season", 1.0, xi=_xi(1)),
        _row("s1", 4, "random", 2.0, xi=_xi(5)),
        _row("s1", 4, "D1_season", 1.0, xi=_xi(5)),
    ]
    agreement = report.build([_artefact(rows)]).agreement
    pair = agreement.loc[("uniform", "D1_season", "random"), "share_in_common"]
    assert pair == pytest.approx(21 / 22)
    assert len(agreement) == 1, "one row per unordered rule pair"


# ---------------------------------------------------------------------------
# AC8 (proposed) -- both squad modes side by side
# ---------------------------------------------------------------------------


@pytest.mark.covers("#32 AC8 (proposed)")
def test_both_squad_modes_are_reported_side_by_side_in_one_table() -> None:
    uniform = _artefact(_two_rule_panel(), squad_mode="uniform", zero_information=1)
    weighted_rows = [r | {"regret": float(r["regret"]) + 1.0} for r in _two_rule_panel()]  # type: ignore[arg-type]
    weighted = _artefact(weighted_rows, squad_mode="ownership_weighted", zero_information=3)
    built = report.build([uniform, weighted])

    assert set(built.rules.index.get_level_values("squad_mode")) == {"uniform", "ownership_weighted"}
    assert built.zero_information == {"uniform": 1, "ownership_weighted": 3}
    gap = (
        built.rules.loc[("ownership_weighted", "random"), "xi_mean"] - built.rules.loc[("uniform", "random"), "xi_mean"]
    )
    assert gap == pytest.approx(1.0)


@pytest.mark.covers("#32 AC8 (proposed)")
def test_two_artefacts_with_the_same_squad_mode_raise() -> None:
    with pytest.raises(ValueError, match="squad_mode"):
        report.build([_artefact(_two_rule_panel()), _artefact(_two_rule_panel())])
