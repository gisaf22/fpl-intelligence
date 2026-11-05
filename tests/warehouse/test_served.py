"""Acceptance tests for the served-publish loader (#29).

The fixture under `warehouse/fixtures/40289379567/` is a real sample of fpl-warehouse publish run
40289379567: its `_manifest.json` verbatim, the `fct_player_fixture`, `fct_player_gameweek` and
`dim_player` rows of two players, both seasons, the `fct_manager_pick` and `fct_manager_gameweek`
rows of one manager, and the `dim_gameweek` rows of 2026-27 GW1-8 and 2025-26 GW1, written with the
publish's own arrow schema.

- `fpl_id` 149 (2025-26): starts at club 6, loans to club 19 from GW4, returns to club 6 from GW24;
  blank in GW34; double in GW33.
- `fpl_id` 691 (2025-26): enters at GW2; GW1 is a pre-entry row (`fixture_count` 0, nulls).
- `fpl_id` 149 also carries 2026-27 rows (GW1-7), so a season filter that leaks shows up. Their
  `fixture_count_at_deadline` is NULL at GW1-2 (no capture before those deadlines) and 1 from GW3;
  every 2025-26 row's is NULL.
- `entry_id` 7254 (2026-27, GW1-7): Bench Boost in GW2, Free Hit in GW3, auto-subs in GW5 and GW6.
- `dim_gameweek`: `ranked_count` is set for 2026-27 GW1-7 and null at GW8 and for 2025-26.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from warehouse import served

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "warehouse" / "fixtures"
RUN_ID = "40289379567"
SEASON = "2025-26"
LOAN_AND_RETURN = 149
LATE_ENTRANT = 691
MANAGER_SEASON = "2026-27"
SAMPLED_MANAGER = 7254


@pytest.fixture
def pin() -> served.Pin:
    return served.pin_of(FIXTURE_ROOT / RUN_ID)


@pytest.fixture
def frames(pin: served.Pin) -> served.Frames:
    return served.load(SEASON, pin=pin, snapshot_root=FIXTURE_ROOT)


def _copy_snapshot(tmp_path: Path) -> Path:
    target = tmp_path / RUN_ID
    shutil.copytree(FIXTURE_ROOT / RUN_ID, target)
    return target


def _rewrite(path: Path, edit: object) -> None:
    table = pq.read_table(path)
    pq.write_table(edit(table), path)  # type: ignore[operator]


def _gameweek_row(frames: served.Frames, player_id: int, gw: int) -> pd.Series:
    rows = frames.gameweek[(frames.gameweek["player_id"] == player_id) & (frames.gameweek["gw"] == gw)]
    assert len(rows) == 1
    return rows.iloc[0]


# --- AC1: same pin -> identical frames; nothing but the pinned bytes is read ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC1")
def test_the_same_pin_loads_identical_frames(pin: served.Pin) -> None:
    first = served.load(SEASON, pin=pin, snapshot_root=FIXTURE_ROOT)
    second = served.load(SEASON, pin=pin, snapshot_root=FIXTURE_ROOT)
    pd.testing.assert_frame_equal(first.fixture, second.fixture)
    pd.testing.assert_frame_equal(first.gameweek, second.gameweek)
    assert first.pin == second.pin == pin


@pytest.mark.integration
@pytest.mark.covers("#29 AC1")
def test_a_snapshot_whose_bytes_differ_from_its_pin_is_refused(pin: served.Pin, tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _rewrite(snapshot / "fct_player_fixture.parquet", lambda t: t.slice(1))
    with pytest.raises(served.ServedContractError, match=r"fct_player_fixture.*sha256"):
        served.load(SEASON, pin=pin, snapshot_root=tmp_path)


@pytest.mark.unit
@pytest.mark.covers("#29 AC1")
def test_a_pin_round_trips_through_its_file(pin: served.Pin, tmp_path: Path) -> None:
    path = tmp_path / "pin.json"
    served.write_pin(pin, path)
    assert served.read_pin(path) == pin
    assert pin.run_id == RUN_ID


# --- AC2: only contract v2 is accepted ---


@pytest.mark.unit
@pytest.mark.covers("#29 AC2")
@pytest.mark.parametrize("version", [1, 3, None])
def test_a_publish_on_another_contract_version_is_refused(tmp_path: Path, version: int | None) -> None:
    snapshot = _copy_snapshot(tmp_path)
    manifest_path = snapshot / "_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if version is None:
        del manifest["contract_version"]
    else:
        manifest["contract_version"] = version
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(served.ServedContractError, match="contract"):
        served.load(SEASON, pin=served.pin_of(snapshot), snapshot_root=tmp_path)


# --- AC3: a relied-on column missing or retyped is refused, naming it ---


@pytest.mark.unit
@pytest.mark.covers("#29 AC3")
@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("fct_player_fixture", "team_fpl_id"),
        ("fct_player_gameweek", "selected"),
        ("dim_player", "position_id"),
    ],
)
def test_a_missing_relied_on_column_is_refused(tmp_path: Path, table: str, column: str) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _rewrite(snapshot / f"{table}.parquet", lambda t: t.drop_columns([column]))
    with pytest.raises(served.ServedContractError, match=rf"{table}.*{column}"):
        served.load(SEASON, pin=served.pin_of(snapshot), snapshot_root=tmp_path)


@pytest.mark.unit
@pytest.mark.covers("#30 AC7")
@pytest.mark.parametrize("column", ["total_points", "minutes", "starts"])
def test_the_gameweek_frame_carries_gameweek_outcomes_and_refuses_a_publish_without_them(
    tmp_path: Path, frames: served.Frames, column: str
) -> None:
    # 691's GW33 double: two fixtures summed by the warehouse (8 points, 180 minutes, 2 starts).
    assert {"total_points": 8, "minutes": 180, "starts": 2}[column] == _gameweek_row(frames, LATE_ENTRANT, 33)[column]
    snapshot = _copy_snapshot(tmp_path)
    _rewrite(snapshot / "fct_player_gameweek.parquet", lambda t: t.drop_columns([column]))
    with pytest.raises(served.ServedContractError, match=rf"fct_player_gameweek.*{column}"):
        served.load(SEASON, pin=served.pin_of(snapshot), snapshot_root=tmp_path)


@pytest.mark.unit
@pytest.mark.covers("#29 AC3")
@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("fct_player_fixture", "minutes"),
        ("fct_player_gameweek", "value"),
    ],
)
def test_a_retyped_relied_on_column_is_refused(tmp_path: Path, table: str, column: str) -> None:
    snapshot = _copy_snapshot(tmp_path)

    def retype(t: pa.Table) -> pa.Table:
        index = t.schema.get_field_index(column)
        return t.set_column(index, column, t[column].cast(pa.float64()))

    _rewrite(snapshot / f"{table}.parquet", retype)
    with pytest.raises(served.ServedContractError, match=rf"{table}.*{column}"):
        served.load(SEASON, pin=served.pin_of(snapshot), snapshot_root=tmp_path)


# --- AC4: season filter; an absent season is refused ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC4")
def test_only_the_requested_season_is_returned(frames: served.Frames) -> None:
    assert set(frames.fixture["season"]) == {SEASON}
    assert set(frames.gameweek["season"]) == {SEASON}


@pytest.mark.integration
@pytest.mark.covers("#29 AC4")
def test_a_season_absent_from_the_publish_is_refused(pin: served.Pin) -> None:
    with pytest.raises(served.ServedContractError, match="2024-25"):
        served.load("2024-25", pin=pin, snapshot_root=FIXTURE_ROOT)


# --- AC5: price and ownership are the last non-null values strictly before the gameweek ---


@pytest.mark.unit
@pytest.mark.covers("#29 AC5")
def test_price_and_ownership_are_the_previous_gameweeks_value_and_selected(frames: served.Frames) -> None:
    # Source rows for 149: GW32 value 45, selected 10623; GW33 value 45, selected 12561.
    row = _gameweek_row(frames, LOAN_AND_RETURN, 33)
    assert row["price"] == pytest.approx(4.5)
    assert row["ownership"] == 10623


@pytest.mark.unit
@pytest.mark.covers("#29 AC5")
def test_after_a_blank_price_and_ownership_carry_the_last_known_values(frames: served.Frames) -> None:
    # 149 blanks in GW34 (null value/selected); GW33 has value 45, selected 12561.
    row = _gameweek_row(frames, LOAN_AND_RETURN, 35)
    assert row["price"] == pytest.approx(4.5)
    assert row["ownership"] == 12561


# --- AC6: blank carries club forward ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC6")
def test_a_blank_gameweek_carries_the_club_forward(frames: served.Frames) -> None:
    row = _gameweek_row(frames, LOAN_AND_RETURN, 34)
    assert row["fixture_count"] == 0
    assert row["team_id"] == 6


# --- AC7: a mover's club follows that gameweek's fixture rows ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC7")
def test_a_loan_and_return_follows_each_gameweeks_fixture_club(frames: served.Frames) -> None:
    clubs = frames.gameweek[frames.gameweek["player_id"] == LOAN_AND_RETURN].set_index("gw")["team_id"]
    assert clubs.loc[[1, 2, 3]].tolist() == [6, 6, 6]
    assert clubs.loc[[4, 23]].tolist() == [19, 19]
    assert clubs.loc[[24, 38]].tolist() == [6, 6]
    mine = frames.fixture[frames.fixture["player_id"] == LOAN_AND_RETURN]
    for gw, fixture_clubs in mine.groupby("gw")["team_id"]:
        assert set(fixture_clubs) == {clubs.loc[gw]}


# --- AC8 lives in decisions/starting_xi/test_results.py (the run manifest) ---


# --- AC9: a double gameweek ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC9")
def test_a_double_gameweek_has_two_fixtures_in_both_frames(frames: served.Frames) -> None:
    assert _gameweek_row(frames, LOAN_AND_RETURN, 33)["fixture_count"] == 2
    fixtures = frames.fixture[(frames.fixture["player_id"] == LOAN_AND_RETURN) & (frames.fixture["gw"] == 33)]
    assert len(fixtures) == 2
    assert fixtures["fixture_id"].nunique() == 2


# --- AC10: with no earlier value (GW1, entry week), the gameweek's own value ---


@pytest.mark.unit
@pytest.mark.covers("#29 AC10")
def test_gameweek_one_uses_its_own_price_and_ownership(frames: served.Frames) -> None:
    # Source row for 149 at GW1: value 45, selected 3843.
    row = _gameweek_row(frames, LOAN_AND_RETURN, 1)
    assert row["price"] == pytest.approx(4.5)
    assert row["ownership"] == 3843


@pytest.mark.unit
@pytest.mark.covers("#29 AC10")
def test_an_entry_week_uses_its_own_price_and_ownership(frames: served.Frames) -> None:
    # 691 enters at GW2 (GW1 is a null pre-entry row); its GW2 row has value 55, selected 6667.
    row = _gameweek_row(frames, LATE_ENTRANT, 2)
    assert row["price"] == pytest.approx(5.5)
    assert row["ownership"] == 6667


# --- AC11 (proposed): no gameweek row before a player's entry ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC11")
def test_a_late_entrant_has_no_row_before_entry(frames: served.Frames) -> None:
    rows = frames.gameweek[frames.gameweek["player_id"] == LATE_ENTRANT]
    assert rows["gw"].min() == 2
    assert set(rows["entry_gw"]) == {2}


# --- #69 AC6: the manager frames are pinned like the player frames, and keep entry_id ---


@pytest.fixture
def manager_frames(pin: served.Pin) -> served.ManagerFrames:
    return served.load_managers(MANAGER_SEASON, pin=pin, snapshot_root=FIXTURE_ROOT)


@pytest.mark.integration
@pytest.mark.covers("#69 AC6")
def test_the_manager_frames_keep_entry_id_on_the_loaders_column_names(manager_frames: served.ManagerFrames) -> None:
    assert list(manager_frames.picks.columns) == [
        "season",
        "entry_id",
        "gw",
        "slot",
        "player_id",
        "is_auto_sub_in",
        "is_auto_sub_out",
        "is_captain",
    ]
    assert list(manager_frames.gameweeks.columns) == [
        "season",
        "entry_id",
        "gw",
        "active_chip",
        "cohort",
        "event_transfers",
        "overall_rank",
    ]
    assert set(manager_frames.picks["entry_id"]) == {SAMPLED_MANAGER}
    assert len(manager_frames.picks) == 7 * 15
    assert manager_frames.gameweeks.set_index("gw")["active_chip"].loc[[2, 3]].tolist() == ["bboost", "freehit"]


@pytest.mark.integration
@pytest.mark.covers("#69 AC6")
@pytest.mark.covers("#70 AC6")
@pytest.mark.parametrize("table", ["fct_manager_pick", "fct_manager_gameweek", "dim_gameweek"])
def test_a_changed_byte_in_a_manager_file_is_refused(pin: served.Pin, tmp_path: Path, table: str) -> None:
    snapshot = _copy_snapshot(tmp_path)
    path = snapshot / f"{table}.parquet"
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(data)
    with pytest.raises(served.ServedContractError, match=rf"{table}.*sha256"):
        served.load_managers(MANAGER_SEASON, pin=pin, snapshot_root=tmp_path)


@pytest.mark.integration
@pytest.mark.covers("#69 AC6")
@pytest.mark.covers("#70 AC6")
@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("fct_manager_pick", "entry_id"),
        ("fct_manager_pick", "is_auto_sub_out"),
        ("fct_manager_pick", "is_captain"),
        ("fct_manager_gameweek", "active_chip"),
        ("fct_manager_gameweek", "cohort"),
        ("fct_manager_gameweek", "event_transfers"),
        ("fct_manager_gameweek", "overall_rank"),
        ("dim_gameweek", "ranked_count"),
    ],
)
def test_a_missing_relied_on_manager_column_is_refused(tmp_path: Path, table: str, column: str) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _rewrite(snapshot / f"{table}.parquet", lambda t: t.drop_columns([column]))
    with pytest.raises(served.ServedContractError, match=rf"{table}.*{column}"):
        served.load_managers(MANAGER_SEASON, pin=served.pin_of(snapshot), snapshot_root=tmp_path)


@pytest.mark.integration
@pytest.mark.covers("#69 AC8")
def test_a_published_season_with_no_manager_rows_is_refused(pin: served.Pin) -> None:
    with pytest.raises(served.ServedContractError, match=rf"no manager rows.*{SEASON}"):
        served.load_managers(SEASON, pin=pin, snapshot_root=FIXTURE_ROOT)


# --- #70 AC6: `ranked_count` comes from a pinned `dim_gameweek`, and ranks stay integers ---


@pytest.mark.integration
@pytest.mark.covers("#70 AC6")
def test_the_pin_names_dim_gameweek_by_its_hash_and_its_s3_version() -> None:
    pin = served.read_pin()
    assert pin.run_id == "41513262675"  # the look pin (#76); the fixture sample stays at RUN_ID
    assert pin.sha256["dim_gameweek.parquet"] == "8c338c6ed7829cea9cb0145a88bda355520a224c4c2c439e7ad0b9cae66947e2"
    assert pin.object_versions["dim_gameweek.parquet"] == "2NIXs1AFM1gPnhIeR2NfuCcSJna0kTlo"


@pytest.mark.integration
@pytest.mark.covers("#70 AC6")
def test_ranked_count_is_read_for_the_requested_season_and_a_null_stays_null(
    manager_frames: served.ManagerFrames,
) -> None:
    counts = manager_frames.ranked_counts
    assert list(counts.columns) == ["season", "gw", "ranked_count"]
    assert set(counts["season"]) == {MANAGER_SEASON}
    by_gw = counts.set_index("gw")["ranked_count"]
    assert by_gw.index.tolist() == list(range(1, 9))
    assert by_gw.loc[[1, 7]].tolist() == [8903411, 11063261]
    assert by_gw.loc[8] is pd.NA


@pytest.mark.integration
@pytest.mark.covers("#70 AC3")
def test_ranks_and_ranked_counts_load_as_integers_with_a_null_rank_kept(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)

    def null_gw4_rank(table: pa.Table) -> pa.Table:
        weeks = table["gameweek"].to_pylist()
        ranks = table["overall_rank"].to_pylist()
        rank = pa.array([None if gw == 4 else r for gw, r in zip(weeks, ranks, strict=True)], pa.int32())
        return table.set_column(table.schema.get_field_index("overall_rank"), "overall_rank", rank)

    _rewrite(snapshot / "fct_manager_gameweek.parquet", null_gw4_rank)
    loaded = served.load_managers(MANAGER_SEASON, pin=served.pin_of(snapshot), snapshot_root=tmp_path)
    assert loaded.gameweeks["overall_rank"].dtype == "Int64"
    assert loaded.ranked_counts["ranked_count"].dtype == "Int64"
    assert loaded.gameweeks.set_index("gw")["overall_rank"].isna().loc[[3, 4]].tolist() == [False, True]


# --- #70 AC7: the producer's guarantee of an unbroken history, asserted on load ---

OTHER_MANAGER = 11
THIRD_MANAGER = 12


def _add_manager(snapshot: Path, entry_id: int, weeks: range | list[int], *, cohort: str = "random") -> None:
    """Copy the sampled manager's rows for `weeks` to a new `entry_id` in both manager tables."""

    def with_copy(table: pa.Table) -> pa.Table:
        sampled = (table["entry_id"].to_numpy() == SAMPLED_MANAGER) & np.isin(table["gameweek"].to_numpy(), list(weeks))
        rows = table.filter(pa.array(sampled))
        ids = pa.array([entry_id] * rows.num_rows, pa.int32())
        rows = rows.set_column(rows.schema.get_field_index("entry_id"), "entry_id", ids)
        if "cohort" in rows.schema.names:
            cohorts = pa.array([cohort] * rows.num_rows, pa.string())
            rows = rows.set_column(rows.schema.get_field_index("cohort"), "cohort", cohorts)
        return pa.concat_tables([table, rows])

    _rewrite(snapshot / "fct_manager_pick.parquet", with_copy)
    _rewrite(snapshot / "fct_manager_gameweek.parquet", with_copy)


