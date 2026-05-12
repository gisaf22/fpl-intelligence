"""Create the golden test fixture database for Wave 1-6 stabilization tests.

Run directly to (re)create tests/fixtures/test.db:
    python tests/fixtures/create_test_db.py

The DB is fully deterministic — running twice produces the same file.

Scenario design:
    Teams:   T1=1, T2=2, T3=3, T4=4
    Players: P1=101 (GK, always T1), P2=102 (GK, always T2), P3=103 (MID, T1→T2)
    GWs:     1–5

    GW1: F1  T1 home vs T2 away
    GW2: F2  T1 home vs T3 away  |  F3  T2 home vs T4 away
    GW3: F4  T2 home vs T3 away        T1 has NO fixture → BGW for P1, P3
    GW4: F5  T1 home vs T2 away  |  F6  T2 home vs T4 away  → DGW for T2 (P2)
    GW5: F7  T1 home vs T3 away  |  F8  T2 home vs T4 away

SC-2 (BGW team_id):
    P3 plays for T1 in GW1–2, has BGW in GW3 (T1 has no fixture), then transfers to T2 for GW4–5.
    players.team for P3 = 2 (T2, current snapshot — post-transfer).
    Correct BGW GW3 team_id for P3 = 1 (T1, last team before BGW).
    Bug: current code uses latest players.team = T2 for all BGW rows.

SC-3 (goals_conceded mean vs sum):
    P2 (GK at T2) plays both DGW fixtures in GW4.
    T2 concedes 1 goal in F5 and 1 goal in F6 → total = 2.
    Bug: current code uses mean → returns 1 instead of 2.

DGW fixture difficulties:
    F5: T2 away difficulty = 3
    F6: T2 home difficulty = 4
    fdr_avg for P2 in GW4 = 3.5, fdr_min = 3, fdr_max = 4

SC-1 (minutes_trend look-ahead):
    P1 plays 90 min in GW1–2, BGW GW3, then 90 min GW4–5.
    Separate unit test uses synthetic data; golden DB used for golden-value assertions.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "test.db"


def create_test_db(path: Path = DB_PATH) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        _create_schema(conn)
        _insert_element_types(conn)
        _insert_teams(conn)
        _insert_players(conn)
        _insert_fixtures(conn)
        _insert_events(conn)
        _insert_player_histories(conn)
        conn.commit()
    finally:
        conn.close()


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE element_types (
        id INTEGER NOT NULL,
        singular_name TEXT NOT NULL,
        singular_name_short TEXT NOT NULL,
        plural_name TEXT NOT NULL,
        plural_name_short TEXT NOT NULL,
        squad_select INTEGER NOT NULL,
        squad_min_play INTEGER NOT NULL,
        squad_max_play INTEGER NOT NULL,
        element_count INTEGER NOT NULL
    );

    CREATE TABLE teams (
        id INTEGER NOT NULL,
        name TEXT NOT NULL,
        short_name TEXT NOT NULL,
        code INTEGER NOT NULL,
        strength INTEGER NOT NULL,
        strength_overall_home INTEGER NOT NULL,
        strength_overall_away INTEGER NOT NULL,
        strength_attack_home INTEGER NOT NULL,
        strength_attack_away INTEGER NOT NULL,
        strength_defence_home INTEGER NOT NULL,
        strength_defence_away INTEGER NOT NULL,
        played INTEGER NOT NULL DEFAULT 0,
        win INTEGER NOT NULL DEFAULT 0,
        draw INTEGER NOT NULL DEFAULT 0,
        loss INTEGER NOT NULL DEFAULT 0,
        points INTEGER NOT NULL DEFAULT 0,
        position INTEGER NOT NULL,
        unavailable INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE players (
        id INTEGER NOT NULL,
        first_name TEXT NOT NULL,
        second_name TEXT NOT NULL,
        web_name TEXT NOT NULL,
        code INTEGER NOT NULL,
        team INTEGER NOT NULL,
        element_type INTEGER NOT NULL,
        now_cost INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'a',
        total_points INTEGER NOT NULL DEFAULT 0,
        event_points INTEGER NOT NULL DEFAULT 0,
        minutes INTEGER NOT NULL DEFAULT 0,
        goals_scored INTEGER NOT NULL DEFAULT 0,
        assists INTEGER NOT NULL DEFAULT 0,
        clean_sheets INTEGER NOT NULL DEFAULT 0,
        goals_conceded INTEGER NOT NULL DEFAULT 0,
        own_goals INTEGER NOT NULL DEFAULT 0,
        penalties_saved INTEGER NOT NULL DEFAULT 0,
        penalties_missed INTEGER NOT NULL DEFAULT 0,
        yellow_cards INTEGER NOT NULL DEFAULT 0,
        red_cards INTEGER NOT NULL DEFAULT 0,
        saves INTEGER NOT NULL DEFAULT 0,
        bonus INTEGER NOT NULL DEFAULT 0,
        bps INTEGER NOT NULL DEFAULT 0,
        starts INTEGER NOT NULL DEFAULT 0,
        influence REAL NOT NULL DEFAULT 0.0,
        creativity REAL NOT NULL DEFAULT 0.0,
        threat REAL NOT NULL DEFAULT 0.0,
        ict_index REAL NOT NULL DEFAULT 0.0,
        expected_goals REAL NOT NULL DEFAULT 0.0,
        expected_assists REAL NOT NULL DEFAULT 0.0,
        expected_goal_involvements REAL NOT NULL DEFAULT 0.0,
        expected_goals_conceded REAL NOT NULL DEFAULT 0.0,
        form REAL NOT NULL DEFAULT 0.0,
        points_per_game REAL NOT NULL DEFAULT 0.0,
        selected_by_percent REAL NOT NULL DEFAULT 0.0,
        transfers_in INTEGER NOT NULL DEFAULT 0,
        transfers_out INTEGER NOT NULL DEFAULT 0,
        transfers_in_event INTEGER NOT NULL DEFAULT 0,
        transfers_out_event INTEGER NOT NULL DEFAULT 0,
        cost_change_event INTEGER NOT NULL DEFAULT 0,
        cost_change_start INTEGER NOT NULL DEFAULT 0,
        chance_of_playing_next_round INTEGER,
        chance_of_playing_this_round INTEGER,
        news TEXT,
        team_join_date TEXT
    );

    CREATE TABLE fixtures (
        id INTEGER NOT NULL,
        code INTEGER NOT NULL,
        event INTEGER,
        team_h INTEGER NOT NULL,
        team_a INTEGER NOT NULL,
        team_h_score INTEGER,
        team_a_score INTEGER,
        team_h_difficulty INTEGER NOT NULL,
        team_a_difficulty INTEGER NOT NULL,
        kickoff_time TEXT,
        minutes INTEGER NOT NULL DEFAULT 90,
        started INTEGER,
        finished INTEGER NOT NULL DEFAULT 1,
        finished_provisional INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE events (
        id INTEGER NOT NULL,
        name TEXT NOT NULL,
        deadline_time TEXT NOT NULL,
        deadline_time_epoch INTEGER NOT NULL,
        finished INTEGER NOT NULL DEFAULT 0,
        data_checked INTEGER NOT NULL DEFAULT 0,
        is_previous INTEGER NOT NULL DEFAULT 0,
        is_current INTEGER NOT NULL DEFAULT 0,
        is_next INTEGER NOT NULL DEFAULT 0,
        average_entry_score INTEGER,
        highest_score INTEGER,
        transfers_made INTEGER NOT NULL DEFAULT 0,
        most_selected INTEGER,
        most_transferred_in INTEGER,
        most_captained INTEGER,
        most_vice_captained INTEGER,
        top_element INTEGER,
        top_element_points INTEGER
    );

    CREATE TABLE player_histories (
        element_id INTEGER NOT NULL,
        round INTEGER NOT NULL,
        fixture INTEGER NOT NULL,
        minutes INTEGER NOT NULL DEFAULT 0,
        goals_scored INTEGER NOT NULL DEFAULT 0,
        assists INTEGER NOT NULL DEFAULT 0,
        clean_sheets INTEGER NOT NULL DEFAULT 0,
        goals_conceded INTEGER NOT NULL DEFAULT 0,
        own_goals INTEGER NOT NULL DEFAULT 0,
        penalties_saved INTEGER NOT NULL DEFAULT 0,
        penalties_missed INTEGER NOT NULL DEFAULT 0,
        yellow_cards INTEGER NOT NULL DEFAULT 0,
        red_cards INTEGER NOT NULL DEFAULT 0,
        saves INTEGER NOT NULL DEFAULT 0,
        bonus INTEGER NOT NULL DEFAULT 0,
        bps INTEGER NOT NULL DEFAULT 0,
        total_points INTEGER NOT NULL DEFAULT 0,
        influence REAL NOT NULL DEFAULT 0.0,
        creativity REAL NOT NULL DEFAULT 0.0,
        threat REAL NOT NULL DEFAULT 0.0,
        ict_index REAL NOT NULL DEFAULT 0.0,
        expected_goals REAL NOT NULL DEFAULT 0.0,
        expected_assists REAL NOT NULL DEFAULT 0.0,
        expected_goal_involvements REAL NOT NULL DEFAULT 0.0,
        expected_goals_conceded REAL NOT NULL DEFAULT 0.0,
        starts INTEGER NOT NULL DEFAULT 0,
        in_dreamteam INTEGER NOT NULL DEFAULT 0,
        opponent_team INTEGER NOT NULL,
        was_home INTEGER NOT NULL,
        kickoff_time TEXT NOT NULL,
        team_h_score INTEGER,
        team_a_score INTEGER,
        value INTEGER NOT NULL,
        selected INTEGER NOT NULL DEFAULT 0,
        transfers_in INTEGER NOT NULL DEFAULT 0,
        transfers_out INTEGER NOT NULL DEFAULT 0,
        transfers_balance INTEGER NOT NULL DEFAULT 0
    );
    """)


