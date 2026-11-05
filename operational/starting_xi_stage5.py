"""The Stage 5 runner (#73): D2 over the real squads, paired with the managers, into the look or the verdict.

    uv run python -m operational.starting_xi_stage5 look
    uv run python -m operational.starting_xi_stage5 verdict
    uv run python -m operational.starting_xi_stage5 scan
    uv run python -m operational.starting_xi_stage5 check-feed

One runner, one shared feed builder, two modes (D-N1 on https://github.com/gisaf22/fpl-intelligence/issues/55).
`look` prints descriptive numbers per gameweek from GW4 up to `LOOK_CEILING_GW` and never calls
`verdict.py`'s statistics (D-N2, D-N3 as revised). `verdict` refuses a pin without the 8 gameweeks
GW4-GW11, and writes `VERDICT.md` and the local, git-ignored `FEED.csv` into `stage5_results/` and
`REALISM.md` beside the lab's `REPORT.md`, all from one feed and one pin (D-N4, D-N5, D-N6 (revised)).

**Both modes check the registration first** (`look` in `PRE_REGISTRATION.yaml`, D-N10; `verdict`
also the lab's Stage 5 entries), **then the pin's build identity**: `built_at` and `git_sha` are
required on this load path only (D-N12). **A pin's gameweeks are its ratified ones** until the
warehouse publishes a ratification flag (D-N11, https://github.com/gisaf22/fpl-warehouse/issues/224);
the freeze PR's posting (https://github.com/gisaf22/fpl-intelligence/issues/76 AC4) is the check.

`scan` and `check-feed` are the verdict PR's two checks: no manager id or per-manager row in a
committed output (AC8), and the local `FEED.csv` against the row count and SHA-256 that
`VERDICT.md` records (AC7).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Final

import pandas as pd
import yaml

from decisions.starting_xi import evaluation_panel, harness, manager_comparison, orderings, power_lab, rankers, realism
from decisions.starting_xi import verdict as verdict_procedure
from operational import starting_xi_power_lab
from warehouse import served

SEASON: Final[str] = "2026-27"
#: The ranker under test (CARD.md §2), and the seed `rankers.rules` takes: D2 draws nothing from it.
D2: Final[str] = "ppg_fixture_season"
RULE_SEED: Final[int] = 0

# The pre-registered look (PRE_REGISTRATION.yaml `look`, D-N10).
LOOK_CEILING_GW: Final[int] = 8  # the look never reads a gameweek past this one (D-N3 as revised)
ONCE_PER_PURPOSE: Final[bool] = True  # one pin for the look, another chosen once for the verdict

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PRE_REGISTRATION_PATH: Final[Path] = REPO_ROOT / "decisions" / "starting_xi" / "PRE_REGISTRATION.yaml"
RESULTS_DIR: Final[Path] = REPO_ROOT / "decisions" / "starting_xi" / "stage5_results"
LOOK_NOTEBOOK: Final[Path] = REPO_ROOT / "decisions" / "starting_xi" / "stage5_look.ipynb"
VERDICT_FILENAME: Final[str] = "VERDICT.md"
FEED_FILENAME: Final[str] = "FEED.csv"

_FEED_LINE: Final = re.compile(r"`FEED\.csv`, (\d+) rows, SHA-256 `([0-9a-f]{64})`")
_GAMEWEEK_LABEL: Final = re.compile(r"GW\d+")
_SEPARATOR_ROW: Final = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")


class OffRegistration(Exception):
    """The runner's code and `PRE_REGISTRATION.yaml` disagree; nothing is read or written."""


# ---------------------------------------------------------------------------
# The pre-run checks
# ---------------------------------------------------------------------------


def _look_registration() -> dict[str, object]:
    """The look's pre-registered constants, in the file's shape."""
    return {
        "ceiling_gw": LOOK_CEILING_GW,
        "overlap": {
            "look": {"first_gw": rankers.RULE_WINDOW[0], "last_gw": LOOK_CEILING_GW},
            "verdict": {"first_gw": realism.VERDICT_GAMEWEEKS[0], "last_gw": realism.VERDICT_GAMEWEEKS[-1]},
        },
        "once_per_purpose": ONCE_PER_PURPOSE,
    }


