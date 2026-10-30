"""Stage 5's real-squad path: the manager's chosen eleven, its scorer, and the feed to the verdict (#69).

`harness.run` scores one ranker per call and keys its scores on (`player_id`, `gw`), so a manager
cannot be a second arm. D2 goes through `harness.run` over the real squads (`real_squads`); the
manager's eleven goes through `score_elevens`, tied to the harness's plain-points rule by test
(D-R3). Neither side has auto-subs or a captain multiplier (#55 decision 9).

**The feed reads `no_subs_xi_points`, never `chosen_xi_points`:** the second includes the harness's
own auto-subs. `verdict.py` reads no points column, so `paired_feed` is the one place that rule can
hold.

**The evaluation panel and rank bands are the caller's input** (D-R6), built by
https://github.com/gisaf22/fpl-intelligence/issues/70. The feed adds no population rule beyond the
Free Hit and Bench Boost exclusion.

**Comparing D2 with a manager on real results waits for the freeze** (#55). Nothing here runs it;
this module only provides the pieces.
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from decisions.starting_xi.harness import _realised_points
from decisions.starting_xi.picks_profile import picked_xi
from decisions.starting_xi.verdict import COLUMNS
from domain.fpl_squad import XI_SIZE

SOURCE_REBUILT: Final = "rebuilt_from_flags"
SOURCE_CAPTURED: Final = "captured_pre_autosub"
ELEVEN_COLUMNS: Final[tuple[str, ...]] = ("entry_id", "gw", "player_id", "source")
#: Chips whose gameweek is not a choice of eleven from the manager's own squad (#55 done-check).
EXCLUDED_CHIPS: Final[frozenset[str]] = frozenset({"freehit", "bboost"})


def squad_id(entry_id: int, gw: int) -> str:
    """The harness's squad id for one manager-week: it holds one `gw` per `squad_id`."""
    return f"{entry_id}:{gw}"


def real_squads(picks: pd.DataFrame) -> pd.DataFrame:
    """The managers' 15s in the harness's squad table shape: `gw`, `squad_id`, `player_id`."""
    ids = [squad_id(int(e), int(g)) for e, g in zip(picks["entry_id"], picks["gw"], strict=True)]
    return pd.DataFrame({"gw": picks["gw"].to_numpy(), "squad_id": ids, "player_id": picks["player_id"].to_numpy()})


def chosen_eleven(picks: pd.DataFrame) -> pd.DataFrame:
    """Each manager-week's chosen eleven, rebuilt from the auto-sub flags, one row per player.

    The flags are outcome data, so only they and `slot` are read (D-R1); the set is
    `picks_profile.picked_xi`. Slot order is not used.

    Raises:
        ValueError: a manager-week that does not rebuild to `XI_SIZE` players, naming it.
    """
    elevens = picked_xi(picks.rename(columns={"player_id": "fpl_id", "gw": "gameweek"}))
    wrong = sorted((int(e), int(g)) for (e, g), xi in elevens.items() if len(xi) != XI_SIZE)
    if wrong:
        raise ValueError(f"{len(wrong)} manager-week(s) do not rebuild to {XI_SIZE} players: {wrong}")
    rows = [(int(e), int(g), int(p), SOURCE_REBUILT) for (e, g), xi in elevens.items() for p in sorted(xi)]
    return pd.DataFrame(rows, columns=list(ELEVEN_COLUMNS))


def captured_pre_autosub_eleven(capture: pd.DataFrame) -> pd.DataFrame:
    """The second backend: `ELEVEN_COLUMNS` from a pre-auto-sub capture, `source` `SOURCE_CAPTURED`.

    The capture's schema belongs to gisaf22/fpl-ingest#128, parked until its own grill.
    """
    raise NotImplementedError("the pre-auto-sub capture has no schema yet: gisaf22/fpl-ingest#128")


