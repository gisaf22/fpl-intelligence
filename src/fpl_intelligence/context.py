from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameweekContext:
    gw: int
    team_id: int
    is_dgw: bool
    is_bgw: bool
    fixture_count: int          # 0, 1, or 2
    opponent_team_ids: list[int]
    home_flags: list[bool]


def build_gameweek_context(conn: sqlite3.Connection, gw: int) -> dict[int, GameweekContext]:
    """
    Returns mapping: player_id -> GameweekContext.

    Rules:
    - A player is DGW if their team has 2 fixtures in this GW
    - A player is BGW if their team has 0 fixtures in this GW
    - Uses ALL fixtures for event = gw (does NOT filter on finished)
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Retrieve all players
    cur.execute("SELECT id, team FROM players")
    player_rows = cur.fetchall()

    # Initialize default context: every player starts as BGW (fixture_count = 0)
    player_team: dict[int, int] = {}
    player_data: dict[int, dict] = {}
    for row in player_rows:
        pid = int(row["id"])
        tid = int(row["team"]) if row["team"] is not None else 0
        player_team[pid] = tid
        player_data[pid] = {
            "fixture_count": 0,
            "is_bgw": True,
            "is_dgw": False,
            "opponent_team_ids": [],
            "home_flags": [],
        }

    # Query all fixtures for this GW (no finished filter)
    cur.execute("SELECT team_h, team_a FROM fixtures WHERE event = ?", (gw,))
    fixture_rows = cur.fetchall()

    # Build team -> [(opponent_id, is_home)] mapping
    team_fixtures: dict[int, list[tuple[int, bool]]] = {}
    for row in fixture_rows:
        th = int(row["team_h"])
        ta = int(row["team_a"])
        team_fixtures.setdefault(th, []).append((ta, True))
        team_fixtures.setdefault(ta, []).append((th, False))

    # Update each player's context from their team's fixtures
    for pid, tid in player_team.items():
        if tid not in team_fixtures:
            # team has no fixtures this GW: remains BGW default
            continue
        fixtures = team_fixtures[tid]
        fc = len(fixtures)
        player_data[pid]["fixture_count"] = fc
        player_data[pid]["is_bgw"] = fc == 0
        player_data[pid]["is_dgw"] = fc == 2
        player_data[pid]["opponent_team_ids"] = [f[0] for f in fixtures]
        player_data[pid]["home_flags"] = [f[1] for f in fixtures]

    result = {
        pid: GameweekContext(
            gw=gw,
            team_id=player_team[pid],
            is_dgw=ctx["is_dgw"],
            is_bgw=ctx["is_bgw"],
            fixture_count=ctx["fixture_count"],
            opponent_team_ids=ctx["opponent_team_ids"],
            home_flags=ctx["home_flags"],
        )
        for pid, ctx in player_data.items()
    }

    assert all(ctx.fixture_count in {0, 1, 2} for ctx in result.values())
    assert all(ctx.fixture_count == 2 for ctx in result.values() if ctx.is_dgw)
    assert all(ctx.fixture_count == 0 for ctx in result.values() if ctx.is_bgw)
    assert all(len(ctx.opponent_team_ids) == ctx.fixture_count for ctx in result.values())
    assert all(len(ctx.home_flags) == ctx.fixture_count for ctx in result.values())

    # Players on the same team must share fixture_count
    team_fixture_counts: dict[int, set] = {}
    for ctx in result.values():
        team_fixture_counts.setdefault(ctx.team_id, set()).add(ctx.fixture_count)
    assert all(len(counts) == 1 for counts in team_fixture_counts.values())

    return result
