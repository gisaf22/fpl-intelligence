"""Stage 3 regret reporting -- CARD.md §3, "Report per rule" (#32).

Reads one run artefact per squad mode, as `results.read` returns it, and lays the modes side by
side. Descriptive only: no table carries a pass/fail verdict.

* **Three regrets per rule.** XI regret (primary), bench-order regret and no-subs regret, each as
  mean, median, P90 and a 95% paired block-bootstrap range. Bench-order regret is 0 where no
  substitution fired, since bench order cannot matter there; it is also reported conditional on a
  substitution firing, without a range.
* **Scale.** XI regret placed on random (0%) -> hindsight ideal (100%). The ideal's regret is 0 by
  definition, so the scale is `1 - rule / random`.
* **Segments.** Position (the harness's `regret_<position>`, summing to XI regret) and phase.
* **Rule agreement.** The mean share of XI picks two rules have in common.
* **Zero-information squad-weeks** are excluded everywhere; the manifest's count is reported.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Final

import pandas as pd

from decisions.starting_xi.uncertainty import gameweek_block_ci
from domain.fpl_squad import POSITIONS, XI_SIZE

# The lens phase scheme from the first scored gameweek (CARD.md §3); edges inclusive.
PHASES: Final[tuple[tuple[str, int, int], ...]] = (("4-12", 4, 12), ("13-26", 13, 26), ("27-38", 27, 38))

RANDOM_RULE: Final[str] = "random"

# Report name -> the per-squad-week column `_with_regrets` derives it into.
REGRETS: Final[Mapping[str, str]] = {
    "xi": "regret",
    "bench_order": "bench_order_regret",
    "no_subs": "no_subs_regret",
}


@dataclass(frozen=True)
class Report:
    """The report's tables, each indexed by `squad_mode` first so the modes sit side by side."""

    rules: pd.DataFrame
    positions: pd.DataFrame
    phases: pd.DataFrame
    agreement: pd.DataFrame
    zero_information: dict[str, int]


def phase_of(gw: int) -> str:
    """The season phase a scored gameweek falls in."""
    for name, first, last in PHASES:
        if first <= gw <= last:
            return name
    raise ValueError(f"gw {gw} is outside every phase {PHASES}; only GW4-38 are scored (CARD.md §3)")


def summarise(values: pd.Series) -> dict[str, Any]:
    """n, mean, median and P90 (linear interpolation). An empty series is reported as empty --
    `n` 0 and no statistics -- rather than as NaN that would propagate into a table."""
    if values.empty:
        return {"n": 0, "mean": None, "median": None, "p90": None}
    return {
        "n": len(values),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p90": float(values.quantile(0.9)),
    }


def scale_position(rule_mean: float, random_mean: float) -> float:
    """A rule's mean XI regret as a percentage of the way from random (0%) to the hindsight ideal
    (100%, regret 0)."""
    if random_mean <= 0:
        raise ValueError(f"random's mean regret is {random_mean}; the scale needs it above the ideal's 0")
    return 100.0 * (1.0 - rule_mean / random_mean)


def paired_ranges(t2: pd.DataFrame, column: str) -> dict[str, tuple[float, float]]:
    """Each rule's 95% block-bootstrap range of `column`'s per-gameweek mean over squads.

    Every rule is resampled with the same seed over the same gameweeks, so `gameweek_block_ci`
    draws the same blocks for each: the ranges are paired. Rules covering different gameweeks
    cannot be paired and raise.
    """
    series = {rule: rows.groupby("gw")[column].mean() for rule, rows in t2.groupby("ranker", sort=True)}
    gameweeks = {tuple(s.index) for s in series.values()}
    if len(gameweeks) > 1:
        raise ValueError(f"rules cover different gameweeks, so their ranges cannot be paired: {sorted(series)}")
    return {rule: gameweek_block_ci(s.to_numpy(dtype=float), n_scoreable_gw=len(s)) for rule, s in series.items()}


def _with_regrets(t2: pd.DataFrame) -> pd.DataFrame:
    frame = t2.copy()
    frame["no_subs_regret"] = frame["best_legal_xi_points"] - frame["no_subs_xi_points"]
    fired = frame["substitution_fired"].astype(bool)
    frame["bench_order_regret"] = (frame["best_permutation_total"] - frame["chosen_xi_points"]).where(fired, 0.0)
    return frame


