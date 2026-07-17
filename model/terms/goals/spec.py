"""The goals candidate pool + grain (spec §3).

**One pool, two draws.** ``GOALS_POOL.minimal`` is the mechanistic bar carried over verbatim from
the god-file — ``xgi_roll3`` (leading indicator) + ``minutes_roll3`` (exposure as a covariate, not an
offset) — a Poisson GLM that is both the fast smoke-test *and* the comparison bar the shipped model
must beat. The full pool adds the §3 forward agenda (opponent-forward, team context) as declared but
not-yet-materialized candidates the *selected* model will regularize over once ``build.py`` opens
those axes. Until then the selected model draws the same columns as minimal, so the frozen composed
numbers are untouched.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# The model is fit at player-GW grain: one row per player per gameweek, target = goals that GW.
GRAIN = "player_gw"

# The mechanistic bar (materialized mart columns today; both are lag-safe — verified to exclude the
# current GW). These two ARE the minimal model and the god-file's goals design.
_XGI_ROLL3 = FeatureSpec(
    name="xgi_roll3",
    source="xgi",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="xG+xA regresses to a truer scoring rate than noisy realized goals (xG>goals, all positions)",
    prior="phase2 design check: lagged xG beats lagged goals at DEF/MID/FWD",
)
_MINUTES_ROLL3 = FeatureSpec(
    name="minutes_roll3",
    source="minutes",
    grain="player_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="expected minutes as a covariate (exposure test rejected a proportional offset for DEF/FWD)",
    prior="phase2 minutes-exposure study",
)

# Declared-but-not-yet-materialized §3 forward agenda: candidates the selected model will regularize
# over once features/build.py opens the aggregation / opponent-forward axes. Listed here so the pool
# reads as the plan of record; build.materialize raises until they exist, so they are not yet drawn.
_TEAM_XG_ROLL3 = FeatureSpec(
    name="team_xg_roll3",
    source="team_xg",
    grain="team_gw",
    transform="roll",
    window=3,
    lag_safe=True,
    rationale="team attacking context (opportunity) — a team-grain feature broadcast to its players",
    prior="families §3 axis 5: team attacking context",
)
_OPP_XGC_FORWARD = FeatureSpec(
    name="opp_xgc_forward",
    source="opponent_xgc",
    grain="team_gw",
    transform="roll",
    window=5,
    lag_safe=True,
    known_future=False,
    rationale="the specific upcoming opponent's conceded xG — fixture-forward difficulty beyond fdr_avg",
    prior="families §3 axis 3: fixture-forward",
)

GOALS_POOL = FeaturePool(
    name="goals",
    candidates=(_XGI_ROLL3, _MINUTES_ROLL3, _TEAM_XG_ROLL3, _OPP_XGC_FORWARD),
    minimal=("xgi_roll3", "minutes_roll3"),
)
