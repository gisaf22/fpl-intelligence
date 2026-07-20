"""The P(play) candidate pool + grain (spec §3, X1 blank-tail).

**One pool, two draws.** ``selected`` = lagged minutes form at two windows + lagged start rate — the
signals that separate a nailed starter from a rotation/injury risk. ``minimal`` = ``minutes_roll3 +
starts_roll3`` (recent minutes + start form), the mechanistic bar. Rotation / availability signals
(days-since-start, fixture congestion) are the §3 forward agenda — declared unmaterialized.

This models **P(play)** = P(minutes>0), the appearance gate *before* the ``minutes`` term's
P(>=60' | played). Its population is the **whole** universe (blanks included) because the target
``played`` needs the 0-minute rows — the one place P(play) differs from every conditional-on-appearance
term (see ``p_play.py`` / ``ASSUMPTIONS.md``).
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at player-GW grain; a per-position logistic (all four positions — GK is a normal starters-vs-backups
# split here, not near-constant like the p60 hurdle, so no override).
GRAIN = "player_gw"


def _minutes_roll(window: int) -> FeatureSpec:
    return FeatureSpec(
        name=f"minutes_roll{window}", source="minutes", grain="player_gw", transform="roll", window=window,
        lag_safe=True, rationale="lagged minutes form — a player getting minutes recently is likely to feature again",
        prior="X1 P(play) blank tail",
    )


_STARTS_ROLL3 = FeatureSpec(
    name="starts_roll3", source="starts", grain="player_gw", transform="roll", window=3,
    lag_safe=True, rationale="lagged start rate — a nailed starter features far more reliably than a rotation risk",
    prior="X1 P(play) blank tail",
)

# Declared-but-unmaterialized §3 forward agenda: rotation / availability signals (the biggest lever on
# P(play) — injuries, suspensions, rotation — but not on the mart yet).
_DAYS_SINCE_START = FeatureSpec(
    name="days_since_start", source="fixture_calendar", grain="player_gw", transform="identity", window=None,
    lag_safe=True, known_future=True,
    rationale="rest since last start — congestion and rotation risk, known from the fixture calendar",
    prior="§3 axis 6: rotation / availability",
)

PLAY_POOL = FeaturePool(
    name="p_play",
    candidates=(_minutes_roll(3), _minutes_roll(5), _STARTS_ROLL3, _DAYS_SINCE_START),
    minimal=("minutes_roll3", "starts_roll3"),
)
