"""The defensive-contribution candidate pool + grain (spec §3).

**One pool, two draws.** ``selected`` = the god-file's five features (``dc_roll3/5`` lagged DC-action
form + minutes + fixture context) — the shipped design the golden test reproduces. ``minimal`` =
``dc_roll3 + minutes_roll3`` (recent DC form + exposure), the mechanistic bar. The lagged DC-action
rolls are **constructed** at build time (they are not raw mart columns); a genuine per-action breakdown
(tackles / CBI / recoveries separately) is the §3 forward agenda, declared unmaterialized.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at player-GW grain, DEF/MID/FWD only, one logistic per position (the fit lives on the model).
GRAIN = "player_gw"


def _dc_roll(window: int) -> FeatureSpec:
    return FeatureSpec(
        name=f"dc_roll{window}", source="defensive_contribution", grain="player_gw", transform="roll",
        window=window, lag_safe=True,
        rationale="lagged DC-action form — a player who racks up tackles/CBI/recoveries keeps doing so",
        prior="phase3 DC component (D-A: DC conditionally independent of CS given minutes)",
    )


_MINUTES_ROLL3 = FeatureSpec(
    name="minutes_roll3", source="minutes", grain="player_gw", transform="roll", window=3,
    lag_safe=True, rationale="expected minutes — more time on pitch, more chances to hit the DC threshold",
    prior="phase2 minutes-exposure study",
)
_FDR = FeatureSpec(
    name="fdr_avg", source="fdr_avg", grain="player_gw", transform="identity", window=None,
    lag_safe=True, known_future=True,
    rationale="fixture difficulty — harder fixtures mean more defensive actions to make",
    prior="families: opponent strength",
)
_WAS_HOME = FeatureSpec(
    name="was_home", source="was_home", grain="player_gw", transform="identity", window=None,
    lag_safe=True, known_future=True, rationale="venue — away sides defend more; known pre-kickoff",
)

# Declared-but-unmaterialized §3 forward agenda: the per-action breakdown behind the composite.
_TACKLES_ROLL3 = FeatureSpec(
    name="tackles_roll3", source="tackles", grain="player_gw", transform="roll", window=3,
    lag_safe=True, rationale="tackles rate alone, sharper than the DC composite for the DEF (CBIT) threshold",
    prior="§3 axis 1: per-action defensive breakdown",
)

DC_POOL = FeaturePool(
    name="defensive_contribution",
    candidates=(_dc_roll(3), _dc_roll(5), _MINUTES_ROLL3, _FDR, _WAS_HOME, _TACKLES_ROLL3),
    minimal=("dc_roll3", "minutes_roll3"),
)
