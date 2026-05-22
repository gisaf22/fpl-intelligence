# DB Schema Reference
Source: `~/.fpl/fpl.db`
Queried: 2026-04-25

---

## players

**Row count: 829**

### Columns

| cid | name | type | notnull | pk |
|-----|------|------|---------|----|
| 0 | id | INTEGER | yes | yes |
| 1 | first_name | TEXT | yes | |
| 2 | second_name | TEXT | yes | |
| 3 | web_name | TEXT | yes | |
| 4 | known_name | TEXT | | |
| 5 | team | INTEGER | yes | |
| 6 | team_code | INTEGER | yes | |
| 7 | element_type | INTEGER | yes | |
| 8 | now_cost | INTEGER | yes | |
| 9 | price_change_percent | INTEGER | | |
| 10 | status | TEXT | yes | |
| 11 | code | INTEGER | yes | |
| 12 | opta_code | TEXT | | |
| 13 | photo | TEXT | | |
| 14 | birth_date | TEXT | | |
| 15 | team_join_date | TEXT | | |
| 16 | region | INTEGER | | |
| 17 | squad_number | INTEGER | | |
| 18 | special | INTEGER | | |
| 19 | removed | INTEGER | | |
| 20 | can_transact | INTEGER | | |
| 21 | can_select | INTEGER | | |
| 22 | has_temporary_code | INTEGER | | |
| 23 | total_points | INTEGER | yes | |
| 24 | event_points | INTEGER | yes | |
| 25 | minutes | INTEGER | yes | |
| 26 | goals_scored | INTEGER | yes | |
| 27 | assists | INTEGER | yes | |
| 28 | clean_sheets | INTEGER | yes | |
| 29 | goals_conceded | INTEGER | yes | |
| 30 | own_goals | INTEGER | yes | |
| 31 | penalties_saved | INTEGER | yes | |
| 32 | penalties_missed | INTEGER | yes | |
| 33 | yellow_cards | INTEGER | yes | |
| 34 | red_cards | INTEGER | yes | |
| 35 | saves | INTEGER | yes | |
| 36 | bonus | INTEGER | yes | |
| 37 | bps | INTEGER | yes | |
| 38 | starts | INTEGER | yes | |
| 39 | tackles | INTEGER | | |
| 40 | recoveries | INTEGER | | |
| 41 | clearances_blocks_interceptions | INTEGER | | |
| 42 | defensive_contribution | INTEGER | | |
| 43 | dreamteam_count | INTEGER | yes | |
| 44 | in_dreamteam | INTEGER | yes | |
| 45 | influence | REAL | yes | |
| 46 | creativity | REAL | yes | |
| 47 | threat | REAL | yes | |
| 48 | ict_index | REAL | yes | |
| 49 | expected_goals | REAL | yes | |
| 50 | expected_assists | REAL | yes | |
| 51 | expected_goal_involvements | REAL | yes | |
| 52 | expected_goals_conceded | REAL | yes | |
| 53 | clean_sheets_per_90 | REAL | | |
| 54 | goals_conceded_per_90 | REAL | | |
| 55 | saves_per_90 | REAL | | |
| 56 | expected_goals_per_90 | REAL | | |
| 57 | expected_assists_per_90 | REAL | | |
| 58 | expected_goal_involvements_per_90 | REAL | | |
| 59 | expected_goals_conceded_per_90 | REAL | | |
| 60 | defensive_contribution_per_90 | REAL | | |
| 61 | starts_per_90 | REAL | | |
| 62 | form | REAL | yes | |
| 63 | points_per_game | REAL | yes | |
| 64 | selected_by_percent | REAL | yes | |
| 65 | value_form | REAL | yes | |
| 66 | value_season | REAL | yes | |
| 67 | ep_next | REAL | | |
| 68 | ep_this | REAL | | |
| 69 | form_rank | INTEGER | yes | |
| 70 | form_rank_type | INTEGER | yes | |
| 71 | points_per_game_rank | INTEGER | yes | |
| 72 | points_per_game_rank_type | INTEGER | yes | |
| 73 | now_cost_rank | INTEGER | yes | |
| 74 | now_cost_rank_type | INTEGER | yes | |
| 75 | selected_rank | INTEGER | yes | |
| 76 | selected_rank_type | INTEGER | yes | |
| 77 | influence_rank | INTEGER | yes | |
| 78 | influence_rank_type | INTEGER | yes | |
| 79 | creativity_rank | INTEGER | yes | |
| 80 | creativity_rank_type | INTEGER | yes | |
| 81 | threat_rank | INTEGER | yes | |
| 82 | threat_rank_type | INTEGER | yes | |
| 83 | ict_index_rank | INTEGER | yes | |
| 84 | ict_index_rank_type | INTEGER | yes | |
| 85 | chance_of_playing_next_round | INTEGER | | |
| 86 | chance_of_playing_this_round | INTEGER | | |
| 87 | transfers_in | INTEGER | yes | |
| 88 | transfers_out | INTEGER | yes | |
| 89 | transfers_in_event | INTEGER | yes | |
| 90 | transfers_out_event | INTEGER | yes | |
| 91 | cost_change_event | INTEGER | yes | |
| 92 | cost_change_event_fall | INTEGER | yes | |
| 93 | cost_change_start | INTEGER | yes | |
| 94 | cost_change_start_fall | INTEGER | yes | |
| 95 | penalties_order | INTEGER | | |
| 96 | penalties_text | TEXT | | |
| 97 | corners_and_indirect_freekicks_order | INTEGER | | |
| 98 | corners_and_indirect_freekicks_text | TEXT | | |
| 99 | direct_freekicks_order | INTEGER | | |
| 100 | direct_freekicks_text | TEXT | | |
| 101 | news | TEXT | | |
| 102 | news_added | TEXT | | |
| 103 | ingested_at | TEXT | | |

