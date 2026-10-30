"""The Stage 5 power lab's command line (#60, #65): pilot, run one tier, run the probe, report.

    uv run python -m operational.starting_xi_power_lab pilot
    caffeinate -dimsu uv run python -m operational.starting_xi_power_lab run --tier 1
    caffeinate -dimsu uv run python -m operational.starting_xi_power_lab probe
    uv run python -m operational.starting_xi_power_lab report

`pilot` times each distinct (managers, gameweeks) size under the run's parallelism, prints each
tier's and the probe's wall-clock estimate (flagging any tier over one ~90-minute sitting) and saves
the timings; its verdicts are discarded. `run` and `probe` refuse to start without those timings,
stop cleanly at their budget (default one sitting) and resume from the saved cells. `probe` saves its
cells beside the grid's, keyed by cell name, so it never touches a grid cell, and writes `PROBE.md`.
`report` refuses a partial grid or a missing probe cell.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import yaml

from decisions.starting_xi import power_lab, power_report, verdict

RESULTS_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "decisions" / "starting_xi" / "power_lab_results"
CELLS_DIR: Final[Path] = RESULTS_DIR / "cells"
TIMINGS_PATH: Final[Path] = RESULTS_DIR / "pilot_timings.json"
LOG_PATH: Final[Path] = RESULTS_DIR / "progress.log"
PRE_REGISTRATION_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "decisions" / "starting_xi" / "PRE_REGISTRATION.yaml"
)


def _stage5_verdict() -> dict[str, object]:
    """`verdict.py`'s pre-registered constants, in `PRE_REGISTRATION.yaml`'s shape."""
    return {
        "groups": list(verdict.GROUPS),
        "sides": 2,
        "null_share": verdict.NULL_SHARE,
        "family_wise_alpha": verdict.FAMILY_WISE_ALPHA,
        "p_value": verdict.P_VALUE_CONVENTION,
        "n_resamples": verdict.N_RESAMPLES,
        "seed": verdict.SEED,
        "rerun_resamples": verdict.RERUN_RESAMPLES,
        "rerun_seed": verdict.RERUN_SEED,
    }


def _anchor(setting: power_lab.Setting) -> dict[str, object]:
    return {
        "shock": setting.shock,
        "manager_effect": setting.manager_effect,
        "tie_rate": setting.tie_rate,
        "gameweeks": setting.gameweeks,
        "managers": setting.managers,
    }


def _power_lab() -> dict[str, object]:
    """`power_lab.py`'s and `power_report.py`'s pre-registered constants, in the file's shape."""
    return {
        "true_win_shares": list(power_lab.TRUE_WIN_SHARES),
        "tie_rates": list(power_lab.TIE_RATES),
        "effect_levels": list(power_lab.EFFECT_LEVELS),
        "shock_sd_points": dict(power_lab.SHOCK_SD_POINTS),
        "manager_effect_sd_points": dict(power_lab.MANAGER_EFFECT_SD_POINTS),
        "gameweek_sweep": list(power_lab.GAMEWEEK_SWEEP),
        "manager_sweep": list(power_lab.MANAGER_SWEEP),
        "baseline": _anchor(power_lab.BASELINE),
        "worst_case_corner": _anchor(power_lab.WORST_CASE_CORNER),
        "settings": [s.name for s in power_lab.SETTINGS],
        "fake_studies": power_lab.FAKE_STUDIES,
        "inner_resamples": power_lab.INNER_RESAMPLES,
        "false_alarm_max_firings": power_report.false_alarm_max_firings(power_lab.FAKE_STUDIES),
        "sensitivity": {
            "setting": power_lab.WORST_CASE_CORNER.name,
            "share": power_lab.SENSITIVITY_SHARE,
            "min_power": power_report.SENSITIVITY_MIN_POWER,
        },
        "pass_mark": power_report.PASS_MARK,
        "headline_edge": power_report.HEADLINE_EDGE,
        "secondary_edge": power_report.SECONDARY_EDGE,
        "master_seed": power_lab.MASTER_SEED,
        "probe": {
            "shock_sd_points": power_lab.PROBE_SHOCK_SD_POINTS,
            "share": power_lab.NULL_SHARE,
            "gameweeks": list(power_lab.PROBE_GAMEWEEKS),
            "anchors": [anchor.name for anchor in power_lab.PROBE_ANCHORS],
        },
    }


def pre_registration_mismatches(pre_registration: Mapping[str, Any]) -> list[str]:
    """`PRE_REGISTRATION.yaml`'s Stage 5 entries against the code that owns them (#60 AC5).

    One `"<yaml field>: code=<value> registered=<value>"` string per mismatch. Kept apart from
    `operational.starting_xi.pre_registration_mismatches`, whose Stage 3 composition root must not
    load `research` (Holm's home).
    """
    pairs = {
        "stage5_verdict": (_stage5_verdict(), dict(pre_registration["stage5_verdict"])),
        "power_lab": (_power_lab(), dict(pre_registration["power_lab"])),
    }
    return [f"{name}: code={code!r} registered={reg!r}" for name, (code, reg) in pairs.items() if code != reg]


def _refuse_off_registration() -> None:
    mismatches = pre_registration_mismatches(yaml.safe_load(PRE_REGISTRATION_PATH.read_text()))
    if mismatches:
        raise SystemExit("the lab is off its pre-registration:\n" + "\n".join(mismatches))


