"""Acceptance tests for the served-publish loader (#29).

The fixture under `warehouse/fixtures/40289379567/` is a real sample of fpl-warehouse publish run
40289379567: its `_manifest.json` verbatim, the `fct_player_fixture`, `fct_player_gameweek` and
`dim_player` rows of two players, both seasons, and the `fct_manager_pick` and
`fct_manager_gameweek` rows of one manager, written with the publish's own arrow schema.

- `fpl_id` 149 (2025-26): starts at club 6, loans to club 19 from GW4, returns to club 6 from GW24;
  blank in GW34; double in GW33.
- `fpl_id` 691 (2025-26): enters at GW2; GW1 is a pre-entry row (`fixture_count` 0, nulls).
- `fpl_id` 149 also carries 2026-27 rows (GW1-7), so a season filter that leaks shows up. Their
  `fixture_count_at_deadline` is NULL at GW1-2 (no capture before those deadlines) and 1 from GW3;
  every 2025-26 row's is NULL.
- `entry_id` 7254 (2026-27, GW1-7): Bench Boost in GW2, Free Hit in GW3, auto-subs in GW5 and GW6.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

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
    ]
    assert list(manager_frames.gameweeks.columns) == ["season", "entry_id", "gw", "active_chip"]
    assert set(manager_frames.picks["entry_id"]) == {SAMPLED_MANAGER}
    assert len(manager_frames.picks) == 7 * 15
    assert manager_frames.gameweeks.set_index("gw")["active_chip"].loc[[2, 3]].tolist() == ["bboost", "freehit"]


@pytest.mark.integration
@pytest.mark.covers("#69 AC6")
@pytest.mark.parametrize("table", ["fct_manager_pick", "fct_manager_gameweek"])
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
@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("fct_manager_pick", "entry_id"),
        ("fct_manager_pick", "is_auto_sub_out"),
        ("fct_manager_gameweek", "active_chip"),
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
