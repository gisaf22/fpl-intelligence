"""The served-publish loader's interface (#29). Bodies land with the implementation commit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class ServedContractError(Exception):
    """A pinned snapshot that does not match its pin, its contract, or the requested season."""


@dataclass(frozen=True)
class Pin:
    """One fpl-warehouse publish: its manifest `run_id` and the sha256 of each file read."""

    run_id: str
    sha256: Mapping[str, str]


@dataclass(frozen=True)
class Frames:
    """The two frames a consumer reads: fixture grain and gameweek grain, with their pin."""

    fixture: pd.DataFrame
    gameweek: pd.DataFrame
    pin: Pin


def pin_of(snapshot_dir: Path) -> Pin:
    raise NotImplementedError


def read_pin(path: Path) -> Pin:
    raise NotImplementedError


def write_pin(pin: Pin, path: Path) -> None:
    raise NotImplementedError


def load(season: str, *, pin: Pin, snapshot_root: Path) -> Frames:
    raise NotImplementedError