### Null counts (non-zero only)

| column | nulls |
|--------|-------|
| birth_date | 20 |
| team_join_date | 20 |
| region | 21 |
| squad_number | 829 (all null) |
| chance_of_playing_next_round | 209 |
| chance_of_playing_this_round | 212 |
| penalties_order | 770 |
| corners_and_indirect_freekicks_order | 755 |
| direct_freekicks_order | 767 |
| news_added | 209 |

### Sample rows (3)

| field | row 1 (id=1, Raya) | row 2 (id=2, Arrizabalaga) | row 3 (id=3, Hein) |
|-------|--------------------|---------------------------|---------------------|
| id | 1 | 2 | 3 |
| web_name | Raya | Arrizabalaga | Hein |
| team | 1 | 1 | 1 |
| element_type | 1 | 1 | 1 |
| now_cost | 60 | 40 | 40 |
| status | a | a | u |
| total_points | 131 | 0 | 0 |
| starts | 33 | 0 | 0 |
| selected_by_percent | 21.8 | 0.0 | 0.0 |
| ep_next | 2.0 | 1.0 | 0.0 |
| news | (empty) | (empty) | Has joined Werder Bremen on loan |

---

## fixtures

**Row count: 380**

### Columns

| cid | name | type | notnull | pk |
|-----|------|------|---------|----|
| 0 | id | INTEGER | yes | yes |
| 1 | code | INTEGER | yes | |
| 2 | event | INTEGER | | |
| 3 | team_h | INTEGER | yes | |
| 4 | team_a | INTEGER | yes | |
| 5 | team_h_score | INTEGER | | |
| 6 | team_a_score | INTEGER | | |
| 7 | team_h_difficulty | INTEGER | yes | |
| 8 | team_a_difficulty | INTEGER | yes | |
| 9 | kickoff_time | TEXT | | |
| 10 | minutes | INTEGER | yes | |
| 11 | started | INTEGER | | |
| 12 | finished | INTEGER | yes | |
| 13 | finished_provisional | INTEGER | yes | |
| 14 | provisional_start_time | INTEGER | | |
| 15 | pulse_id | INTEGER | | |
| 16 | ingested_at | TEXT | | |

