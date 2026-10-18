"""The Stage 3 rule grid -- CARD.md §3 (#30).

Unfitted rules, one idea each, read from the pinned warehouse frames (DATA.md): D1-D4 by
{season, last 3}, the starts-rate decomposition, and the seeded random XI. Every rule declares
`RULE_WINDOW` and emits NULL wherever it cannot score; the harness ranks unscored players below
scored ones.

**What a rule must not do:** read any row at gameweek >= *t* when scoring *t*, read realised
outcomes for the gameweek being scored, or mutate the frames it is handed -- the same frames go
to every rule. :func:`_assert_lag_safe` enforces the first two on every rule's score column.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

import numpy as np
import pandas as pd

from decisions.starting_xi.seeding import week_seed
from model.eval.baselines import expanding_prior_mean

if TYPE_CHECKING:
    from warehouse import served

_SCORE_COLUMNS: Final[tuple[str, ...]] = ("player_id", "gw", "score")


# ---------------------------------------------------------------------------
# The interface (§6.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RankerOutput:
    """§6.1's panel-producing output: a name, a declared window, and a score panel.

    Structural, not nominal. `harness.py` consumes this shape as a `Protocol` and never imports
    this module (§3.5, §5.1) -- the composition root is the only place the two meet. The class is
    declared here so the ranker side has a concrete type; `test_rankers.py` asserts it satisfies
    the harness's protocol, so the two cannot drift apart unnoticed.

    `scores` carries exactly (`player_id`, `gw`, `score`), one row per player-gameweek the ranker
    covers inside `window`, sorted by (`player_id`, `gw`). Higher `score` = more preferred. A row
    the ranker cannot score is emitted with a **null** `score` rather than a number (§6.5); a row
    the ranker's population never contained is absent, which the harness reads identically.
    """

    name: str
    window: tuple[int, int]
    scores: pd.DataFrame


# ---------------------------------------------------------------------------
# Leakage
# ---------------------------------------------------------------------------


def _assert_lag_safe(rolled: pd.DataFrame, column: str, *, rule: str | None = None) -> None:
    """§6.2's leakage assertion, written against the column actually used.

    The property is the one `model/features/build.py:190` enforces for governed features: a
    strictly-prior column is **NaN on each player's first row**, because that row has no legitimate
    history. Any construction that leaks -- a missing `shift(1)`, a forward window, a window
    bleeding across the player boundary -- is forced to surface a non-null value there.

    `assert_lag_safe` itself is not called: it takes a `FeaturePool`, and this column is not a
    governed feature and must not be given a spec that suggests it is (`archive/INVENTORY.md` §2.1 records
    the mart's exclusion of `points_roll*`). §6.2 asks for an assertion over the columns the ranker
    uses, which is this.
    """
    first_rows = rolled.groupby("player_id", sort=False).head(1)
    if bool(first_rows[column].notna().any()):
        owner = f"rule {rule!r}: " if rule else ""
        raise AssertionError(
            f"leakage: {owner}{column!r} is defined on a player's first population row (DESIGN.md §6.2)"
        )


# ---------------------------------------------------------------------------
# The Stage 3 rule grid (CARD.md §3, #30)
# ---------------------------------------------------------------------------

RULE_WINDOW: Final[tuple[int, int]] = (4, 38)
"""Every rule's declared window: CARD.md §3's scored gameweeks. GW3 is excluded because every
last-3 rule is NULL for everyone there; a rule emits NULL wherever it cannot score."""

LAST_N: Final[int] = 3

RuleFn = Callable[["served.Frames"], RankerOutput]
"""A rule reads the pinned warehouse frames, not the mart."""


def _spine(frames: served.Frames) -> pd.DataFrame:
    """One row per player-gameweek from entry, with that gameweek's outcomes and units.

    Outcomes are the gameweek frame's sums, 0 on a blank. Appearances (fixtures with minutes > 0)
    are counted from the fixture frame, because summed minutes cannot tell one appearance in a
    double from two; gisaf22/fpl-warehouse#215 moves the count onto the gameweek table.
    """
    spine = frames.gameweek.loc[:, ["player_id", "gw", "fixture_count", "total_points", "starts"]].copy()
    fixture = frames.fixture
    appearances = (fixture["minutes"] > 0).groupby([fixture["player_id"], fixture["gw"]]).sum().rename("appearances")
    spine = spine.join(appearances, on=["player_id", "gw"])
    spine = spine.sort_values(["player_id", "gw"], kind="stable").reset_index(drop=True)
    for column in ("total_points", "starts", "appearances"):
        spine[column] = spine[column].fillna(0).astype(float)
    spine["fixture_count"] = spine["fixture_count"].astype(float)
    spine["gameweek"] = 1.0
    return spine


def _season_rate(spine: pd.DataFrame, points: str, unit: str) -> pd.Series:
    """Summed `points` over summed `unit`, across every gameweek before the scored one.

    Points count only in gameweeks holding the unit (a start rate ignores points from a substitute
    appearance). The ratio of two strictly-prior expanding means over the same rows is the ratio of
    their sums; a zero denominator is NULL.
    """
    qualifying = spine[unit] > 0
    numerator = expanding_prior_mean(spine.assign(total_points=spine[points].where(qualifying, 0.0)))
    denominator = expanding_prior_mean(spine.assign(total_points=spine[unit]))
    return (numerator / denominator.where(denominator > 0)).astype(float)


def _last_n_rate(spine: pd.DataFrame, points: str, unit: str) -> pd.Series:
    """Summed `points` over summed `unit`, across the last `LAST_N` past gameweeks holding the unit.

    NULL with fewer than `LAST_N` such gameweeks. The window is summed over qualifying gameweeks
    only, carried forward to every later gameweek, then shifted one row, so the scored gameweek
    never enters its own window.
    """
    qualifying = spine.loc[spine[unit] > 0, ["player_id", points, unit]]
    by_player = qualifying.groupby("player_id", sort=False)
    sums = by_player[[points, unit]].rolling(LAST_N, min_periods=LAST_N).sum().reset_index(level=0, drop=True)
    rate = (sums[points] / sums[unit]).reindex(spine.index)
    carried = rate.groupby(spine["player_id"], sort=False).ffill()
    return carried.groupby(spine["player_id"], sort=False).shift(1).astype(float)


def _rule_panel(name: str, spine: pd.DataFrame, score: pd.Series) -> RankerOutput:
    frame = spine.loc[:, ["player_id", "gw"]].assign(score=score.to_numpy(dtype=float))
    _assert_lag_safe(frame, "score", rule=name)
    first_gw, last_gw = RULE_WINDOW
    frame = frame.loc[(frame["gw"] >= first_gw) & (frame["gw"] <= last_gw)].reset_index(drop=True)
    frame = frame.astype({"player_id": int, "gw": int})
    return RankerOutput(name=name, window=RULE_WINDOW, scores=frame.loc[:, list(_SCORE_COLUMNS)])


def _per_gameweek_rule(name: str, window: str) -> RuleFn:
    """D1: plain points per gameweek elapsed (blanks 0, a double once); the rate, unscaled."""

    def rank(frames: served.Frames) -> RankerOutput:
        spine = _spine(frames)
        rate = (_season_rate if window == "season" else _last_n_rate)(spine, "total_points", "gameweek")
        return _rule_panel(name, spine, rate)

    return rank


def _per_unit_rule(name: str, unit: str, window: str) -> RuleFn:
    """D2-D4: points per team fixture, appearance or start, times the coming gameweek's fixtures."""

    def rank(frames: served.Frames) -> RankerOutput:
        spine = _spine(frames)
        rate = (_season_rate if window == "season" else _last_n_rate)(spine, "total_points", unit)
        return _rule_panel(name, spine, rate * spine["fixture_count"])

    return rank


def _starts_rate_x_points_per_appearance(frames: served.Frames) -> RankerOutput:
    """Starts per team fixture (last 3 gameweeks with a fixture) times season points per appearance,
    times the coming gameweek's fixtures. NULL if either half is."""
    spine = _spine(frames)
    starts_rate = _last_n_rate(spine, "starts", "fixture_count")
    points_per_appearance = _season_rate(spine, "total_points", "appearances")
    return _rule_panel(
        "starts_rate_x_points_per_appearance", spine, starts_rate * points_per_appearance * spine["fixture_count"]
    )


def _random_rule(seed: int) -> RuleFn:
    """A seeded random score per player-gameweek: the random-XI floor.

    Each gameweek draws from its own `week_seed(seed, gw)` stream over its players in `player_id`
    order, so a gameweek's scores do not depend on which other gameweeks are scored. The harness's
    `player_id` tie-break stays deterministic; only the scores are random.
    """

    def rank(frames: served.Frames) -> RankerOutput:
        spine = _spine(frames)
        score = pd.Series(np.nan, index=spine.index)
        for gw, rows in spine.groupby("gw", sort=True):
            rng = np.random.default_rng(week_seed(seed, int(gw)))
            score.loc[rows.index] = rng.random(len(rows))
        first_gw, last_gw = RULE_WINDOW
        frame = spine.loc[:, ["player_id", "gw"]].assign(score=score)
        frame = frame.loc[(frame["gw"] >= first_gw) & (frame["gw"] <= last_gw)].reset_index(drop=True)
        return RankerOutput(name="random", window=RULE_WINDOW, scores=frame.loc[:, list(_SCORE_COLUMNS)])

    return rank


def rules(seed: int) -> Mapping[str, RuleFn]:
    """CARD.md §3's rule grid: D1-D4 by {season, last 3}, the decomposition, and the random XI.

    `seed` is the pre-registration's `master_seed`; only the random rule reads it.
    """
    grid: dict[str, RuleFn] = {}
    for window in ("season", "last3"):
        grid[f"ppg_gameweek_{window}"] = _per_gameweek_rule(f"ppg_gameweek_{window}", window)
    for unit, label in (("fixture_count", "fixture"), ("appearances", "appearance"), ("starts", "start")):
        for window in ("season", "last3"):
            grid[f"ppg_{label}_{window}"] = _per_unit_rule(f"ppg_{label}_{window}", unit, window)
    grid["starts_rate_x_points_per_appearance"] = _starts_rate_x_points_per_appearance
    grid["random"] = _random_rule(seed)
    return MappingProxyType(grid)