def _insert_element_types(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO element_types VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, "Goalkeeper", "GKP", "Goalkeepers", "GKPs", 2, 1, 1, 100),
            (2, "Defender",   "DEF", "Defenders",   "DEFs", 5, 3, 5, 200),
            (3, "Midfielder", "MID", "Midfielders",  "MIDs", 5, 2, 5, 250),
            (4, "Forward",    "FWD", "Forwards",     "FWDs", 3, 1, 3, 120),
        ],
    )


def _insert_teams(conn: sqlite3.Connection) -> None:
    # id, name, short_name, code, strength, str_ov_h, str_ov_a, str_att_h, str_att_a,
    # str_def_h, str_def_a, played, win, draw, loss, points, position, unavailable
    conn.executemany(
        "INSERT INTO teams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "Team Alpha",   "ALP", 101, 4, 1250, 1200, 1300, 1250, 1200, 1150, 0,0,0,0,0, 1, 0),
            (2, "Team Beta",    "BET", 102, 3, 1150, 1100, 1200, 1150, 1100, 1050, 0,0,0,0,0, 2, 0),
            (3, "Team Gamma",   "GAM", 103, 2, 1050, 1000, 1100, 1050, 1000,  950, 0,0,0,0,0, 3, 0),
            (4, "Team Delta",   "DEL", 104, 1,  950,  900, 1000,  950,  900,  850, 0,0,0,0,0, 4, 0),
        ],
    )


