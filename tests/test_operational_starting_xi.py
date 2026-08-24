"""Tests for the `starting_xi` composition root (`operational.starting_xi`).

`DESIGN.md` §5.1.2 puts T3 assembly here as named private functions taking and returning frames,
precisely so it is testable without `dal/` or `model/`: most of this suite constructs T2/T5 directly
and calls `_determine_floor`, `_difference_and_restrict`, `_derive_ordering_relevant_count` and
`_assemble_comparison` against a hand-verifiable case, rather than running the harness to get one.

The one end-to-end pass (`test_run_study_end_to_end_on_a_small_fixture`) exercises `run_study` for
real -- the sampler's actual rejection sampling and the harness's actual replay -- against fake,
cheap rankers standing in for `rankers.py`'s real `p_play`/PPG fits, on the same small-universe
convention `decisions/starting_xi/test_sampler.py` uses (a feasible, budget-and-club-legal universe
small enough to run a real pilot over).
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from decisions.starting_xi import rankers, results
from operational import starting_xi
from operational.starting_xi import run_study

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# A small, sampler-feasible mart (convention: decisions/starting_xi/test_sampler.py's `mart`)
# ---------------------------------------------------------------------------


def _small_mart(n_gw: int = 8, seed: int = 3) -> pd.DataFrame:
    """68 players over GK/DEF/MID/FWD, GW1..`n_gw`, 8 clubs, prices spread so §2.6's uniform
    rejection sampling clears the proceed threshold on a real pilot."""
    rng = np.random.default_rng(seed)
    counts = {"GK": 10, "DEF": 22, "MID": 24, "FWD": 12}
    rows: list[dict[str, object]] = []
    player_id = 0
    for position, n in counts.items():
        for slot in range(n):
            player_id += 1
            # A narrower band than the real price range keeps a 2/5/5/3 squad affordable under
            # the 100.0 cap on this small a universe; a wider one red-lines the pilot (§2.6).
            price = float(np.round(rng.uniform(4.0, 8.0), 1))
            team = (player_id % 8) + 1
            debut = 1 if slot % 3 else 2
            for gw in range(1, n_gw + 1):
                minutes = None if gw < debut else 90.0
                rows.append(
                    {
                        "player_id": player_id,
                        "gw": gw,
                        "position": position,
                        "purchase_price": price,
                        "team_id": team,
                        "minutes": minutes,
                        "total_points": None if minutes is None else float(rng.integers(0, 12)),
                    }
                )
    mart = pd.DataFrame(rows)
    mart["minutes"] = mart["minutes"].astype("Float64")
    mart["total_points"] = mart["total_points"].astype("Float64")
    return mart


@dataclass(frozen=True)
class _FakeRanker:
    """A stand-in for §6.1's `RankerOutput`, satisfying the harness's protocol structurally."""

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


def _fake_rank_fns(mart: pd.DataFrame) -> dict[str, Callable[[pd.DataFrame], _FakeRanker]]:
    """One fake ranker per pre-registered name, at that name's real declared window.

    Cheap and deterministic, standing in for the real `p_play`/PPG fits -- `rankers.py`'s own
    tests cover those; this module's job is the wiring around them, not the fits themselves.
    """

    def _make(name: str) -> Callable[[pd.DataFrame], _FakeRanker]:
        window = rankers.DECLARED_WINDOWS[name]

        def _rank(m: pd.DataFrame) -> _FakeRanker:
            scores = m.loc[:, ["player_id", "gw"]].copy()
            scores["score"] = m["total_points"].fillna(0.0) - m["player_id"].astype(float) * 0.001
            return _FakeRanker(name=name, window=window, scores=scores)

        return _rank

    return {name: _make(name) for name in rankers.FLOOR_RANKERS}


# ---------------------------------------------------------------------------
# §5.1.2's end-to-end pass: the DB-free core, on a small fixture
# ---------------------------------------------------------------------------


def test_run_study_end_to_end_on_a_small_fixture(tmp_path) -> None:
    mart = _small_mart(n_gw=8)
    rank_fns = _fake_rank_fns(mart)

    run = run_study(mart, rank_fns=rank_fns, gameweeks=range(2, 9), n_squads=5, seed=7, results_root=tmp_path)

    assert run.n_squad_weeks > 0
    # The module docstring's resolution: no name in `rank_fns` is outside the floor set, so there
    # is no candidate and zero comparisons -- not an omission, see `_assemble_comparisons`.
    assert run.n_comparisons == 0
    assert run.results_dir == tmp_path / run.run_id

    read_back = results.read(tmp_path, run.run_id)
    assert len(read_back["squad_weeks"]) == run.n_squad_weeks
    assert list(read_back["comparisons"].columns) == list(results.T3_COLUMNS)
    assert read_back["comparisons"].empty
    assert set(read_back["squad_weeks"]["ranker"]) == set(rankers.FLOOR_RANKERS)


def test_same_seed_reproduces_run_id_and_squad_set_id(tmp_path) -> None:
    mart = _small_mart(n_gw=8)
    rank_fns = _fake_rank_fns(mart)
    kwargs = dict(rank_fns=rank_fns, gameweeks=range(2, 9), n_squads=5, seed=11)

    first = run_study(mart, results_root=tmp_path / "a", **kwargs)
    second = run_study(mart, results_root=tmp_path / "b", **kwargs)

    assert first.run_id == second.run_id
    manifest_a = json.loads((tmp_path / "a" / first.run_id / "manifest.json").read_text())
    manifest_b = json.loads((tmp_path / "b" / second.run_id / "manifest.json").read_text())
    assert manifest_a["identity"]["squad_set_id"] == manifest_b["identity"]["squad_set_id"]


def test_write_t1_is_never_called() -> None:
    """§7.8's `T1HasNoProducer` gap -- the composition root must not attempt to fabricate T1."""
    source = inspect.getsource(starting_xi)
    assert "write_t1" not in source


