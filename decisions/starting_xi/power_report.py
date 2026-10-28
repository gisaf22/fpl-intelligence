"""The power lab's report: the acceptance gate, the MDE table and its labels (#60 P10, P11, U-U5).

Pure functions over a `PowerResults` -- every one can be called with a hand-built power table.

**Row labels, in order (U3, U4, U5).** At a gameweek count:

0. the false-alarm check failed at any setting at that count: "verdict procedure invalid at this
   count (false-alarm check failed)" -- no power is claimed there (U5);
1. Holm's strictest threshold cannot be reached: "undetermined by construction", its power still
   shown and its MDE "not defined at this count" (U, U2, U4);
2. otherwise, power at the headline edge (55%) below 80%: "underpowered" (U3);
3. on a reachable row only, in addition to "underpowered": no swept share reaches 80% -> "MDE beyond
   the sweep" (U3, U4).

**The gate (P11, AC3, U5).** The false-alarm check (AC1) gates per gameweek count; the sensitivity
check (AC2, one cell at the corner) gates the whole table. A partial grid is refused outright.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from decisions.starting_xi import verdict
from decisions.starting_xi.power_lab import (
    FAKE_STUDIES,
    GAMEWEEK_SWEEP,
    MANAGER_EFFECT_SD_POINTS,
    NULL_SHARE,
    SENSITIVITY_SHARE,
    SETTINGS,
    SHOCK_SD_POINTS,
    TRUE_WIN_SHARES,
    WORST_CASE_CORNER,
    PowerResults,
    Setting,
)

# The pre-registered reading (PRE_REGISTRATION.yaml `power_lab`).
PASS_MARK: Final[float] = 0.8
HEADLINE_EDGE: Final[float] = 0.55
SECONDARY_EDGE: Final[float] = 0.53
SENSITIVITY_MIN_POWER: Final[float] = 0.99
FALSE_ALARM_SE_MULTIPLIER: Final[float] = 2.0
HOLM_STRICTEST: Final[float] = verdict.FAMILY_WISE_ALPHA / len(verdict.GROUPS)

INVALID: Final[str] = "verdict procedure invalid at this count (false-alarm check failed)"
UNDETERMINED: Final[str] = "undetermined by construction"
UNDERPOWERED: Final[str] = "underpowered"
NOT_DEFINED: Final[str] = "not defined at this count"
U4_VIOLATION: Final[str] = '"MDE beyond the sweep" without "underpowered"'
CONDITIONAL: Final[str] = "conditional on the assumed edge, shock size, manager effect and tie rate"


class ReportRefused(ValueError):
    """The results cannot be reported at all: a pilot's numbers, or a partial grid."""


def false_alarm_max_firings(n_studies: int, alpha: float = verdict.FAMILY_WISE_ALPHA) -> int:
    """N2: the most family-wise firings that pass, `floor(n (alpha + 2 sqrt(alpha (1 - alpha) / n)))`."""
    bound = alpha + FALSE_ALARM_SE_MULTIPLIER * math.sqrt(alpha * (1 - alpha) / n_studies)
    return math.floor(n_studies * bound)


# --- Row labels --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RowLabel:
    status: str | None
    mde: float | str | None  # a swept share, NOT_DEFINED, or None when beyond the sweep
    mde_beyond_sweep: bool
    power_at_headline: float | None
    headline_detectable: bool | None
    secondary_detectable: bool | None


def label_row(
    power_by_share: Mapping[float, float], *, threshold_reachable: bool, false_alarm_ok: bool = True
) -> RowLabel:
    """One gameweek count's (or setting's) labels, in the order of this module's docstring."""
    if not false_alarm_ok:
        return RowLabel(INVALID, NOT_DEFINED, False, None, None, None)
    headline = power_by_share[HEADLINE_EDGE]
    if not threshold_reachable:
        return RowLabel(UNDETERMINED, NOT_DEFINED, False, headline, None, None)
    reaching = [share for share in sorted(power_by_share) if power_by_share[share] >= PASS_MARK]
    mde = reaching[0] if reaching else None
    return RowLabel(
        status=UNDERPOWERED if headline < PASS_MARK else None,
        mde=mde,
        mde_beyond_sweep=mde is None,
        power_at_headline=headline,
        headline_detectable=mde is not None and mde <= HEADLINE_EDGE,
        secondary_detectable=mde is not None and mde <= SECONDARY_EDGE,
    )


