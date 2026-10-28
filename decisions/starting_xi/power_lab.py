"""Stage 5's power simulation lab (#60): the real verdict, run on fake data across a frozen grid.

Each **cell** is one setting (shock size, manager effect, tie rate, gameweeks, managers) at one true
win share. A cell runs `FAKE_STUDIES` fake studies; each generates a manager-week table and calls
`primary_verdict` -- the function the real Stage 5 run calls (#60 L), not a copy. The lab never
applies P6's 100,000-repeat re-run; it counts the studies that would have triggered one.

**The fake data (assumptions, not measurements; #55 P8, P9).** A manager-week ties with probability
`tie_rate`; otherwise the rule wins with probability `logistic(a + shock[gw] + effect[manager])`,
with both effects normal. A size label is the standard deviation, in win-share points, of a
gameweek's true share (shock) or a manager's true share (manager effect): `SHOCK_SD_POINTS`,
`MANAGER_EFFECT_SD_POINTS`. Converted to the logit scale by the delta method at 50% for each tie
rate; the intercept `a` is then solved so the expected share equals the target exactly. Managers are
generated, not subsampled from the real panel (#60 decision 5): every manager plays every gameweek,
and bands are equal thirds fixed per manager.

**What the lab reads: nothing.** It takes settings and counts only; `check_lab_inputs` refuses any
frame carrying more than the panel's structure, and `.importlinter` forbids this module `dal`,
`warehouse`, `model` and the slice's data-reading siblings, so D2's scores against managers cannot
reach it (#60 AC7).

**Runtime (#60, runtime constraint).** Cells run in parallel (`workers`), in three tiers approved one
at a time; every finished cell is saved atomically, so a stop and resume gives the same answer
(the seed is fixed per cell by its name, not its position). The pilot times each distinct
(managers, gameweeks) size under the same parallelism, and its verdicts are discarded.

The command line (pilot, run a tier, report) is `operational.starting_xi_power_lab`.
"""

from __future__ import annotations

import json
import os
import time
import zlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass, field, replace
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

from decisions.starting_xi.verdict import N_RESAMPLES, RERUN_RESAMPLES, RERUN_SEED, SEED, Verdict, primary_verdict

# --- The frozen design (PRE_REGISTRATION.yaml `power_lab`) ----------------------------------------

TRUE_WIN_SHARES: Final[tuple[float, ...]] = (0.51, 0.52, 0.53, 0.55, 0.58, 0.60)
NULL_SHARE: Final[float] = 0.5
TIE_RATES: Final[tuple[float, ...]] = (0.2, 0.4, 0.6)
EFFECT_LEVELS: Final[tuple[str, ...]] = ("small", "medium", "large")
SHOCK_SD_POINTS: Final[Mapping[str, int]] = {"small": 2, "medium": 4, "large": 6}
MANAGER_EFFECT_SD_POINTS: Final[Mapping[str, int]] = {"small": 5, "medium": 10, "large": 15}
GAMEWEEK_SWEEP: Final[tuple[int, ...]] = (5, 8, 12, 16, 24, 38)
MANAGER_SWEEP: Final[tuple[int, ...]] = (500, 1_000, 2_000)
FAKE_STUDIES: Final[int] = 1_000
INNER_RESAMPLES: Final[int] = N_RESAMPLES
MASTER_SEED: Final[int] = 60
SENSITIVITY_SHARE: Final[float] = 0.65
FIRST_GAMEWEEK: Final[int] = 4  # labels only: the Stage 5 window starts at GW4 (#55 decision 15)


@dataclass(frozen=True)
class Setting:
    name: str
    shock: str
    manager_effect: str
    tie_rate: float
    gameweeks: int
    managers: int


BASELINE: Final[Setting] = Setting("baseline", "medium", "medium", 0.4, 5, 2_000)
WORST_CASE_CORNER: Final[Setting] = Setting("worst_case_corner", "large", "large", 0.6, 5, 2_000)


