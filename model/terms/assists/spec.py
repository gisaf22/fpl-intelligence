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

# Materialized richer process signals — the shipped points model's assists design (ASSIST_FEATURES): xA
# at two windows (assist threat, sharper than the xGI composite) + xGI at roll5. Built lag-safe by
# features.build.add_lagged_rolls in the model's population; drawn by the `selected` model.
_XA_ROLL3 = FeatureSpec(
    name="xa_roll3", source="xa", grain="player_gw", transform="roll", window=3, lag_safe=True,
    rationale="lagged xA (chance creation) at a short window — sharper than the xGI composite",
    prior="phase3 points model ASSIST_FEATURES",
)
_XA_ROLL5 = FeatureSpec(
    name="xa_roll5", source="xa", grain="player_gw", transform="roll", window=5, lag_safe=True,
    rationale="lagged xA at a longer window — steadier creation-rate estimate",
    prior="phase3 points model ASSIST_FEATURES",
)
_XGI_ROLL5 = FeatureSpec(
    name="xgi_roll5", source="xgi", grain="player_gw", transform="roll", window=5, lag_safe=True,
    rationale="lagged xGI at a longer window (a mart column) — steadier involvement estimate",
    prior="phase3 points model ASSIST_FEATURES",
)

# Fixture difficulty of the specific upcoming opponent — a materialized mart column, known before
# kickoff, so using it for GW t is NOT leakage (a known-future feature, unlike a lagged roll). Added
# to the assists `selected` design after the mean-features step-1 protocol
# (docs/model-redesign-mean-features-plan.md): walk-forward, the paired per-GW Spearman delta pooled
# over the model's (gw, position) cells is +0.0151, block-bootstrap CI [+0.0010, +0.0296] — excludes 0
# (every position's point estimate is positive; DEF +0.021, FWD +0.021 reproduce the scoping measurement).
# Level gate (position_bias) unchanged. `was_home` was tested the same way and DROPPED (pooled delta
# -0.0070, CI [-0.0225, +0.0057] — indistinguishable from zero).
_FDR = FeatureSpec(
    name="fdr_avg", source="fdr_avg", grain="player_gw", transform="identity", window=None,
    lag_safe=True, known_future=True,
    rationale="fixture difficulty of the specific upcoming opponent — more assists to go round vs a weak defence",
    prior="families §3: opponent strength; mean-features step-1 (assists pooled Δrho +0.0151, CI [+0.0010, +0.0296])",
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
# NOTE — opp_xgc_forward (mean-features step-2, the dynamic defence-side replacement for `fdr_avg`) was
# built and measured for assists too, and is **REFUTED**: opp_xgc - fdr = -0.0183, block-bootstrap
# CI[-0.0351,-0.0032] (SIG-negative), and absolute rho falls from +fdr 0.107 to +opp_xgc 0.089 (below the
# no-opponent base 0.092). Not in the pool; fdr_avg kept. See goals/spec.py and
# docs/model-redesign-mean-features-plan.md step-2.

ASSISTS_POOL = FeaturePool(
    name="assists",
    candidates=(_XGI_ROLL3, _MINUTES_ROLL3, _XA_ROLL3, _XA_ROLL5, _XGI_ROLL5, _FDR, _CREATIVITY_ROLL3,
                _TEAM_XG_ROLL3),
    minimal=("xgi_roll3", "minutes_roll3"),
)