def check_row(label: RowLabel) -> list[str]:
    """The label combinations U3-U5 rule out; `build_report` fails loud on any."""
    problems = []
    if label.mde_beyond_sweep and label.status != UNDERPOWERED:
        problems.append(U4_VIOLATION)
    if label.status in (INVALID, UNDETERMINED) and label.mde != NOT_DEFINED:
        problems.append(f'"{label.status}" with an MDE value')
    if label.status == INVALID and label.power_at_headline is not None:
        problems.append("power claimed at an invalid count")
    if label.status == UNDETERMINED and label.power_at_headline is None:
        problems.append("an undetermined row hides its power")
    return problems


# --- Reading the grid ----------------------------------------------------------------------------------


def _curve(results: PowerResults, setting: Setting) -> dict[float, float]:
    return {share: results.power[(setting.name, share)] for share in TRUE_WIN_SHARES}


def _false_alarm_ok(results: PowerResults, settings: Iterable[Setting]) -> bool:
    limit = false_alarm_max_firings(results.fake_studies)
    return all(results.false_alarm_firings[s.name] <= limit for s in settings)


def _at_count(results: PowerResults, gameweeks: int) -> list[Setting]:
    return [s for s in results.settings if s.gameweeks == gameweeks]


def _lowest_power(results: PowerResults, settings: Sequence[Setting]) -> Setting:
    return min(settings, key=lambda s: results.power[(s.name, HEADLINE_EDGE)])


@dataclass(frozen=True)
class MdeReading:
    setting: str
    gameweeks: int
    label: RowLabel


def mde_reading(results: PowerResults, reachable: Mapping[int, bool]) -> MdeReading:
    """P10/AC4: the MDE at the lowest-power setting of the whole grid (lowest power at 55%)."""
    weakest = _lowest_power(results, results.settings)
    label = label_row(
        _curve(results, weakest),
        threshold_reachable=reachable[weakest.gameweeks],
        false_alarm_ok=_false_alarm_ok(results, _at_count(results, weakest.gameweeks)),
    )
    return MdeReading(weakest.name, weakest.gameweeks, label)


@dataclass(frozen=True)
class GameweekRow:
    gameweeks: int
    setting: str
    label: RowLabel


def mde_by_gameweeks(results: PowerResults, reachable: Mapping[int, bool]) -> list[GameweekRow]:
    """AC9: each swept count, read at its lowest-power setting, gated by every setting at that count (U5)."""
    rows = []
    for gameweeks in GAMEWEEK_SWEEP:
        settings = _at_count(results, gameweeks)
        weakest = _lowest_power(results, settings)
        label = label_row(
            _curve(results, weakest),
            threshold_reachable=reachable[gameweeks],
            false_alarm_ok=_false_alarm_ok(results, settings),
        )
        rows.append(GameweekRow(gameweeks, weakest.name, label))
    return rows


@dataclass(frozen=True)
class GameweeksNeeded:
    edge: float
    count: int | None
    largest_tried: int
    text: str


def gameweeks_needed(results: PowerResults, edge: float) -> GameweeksNeeded:
    """AC8, U5: the smallest swept count where the false-alarm check passes at every setting there
    and power at `edge` is at least 80% at that count's lowest-power setting."""
    largest = max(GAMEWEEK_SWEEP)
    for gameweeks in GAMEWEEK_SWEEP:
        settings = _at_count(results, gameweeks)
        if not settings or not _false_alarm_ok(results, settings):
            continue
        if min(results.power[(s.name, edge)] for s in settings) >= PASS_MARK:
            text = f"{gameweeks} gameweeks for 80% power at a true {edge:.0%}, {CONDITIONAL}"
            return GameweeksNeeded(edge, gameweeks, largest, text)
    text = (
        f"no swept count reaches 80% power at a true {edge:.0%} with a valid verdict procedure "
        f"(largest tried: {largest}): more gameweeks than the season has, {CONDITIONAL}"
    )
    return GameweeksNeeded(edge, None, largest, text)


@dataclass(frozen=True)
class ManagerRow:
    setting: str
    managers: int
    gameweeks: int
    rows: int
    power_at_headline: float


def manager_sweep(results: PowerResults) -> list[ManagerRow]:
    """AC10: power at 55% against the manager count, with the manager-week rows each setting implies."""
    return [
        ManagerRow(s.name, s.managers, s.gameweeks, s.managers * s.gameweeks, results.power[(s.name, HEADLINE_EDGE)])
        for s in results.settings
    ]


# --- p-value resolution (AC11) -------------------------------------------------------------------------

RESOLUTION_METHOD: Final[str] = (
    "exact enumeration of the gameweek resampling: G gameweeks drawn with replacement give C(2G-1, G) "
    "distinct multisets; the smallest step a two-sided p-value can take from them is 2 / G^G (all G draws "
    "the same gameweek), and the Monte Carlo floor is 2 / (B + 1); the threshold is reachable when both "
    "are at or below Holm's strictest threshold"
)