def _grid() -> tuple[Setting, ...]:
    """One dimension at a time around the baseline, plus the corner and its gameweek and manager sweeps."""
    b, c = BASELINE, WORST_CASE_CORNER
    one_at_a_time = [
        *(replace(b, name=f"shock_{lvl}", shock=lvl) for lvl in EFFECT_LEVELS if lvl != b.shock),
        *(
            replace(b, name=f"manager_effect_{lvl}", manager_effect=lvl)
            for lvl in EFFECT_LEVELS
            if lvl != b.manager_effect
        ),
        *(replace(b, name=f"ties_{round(t * 100)}", tie_rate=t) for t in TIE_RATES if t != b.tie_rate),
        *(replace(b, name=f"gameweeks_{g}", gameweeks=g) for g in GAMEWEEK_SWEEP if g != b.gameweeks),
        *(replace(b, name=f"managers_{m}", managers=m) for m in MANAGER_SWEEP if m != b.managers),
    ]
    corner_sweeps = [
        *(replace(c, name=f"{c.name}_gameweeks_{g}", gameweeks=g) for g in GAMEWEEK_SWEEP if g != c.gameweeks),
        *(replace(c, name=f"{c.name}_managers_{m}", managers=m) for m in MANAGER_SWEEP if m != c.managers),
    ]
    return (b, *one_at_a_time, c, *corner_sweeps)


SETTINGS: Final[tuple[Setting, ...]] = _grid()
SETTINGS_BY_NAME: Final[Mapping[str, Setting]] = {s.name: s for s in SETTINGS}

# The settings that decide "gameweeks needed" and the MDE per count: the baseline, the corner and
# both gameweek sweeps. The rest are the one-at-a-time sensitivity settings (Tier 3).
GAMEWEEK_SWEEP_SETTINGS: Final[tuple[Setting, ...]] = tuple(
    s
    for s in SETTINGS
    if s.name in (BASELINE.name, WORST_CASE_CORNER.name)
    or s.name.startswith(("gameweeks_", "worst_case_corner_gameweeks_"))
)

Cell = tuple[Setting, float]


def cell_id(setting: Setting, share: float) -> str:
    return f"{setting.name}|{share:.2f}"


def tier_cells(tier: int) -> list[Cell]:
    """The runtime tiers, approved one at a time (#60 runtime (b)).

    1: the false-alarm cell (50%) at every setting, 55% and 53% on the gameweek-sweep settings, and
       the sensitivity cell -- enough to decide "gameweeks needed".
    2: the rest of the win-share sweep on the gameweek-sweep settings (the MDE curve).
    3: every win share on the one-at-a-time sensitivity settings.
    """
    edges = (0.53, 0.55)
    if tier == 1:
        return [
            *((s, NULL_SHARE) for s in SETTINGS),
            *((s, e) for s in GAMEWEEK_SWEEP_SETTINGS for e in edges),
            (WORST_CASE_CORNER, SENSITIVITY_SHARE),
        ]
    if tier == 2:
        return [(s, w) for s in GAMEWEEK_SWEEP_SETTINGS for w in TRUE_WIN_SHARES if w not in edges]
    if tier == 3:
        return [(s, w) for s in SETTINGS if s not in GAMEWEEK_SWEEP_SETTINGS for w in TRUE_WIN_SHARES]
    raise ValueError(f"tier must be 1, 2 or 3, got {tier}")


TIERS: Final[tuple[int, ...]] = (1, 2, 3)

# --- The fake data -----------------------------------------------------------------------------------

_NODES, _WEIGHTS = np.polynomial.hermite_e.hermegauss(80)
_WEIGHTS = _WEIGHTS / _WEIGHTS.sum()  # probabilists' Hermite: E[f(Z)], Z ~ N(0, 1)


def _logit_sds(setting: Setting) -> tuple[float, float]:
    """Share-point SDs -> logit SDs of the decided-week win probability (delta method at 50%)."""
    to_logit = 4.0 / (100.0 * (1.0 - setting.tie_rate))  # d logit / d p = 4 at p = 0.5
    return SHOCK_SD_POINTS[setting.shock] * to_logit, MANAGER_EFFECT_SD_POINTS[setting.manager_effect] * to_logit


def _decided_win_rate(setting: Setting, share: float) -> float:
    q = 0.5 + (share - 0.5) / (1.0 - setting.tie_rate)
    if not 0.0 < q < 1.0:
        raise ValueError(
            f"a true share of {share} is unreachable at {setting.tie_rate:.0%} ties (decided win rate {q:.3f})"
        )
    return q


def _intercept(setting: Setting, share: float) -> float:
    """The logit intercept whose expected decided-week win rate, over both effects, is the target."""
    q = _decided_win_rate(setting, share)
    sd = float(np.hypot(*_logit_sds(setting)))
    return float(brentq(lambda a: float(_WEIGHTS @ expit(a + sd * _NODES)) - q, -20.0, 20.0, xtol=1e-14))