def test_importing_the_composition_root_reaches_model_and_dal_and_not_research() -> None:
    """§3.8: the composition root is the one legal place Tier A and Tier B meet, so `model` (via
    `rankers.py`) and `dal` (via `dal.pipeline.load`) are expected. `research` is not needed by
    anything this module imports and must not leak in -- §3.9 excludes it from both tiers.

    `serve` is *not* asserted absent: `operational/__init__.py` eagerly re-exports
    `operational.recommend`, which imports `serve`, so `import operational.starting_xi` always
    executes that package `__init__` first and pulls `serve` in regardless of what
    `starting_xi.py` itself imports (§5.6's re-export hazard, pre-existing and unrelated to this
    module). Asserting its absence would be asserting something false about this repository.
    """
    program = (
        "import sys; import operational.starting_xi; "
        "reached = {m.split('.')[0] for m in sys.modules}; "
        "assert 'model' in reached, reached; "
        "assert 'dal' in reached, reached; "
        "assert 'research' not in reached, reached"
    )
    assert subprocess.run([sys.executable, "-c", program], check=False).returncode == 0


# ---------------------------------------------------------------------------
# §5.1.2's private functions, on constructed frames
# ---------------------------------------------------------------------------


def _t2_row(
    squad_id: str,
    gw: int,
    ranker: str,
    regret: float,
    *,
    is_zero_gap: bool = False,
    substitution_fired: bool = False,
    uncovered_blank: bool = False,
    no_fixture_rule_changed_xi: bool = False,
) -> dict[str, object]:
    return {
        "squad_id": squad_id,
        "gw": gw,
        "ranker": ranker,
        "regret": regret,
        "is_zero_gap": is_zero_gap,
        "substitution_fired": substitution_fired,
        "uncovered_blank": uncovered_blank,
        "no_fixture_rule_changed_xi": no_fixture_rule_changed_xi,
    }


def _constant_regret_t2(
    candidate_regret: float,
    floor_a_regret: float,
    floor_b_regret: float,
    *,
    gws: range = range(2, 10),
    n_squads: int = 4,
) -> pd.DataFrame:
    """A T2 fixture with no squad-week or gameweek variance, so the bootstrap intervals collapse
    to a single point and the S1/S2/S3 outcome is exact rather than approximate."""
    rows = []
    for gw in gws:
        for index in range(n_squads):
            squad_id = f"gw{gw:02d}-{index:04d}"
            rows.append(_t2_row(squad_id, gw, "candidate", candidate_regret))
            rows.append(_t2_row(squad_id, gw, rankers.F2_SEASON_PPG, floor_a_regret))
            rows.append(_t2_row(squad_id, gw, rankers.F3_FORM_ROLL3, floor_b_regret))
    return pd.DataFrame(rows)