@dataclass(frozen=True)
class Resolution:
    gameweeks: int
    n_resamples: int
    distinct_resamples: int
    smallest_step: float
    monte_carlo_floor: float
    threshold_reachable: bool
    method: str


def resolution(gameweeks: int, *, n_resamples: int) -> Resolution:
    step = 2.0 * float(gameweeks) ** -gameweeks
    floor = 2.0 / (n_resamples + 1)
    return Resolution(
        gameweeks=gameweeks,
        n_resamples=n_resamples,
        distinct_resamples=math.comb(2 * gameweeks - 1, gameweeks),
        smallest_step=step,
        monte_carlo_floor=floor,
        threshold_reachable=step <= HOLM_STRICTEST and floor <= HOLM_STRICTEST,
        method=RESOLUTION_METHOD,
    )


def resolution_table(gameweek_counts: Iterable[int], *, n_resamples: int) -> list[Resolution]:
    return [resolution(g, n_resamples=n_resamples) for g in gameweek_counts]


# --- The report ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PowerRow:
    setting: str
    gameweeks: int
    share: float
    power: float | None  # None where the count's verdict procedure is invalid (U5)


@dataclass(frozen=True)
class Report:
    failed_checks: list[str]
    power_table: list[PowerRow] | None
    mde: MdeReading | None
    gameweek_rows: list[GameweekRow]
    needed: list[GameweeksNeeded]
    managers: list[ManagerRow]
    resolution: list[Resolution]
    fake_studies: int
    inner_resamples: int
    rerun_triggers: int


def _refuse_unreportable(results: PowerResults) -> None:
    if results.is_pilot:
        raise ReportRefused("pilot results are never reported (#60 P13)")
    names = [s.name for s in results.settings]
    missing = [s.name for s in SETTINGS if s.name not in names]
    missing += [n for n in names if n not in results.false_alarm_firings]
    missing += [f"{n}|{w:.2f}" for n in names for w in TRUE_WIN_SHARES if (n, w) not in results.power]
    if missing:
        raise ReportRefused(f"partial grid: missing {', '.join(dict.fromkeys(missing))}")


def build_report(results: PowerResults, *, reachable: Mapping[int, bool]) -> Report:
    _refuse_unreportable(results)
    limit = false_alarm_max_firings(results.fake_studies)
    failed = [
        f"false-alarm check failed: {s.name} fired in {results.false_alarm_firings[s.name]} of {results.fake_studies}"
        for s in results.settings
        if results.false_alarm_firings[s.name] > limit
    ]
    sensitivity_failed = not results.sensitivity_power >= SENSITIVITY_MIN_POWER
    if sensitivity_failed:
        failed.append(
            f"sensitivity check failed: power {results.sensitivity_power:.2f} at a true {SENSITIVITY_SHARE:.0%}, "
            f"below {SENSITIVITY_MIN_POWER}"
        )
    rows = mde_by_gameweeks(results, reachable)
    for row in rows:
        problems = check_row(row.label)
        if problems:
            raise AssertionError(f"{row.gameweeks} gameweeks: {problems}")
    valid = {g: _false_alarm_ok(results, _at_count(results, g)) for g in GAMEWEEK_SWEEP}
    table = (
        None
        if sensitivity_failed
        else [
            PowerRow(s.name, s.gameweeks, w, results.power[(s.name, w)] if valid[s.gameweeks] else None)
            for s in results.settings
            for w in TRUE_WIN_SHARES
        ]
    )
    return Report(
        failed_checks=failed,
        power_table=table,
        mde=None if sensitivity_failed else mde_reading(results, reachable),
        gameweek_rows=[] if sensitivity_failed else rows,
        needed=[] if sensitivity_failed else [gameweeks_needed(results, e) for e in (HEADLINE_EDGE, SECONDARY_EDGE)],
        managers=[] if sensitivity_failed else manager_sweep(results),
        resolution=resolution_table(GAMEWEEK_SWEEP, n_resamples=results.inner_resamples),
        fake_studies=results.fake_studies,
        inner_resamples=results.inner_resamples,
        rerun_triggers=sum(results.rerun_triggers.values()),
    )


