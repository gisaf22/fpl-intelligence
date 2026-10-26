"""The `starting_xi` composition root: the one place the rules, the sampler, the harness and the
results writer meet.

`run_study` checks the run against `PRE_REGISTRATION.yaml` and the git tree, samples squads once,
replays each rule in `rankers.rules(seed)` through the harness at `rankers.RULE_WINDOW`, flags
zero-information squad-weeks, and writes the artefact. Reporting is `decisions.starting_xi.report`'s.

`operational/` is covered by no `.importlinter` contract, which is what makes it the legal place to
wire the rules (which import `model/`) into the harness. (`serve` also loads whenever this module
does, because `operational/__init__.py` eagerly re-exports `operational.recommend`.)
"""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

import pandas as pd
import yaml

from decisions.starting_xi import orderings, rankers, report, results, sampler, uncertainty
from decisions.starting_xi.harness import BenchOrder, HarnessResult, RankFn
from decisions.starting_xi.harness import run as harness_run
from warehouse import served

# The season every run reads (`decisions/starting_xi/DATA.md`).
SEASON: Final[str] = "2025-26"

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PRE_REGISTRATION_PATH: Final[Path] = REPO_ROOT / "decisions" / "starting_xi" / "PRE_REGISTRATION.yaml"
RESULTS_ROOT: Final[Path] = REPO_ROOT / "decisions" / "starting_xi" / "results"

# A structural property of the sampler: each gameweek draws its own squads.
CONSTRUCTION: Final[str] = "weekly"

DEADLINE_FALLBACK_SENSITIVITY: Final[Mapping[str, object]] = {
    "run": "excluding_deadline_fallback_weeks",
    "excludes": "deadline_count_is_realised",
    "holm_family": False,
}
"""Stage 5's sensitivity run beside the headline (#59 D3): it drops exactly the manager-weeks T2
flags in `excludes`, is reported with its interval, and is not one of the Holm family's tests."""


class RunRefused(RuntimeError):
    """The pre-run check failed and the caller did not force past it."""


@dataclass(frozen=True)
class StartingXIRun:
    """One run's summary -- `run_id`, where it landed, and its squad-week count."""

    run_id: str
    results_dir: Path
    n_squad_weeks: int


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _flag_zero_information(t2: pd.DataFrame) -> pd.DataFrame:
    """Flag every squad-week where every rule picked the same XI (CARD.md §3, #31).

    Such a week carries no information about which rule is better. Its rows are kept and flagged
    rather than dropped, so the artefact still holds every squad-week; reporting excludes them and
    the manifest records their count. The flag sits after `is_zero_gap`, T2's own column order.
    """
    same_xi = t2.groupby(["squad_id", "gw"])["chosen_xi"].transform("nunique") == 1
    flagged = t2.copy()
    flagged.insert(flagged.columns.get_loc("is_zero_gap") + 1, "is_zero_information", same_xi.to_numpy())
    return flagged


def _sampler_diagnostics(run_record: pd.DataFrame) -> list[dict[str, object]]:
    """§7.3's manifest metadata: the sampler's per-gameweek run record, as plain Python values.

    `DataFrame.to_dict` returns numpy scalars for numeric columns, which `json.dumps`
    (`results.manifest_document`) does not serialise; `.item()` narrows each cell back to a native
    type.
    """
    return [
        {key: (value.item() if hasattr(value, "item") else value) for key, value in row.items()}
        for row in run_record.to_dict("records")
    ]


# ---------------------------------------------------------------------------
# Run hygiene -- the pre-run check
# ---------------------------------------------------------------------------


def pre_registration_mismatches(
    *,
    bench_order: BenchOrder,
    rank_fns: Mapping[str, RankFn],
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    pre_registration: Mapping[str, Any],
) -> list[str]:
    """Every value `PRE_REGISTRATION.yaml` freezes, compared against this run and the code that owns it.

    Returns one `"<yaml field>: run=<value> registered=<value>"` string per mismatch, in the file's
    field order; empty when the run and the code are on-registration.
    """
    reg = pre_registration
    span = reg["scored_gameweeks"]
    registered_gameweeks = list(range(span["first_gw"], span["last_gw"] + 1))
    rule_gameweeks = list(range(rankers.RULE_WINDOW[0], rankers.RULE_WINDOW[1] + 1))
    pairs: dict[str, tuple[object, object]] = {
        "rules": (sorted(rank_fns), sorted(reg["rules"])),
        # The run builds exactly the gameweeks the rules score.
        "scored_gameweeks": (
            {"run": sorted(set(gameweeks)), "rules": rule_gameweeks},
            {"run": registered_gameweeks, "rules": registered_gameweeks},
        ),
        "phases": ({name: [first, last] for name, first, last in report.PHASES}, dict(reg["phases"])),
        "squad_modes": (list(sampler.SQUAD_MODES), list(reg["squad_modes"])),
        "squads_per_gameweek": (n_squads, reg["squads_per_gameweek"]),
        "construction": (CONSTRUCTION, reg["construction"]),
        "master_seed": (seed, reg["master_seed"]),
        "bench_ordering": ([name for name, _ in bench_order], list(reg["bench_ordering"])),
        "gameweek_interval": (
            {
                "n": uncertainty.N_RESAMPLES,
                "block": uncertainty.BLOCK_GWS,
                "ci_level": uncertainty.CI_LEVEL,
                "seed": uncertainty.SEED,
            },
            dict(reg["gameweek_interval"]),
        ),
        "deadline_fallback_sensitivity": (
            dict(DEADLINE_FALLBACK_SENSITIVITY),
            dict(reg["deadline_fallback_sensitivity"]),
        ),
    }
    return [
        f"{field}: run={ran!r} registered={registered!r}"
        for field, (ran, registered) in pairs.items()
        if ran != registered
    ]