### Null counts (non-zero only)

| column | nulls |
|--------|-------|
| event | 1 (one fixture not yet assigned to a GW) |
| team_h_score | 48 (future fixtures) |
| team_a_score | 48 (future fixtures) |
| kickoff_time | 1 |
| started | 1 |

### Sample rows (3)

| field | fixture 1 | fixture 2 | fixture 3 |
|-------|-----------|-----------|-----------|
| id | 1 | 2 | 3 |
| event | 1 | 1 | 1 |
| team_h | 12 | 2 | 6 |
| team_a | 4 | 15 | 10 |
| team_h_score | 4 | 0 | 1 |
| team_a_score | 2 | 0 | 1 |
| team_h_difficulty | 3 | 3 | 3 |
| team_a_difficulty | 4 | 4 | 4 |
| kickoff_time | 2025-08-15T19:00:00Z | 2025-08-16T11:30:00Z | 2025-08-16T14:00:00Z |
| finished | 1 | 1 | 1 |

---

## player_histories

**Row count: 25,732**

### Columns

| cid | name | type | notnull | pk |
|-----|------|------|---------|----|
| 0 | element_id | INTEGER | yes | |
| 1 | round | INTEGER | yes | |
| 2 | fixture | INTEGER | yes | |
| 3 | minutes | INTEGER | yes | |
| 4 | goals_scored | INTEGER | yes | |
| 5 | assists | INTEGER | yes | |
| 6 | clean_sheets | INTEGER | yes | |
| 7 | goals_conceded | INTEGER | yes | |
| 8 | own_goals | INTEGER | yes | |
| 9 | penalties_saved | INTEGER | yes | |
| 10 | penalties_missed | INTEGER | yes | |
| 11 | yellow_cards | INTEGER | yes | |
| 12 | red_cards | INTEGER | yes | |
| 13 | saves | INTEGER | yes | |
| 14 | bonus | INTEGER | yes | |
| 15 | bps | INTEGER | yes | |
| 16 | total_points | INTEGER | yes | |
| 17 | influence | REAL | yes | |
| 18 | creativity | REAL | yes | |
| 19 | threat | REAL | yes | |
| 20 | ict_index | REAL | yes | |
| 21 | expected_goals | REAL | yes | |
| 22 | expected_assists | REAL | yes | |
| 23 | expected_goal_involvements | REAL | yes | |
| 24 | expected_goals_conceded | REAL | yes | |
| 25 | starts | INTEGER | yes | |
| 26 | in_dreamteam | INTEGER | yes | |
| 27 | tackles | INTEGER | | |
| 28 | clearances_blocks_interceptions | INTEGER | | |
| 29 | recoveries | INTEGER | | |
| 30 | defensive_contribution | INTEGER | | |
| 31 | opponent_team | INTEGER | yes | |
| 32 | was_home | INTEGER | yes | |
| 33 | kickoff_time | TEXT | yes | |
| 34 | team_h_score | INTEGER | | |
| 35 | team_a_score | INTEGER | | |
| 36 | value | INTEGER | yes | |
| 37 | selected | INTEGER | yes | |
| 38 | transfers_in | INTEGER | yes | |
| 39 | transfers_out | INTEGER | yes | |
| 40 | transfers_balance | INTEGER | yes | |
| 41 | ingested_at | TEXT | | |

### Null counts

All columns: **0 nulls**. This table is fully populated.

### Notes on nullable columns

`tackles`, `clearances_blocks_interceptions`, `recoveries`, `defensive_contribution` are declared nullable but contain no nulls in the current data. `team_h_score`, `team_a_score` are nullable but contain no nulls (all rows are completed fixtures).

### Sample rows (3)

