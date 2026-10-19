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
* **Paired differences.** Each rule's mean XI regret minus random's and minus the reference
  rule's, with a 95% range from the block bootstrap on the per-gameweek difference series.
* **Outfield only.** XI regret without the GK slot (DEF + MID + FWD), since synthetic squads
  field two playing keepers far more often than real ones.
* **Squad diagnostics** (`diagnose`, which needs the re-drawn squads): how many squad players
  played, how often both keepers did, and which formations the rules and the hindsight ideal use.
* **Zero-information squad-weeks** are excluded everywhere; the manifest's count is reported.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Final

import pandas as pd

from decisions.starting_xi import sampler
from decisions.starting_xi.formations import LEGAL_FORMATIONS, Formation, best_legal_xi
from decisions.starting_xi.uncertainty import gameweek_block_ci
from domain.fpl_squad import POSITION_BY_ID, POSITIONS, XI_SIZE
from warehouse import served

# The lens phase scheme from the first scored gameweek (CARD.md §3); edges inclusive.
PHASES: Final[tuple[tuple[str, int, int], ...]] = (("4-12", 4, 12), ("13-26", 13, 26), ("27-38", 27, 38))

RANDOM_RULE: Final[str] = "random"

# The rule every other is compared with besides random: Stage 4's adopted rule (CARD.md §4).
REFERENCE_RULE: Final[str] = "ppg_fixture_season"

# The squads re-drawn for `diagnose` must be the run's own: the sampler's size per gameweek.
SQUADS_PER_GAMEWEEK: Final[int] = 300

# Report name -> the per-squad-week column `_with_regrets` derives it into.
REGRETS: Final[Mapping[str, str]] = {
    "xi": "regret",
    "bench_order": "bench_order_regret",
    "no_subs": "no_subs_regret",
    "outfield": "outfield_regret",
}


@dataclass(frozen=True)
class Report:
    """The report's tables, each indexed by `squad_mode` first so the modes sit side by side."""

    rules: pd.DataFrame
    differences: pd.DataFrame
    positions: pd.DataFrame
    phases: pd.DataFrame
    agreement: pd.DataFrame
    zero_information: dict[str, int]


@dataclass(frozen=True)
class Diagnostics:
    """What the squads themselves say, indexed by `squad_mode` first.

    `squads`: per mode, squad-weeks, players with minutes > 0 per squad (mean, median), the share
    of squad-weeks with at most 11 such players, and the share where both keepers played.
    `formations`: per mode and picker (each rule, and `hindsight_ideal`), each formation's share
    of squad-weeks -- the chosen XI before substitutions; the ideal's ties go to the first
    maximising formation in `LEGAL_FORMATIONS` order, as the harness breaks them.
    """

    squads: pd.DataFrame
    formations: pd.DataFrame


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


def paired_difference(t2: pd.DataFrame, rule_a: str, rule_b: str) -> dict[str, float]:
    """Mean XI regret of `rule_a` minus `rule_b`, with the 95% block-bootstrap range of the
    per-gameweek difference series. Negative means `rule_a` misses fewer points."""
    per_gw = t2.pivot_table(index="gw", columns="ranker", values="regret", aggfunc="mean")
    series = (per_gw[rule_a] - per_gw[rule_b]).to_numpy(dtype=float)
    lo, hi = gameweek_block_ci(series, n_scoreable_gw=len(series))
    means = t2.groupby("ranker")["regret"].mean()
    return {"mean_diff": float(means[rule_a] - means[rule_b]), "ci_lo": lo, "ci_hi": hi}


def _with_regrets(t2: pd.DataFrame) -> pd.DataFrame:
    frame = t2.copy()
    frame["outfield_regret"] = frame["regret_def"] + frame["regret_mid"] + frame["regret_fwd"]
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


def _difference_rows(mode: str, t2: pd.DataFrame) -> list[dict[str, Any]]:
    rules = sorted(t2["ranker"].unique())
    return [
        {"squad_mode": mode, "rule": rule, "versus": versus} | paired_difference(t2, rule, versus)
        for versus in (RANDOM_RULE, REFERENCE_RULE)
        if versus in rules
        for rule in rules
        if rule != versus
    ]


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
    return frame.set_index(list(index)).sort_index()


def build(artefacts: Sequence[Mapping[str, Any]]) -> Report:
    """The report over one artefact per squad mode, zero-information squad-weeks excluded."""
    rules: list[dict[str, Any]] = []
    differences: list[dict[str, Any]] = []
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
        differences += _difference_rows(mode, t2)
        positions += _position_rows(mode, t2)
        phases += _phase_rows(mode, t2)
        agreement += _agreement_rows(mode, t2)

    return Report(
        rules=_table(rules, ("squad_mode", "rule")),
        differences=_table(differences, ("squad_mode", "versus", "rule")),
        positions=_table(positions, ("squad_mode", "rule", "position")),
        phases=_table(phases, ("squad_mode", "rule", "phase")),
        agreement=_table(agreement, ("squad_mode", "rule_a", "rule_b")),
        zero_information=zero_information,
    )


# ---------------------------------------------------------------------------
# Squad diagnostics -- these need the squads, which the artefact does not store
# ---------------------------------------------------------------------------


