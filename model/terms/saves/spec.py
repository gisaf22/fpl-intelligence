"""The saves candidate pool + grain (spec §3).

**One pool, two draws** (mirrors goals). ``minimal`` = ``xgc_roll3 + minutes_roll3`` — the god-file's
GK-saves design: shots faced scale with the expected-goals-conceded a keeper's defence concedes (xGC is
the available shots-faced proxy), and minutes as a covariate. The full pool adds the §3 forward agenda —
a genuine **shots-faced** rate and the upcoming **opponent's attacking volume** — as declared-but-
unmaterialized candidates the *selected* model will regularize over once ``build.py`` builds them.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at player-GW grain, GK only (the population override lives on the model): target = saves that GW.
GRAIN = "player_gw"

_XGC_ROLL3 = FeatureSpec(
    name="xgc_roll3",
    source="xgc",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="xGC (expected goals conceded) proxies shots faced — more shots means more save chances",
    prior="phase2 component model: GK saves ~ xgc_roll3 + minutes_roll3 (Poisson)",
)
_MINUTES_ROLL3 = FeatureSpec(
    name="minutes_roll3",
    source="minutes",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="expected minutes as a covariate (exposure test rejected a proportional offset)",
    prior="phase2 minutes-exposure study",
)

# Declared-but-unmaterialized §3 forward agenda: a true shots-faced rate and opponent attacking volume,
# built later in features/build.py (materialize raises until then).
_SHOTS_FACED_ROLL3 = FeatureSpec(
    name="shots_faced_roll3",
    source="shots_faced",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="a direct shots-faced rate, sharper than the xGC proxy, for the save-volume signal",
    prior="§3 axis 3: fixture-forward defensive exposure",
)
_OPP_SHOTS_FORWARD = FeatureSpec(
    name="opp_shots_forward",
    source="opponent_shots",
    grain="team_gw",
    transform="roll",
    window=5,
    lag_safe=True,
    rationale="the specific upcoming opponent's attacking volume — more opponent shots, more saves to make",
    prior="§3 axis 3: fixture-forward (opponent attacking volume)",
)

SAVES_POOL = FeaturePool(
    name="saves",
    candidates=(_XGC_ROLL3, _MINUTES_ROLL3, _SHOTS_FACED_ROLL3, _OPP_SHOTS_FORWARD),
    minimal=("xgc_roll3", "minutes_roll3"),
)
