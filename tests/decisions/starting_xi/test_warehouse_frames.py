"""Acceptance tests for the warehouse rewire (#43) -- the sampler, the harness and the composition root
read the pinned warehouse frames, not the local mart -- and for the squad modes run on them (#31).

The real fixture under `warehouse/fixtures/` holds two players, too few to fill a squad, so these
tests write a synthetic pinned snapshot in the publish's own schema and read it through
`warehouse.served.load`, exactly as a run does. Its cases:

- 26 players over 13 clubs (2 each), 4 GK / 8 DEF / 8 MID / 6 FWD by `position_id`, every one
  priced 4.5 -- every quota-satisfying draw is feasible, so the pilot never red-lines.
- `DOUBLE_DEFENDER` has a double in GW4: two fixture rows of 25, a gameweek total of 50. A
  realised total read per fixture, or a mart that does not hold him, cannot reach 50.
- `BLANK_KEEPER` blanks in GW5: no fixture row, `fixture_count` 0, null outcomes.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from decisions.starting_xi import harness, orderings, rankers, results, sampler
from operational import starting_xi
from warehouse import served

REPO_ROOT = Path(__file__).resolve().parents[3]
SEASON = "2025-26"
RUN_ID = "synthetic-43"
SEED = 20261017
GAMEWEEKS = range(1, 39)

POSITION_COUNTS = {1: 4, 2: 8, 3: 8, 4: 6}
PLAYER_IDS = list(range(1001, 1001 + sum(POSITION_COUNTS.values())))
BLANK_KEEPER = 1001
DOUBLE_DEFENDER = 1005
DOUBLE_TOTAL = 50


def _position_ids() -> dict[int, int]:
    ids = iter(PLAYER_IDS)
    return {next(ids): position_id for position_id, count in POSITION_COUNTS.items() for _ in range(count)}


def _write(path: Path, rows: list[dict[str, object]], schema: pa.Schema) -> None:
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)


def _int32(*names: str) -> list[tuple[str, pa.DataType]]:
    return [(name, pa.int32()) for name in names]


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, served.Pin]:
    """A synthetic publish with the cases in the module docstring, and the pin it reads under."""
    root = tmp_path_factory.mktemp("warehouse")
    target = root / RUN_ID
    target.mkdir()
    positions = _position_ids()
    club = {player_id: index // 2 + 1 for index, player_id in enumerate(PLAYER_IDS)}

    fixture_rows: list[dict[str, object]] = []
    gameweek_rows: list[dict[str, object]] = []
    for gw in GAMEWEEKS:
        for player_id in PLAYER_IDS:
            if player_id == BLANK_KEEPER and gw == 5:
                fixtures: list[int] = []
            elif player_id == DOUBLE_DEFENDER and gw == 4:
                fixtures = [DOUBLE_TOTAL // 2, DOUBLE_TOTAL // 2]
            else:
                fixtures = [(player_id + gw) % 4]
            for index, points in enumerate(fixtures):
                fixture_rows.append(
                    {
                        "season": SEASON,
                        "fpl_id": player_id,
                        "gameweek": gw,
                        "fixture_id": gw * 100 + club[player_id] * 2 + index,
                        "team_fpl_id": club[player_id],
                        "minutes": 90,
                        "starts": 1,
                        "total_points": points,
                    }
                )
            gameweek_rows.append(
                {
                    "season": SEASON,
                    "fpl_id": player_id,
                    "gameweek": gw,
                    "fixture_count": len(fixtures),
                    "total_points": sum(fixtures) if fixtures else None,
                    "minutes": 90 * len(fixtures) if fixtures else None,
                    "starts": len(fixtures) if fixtures else None,
                    "value": 45 if fixtures else None,
                    "selected": 1000 if fixtures else None,
                }
            )

    _write(
        target / "fct_player_fixture.parquet",
        fixture_rows,
        pa.schema(
            [
                ("season", pa.string()),
                *_int32("fpl_id", "gameweek", "fixture_id", "team_fpl_id", "minutes", "starts", "total_points"),
            ]
        ),
    )
    _write(
        target / "fct_player_gameweek.parquet",
        gameweek_rows,
        pa.schema(
            [
                ("season", pa.string()),
                *_int32(
                    "fpl_id", "gameweek", "fixture_count", "total_points", "minutes", "starts", "value", "selected"
                ),
            ]
        ),
    )
    _write(
        target / "dim_player.parquet",
        [{"season": SEASON, "fpl_id": p, "position_id": positions[p]} for p in PLAYER_IDS],
        pa.schema([("season", pa.string()), *_int32("fpl_id", "position_id")]),
    )
    manifest = {"run_id": RUN_ID, "contract_version": served.CONTRACT_VERSION, "seasons": [SEASON]}
    (target / served.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return root, served.pin_of(target)


def _fixed_squad(gw: int) -> pd.DataFrame:
    """One legal 15 holding both cases: 2 GK, 5 DEF, 5 MID, 3 FWD, at most 2 per club."""
    by_position: dict[int, list[int]] = {}
    for player_id, position_id in _position_ids().items():
        by_position.setdefault(position_id, []).append(player_id)
    picked = by_position[1][:2] + by_position[2][:5] + by_position[3][:5] + by_position[4][:3]
    assert BLANK_KEEPER in picked and DOUBLE_DEFENDER in picked
    return pd.DataFrame({"gw": gw, "squad_id": f"fixed-gw{gw:02d}", "player_id": picked})


@pytest.mark.integration
@pytest.mark.covers("#43 AC1")
def test_the_sampler_draws_squads_from_the_warehouse_frames(snapshot: tuple[Path, served.Pin]) -> None:
    sample = sampler.build_squads([4, 5], 3, SEED, season=SEASON, pin=snapshot[1], snapshot_root=snapshot[0])

    assert set(sample.squads["player_id"]) <= set(PLAYER_IDS)
    positions = _position_ids()
    for _, squad in sample.squads.groupby("squad_id"):
        counts = squad["player_id"].map(positions).value_counts().to_dict()
        assert counts == {1: 2, 2: 5, 3: 5, 4: 3}


@pytest.mark.integration
@pytest.mark.covers("#43 AC1")
def test_the_harness_scores_realised_points_from_the_gameweek_frame(snapshot: tuple[Path, served.Pin]) -> None:
    squads = pd.concat([_fixed_squad(4), _fixed_squad(5)], ignore_index=True)
    rule = rankers.rules(SEED)["random"]

    result = harness.build(
        squads,
        rule,
        orderings.PRE_REGISTERED_ORDERINGS,
        rankers.RULE_WINDOW,
        season=SEASON,
        pin=snapshot[1],
        snapshot_root=snapshot[0],
    )

    t2 = result.squad_weeks.set_index("gw")
    assert sorted(t2.index) == [4, 5]
    # Only the gameweek frame's double total (25 + 25) lets the best XI reach 50; every other player
    # scores at most 3 a fixture, so eleven of them cannot.
    assert t2.loc[4, "best_legal_xi_points"] >= DOUBLE_TOTAL


@pytest.mark.integration
@pytest.mark.covers("#43 AC1")
def test_build_and_run_replays_the_rule_grid_on_the_warehouse_frames(
    snapshot: tuple[Path, served.Pin], tmp_path: Path
) -> None:
    run = starting_xi.build_and_run(
        gameweeks=[4, 5],
        n_squads=2,
        seed=SEED,
        results_root=tmp_path,
        allow_dirty=True,
        allow_off_registration=True,
        season=SEASON,
        pin=snapshot[1],
        snapshot_root=snapshot[0],
    )

    read_back = results.read(tmp_path, run.run_id)
    t2 = read_back["squad_weeks"]
    manifest = read_back["manifest"]
    assert isinstance(t2, pd.DataFrame) and isinstance(manifest, dict)
    assert set(t2["ranker"]) == set(rankers.rules(SEED))
    assert run.n_squad_weeks == 2 * 2 * len(rankers.rules(SEED))
    assert manifest["provenance"]["warehouse_run_id"] == RUN_ID


# Today's uniform squads at GW4-6, three a week, under `SEED` -- captured from `main` at 4bb7ebe,
# before squad modes existed.
UNIFORM_SQUAD_SET_ID = "076cc304dfa260ac81cd1db9ea015c16154221ece7bdedef1b7309c68ddb7e6a"


@pytest.mark.integration
@pytest.mark.covers("#31 AC1")
def test_uniform_mode_draws_todays_squads_byte_for_byte(snapshot: tuple[Path, served.Pin]) -> None:
    sample = sampler.build_squads(
        [4, 5, 6], 3, SEED, squad_mode="uniform", season=SEASON, pin=snapshot[1], snapshot_root=snapshot[0]
    )

    assert sample.squad_set_id == UNIFORM_SQUAD_SET_ID


def _agrees_with_random_at_gw4(frames: served.Frames) -> rankers.RankerOutput:
    """A second random rule: the grid's own at GW4, a differently seeded one elsewhere, so GW4 is a
    zero-information week for every squad and the other weeks are not."""
    same = rankers.rules(SEED)["random"](frames).scores
    other = rankers.rules(SEED + 1)["random"](frames).scores
    scores = pd.concat([same.loc[same["gw"] == 4], other.loc[other["gw"] != 4]])
    return rankers.RankerOutput(
        name="random_reseeded",
        window=rankers.RULE_WINDOW,
        scores=scores.sort_values(["player_id", "gw"], ignore_index=True),
    )


@pytest.mark.integration
@pytest.mark.covers("#31 AC4")
@pytest.mark.parametrize("squad_mode", ["uniform", "ownership"])
def test_squad_weeks_where_every_rule_picks_the_same_xi_are_excluded_and_counted(
    snapshot: tuple[Path, served.Pin], tmp_path: Path, squad_mode: str
) -> None:
    rank_fns = {"random": rankers.rules(SEED)["random"], "random_reseeded": _agrees_with_random_at_gw4}
    n_squads, gameweeks = 3, [4, 5, 6]
    run = starting_xi.build_and_run(
        rank_fns=rank_fns,
        gameweeks=gameweeks,
        n_squads=n_squads,
        seed=SEED,
        squad_mode=squad_mode,
        results_root=tmp_path,
        allow_dirty=True,
        allow_off_registration=True,
        season=SEASON,
        pin=snapshot[1],
        snapshot_root=snapshot[0],
    )

    read_back = results.read(tmp_path, run.run_id)
    t2, manifest = read_back["squad_weeks"], read_back["manifest"]
    assert isinstance(t2, pd.DataFrame) and isinstance(manifest, dict)
    assert 4 not in set(t2["gw"])
    excluded = manifest["zero_information_excluded"]
    assert manifest["squad_mode"] == squad_mode
    assert excluded >= n_squads
    assert excluded == n_squads * len(gameweeks) - t2[["squad_id", "gw"]].drop_duplicates().shape[0]


@pytest.mark.integration
@pytest.mark.covers("#31 AC5")
def test_only_gameweeks_4_to_38_are_scored(snapshot: tuple[Path, served.Pin], tmp_path: Path) -> None:
    run = starting_xi.build_and_run(
        gameweeks=[2, 3, 4, 5],
        n_squads=2,
        seed=SEED,
        squad_mode="uniform",
        results_root=tmp_path,
        allow_dirty=True,
        allow_off_registration=True,
        season=SEASON,
        pin=snapshot[1],
        snapshot_root=snapshot[0],
    )

    read_back = results.read(tmp_path, run.run_id)
    for table in ("squad_weeks", "ordering_replays"):
        frame = read_back[table]
        assert isinstance(frame, pd.DataFrame)
        assert set(frame["gw"]) == {4, 5}, table


def _imports_dal_pipeline(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import) and any(alias.name.startswith("dal.pipeline") for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.startswith("dal.pipeline"):
                return True
            if node.module == "dal" and any(alias.name == "pipeline" for alias in node.names):
                return True
    return False


@pytest.mark.integration
@pytest.mark.covers("#43 AC1")
@pytest.mark.parametrize(
    "module",
    [*sorted((REPO_ROOT / "decisions" / "starting_xi").glob("*.py")), REPO_ROOT / "operational" / "starting_xi.py"],
    ids=lambda path: str(path.relative_to(REPO_ROOT)),
)
def test_nothing_in_starting_xi_imports_the_local_mart_loader(module: Path) -> None:
    assert not _imports_dal_pipeline(module)
