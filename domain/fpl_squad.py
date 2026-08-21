"""FPL squad-construction rules as typed, importable constants.

The scoring rules live in ``domain/fpl_scoring.py``; this module carries the *squad* rules —
the position quota, the per-position XI bounds, the club limit and the budget cap — which the
`starting_xi` decision slice needs and which reach no layer below it today.

Each constant is annotated STAGED, VERIFIED or UNVERIFIED:

- STAGED: FPL declares the value itself and the repository stages it. Sourced from
  ``element_types`` via ``dal/staging/contracts/element_types.yaml`` (``squad_select``,
  ``squad_min_play``, ``squad_max_play``) and guarded against drift by
  ``tests/test_domain_fpl_squad.py``, which reads the staged frame and compares.
- VERIFIED: confirmed against the FPL bootstrap-static API for the stated season.
- UNVERIFIED: the rule is known and is not in dispute, but no endpoint in this repository
  carries it, so nothing here can cross-check it. The value's provenance is stated per constant.

Last reviewed: season 2025/26.

Position vocabulary: these constants are keyed on ``position`` (GK/DEF/MID/FWD), the mart
column ``DESIGN.md`` §8.4 fixes for the slice — *not* on ``position_label`` (GKP/DEF/MID/FWD),
which is what ``element_types`` itself declares. The two differ only at goalkeeper. The drift
test performs the GKP→GK mapping explicitly rather than leaving it implicit here.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

# ---------------------------------------------------------------------------
# Position vocabulary
# ---------------------------------------------------------------------------

# The canonical draw order for a squad. Fixed rather than incidental: the sampler draws each
# position's players in this order from one RNG stream, so the order is part of what makes a
# seeded squad set reproducible.
POSITIONS: Final[tuple[str, ...]] = ("GK", "DEF", "MID", "FWD")

# ---------------------------------------------------------------------------
# Squad composition
# ---------------------------------------------------------------------------

# STAGED 2025/26 — element_types.squad_select. The 2/5/5/3 quota.
SQUAD_SELECT: Final[Mapping[str, int]] = MappingProxyType({"GK": 2, "DEF": 5, "MID": 5, "FWD": 3})

SQUAD_SIZE: Final[int] = 15  # = sum(SQUAD_SELECT.values()); asserted in the drift test.

# ---------------------------------------------------------------------------
# XI bounds — the eight legal formations follow from these
# ---------------------------------------------------------------------------

# STAGED 2025/26 — element_types.squad_min_play / squad_max_play.
XI_MIN_PLAY: Final[Mapping[str, int]] = MappingProxyType({"GK": 1, "DEF": 3, "MID": 2, "FWD": 1})
XI_MAX_PLAY: Final[Mapping[str, int]] = MappingProxyType({"GK": 1, "DEF": 5, "MID": 5, "FWD": 3})

XI_SIZE: Final[int] = 11

# ---------------------------------------------------------------------------
# Club limit and budget
# ---------------------------------------------------------------------------

# UNVERIFIED — FPL's squad rules cap a squad at three players from any one club. The value is
# not staged: `element_types` does not carry it and no other table in this repository does.
# Recorded in decisions/starting_xi/INVENTORY.md §2.2 as one of the four feasibility conditions.
MAX_PER_CLUB: Final[int] = 3

# UNVERIFIED — the initial squad budget, in FPL price units (millions). Not staged for the same
# reason as MAX_PER_CLUB. decisions/starting_xi/INVENTORY.md §2.2 measures the cheapest legal
# 2/5/5/3 at GW1 as 64.0 against this cap, which is the only cross-check available in-repo.
#
# This is the *ceiling only*. There is no floor: DESIGN.md §0.16 draws squads uniformly over the
# feasible set, and a squad costing less than the cap is feasible.
BUDGET_CAP: Final[float] = 100.0

# FPL prices are quoted in tenths (`player_histories.value ÷ 10`), so the budget test is exact in
# integer tenths and only approximate in floats. Consumers comparing a summed squad price against
# the cap should work in tenths rather than round a float sum.
BUDGET_CAP_TENTHS: Final[int] = 1000