def _insert_players(conn: sqlite3.Connection) -> None:
    # Only columns used by staging are critical. All others get safe defaults.
    # id, first_name, second_name, web_name, code, team, element_type, now_cost, ...
    # P1=101: GK at T1 (always T1)
    # P2=102: GK at T2 (always T2, DGW player)
    # P3=103: MID currently at T2 (was at T1 in GW1-2, transferred to T2 by GW4)
    conn.executemany(
        """INSERT INTO players (id, first_name, second_name, web_name, code,
           team, element_type, now_cost, status)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [
            (101, "Alpha", "Keeper",   "A.Keeper",   1001, 1, 1, 55, "a"),
            (102, "Beta",  "Stopper",  "B.Stopper",  1002, 2, 1, 65, "a"),
            (103, "Gamma", "Runner",   "G.Runner",   1003, 2, 3, 75, "a"),
        ],
    )


def _insert_fixtures(conn: sqlite3.Connection) -> None:
    # id, code, event(gw), team_h, team_a, team_h_score, team_a_score,
    # team_h_difficulty, team_a_difficulty, kickoff_time, minutes, started, finished, finished_provisional
    conn.executemany(
        """INSERT INTO fixtures
           (id, code, event, team_h, team_a, team_h_score, team_a_score,
            team_h_difficulty, team_a_difficulty, kickoff_time, minutes, started, finished, finished_provisional)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            # GW1: T1 home vs T2 away.  T1 wins 2-0.
            (1, 1001, 1, 1, 2,  2, 0,  3, 3,  "2025-08-16T12:30:00Z", 90, 1, 1, 1),
            # GW2: T1 home vs T3 away.  Draw 1-1.
            (2, 1002, 2, 1, 3,  1, 1,  2, 4,  "2025-08-23T12:30:00Z", 90, 1, 1, 1),
            # GW2: T2 home vs T4 away.  T2 wins 1-0.
            (3, 1003, 2, 2, 4,  1, 0,  3, 3,  "2025-08-23T15:00:00Z", 90, 1, 1, 1),
            # GW3: T2 home vs T3 away.  T2 wins 2-1.  T1 has NO GW3 fixture → BGW for P1, P3.
            (4, 1004, 3, 2, 3,  2, 1,  3, 3,  "2025-08-30T12:30:00Z", 90, 1, 1, 1),
            # GW4: T1 home vs T2 away.  T1 wins 1-0.  T2 concedes 1.  DGW fixture 1 for T2.
            (5, 1005, 4, 1, 2,  1, 0,  3, 3,  "2025-09-13T12:30:00Z", 90, 1, 1, 1),
            # GW4: T2 home vs T4 away.  T4 scores 1.  T2 concedes 1.  DGW fixture 2 for T2. diff=4.
            (6, 1006, 4, 2, 4,  0, 1,  4, 3,  "2025-09-13T15:00:00Z", 90, 1, 1, 1),
            # GW5: T1 home vs T3 away.  T1 wins 2-0.
            (7, 1007, 5, 1, 3,  2, 0,  2, 3,  "2025-09-20T12:30:00Z", 90, 1, 1, 1),
            # GW5: T2 home vs T4 away.  T2 wins 3-0.
            (8, 1008, 5, 2, 4,  3, 0,  3, 3,  "2025-09-20T15:00:00Z", 90, 1, 1, 1),
        ],
    )


