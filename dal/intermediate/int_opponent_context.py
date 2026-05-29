"""Opponent defensive context — rolling defensive metrics per opponent at (player_id, gw) grain."""

from __future__ import annotations

import logging

import pandas as pd

from dal.exceptions import DALContractViolation
from dal.validation.grain import validate_grain_uniqueness

logger = logging.getLogger(__name__)


def build_player_opponent_defensive_context(player_fixture_base: pd.DataFrame) -> pd.DataFrame:
    """Return one row per (player_id, gw) with rolling opponent defensive metrics.

    Derives opponent goals conceded and xgc rolling averages (3 and 5 GW windows) with no
    look-ahead. Input must be the player_fixture_base frame from get_player_fixture_base().
    """
    analytics_90 = player_fixture_base[player_fixture_base["minutes"] == 90].copy()
    _validate_contracts(player_fixture_base, analytics_90)
    team_def = _build_team_defensive_records(player_fixture_base, analytics_90)
    opp_stats = _build_opponent_rolling_stats(team_def)
    result = _aggregate_to_player_gw(player_fixture_base, opp_stats)
    validate_grain_uniqueness(result, ["player_id", "gw"], "build_player_opponent_defensive_context")
    return result


def validate_xgc_001(analytics_90: pd.DataFrame) -> None:
    """CONTRACT-XGC-001: xgc must be invariant within 90-minute players per fixture."""
    xgc_var = analytics_90.groupby(["team_id", "gw", "fixture_id"])["xgc"].var(ddof=0)
    violators = xgc_var[xgc_var > 0.001]
    if not violators.empty:
        raise DALContractViolation(
            f"CONTRACT-XGC-001: xgc not invariant within 90-min players for groups: "
            f"{violators.index.tolist()}",

            validation="validate_xgc_001",
            n_violations=len(violators),
            error_code="GRAIN_DUPLICATE",
        )
    logger.debug("[validate_xgc_001] OK across %s groups", len(xgc_var))


def _validate_contracts(analytics: pd.DataFrame, analytics_90: pd.DataFrame) -> None:
    """Run hard contract checks and coverage diagnostics for opponent context inputs."""
    # SC-14 note: validate_xgc_001 supports all positions as a function, but the hard contract
    # check is restricted to GK (position_code==1) because FPL assigns distinct xgc values to
    # different field-player positions within the same fixture — non-GK variance is expected
    # and not an invariant violation.
    validate_xgc_001(analytics_90[analytics_90["position_code"] == 1])

    all_team_gws = set(map(tuple, analytics[["team_id", "gw"]].drop_duplicates().to_numpy()))
    covered = set(map(tuple, analytics_90[["team_id", "gw"]].drop_duplicates().to_numpy()))
    missing = all_team_gws - covered
    if missing:
        logger.warning(
            "[build_player_opponent_defensive_context] CONTRACT-XGC-002: "
            "no 90-minute players for (team_id, gw) groups: %s", sorted(missing)
        )


def _build_team_defensive_records(
    analytics: pd.DataFrame,
    analytics_90: pd.DataFrame,
) -> pd.DataFrame:
    """Build one defensive record per (team_id, gw) with goals conceded and xgc."""
    analytics_90_gk = analytics_90[analytics_90["position_code"] == 1]
    analytics_90_def = analytics_90[analytics_90["position_code"] == 2]

    # sum: goals_conceded is additive across fixtures — a DGW team conceding 1+1 = 2 goals
    team_gc = analytics.groupby(["team_id", "gw"], as_index=False).agg(
        goals_conceded=("goals_conceded", "sum")
    )
    xgc_gk = analytics_90_gk.groupby(["team_id", "gw"], as_index=False).agg(xgc_gk=("xgc", "mean"))
    xgc_def = analytics_90_def.groupby(["team_id", "gw"], as_index=False).agg(xgc_def=("xgc", "mean"))
    xgc_any = analytics_90.groupby(["team_id", "gw"], as_index=False).agg(xgc_any=("xgc", "mean"))

    # Prefer GK xgc → DEF xgc → any 90-min player xgc
    team_xgc = xgc_any.merge(xgc_def, on=["team_id", "gw"], how="left")
    team_xgc = team_xgc.merge(xgc_gk, on=["team_id", "gw"], how="left")
    team_xgc["xgc"] = team_xgc["xgc_gk"].fillna(team_xgc["xgc_def"]).fillna(team_xgc["xgc_any"])

    team_def = team_gc.merge(team_xgc[["team_id", "gw", "xgc"]], on=["team_id", "gw"], how="left")
    logger.debug("[build_team_defensive_records] %s rows", len(team_def))
    return team_def


def _build_opponent_rolling_stats(team_def: pd.DataFrame) -> pd.DataFrame:
    """Compute lag-1 rolling defensive metrics per team — no look-ahead."""
    team_def = team_def.sort_values(["team_id", "gw"]).reset_index(drop=True)

    for metric, col in [("goals_conceded", "opp_gc"), ("xgc", "opp_xgc")]:
        team_def[f"{col}_roll3"] = team_def.groupby("team_id")[metric].transform(
            lambda s: s.shift(1).rolling(3, min_periods=1).mean()
        )
        team_def[f"{col}_roll5"] = team_def.groupby("team_id")[metric].transform(
            lambda s: s.shift(1).rolling(5, min_periods=1).mean()
        )

    return team_def[["team_id", "gw", "opp_gc_roll3", "opp_gc_roll5", "opp_xgc_roll3", "opp_xgc_roll5"]]


def _aggregate_to_player_gw(
    player_fixture_base: pd.DataFrame,
    opp_stats: pd.DataFrame,
) -> pd.DataFrame:
    """Join opponent stats onto player fixtures and aggregate to (player_id, gw) grain."""
    merged = player_fixture_base.merge(
        opp_stats,
        left_on=["opponent_team_id", "gw"],
        right_on=["team_id", "gw"],
        how="left",
    )
    return merged.groupby(["player_id", "gw"], as_index=False).agg(
        opponent_goals_conceded_roll3=("opp_gc_roll3", "max"),
        opponent_goals_conceded_roll5=("opp_gc_roll5", "max"),
        opponent_xgc_roll3=("opp_xgc_roll3", "max"),
        opponent_xgc_roll5=("opp_xgc_roll5", "max"),
        fixture_difficulty_avg=("fixture_difficulty", "mean"),
    )
