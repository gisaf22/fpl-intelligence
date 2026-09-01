"""Club-schedule-level DGW/BGW gameweek classification -- `DESIGN.md` §2.

A gameweek qualifies for the v1 evaluation set iff no club has a real blank (`fixture_count ==
0`) or a real double (`fixture_count == 2`) that gameweek, checked at `(team_id, gw)` grain among
already-registered players -- not the row-level `is_bgw`/`is_dgw` flags, which are saturated by
the pre-registration prefix (`INVENTORY.md` §1; `decisions/starting_xi/INVENTORY.md` §2.5 first
characterised the same NULL-`minutes` artefact for the sibling slice). Registration mirrors
`decisions.starting_xi.sampler`'s own predicate (first non-null `minutes` row) but is re-derived
here rather than imported, matching this slice's in-slice, self-contained construction
(`DESIGN.md` §3/§4).

Verified directly against the live mart: excludes exactly GW26/31/33/34/36, leaving 33 of 38
gameweeks -- the figure `DESIGN.md` §2 and `INVENTORY.md` §1 cite. `test_gameweek_population.py`
pins this against the live mart as an integration test.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load

_ANOMALOUS_FIXTURE_COUNTS: frozenset[int] = frozenset({0, 2})
"""`fixture_count` values marking a real blank (0) or a real double (2) for a club-gameweek."""


def _registration_gw(mart: pd.DataFrame) -> pd.Series:
    """Per player, the first gameweek carrying a non-null `minutes` row.

    Duplicated from `decisions.starting_xi.sampler._registration_gw` rather than imported -- this
    slice stays self-contained (`DESIGN.md` §3/§4) rather than reaching into a sibling decision
    slice's private internals for a five-line predicate.
    """
    played = mart.loc[mart["minutes"].notna(), ["player_id", "gw"]]
    return played.groupby("player_id")["gw"].min()


def qualifying_gameweeks(mart: pd.DataFrame) -> frozenset[int]:
    """The club-schedule-level non-DGW/non-BGW gameweeks, per `DESIGN.md` §2.

    A gameweek is excluded iff at least one club has `fixture_count == 0` or `fixture_count == 2`
    among its already-registered players that gameweek -- the *whole* calendar gameweek, not just
    that club's rows (`DESIGN.md` §2's stated scope of exclusion). `fixture_count` is asserted
    constant within a `(team_id, gw)` group of registered rows, since it is a schedule fact about
    the team rather than the individual player.

    Raises:
        ValueError: if `fixture_count` disagrees within some `(team_id, gw)` group of registered
            players -- a data-shape violation this classification's central assumption depends on.
    """
    registration_gw = mart["player_id"].map(_registration_gw(mart))
    registered = mart.loc[registration_gw.notna() & (registration_gw <= mart["gw"])]

    per_team_gw = registered.groupby(["team_id", "gw"])["fixture_count"]
    if (per_team_gw.nunique() > 1).any():
        raise ValueError("fixture_count is not constant within a (team_id, gw) group of registered players")
    fixture_count = per_team_gw.first()

    anomalous_gws = fixture_count.loc[fixture_count.isin(_ANOMALOUS_FIXTURE_COUNTS)].index.get_level_values("gw")
    all_gws = {int(gw) for gw in mart["gw"].unique()}
    return frozenset(all_gws - {int(gw) for gw in anomalous_gws})


def load_qualifying_gameweeks(db_path: Path = DB_PATH) -> frozenset[int]:
    """Read the mart via `dal/` and classify its gameweeks (§2).

    The one line of this module that touches the data layer, mirroring
    `decisions.starting_xi.sampler.build_squads`'s split from `sample_squads`.
    """
    return qualifying_gameweeks(load(db_path).mart)
