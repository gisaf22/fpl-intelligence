"""Stage 5's realism check (#66): does each gameweek count's row of the power lab's table apply?

#55 decision B as amended by the revised D-C3, D-C4, D-C5 and R1-R3: a labelling check run after the
freeze, never used to change a lab setting. It measures the real gameweek shock directly -- the spread
across gameweeks of the weekly win share, in win-share points, the same quantity as the lab's shock
(`power_lab.SHOCK_SD_POINTS`) -- so no conversion is applied.

**The measure.** The input is the verdict's feed table (`verdict.COLUMNS`, one row per scored panel
manager-week). Each gameweek's share is the mean of `outcome` over its panel managers, ties counting
0.5 as the verdict counts them; the spread is the sample standard deviation of those shares across
the requested gameweeks. `Measurement` holds the spread and the counts and never the mean: D2's
outcomes serve only the spread.

**The label (D-C4).** Each count in `power_lab.GAMEWEEK_SWEEP` is compared with its own level from
the lab's committed probe (#65): the largest shock at which it stays within the false-rejection
limit. A spread strictly beyond a count's level marks that row alone "not applicable"; a count with
no level (the verdict procedure is invalid there) is not compared. The rough uncertainty and the
sampling noise are printed beside the estimate and gate nothing.

**The record (D-C5, R2).** This module writes `power_lab_results/REALISM.md` itself, from the lab's
committed levels and the feed spread; `power_report` and the other lab modules receive nothing from
it, and `REPORT.md` is never written here. The bytes are deterministic: no timestamp, rows in
gameweek order and fixed number formats (#66 AC11). A run on any gameweeks other than the verdict's
is a labelled preview.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from decisions.starting_xi import power_lab, power_report
from decisions.starting_xi.power_report import ShockLevel
from decisions.starting_xi.verdict import COLUMNS, OUTCOMES

# The pre-registered check (PRE_REGISTRATION.yaml `realism_check`).
STATISTIC: Final[str] = "spread_across_gameweeks_of_weekly_win_share"
SPREAD_DDOF: Final[int] = 1  # the sample standard deviation across gameweeks
UNIT: Final[str] = "win_share_points"
VERDICT_GAMEWEEKS: Final[tuple[int, ...]] = tuple(range(4, 16))  # GW4-GW15 (#55 D-N3)
PRINTS_MEAN: Final[bool] = False  # no return field, line or file carries the weekly shares' mean
LABEL: Final[str] = "per_gameweek_count"  # each swept count against its own level (D-C4)
FILENAME: Final[str] = "REALISM.md"

_NULL_VARIANCE: Final[float] = 0.25  # a weekly share's per-manager variance at 50%


class RealismRefused(ValueError):
    """The check cannot be measured or stated as asked; nothing is written."""


@dataclass(frozen=True)
class Measurement:
    gameweeks: tuple[int, ...]
    spread_points: float
    panel_managers: int  # distinct panel managers over the gameweeks
    managers_per_gameweek: tuple[int, ...]  # n_g, in `gameweeks` order


@dataclass(frozen=True)
class RowCheck:
    gameweeks: int
    level: int | None
    note: str | None
    applies: bool | None  # None: no level, so not compared


def measure(feed: pd.DataFrame, *, gameweeks: Iterable[int]) -> Measurement:
    """The spread across `gameweeks` of the weekly win share in `feed`; rows outside them are unread."""
    wanted = tuple(sorted(set(int(g) for g in gameweeks)))
    if len(wanted) < 2:
        raise RealismRefused(f"a spread needs at least two gameweeks; got {list(wanted)}")
    extra = sorted(set(feed.columns) - set(COLUMNS))
    missing = [c for c in COLUMNS if c not in feed.columns]
    if extra or missing:
        raise RealismRefused(f"feed must hold exactly {list(COLUMNS)}; extra {extra}, missing {missing}")
    rows = feed.loc[feed["gameweek"].isin(wanted)]
    absent = [g for g in wanted if g not in set(rows["gameweek"])]
    if absent:
        raise RealismRefused(f"no rows for {', '.join(f'GW{g}' for g in absent)}")
    bad = ~rows["outcome"].isin(OUTCOMES)
    if bad.any():
        raise RealismRefused(f"outcome must be 1, 0.5 or 0; got {sorted(set(rows.loc[bad, 'outcome']))[:5]}")
    by_gameweek = rows.groupby("gameweek")
    # In halves, so a share is exact and two feeds whose shares differ by a constant give one spread.
    halves = (rows["outcome"] * 2).round().astype(int).groupby(rows["gameweek"]).sum()
    counts = by_gameweek["manager_id"].nunique()
    shares = 50 * halves.loc[list(wanted)] / counts.loc[list(wanted)]
    return Measurement(
        gameweeks=wanted,
        spread_points=float(shares.std(ddof=SPREAD_DDOF)),
        panel_managers=int(rows["manager_id"].nunique()),
        managers_per_gameweek=tuple(int(counts.loc[g]) for g in wanted),
    )


def relative_uncertainty(gameweeks: int) -> float:
    """The rough relative error of a standard deviation over `gameweeks` roughly normal values."""
    return 1 / math.sqrt(2 * (gameweeks - 1))


def sampling_noise_points(managers_per_gameweek: Sequence[int]) -> float:
    """100 x sqrt(mean over the gameweeks of 0.25 / n_g): a weekly share's noise at 50%, in points."""
    return 100 * math.sqrt(sum(_NULL_VARIANCE / n for n in managers_per_gameweek) / len(managers_per_gameweek))