def formation_name(counts: Formation) -> str:
    """DEF-MID-FWD, e.g. "4-4-2"; the GK count is always 1."""
    return "-".join(str(count) for count in counts[1:])


def ideal_formation(positions: Sequence[str], points: Sequence[float]) -> Formation:
    """The hindsight-best XI's formation: the first maximiser in `LEGAL_FORMATIONS` order, as the
    harness breaks ties. Checked against `best_legal_xi`'s total so the two cannot drift apart."""
    by_position = {
        position: sorted((pts for pos, pts in zip(positions, points, strict=True) if pos == position), reverse=True)
        for position in POSITIONS
    }
    totals = [
        sum(sum(by_position[position][:count]) for position, count in zip(POSITIONS, formation, strict=True))
        for formation in LEGAL_FORMATIONS
    ]
    best = max(totals)
    expected = best_legal_xi(positions, points).best_legal_xi_points
    if abs(best - expected) > 1e-9:
        raise ValueError(f"ideal formation total {best} disagrees with best_legal_xi's {expected}")
    return LEGAL_FORMATIONS[totals.index(best)]


def squad_facts(frames: served.Frames, artefact: Mapping[str, Any]) -> pd.DataFrame:
    """The run's squads, re-drawn from its manifest, with each player's position, points and
    whether he played that gameweek: one row per (squad_id, gw, player_id).

    Raises if the re-drawn squads are not the run's (a different `squad_set_id`)."""
    identity = artefact["manifest"]["identity"]
    sample = sampler.sample_squads(
        frames,
        identity["build_gameweeks"],
        SQUADS_PER_GAMEWEEK,
        identity["master_seed"],
        squad_mode=identity["squad_mode"],
    )
    if sample.squad_set_id != identity["squad_set_id"]:
        raise ValueError(f"re-drawn squads {sample.squad_set_id} are not the run's {identity['squad_set_id']}")
    gameweek = frames.gameweek
    facts = pd.DataFrame(
        {
            "player_id": gameweek["player_id"],
            "gw": gameweek["gw"],
            "position": gameweek["position_id"].map(lambda p: POSITION_BY_ID[int(p)] if pd.notna(p) else None),
            "points": gameweek["total_points"].fillna(0.0).astype(float),
            "played": gameweek["minutes"].fillna(0) > 0,
        }
    )
    squads = sample.squads[["squad_id", "gw", "player_id"]]
    return squads.merge(facts, on=["player_id", "gw"], how="left", validate="many_to_one")


def _squad_row(mode: str, squads: pd.DataFrame) -> dict[str, Any]:
    played = squads.groupby(["squad_id", "gw"])["played"].sum()
    keepers = squads.loc[squads["position"] == "GK"].groupby(["squad_id", "gw"])["played"].sum()
    return {
        "squad_mode": mode,
        "squad_weeks": len(played),
        "played_mean": float(played.mean()),
        "played_median": float(played.median()),
        "share_played_at_most_11": float((played <= XI_SIZE).mean()),
        "share_both_keepers_played": float((keepers.reindex(played.index, fill_value=0) == 2).mean()),
    }


def _formation_rows(mode: str, t2: pd.DataFrame, squads: pd.DataFrame) -> list[dict[str, Any]]:
    position_of = squads.drop_duplicates(["player_id", "gw"]).set_index(["player_id", "gw"])["position"]
    picks = t2.assign(player_id=t2["chosen_xi"].str.split(",")).explode("player_id")
    picks["player_id"] = picks["player_id"].astype(int)
    picks["position"] = position_of.reindex(pd.MultiIndex.from_frame(picks[["player_id", "gw"]])).to_numpy()
    chosen = picks.groupby(["ranker", "squad_id", "gw"])["position"].agg(
        lambda xi: formation_name(tuple(int((xi == position).sum()) for position in POSITIONS))
    )
    ideal = squads.groupby(["squad_id", "gw"]).apply(
        lambda squad: formation_name(ideal_formation(list(squad["position"]), list(squad["points"]))),
        include_groups=False,
    )
    shares = pd.concat(
        [
            chosen.groupby("ranker").value_counts(normalize=True),
            pd.concat({"hindsight_ideal": ideal.value_counts(normalize=True)}),
        ]
    )
    return [
        {"squad_mode": mode, "picker": picker, "formation": formation, "share": float(share)}
        for (picker, formation), share in shares.items()
    ]


def diagnose(runs: Sequence[tuple[Mapping[str, Any], pd.DataFrame]]) -> Diagnostics:
    """Squad diagnostics over (artefact, `squad_facts`) per squad mode, zero-information
    squad-weeks excluded."""
    squads_rows: list[dict[str, Any]] = []
    formations: list[dict[str, Any]] = []
    for artefact, facts in runs:
        mode = artefact["manifest"]["identity"]["squad_mode"]
        squad_weeks = artefact["squad_weeks"]
        t2 = squad_weeks.loc[~squad_weeks["is_zero_information"].astype(bool)]
        kept = facts.merge(t2[["squad_id", "gw"]].drop_duplicates(), on=["squad_id", "gw"])
        squads_rows.append(_squad_row(mode, kept))
        formations += _formation_rows(mode, t2, kept)
    return Diagnostics(
        squads=_table(squads_rows, ("squad_mode",)),
        formations=_table(formations, ("squad_mode", "picker", "formation")),
    )
