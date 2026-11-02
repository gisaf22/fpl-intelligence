"""Stage 5's evaluation panel and rank bands: the population and `band` the paired feed takes.

Built from the pinned manager frames, https://github.com/gisaf22/fpl-intelligence/issues/70. The
rules are decisions 2, 3, 4, 5, 10, 12 and 15 on
https://github.com/gisaf22/fpl-intelligence/issues/55.

**The panel:** a manager-week is in it if the manager is not in an excluded cohort and either has a
tenure of three gameweeks or less or passes `picks_profile.activity_screen`. The screen is reused,
not copied. Only gameweeks in `rankers.RULE_WINDOW` have a row: D2 has no eleven before it, and
`manager_comparison.paired_feed` raises on a panel week without a D2 score. Free Hit and Bench Boost
weeks stay here and are dropped by the feed, the one place that exclusion lives.

**The band** reads the end of the previous gameweek, so a week's own outcome cannot move it: r is
that gameweek's `overall_rank` and N its `ranked_count`, cut in integer arithmetic into thirds of
all ranked teams, with a rank on a boundary in the better band. No valid rank means a null band and
the manager stays in the panel.

**No points are read here,** and nothing here compares D2 with a manager.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from decisions.starting_xi.picks_profile import activity_screen, is_ranked
from decisions.starting_xi.rankers import RULE_WINDOW
from decisions.starting_xi.verdict import BANDS

#: Cohorts that are never in the panel: the self cohort is not a baseline (decision 4).
EXCLUDED_COHORTS: Final[frozenset[str]] = frozenset({"self"})
#: Gameweeks between the scored gameweek and the rank its band reads. Same-week would leak the outcome.
RANK_LAG_GAMEWEEKS: Final = 1
#: The bands are this many equal shares of all ranked teams.
BAND_COUNT: Final = len(BANDS)
#: Where a rank exactly on a cut goes. It selects the comparison in `_AT_OR_ABOVE_CUT`.
BOUNDARY_RANK_GOES_TO: Final = "better_band"
#: The band of a real previous gameweek with a null or 0 rank (decision 3). A first capture is a
#: separate case: it has no previous gameweek and is always null.
NULL_OR_ZERO_RANK_BAND: Final[str | None] = None
_AT_OR_ABOVE_CUT: Final = {"better_band": np.less_equal}
KEYS: Final[list[str]] = ["entry_id", "gw"]
#: One row per scored manager-week.
WEEK_COLUMNS: Final[tuple[str, ...]] = ("entry_id", "gw", "cohort", "tenure", "screened", "in_panel", "band")
#: What `manager_comparison.paired_feed` takes as `panel`.
PANEL_COLUMNS: Final[tuple[str, ...]] = ("entry_id", "gw", "band")


def _named(weeks: pd.DataFrame) -> list[tuple[int, int]]:
    return sorted((int(e), int(g)) for e, g in weeks[KEYS].itertuples(index=False))


def rank_bands(weeks: pd.DataFrame, gameweeks: pd.DataFrame, ranked_counts: pd.DataFrame) -> pd.DataFrame:
    """Each manager-week's rank band, from the previous gameweek's rank and ranked count.

    Args:
        weeks: the captured manager-weeks, `entry_id`, `gw`. A manager's earliest is their first
            capture, the one week with no previous gameweek to read.
        gameweeks: `entry_id`, `gw`, `overall_rank`.
        ranked_counts: `gw`, `ranked_count`.

    Returns:
        `entry_id`, `gw`, `band`: a label of `verdict.BANDS`, or null for a first capture or a null
        or 0 previous rank. The rank check comes first, so `ranked_count` is read only for a real
        rank.

    Raises:
        ValueError: naming the manager-weeks, when `gameweeks` lacks a row a week needs (a missing
            row is never a null rank), when a rank is greater than `ranked_count`, or when
            `ranked_count` is null or missing for a real rank.
    """
    bands = weeks[KEYS].reset_index(drop=True)
    has_previous = bands["gw"] > bands.groupby("entry_id")["gw"].transform("min")
    previous_weeks = bands.loc[has_previous, KEYS].assign(gw=lambda f: f["gw"] - RANK_LAG_GAMEWEEKS)
    needed = pd.concat([bands, previous_weeks]).drop_duplicates()
    absent = needed.merge(gameweeks[KEYS], on=KEYS, how="left", indicator=True)
    absent = absent[absent["_merge"] == "left_only"]
    if not absent.empty:
        raise ValueError(f"no fct_manager_gameweek row for manager-week(s): {_named(absent)}")

    previous_rank = gameweeks[[*KEYS, "overall_rank"]].assign(gw=lambda f: f["gw"] + RANK_LAG_GAMEWEEKS)
    previous = bands[has_previous].merge(previous_rank, on=KEYS, validate="one_to_one")
    valid_rank = is_ranked(previous["overall_rank"])
    previous_count = ranked_counts[["gw", "ranked_count"]].assign(gw=lambda f: f["gw"] + RANK_LAG_GAMEWEEKS)
    ranked = previous[valid_rank].merge(previous_count, on="gw", how="left", validate="many_to_one")

    unknown = ranked[ranked["ranked_count"].isna()]
    if not unknown.empty:
        raise ValueError(f"null or missing ranked_count for a real rank at manager-week(s): {_named(unknown)}")
    over = ranked[ranked["overall_rank"] > ranked["ranked_count"]]
    if not over.empty:
        raise ValueError(f"previous rank greater than ranked_count at manager-week(s): {_named(over)}")

    rank = ranked["overall_rank"].to_numpy(dtype="int64")
    count = ranked["ranked_count"].to_numpy(dtype="int64")
    top, middle, bottom = BANDS
    at_or_above_cut = _AT_OR_ABOVE_CUT[BOUNDARY_RANK_GOES_TO]
    in_top = at_or_above_cut(BAND_COUNT * rank, count)
    in_middle = at_or_above_cut(BAND_COUNT * rank, 2 * count)
    ranked["band"] = np.select([in_top, in_middle], [top, middle], default=bottom)
    no_rank = previous.loc[~valid_rank, KEYS].assign(band=NULL_OR_ZERO_RANK_BAND)
    assigned = pd.concat([ranked[[*KEYS, "band"]].astype({"band": object}), no_rank.astype({"band": object})])
    return bands.merge(assigned, on=KEYS, how="left", validate="one_to_one")


def manager_weeks(picks: pd.DataFrame, gameweeks: pd.DataFrame, ranked_counts: pd.DataFrame) -> pd.DataFrame:
    """One row per scored manager-week with its panel membership and band, `WEEK_COLUMNS`.

    The inputs are `warehouse.served.ManagerFrames`' three frames, whose loader has refused a hole
    in any manager's history. `screened` False is the exempt group: a tenure of three or less.
    """
    weeks = picks[KEYS].drop_duplicates()
    first_gw, last_gw = RULE_WINDOW
    scored = sorted(int(g) for g in weeks["gw"].unique() if first_gw <= g <= last_gw)
    screen_picks = picks.rename(columns={"player_id": "fpl_id", "gw": "gameweek"})
    screen_gameweeks = gameweeks.rename(columns={"gw": "gameweek"})
    screens = [activity_screen(screen_gameweeks, screen_picks, g).assign(gw=g) for g in scored]
    out = pd.concat(screens, ignore_index=True)
    out["in_panel"] = out["passes"] & ~out["cohort"].isin(EXCLUDED_COHORTS)
    out = out.merge(rank_bands(weeks, gameweeks, ranked_counts), on=KEYS, how="left", validate="one_to_one")
    return out.loc[:, list(WEEK_COLUMNS)].sort_values(KEYS, ignore_index=True)


def evaluation_panel(weeks: pd.DataFrame) -> pd.DataFrame:
    """The panel manager-weeks of `manager_weeks`, as `manager_comparison.paired_feed` takes them."""
    return weeks.loc[weeks["in_panel"], list(PANEL_COLUMNS)].reset_index(drop=True)