_EMPTY_T5 = pd.DataFrame(columns=["squad_id", "gw", "ranker", "substitution_fired", "entered_outfield"])


def test_determine_floor_picks_the_lower_mean_regret_naive_ranker() -> None:
    t2 = _constant_regret_t2(1.0, 1.5, 2.0)
    floor_ranker, floor_mean_regret = starting_xi._determine_floor(
        t2, [rankers.F2_SEASON_PPG, rankers.F3_FORM_ROLL3], (2, 9)
    )
    assert floor_ranker == rankers.F2_SEASON_PPG
    assert floor_mean_regret == pytest.approx(1.5)


def test_difference_and_restrict_drops_zero_gap_rows_and_the_window() -> None:
    t2 = pd.DataFrame(
        [
            _t2_row("s1", 2, "candidate", 1.0),
            _t2_row("s1", 2, rankers.F2_SEASON_PPG, 1.5),
            _t2_row("s2", 3, "candidate", 1.0, is_zero_gap=True),
            _t2_row("s2", 3, rankers.F2_SEASON_PPG, 1.5, is_zero_gap=True),
            _t2_row("s3", 10, "candidate", 9.0),  # outside the window
            _t2_row("s3", 10, rankers.F2_SEASON_PPG, 9.0),
        ]
    )
    panel = starting_xi._difference_and_restrict(t2, "candidate", rankers.F2_SEASON_PPG, (2, 5))
    assert list(panel["squad_id"]) == ["s1"]
    assert panel["value"].iloc[0] == pytest.approx(0.5)  # floor(1.5) - candidate(1.0)


def test_derive_ordering_relevant_count_matches_section_7_2_1() -> None:
    def _row(squad_id: str, fired: bool, entered: tuple[int, ...]) -> dict[str, object]:
        return {
            "squad_id": squad_id,
            "gw": 2,
            "ranker": "candidate",
            "substitution_fired": fired,
            "entered_outfield": entered,
        }

    t5 = pd.DataFrame(
        [
            _row("s1", True, (1, 2, 3)),
            _row("s1", True, (4, 5, 6)),
            _row("s2", True, (1, 2, 3)),
            _row("s2", True, (1, 2, 3)),
            _row("s3", False, ()),
            _row("s3", False, ()),
        ]
    )
    count = starting_xi._derive_ordering_relevant_count(t5, "candidate", (2, 2))
    # s1: substitution fired and the two orderings' entering sets differ -- relevant.
    # s2: substitution fired but both orderings brought on the same player -- not relevant.
    # s3: no substitution fired at all -- not relevant, regardless of the (empty) sets.
    assert count == 1


def test_assemble_comparison_evaluated_pass_case_is_hand_verifiable() -> None:
    """A constant regret gap has a degenerate (zero-width) bootstrap interval at exactly the
    gap's value, which is what makes S1/S2/S3 exact here rather than approximate."""
    t2 = _constant_regret_t2(candidate_regret=1.0, floor_a_regret=1.5, floor_b_regret=2.0)
    row = starting_xi._assemble_comparison("candidate", [rankers.F2_SEASON_PPG, rankers.F3_FORM_ROLL3], t2, _EMPTY_T5)

    assert row["status"] == "evaluated"
    assert row["floor_ranker"] == rankers.F2_SEASON_PPG
    assert row["floor_mean_regret"] == pytest.approx(1.5)
    assert row["candidate_mean_regret"] == pytest.approx(1.0)
    assert row["abs_reduction"] == pytest.approx(0.5)
    assert row["rel_reduction"] == pytest.approx(0.5 / 1.5)
    assert row["ci_squads_lo"] == pytest.approx(0.5)
    assert row["ci_squads_hi"] == pytest.approx(0.5)
    assert row["ci_gw_lo"] == pytest.approx(0.5)
    assert row["ci_gw_hi"] == pytest.approx(0.5)
    assert (row["crit_direction"], row["crit_significance"], row["crit_materiality"], row["passed"]) == (
        True,
        True,
        True,
        True,
    )