def pre_registration_mismatches(pre_registration: Mapping[str, Any]) -> list[str]:
    """`PRE_REGISTRATION.yaml`'s `look` key against the code that owns it: one string per mismatch.

    A missing key is a mismatch, not an error, so the refusal names it.
    """
    code, registered = _look_registration(), pre_registration.get("look")
    return [] if code == registered else [f"look: code={code!r} registered={registered!r}"]


def _refuse_off_registration(*, verdict: bool) -> None:
    registered = yaml.safe_load(PRE_REGISTRATION_PATH.read_text(encoding="utf-8"))
    mismatches = pre_registration_mismatches(registered)
    if verdict and not mismatches:
        mismatches = starting_xi_power_lab.pre_registration_mismatches(registered)
    if mismatches:
        raise OffRegistration("the Stage 5 runner is off its pre-registration:\n" + "\n".join(mismatches))


def _require_build_identity(pin: served.Pin) -> None:
    """The warehouse build's time and git sha, required on this load path only (D-N12)."""
    for name in ("built_at", "git_sha"):
        if not getattr(pin, name):
            raise served.ServedContractError(
                f"run_id {pin.run_id}: the pin has no {name}; the Stage 5 runner reads only a pin that names "
                "its warehouse build (https://github.com/gisaf22/fpl-intelligence/issues/73 D-N12)"
            )


# ---------------------------------------------------------------------------
# The shared feed builder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pinned:
    frames: served.Frames
    managers: served.ManagerFrames

    @property
    def ratified_gameweeks(self) -> tuple[int, ...]:
        """The pin's gameweeks, read as its ratified ones until the publish says so (D-N11)."""
        return tuple(sorted(int(g) for g in self.managers.picks["gw"].unique()))

    @property
    def managers_per_gameweek(self) -> dict[int, int]:
        """Every manager in the pin, per gameweek: the pin's population, not the panel."""
        counts = self.managers.picks.groupby("gw")["entry_id"].nunique()
        return {int(g): int(n) for g, n in counts.items()}


def _load(pin: served.Pin, snapshot_root: Path) -> _Pinned:
    return _Pinned(
        frames=served.load(SEASON, pin=pin, snapshot_root=snapshot_root),
        managers=served.load_managers(SEASON, pin=pin, snapshot_root=snapshot_root),
    )


@dataclass(frozen=True)
class _Paired:
    feed: pd.DataFrame  # `verdict.COLUMNS`
    points: pd.DataFrame  # `manager_id`, `gameweek`, `d2_points`, `manager_points`, on the feed's rows


