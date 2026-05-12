from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def fetch_player_histories_raw(db_path: Path) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT
                element_id,
                round,
                fixture,
                minutes,
                goals_scored,
                assists,
                clean_sheets,
                goals_conceded,
                own_goals,
                penalties_saved,
                penalties_missed,
                yellow_cards,
                red_cards,
                saves,
                bonus,
                bps,
                total_points,
                influence,
                creativity,
                threat,
                ict_index,
                expected_goals,
                expected_assists,
                expected_goal_involvements,
                expected_goals_conceded,
                starts,
                in_dreamteam,
                tackles,
                clearances_blocks_interceptions,
                recoveries,
                defensive_contribution,
                opponent_team,
                was_home,
                kickoff_time,
                team_h_score,
                team_a_score,
                value,
                selected,
                transfers_in,
                transfers_out,
                transfers_balance,
                ingested_at
            FROM player_histories
            """,
            conn,
        )