def _fmt(value: float | str | bool | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return value if isinstance(value, str) else f"{value:.0%}" if value in TRUE_WIN_SHARES else f"{value:.3f}"


def _labels(label: RowLabel) -> str:
    names = [n for n in (label.status, "MDE beyond the sweep" if label.mde_beyond_sweep else None) if n]
    return "; ".join(names) or "none"


def render(report: Report) -> str:
    """The report as Markdown, assumptions first."""
    shock = ", ".join(f"{k} {v}" for k, v in SHOCK_SD_POINTS.items())
    manager = ", ".join(f"{k} {v}" for k, v in MANAGER_EFFECT_SD_POINTS.items())
    lines = [
        "# Stage 5 power simulation lab -- report",
        "",
        "## Assumptions (not measurements)",
        "",
        f"- Gameweek shock sizes, SD of a gameweek's true win share in points: {shock} (assumption).",
        f"- Manager effect sizes, SD of a manager's true win share in points: {manager} (assumption).",
        "- Fake managers: every manager plays every gameweek; bands are equal thirds fixed per manager (assumption).",
        f"- {report.fake_studies:,} fake studies per setting; {report.inner_resamples:,} inner bootstrap repeats; "
        "two-sided p-value (1 + k) / (1 + B), unrounded.",
        f"- False-alarm check (N2): at most {false_alarm_max_firings(report.fake_studies)} family-wise firings "
        f"of {report.fake_studies:,} at a true 50%, at every setting; gated per gameweek count (U5).",
        f"- Sensitivity check: power at least {SENSITIVITY_MIN_POWER} at a true {SENSITIVITY_SHARE:.0%} at the "
        f"{WORST_CASE_CORNER.name} (a judgement).",
        f"- P6's 100,000-repeat re-run is not applied in the lab: {report.rerun_triggers:,} fake studies "
        "would have triggered one.",
        "",
    ]
    if report.failed_checks:
        lines += ["## Failed checks", "", *(f"- {c}" for c in report.failed_checks), ""]
    if report.power_table is None:
        lines += ["No power table: the sensitivity check failed (P11).", ""]
        return "\n".join(lines)
    assert report.mde is not None
    lines += [
        "## MDE at the lowest-power setting (P10)",
        "",
        f"- Setting: {report.mde.setting} ({report.mde.gameweeks} gameweeks); MDE {_fmt(report.mde.label.mde)}; "
        f"labels: {_labels(report.mde.label)}.",
        "",
        "## Gameweeks needed (output a)",
        "",
        *(f"- {n.text}." for n in report.needed),
        "",
        "## MDE per gameweek count (output b), " + CONDITIONAL,
        "",
        "| Gameweeks | Read at | Power at 55% | MDE | Label | 55% detectable | 53% detectable |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| {r.gameweeks} | {r.setting} | {_fmt(r.label.power_at_headline)} | {_fmt(r.label.mde)} | "
            f"{_labels(r.label)} | "
            f"{_fmt(r.label.headline_detectable)} | {_fmt(r.label.secondary_detectable)} |"
            for r in report.gameweek_rows
        ),
        "",
        "## Power against managers, and manager-week rows (outputs c, d)",
        "",
        "| Setting | Managers | Gameweeks | Rows | Power at 55% |",
        "|---|---|---|---|---|",
        *(
            f"| {m.setting} | {m.managers:,} | {m.gameweeks} | {m.rows:,} | {m.power_at_headline:.3f} |"
            for m in report.managers
        ),
        "",
        "## p-value resolution (output e)",
        "",
        f"Method: {RESOLUTION_METHOD}.",
        "",
        "| Gameweeks | Inner repeats | Distinct gameweek resamples | Smallest step | Monte Carlo floor "
        "| 0.0125 reachable |",
        "|---|---|---|---|---|---|",
        *(
            f"| {r.gameweeks} | {r.n_resamples:,} | {r.distinct_resamples:,} | {r.smallest_step:.3g} | "
            f"{r.monte_carlo_floor:.3g} | {'yes' if r.threshold_reachable else 'no'} |"
            for r in report.resolution
        ),
        "",
        "## Power by setting and true win share",
        "",
        "| Setting | Gameweeks | " + " | ".join(f"{w:.0%}" for w in TRUE_WIN_SHARES) + " |",
        "|---|---|" + "---|" * len(TRUE_WIN_SHARES),
    ]
    by_setting: dict[str, list[PowerRow]] = {}
    for row in report.power_table:
        by_setting.setdefault(row.setting, []).append(row)
    for name, rows in by_setting.items():
        cells = " | ".join("invalid" if r.power is None else f"{r.power:.3f}" for r in rows)
        lines.append(f"| {name} | {rows[0].gameweeks} | {cells} |")
    lines += [
        "",
        f"Null share for the false-alarm check: {NULL_SHARE:.0%}; studies per cell: {FAKE_STUDIES:,} pre-registered.",
    ]
    return "\n".join(lines) + "\n"