def _load_managers(snapshot: Path) -> served.ManagerFrames:
    return served.load_managers(MANAGER_SEASON, pin=served.pin_of(snapshot), snapshot_root=snapshot.parent)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_a_manager_missing_a_middle_gameweek_is_refused_and_named(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _add_manager(snapshot, OTHER_MANAGER, [1, 2, 3, 5, 6, 7])
    with pytest.raises(served.ServedContractError, match=rf"{{{OTHER_MANAGER}: \[4\]}}"):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_a_manager_missing_the_latest_gameweek_is_refused_and_named(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _add_manager(snapshot, OTHER_MANAGER, range(1, 7))
    with pytest.raises(served.ServedContractError, match=rf"{{{OTHER_MANAGER}: \[7\]}}"):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_every_broken_manager_is_named_with_all_their_missing_gameweeks(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _add_manager(snapshot, OTHER_MANAGER, [1, 2, 5, 6, 7])
    _add_manager(snapshot, THIRD_MANAGER, [3, 4, 6])
    match = rf"{{{OTHER_MANAGER}: \[3, 4\], {THIRD_MANAGER}: \[5, 7\]}}"
    with pytest.raises(served.ServedContractError, match=match):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_a_gameweek_short_of_fifteen_picks_counts_as_missing(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _rewrite(
        snapshot / "fct_manager_pick.parquet",
        lambda t: t.filter(pa.array((t["gameweek"].to_numpy() != 2) | (t["slot"].to_numpy() != 15))),
    )
    with pytest.raises(served.ServedContractError, match=rf"{{{SAMPLED_MANAGER}: \[2\]}}"):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_a_manager_week_with_picks_and_no_gameweek_row_is_refused_and_named(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _rewrite(
        snapshot / "fct_manager_gameweek.parquet",
        lambda t: t.filter(pa.array(t["gameweek"].to_numpy() != 4)),
    )
    with pytest.raises(served.ServedContractError, match=rf"fct_manager_gameweek.*\({SAMPLED_MANAGER}, 4\)"):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_gameweek_rows_with_no_picks_are_refused_and_each_manager_week_named(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _add_manager(snapshot, OTHER_MANAGER, range(5, 8))
    _rewrite(
        snapshot / "fct_manager_pick.parquet",
        lambda t: t.filter(pa.array(t["entry_id"].to_numpy() != OTHER_MANAGER)),
    )
    weeks = rf"\[\({OTHER_MANAGER}, 5\), \({OTHER_MANAGER}, 6\), \({OTHER_MANAGER}, 7\)\]"
    with pytest.raises(served.ServedContractError, match=rf"fct_manager_pick.*{weeks}"):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_a_self_cohort_manager_is_checked_like_any_other(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _add_manager(snapshot, OTHER_MANAGER, range(1, 7), cohort="self")
    with pytest.raises(served.ServedContractError, match=rf"{{{OTHER_MANAGER}: \[7\]}}"):
        _load_managers(snapshot)


@pytest.mark.unit
@pytest.mark.covers("#70 AC7")
def test_a_complete_panel_with_a_late_joiner_loads(tmp_path: Path) -> None:
    snapshot = _copy_snapshot(tmp_path)
    _add_manager(snapshot, OTHER_MANAGER, range(3, 8))
    assert set(_load_managers(snapshot).gameweeks["entry_id"]) == {SAMPLED_MANAGER, OTHER_MANAGER}


# --- #70 AC9 (proposed): `refresh` records the S3 version of every file it fetches ---

SOURCE = "s3://capture-bucket/served/"


def _fake_get_object(version: str | None, commands: list[list[str]] | None = None) -> Callable[..., object]:
    """`aws s3api get-object`, serving the fixture's files and replying as the CLI does."""

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        name = Path(command[command.index("--key") + 1]).name
        shutil.copy(FIXTURE_ROOT / RUN_ID / name, command[-1])
        if commands is not None:
            commands.append(command)
        reply = {"VersionId": f"{version}-{name}"} if version else {}
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(reply), stderr="")

    return run


@pytest.mark.unit
@pytest.mark.covers("#70 AC9 (proposed)")
def test_refresh_writes_the_s3_version_of_every_file_it_fetched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(served.subprocess, "run", _fake_get_object("v1", commands))
    pin_path = tmp_path / "pin.json"
    served.refresh(source=SOURCE, snapshot_root=tmp_path / "snapshots", pin_path=pin_path)
    written = served.read_pin(pin_path)
    assert written.run_id == RUN_ID
    assert written.object_versions == {name: f"v1-{name}" for name in served.FILES}
    assert written.sha256 == served.pin_of(FIXTURE_ROOT / RUN_ID).sha256
    assert commands[0][:7] == [
        "aws",
        "s3api",
        "get-object",
        "--bucket",
        "capture-bucket",
        "--key",
        "served/_manifest.json",
    ]


@pytest.mark.unit
@pytest.mark.covers("#70 AC9 (proposed)")
def test_refreshing_a_run_already_held_still_writes_its_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin_path = tmp_path / "pin.json"
    monkeypatch.setattr(served.subprocess, "run", _fake_get_object("v1"))
    served.refresh(source=SOURCE, snapshot_root=tmp_path / "snapshots", pin_path=pin_path)
    monkeypatch.setattr(served.subprocess, "run", _fake_get_object("v2"))
    served.refresh(source=SOURCE, snapshot_root=tmp_path / "snapshots", pin_path=pin_path)
    assert served.read_pin(pin_path).object_versions == {name: f"v2-{name}" for name in served.FILES}


@pytest.mark.unit
@pytest.mark.covers("#70 AC9 (proposed)")
def test_a_fetch_with_no_version_id_raises_and_leaves_the_pin_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pin_path = tmp_path / "pin.json"
    served.write_pin(served.Pin(run_id="1", sha256={"a": "b"}, object_versions={"a": "v0"}), pin_path)
    before = pin_path.read_text()
    monkeypatch.setattr(served.subprocess, "run", _fake_get_object(None))
    with pytest.raises(served.ServedContractError, match=r"_manifest\.json.*no S3 version"):
        served.refresh(source=SOURCE, snapshot_root=tmp_path / "snapshots", pin_path=pin_path)
    assert pin_path.read_text() == before


@pytest.mark.unit
@pytest.mark.covers("#70 AC9 (proposed)")
def test_a_held_snapshot_that_differs_raises_and_names_the_pinned_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "snapshots"
    root.mkdir()
    snapshot = _copy_snapshot(root)
    (snapshot / "dim_gameweek.parquet").write_bytes(b"not the publish")
    pin_path = tmp_path / "pin.json"
    served.write_pin(served.Pin(run_id=RUN_ID, sha256={"a": "b"}, object_versions={"a": "v0"}), pin_path)
    monkeypatch.setattr(served.subprocess, "run", _fake_get_object("v1"))
    with pytest.raises(served.ServedContractError, match=r"differs.*'a': 'v0'"):
        served.refresh(source=SOURCE, snapshot_root=root, pin_path=pin_path)


# --- #73 AC10: the pin carries the warehouse build's time and git sha, and the loader requires both ---

FIXTURE_BUILT_AT = "2026-10-26T08:05:01+00:00"
FIXTURE_GIT_SHA = "86536e536caa07f089df3dda7f1e94fb5c776ed7"


@pytest.mark.unit
@pytest.mark.covers("#73 AC10")
def test_a_pin_taken_from_a_snapshot_carries_its_manifests_build_time_and_git_sha(pin: served.Pin) -> None:
    assert (pin.built_at, pin.git_sha) == (FIXTURE_BUILT_AT, FIXTURE_GIT_SHA)


@pytest.mark.unit
@pytest.mark.covers("#73 AC10")
def test_a_pins_build_time_and_git_sha_round_trip_through_its_file(pin: served.Pin, tmp_path: Path) -> None:
    path = tmp_path / "pin.json"
    served.write_pin(pin, path)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert (document["built_at"], document["git_sha"]) == (FIXTURE_BUILT_AT, FIXTURE_GIT_SHA)
    assert served.read_pin(path) == pin


@pytest.mark.unit
@pytest.mark.covers("#73 AC10")
def test_a_pin_file_without_the_build_fields_still_reads_and_loads(pin: served.Pin, tmp_path: Path) -> None:
    # The requirement lives on the Stage 5 runner's load path only (D-N12): today's pin lacks both.
    path = tmp_path / "pin.json"
    served.write_pin(pin, path)
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["built_at"], document["git_sha"]
    path.write_text(json.dumps(document), encoding="utf-8")
    read = served.read_pin(path)
    assert (read.built_at, read.git_sha) == (None, None)
    assert not served.load(MANAGER_SEASON, pin=read, snapshot_root=FIXTURE_ROOT).gameweek.empty
