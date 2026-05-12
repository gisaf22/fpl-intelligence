"""DAL grain contracts registry — machine-readable grain declarations for all DAL layers.

All DAL layer grains are declared here. Validators consume this registry.
If a new curated table is added, its grain must be registered here before any validator
is written. This prevents validators from drifting away from the declared grain.
"""

GRAIN_CONTRACTS: dict[str, dict] = {
    "staging_players":          {"pk": ["player_id"],                      "duplicates_allowed": False},
    "staging_player_histories": {"pk": ["player_id", "fixture_id"],        "duplicates_allowed": False},
    "staging_fixtures":         {"pk": ["fixture_id"],                     "duplicates_allowed": False},
    "staging_teams":            {"pk": ["team_id"],                        "duplicates_allowed": False},
    "staging_events":           {"pk": ["gw"],                             "duplicates_allowed": False},
    "staging_element_types":    {"pk": ["position_code"],                  "duplicates_allowed": False},
    "gameweek_context":         {"pk": ["gw"],                             "duplicates_allowed": False},
    "player_fixture_base":      {"pk": ["player_id", "gw", "fixture_id"],  "duplicates_allowed": False},
    "player_gameweek_spine":    {"pk": ["player_id", "gw"],                "duplicates_allowed": False},
    "player_gameweek_state":    {"pk": ["player_id", "gw"],                "duplicates_allowed": False},
    "player_opponent_context":  {"pk": ["player_id", "gw"],                "duplicates_allowed": False},
}