def _paired(pinned: _Pinned, gameweeks: Sequence[int]) -> _Paired:
    """D2 through `harness.run` over the real squads, paired with the managers on `gameweeks`.

    The one builder both modes call (AC4), so they cannot disagree on who was scored.
    """
    picks, chips = pinned.managers.picks, pinned.managers.gameweeks
    window = (min(gameweeks), max(gameweeks))
    rule_weeks = harness.run(
        manager_comparison.real_squads(picks),
        rankers.rules(RULE_SEED)[D2],
        orderings.PRE_REGISTERED_ORDERINGS,
        pinned.frames,
        window,
    ).squad_weeks
    in_gameweeks = picks[picks["gw"].isin(gameweeks)]
    manager_points = manager_comparison.score_elevens(
        manager_comparison.chosen_eleven(in_gameweeks), pinned.frames.gameweek
    )
    weeks = evaluation_panel.manager_weeks(picks, chips, pinned.managers.ranked_counts)
    panel = evaluation_panel.evaluation_panel(weeks)
    panel = panel[panel["gw"].isin(gameweeks)].reset_index(drop=True)
    feed = manager_comparison.paired_feed(rule_weeks, manager_points, chips, panel)

    keys = feed.loc[:, ["manager_id", "gameweek"]]
    squad_ids = [manager_comparison.squad_id(int(e), int(g)) for e, g in keys.itertuples(index=False)]
    d2 = rule_weeks.set_index(["squad_id", "gw"])["no_subs_xi_points"]
    theirs = manager_points.set_index(["entry_id", "gw"])["points"]
    points = keys.assign(
        d2_points=[float(d2[(s, int(g))]) for s, g in zip(squad_ids, keys["gameweek"], strict=True)],
        manager_points=[float(theirs[(int(e), int(g))]) for e, g in keys.itertuples(index=False)],
    )
    return _Paired(feed=feed, points=points)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _named(gameweeks: Sequence[int]) -> str:
    """`GW4-GW8 (5)` for a run of consecutive gameweeks, else each one."""
    gws = list(gameweeks)
    if gws and gws == list(range(gws[0], gws[-1] + 1)) and len(gws) > 1:
        return f"GW{gws[0]}-GW{gws[-1]} ({len(gws)})"
    return ", ".join(f"GW{g}" for g in gws) + f" ({len(gws)})"


def _per_gameweek(counts: Mapping[int, int]) -> str:
    return ", ".join(f"GW{g} {n:,}" for g, n in sorted(counts.items()))


# ---------------------------------------------------------------------------
# The look
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Look:
    """The descriptive look: its header facts, one row per gameweek used, and the feed behind them.

    `feed` is the shared builder's table, kept for the test that both modes agree (AC4); `text`
    prints no row of it.
    """

    run_id: str
    ratified_gameweeks: tuple[int, ...]
    gameweeks_used: tuple[int, ...]
    ceiling_gw: int
    verdict_window: tuple[int, int]
    managers_per_gameweek: dict[int, int]
    panel_size: int
    rows: pd.DataFrame  # `gameweek`, `panel_size`, `d2_share`, `mean_points_difference`
    feed: pd.DataFrame

    @property
    def text(self) -> str:
        first, last = self.verdict_window
        lines = [
            "# Stage 5 descriptive look",
            "",
            "Descriptive numbers only: no verdict is drawn from this look.",
            "",
            f"- Pin: run {self.run_id}",
            f"- Ratified gameweeks in the pin: {_named(self.ratified_gameweeks)}",
            f"- Gameweeks used: {_named(self.gameweeks_used)}; the look's ceiling is GW{self.ceiling_gw}, "
            "however far the pin reaches",
            f"- These gameweeks sit inside the verdict window, GW{first}-GW{last}; each pin serves one purpose",
            f"- Managers in the pin per gameweek: {_per_gameweek(self.managers_per_gameweek)}",
            f"- Panel size: {self.panel_size:,} managers",
            "",
            "| Gameweek | Panel managers | Share of managers D2 beats (ties 0.5) "
            "| Mean points difference, D2 minus manager |",
            "|---|---|---|---|",
            *(
                f"| GW{int(r.gameweek)} | {int(r.panel_size):,} | {r.d2_share:.3f} | {r.mean_points_difference:.2f} |"
                for r in self.rows.itertuples(index=False)
            ),
        ]
        return "\n".join(lines) + "\n"