def committed_levels(cells_dir: Path) -> list[ShockLevel]:
    """Each count's level, from the lab's committed cells through the lab's own probe reading."""
    saved = {path.stem: power_lab.load_cell(path) for path in sorted(cells_dir.glob("*.json"))}
    results = power_lab.assemble_results(saved, fake_studies=power_lab.FAKE_STUDIES)
    return power_report.probe_report(results).shock_levels


def label_rows(spread_points: float, levels: Iterable[ShockLevel]) -> list[RowCheck]:
    """Each swept count against its own level; refused unless every swept count has exactly one."""
    by_count: dict[int, ShockLevel] = {}
    for level in levels:
        if level.gameweeks in by_count:
            raise RealismRefused(f"two levels for {level.gameweeks} gameweeks")
        by_count[level.gameweeks] = level
    missing = [g for g in power_lab.GAMEWEEK_SWEEP if g not in by_count]
    extra = sorted(set(by_count) - set(power_lab.GAMEWEEK_SWEEP))
    if missing or extra:
        raise RealismRefused(f"levels must cover the swept counts; missing {missing}, extra {extra}")
    rows = []
    for g in sorted(by_count):
        points = by_count[g].level
        applies = None if points is None else spread_points <= points
        rows.append(RowCheck(gameweeks=g, level=points, note=by_count[g].note, applies=applies))
    return rows


def _points(value: float) -> str:
    return f"{value:.2f}"


def _named(gameweeks: Sequence[int]) -> str:
    return ", ".join(f"GW{g}" for g in gameweeks)


def _scope_line(measurement: Measurement) -> str:
    counted = f"({len(measurement.gameweeks)} gameweeks)"
    if measurement.gameweeks == VERDICT_GAMEWEEKS:
        return f"Record: measured on the verdict's gameweeks, {_named(measurement.gameweeks)} {counted}."
    return (
        f"Preview, not the record: measured on {_named(measurement.gameweeks)} {counted}; the record is "
        f"the run on the verdict's gameweeks, GW{VERDICT_GAMEWEEKS[0]} to GW{VERDICT_GAMEWEEKS[-1]}."
    )


def _managers(counts: Sequence[int]) -> str:
    low, high = min(counts), max(counts)
    if low == high:
        return f"n_g = {low:,} panel managers in every gameweek"
    return f"n_g from {low:,} to {high:,} panel managers a gameweek"


def _level_cell(row: RowCheck) -> str:
    if row.level is None:
        return "no level (verdict procedure invalid at this count)"
    return f"{row.level} points" + (f", {row.note}" if row.note else "")


def _verdict_cell(row: RowCheck, spread: str) -> str:
    if row.applies is None:
        return "not compared"
    if row.applies:
        return f"applies: the spread of {spread} points is within the level of {row.level} points"
    return f"not applicable: the spread of {spread} points is beyond the level of {row.level} points"


def render(measurement: Measurement, levels: Iterable[ShockLevel]) -> str:
    """`REALISM.md`'s text: the scope, the statistic, the compared values and one row per swept count."""
    rows = label_rows(measurement.spread_points, levels)
    n = len(measurement.gameweeks)
    relative = relative_uncertainty(n)
    spread = _points(measurement.spread_points)
    noise = sampling_noise_points(measurement.managers_per_gameweek)
    lines = [
        "# Stage 5 realism check",
        "",
        _scope_line(measurement),
        "",
        "A labelling check, not a calibration: run after the freeze, it changes no lab setting. Each "
        "gameweek count's row of the lab's table (`REPORT.md`) is compared with that count's own level, "
        "the largest gameweek shock at which it stays within the false-rejection limit (#65).",
        "",
        "- Statistic: the spread across gameweeks of the weekly win share -- the sample standard "
        "deviation across gameweeks of each gameweek's mean outcome over its panel managers (win 1, "
        "tie 0.5, loss 0) -- in win-share points, the same quantity as the lab's shock, so no conversion "
        "is applied.",
        f"- Real spread: {spread} win-share points over {n} gameweeks and {measurement.panel_managers:,} "
        "panel managers.",
        f"- Rough uncertainty: about {_points(measurement.spread_points * relative)} points (relative "
        f"error {relative:.0%}, 1/sqrt(2(n-1)) at n = {n} gameweeks, assuming roughly normal weekly "
        "values); printed only, it gates no label.",
        f"- Noise: the sampling noise of a weekly share at 50% is about {_points(noise)} points (100 x sqrt(mean over "
        f"the gameweeks of 0.25 / n_g), {_managers(measurement.managers_per_gameweek)}); not subtracted "
        "from the spread, so the check is conservative; printed only, it gates no label.",
        "",
        "## Does the lab's row apply, per gameweek count",
        "",
        "| Gameweeks | Level: largest tolerable shock | Real spread | Lab's row |",
        "|---|---|---|---|",
        *(f"| {r.gameweeks} | {_level_cell(r)} | {spread} points | {_verdict_cell(r, spread)} |" for r in rows),
    ]
    return "\n".join(lines) + "\n"


def write(results_dir: Path, measurement: Measurement, levels: Iterable[ShockLevel]) -> Path:
    """Write `REALISM.md` into `results_dir` (the lab's results, beside `REPORT.md`) and return its path."""
    path = results_dir / FILENAME
    path.write_bytes(render(measurement, levels).encode("utf-8"))
    return path
