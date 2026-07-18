"""The minutes-hurdle candidate pool + grain (spec §3).

**One pool, two draws.** ``selected`` = the god-file's four features (lagged minutes at three windows +
lagged starts) — the shipped design the golden test reproduces. ``minimal`` = ``minutes_roll3 +
starts_roll3`` (recent minutes + start form), the mechanistic bar. Rotation/availability signals
(days-since-start, fixture congestion) are the §3 forward agenda — declared unmaterialized.

This models P(>=60' | played); P(play) itself — the 0-minute blank tail — is X1, deferred (the biggest
missing tail for a full distribution), not part of this term.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at player-GW grain; outfield by a per-position logistic, GK by a robust rate (the model handles it).
GRAIN = "player_gw"


def _minutes_roll(window: int) -> FeatureSpec:
    return FeatureSpec(
        name=f"minutes_roll{window}", source="minutes", grain="player_gw", transform="roll", window=window,
        lag_safe=True, rationale="lagged minutes form — recent playing time predicts a full appearance",
        prior="phase3 minutes hurdle",
    )


_STARTS_ROLL3 = FeatureSpec(
    name="starts_roll3", source="starts", grain="player_gw", transform="roll", window=3,
    lag_safe=True, rationale="lagged start rate — a nailed starter clears 60' far more often than a rotation risk",
    prior="phase3 minutes hurdle",
)

# Declared-but-unmaterialized §3 forward agenda: rotation / availability signals.
_DAYS_SINCE_START = FeatureSpec(
    name="days_since_start", source="fixture_calendar", grain="player_gw", transform="identity", window=None,
    lag_safe=True, known_future=True,
    rationale="rest since last start — congestion and rotation risk, known from the fixture calendar",
    prior="§3 axis 6: rotation / availability",
)

MINUTES_POOL = FeaturePool(
    name="minutes",
    candidates=(_minutes_roll(3), _minutes_roll(5), _minutes_roll(8), _STARTS_ROLL3, _DAYS_SINCE_START),
    minimal=("minutes_roll3", "starts_roll3"),
)