| field | row 1 | row 2 | row 3 |
|-------|-------|-------|-------|
| element_id | 1 | 1 | 1 |
| round | 1 | 2 | 3 |
| fixture | 9 | 11 | 25 |
| minutes | 90 | 90 | 90 |
| total_points | 10 | 6 | 2 |
| starts | 1 | 1 | 1 |
| was_home | 0 | 1 | 0 |
| opponent_team | 14 | 11 | 12 |
| value | 55 | 55 | 55 |
| selected | 1,531,911 | 2,284,634 | 2,406,964 |
| expected_goals | 0.0 | 0.0 | 0.0 |
| expected_goals_conceded | 1.52 | 0.17 | 0.52 |
| kickoff_time | 2025-08-17T15:30:00Z | 2025-08-23T16:30:00Z | 2025-08-31T15:30:00Z |

---

## events

**Row count: 38**

### Columns

| cid | name | type | notnull | pk |
|-----|------|------|---------|----|
| 0 | id | INTEGER | yes | yes |
| 1 | name | TEXT | yes | |
| 2 | deadline_time | TEXT | yes | |
| 3 | deadline_time_epoch | INTEGER | yes | |
| 4 | deadline_time_game_offset | INTEGER | yes | |
| 5 | release_time | TEXT | | |
| 6 | released | INTEGER | | |
| 7 | average_entry_score | INTEGER | | |
| 8 | highest_score | INTEGER | | |
| 9 | highest_scoring_entry | INTEGER | | |
| 10 | ranked_count | INTEGER | | |
| 11 | finished | INTEGER | yes | |
| 12 | data_checked | INTEGER | yes | |
| 13 | is_previous | INTEGER | yes | |
| 14 | is_current | INTEGER | yes | |
| 15 | is_next | INTEGER | yes | |
| 16 | can_enter | INTEGER | yes | |
| 17 | can_manage | INTEGER | yes | |
| 18 | cup_leagues_created | INTEGER | yes | |
| 19 | h2h_ko_matches_created | INTEGER | yes | |
| 20 | most_selected | INTEGER | | |
| 21 | most_transferred_in | INTEGER | | |
| 22 | most_captained | INTEGER | | |
| 23 | most_vice_captained | INTEGER | | |
| 24 | top_element | INTEGER | | |
| 25 | top_element_points | INTEGER | | |
| 26 | transfers_made | INTEGER | yes | |
| 27 | chip_plays_json | TEXT | | |
| 28 | ingested_at | TEXT | | |

### Null counts (non-zero only)

| column | nulls |
|--------|-------|
| release_time | 38 (all null) |
| highest_score | 5 (future GWs) |
| highest_scoring_entry | 5 |
| most_selected | 5 |
| most_transferred_in | 5 |
| most_captained | 5 |
| most_vice_captained | 5 |
| top_element | 5 |
| top_element_points | 5 |
| chip_plays_json | 5 |

### Notes

5 null rows = GWs 34–38, which have not yet been played. `release_time` is all-null across all 38 GWs. `is_next=1` on GW 34 at time of ingest.

### Sample rows (3)

| field | GW 1 | GW 2 | GW 3 |
|-------|------|------|------|
| id | 1 | 2 | 3 |
| name | Gameweek 1 | Gameweek 2 | Gameweek 3 |
| deadline_time | 2025-08-15T17:30:00Z | 2025-08-22T17:30:00Z | 2025-08-30T10:00:00Z |
| finished | 1 | 1 | 1 |
| is_previous | 0 | 0 | 0 |
| is_current | 0 | 0 | 0 |
| is_next | 0 | 0 | 0 |
| average_entry_score | 54 | 51 | 48 |
| highest_score | 127 | 140 | 118 |
| transfers_made | 0 | 18,178,809 | 27,802,596 |

---

## teams

**Row count: 20**

### Columns

