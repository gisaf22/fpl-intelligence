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

# Materialized richer process signals — the shipped points model's goals design (GOAL_FEATURES): xG at
# two windows (a sharper leading indicator than the xGI composite) + xGI at roll5. Built lag-safe by
# features.build.add_lagged_rolls in the model's population; drawn by the `selected` model.
_XG_ROLL3 = FeatureSpec(
    name="xg_roll3", source="xg", grain="player_gw", transform="roll", window=3, lag_safe=True,
    rationale="lagged xG (goal threat) at a short window — sharper than the xGI composite",
    prior="phase3 points model GOAL_FEATURES",
)
_XG_ROLL5 = FeatureSpec(
    name="xg_roll5", source="xg", grain="player_gw", transform="roll", window=5, lag_safe=True,
    rationale="lagged xG at a longer window — steadier scoring-rate estimate",
    prior="phase3 points model GOAL_FEATURES",
)
_XGI_ROLL5 = FeatureSpec(
    name="xgi_roll5", source="xgi", grain="player_gw", transform="roll", window=5, lag_safe=True,
    rationale="lagged xGI at a longer window (a mart column) — steadier involvement estimate",
    prior="phase3 points model GOAL_FEATURES",
)

# Fixture difficulty of the specific upcoming opponent — a materialized mart column, known before
# kickoff (the fixture is fixed once the schedule is out), so using it for GW t is NOT leakage: it is
# a known-future feature, unlike a lagged roll. Added to the attacking `selected` design after the
# mean-features step-1 protocol (docs/model-redesign-mean-features-plan.md): walk-forward, the paired
# per-GW Spearman delta pooled over the model's (gw, position) cells is +0.0106, block-bootstrap CI
# [+0.0039, +0.0186] — excludes 0. Level gate (position_bias) unchanged. `was_home` was tested the
# same way and DROPPED (pooled delta -0.0001, CI [-0.0051, +0.0058] — indistinguishable from zero).
_FDR = FeatureSpec(
    name="fdr_avg", source="fdr_avg", grain="player_gw", transform="identity", window=None,
    lag_safe=True, known_future=True,
    rationale="fixture difficulty of the specific upcoming opponent — opponent context the own-form rolls miss",
    prior="families §3: opponent strength; mean-features step-1 (goals pooled Δrho +0.0106, CI [+0.0039, +0.0186])",
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
# NOTE — opp_xgc_forward (the upcoming opponent's rolling conceded-xG, window 5) was the mean-features
# step-2 candidate: a dynamic, defence-side replacement for the static `fdr_avg` tier. It was BUILT
# (features.build.add_opponent_xgc_forward — team-grain roll broadcast on opponent_team_id, coverage-
# filled) and MEASURED walk-forward on the full mart, and is **REFUTED** — it does not beat fdr_avg. It
# is not in the pool (would only cost the opponent join for a worse ranking). Measured, pooled Spearman
# with block-bootstrap CI (docs/model-redesign-mean-features-plan.md step-2):
#   opp_xgc - fdr : goals -0.0126 CI[-0.0206,-0.0031] (SIG-negative — standalone worse than fdr);
#   +fdr+opp ablation: dropping opp_xgc costs ~0 (CI spans 0 — not complementary);
#   absolute rho: base 0.117 → +fdr 0.128 → +opp_xgc 0.115 (ranks BELOW the no-opponent base).
# Keep fdr_avg. The build + dal.pipeline.load_opponent_map remain as tested infra should a minutes-aware
# opponent variant (team_xgc_minutes_aware) ever be revisited.

GOALS_POOL = FeaturePool(
    name="goals",
    candidates=(_XGI_ROLL3, _MINUTES_ROLL3, _XG_ROLL3, _XG_ROLL5, _XGI_ROLL5, _FDR, _TEAM_XG_ROLL3),
    minimal=("xgi_roll3", "minutes_roll3"),
)
