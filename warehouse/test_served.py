"""Acceptance tests for the served-publish loader (#29).

The fixture under `fixtures/39064033745/` is a real sample of fpl-warehouse publish run
39064033745: its `_manifest.json` verbatim, and the `fct_player_fixture`, `fct_player_gameweek`
and `dim_player` rows of two players, both seasons, written with the publish's own arrow schema.

- `fpl_id` 149 (2025-26): starts at club 6, loans to club 19 from GW4, returns to club 6 from GW24;
  blank in GW34; double in GW33.
- `fpl_id` 691 (2025-26): enters at GW2; GW1 is a pre-entry row (`fixture_count` 0, nulls).
- Both ids also carry 2026-27 rows, so a season filter that leaks shows up.
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

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
RUN_ID = "39064033745"
SEASON = "2025-26"
LOAN_AND_RETURN = 149
LATE_ENTRANT = 691


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


# --- AC5: lag-1 price and ownership ---


@pytest.mark.unit
@pytest.mark.covers("#29 AC5")
def test_price_and_ownership_are_the_previous_gameweeks_value_and_selected(frames: served.Frames) -> None:
    # Source rows for 149: GW32 value 45, selected 10623; GW33 value 45, selected 12561.
    row = _gameweek_row(frames, LOAN_AND_RETURN, 33)
    assert row["price"] == pytest.approx(4.5)
    assert row["ownership"] == 10623


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


# --- AC10: GW1 has no lag-1 ---


@pytest.mark.unit
@pytest.mark.covers("#29 AC10")
def test_gameweek_one_price_and_ownership_are_null(frames: served.Frames) -> None:
    row = _gameweek_row(frames, LOAN_AND_RETURN, 1)
    assert pd.isna(row["price"])
    assert pd.isna(row["ownership"])


# --- AC11 (proposed): no gameweek row before a player's entry ---


@pytest.mark.integration
@pytest.mark.covers("#29 AC11")
def test_a_late_entrant_has_no_row_before_entry(frames: served.Frames) -> None:
    rows = frames.gameweek[frames.gameweek["player_id"] == LATE_ENTRANT]
    assert rows["gw"].min() == 2
    assert set(rows["entry_gw"]) == {2}