def _default_workers() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def pilot(workers: int) -> None:
    sizes = power_lab.pilot_sizes(power_lab.SETTINGS)
    print(f"pilot: {os.cpu_count()} cores detected, {workers} workers; timing {len(sizes)} sizes (verdicts discarded)")
    timings = power_lab.time_pilot(sizes, workers=workers)
    for (managers, gameweeks), seconds in timings.items():
        print(f"  managers={managers:>5} gameweeks={gameweeks:>2}: {seconds:.4f} s wall per study ({workers}-way)")
    for studies in (power_lab.FAKE_STUDIES, power_lab.FAKE_STUDIES // 2):
        for est in power_lab.estimate_by_tier(timings, fake_studies=studies, workers=workers):
            flag = "  ** over 90 minutes **" if est.over_sitting_limit else ""
            print(
                f"{power_lab.ESTIMATE_PREFIX} tier {est.tier}: {est.cells} cells x {studies} studies "
                f"= {est.seconds / 60:.1f} min with {workers} workers{flag}"
            )
    probe = power_lab.probe_cells()
    seconds = power_lab.estimate_grid_seconds(
        cells=probe, fake_studies=power_lab.FAKE_STUDIES, seconds_per_study=timings, workers=workers
    )
    print(
        f"{power_lab.ESTIMATE_PREFIX} probe: {len(probe)} cells x {power_lab.FAKE_STUDIES} studies "
        f"= {seconds / 60:.1f} min with {workers} workers"
    )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TIMINGS_PATH.write_text(
        json.dumps(
            {"workers": workers, "seconds_per_study": {f"{m}x{g}": s for (m, g), s in timings.items()}}, indent=2
        )
    )


def _timings(workers: int) -> dict[tuple[int, int], float]:
    if not TIMINGS_PATH.exists():
        raise SystemExit(f"no pilot timings at {TIMINGS_PATH}; run the pilot first")
    raw = json.loads(TIMINGS_PATH.read_text())
    if raw["workers"] != workers:
        raise SystemExit(f"the pilot was timed with {raw['workers']} workers, not {workers}; re-run the pilot")
    return {(int(k.split("x")[0]), int(k.split("x")[1])): float(v) for k, v in raw["seconds_per_study"].items()}


def _log(line: str) -> None:
    print(line, flush=True)
    with LOG_PATH.open("a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {line}\n")


def _run_cells(name: str, cells: list[power_lab.Cell], *, budget_minutes: float, workers: int) -> bool:
    _refuse_off_registration()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = power_lab.run_lab(
        cells=cells,
        fake_studies=power_lab.FAKE_STUDIES,
        out_dir=CELLS_DIR,
        budget_seconds=budget_minutes * 60,
        seconds_per_study=_timings(workers),
        log=_log,
        workers=workers,
    )
    state = "complete" if result.complete else "stopped"
    _log(f"{name} {state}: {len(result.finished)} of {len(result.finished) + len(result.not_run)} cells saved")
    return result.complete


def run(tier: int, *, budget_minutes: float, workers: int) -> None:
    _run_cells(f"tier {tier}", power_lab.tier_cells(tier), budget_minutes=budget_minutes, workers=workers)


def _saved_results() -> power_lab.PowerResults:
    saved = {path.stem: power_lab.load_cell(path) for path in sorted(CELLS_DIR.glob("*.json"))}
    return power_lab.assemble_results(saved, fake_studies=power_lab.FAKE_STUDIES)


def probe(*, budget_minutes: float, workers: int) -> None:
    """Run the probe's cells (#65), then write and print its report; refused while a cell is missing."""
    if not _run_cells("probe", power_lab.probe_cells(), budget_minutes=budget_minutes, workers=workers):
        return
    text = power_report.render_probe(power_report.probe_report(_saved_results()))
    (RESULTS_DIR / "PROBE.md").write_text(text)
    print(text)
    print(f"wrote {RESULTS_DIR / 'PROBE.md'}")


def report() -> None:
    _refuse_off_registration()
    results = _saved_results()
    resolution = power_report.resolution_table(power_lab.GAMEWEEK_SWEEP, n_resamples=power_lab.INNER_RESAMPLES)
    built = power_report.build_report(results, reachable={r.gameweeks: r.threshold_reachable for r in resolution})
    (RESULTS_DIR / "REPORT.md").write_text(power_report.render(built))
    print(f"wrote {RESULTS_DIR / 'REPORT.md'}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="starting_xi_power_lab", description="Stage 5 power simulation lab (#60)")
    parser.add_argument("command", choices=["pilot", "run", "probe", "report"])
    parser.add_argument("--tier", type=int, choices=power_lab.TIERS)
    parser.add_argument("--budget-minutes", type=float, default=power_lab.SITTING_LIMIT_SECONDS / 60)
    parser.add_argument("--workers", type=int, default=_default_workers())
    args = parser.parse_args(argv)
    if args.command == "pilot":
        pilot(args.workers)
    elif args.command == "run":
        if args.tier is None:
            parser.error("run needs --tier")
        run(args.tier, budget_minutes=args.budget_minutes, workers=args.workers)
    elif args.command == "probe":
        probe(budget_minutes=args.budget_minutes, workers=args.workers)
    else:
        report()


if __name__ == "__main__":
    main()
