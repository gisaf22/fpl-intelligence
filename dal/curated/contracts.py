"""Curated spine contracts — column definitions, dtypes, null rules, and aggregation strategies."""

# Columns selected from staged events for gameweek-level context
GAMEWEEK_CONTEXT_COLS = [
    "gw",
    "deadline_time",
    "finished",
    "is_previous",
    "is_live",
    "is_next",
    "average_entry_score",
    "highest_score",
    "transfers_made",
]

# Output column order for the final spine
SPINE_COLS = [
    "player_id",
    "gw",
    "player_name",
    "position_code",
    "position_label",
    "team_id",
    "purchase_price",
    "ownership_count",
    "transfers_in",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "goals_conceded",
    "xg",
    "xa",
    "xgi",
    "xgc",
    "fdr_avg",
    "fdr_min",
    "fdr_max",
    "transfers_balance",
    "fixture_count",
    "is_bgw",
    "is_dgw",
    "home_count",
    "away_count",
    "was_home",
    "starts",
    "penalties_saved",
    "penalties_missed",
    "own_goals",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "in_dreamteam",
    "transfers_out",
    "deadline_time",
    "finished",
    "is_previous",
    "is_live",
    "is_next",
    "average_entry_score",
    "highest_score",
    "transfers_made",
]

# Semantic classification for every FIRST_COLS entry.
# invariant_per_gw: value is identical across all fixtures in the GW — taking first is safe;
#   an assertion enforces this before aggregation.
# canonical_first_fixture: intentionally takes value from the earliest fixture; semantically significant.
# temporally_first: takes value from the fixture with the lowest kickoff time.
# representative_arbitrary: no analytical semantics; any fixture's value is acceptable.
FIRST_COL_SEMANTICS: dict[str, str] = {
    "player_name":        "invariant_per_gw",
    "position_code":      "invariant_per_gw",
    "position_label":     "invariant_per_gw",
    "team_id":            "invariant_per_gw",   # enforced by fixture join; transfers handled separately
    "purchase_price":     "invariant_per_gw",   # FPL uses one price per GW deadline
    "ownership_count":    "invariant_per_gw",
    "transfers_in":       "invariant_per_gw",
    "transfers_out":      "invariant_per_gw",
    "transfers_balance":  "invariant_per_gw",
    "was_home":           "canonical_first_fixture",  # NULL for DGW by contract
}

# Columns aggregated by taking the first value per (player_id, gw)
FIRST_COLS = [
    "player_name",
    "position_code",
    "position_label",
    "team_id",
    "purchase_price",
    "ownership_count",
    "transfers_in",
    "transfers_out",
    "transfers_balance",
    "was_home",
]

# Columns aggregated by summing across fixtures per (player_id, gw)
SUM_COLS = [
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "goals_conceded",
    "xg",
    "xa",
    "xgi",
    "xgc",
    "home_count",
    "away_count",
    "starts",
    "penalties_saved",
    "penalties_missed",
    "own_goals",
    "influence",
    "creativity",
    "threat",
    "ict_index",
]

# Performance columns are NULL for BGW rows; all others default to 0.
PERFORMANCE_COLS = {
    "total_points", "minutes", "goals_scored", "assists", "clean_sheets",
    "yellow_cards", "red_cards", "saves", "bonus", "bps",
    "goals_conceded", "xg", "xa", "xgi", "xgc",
    "starts", "penalties_saved", "penalties_missed", "own_goals",
    "influence", "creativity", "threat", "ict_index",
}