| cid | name | type | notnull | pk |
|-----|------|------|---------|----|
| 0 | id | INTEGER | yes | yes |
| 1 | name | TEXT | yes | |
| 2 | short_name | TEXT | yes | |
| 3 | code | INTEGER | yes | |
| 4 | pulse_id | INTEGER | | |
| 5 | strength | INTEGER | yes | |
| 6 | strength_overall_home | INTEGER | yes | |
| 7 | strength_overall_away | INTEGER | yes | |
| 8 | strength_attack_home | INTEGER | yes | |
| 9 | strength_attack_away | INTEGER | yes | |
| 10 | strength_defence_home | INTEGER | yes | |
| 11 | strength_defence_away | INTEGER | yes | |
| 12 | played | INTEGER | yes | |
| 13 | win | INTEGER | yes | |
| 14 | draw | INTEGER | yes | |
| 15 | loss | INTEGER | yes | |
| 16 | points | INTEGER | yes | |
| 17 | position | INTEGER | yes | |
| 18 | form | REAL | | |
| 19 | team_division | TEXT | | |
| 20 | unavailable | INTEGER | yes | |
| 21 | ingested_at | TEXT | | |

### Null counts (non-zero only)

| column | nulls |
|--------|-------|
| form | 20 (all null) |
| team_division | 20 (all null) |

### Notes

`played`, `win`, `draw`, `loss`, `points` are all 0 for all teams — these are not populated in the ingest source. `strength_*` columns contain FPL's internal difficulty ratings (1305–1390 range for Arsenal). `form` and `team_division` are all null.

### Sample rows (3)

| field | Arsenal | Aston Villa | Burnley |
|-------|---------|-------------|---------|
| id | 1 | 2 | 3 |
| short_name | ARS | AVL | BUR |
| strength | 5 | 3 | 2 |
| strength_overall_home | 1305 | 1140 | 975 |
| strength_overall_away | 1365 | 1220 | 1080 |
| strength_attack_home | 1340 | 1100 | 910 |
| strength_attack_away | 1390 | 1230 | 1070 |
| strength_defence_home | 1270 | 1180 | 1040 |
| strength_defence_away | 1340 | 1210 | 1090 |
| position | 2 | 4 | 19 |
| played | 0 | 0 | 0 |

---

## element_types

**Row count: 4**

### Columns

| cid | name | type | notnull | pk |
|-----|------|------|---------|----|
| 0 | id | INTEGER | yes | yes |
| 1 | singular_name | TEXT | yes | |
| 2 | singular_name_short | TEXT | yes | |
| 3 | plural_name | TEXT | yes | |
| 4 | plural_name_short | TEXT | yes | |
| 5 | squad_select | INTEGER | yes | |
| 6 | squad_min_select | INTEGER | | |
| 7 | squad_max_select | INTEGER | | |
| 8 | squad_min_play | INTEGER | yes | |
| 9 | squad_max_play | INTEGER | yes | |
| 10 | ui_shirt_specific | INTEGER | yes | |
| 11 | element_count | INTEGER | yes | |
| 12 | ingested_at | TEXT | | |

### Null counts (non-zero only)

| column | nulls |
|--------|-------|
| squad_min_select | 4 (all null) |
| squad_max_select | 4 (all null) |

### All rows

| id | singular_name | singular_name_short | squad_select | squad_min_play | squad_max_play | element_count |
|----|---------------|---------------------|--------------|----------------|----------------|---------------|
| 1 | Goalkeeper | GKP | 2 | 1 | 1 | 96 |
| 2 | Defender | DEF | 5 | 3 | 5 | 268 |
| 3 | Midfielder | MID | 5 | 2 | 5 | 373 |
| 4 | Forward | FWD | 3 | 1 | 3 | 92 |

---

## Summary

| table | rows | columns | pk | nullable cols with nulls |
|-------|------|---------|----|--------------------------|
| players | 829 | 104 | id | birth_date, team_join_date, region, squad_number (all), chance_of_playing (209–212), set-piece order cols (755–770), news_added (209) |
| fixtures | 380 | 17 | id | event (1), team_h/a_score (48 each — future fixtures), kickoff_time (1), started (1) |
| player_histories | 25,732 | 42 | — (no declared pk) | none |
| events | 38 | 29 | id | release_time (all), post-match stats (5 each — future GWs) |
| teams | 20 | 22 | id | form (all), team_division (all) |
| element_types | 4 | 13 | id | squad_min_select (all), squad_max_select (all) |