def expected_share(setting: Setting, share: float) -> float:
    """The fake data's population win share at `share` -- equal to it, by construction of the intercept."""
    sd = float(np.hypot(*_logit_sds(setting)))
    decided = float(_WEIGHTS @ expit(_intercept(setting, share) + sd * _NODES))
    return setting.tie_rate * 0.5 + (1.0 - setting.tie_rate) * decided


BAND_LABELS: Final[tuple[str, ...]] = ("top", "middle", "bottom")


def generate_fake_table(setting: Setting, share: float, rng: np.random.Generator) -> pd.DataFrame:
    """One fake study's manager-week table: `manager_id`, `gameweek`, `outcome`, `band`."""
    shock_sd, manager_sd = _logit_sds(setting)
    a = _intercept(setting, share)
    m, g = setting.managers, setting.gameweeks
    shock = rng.normal(0.0, shock_sd, size=g)
    effect = rng.normal(0.0, manager_sd, size=m)
    p_win = expit(a + effect[:, None] + shock[None, :])
    tie = rng.random((m, g)) < setting.tie_rate
    win = rng.random((m, g)) < p_win
    outcome = np.where(tie, 0.5, win.astype(float))
    return pd.DataFrame(
        {
            "manager_id": np.repeat(np.arange(1, m + 1), g),
            "gameweek": np.tile(np.arange(FIRST_GAMEWEEK, FIRST_GAMEWEEK + g), m),
            "outcome": outcome.ravel(),
            "band": np.repeat(np.array(BAND_LABELS, dtype=object)[np.arange(m) % 3], g),
        }
    )


def run_fake_study(
    setting: Setting,
    share: float,
    rng: np.random.Generator,
    *,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    rerun_resamples: int = RERUN_RESAMPLES,
    rerun_seed: int = RERUN_SEED,
) -> Verdict:
    """One fake study through the real verdict; P6's re-run is counted, never applied (runtime (e))."""
    table = generate_fake_table(setting, share, rng)
    return primary_verdict(
        table,
        n_resamples=n_resamples,
        seed=seed,
        rerun_resamples=rerun_resamples,
        rerun_seed=rerun_seed,
        apply_rerun=False,
    )


# --- Inputs ------------------------------------------------------------------------------------------

PANEL_STRUCTURE_COLUMNS: Final[frozenset[str]] = frozenset({"manager_id", "gameweek", "band"})


class LabInputRefused(ValueError):
    """An input to the lab carries something beyond the panel's structure (#60 AC7)."""


def check_lab_inputs(inputs: Mapping[str, object]) -> None:
    """Refuse, by name, any frame carrying a column beyond the panel's structure.

    An allowlist, so a Stage 5 result frame, a D2 score column or anything derived from one fails
    without the check having to know its name.
    """
    for name, value in inputs.items():
        if isinstance(value, pd.DataFrame):
            extra = sorted(set(value.columns) - PANEL_STRUCTURE_COLUMNS)
            if extra:
                raise LabInputRefused(
                    f"lab input {name!r} carries column(s) {extra} beyond the panel structure "
                    f"{sorted(PANEL_STRUCTURE_COLUMNS)}; the lab never reads D2's scores against managers"
                )


# --- One cell ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CellResult:
    """One cell's tallies over its fake studies."""

    cell: str
    setting: str
    share: float
    studies: int
    overall_favourable: int  # the overall test rejects after Holm with the estimate above 50%: "power"
    family_wise_firings: int  # any of the four tests rejects: the false-alarm count at 50%
    band_favourable: tuple[int, int, int]  # top, middle, bottom: reported alongside
    rerun_triggers: int  # studies whose raw p-values would have triggered P6's re-run


def _cell_seed(cell: str) -> np.random.SeedSequence:
    return np.random.SeedSequence([MASTER_SEED, zlib.crc32(cell.encode())])


def run_cell(setting: Setting, share: float, fake_studies: int, verdict_kwargs: Mapping[str, Any]) -> CellResult:
    name = cell_id(setting, share)
    overall = family = triggers = 0
    bands = np.zeros(3, dtype=int)
    for child in _cell_seed(name).spawn(fake_studies):
        v = run_fake_study(setting, share, np.random.default_rng(child), **verdict_kwargs)
        favourable = v.reject & (v.shares > NULL_SHARE)
        overall += int(favourable[0])
        family += int(v.reject.any())
        bands += favourable[1:].astype(int)
        triggers += int(v.rerun_needed)
    return CellResult(name, setting.name, share, fake_studies, overall, family, tuple(bands.tolist()), triggers)


def _run_cell_task(args: tuple[Setting, float, int, Mapping[str, Any]]) -> CellResult:
    return run_cell(*args)


