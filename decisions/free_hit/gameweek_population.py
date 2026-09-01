"""The v1 evaluation gameweek set, on the two independent exclusion axes `METRIC.md` §3 names.

`METRIC.md` §3.3 states plainly that the warm-up question is "a second, independent exclusion axis
layered on top of §3.2's DGW/BGW question (both narrow the same 38-gameweek universe, for
unrelated reasons)". This module keeps them as two functions for that reason, rather than one
predicate conflating them:

* `schedule_clean_gameweeks` -- §3.2's axis, the club-schedule-level DGW/BGW classification
  (`DESIGN.md` §2).
* `qualifying_gameweeks` -- what the evaluation actually runs over: §3.2's axis minus §3.3's
  warm-up exclusion.

**§3.2's axis.** A gameweek is schedule-clean iff no club has a real blank (`fixture_count == 0`)
or a real double (`fixture_count == 2`) that gameweek, checked at `(team_id, gw)` grain among
already-registered players -- not the row-level `is_bgw`/`is_dgw` flags, which are saturated by
the pre-registration prefix (`INVENTORY.md` §1; `decisions/starting_xi/INVENTORY.md` §2.5 first
characterised the same NULL-`minutes` artefact for the sibling slice). Registration mirrors
`decisions.starting_xi.sampler`'s own predicate (first non-null `minutes` row) but is re-derived
here rather than imported, matching this slice's in-slice, self-contained construction
(`DESIGN.md` §3/§4).

Verified directly against the live mart: excludes exactly GW26/31/33/34/36, leaving 33 of 38
gameweeks -- the figure `DESIGN.md` §2 and `INVENTORY.md` §1 cite.

**§3.3's axis.** GW1 is then dropped as a measured degeneracy, not a precaution -- see
`WARM_UP_EXCLUDED` for the measurement and `METRIC.md` §3.3's appended resolution for the
reasoning. 32 gameweeks remain. `test_gameweek_population_integration.py` pins both axes against
the live mart.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dal.config import DB_PATH
from dal.pipeline import load

_ANOMALOUS_FIXTURE_COUNTS: frozenset[int] = frozenset({0, 2})
"""`fixture_count` values marking a real blank (0) or a real double (2) for a club-gameweek."""

WARM_UP_EXCLUDED: frozenset[int] = frozenset({1})
"""`METRIC.md` §3.3's warm-up exclusion, measured against the live mart rather than assumed.

Every as-of signal the three baselines rank on is derived `shift(1)`-lagged (`candidates.py`), so
at GW1 there is no prior row and **all 690 candidates carry NaN on all three signals**. The greedy
fill treats NaN as unrankable and falls back to its ascending-`player_id` tie-break
(`candidates._sort_key`), so C1, C2 and C3 return the *identical* 15-player squad -- verified
directly. Two consequences, both of which make GW1 unusable rather than merely weak:

* Every pairwise `ConstructionRegret_{C,B}(1)` in `METRIC.md` §1.3 is **exactly zero with zero
  variance, by construction and not by outcome**. A paired bootstrap over the gameweek panel
  (§3.1) resamples that observation as though it carried information; it does not, and including
  it shrinks §2's intervals toward a difference the design never had the power to observe.
* For §2's eventual candidate-vs-baseline tests, GW1's "baseline" is a squad chosen by ascending
  player id. That is not the naive baseline `DECISION.md` §4 defines, so a GW1 observation would
  not measure the comparison §2's verdict rule claims to make.

Excluding it moves the three mean ConstructionRegret figures from +7.97 / +4.94 / -3.03 to
+8.22 / +5.09 / -3.13 (C1-C2, C1-C3, C2-C3 respectively).

**GW2-GW4 are deliberately *not* excluded here, though they carry a narrower, measured
degeneracy.** `candidates.RECENT_FORM_WINDOW` is 3, so C3's `shift(1).rolling(3, min_periods=1)`
window spans the same prior gameweeks as C1's `shift(1).expanding()` until the season is more than
four gameweeks old: `recent_form_ppg == season_ppg` for every candidate at GW2, GW3 and GW4
(705/705, 712/712, 740/740 verified), diverging first at GW5 (382/741). C1 and C3 therefore return
identical squads and a guaranteed-zero `ConstructionRegret_{C1,C3}` across those three weeks. That
is a *pair-scoped* defect -- those gameweeks remain fully informative for C1-vs-C2 and C2-vs-C3,
and for any future candidate-vs-baseline test they make the C1 and C3 comparisons redundant rather
than uninformative. Dropping three weeks of real signal for two of three pairs to repair one pair
is not the trade this exclusion is for, so it is recorded in `METRIC.md` §3.3 as a constraint on
reading the C1-vs-C3 series rather than applied to the population."""


def _registration_gw(mart: pd.DataFrame) -> pd.Series:
    """Per player, the first gameweek carrying a non-null `minutes` row.

    Duplicated from `decisions.starting_xi.sampler._registration_gw` rather than imported -- this
    slice stays self-contained (`DESIGN.md` §3/§4) rather than reaching into a sibling decision
    slice's private internals for a five-line predicate.
    """
    played = mart.loc[mart["minutes"].notna(), ["player_id", "gw"]]
    return played.groupby("player_id")["gw"].min()


def schedule_clean_gameweeks(mart: pd.DataFrame) -> frozenset[int]:
    """The club-schedule-level non-DGW/non-BGW gameweeks, per `DESIGN.md` §2 / `METRIC.md` §3.2.

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


def qualifying_gameweeks(mart: pd.DataFrame) -> frozenset[int]:
    """The set the evaluation runs over: `schedule_clean_gameweeks` minus `WARM_UP_EXCLUDED`.

    Both of `METRIC.md` §3's exclusion axes, composed. Kept separate from the §3.2 classifier it
    wraps because the two axes answer unrelated questions and are pinned by separate tests -- a
    change to either must fail visibly on its own.
    """
    return schedule_clean_gameweeks(mart) - WARM_UP_EXCLUDED


def load_qualifying_gameweeks(db_path: Path = DB_PATH) -> frozenset[int]:
    """Read the mart via `dal/` and classify its gameweeks (§2).

    The one line of this module that touches the data layer, mirroring
    `decisions.starting_xi.sampler.build_squads`'s split from `sample_squads`.
    """
    return qualifying_gameweeks(load(db_path).mart)
