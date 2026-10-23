"""Data profile of the 2026-27 manager picks panel (Stage 5 groundwork, exploration only).

**It describes the panel and scores nothing.** Every function here counts what the captured data
holds: who is in the panel and when, auto-subs, chips, transfers, ranks and two screens reported
as counts. No function takes a rule, a ranker or a points outcome, and none compares a rule's XI
with a manager's. Stage 5's comparison is pre-registered on fpl-intelligence#55 before anything
like it is computed, and this module must stay unable to compute it.

**Inputs.** The served `fct_manager_gameweek` and `fct_manager_pick` (fpl-warehouse), each
manager's `entry_history.overall_rank` read from the raw entry-picks payloads, and each
gameweek's `ranked_count` from one bootstrap-static payload. Standing is `overall_rank` only: the
per-gameweek `rank` ranks one week's points, not a manager's season. Rank is not served yet, which
is why the raw payloads are read at all. `load` reads a local copy; it never reaches S3.

**Import closure: stdlib, numpy, pandas and scipy.** No `dal/`, `model/`, `research/` or `serve/`,
and no sibling slice module.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from scipy import stats

SEASON: Final = "2026-27"
#: The local, git-ignored copy `load` reads (synced by hand with `aws s3 cp`; see the notebook).
DATA_ROOT: Final = Path(__file__).resolve().parents[2] / "data" / "manager_picks"
#: Chips under which a gameweek's transfers are free and unlimited, so its count is not a choice
#: made against the transfer budget.
UNLIMITED_TRANSFER_CHIPS: Final[frozenset[str]] = frozenset({"wildcard", "freehit"})
CHIPS: Final[tuple[str, ...]] = ("3xc", "bboost", "freehit", "wildcard")
#: Transfer counts at and above this are pooled into one bucket.
TRANSFER_BUCKET_CAP: Final = 4
#: Gameweeks the activity screen looks back over.
ACTIVITY_WINDOW: Final = 3
#: Overall-rank cut-offs the rank screen counts at. Counts only: no cut-off is chosen here.
RANK_SCREEN_THRESHOLDS: Final[tuple[int, ...]] = (10_000, 100_000, 1_000_000)
DECILES: Final = 10


@dataclass(frozen=True)
class PicksData:
    """The panel's frames: one row per manager-week, one per pick, one rank per manager-week."""

    gameweeks: pd.DataFrame
    picks: pd.DataFrame
    ranks: pd.DataFrame
    ranked_counts: dict[int, int]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def read_raw_ranks(entry_picks_root: Path) -> pd.DataFrame:
    """`entry_history.overall_rank` per manager-week from raw entry-picks payloads.

    The tree is `{gw}/{entry_id}/{date}/{run_id}/payload.json`, as fpl-ingest writes it. If a
    manager-week was captured more than once, the latest `{date}/{run_id}` wins; both sort in
    capture order. A missing or null `overall_rank` is kept as null, not dropped, so it can be
    counted.
    """
    rows: dict[tuple[int, int], tuple[str, object]] = {}
    for path in entry_picks_root.glob("*/*/*/*/payload.json"):
        gw_part, entry_part, date_part, run_part = path.parts[-5:-1]
        key = (int(gw_part), int(entry_part))
        order = f"{date_part}/{run_part}"
        if key in rows and rows[key][0] >= order:
            continue
        history = json.loads(path.read_text()).get("entry_history") or {}
        rows[key] = (order, history.get("overall_rank"))
    frame = pd.DataFrame(
        [(gw, entry, rank) for (gw, entry), (_, rank) in rows.items()],
        columns=["gameweek", "entry_id", "overall_rank"],
    )
    frame["overall_rank"] = frame["overall_rank"].astype("Int64")
    return frame.sort_values(["gameweek", "entry_id"], ignore_index=True)