def _rule_rows(mode: str, t2: pd.DataFrame) -> list[dict[str, Any]]:
    ranges = {name: paired_ranges(t2, column) for name, column in REGRETS.items()}
    xi_means = t2.groupby("ranker")["regret"].mean()
    rows = []
    for rule, rows_for_rule in t2.groupby("ranker", sort=True):
        row: dict[str, Any] = {"squad_mode": mode, "rule": rule, "n": len(rows_for_rule)}
        for name, column in REGRETS.items():
            stats = summarise(rows_for_rule[column])
            row |= {f"{name}_{stat}": stats[stat] for stat in ("mean", "median", "p90")}
            row[f"{name}_ci_lo"], row[f"{name}_ci_hi"] = ranges[name][rule]
        row["xi_scale_pct"] = (
            scale_position(float(xi_means[rule]), float(xi_means[RANDOM_RULE])) if RANDOM_RULE in xi_means else None
        )
        fired = summarise(rows_for_rule.loc[rows_for_rule["substitution_fired"].astype(bool), "bench_order_regret"])
        row |= {f"bench_order_fired_{stat}": value for stat, value in fired.items()}
        rows.append(row)
    return rows


def _position_rows(mode: str, t2: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"squad_mode": mode, "rule": rule, "position": position}
        | summarise(rows_for_rule[f"regret_{position.lower()}"])
        for rule, rows_for_rule in t2.groupby("ranker", sort=True)
        for position in POSITIONS
    ]


def _phase_rows(mode: str, t2: pd.DataFrame) -> list[dict[str, Any]]:
    phase = t2["gw"].map(phase_of)
    return [
        {"squad_mode": mode, "rule": rule, "phase": name}
        | summarise(t2.loc[(t2["ranker"] == rule) & (phase == name), "regret"])
        for rule in sorted(t2["ranker"].unique())
        for name, _, _ in PHASES
    ]


def _agreement_rows(mode: str, t2: pd.DataFrame) -> list[dict[str, Any]]:
    picks = t2.assign(xi=t2["chosen_xi"].map(lambda xi: frozenset(xi.split(","))))
    by_rule = picks.pivot(index=["squad_id", "gw"], columns="ranker", values="xi")
    rows = []
    for rule_a, rule_b in combinations(sorted(by_rule.columns), 2):
        shares = [len(a & b) / XI_SIZE for a, b in zip(by_rule[rule_a], by_rule[rule_b], strict=True)]
        rows.append(
            {"squad_mode": mode, "rule_a": rule_a, "rule_b": rule_b, "share_in_common": sum(shares) / len(shares)}
        )
    return rows


def _table(rows: list[dict[str, Any]], index: Sequence[str]) -> pd.DataFrame:
    # Object dtype keeps an empty segment's None as None rather than coercing it to NaN.
    # A single-rule run has no rule pairs; the empty table still carries its index columns.
    frame = pd.DataFrame(rows, dtype=object) if rows else pd.DataFrame(columns=list(index), dtype=object)
    return frame.set_index(list(index))


def build(artefacts: Sequence[Mapping[str, Any]]) -> Report:
    """The report over one artefact per squad mode, zero-information squad-weeks excluded."""
    rules: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    phases: list[dict[str, Any]] = []
    agreement: list[dict[str, Any]] = []
    zero_information: dict[str, int] = {}
    for artefact in artefacts:
        manifest = artefact["manifest"]
        mode = manifest["identity"]["squad_mode"]
        if mode in zero_information:
            raise ValueError(f"two artefacts share squad_mode {mode!r}; one run per squad mode (CARD.md §3)")
        zero_information[mode] = int(manifest["metadata"]["zero_information_squad_weeks"])

        squad_weeks = artefact["squad_weeks"]
        t2 = _with_regrets(squad_weeks.loc[~squad_weeks["is_zero_information"].astype(bool)])
        rules += _rule_rows(mode, t2)
        positions += _position_rows(mode, t2)
        phases += _phase_rows(mode, t2)
        agreement += _agreement_rows(mode, t2)

    return Report(
        rules=_table(rules, ("squad_mode", "rule")),
        positions=_table(positions, ("squad_mode", "rule", "position")),
        phases=_table(phases, ("squad_mode", "rule", "phase")),
        agreement=_table(agreement, ("squad_mode", "rule_a", "rule_b")),
        zero_information=zero_information,
    )
