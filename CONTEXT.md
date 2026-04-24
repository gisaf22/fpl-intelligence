# fpl-intelligence — Agent Context

> Read this fully before writing any code. Do not summarise back to the user. Go straight to work.

## What this project is

`fpl-intelligence` is an FPL analytical system that reads from `~/.fpl/fpl.db`, a SQLite database
written by a separate pipeline called `fpl-ingest`. This project does not write to the DB.
Default path is `~/.fpl/fpl.db` (configured in `config.py` as `DB_PATH`).
It produces analytical outputs: briefing JSONs, experiment findings, evaluation reports.

## Current state (as of GW 34, April 2026)

- 79/87 tests pass
- Pipeline is fully built but blocked by one missing function
- No output has ever been produced against the live DB
- GW 33 is complete. GW 34 is the active gameweek.

## Architecture

```
fpl.db (read-only)
  └── analysis/source/          raw SQL queries → DataFrames
  └── analysis/staging/         type-cast and rename
  └── analysis/curated/         player_gameweek_spine (one row per player/GW)
  └── analysis/state/           fixture_context, home_away_profile
  └── analysis/dal/             DAL for notebooks and analysis scripts
  └── src/fpl_intelligence/db/  DAL for pipeline (tuple-based)
  └── src/fpl_intelligence/pipeline/  11-step pipeline → briefing JSON
  └── src/fpl_intelligence/eval/      scoring pipeline (built, unreachable)
```

## DB tables available

| Table | Rows | Key columns | Used? |
|-------|------|-------------|-------|
| players | 829 | id, web_name, element_type, team, now_cost, selected_by_percent, ep_next, status, news | Yes |
| fixtures | 380 | id, event, team_h, team_a, team_h_difficulty, team_a_difficulty | Yes |
| player_histories | 25,732 | element_id, round, fixture, total_points, starts, selected, was_home, minutes, goals_scored, assists, clean_sheets, bps, ict_index, expected_goals, expected_assists, value, transfers_in, transfers_out, ingested_at | Yes |
| events | 38 | id, is_current, is_next, deadline_time, average_entry_score | Partially |
| _metadata | 3 | current_gameweek=33, last_successful_run_at | Not yet |
| gameweeks | 25,566 | element_id, round | Not used |
| teams | 20 | id, strength, form | Not used |
| element_types | 4 | id, singular_name_short | Not used |
| fixture_stats | 22,826 | fixture_id, identifier, element, value, side | Not used |

## Immediate fixes — do in order

### FIX 1 — implement fetch_current_gw() [CRITICAL — do this first]

File: `src/fpl_intelligence/db/player_repo.py`
Called by: `src/fpl_intelligence/pipeline/steps.py:75` via `load_gw_context()`
Blocking: `run_gw()`, `main.py`, 7 failing tests, all e2e tests

Implementation: query `_metadata` table for `current_gameweek` key.

```python
def fetch_current_gw(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM _metadata WHERE key = 'current_gameweek'"
    ).fetchone()
    if row is None:
        raise DataFreshnessError("current_gameweek not found in _metadata")
    return int(row[0])
```

After implementing: run `pytest` — expect 85+/87 passing.
Then run: `python main.py --gw 34` — expect briefing JSON written to `data/briefs/`.

### FIX 2 — create docs/contracts/test_cases.json

Required by: `tests/test_briefing_models.py:20`
Content: valid and invalid Briefing model test cases
Base models on: `src/fpl_intelligence/models/briefing.py`

### FIX 3 — add CLI entry point for eval/runner.py

`src/fpl_intelligence/eval/runner.py` is fully implemented — `run_gw_evaluation()` and
`run_backtest()` — but completely unreachable. Add argparse to `main.py` or create `eval_cli.py`.

## Open questions — get analyst decisions before coding

1. **fetch_current_gw source**: Use `_metadata`. Decision made.
2. **fixture_context "OTHER" vs "DGW"**: `player_gameweek_v1.py` returns "OTHER" for
   fixture_count > 2. `player_gameweek_state.py` returns "DGW". Which is authoritative?
   Recommendation: "DGW" is correct — "OTHER" in v1 is the bug. Confirm with analyst.
3. **Calibration bins always empty**: With OVR_TOP_N=20, n_bins=10, MIN_EVAL_POOL_SIZE=20
   every calibration call returns empty. Defer calibration or reduce MIN_EVAL_POOL_SIZE?
4. **gameweeks table**: 25,566 rows, no fixture column, no ingested_at. Not used anywhere.
   Clarify relationship to player_histories before querying.
5. **Notebook 01**: Missing. Numbering jumps 00 → 02. Ask analyst.
6. **generate_editorial_brief + log_run**: Both stub NotImplementedError. In scope or not?

## Hardcoded values that need documenting (do not change values yet — document them)

| Constant | Value | Location | Notes |
|----------|-------|----------|-------|
| MINUTES_FILTER_LOOKBACK | 6 | config.py | GW lookback for starts aggregation |
| DGW_DIVERGENCE_WEIGHT | 1.5 | config.py | No documented rationale |
| OVR_TOP_N | 20 | config.py | Max items in undervalued/overvalued lists |
| Nailed threshold | 0.75 | steps.py:221 | start_rate >= 0.75 → nailed |
| Rotation threshold | 0.40 | steps.py:222 | start_rate >= 0.40 → rotation |
| Data freshness | 6 hours | steps.py:62 | max_age_hours default |
| Element type map | {1:GK,2:DEF,3:MID,4:FWD} | steps.py:39 | Hardcoded, not in config |

## Pinned definitions (do not change without analyst instruction)

| Term | Definition | Status |
|------|-----------|--------|
| Stack strategy | 3+ players from one fixture | PINNED |
| Spread strategy | Max 2 players from any fixture | PINNED |
| Hybrid strategy | 3+ from one fixture + spread across 2+ others | PINNED |
| Minutes certainty | Started 2 of last 3 available GWs | PINNED |
| Form signal | Pending Study A — use 3 GW rolling points as interim | TO BE VALIDATED |
| High concentration | Top 2 fixtures = 50%+ of expected attacking return | PROVISIONAL |
| Custom attacking FDR | Opponent goals conceded rate × team goals scored rate, rolling 5 GW | PROVISIONAL |
| FH eligible pool | Active GW 34 teams + minutes certainty + £100m + formation constraints | PINNED |

## Feature build order (after fixes)

1. Fix 1 → Fix 2 → Fix 3
2. Study A (form signal validation) — Spearman correlation across GW 2–33
3. Experiment 2 (fixture concentration validation) — Spearman, pre vs actual
4. Experiment 1 (stack vs spread simulation) — Wilcoxon + bootstrap
5. Experiment 3 (form vs fixture) — depends on Study A + Experiment 2
6. Custom FDR (F08) — attacking + defensive, rolling 5 GW
7. GW 34 decision brief (F09) — synthesises all above
8. Post-GW scoring — run eval/runner.py after GW 34

## Session discipline

Start every session by reading this file.
End every session by updating the "Current state" section above and the feature build order.
Never leave a session without running pytest and recording the pass count.
Never fix more than one thing at a time without running tests between fixes.