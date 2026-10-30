"""Load fpl-warehouse's served publish from a pinned local snapshot (#29).

A snapshot is one publish, copied whole into `<snapshot_root>/<run_id>/`. The pin names that
publish's manifest `run_id` and the sha256 of each file read. The hashes are computed at sync,
because the served manifest publishes none (gisaf22/fpl-warehouse#214). Every `load` checks the
bytes against the pin, the contract version and every relied-on column's type before returning
anything, so a run reads exactly one publish, never "whatever was downloaded last".

The mapping from warehouse columns to the frames below is `decisions/starting_xi/DATA.md`. This
module fetches, verifies, filters, renames and lags; it computes no rule or feature.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = REPO_ROOT / "data" / "warehouse"
PIN_PATH = Path(__file__).resolve().parent / "pin.json"
SOURCE = "s3://fpl-data-safari/served/"
MANIFEST = "_manifest.json"
CONTRACT_VERSION = 2

# The columns this loader relies on, with the arrow type the publish writes them as. A column
# missing or retyped in a publish is refused rather than coerced.
RELIED_ON: Mapping[str, Mapping[str, str]] = {
    "fct_player_fixture": {
        "season": "string",
        "fpl_id": "int32",
        "gameweek": "int32",
        "fixture_id": "int32",
        "team_fpl_id": "int32",
        "minutes": "int32",
        "starts": "int32",
        "total_points": "int32",
    },
    "fct_player_gameweek": {
        "season": "string",
        "fpl_id": "int32",
        "gameweek": "int32",
        "fixture_count": "int32",
        "total_points": "int32",
        "minutes": "int32",
        "starts": "int32",
        "value": "int32",
        "selected": "int32",
        "fixture_count_at_deadline": "int32",
    },
    "dim_player": {
        "season": "string",
        "fpl_id": "int32",
        "position_id": "int32",
    },
    "fct_manager_pick": {
        "season": "string",
        "entry_id": "int32",
        "gameweek": "int32",
        "slot": "int32",
        "fpl_id": "int32",
        "is_auto_sub_in": "bool",
        "is_auto_sub_out": "bool",
    },
    "fct_manager_gameweek": {
        "season": "string",
        "entry_id": "int32",
        "gameweek": "int32",
        "active_chip": "string",
    },
}
FILES = (MANIFEST, *(f"{table}.parquet" for table in RELIED_ON))


class ServedContractError(Exception):
    """A pinned snapshot that does not match its pin, its contract, or the requested season."""


@dataclass(frozen=True)
class Pin:
    """One fpl-warehouse publish: its manifest `run_id` and the sha256 of each file read."""

    run_id: str
    sha256: Mapping[str, str]


@dataclass(frozen=True)
class Frames:
    """The two frames a consumer reads, with the pin they came from.

    `fixture`: one row per (player_id, fixture_id) — season, player_id, gw, fixture_id, team_id,
    minutes, starts, total_points.
    `gameweek`: one row per (player_id, gw) from the player's entry gameweek on — season,
    player_id, gw, fixture_count, total_points, minutes, starts (the gameweek's sums, null on a
    blank), team_id, position_id, price, ownership, entry_gw, deadline_fixture_count,
    deadline_count_is_realised.

    `fixture_count` is the realised count (fixtures played); `deadline_fixture_count` is the count
    scheduled at the gameweek's deadline. A gameweek with no at-deadline count for any player had
    no capture before its deadline, so it carries the realised count and `deadline_count_is_realised`
    (today: 2026-27 GW1-2 and all of 2025-26). Elsewhere a NULL stays NULL: a player not
    registered at the deadline, or a defect the harness refuses for a squad player (#59 D6).
    """

    fixture: pd.DataFrame
    gameweek: pd.DataFrame
    pin: Pin


@dataclass(frozen=True)
class ManagerFrames:
    """The panel's two frames for one season, with the pin they came from.

    `picks`: one row per (entry_id, gw, slot) -- season, entry_id, gw, slot, player_id,
    is_auto_sub_in, is_auto_sub_out. `slot` is the lineup after FPL's automatic substitutions.
    `gameweeks`: one row per (entry_id, gw) -- season, entry_id, gw, active_chip (null: no chip).
    """

    picks: pd.DataFrame
    gameweeks: pd.DataFrame
    pin: Pin


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pin_of(snapshot_dir: Path) -> Pin:
    """The pin a snapshot directory would be read under: its manifest's run_id and file hashes."""
    manifest = json.loads((snapshot_dir / MANIFEST).read_text(encoding="utf-8"))
    return Pin(run_id=str(manifest["run_id"]), sha256={name: sha256_of(snapshot_dir / name) for name in FILES})


def read_pin(path: Path = PIN_PATH) -> Pin:
    document = json.loads(path.read_text(encoding="utf-8"))
    return Pin(run_id=document["run_id"], sha256=dict(document["sha256"]))


def write_pin(pin: Pin, path: Path = PIN_PATH) -> None:
    document = {"run_id": pin.run_id, "sha256": dict(sorted(pin.sha256.items()))}
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def refresh(*, source: str = SOURCE, snapshot_root: Path = SNAPSHOT_ROOT, pin_path: Path = PIN_PATH) -> Pin:
    """Sync the current publish into `<snapshot_root>/<run_id>/` and record it as the new pin.

    Reads with the aws CLI under whatever credentials the environment carries. An existing
    snapshot of the same run_id is kept, not overwritten, and must match what was just fetched.
    """
    with tempfile.TemporaryDirectory(dir=snapshot_root.parent if snapshot_root.parent.exists() else None) as tmp:
        staging = Path(tmp)
        for name in FILES:
            subprocess.run(["aws", "s3", "cp", f"{source}{name}", str(staging / name)], check=True)
        pin = pin_of(staging)
        target = snapshot_root / pin.run_id
        if target.exists():
            if pin_of(target) != pin:
                raise ServedContractError(f"snapshot {target} exists but differs from publish {pin.run_id} at {source}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging, target)
    write_pin(pin, pin_path)
    return pin


def _verify(snapshot_dir: Path, pin: Pin) -> dict[str, object]:
    for name in FILES:
        expected = pin.sha256.get(name)
        actual = sha256_of(snapshot_dir / name) if (snapshot_dir / name).exists() else None
        if expected is None or actual != expected:
            raise ServedContractError(
                f"run_id {pin.run_id}: {name} sha256 {actual} does not match pin {expected} ({snapshot_dir})"
            )
    manifest: dict[str, object] = json.loads((snapshot_dir / MANIFEST).read_text(encoding="utf-8"))
    if str(manifest.get("run_id")) != pin.run_id:
        raise ServedContractError(f"manifest run_id {manifest.get('run_id')} does not match pin {pin.run_id}")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise ServedContractError(
            f"run_id {pin.run_id}: contract_version {manifest.get('contract_version')!r}, "
            f"this loader reads only contract v{CONTRACT_VERSION}"
        )
    for table, columns in RELIED_ON.items():
        schema = pq.read_schema(snapshot_dir / f"{table}.parquet")
        for column, expected_type in columns.items():
            if column not in schema.names:
                raise ServedContractError(f"run_id {pin.run_id}: {table} is missing relied-on column {column}")
            actual_type = str(schema.field(column).type)
            if actual_type != expected_type:
                raise ServedContractError(
                    f"run_id {pin.run_id}: {table}.{column} is {actual_type}, expected {expected_type}"
                )
    return manifest


def _read(snapshot_dir: Path, table: str, season: str) -> pd.DataFrame:
    frame = pq.read_table(
        snapshot_dir / f"{table}.parquet", columns=list(RELIED_ON[table]), filters=[("season", "=", season)]
    ).to_pandas()
    return frame.rename(columns={"fpl_id": "player_id", "gameweek": "gw", "team_fpl_id": "team_id"})


def _verified_snapshot(season: str, pin: Pin, snapshot_root: Path) -> Path:
    snapshot_dir = snapshot_root / pin.run_id
    manifest = _verify(snapshot_dir, pin)
    seasons = manifest.get("seasons")
    if not isinstance(seasons, list) or season not in seasons:
        raise ServedContractError(f"run_id {pin.run_id}: season {season} not in publish seasons {seasons}")
    return snapshot_dir


def load(season: str, *, pin: Pin | None = None, snapshot_root: Path = SNAPSHOT_ROOT) -> Frames:
    """The pinned publish's two frames for one season.

    Raises:
        ServedContractError: the snapshot's bytes differ from the pin, the contract version is
            not v2, a relied-on column is missing or retyped, or the season is not in the publish.
    """
    pin = read_pin() if pin is None else pin
    snapshot_dir = _verified_snapshot(season, pin, snapshot_root)

    fixture = _read(snapshot_dir, "fct_player_fixture", season)
    fixture = fixture[["season", "player_id", "gw", "fixture_id", "team_id", "minutes", "starts", "total_points"]]
    fixture = fixture.sort_values(["player_id", "gw", "fixture_id"], ignore_index=True)

    gameweek = _read(snapshot_dir, "fct_player_gameweek", season).sort_values(["player_id", "gw"], ignore_index=True)
    # Decided over the whole season's rows, before entry trims them: a gameweek is uncaptured when
    # no player has a count as at its deadline.
    captured = gameweek.groupby("gw")["fixture_count_at_deadline"].transform(lambda counts: counts.notna().any())
    gameweek["deadline_count_is_realised"] = ~captured.astype(bool)
    gameweek["deadline_fixture_count"] = gameweek["fixture_count_at_deadline"].where(
        captured.astype(bool), gameweek["fixture_count"]
    )
    # Entry is the first gameweek with a fixture: before it the publish holds pre-entry rows that
    # look like blanks (fixture_count 0, nulls), so they are dropped rather than carried.
    entry = fixture.groupby("player_id")["gw"].min().rename("entry_gw")
    gameweek = gameweek.join(entry, on="player_id", how="inner")
    gameweek = gameweek[gameweek["gw"] >= gameweek["entry_gw"]].reset_index(drop=True)

    by_player = gameweek.groupby("player_id")
    # Most recent non-null value strictly before gw (shift, then carry forward within the player).
    # With none -- the entry week, or GW1 -- the gameweek's own value: the listing price and
    # ownership are set before the deadline, so they leak no outcome.
    for source, target in (("value", "price"), ("selected", "ownership")):
        prior = by_player[source].shift(1).groupby(gameweek["player_id"]).ffill()
        gameweek[target] = prior.fillna(gameweek[source])
    gameweek["price"] = gameweek["price"] / 10

    clubs = fixture.groupby(["player_id", "gw"])["team_id"].first().rename("team_id")
    gameweek = gameweek.join(clubs, on=["player_id", "gw"])
    gameweek["team_id"] = gameweek.groupby("player_id")["team_id"].ffill()

    positions = _read(snapshot_dir, "dim_player", season).set_index("player_id")["position_id"]
    gameweek = gameweek.join(positions, on="player_id")

    gameweek = gameweek[
        [
            "season",
            "player_id",
            "gw",
            "fixture_count",
            "total_points",
            "minutes",
            "starts",
            "team_id",
            "position_id",
            "price",
            "ownership",
            "entry_gw",
            "deadline_fixture_count",
            "deadline_count_is_realised",
        ]
    ]
    return Frames(fixture=fixture, gameweek=gameweek, pin=pin)


def load_managers(season: str, *, pin: Pin | None = None, snapshot_root: Path = SNAPSHOT_ROOT) -> ManagerFrames:
    """The pinned publish's manager frames for one season, under `load`'s checks.

    Raises:
        ServedContractError: as `load`, or the season is published with no manager rows.
    """
    pin = read_pin() if pin is None else pin
    snapshot_dir = _verified_snapshot(season, pin, snapshot_root)
    picks = _read(snapshot_dir, "fct_manager_pick", season)
    if picks.empty:
        raise ServedContractError(f"run_id {pin.run_id}: no manager rows for season {season}")
    gameweeks = _read(snapshot_dir, "fct_manager_gameweek", season)
    return ManagerFrames(
        picks=picks.sort_values(["entry_id", "gw", "slot"], ignore_index=True),
        gameweeks=gameweeks.sort_values(["entry_id", "gw"], ignore_index=True),
        pin=pin,
    )
