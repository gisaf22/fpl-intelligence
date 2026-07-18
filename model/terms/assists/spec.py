"""The assists candidate pool + grain (spec §3).

**One pool, two draws** (mirrors goals). ``minimal`` = ``xgi_roll3 + minutes_roll3`` — the god-file's
assists design (xGI carries the creative signal; minutes as a covariate, not an offset). The full pool
adds the §3 forward agenda for assists — **creativity / key-pass** process stats and team attacking
context — as declared-but-unmaterialized candidates the *selected* model will regularize over once
``build.py`` opens those axes. Until then selected draws the same columns as minimal, so the frozen
composed numbers are untouched.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at player-GW grain: one row per player per gameweek, target = assists that GW.
GRAIN = "player_gw"

# The mechanistic bar — the god-file's assists design (both lag-safe mart columns).
_XGI_ROLL3 = FeatureSpec(
    name="xgi_roll3",
    source="xgi",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="xGI (xG+xA) carries the creative signal; regresses to a truer rate than realized assists",
    prior="phase2 component model: goals/assists ~ xgi_roll3 + minutes_roll3 (Poisson)",
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

# Declared-but-unmaterialized §3 forward agenda for assists: creative process stats and team context the
# selected model will regularize over once features/build.py builds them (materialize raises until then).
_CREATIVITY_ROLL3 = FeatureSpec(
    name="creativity_roll3",
    source="creativity",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="chance-creation signal specific to assists, beyond the xGI composite",
    prior="families §3 axis 1: assist-specific creation (key passes / creativity)",
)
_TEAM_XG_ROLL3 = FeatureSpec(
    name="team_xg_roll3",
    source="team_xg",
    grain="team_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="team attacking context — more team goals means more assists to go round (team-grain broadcast)",
    prior="families §3 axis 5: team attacking context",
)

ASSISTS_POOL = FeaturePool(
    name="assists",
    candidates=(_XGI_ROLL3, _MINUTES_ROLL3, _CREATIVITY_ROLL3, _TEAM_XG_ROLL3),
    minimal=("xgi_roll3", "minutes_roll3"),
)