def _git_state(repo_root: Path) -> tuple[str, bool]:
    """`(HEAD sha, clean)`. Untracked files count as dirty -- they can be imported; ignored ones don't."""

    def _git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    return _git("rev-parse", "HEAD"), _git("status", "--porcelain") == ""


def preflight(
    *,
    bench_order: BenchOrder,
    rank_fns: Mapping[str, RankFn],
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    warehouse_pin: served.Pin,
    repo_root: Path = REPO_ROOT,
    pre_registration_path: Path = PRE_REGISTRATION_PATH,
    allow_dirty: bool = False,
    allow_off_registration: bool = False,
) -> results.RunProvenance:
    """The pre-run check. Refuses a dirty tree or an off-registration run unless forced; a forced
    run proceeds and is marked non-canonical, with the reason recorded.

    Raises:
        RunRefused: on a dirty tree without `allow_dirty`, or on any
            `pre_registration_mismatches` without `allow_off_registration`.
    """
    git_sha, clean = _git_state(repo_root)
    mismatches = pre_registration_mismatches(
        bench_order=bench_order,
        rank_fns=rank_fns,
        gameweeks=gameweeks,
        n_squads=n_squads,
        seed=seed,
        pre_registration=yaml.safe_load(pre_registration_path.read_text(encoding="utf-8")),
    )
    if not clean and not allow_dirty:
        raise RunRefused(f"working tree at {repo_root} is dirty; commit first or pass --allow-dirty (non-canonical)")
    if mismatches and not allow_off_registration:
        raise RunRefused(
            "run differs from PRE_REGISTRATION.yaml; pass --allow-off-registration (non-canonical) to force:\n  "
            + "\n  ".join(mismatches)
        )
    reasons = (["dirty_tree"] if not clean else []) + [f"off_registration:{m.split(':')[0]}" for m in mismatches]
    return results.RunProvenance(
        git_sha=git_sha,
        clean_tree=clean,
        warehouse_run_id=warehouse_pin.run_id,
        warehouse_sha256=warehouse_pin.sha256,
        pre_registration_sha256=served.sha256_of(pre_registration_path),
        canonical=not reasons,
        non_canonical_reasons=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# The run (§5.1.2)
# ---------------------------------------------------------------------------


def deadline_fallback_gameweeks(frames: served.Frames) -> list[int]:
    """The frames' gameweeks with no fixture count as at the deadline for any player, ascending.

    Their fixture count is the realised one (`served.Frames`, #59 D3); the run manifest lists them.
    """
    gameweek = frames.gameweek
    return sorted(int(gw) for gw in gameweek.loc[gameweek["deadline_count_is_realised"], "gw"].unique())


def run_study(
    frames: served.Frames,
    *,
    bench_order: BenchOrder = orderings.PRE_REGISTERED_ORDERINGS,
    rank_fns: Mapping[str, RankFn] | None = None,
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    squad_mode: str,
    results_root: Path,
    repo_root: Path = REPO_ROOT,
    pre_registration_path: Path = PRE_REGISTRATION_PATH,
    allow_dirty: bool = False,
    allow_off_registration: bool = False,
) -> StartingXIRun:
    """Run the `starting_xi` study against warehouse frames already in hand -- the load-free core.

    Sequence: `preflight` (refuse, or mark non-canonical), sample squads once, replay each rule
    at `rankers.RULE_WINDOW`, flag zero-information squad-weeks, build the manifest, write the
    artefact.

    Args:
        frames: the pinned warehouse frames, already in hand. The run is recorded against
            their pin (run_id and sha256s).
        bench_order: defaulted to the sole pre-registered policy set; `harness.run` still
            receives it explicitly on every call.
        rank_fns: name -> `rank(frames) -> RankerOutput`. Defaults to `rankers.rules(seed)`,
            CARD.md §3's rule grid, each replayed at `rankers.RULE_WINDOW`.
        gameweeks: the build gameweeks, explicit; the canonical run builds GW4-38.
        n_squads: squads per gameweek.
        seed: the master seed, required with no default (§2.9, §8.4).
        squad_mode: `sampler.SQUAD_MODES`' uniform or ownership-weighted squads, required with no
            default (CARD.md §3); one run per mode, recorded in the run's identity.
        results_root: where `results.write` lands the run's directory (§7.4).
        repo_root, pre_registration_path, allow_dirty, allow_off_registration: see `preflight`.

    Returns:
        A `StartingXIRun` summary.

    Raises:
        RunRefused: from `preflight`, before anything is sampled or written.
    """
    rank_fns = rankers.rules(seed) if rank_fns is None else rank_fns
    provenance = preflight(
        bench_order=bench_order,
        rank_fns=rank_fns,
        gameweeks=gameweeks,
        n_squads=n_squads,
        seed=seed,
        warehouse_pin=frames.pin,
        repo_root=repo_root,
        pre_registration_path=pre_registration_path,
        allow_dirty=allow_dirty,
        allow_off_registration=allow_off_registration,
    )
    sample = sampler.sample_squads(frames, gameweeks, n_squads, seed, squad_mode=squad_mode)

    squad_weeks: list[pd.DataFrame] = []
    ordering_replays: list[pd.DataFrame] = []
    ranker_windows: dict[str, tuple[int, int]] = {}
    for name, rank_fn in rank_fns.items():
        window = rankers.RULE_WINDOW
        result: HarnessResult = harness_run(sample.squads, rank_fn, bench_order, frames, window)
        squad_weeks.append(result.squad_weeks)
        ordering_replays.append(result.ordering_replays)
        ranker_windows[name] = window

    t2 = _flag_zero_information(pd.concat(squad_weeks, ignore_index=True))
    t5 = pd.concat(ordering_replays, ignore_index=True)

    manifest = results.Manifest(
        mart_pin=asdict(sample.mart_pin),
        bench_order=[name for name, _ in bench_order],
        master_seed=seed,
        squad_mode=squad_mode,
        squad_set_id=sample.squad_set_id,
        build_gameweeks=list(gameweeks),
        ranker_windows=ranker_windows,
        sampler_diagnostics=_sampler_diagnostics(sample.run_record),
        zero_information_squad_weeks=int(t2.drop_duplicates(["squad_id", "gw"])["is_zero_information"].sum()),
        gameweek_interval=results.GameweekIntervalParams(
            n=uncertainty.N_RESAMPLES, block=uncertainty.BLOCK_GWS, ci_level=uncertainty.CI_LEVEL, seed=uncertainty.SEED
        ),
        deadline_fallback_gameweeks=deadline_fallback_gameweeks(frames),
        construction=CONSTRUCTION,
        provenance=provenance,
    )

    identifier = results.write(t2, t5, manifest, results_root)
    return StartingXIRun(run_id=identifier, results_dir=results_root / identifier, n_squad_weeks=len(t2))


def build_and_run(
    *,
    bench_order: BenchOrder = orderings.PRE_REGISTERED_ORDERINGS,
    rank_fns: Mapping[str, RankFn] | None = None,
    gameweeks: Sequence[int],
    n_squads: int,
    seed: int,
    squad_mode: str,
    results_root: Path,
    season: str = SEASON,
    pin: served.Pin | None = None,
    snapshot_root: Path = served.SNAPSHOT_ROOT,
    allow_dirty: bool = False,
    allow_off_registration: bool = False,
) -> StartingXIRun:
    """Load the pinned warehouse frames and run the study against them. The one line that reads data."""
    return run_study(
        served.load(season, pin=pin, snapshot_root=snapshot_root),
        bench_order=bench_order,
        rank_fns=rank_fns,
        gameweeks=gameweeks,
        n_squads=n_squads,
        seed=seed,
        squad_mode=squad_mode,
        results_root=results_root,
        allow_dirty=allow_dirty,
        allow_off_registration=allow_off_registration,
    )


def main(argv: Sequence[str] | None = None) -> None:
    """Run the pre-registered study. Prints the run id and its canonical status -- no regret."""
    parser = argparse.ArgumentParser(description="Run the pre-registered starting_xi study.")
    parser.add_argument("--allow-dirty", action="store_true", help="run on a dirty tree; marks the run non-canonical")
    parser.add_argument(
        "--allow-off-registration",
        action="store_true",
        help="run despite differing from PRE_REGISTRATION.yaml; marks the run non-canonical",
    )
    parser.add_argument(
        "--squad-mode", required=True, choices=sampler.SQUAD_MODES, help="uniform or ownership-weighted squads"
    )
    args = parser.parse_args(argv)
    pre_registration = yaml.safe_load(PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    span = pre_registration["scored_gameweeks"]
    run = build_and_run(
        gameweeks=range(span["first_gw"], span["last_gw"] + 1),
        n_squads=pre_registration["squads_per_gameweek"],
        seed=pre_registration["master_seed"],
        squad_mode=args.squad_mode,
        results_root=RESULTS_ROOT,
        allow_dirty=args.allow_dirty,
        allow_off_registration=args.allow_off_registration,
    )
    canonical = results.read(RESULTS_ROOT, run.run_id)["manifest"]["provenance"]["canonical"]  # type: ignore[index]
    print(f"run_id={run.run_id} canonical={canonical} squad_weeks={run.n_squad_weeks}")


if __name__ == "__main__":
    main()