def reconcile_sources(rebuilt: pd.DataFrame, captured: pd.DataFrame) -> pd.DataFrame:
    """One chosen-eleven table from two sources (D-R5).

    Where both hold a manager-week they must agree as sets, and the rebuilt rows stand for the
    pair. Where one does, it is used and `source` says which.

    Raises:
        ValueError: the sources disagree on any manager-week, naming each. Neither is preferred.
    """
    keys = ["entry_id", "gw"]
    rebuilt_sets = rebuilt.groupby(keys)["player_id"].agg(frozenset)
    captured_sets = captured.groupby(keys)["player_id"].agg(frozenset)
    both = rebuilt_sets.index.intersection(captured_sets.index)
    differ = sorted((int(e), int(g)) for e, g in both if rebuilt_sets[(e, g)] != captured_sets[(e, g)])
    if differ:
        raise ValueError(f"{len(differ)} manager-week(s) where the chosen-eleven sources disagree: {differ}")
    only_captured = captured.set_index(keys).index.difference(both)
    extra = captured[captured.set_index(keys).index.isin(only_captured)]
    return pd.concat([rebuilt, extra], ignore_index=True).sort_values([*keys, "player_id"], ignore_index=True)


def score_elevens(elevens: pd.DataFrame, gameweek: pd.DataFrame) -> pd.DataFrame:
    """Plain points per manager-week: the eleven's summed gameweek points, null points as 0.

    The same rule as the harness's `no_subs_xi_points`: no auto-subs, no captain multiplier.

    Returns:
        `entry_id`, `gw`, `source`, `points`.

    Raises:
        ValueError: a player absent from the gameweek frame, as `harness.run` does.
    """
    joined = elevens.merge(
        gameweek.loc[:, ["player_id", "gw", "total_points"]],
        on=["player_id", "gw"],
        how="left",
        indicator=True,
        validate="many_to_one",
    )
    absent = joined.loc[joined["_merge"] == "left_only", ["entry_id", "gw", "player_id"]]
    if not absent.empty:
        rows = sorted((int(e), int(g), int(p)) for e, g, p in absent.itertuples(index=False))
        raise ValueError(f"elevens name players absent from the gameweek frame (entry_id, gw, player_id): {rows}")
    joined["points"] = [_realised_points(value) for value in joined["total_points"]]
    return joined.groupby(["entry_id", "gw", "source"], as_index=False)["points"].sum()


def paired_feed(
    rule_weeks: pd.DataFrame, manager_points: pd.DataFrame, chips: pd.DataFrame, panel: pd.DataFrame
) -> pd.DataFrame:
    """`verdict.py`'s table: one row per scored panel manager-week.

    Args:
        rule_weeks: the harness's `squad_weeks` over `real_squads`; only `no_subs_xi_points` is read.
        manager_points: `score_elevens`'s output.
        chips: the manager frames' `gameweeks`: `entry_id`, `gw`, `active_chip`.
        panel: the evaluation panel as `entry_id`, `gw`, `band`, built by the caller.

    Returns:
        `verdict.COLUMNS`. `outcome` is 1 when D2 scores strictly more, 0.5 on a tie, 0 otherwise.

    Raises:
        ValueError: a panel manager-week with no chip row, D2 score or manager score, naming each,
            rather than letting a join shrink the sample.
    """
    keys = ["entry_id", "gw"]
    rows = panel.loc[:, [*keys, "band"]].merge(
        chips.loc[:, [*keys, "active_chip"]], on=keys, how="left", indicator="chip_row", validate="one_to_one"
    )
    rows = rows[~rows["active_chip"].isin(EXCLUDED_CHIPS)].copy()
    rows["squad_id"] = [squad_id(int(e), int(g)) for e, g in zip(rows["entry_id"], rows["gw"], strict=True)]
    rows = rows.merge(
        rule_weeks.loc[:, ["squad_id", "gw", "no_subs_xi_points"]], on=["squad_id", "gw"], how="left", validate="1:1"
    ).merge(manager_points.loc[:, [*keys, "points"]], on=keys, how="left", validate="1:1")

    unscored = (rows["chip_row"] == "left_only") | rows["no_subs_xi_points"].isna() | rows["points"].isna()
    if unscored.any():
        weeks = sorted((int(e), int(g)) for e, g in rows.loc[unscored, keys].itertuples(index=False))
        raise ValueError(f"{len(weeks)} panel manager-week(s) lack a chip row or a score: {weeks}")

    rule, manager = rows["no_subs_xi_points"].to_numpy(dtype=float), rows["points"].to_numpy(dtype=float)
    rows["outcome"] = np.where(rule > manager, 1.0, np.where(rule == manager, 0.5, 0.0))
    rows = rows.rename(columns={"entry_id": "manager_id", "gw": "gameweek"})
    return rows.loc[:, list(COLUMNS)].sort_values(["manager_id", "gameweek"], ignore_index=True)
