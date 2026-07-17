"""The team-goals-against candidate pool + grain (spec §3).

**One pool, two draws — siblings** (locked decision B). Both the ``minimal`` and ``selected`` models are
Poisson GLMs at **team_gw** grain on the same pool:

* ``minimal`` = ``ga_roll3`` only — the mechanistic bar (a team concedes like it has been conceding) and
  the fast smoke-test.
* ``selected`` = regularized over the full pool (lagged GA + xGC at two windows, venue, fixture
  difficulty) — the shipped model.

The old **player-Binomial** clean-sheet model (Phase-2.1 ``clean_sheets ~ …``) is deliberately **not** a
pool draw — it is a different grain and family, kept only as an external legacy comparator in the
notebook.

``team_xgc`` today is the mean per-player xGC over appeared players — **minutes-entangled** (see
``ASSUMPTIONS.md``). A proper minutes-aware team xGC is declared below as an **unmaterialized** candidate
(``build.materialize`` raises until it exists); building it is a separate ``features/build.py`` step, not
this migration.
"""

from __future__ import annotations

from model.features.spec import FeaturePool, FeatureSpec

# Fit at the team-fixture grain: one row per (team_id, gw), target = team goals-against that GW.
GRAIN = "team_gw"


def _ga(window: int) -> FeatureSpec:
    return FeatureSpec(
        name=f"ga_roll{window}", source="team_ga", grain="team_gw", transform="roll", window=window,
        lag_safe=True, rationale="lagged team goals-against — a team concedes like its recent form",
        prior="phase3 team-GA layer (D-D)",
    )


def _xgc(window: int) -> FeatureSpec:
    return FeatureSpec(
        name=f"xgc_roll{window}", source="team_xgc", grain="team_gw", transform="roll", window=window,
        lag_safe=True, rationale="lagged team xGC — expected goals conceded regresses to a truer rate than GA",
        prior="phase3 team-GA layer",
    )


# was_home + fdr_avg are known before kickoff (the upcoming fixture), so legitimate predictors.
_WAS_HOME = FeatureSpec(
    name="was_home", source="was_home", grain="team_gw", transform="identity", window=None,
    lag_safe=True, known_future=True, rationale="home teams concede less; venue is known pre-kickoff",
)
_FDR = FeatureSpec(
    name="fdr_avg", source="fdr_avg", grain="team_gw", transform="identity", window=None,
    lag_safe=True, known_future=True, rationale="fixture difficulty of the specific upcoming opponent",
    prior="families: opponent strength",
)

# Declared-but-unmaterialized §3 forward agenda: a minutes-aware team xGC construction the selected
# model will regularize over once features/build.py builds it (materialize raises until then).
_TEAM_XGC_MINUTES_AWARE = FeatureSpec(
    name="team_xgc_minutes_aware", source="xgc", grain="team_gw", transform="roll", window=3,
    lag_safe=True, rationale="team xGC weighted by minutes, decoupling exposure from the mean-over-appeared proxy",
    prior="§3 axis 5: team defensive context (minutes-aware aggregation)",
)

TEAM_GA_POOL = FeaturePool(
    name="team_goals_against",
    candidates=(_ga(3), _ga(5), _xgc(3), _xgc(5), _WAS_HOME, _FDR, _TEAM_XGC_MINUTES_AWARE),
    minimal=("ga_roll3",),
)