def look(pin: served.Pin | None = None, *, snapshot_root: Path = served.SNAPSHOT_ROOT) -> Look:
    """The look on `pin` (default: `warehouse/pin.json`), GW4 up to `LOOK_CEILING_GW` and no further.

    A pin ratified to fewer gameweeks gives those it holds, without padding.
    """
    _refuse_off_registration(verdict=False)
    pin = served.read_pin() if pin is None else pin
    _require_build_identity(pin)
    pinned = _load(pin, snapshot_root)
    ratified = pinned.ratified_gameweeks
    used = tuple(g for g in ratified if rankers.RULE_WINDOW[0] <= g <= LOOK_CEILING_GW)
    if not used:
        raise ValueError(f"run_id {pin.run_id}: no ratified gameweek from GW{rankers.RULE_WINDOW[0]} to look at")
    paired = _paired(pinned, used)
    outcomes = paired.feed.groupby("gameweek")["outcome"]
    difference = (paired.points["d2_points"] - paired.points["manager_points"]).groupby(paired.points["gameweek"])
    rows = pd.DataFrame(
        {
            "gameweek": list(used),
            "panel_size": [int(outcomes.get_group(g).size) for g in used],
            "d2_share": [float(outcomes.get_group(g).mean()) for g in used],
            "mean_points_difference": [float(difference.get_group(g).mean()) for g in used],
        }
    )
    return Look(
        run_id=pin.run_id,
        ratified_gameweeks=ratified,
        gameweeks_used=used,
        ceiling_gw=LOOK_CEILING_GW,
        verdict_window=(realism.VERDICT_GAMEWEEKS[0], realism.VERDICT_GAMEWEEKS[-1]),
        managers_per_gameweek=pinned.managers_per_gameweek,
        panel_size=int(paired.feed["manager_id"].nunique()),
        rows=rows,
        feed=paired.feed,
    )


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerdictHeader:
    """What identifies the one pin the verdict rests on (AC5)."""

    run_id: str | None
    built_at: str | None
    git_sha: str | None
    ratified_gameweeks: tuple[int, ...] | None
    managers_per_gameweek: dict[int, int] | None


def verdict_header(pin: served.Pin, *, snapshot_root: Path) -> VerdictHeader:
    pinned = _load(pin, snapshot_root)
    return VerdictHeader(
        run_id=pin.run_id,
        built_at=pin.built_at,
        git_sha=pin.git_sha,
        ratified_gameweeks=pinned.ratified_gameweeks,
        managers_per_gameweek=pinned.managers_per_gameweek,
    )


def render_verdict_header(header: VerdictHeader) -> list[str]:
    """The header's lines.

    Raises:
        ValueError: a field is missing or empty, naming it, so nothing is written without it.
    """
    for item in fields(header):
        if not getattr(header, item.name):
            raise ValueError(f"the verdict header has no {item.name}; no result is written without it")
    assert header.ratified_gameweeks is not None and header.managers_per_gameweek is not None
    return [
        f"- Pin: run `{header.run_id}`, built `{header.built_at}`, warehouse git sha `{header.git_sha}`",
        f"- Ratified gameweeks in the pin: {_named(header.ratified_gameweeks)}",
        f"- Managers in the pin per gameweek: {_per_gameweek(header.managers_per_gameweek)}",
    ]


def _feed_bytes(feed: pd.DataFrame) -> bytes:
    """Deterministic bytes: `verdict.COLUMNS` in order, rows sorted, no index."""
    ordered = feed.loc[:, list(verdict_procedure.COLUMNS)].sort_values(["manager_id", "gameweek"], ignore_index=True)
    text: str = ordered.to_csv(index=False, lineterminator="\n")
    return text.encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _result_rows(feed: pd.DataFrame, result: verdict_procedure.Verdict) -> list[str]:
    managers = {"overall": int(feed["manager_id"].nunique())} | {
        band: int(feed.loc[feed["band"] == band, "manager_id"].nunique()) for band in verdict_procedure.BANDS
    }
    return [
        f"| {group} | {managers[group]:,} | {share:.4f} | {p_raw:.6f} | {p_adj:.6f} | {'yes' if reject else 'no'} |"
        for group, share, p_raw, p_adj, reject in zip(
            result.groups, result.shares, result.p_raw, result.p_adj, result.reject, strict=True
        )
    ]


