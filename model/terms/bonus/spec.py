"""The bonus candidate pool + grain (spec §3).

Bonus is a **contemporaneous scoring-map**, so its single input — ``returns_pts``, the FPL point value of
the modelled returns (goals/assists/CS/GK-saves) — is **not lagged**: it is the *same-match* return, known
at composition time from the other terms' expected outputs. It is therefore marked ``known_future`` (a
scoring map, not a leaky lagged feature). D-B established this composite as a strong BPS proxy that a
per-component GLM does not beat (and DC hurts), so the pool is deliberately just this one predictor;
minimal == selected.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at player-GW grain, per position; the "feature" is a same-match composite, not lagged history.
GRAIN = "player_gw"

_RETURNS_PTS = FeatureSpec(
    name="returns_pts",
    source="modelled_returns",
    grain="player_gw",
    transform="identity",
    window=None,
    lag_safe=True,             # not a lagged feature at all; see known_future
    known_future=True,         # contemporaneous scoring map: the SAME-match return, not prior history
    rationale="FPL value of the modelled returns is a strong BPS proxy (D-B: rho 0.50-0.77); GLM/DC don't beat it",
    prior="D-B bonus-proxy study",
)

BONUS_POOL = FeaturePool(
    name="bonus",
    candidates=(_RETURNS_PTS,),
    minimal=("returns_pts",),
)