# --- Estimate, pilot, run ------------------------------------------------------------------------------

ESTIMATE_PREFIX: Final[str] = "[estimate]"
PROGRESS_PREFIX: Final[str] = "[progress]"
BUDGET_STOP_PREFIX: Final[str] = "[budget stop]"
SITTING_LIMIT_SECONDS: Final[float] = 90 * 60  # no single sitting over about 90 minutes

Size = tuple[int, int]


def _size(setting: Setting) -> Size:
    return (setting.managers, setting.gameweeks)


def _seconds_for(seconds_per_study: Mapping[Size, float], setting: Setting) -> float:
    size = _size(setting)
    if size not in seconds_per_study:
        raise KeyError(f"no pilot timing for managers={size[0]}, gameweeks={size[1]}")
    return seconds_per_study[size]


def estimate_grid_seconds(
    *, cells: Iterable[Cell], fake_studies: int, seconds_per_study: Mapping[Size, float]
) -> float:
    """Wall-clock for `cells`, each priced at its own (managers, gameweeks) size's measured cost.

    `seconds_per_study` is the pilot's wall-clock per study under the parallelism the run will use.
    """
    return sum(fake_studies * _seconds_for(seconds_per_study, s) for s, _ in cells)


@dataclass(frozen=True)
class TierEstimate:
    tier: int
    cells: int
    fake_studies: int
    seconds: float
    over_sitting_limit: bool


def estimate_by_tier(seconds_per_study: Mapping[Size, float], *, fake_studies: int) -> list[TierEstimate]:
    """Each tier's wall-clock at the pilot's parallelism, flagged when over one ~90-minute sitting."""
    estimates = []
    for tier in TIERS:
        cells = tier_cells(tier)
        seconds = estimate_grid_seconds(cells=cells, fake_studies=fake_studies, seconds_per_study=seconds_per_study)
        estimates.append(TierEstimate(tier, len(cells), fake_studies, seconds, seconds > SITTING_LIMIT_SECONDS))
    return estimates


def pilot_sizes(settings: Iterable[Setting]) -> list[Size]:
    return sorted({_size(s) for s in settings})


def _executor(workers: int) -> ProcessPoolExecutor:
    # One BLAS thread per worker, so `workers` processes share the cores rather than oversubscribe them.
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[var] = "1"
    return ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"))


def time_pilot(
    sizes: Sequence[Size],
    *,
    workers: int,
    studies_per_worker: int = 2,
    verdict_kwargs: Mapping[str, Any] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[Size, float]:
    """Wall-clock per study at each size, measured with `workers` processes busy at once.

    Returns timings only: the pilot's verdicts are discarded, so its power numbers cannot be used.
    """
    kwargs = dict(verdict_kwargs or {})
    timings: dict[Size, float] = {}
    with _executor(workers) as pool:
        warm = Setting("pilot", "medium", "medium", 0.4, 5, 100)
        list(pool.map(_run_cell_task, [(warm, 0.55, 1, kwargs)] * workers))  # start-up and imports, untimed
        for managers, gameweeks in sizes:
            setting = Setting(f"pilot_{managers}_{gameweeks}", "medium", "medium", 0.4, gameweeks, managers)
            start = clock()
            list(pool.map(_run_cell_task, [(setting, 0.55, studies_per_worker, kwargs)] * workers))
            timings[(managers, gameweeks)] = (clock() - start) / (workers * studies_per_worker)
    return timings


@dataclass(frozen=True)
class LabRun:
    finished: list[str]
    not_run: list[str]
    complete: bool
    cell_results: dict[str, CellResult] = field(default_factory=dict)


def _checkpoint(out_dir: Path, cell: str) -> Path:
    return out_dir / f"{cell.replace('|', '__')}.json"


def load_cell(path: Path) -> CellResult:
    raw = json.loads(path.read_text())
    return CellResult(**{**raw, "band_favourable": tuple(raw["band_favourable"])})


def _save(out_dir: Path, result: CellResult) -> None:
    path = _checkpoint(out_dir, result.cell)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(asdict(result), sort_keys=True))
    os.replace(tmp, path)  # atomic: a stop never leaves a half-written cell