def test_assemble_comparison_fails_materiality_below_ten_percent() -> None:
    """§0.15: a real, significant, correctly-directed improvement still fails the bar below 10%."""
    t2 = _constant_regret_t2(candidate_regret=1.45, floor_a_regret=1.5, floor_b_regret=2.0)
    row = starting_xi._assemble_comparison("candidate", [rankers.F2_SEASON_PPG, rankers.F3_FORM_ROLL3], t2, _EMPTY_T5)

    assert row["status"] == "evaluated"
    assert row["crit_direction"] is True
    assert row["crit_significance"] is True
    assert row["crit_materiality"] is False
    assert row["passed"] is False


def test_assemble_comparison_underpowered_below_one_bootstrap_block() -> None:
    t2 = _constant_regret_t2(1.0, 1.5, 2.0, gws=range(2, 5))  # 3 gameweeks < MIN_SCOREABLE_GW
    row = starting_xi._assemble_comparison("candidate", [rankers.F2_SEASON_PPG, rankers.F3_FORM_ROLL3], t2, _EMPTY_T5)

    assert row["status"] == "underpowered"
    assert row["n_scoreable_gw"] == 3
    assert row["floor_mean_regret"] == pytest.approx(1.5)
    assert row["ci_squads_lo"] is None
    assert row["ci_gw_lo"] is None
    assert row["crit_significance"] is None
    assert row["passed"] is None
    # §7.5: point estimates need no interval, so direction and materiality are still populated.
    assert row["crit_direction"] is True
    assert row["crit_materiality"] is True


def test_assemble_comparison_not_evaluable_on_empty_window_intersection() -> None:
    t2 = pd.DataFrame(
        [
            _t2_row("s1", 2, "candidate", 1.0),
            _t2_row("s2", 10, rankers.F2_SEASON_PPG, 1.5),
        ]
    )
    row = starting_xi._assemble_comparison("candidate", [rankers.F2_SEASON_PPG], t2, _EMPTY_T5)

    assert row["status"] == "not_evaluable"
    assert row["window_first_gw"] == 10
    assert row["window_last_gw"] == 2
    assert row["floor_ranker"] is None
    assert row["n_scoreable_gw"] is None


def test_assemble_comparisons_is_empty_when_rank_fns_is_the_floor_set_alone() -> None:
    """The module docstring's resolution: with no name in `rank_fns` outside the floor set, there
    is no candidate to compare against it, and T3 is a correctly-schematised zero-row frame."""
    t2 = _constant_regret_t2(1.0, 1.5, 2.0)
    rank_fns = dict.fromkeys(rankers.FLOOR_RANKERS)
    t3 = starting_xi._assemble_comparisons(t2, _EMPTY_T5, rank_fns)

    assert t3.empty
    assert list(t3.columns) == list(results.T3_COLUMNS[1:])


def test_assemble_comparisons_forms_one_comparison_per_non_floor_name() -> None:
    """A name in `rank_fns` that is not in `rankers.FLOOR_RANKERS` is a candidate, and gets its
    own T3 row against the floor set present in `rank_fns` (module docstring's resolution)."""
    rows = []
    for gw in range(2, 10):
        for index in range(4):
            squad_id = f"gw{gw:02d}-{index:04d}"
            rows.append(_t2_row(squad_id, gw, rankers.F2_SEASON_PPG, 1.5))
            rows.append(_t2_row(squad_id, gw, rankers.F3_FORM_ROLL3, 2.0))
            rows.append(_t2_row(squad_id, gw, "a_candidate", 0.5))
    t2 = pd.DataFrame(rows)
    rank_fns = {rankers.F2_SEASON_PPG: None, rankers.F3_FORM_ROLL3: None, "a_candidate": None}

    t3 = starting_xi._assemble_comparisons(t2, _EMPTY_T5, rank_fns)

    assert list(t3["comparison_id"]) == ["a_candidate"]
    assert t3.iloc[0]["status"] == "evaluated"
    assert t3.iloc[0]["floor_ranker"] == rankers.F2_SEASON_PPG
    assert t3.iloc[0]["candidate_mean_regret"] == pytest.approx(0.5)