def verdict(
    pin: served.Pin | None = None,
    *,
    snapshot_root: Path = served.SNAPSHOT_ROOT,
    results_dir: Path = RESULTS_DIR,
    realism_dir: Path = starting_xi_power_lab.RESULTS_DIR,
    cells_dir: Path = starting_xi_power_lab.CELLS_DIR,
) -> Path:
    """The verdict on exactly `realism.VERDICT_GAMEWEEKS`, written once from one feed and one pin.

    Writes `REALISM.md` first, so a realism error leaves no verdict result, then `FEED.csv` and
    `VERDICT.md`. Returns `VERDICT.md`'s path.

    Raises:
        OffRegistration: the code is off `PRE_REGISTRATION.yaml`.
        warehouse.served.ServedContractError: the pin has no `built_at` or `git_sha`, or its bytes or
            contract do not match.
        ValueError: the pin lacks any of the verdict's gameweeks, or the header lacks a field.
    """
    _refuse_off_registration(verdict=True)
    pin = served.read_pin() if pin is None else pin
    _require_build_identity(pin)
    header = render_verdict_header(verdict_header(pin, snapshot_root=snapshot_root))
    pinned = _load(pin, snapshot_root)
    gameweeks = realism.VERDICT_GAMEWEEKS
    absent = [g for g in gameweeks if g not in pinned.ratified_gameweeks]
    if absent:
        held = [g for g in gameweeks if g in pinned.ratified_gameweeks]
        raise ValueError(
            f"run_id {pin.run_id}: the verdict needs the {len(gameweeks)} scorable ratified gameweeks "
            f"{_named(gameweeks)}; the pin holds {len(held)} of them, lacking {', '.join(f'GW{g}' for g in absent)}"
        )

    feed = _paired(pinned, gameweeks).feed
    result = verdict_procedure.primary_verdict(feed)
    measurement = realism.measure(feed, gameweeks=gameweeks)
    levels = realism.committed_levels(cells_dir)
    feed_bytes = _feed_bytes(feed)

    realism_dir.mkdir(parents=True, exist_ok=True)
    realism_path = realism.write(realism_dir, measurement, levels)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / FEED_FILENAME).write_bytes(feed_bytes)
    rerun = (
        f"applied at {verdict_procedure.RERUN_RESAMPLES:,} repeats"
        if result.rerun
        else ("needed, not applied" if result.rerun_needed else "not needed")
    )
    lines = [
        "# Stage 5 verdict",
        "",
        *header,
        f"- Verdict gameweeks: {_named(gameweeks)}",
        f"- Feed: `{FEED_FILENAME}`, {len(feed):,} rows, SHA-256 `{_sha256(feed_bytes)}` (local, git-ignored)",
        f"- Realism check: `power_lab_results/{realism_path.name}`, SHA-256 `{_sha256(realism_path.read_bytes())}`",
        "",
        "## D2's win share against the evaluation panel",
        "",
        f"Four two-sided crossed-bootstrap tests against {verdict_procedure.NULL_SHARE:g}, Holm-adjusted at a "
        f"family-wise alpha of {verdict_procedure.FAMILY_WISE_ALPHA:g} ({verdict_procedure.N_RESAMPLES:,} repeats; "
        f"near-threshold re-run: {rerun}).",
        "",
        "| Group | Managers | Win share | Raw p | Holm-adjusted p | Rejected |",
        "|---|---|---|---|---|---|",
        *_result_rows(feed, result),
    ]
    path = results_dir / VERDICT_FILENAME
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


# ---------------------------------------------------------------------------
# The verdict PR's two checks
# ---------------------------------------------------------------------------


def _scanned_text(path: Path) -> str:
    """A file's text, or for a notebook its saved outputs only (its source is code, not output)."""
    if path.suffix != ".ipynb":
        return path.read_text(encoding="utf-8")
    parts: list[str] = []
    for cell in json.loads(path.read_text(encoding="utf-8")).get("cells", []):
        for output in cell.get("outputs", []):
            parts.extend(output.get("text", []))
            for value in output.get("data", {}).values():
                parts.extend(value if isinstance(value, list) else [str(value)])
    return "".join(parts)