def run_lab(
    *,
    cells: Sequence[Cell],
    fake_studies: int,
    out_dir: Path,
    budget_seconds: float,
    seconds_per_study: Mapping[Size, float],
    clock: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = print,
    verdict_kwargs: Mapping[str, Any] | None = None,
    workers: int = 1,
) -> LabRun:
    """Run `cells`, skipping any already saved in `out_dir`, until done or the budget would be passed.

    The whole set's estimate is logged before any cell starts. A cell is started only if it would
    finish inside the budget (`seconds_per_study` is per study under `workers`-way parallelism, so
    one cell on one worker takes `workers` times its share); in-flight cells finish and are saved.
    """
    kwargs = dict(verdict_kwargs or {})
    check_lab_inputs({"cells": cells, "fake_studies": fake_studies, "verdict_kwargs": kwargs})
    estimate = estimate_grid_seconds(cells=cells, fake_studies=fake_studies, seconds_per_study=seconds_per_study)
    log(f"{ESTIMATE_PREFIX} {len(cells)} cells, {estimate:,.0f} s ({estimate / 60:.1f} min) with {workers} worker(s)")

    out_dir.mkdir(parents=True, exist_ok=True)
    order = [cell_id(s, w) for s, w in cells]
    results: dict[str, CellResult] = {}
    for name in order:
        if _checkpoint(out_dir, name).exists():
            results[name] = load_cell(_checkpoint(out_dir, name))
    pending = [(s, w) for s, w in cells if cell_id(s, w) not in results]
    start = clock()
    stopped = False

    def fits(setting: Setting) -> bool:
        cell_wall = fake_studies * _seconds_for(seconds_per_study, setting) * workers
        return clock() - start + cell_wall <= budget_seconds

    def record(result: CellResult) -> None:
        _save(out_dir, result)
        results[result.cell] = result
        log(
            f"{PROGRESS_PREFIX} {len(results)}/{len(order)} {result.cell} done at {clock() - start:,.0f} s: "
            f"power {result.overall_favourable}/{result.studies}, family-wise {result.family_wise_firings}, "
            f"re-run triggers {result.rerun_triggers}"
        )

    if workers == 1:
        for setting, share in pending:
            if not fits(setting):
                stopped = True
                break
            record(run_cell(setting, share, fake_studies, kwargs))
    else:
        queue = list(pending)
        with _executor(workers) as pool:
            running: set[Future[CellResult]] = set()
            while queue or running:
                while queue and len(running) < workers and not stopped:
                    if not fits(queue[0][0]):
                        stopped = True
                        break
                    setting, share = queue.pop(0)
                    running.add(pool.submit(run_cell, setting, share, fake_studies, kwargs))
                if not running:
                    break
                done, running = wait(running, return_when=FIRST_COMPLETED)
                for future in done:
                    record(future.result())

    finished = [name for name in order if name in results]
    not_run = [name for name in order if name not in results]
    if not_run:
        log(f"{BUDGET_STOP_PREFIX} {len(finished)} finished, {len(not_run)} not run: {', '.join(not_run)}")
    return LabRun(finished, not_run, complete=not not_run and not stopped, cell_results=results)


# --- Results -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PowerResults:
    """The lab's numbers, ready for `power_report`. `is_pilot` results are refused there (#60 AC4)."""

    settings: tuple[Setting, ...]
    power: Mapping[tuple[str, float], float]
    false_alarm_firings: Mapping[str, int]
    sensitivity_power: float
    fake_studies: int
    inner_resamples: int
    is_pilot: bool
    band_power: Mapping[tuple[str, float], tuple[float, float, float]] = field(default_factory=dict)
    rerun_triggers: Mapping[str, int] = field(default_factory=dict)


def assemble_results(cell_results: Mapping[str, CellResult], *, fake_studies: int) -> PowerResults:
    """Every saved cell, as power fractions; `power_report.build_report` refuses it if any are missing."""
    power: dict[tuple[str, float], float] = {}
    band_power: dict[tuple[str, float], tuple[float, float, float]] = {}
    firings: dict[str, int] = {}
    sensitivity = float("nan")
    for r in cell_results.values():
        if r.share == NULL_SHARE:
            firings[r.setting] = r.family_wise_firings
        elif r.setting == WORST_CASE_CORNER.name and r.share == SENSITIVITY_SHARE:
            sensitivity = r.overall_favourable / r.studies
        else:
            power[(r.setting, r.share)] = r.overall_favourable / r.studies
            band_power[(r.setting, r.share)] = tuple(b / r.studies for b in r.band_favourable)  # type: ignore[assignment]
    return PowerResults(
        settings=SETTINGS,
        power=power,
        false_alarm_firings=firings,
        sensitivity_power=sensitivity,
        fake_studies=fake_studies,
        inner_resamples=INNER_RESAMPLES,
        is_pilot=False,
        band_power=band_power,
        rerun_triggers={name: r.rerun_triggers for name, r in cell_results.items()},
    )