def read_ranked_counts(bootstrap_payload: Path) -> dict[int, int]:
    """`ranked_count` per gameweek from one bootstrap-static payload: the teams a gameweek's
    overall ranks are taken over. Gameweeks not yet ranked (count 0) are left out."""
    events = json.loads(bootstrap_payload.read_text())["events"]
    return {int(e["id"]): int(e["ranked_count"]) for e in events if e.get("ranked_count")}


def load(root: Path) -> PicksData:
    """Read the local copy laid out as `served/*.parquet`, `raw/entry-picks/<season>/` and
    `raw/bootstrap-static/payload.json` under `root`, filtered to `SEASON`."""
    gameweeks = pd.read_parquet(root / "served" / "fct_manager_gameweek.parquet")
    picks = pd.read_parquet(root / "served" / "fct_manager_pick.parquet")
    bootstrap = root / "raw" / "bootstrap-static" / "payload.json"
    return PicksData(
        gameweeks=gameweeks[gameweeks["season"] == SEASON].reset_index(drop=True),
        picks=picks[picks["season"] == SEASON].reset_index(drop=True),
        ranks=read_raw_ranks(root / "raw" / "entry-picks" / SEASON),
        ranked_counts=read_ranked_counts(bootstrap),
    )


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def coverage(gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Per gameweek: manager-weeks by cohort, managers new that week, and distinct managers to date.

    A manager-week is one captured `(entry_id, gameweek)`. Its first gameweek is a manager's
    first capture, so a late joiner is new in the week they first have picks.
    """
    by_cohort = gameweeks.groupby(["gameweek", "cohort"]).size().unstack("cohort", fill_value=0)
    first = gameweeks.groupby("entry_id")["gameweek"].min()
    new = first.value_counts().reindex(by_cohort.index, fill_value=0)
    out = by_cohort.add_prefix("manager_weeks_")
    out["manager_weeks"] = by_cohort.sum(axis=1)
    out["new_managers"] = new
    out["managers_to_date"] = new.cumsum()
    return out


def gaps(gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Managers missing a gameweek between their first and last capture: `entry_id`, `missing`."""
    span = gameweeks.groupby("entry_id")["gameweek"].agg(["min", "max", "nunique"])
    holed = span[span["max"] - span["min"] + 1 != span["nunique"]]
    rows = []
    for entry_id, row in holed.iterrows():
        seen = set(gameweeks.loc[gameweeks["entry_id"] == entry_id, "gameweek"])
        rows.append((entry_id, sorted(set(range(row["min"], row["max"] + 1)) - seen)))
    return pd.DataFrame(rows, columns=["entry_id", "missing"])


# ---------------------------------------------------------------------------
# Auto-subs, chips, transfers
# ---------------------------------------------------------------------------


def auto_sub_share(gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Per gameweek: manager-weeks, how many had at least one automatic sub, and that share."""
    had = gameweeks["automatic_subs"].map(len) > 0
    out = had.groupby(gameweeks["gameweek"]).agg(manager_weeks="size", with_auto_sub="sum")
    out["share"] = out["with_auto_sub"] / out["manager_weeks"]
    return out


def chip_share(gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Per gameweek: the share of manager-weeks playing each chip, and the share playing none."""
    chip = gameweeks["active_chip"].fillna("none")
    unknown = set(chip) - set(CHIPS) - {"none"}
    if unknown:
        raise ValueError(f"unknown chips: {sorted(unknown)}")
    counts = pd.crosstab(gameweeks["gameweek"], chip).reindex(columns=[*CHIPS, "none"], fill_value=0)
    return counts.div(counts.sum(axis=1), axis=0)


def transfers_distribution(gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Per gameweek: manager-weeks by transfers made (`0`..`TRANSFER_BUCKET_CAP+`), with weeks
    under a Wildcard or Free Hit counted in their own column rather than a bucket, plus how many
    took a points hit (`event_transfers_cost > 0`)."""
    unlimited = gameweeks["active_chip"].isin(UNLIMITED_TRANSFER_CHIPS)
    capped = gameweeks["event_transfers"].clip(upper=TRANSFER_BUCKET_CAP)
    labels = [str(n) for n in range(TRANSFER_BUCKET_CAP)] + [f"{TRANSFER_BUCKET_CAP}+"]
    bucket = capped.map(dict(enumerate(labels))).where(~unlimited, "wildcard/free hit")
    out = pd.crosstab(gameweeks["gameweek"], bucket).reindex(columns=[*labels, "wildcard/free hit"], fill_value=0)
    out["took_hit"] = (gameweeks["event_transfers_cost"] > 0).groupby(gameweeks["gameweek"]).sum()
    return out


def transfers_summary(gameweeks: pd.DataFrame) -> pd.DataFrame:
    """Per gameweek, over weeks without a Wildcard or Free Hit: mean, median and max transfers,
    and the share making at least one."""
    capped = gameweeks[~gameweeks["active_chip"].isin(UNLIMITED_TRANSFER_CHIPS)]
    grouped = capped.groupby("gameweek")["event_transfers"]
    return pd.DataFrame(
        {
            "manager_weeks": grouped.size(),
            "mean": grouped.mean(),
            "median": grouped.median(),
            "max": grouped.max(),
            "share_any": grouped.apply(lambda s: float((s > 0).mean())),
        }
    )


# ---------------------------------------------------------------------------
# Ranks
# ---------------------------------------------------------------------------


def is_ranked(overall_rank: pd.Series) -> pd.Series:
    """True where `overall_rank` is a rank. FPL reports an unranked team as null or as 0."""
    return overall_rank.fillna(0).astype("int64") >= 1


def unranked(ranks: pd.DataFrame) -> pd.DataFrame:
    """Manager-weeks with no rank: `entry_id`, `gameweek`, and `kind` (`null` or `zero`)."""
    out = ranks[~is_ranked(ranks["overall_rank"])][["entry_id", "gameweek"]].copy()
    out["kind"] = np.where(ranks.loc[out.index, "overall_rank"].isna(), "null", "zero")
    return out.reset_index(drop=True)


def latest_ranks(ranks: pd.DataFrame) -> pd.DataFrame:
    """Each manager's `overall_rank` in their last captured gameweek, with `ranked` False where
    that week is unranked. An older rank is never carried forward: it was taken over a different
    population of teams, so it would not share the latest week's denominator."""
    last = ranks.sort_values(["entry_id", "gameweek"]).groupby("entry_id", as_index=False).last()
    last["ranked"] = is_ranked(last["overall_rank"])
    return last[["entry_id", "gameweek", "overall_rank", "ranked"]]


def rank_deciles(overall_rank: pd.Series, ranked_count: int) -> pd.Series:
    """Rank-percentile decile, 1 = best 10% of `ranked_count` to 10 = worst 10%.

    `ranked_count` is the gameweek's from `read_ranked_counts`, the population its overall ranks
    are taken over, not `total_players`, which also counts teams that are not ranked.

    Decile d holds ranks r with (d-1)/10 < r/N <= d/10, so rank N is decile 10 and rank 1 decile 1.
    A rank outside 1..N is an error rather than a clip: it would mean the two inputs disagree.
    """
    ranks = overall_rank.astype("int64")
    if (ranks < 1).any() or (ranks > ranked_count).any():
        raise ValueError("overall_rank outside 1..ranked_count")
    return pd.Series(np.ceil(ranks * DECILES / ranked_count).astype("int64"), index=overall_rank.index)


@dataclass(frozen=True)
class UniformityTest:
    """Decile counts and the chi-square test of them against a uniform spread."""

    counts: pd.Series
    statistic: float
    dof: int
    p_value: float


def decile_uniformity(deciles: pd.Series) -> UniformityTest:
    """Chi-square goodness of fit of decile counts against equal counts in all ten deciles."""
    counts = deciles.value_counts().reindex(range(1, DECILES + 1), fill_value=0)
    result = stats.chisquare(counts.to_numpy())
    return UniformityTest(
        counts=counts, statistic=float(result.statistic), dof=DECILES - 1, p_value=float(result.pvalue)
    )


def rank_screen_counts(latest: pd.DataFrame, thresholds: Sequence[int] = RANK_SCREEN_THRESHOLDS) -> pd.Series:
    """How many ranked managers' latest overall rank is at or better than each threshold."""
    ranked = latest.loc[latest["ranked"], "overall_rank"]
    return pd.Series({t: int((ranked <= t).sum()) for t in thresholds}, name="managers")


# ---------------------------------------------------------------------------
# Activity screen
# ---------------------------------------------------------------------------


def picked_xi(picks: pd.DataFrame) -> pd.Series:
    """The XI each manager picked, per `(entry_id, gameweek)`, as a frozenset of `fpl_id`.

    `slot` is the lineup *after* automatic substitutions: a player subbed on sits in slots 1-11
    flagged `is_auto_sub_in`, the starter he replaced on the bench flagged `is_auto_sub_out`. The
    picked XI is therefore slots 1-11 without the subs in, plus the subs out.
    """
    in_xi = (picks["slot"] <= 11) & ~picks["is_auto_sub_in"]
    return picks[in_xi | picks["is_auto_sub_out"]].groupby(["entry_id", "gameweek"])["fpl_id"].agg(frozenset)


def activity_screen(gameweeks: pd.DataFrame, picks: pd.DataFrame, last_gw: int) -> pd.DataFrame:
    """Per manager: did they change anything in the `ACTIVITY_WINDOW` gameweeks to `last_gw`?

    A manager passes if, in any window gameweek g, they made a transfer, played a chip, or their
    picked XI (`picked_xi`, before auto-subs) or captain (`is_captain`, which stays with the picked
    captain when the vice takes the armband) differs from g-1's. A manager is
    `evaluable` only with a capture in every gameweek from the one before the window to `last_gw`;
    every flag of one who is not is False. A Free Hit's reversion shows as a changed XI the week
    after, which counts: the screen asks whether anything changed, not why.
    """
    first_gw = last_gw - ACTIVITY_WINDOW + 1
    needed = set(range(first_gw - 1, last_gw + 1))
    window = range(first_gw, last_gw + 1)

    xi = picked_xi(picks)
    captain = picks[picks["is_captain"]].set_index(["entry_id", "gameweek"])["fpl_id"]
    week = gameweeks.set_index(["entry_id", "gameweek"])
    cohort = gameweeks.groupby("entry_id")["cohort"].first()
    seen = gameweeks.groupby("entry_id")["gameweek"].agg(set)

    rows = []
    for entry_id, gws in seen.items():
        flags = dict(changed_xi=False, changed_captain=False, transferred=False, chip=False)
        evaluable = needed <= gws
        if evaluable:
            for g in window:
                flags["changed_xi"] |= xi[(entry_id, g)] != xi[(entry_id, g - 1)]
                flags["changed_captain"] |= captain[(entry_id, g)] != captain[(entry_id, g - 1)]
                flags["transferred"] |= bool(week.at[(entry_id, g), "event_transfers"] > 0)
                flags["chip"] |= pd.notna(week.at[(entry_id, g), "active_chip"])
        rows.append({"entry_id": entry_id, "cohort": cohort[entry_id], "evaluable": evaluable, **flags})
    out = pd.DataFrame(rows)
    out["passes"] = out[["changed_xi", "changed_captain", "transferred", "chip"]].any(axis=1)
    return out


def activity_counts(screen: pd.DataFrame) -> pd.Series:
    """Counts from `activity_screen`: managers, evaluable, each component, and passing."""
    evaluable = screen[screen["evaluable"]]
    return pd.Series(
        {
            "managers": len(screen),
            "evaluable": len(evaluable),
            "changed_xi": int(evaluable["changed_xi"].sum()),
            "changed_captain": int(evaluable["changed_captain"].sum()),
            "transferred": int(evaluable["transferred"].sum()),
            "chip": int(evaluable["chip"].sum()),
            "passes": int(evaluable["passes"].sum()),
            "fails": int((~evaluable["passes"]).sum()),
        },
        name="managers",
    )
