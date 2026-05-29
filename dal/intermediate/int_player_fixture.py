"""Player-fixture frame — canonical integrated dataset at (player_id, gw, fixture_id) grain.

Pure transform: accepts StagedEntities, returns one integrated row per (player_id, gw, fixture_id).
No I/O — db_path never enters this module.
"""

from __future__ import annotations

import logging

import pandas as pd

from dal.staging import StagedEntities
from dal.intermediate.int_fixture_context import get_fixture_context
from dal.exceptions import DALContractViolation
from dal.validation import validate_join_safety
from dal.validation.grain import validate_grain_uniqueness

logger = logging.getLogger(__name__)

_XG_RENAME_MAP = {
    "expected_goals": "xg",
    "expected_assists": "xa",
    "expected_goal_involvements": "xgi",
    "expected_goals_conceded": "xgc",
}

_FIXTURE_CONTEXT_COLS = [
    "fixture_id",
    "home_team_id",
    "away_team_id",
    "home_team_difficulty",
    "away_team_difficulty",
    "home_team_name",
    "away_team_name",
    "home_team_strength_overall",
    "home_team_strength_attack",
    "home_team_strength_defence",
    "away_team_strength_overall",
    "away_team_strength_attack",
    "away_team_strength_defence",
]


def get_player_fixture_base(staged: StagedEntities, gw: int | None = None) -> pd.DataFrame:
    """Return one integrated row per (player_id, gw, fixture_id) with fixture and team context."""
    fixtures = get_fixture_context(staged.fixtures, staged.teams)
    result = _join_player_fixture(staged.player_histories, staged.players, staged.element_types, fixtures)
    result = _resolve_player_side_context(result)
    if gw is not None:
        result = result[result["gw"] == gw].reset_index(drop=True)
    validate_grain_uniqueness(result, "player_fixture_base")
    return result


def _join_player_fixture(
    player_histories: pd.DataFrame,
    players: pd.DataFrame,
    positions: pd.DataFrame,
    fixtures: pd.DataFrame,
) -> pd.DataFrame:
    """Join player histories, player attributes, positions, and fixture context into one frame."""
    players_slim = players[["player_id", "player_name", "position_code", "team_id"]]
    positions_slim = positions[["position_code", "position_label"]]
    fixtures_slim = fixtures[_FIXTURE_CONTEXT_COLS]

    result = player_histories.merge(players_slim, on="player_id", how="left")
    validate_join_safety(
        left_n=len(player_histories),
        right_n=len(players_slim),
        result_n=len(result),
        join_type="left",
        description="player histories × players",
    )

    n_before_positions_join = len(result)
    result = result.merge(positions_slim, on="position_code", how="left")
    validate_join_safety(
        left_n=n_before_positions_join,
        right_n=len(positions_slim),
        result_n=len(result),
        join_type="left",
        description="player histories × positions",
    )

    n_before_fixtures_join = len(result)
    result = result.merge(fixtures_slim, on="fixture_id", how="left")
    validate_join_safety(
        left_n=n_before_fixtures_join,
        right_n=len(fixtures_slim),
        result_n=len(result),
        join_type="left",
        description="player histories × fixture context",
    )

    return result.rename(columns=_XG_RENAME_MAP)


def _resolve_player_side_context(df: pd.DataFrame) -> pd.DataFrame:
    """Resolve opponent context, fixture difficulty, and team_id for each player-fixture row.

    Raises DALContractViolation if any rows could not be matched to a fixture, as downstream
    analysis on unresolved rows would produce silently incorrect results.

    opponent_team_id is derived from fixture home/away team data (authoritative) rather than
    relying on the staging pass-through from player_histories.opponent_team. This overrides
    any inconsistency between the FPL API's opponent_team field and the fixture assignments.
    """
    result = df.copy()
    is_home = result["was_home"] == 1
    _resolve_fixture_difficulty(result, is_home)
    _resolve_team_id(result, is_home)
    # Derive from fixture data — authoritative over staging's opponent_team field
    result["opponent_team_id"] = (
        result["away_team_id"].where(is_home, result["home_team_id"]).astype("int64")
    )
    return result.drop(
        columns=["home_team_id", "away_team_id", "home_team_difficulty", "away_team_difficulty"]
    )


def _resolve_fixture_difficulty(df: pd.DataFrame, is_home: pd.Series) -> None:
    """Derive fixture_difficulty from the player's side of the fixture."""
    df["fixture_difficulty"] = (
        df["home_team_difficulty"].where(is_home, df["away_team_difficulty"]).astype("Int64")
    )


def _resolve_team_id(df: pd.DataFrame, is_home: pd.Series) -> None:
    """Correct team_id from fixture data, which is authoritative over the player record.

    The player table may lag for mid-season transfers — fixture home/away assignment
    is the ground truth for which team a player was representing in a given match.
    """
    true_team_id = df["home_team_id"].where(is_home, df["away_team_id"])
    _validate_and_log_team_id_resolution(df, true_team_id)
    df["team_id"] = true_team_id.astype("int64")


def _validate_and_log_team_id_resolution(df: pd.DataFrame, true_team_id: pd.Series) -> None:
    """Raise if any fixture could not be matched; log a summary of team_id corrections.

    Unresolved rows (null true_team_id) indicate a player history record with no corresponding
    fixture — typically a player who left the league mid-season. These cannot be safely used
    downstream, so a DALContractViolation is raised rather than allowing silent fallback.

    For resolved rows where team_id differs from the player record, a structured summary is
    logged: e.g. "team_id corrected for 3 rows across 1 player(s)".
    """
    unresolved_mask = true_team_id.isna()
    if unresolved_mask.any():
        n_rows = int(unresolved_mask.sum())
        fixture_ids = sorted(df.loc[unresolved_mask, "fixture_id"].unique().tolist())
        raise DALContractViolation(
            f"team_id resolution failed for {n_rows} row(s) across fixture_id(s) {fixture_ids}."
            f" These rows have no matching fixture and cannot be used downstream.",

            validation="_resolve_player_side_context",
            n_violations=n_rows,
            error_code="JOIN_SAFETY",
        )

    discrepancy_mask = true_team_id.notna() & (true_team_id != df["team_id"])
    if discrepancy_mask.any():
        n_rows = int(discrepancy_mask.sum())
        n_players = df.loc[discrepancy_mask, "player_name"].nunique()
        logger.info(
            "[AUDIT] team_id corrected for %d row(s) across %d player(s)"
            " — fixture data used over player record (mid-season transfer correction)",
            n_rows,
            n_players,
        )