def _allowed_row_key(cell: str) -> bool:
    """A table row may be keyed on a gameweek, a verdict group or a swept gameweek count; any
    other key is one manager's row."""
    key = cell.strip()
    return (
        bool(_GAMEWEEK_LABEL.fullmatch(key))
        or key in verdict_procedure.GROUPS
        or key in {str(g) for g in power_lab.GAMEWEEK_SWEEP}
    )


def scan_outputs(paths: Iterable[Path], manager_ids: Iterable[int]) -> list[str]:
    """Each manager id, as a whole token, and each per-manager table row in `paths` (AC8).

    Empty means clean. An ordinary number equal to a manager id is reported too: a loud false
    alarm rather than a silent pass.
    """
    ids = re.compile(r"\b(" + "|".join(str(int(i)) for i in sorted(set(manager_ids))) + r")\b")
    findings: list[str] = []
    for path in paths:
        lines = _scanned_text(path).splitlines()
        for number, line in enumerate(lines, start=1):
            for found in ids.findall(line):
                findings.append(f"{path}:{number}: manager id {found}")
            stripped = line.strip()
            if not stripped.startswith("|") or _SEPARATOR_ROW.match(stripped):
                continue
            is_header = number < len(lines) and bool(_SEPARATOR_ROW.match(lines[number].strip()))
            cells = stripped.strip("|").split("|")
            if not is_header and not _allowed_row_key(cells[0]):
                findings.append(f"{path}:{number}: a table row keyed on {cells[0].strip()!r}, not a gameweek or group")
    return findings


def check_feed(feed_path: Path, verdict_path: Path) -> list[str]:
    """The local `FEED.csv` against the row count and SHA-256 `VERDICT.md` records (AC7)."""
    recorded = _FEED_LINE.search(verdict_path.read_text(encoding="utf-8"))
    if recorded is None:
        return [f"{verdict_path}: no feed row count and SHA-256 recorded"]
    rows, sha = int(recorded.group(1)), recorded.group(2)
    data = feed_path.read_bytes()
    problems = []
    if _sha256(data) != sha:
        problems.append(f"{feed_path}: SHA-256 {_sha256(data)} differs from the recorded {sha}")
    lines = data.decode("utf-8").splitlines()
    if len(lines) - 1 != rows:
        problems.append(f"{feed_path}: {len(lines) - 1} rows, the record says {rows}")
    if not lines or lines[0].split(",") != list(verdict_procedure.COLUMNS):
        header = lines[0] if lines else ""
        problems.append(f"{feed_path}: columns {header!r}, expected {list(verdict_procedure.COLUMNS)}")
    return problems


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="starting_xi_stage5", description="Stage 5 runner (#73)")
    parser.add_argument("command", choices=["look", "verdict", "scan", "check-feed"])
    parser.add_argument("paths", nargs="*", type=Path, help="scan: the outputs to scan (default: the committed ones)")
    args = parser.parse_args(argv)
    if args.command == "look":
        print(look().text, end="")
    elif args.command == "verdict":
        print(verdict())
    elif args.command == "scan":
        paths = args.paths or [
            RESULTS_DIR / VERDICT_FILENAME,
            starting_xi_power_lab.RESULTS_DIR / realism.FILENAME,
            LOOK_NOTEBOOK,
        ]
        managers = served.load_managers(SEASON, pin=served.read_pin()).picks["entry_id"].unique()
        findings = scan_outputs([p for p in paths if p.exists()], manager_ids=(int(i) for i in managers))
        if findings:
            raise SystemExit("\n".join(findings))
        print(f"clean: {', '.join(str(p) for p in paths if p.exists())}")
    else:
        problems = check_feed(RESULTS_DIR / FEED_FILENAME, RESULTS_DIR / VERDICT_FILENAME)
        if problems:
            raise SystemExit("\n".join(problems))
        print("FEED.csv matches the row count and SHA-256 recorded in VERDICT.md")


if __name__ == "__main__":
    main()