def _insert_events(conn: sqlite3.Connection) -> None:
    # id(gw), name, deadline_time, deadline_time_epoch, finished, data_checked,
    # is_previous, is_current(is_live), is_next, average_entry_score, highest_score,
    # transfers_made, most_selected, most_transferred_in, most_captained, most_vice_captained,
    # top_element, top_element_points
    conn.executemany(
        """INSERT INTO events
           (id, name, deadline_time, deadline_time_epoch, finished, data_checked,
            is_previous, is_current, is_next, average_entry_score, highest_score,
            transfers_made, most_selected, most_transferred_in, most_captained,
            most_vice_captained, top_element, top_element_points)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (1, "Gameweek 1", "2025-08-15T18:00:00Z", 1755025200, 1, 1, 0, 0, 0,  52, 120, 500000, 101, 102, 101, 102, 101, 14),
            (2, "Gameweek 2", "2025-08-22T18:00:00Z", 1755630000, 1, 1, 0, 0, 0,  54, 130, 520000, 101, 102, 101, 102, 101, 12),
            (3, "Gameweek 3", "2025-08-29T18:00:00Z", 1756234800, 1, 1, 1, 0, 0,  50, 115, 480000, 102, 103, 102, 101, 102, 10),
            (4, "Gameweek 4", "2025-09-12T18:00:00Z", 1757239200, 1, 1, 0, 1, 0,  56, 140, 550000, 102, 103, 102, 101, 102, 16),
            (5, "Gameweek 5", "2025-09-19T18:00:00Z", 1757844000, 0, 0, 0, 0, 1, None, None,       0, None, None, None, None, None, None),
        ],
    )


def _insert_player_histories(conn: sqlite3.Connection) -> None:
    # element_id, round(gw), fixture, minutes, goals_scored, assists, clean_sheets, goals_conceded,
    # own_goals, penalties_saved, penalties_missed, yellow_cards, red_cards, saves, bonus, bps,
    # total_points, influence, creativity, threat, ict_index, expected_goals, expected_assists,
    # expected_goal_involvements, expected_goals_conceded, starts, in_dreamteam,
    # opponent_team, was_home, kickoff_time, team_h_score, team_a_score, value, selected,
    # transfers_in, transfers_out, transfers_balance

    rows = [
        # --- P1 (GK, T1, always home side in T1 fixtures) ---
        # GW1/F1: T1 home vs T2.  P1 at T1 home. Clean sheet (T2 scored 0).
        (101, 1, 1,  90, 0,0, 1, 0,  0,0,0,0,0, 3, 0, 20,  6,  30.0, 10.0, 20.0,  6.0,  0.0, 0.0, 0.0, 0.5,  1, 0,  2, 1, "2025-08-16T12:30:00Z",  2, 0, 55, 10000, 200, 100, 100),
        # GW2/F2: T1 home vs T3.  P1 at T1 home. T3 scored 1 → goals_conceded=1.
        (101, 2, 2,  90, 0,0, 0, 1,  0,0,0,0,0, 2, 0, 15,  2,  20.0,  8.0, 15.0,  4.0,  0.0, 0.0, 0.0, 0.8,  1, 0,  3, 1, "2025-08-23T12:30:00Z",  1, 1, 55, 10100, 180, 110,  70),
        # GW3: T1 has NO fixture → BGW for P1. No history row.
        # GW4/F5: T1 home vs T2.  P1 at T1 home. T2 scored 0 → clean sheet.
        (101, 4, 5,  90, 0,0, 1, 0,  0,0,0,0,0, 4, 1, 24,  6,  28.0,  9.0, 18.0,  5.5,  0.0, 0.0, 0.0, 0.4,  1, 0,  2, 1, "2025-09-13T12:30:00Z",  1, 0, 55, 10200, 220, 130,  90),
        # GW5/F7: T1 home vs T3.  P1 at T1 home. Clean sheet.
        (101, 5, 7,  90, 0,0, 1, 0,  0,0,0,0,0, 2, 0, 18,  6,  25.0,  8.0, 16.0,  4.9,  0.0, 0.0, 0.0, 0.5,  1, 0,  3, 1, "2025-09-20T12:30:00Z",  2, 0, 55, 10300, 210, 120,  90),

        # --- P2 (GK, T2) ---
        # GW1/F1: T1 home vs T2.  P2 at T2 away. T1 scored 2 → P2 concedes 2.
        (102, 1, 1,  90, 0,0, 0, 2,  0,0,0,0,0, 1, 0, 12,  2,  15.0,  5.0, 10.0,  3.0,  0.0, 0.0, 0.0, 1.2,  1, 0,  1, 0, "2025-08-16T12:30:00Z",  2, 0, 65, 8000,  150, 120,  30),
        # GW2/F3: T2 home vs T4.  P2 at T2 home. T4 scored 0 → clean sheet.
        (102, 2, 3,  90, 0,0, 1, 0,  0,0,0,0,0, 3, 1, 22,  6,  22.0,  7.0, 14.0,  4.3,  0.0, 0.0, 0.0, 0.4,  1, 0,  4, 1, "2025-08-23T15:00:00Z",  1, 0, 65, 8100,  160, 110,  50),
        # GW3/F4: T2 home vs T3.  P2 at T2 home. T3 scored 1 → P2 concedes 1.
        (102, 3, 4,  90, 0,0, 0, 1,  0,0,0,0,0, 2, 0, 15,  2,  18.0,  6.0, 12.0,  3.6,  0.0, 0.0, 0.0, 0.9,  1, 0,  3, 1, "2025-08-30T12:30:00Z",  2, 1, 65, 8200,  170, 120,  50),
        # GW4/F5: T1 home vs T2.  P2 at T2 away. T1 scored 1 → P2 concedes 1. DGW fixture 1.
        (102, 4, 5,  90, 0,0, 0, 1,  0,0,0,0,0, 1, 0, 12,  2,  14.0,  4.5, 10.0,  2.9,  0.0, 0.0, 0.0, 1.0,  1, 0,  1, 0, "2025-09-13T12:30:00Z",  1, 0, 65, 8300,  180, 130,  50),
        # GW4/F6: T2 home vs T4.  P2 at T2 home. T4 scored 1 → P2 concedes 1. DGW fixture 2.
        (102, 4, 6,  90, 0,0, 0, 1,  0,0,0,0,0, 1, 0, 12,  2,  14.0,  4.5, 10.0,  2.9,  0.0, 0.0, 0.0, 1.0,  1, 0,  4, 1, "2025-09-13T15:00:00Z",  0, 1, 65, 8300,  170, 125,  45),
        # GW5/F8: T2 home vs T4.  P2 at T2 home. Clean sheet.
        (102, 5, 8,  90, 0,0, 1, 0,  0,0,0,0,0, 3, 1, 21,  6,  23.0,  7.5, 15.0,  4.6,  0.0, 0.0, 0.0, 0.5,  1, 0,  4, 1, "2025-09-20T15:00:00Z",  3, 0, 65, 8400,  190, 115,  75),

        # --- P3 (MID, at T1 for GW1-2, BGW in GW3, transfers to T2 for GW4-5) ---
        # players.team = 2 (T2, current snapshot). Bug: BGW GW3 gets team_id=T2.
        # Correct: BGW GW3 team_id should be T1=1 (team in GW1-2).
        #
        # GW1/F1: T1 home vs T2.  P3 at T1 home.
        (103, 1, 1,  90, 1,0, 0, 0,  0,0,0,0,0, 0, 1, 15,  8,  40.0, 20.0, 30.0, 9.0,  0.6, 0.3, 0.9, 0.0,  1, 0,  2, 1, "2025-08-16T12:30:00Z",  2, 0, 75, 5000,  300, 150, 150),
        # GW2/F2: T1 home vs T3.  P3 at T1 home.
        (103, 2, 2,  90, 0,1, 0, 1,  0,0,0,0,0, 0, 2, 16,  5,  35.0, 18.0, 25.0, 7.8,  0.2, 0.5, 0.7, 0.8,  1, 0,  3, 1, "2025-08-23T12:30:00Z",  1, 1, 75, 5100,  280, 140, 140),
        # GW3: T1 has NO fixture → BGW for P3. No history row.
        # GW4/F5: T1 home vs T2.  P3 now at T2 away.
        (103, 4, 5,  90, 0,0, 0, 1,  0,0,0,0,0, 0, 0, 10,  2,  25.0, 12.0, 20.0, 5.7,  0.1, 0.2, 0.3, 1.0,  1, 0,  1, 0, "2025-09-13T12:30:00Z",  1, 0, 80, 5200,  320, 160, 160),
        # GW4/F6: T2 home vs T4.  P3 at T2 home. DGW fixture 2.
        (103, 4, 6,  90, 1,0, 0, 1,  0,0,0,0,0, 0, 1, 14,  6,  42.0, 22.0, 32.0, 9.6,  0.7, 0.3, 1.0, 1.0,  1, 0,  4, 1, "2025-09-13T15:00:00Z",  0, 1, 80, 5200,  310, 155, 155),
        # GW5/F8: T2 home vs T4.  P3 at T2 home.
        (103, 5, 8,  75, 0,1, 0, 0,  0,0,0,0,0, 0, 2, 16,  6,  38.0, 19.0, 28.0, 8.5,  0.3, 0.6, 0.9, 0.5,  1, 0,  4, 1, "2025-09-20T15:00:00Z",  3, 0, 80, 5300,  330, 165, 165),
    ]

    conn.executemany(
        """INSERT INTO player_histories VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )


if __name__ == "__main__":
    create_test_db()
    print(f"Created golden test DB at {DB_PATH}")