# Target dtypes for all spine columns after construction
DTYPES: dict[str, str] = {
    "player_id":        "int64",
    "gw":               "int64",
    "player_name":      "string",
    "position_code":    "int64",
    "position_label":   "string",
    "team_id":          "int64",
    "purchase_price":   "float64",
    "ownership_count":  "int64",
    "transfers_in":     "int64",
    "total_points":     "Int64",   # nullable: BGW
    "minutes":          "Int64",   # nullable: BGW
    "goals_scored":     "Int64",   # nullable: BGW
    "assists":          "Int64",   # nullable: BGW
    "clean_sheets":     "Int64",   # nullable: BGW
    "yellow_cards":     "Int64",   # nullable: BGW
    "red_cards":        "Int64",   # nullable: BGW
    "saves":            "Int64",   # nullable: BGW
    "bonus":            "Int64",   # nullable: BGW
    "bps":              "Int64",   # nullable: BGW
    "goals_conceded":   "Int64",   # nullable: BGW
    "xg":               "Float64", # nullable: BGW
    "xa":               "Float64", # nullable: BGW
    "xgi":              "Float64", # nullable: BGW
    "xgc":              "Float64", # nullable: BGW
    "fdr_avg":          "Float64", # nullable: BGW
    "fdr_min":          "Float64", # nullable: BGW
    "fdr_max":          "Float64", # nullable: BGW
    "transfers_balance":"int64",
    "fixture_count":    "int64",
    "is_bgw":           "boolean",
    "is_dgw":           "boolean",
    "home_count":       "int64",
    "away_count":       "int64",
    "was_home":         "boolean",
    "starts":           "Int64",   # nullable: BGW
    "penalties_saved":  "Int64",   # nullable: BGW
    "penalties_missed": "Int64",   # nullable: BGW
    "own_goals":        "Int64",   # nullable: BGW
    "influence":        "Float64", # nullable: BGW
    "creativity":       "Float64", # nullable: BGW
    "threat":           "Float64", # nullable: BGW
    "ict_index":        "Float64", # nullable: BGW
    "in_dreamteam":     "int64",
    "transfers_out":    "int64",
    # Gameweek context columns — sourced from events table at GW grain
    "deadline_time":        "string",
    "finished":             "int64",
    "is_previous":          "int64",
    "is_live":              "int64",
    "is_next":              "int64",
    "average_entry_score":  "Int64",    # nullable: future GWs
    "highest_score":        "Int64",    # nullable: future GWs
    "transfers_made":       "int64",
}

# Null semantics contract for the final spine
NULL_RULES: dict[str, str] = {
    "player_id":            "never_null",
    "gw":                   "never_null",
    "player_name":          "never_null",
    "position_label":       "never_null",
    "team_id":              "never_null",
    "position_code":        "never_null",
    "fixture_count":        "never_null",
    "is_bgw":               "never_null",
    "is_dgw":               "never_null",
    "home_count":           "never_null",
    "away_count":           "never_null",
    "in_dreamteam":         "never_null",
    "transfers_in":         "never_null",
    "transfers_out":        "never_null",
    "ownership_count":      "never_null",
    "transfers_balance":    "never_null",
    "purchase_price":       "never_null",
    "deadline_time":        "never_null",
    "finished":             "never_null",
    "is_previous":          "never_null",
    "is_live":              "never_null",
    "is_next":              "never_null",
    "transfers_made":       "never_null",
    "total_points":         "null_if_bgw",
    "minutes":              "null_if_bgw",
    "goals_scored":         "null_if_bgw",
    "assists":              "null_if_bgw",
    "clean_sheets":         "null_if_bgw",
    "yellow_cards":         "null_if_bgw",
    "red_cards":            "null_if_bgw",
    "saves":                "null_if_bgw",
    "bonus":                "null_if_bgw",
    "bps":                  "null_if_bgw",
    "xg":                   "null_if_bgw",
    "xa":                   "null_if_bgw",
    "xgi":                  "null_if_bgw",
    "goals_conceded":       "null_if_bgw",
    "xgc":                  "null_if_bgw",
    "fdr_avg":              "null_if_bgw",
    "fdr_min":              "null_if_bgw",
    "fdr_max":              "null_if_bgw",
    "starts":               "null_if_bgw",
    "penalties_saved":      "null_if_bgw",
    "penalties_missed":     "null_if_bgw",
    "own_goals":            "null_if_bgw",
    "influence":            "null_if_bgw",
    "creativity":           "null_if_bgw",
    "threat":               "null_if_bgw",
    "ict_index":            "null_if_bgw",
    "was_home":             "always_nullable",
    "average_entry_score":  "always_nullable",
    "highest_score":        "always_nullable",
}
