# fpl-intelligence — Project Audit

**Audit date:** 2026-04-23
**Auditor:** Claude (automated)
**Scope:** All files in the project root, excluding `.git/` and `.venv/`.

---

## STEP 1 — REPO STRUCTURE

### Root

| Path | Type | Description |
|------|------|-------------|
| `main.py` | script | CLI entry point. Parses `--gw`, `--db`, `--output-dir`, `--log-path` and calls `run_gw()`. |
| `validation.py` | script | Contains `validate_pipeline_output()`. Runs 5 checks on assembled pipeline output and returns a `ValidationResult`. |
| `pyproject.toml` | config | Project metadata, dependencies (pydantic, numpy, scipy, jsonschema), and pytest config. |
| `uv.lock` | config | Locked dependency versions for the uv package manager. |
| `.python-version` | config | Pins Python version to 3.10. |
| `README.md` | doc | Describes layer boundaries: DRC, DAL, EDA, hypothesis registry, experiments, signals. References `analysis/experiments/hypothesis_registry.md` which does not exist. |
| `.gitignore` | config | Ignores `.env`, `output/`, `logs/`, `*.db`, `*.db-shm`, `*.db-wal`. |
| `.claude/settings.local.json` | config | Claude Code local settings. |

### `analysis/`

| Path | Type | Description |
|------|------|-------------|
| `analysis/contracts/schemas.py` | script | Defines `player_gameweek_spine_schema` — a dict of `ColumnSchema(dtype, nullable)` for each spine column. |
| `analysis/contracts/validation.py` | script | Validates a DataFrame against `player_gameweek_spine_schema`: columns, dtypes, nullability, uniqueness, list-field alignment. |
| `analysis/curated/__init__.py` | script | Empty init. |
| `analysis/curated/player_gameweek_spine.py` | script | Builds the canonical `player_gameweek_spine` DataFrame — one row per `(player_id, gameweek)` with list-valued fixture columns. Calls `validate_player_gameweek_spine()` before returning. |
| `analysis/dal/__init__.py` | script | Empty init. |
| `analysis/dal/player_repo.py` | script | Data access layer. Declared sole SQL boundary for the analysis layer. Returns DataFrames. Contains `get_players`, `get_fixtures`, `get_all_player_histories`, `get_fixtures_full`. |
| `analysis/notebooks/00_spine_validation.ipynb` | notebook | Validates spine structure, DGW aggregation, join integrity, ordering. Prints tables. |
| `analysis/notebooks/02_state_descriptive_analysis.ipynb` | notebook | EDA of `total_points` by `fixture_context`, `fixture_count`, `home_away_profile`, `minutes`. Purely observational. |
| `analysis/notebooks/03_stability_analysis.ipynb` | notebook | Variance and stability analysis — CV, quartiles, GW-level mean stability, extreme value influence. Purely observational. |
| `analysis/player_gameweek_v1.py` | script | Defines `player_gameweek_v1` curated dataset, source table contracts, `validate_source_tables`, `build_player_gameweek_v1`, and `define_initial_state_variables`. |
| `analysis/source/__init__.py` | script | Empty init. |
| `analysis/source/fixtures.py` | script | Executes `SELECT * FROM fixtures` and returns a DataFrame. |
| `analysis/source/player_histories.py` | script | Executes a 41-column SELECT from `player_histories` and returns a DataFrame. |
| `analysis/source/players.py` | script | Executes `SELECT id, web_name, element_type, team FROM players` and returns a DataFrame. |
| `analysis/staging/__init__.py` | script | Empty init. |
| `analysis/staging/fixtures.py` | script | Renames `id` to `fixture_id`, optionally includes `kickoff_time`, type-casts to `int64`. |
| `analysis/staging/player_histories.py` | script | Narrows player_histories to 9 columns, renames keys, type-casts. |
| `analysis/staging/players.py` | script | Renames `id → player_id`, `web_name → player_name`, `team → team_id`, type-casts. |
| `analysis/state/player_gameweek_state.py` | script | Derives `fixture_context` (BGW/SGW/DGW), `home_away_profile` (HOME/AWAY/MIXED), and carries `minutes` and `starts` from the spine. |

### `src/fpl_intelligence/`

| Path | Type | Description |
|------|------|-------------|
| `src/fpl_intelligence/__init__.py` | script | Re-exports the three custom exception classes. |
| `src/fpl_intelligence/config.py` | script | Defines `DB_PATH`, `MINUTES_FILTER_LOOKBACK`, `DGW_DIVERGENCE_WEIGHT`, `OVR_TOP_N`, `MIN_EVAL_POOL_SIZE`. |
| `src/fpl_intelligence/context.py` | script | `build_gameweek_context()` — queries `players` and `fixtures` to produce `dict[player_id, GameweekContext]` with DGW/BGW flags. |
| `src/fpl_intelligence/datasets.py` | script | `FeatureRecord` protocol, `PlayerMetrics` and `PlayerFeatures` frozen dataclasses. |
| `src/fpl_intelligence/eligibility.py` | script | Single authoritative `is_player_eligible()` function. Applies BGW gate and starts-count gate. Contains an extended inline audit of prior eligibility logic. |
| `src/fpl_intelligence/exceptions.py` | script | Defines `DataFreshnessError`, `BriefingValidationError`, `SchemaContractError`. |
| `src/fpl_intelligence/db/player_repo.py` | script | Repository layer for pipeline. Contains `validate_data_freshness()` and `fetch_player_metrics()`. Does NOT contain `fetch_current_gw()`. |
| `src/fpl_intelligence/eval/__init__.py` | script | Empty (1-line file). |
| `src/fpl_intelligence/eval/metrics.py` | script | Computes Spearman, precision@k, churn@k, calibration bins, temporal stability. |
| `src/fpl_intelligence/eval/ranking.py` | script | Builds signal and actual rankings, constructs evaluation sets, deduplicates signals. |
| `src/fpl_intelligence/eval/runner.py` | script | `run_gw_evaluation()` and `run_backtest()` — orchestrates eval against briefing JSON and DB ground truth. |
| `src/fpl_intelligence/eval/schema.py` | script | Pydantic models for eval output: `BinStats`, `GwEvalResult`, `EvaluationReport`. |
| `src/fpl_intelligence/models/__init__.py` | script | Re-exports briefing model classes. Does not re-export `OvrSignalOutput`. |
| `src/fpl_intelligence/models/briefing.py` | script | Pydantic models for output: `Briefing`, `BriefingMeta`, `BriefingContext`, `Signals`, `SignalItem`, `OvrSignalOutput`, `MinutesFilter`, and associated enums. |
| `src/fpl_intelligence/models/pipeline.py` | script | Pydantic models for pipeline intermediates: `GwContext`, `MetricsDataset`, `FeaturesDataset`, `FilteredPool`, `BaseSignalOutputs`, `WeightedSignalOutputs`, `RunResult`. |
| `src/fpl_intelligence/pipeline/__init__.py` | script | Re-exports all step functions and `run_gw`. |
| `src/fpl_intelligence/pipeline/runner.py` | script | `run_gw()` — orchestrates all 11 steps in order for a single gameweek. Validates required tables, builds context, runs steps, writes briefing JSON. |
| `src/fpl_intelligence/pipeline/steps.py` | script | Implements: `validate_data_freshness`, `load_gw_context`, `compute_metrics_batch`, `compute_features_batch`, `apply_minutes_filter`, `compute_signals_base`, `apply_context_weighting`, `assemble_briefing`, plus stubs for `generate_editorial_brief` and `log_run`. |

### `tests/`

| Path | Type | Description |
|------|------|-------------|
| `tests/__init__.py` | script | Empty init. |
| `tests/test_briefing_models.py` | test | Contract tests for Pydantic briefing models. Loads test cases from `docs/contracts/test_cases.json`. |
| `tests/test_db_integration.py` | test | In-memory SQLite integration tests for `validate_data_freshness` and `fetch_player_metrics`. |
| `tests/test_eval.py` | test | Unit tests for eval module (ranking, metrics, schema). No DB or files. |
| `tests/test_pipeline_e2e.py` | test | End-to-end `run_gw()` tests with a seeded 60-player SQLite file. |
| `tests/test_player_gameweek_spine_refactor.py` | test | Verifies refactored spine builder produces identical output to the legacy implementation. |
| `tests/test_player_gameweek_state.py` | test | Tests `build_player_gameweek_state()` — DGW/SGW derivation, home/away, immutability of input. |
| `tests/test_player_gameweek_v1.py` | test | Tests `build_player_gameweek_v1`, `validate_source_tables`, and `define_initial_state_variables`. |
| `tests/test_runner_stubs.py` | test | Verifies pipeline steps execute, stubs raise `NotImplementedError`, all functions have type annotations. |
| `tests/test_sensitivity.py` | test | Input perturbation, determinism, and signal responsiveness tests via `run_gw()`. |
| `tests/test_steps_fixes.py` | test | Tests `robust_zscore` outlier resistance, position-grouped ownership_z, top-N truncation post-weighting, direction derivation, signal status types, degenerate signal detection. |

---

## STEP 2 — NOTEBOOKS AUDIT

### `analysis/notebooks/00_spine_validation.ipynb`

**What it does:** Loads the player_gameweek_spine from the live DB, validates structural integrity (null primary keys, duplicate `(player_id, gameweek)` pairs, misaligned list-field lengths), then prints dataset overview (total rows, unique players, unique GWs, rows per GW), aggregation sanity checks for `minutes`, `starts`, `total_points`, DGW structure (distribution of fixture list lengths), join integrity (null rates on four columns), and ordering validation for multi-fixture rows.

**Data read:** `players`, `player_histories`, `fixtures` via `build_player_gameweek_spine(DB_PATH)` (`~/.fpl/fpl.db`).

**Data produced:** Print/display outputs only. No files written.

**Status:** UNKNOWN. Cells have no saved outputs. Cannot confirm run-to-end without execution. The spine builder and all imported modules work correctly in tests, so the notebook likely runs cleanly against a valid DB.

---

### `analysis/notebooks/02_state_descriptive_analysis.ipynb`

**What it does:** Loads spine and state, merges with `total_points`, then computes grouped means, standard deviations, and counts of `total_points` conditioned on `fixture_context`, `fixture_count`, `home_away_profile`, `minutes` quantile bins, `starts`, and cross-conditions. Uses hardcoded thresholds `> 60` and `<= 30` for minutes subsets. Purely observational by declared boundary rule.

**Data read:** `players`, `player_histories`, `fixtures` via `build_player_gameweek_spine` and `build_player_gameweek_state`.

**Data produced:** Display outputs only. No files written.

**Status:** UNKNOWN. No saved outputs. Notebook numbered `02`, implying a `01` is missing.

---

### `analysis/notebooks/03_stability_analysis.ipynb`

**What it does:** Extends the descriptive analysis with variance stability measures — coefficient of variation by condition, sample size proportions, quartile spread, gameweek-level mean stability, and extreme value influence (mean with vs. without top 1% of points). Covers `fixture_context`, `fixture_count`, and `home_away_profile`. Purely observational.

**Data read:** Same as notebook 02.

**Data produced:** Display outputs only. No files written.

**Status:** UNKNOWN. No saved outputs.

---

## STEP 3 — SCRIPTS AUDIT

### `main.py`

**What it does:** CLI entry point. Accepts `--gw` (required), `--db` (default `~/.fpl/fpl.db`), `--output-dir` (default `data/briefs`), `--log-path` (default `data/logs/runs.jsonl`). Calls `run_gw()` and prints the result.

**Entry point:** Yes. `if __name__ == "__main__": main()` with argparse.

**Data read:** fpl.db at `--db` path.

**Data produced:** `gw_{N}_briefing.json` in `--output-dir`.

**Status:** BROKEN. `run_gw()` calls `load_gw_context()` which calls `player_repo.fetch_current_gw()`, a function that does not exist in `src/fpl_intelligence/db/player_repo.py`. Execution fails with `AttributeError` at step 3 of the pipeline.

---

### `validation.py`

**What it does:** Defines `validate_pipeline_output(features, briefing, gw, gw_contexts)`. Runs 5 checks: (1) eligible player count >= 50, (2) score range >= 0.5, (3) warning if DGW players average rank > 80, (4) both undervalued and overvalued lists must be non-empty, (5) warning if any of {GK, DEF, MID, FWD} missing from top 15. Returns `ValidationResult(passed, warnings, errors)`.

**Entry point:** No. Module only. Called by `pipeline/runner.py`.

**Data read:** In-memory only (function arguments).

**Data produced:** `ValidationResult` dataclass.

**Status:** WORKING. All related tests pass.

---

### `analysis/player_gameweek_v1.py`

**What it does:** Defines the `player_gameweek_v1` curated dataset (13 columns, `(player_id, gameweek)` grain). Contains `validate_source_tables()` which checks schema, primary keys, referential integrity, and coverage. Contains `build_player_gameweek_v1()` and `define_initial_state_variables()` which compute `recent_starts` (rolling 3-GW), `minutes_trend`, `home_away_flag`, and `fixture_context`.

**Entry point:** No. Module only.

**Data read:** fpl.db via `analysis/dal/player_repo.py`.

**Data produced:** DataFrames. No files written.

**Status:** WORKING. All 4 tests in `test_player_gameweek_v1.py` pass.

---

### `analysis/curated/player_gameweek_spine.py`

**What it does:** Builds `player_gameweek_spine` — merges staging players, histories, and fixtures into one row per `(player_id, gameweek)`, aggregating multi-fixture rows into list columns (`fixture_ids`, `opponent_team_ids`, `was_home_flags`). Sorts by kickoff_time before aggregation for deterministic list ordering. Validates via `validate_player_gameweek_spine()` before returning.

**Entry point:** No. Module only.

**Data read:** fpl.db via staging layer.

**Data produced:** DataFrame. No files written.

**Status:** WORKING. Tests in `test_player_gameweek_spine_refactor.py` confirm exact equivalence to legacy implementation.

---

### `analysis/state/player_gameweek_state.py`

**What it does:** Takes the spine DataFrame and derives: `fixture_count` (len of `fixture_ids`), `fixture_context` (BGW/SGW/DGW, or "DGW" for count > 2), `home_away_profile` (HOME/AWAY/MIXED), and carries `minutes` and `starts`. Validates row count and fixture_count consistency against spine.

**Entry point:** No. Module only.

**Data read:** spine DataFrame (in-memory).

**Data produced:** DataFrame with 7 columns.

**Status:** WORKING. Tests in `test_player_gameweek_state.py` pass.

---

### `analysis/dal/player_repo.py`

**What it does:** Data access layer for the analysis layer. The declared SQL boundary. Returns DataFrames from `get_players`, `get_fixtures`, `get_all_player_histories`, and `get_fixtures_full`. Delegates to `analysis/source/` functions.

**Entry point:** No. Module only.

**Data read:** fpl.db.

**Data produced:** DataFrames.

**Status:** WORKING.

---

### `src/fpl_intelligence/db/player_repo.py`

**What it does:** Repository layer for the pipeline. Contains `validate_data_freshness()` — checks row count and `ingested_at` age for a given GW. Contains `fetch_player_metrics()` — SQL join across `players`, `player_histories`, and `fixtures` returning per-player aggregates for a lookback window. Does NOT contain `fetch_current_gw()`.

**Entry point:** No. Module only.

**Data read:** fpl.db.

**Data produced:** None (validation) or list of tuples.

**Status:** INCOMPLETE. `fetch_current_gw()` is called by `steps.load_gw_context()` but is not implemented. All other functions work correctly (4 DB integration tests pass).

---

### `src/fpl_intelligence/pipeline/steps.py`

**What it does:** Implements all named pipeline steps. `load_gw_context()` calls `fetch_current_gw()` (missing). All other steps — `compute_metrics_batch`, `compute_features_batch`, `apply_minutes_filter`, `compute_signals_base`, `apply_context_weighting`, `assemble_briefing` — are implemented and tested. `generate_editorial_brief()` and `log_run()` are confirmed stubs that raise `NotImplementedError`.

**Entry point:** No. Module only.

**Data read:** fpl.db for metrics; DataFrames passed between steps.

**Data produced:** Pipeline intermediates and `Briefing`.

**Status:** BROKEN at `load_gw_context` (missing dependency). All other steps: WORKING.

---

### `src/fpl_intelligence/pipeline/runner.py`

**What it does:** `run_gw()` — orchestrates 11 steps in order. Validates required tables (`players`, `fixtures`, `player_histories`) before connecting. Builds gameweek context, loads GW context (step that fails), computes metrics → features → pool → signals → weighting → briefing → validation → writes JSON. Returns `RunResult`.

**Entry point:** No. Called by `main.py`.

**Data read:** fpl.db.

**Data produced:** `gw_{N}_briefing.json`.

**Status:** BROKEN. Fails at step 3 (`load_gw_context`) due to missing `fetch_current_gw`. Consequently all 4 e2e tests and all 3 sensitivity tests fail.

---

### `src/fpl_intelligence/eval/runner.py`

**What it does:** `run_gw_evaluation()` — loads signal items from a briefing JSON, loads ground truth from DB (`player_histories` where `minutes > 0` for GW t+1), constructs evaluation set (intersection), computes Spearman, precision@k (5, 10, 20), churn@k, temporal stability, and calibration bins. `run_backtest()` — runs over a GW window, aggregates metrics.

**Entry point:** No. No CLI exposes it.

**Data read:** Briefing JSON files, fpl.db.

**Data produced:** `EvaluationReport` Pydantic model. No files written.

**Status:** UNKNOWN. The module is fully implemented. No test exercises it against real data. No entry point exposes it to the user.

---

## STEP 4 — DATABASE AUDIT

**Connection method:** `sqlite3.connect(str(Path("~/.fpl/fpl.db").expanduser()))` as defined in `src/fpl_intelligence/config.py:3`.

**Connection result:** Successful.

---

### `players`

| Attribute | Value |
|-----------|-------|
| Row count | 829 |
| Key columns used by pipeline | `id`, `web_name`, `element_type`, `team` |
| Total columns | 101 |
| GW coverage | N/A (current-season snapshot) |
| Nulls | None in key columns |

**Description:** One row per player registered in the current FPL season. Contains season-aggregate stats, pricing data, ownership, form, expected goals, transfer data, status, and set-piece order. The pipeline uses 4 of 101 columns. Columns available but unused: `status`, `chance_of_playing_next_round`, `chance_of_playing_this_round`, `now_cost`, `ep_next`, `news`.

---

### `fixtures`

| Attribute | Value |
|-----------|-------|
| Row count | 380 |
| Key columns used by pipeline | `id`, `event`, `team_h`, `team_a` |
| Total columns | 17 |
| GW coverage (event) | 1–38 (all 38 GWs) |
| Nulls | 1 row with `event IS NULL` (fixture id=307, team_h=13, team_a=8) |

**Description:** One row per scheduled fixture for the 2025/26 season. Includes kickoff time, scores, difficulty ratings, and completion flags. One fixture has a NULL event column — this is the only NULL in the table.

---

### `player_histories`

| Attribute | Value |
|-----------|-------|
| Row count | 25,732 |
| Key columns used by pipeline | `element_id`, `round`, `fixture`, `total_points`, `starts`, `selected`, `was_home`, `ingested_at` |
| Total columns | 42 |
| GW coverage (round) | 1–33 |
| Latest `ingested_at` | 2026-04-23T17:57:51 |
| Nulls | None in any column |

**Description:** One row per player per fixture played. Aggregates match statistics, expected metrics, transfer data, ownership (`selected`), and an `ingested_at` timestamp. The pipeline uses this table for lookback-window aggregation. Note: column is named `round` in the DB; the pipeline comments note the spec said `event`.

---

### `gameweeks`

| Attribute | Value |
|-----------|-------|
| Row count | 25,566 |
| Key columns | `element_id`, `round` |
| Total columns | 30 |
| GW coverage | Not inspected in detail |
| Nulls | Not inspected |

**Description:** Similar in structure to `player_histories` but lacks `fixture`, `was_home`, `kickoff_time`, `team_h_score`, `team_a_score`, `value`, `selected`, `transfers_*`, and `ingested_at` (per row). Not used by any code in this project.

---

### `teams`

| Attribute | Value |
|-----------|-------|
| Row count | 20 |
| Total columns | 21 |
| Nulls | Not inspected |

**Description:** One row per Premier League team. Contains strength ratings, form, league table position. Not queried by any code in this project.

---

### `events`

| Attribute | Value |
|-----------|-------|
| Row count | 38 |
| Total columns | 29 |
| Current GW | `id=33`, `is_current=1`, `finished=1` |

**Description:** One row per gameweek. Contains deadline time, average score, most-captained player, chip plays, and flags (`is_current`, `is_next`, `is_previous`). `load_gw_context()` in `steps.py` references `fetch_current_gw()` which should query this table, but the function is not implemented.

---

### `_metadata`

| Attribute | Value |
|-----------|-------|
| Row count | 3 |
| Keys present | `last_successful_run_at`, `total_players`, `current_gameweek` |
| `current_gameweek` value | `33` |
| `last_successful_run_at` | `2026-04-23T17:56:24` |

**Description:** fpl-ingest run metadata. Contains the current gameweek number. Not queried by this project despite being the natural source for `fetch_current_gw`.

---

### `_runs`

| Attribute | Value |
|-----------|-------|
| Row count | 4 |

**Description:** fpl-ingest pipeline run log with stage names, counts, and status. Not used by this project.

---

### `element_types`

| Attribute | Value |
|-----------|-------|
| Row count | 4 |

**Description:** GK, DEF, MID, FWD position definitions. Not queried by this project; the mapping is hardcoded in `steps.py`.

---

### `fixture_stats`

| Attribute | Value |
|-----------|-------|
| Row count | 22,826 |
| Key columns | `fixture_id`, `identifier`, `element`, `value`, `side` |

**Description:** Per-player per-fixture event-level stats (goals, assists, bonus points, etc.). Not used by this project.

---

## STEP 5 — OUTPUT AUDIT

No output files exist anywhere in the project.

| Expected path | Referenced in | Status |
|---------------|--------------|--------|
| `data/briefs/gw_{N}_briefing.json` | `main.py` default `--output-dir` | Does not exist. `data/` directory does not exist. |
| `data/logs/runs.jsonl` | `main.py` default `--log-path` | Does not exist. |
| `output/` | `.gitignore` | Does not exist. |
| `logs/` | `.gitignore` | Does not exist. |

The pipeline has never been run successfully against the live database (confirmed by absence of any briefing files and by the broken `fetch_current_gw` dependency).

---

## STEP 6 — WHAT LIVES ONLY IN CODE

### Hardcoded constants in `src/fpl_intelligence/config.py`

| Constant | Value | Location | Why it matters |
|----------|-------|----------|----------------|
| `DB_PATH` | `~/.fpl/fpl.db` | `config.py:3` | Single definition of the DB location. All consumers import this. |
| `MINUTES_FILTER_LOOKBACK` | `6` | `config.py:5` | Number of GWs in the lookback window for starts aggregation. A TODO comment notes the name may be wrong. Affects SQL, start_rate calculation, and eligibility threshold derivation. |
| `DGW_DIVERGENCE_WEIGHT` | `1.5` | `config.py:7` | Multiplier on `mispricing_score` for DGW players. No documentation of how 1.5 was chosen. |
| `OVR_TOP_N` | `20` | `config.py:8` | Max items in undervalued/overvalued lists after weighting. No rationale documented. |
| `MIN_EVAL_POOL_SIZE` | `20` | `config.py:9` | Minimum bin sample count for calibration. At current settings (OVR_TOP_N=20, n_bins=10), calibration bins are always empty. Documented in a code comment but not externally. |

### Hardcoded thresholds in `src/fpl_intelligence/pipeline/steps.py`

| Item | Value | Location | Why it matters |
|------|-------|----------|----------------|
| Nailed threshold | `0.75` | `steps.py:221` | start_rate >= 0.75 → nailed bucket. Not in config. A TODO notes unclear rationale. |
| Rotation threshold | `0.40` | `steps.py:222` | start_rate >= 0.40 → rotation bucket; also the eligibility lower bound. Not in config. |
| Min starts derivation | `math.ceil(0.40 * MINUTES_FILTER_LOOKBACK)` | `steps.py:163` | Eligibility threshold as raw start count (= 3 for lookback=6). Inline formula, not a named constant. |
| MAD scaling factor | `1.4826` | `steps.py:53` | Normal-distribution consistency factor for robust z-score. Not a named constant. |
| Data freshness default | `max_age_hours=6` | `steps.py:62` / `db/player_repo.py:12` | Maximum allowed age for `ingested_at`. Function default only, not a config constant. |
| Element type mapping | `{1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}` | `steps.py:39` | Hardcoded in the pipeline. Same mapping is implicitly assumed across the analysis layer. No shared constants file. |

### Hardcoded thresholds in `validation.py`

| Item | Value | Location | Why it matters |
|------|-------|----------|----------------|
| Minimum eligible players | `50` | `validation.py:50` | Pipeline raises if fewer than 50 eligible players for the GW. No documented basis. |
| Score range minimum | `0.5` | `validation.py:66` | Signal is flagged degenerate if `max(scores) - min(scores) < 0.5`. No documented basis. |
| DGW rank warning threshold | `80` | `validation.py:87` | Warning if average rank of DGW players exceeds 80. No documented basis. |
| Position coverage check | `top_15 = ranked[:15]` | `validation.py:103` | Checks all 4 positions appear in top 15. Threshold of 15 not in config. |
| Expected positions | `{"GK", "DEF", "MID", "FWD"}` | `validation.py:104` | Hardcoded set. |

### Hardcoded values in `analysis/player_gameweek_v1.py`

| Item | Value | Location | Why it matters |
|------|-------|----------|----------------|
| Rolling window for `recent_starts` | `3` | `player_gameweek_v1.py:312` | Rolling sum over 3 GWs. Not in config. |
| `fixture_context` catch-all | `"OTHER"` | `player_gameweek_v1.py:328` | fixture_count > 2 → "OTHER". Inconsistent with `player_gameweek_state.py` which returns "DGW" for the same case. |

### Hardcoded values in notebooks

| Item | Value | Notebook | Why it matters |
|------|-------|----------|----------------|
| High-minutes threshold | `> 60` | `02_state_descriptive_analysis.ipynb` | Used as a minutes subset cutoff. Not defined as a constant anywhere. |
| Low-minutes threshold | `<= 30` | `02_state_descriptive_analysis.ipynb` | Used as a low-minutes noise zone cutoff. Not defined as a constant anywhere. |

### Structural inconsistency

`player_gameweek_v1.py` returns `"OTHER"` for `fixture_count > 2`. `player_gameweek_state.py` returns `"DGW"` for the same case. Both are active code paths. The two representations cannot be reconciled without clarification.

---

## STEP 7 — AUDIT SUMMARY

### WHAT EXISTS AND WORKS

- `analysis/curated/player_gameweek_spine.py` (`build_player_gameweek_spine`): produces validated DataFrame; tested and confirmed equivalent to legacy implementation.
- `analysis/state/player_gameweek_state.py` (`build_player_gameweek_state`): derives fixture context and home/away profile; tested.
- `analysis/player_gameweek_v1.py`: full curated dataset, source table validation, and state variable derivation; tested.
- `analysis/dal/player_repo.py` and `analysis/source/*.py`: raw and DAL DB access; working.
- `analysis/contracts/*.py`: schema and validation contracts; tested.
- `analysis/staging/*.py`: staging transforms; tested as part of spine.
- `src/fpl_intelligence/models/briefing.py`: Pydantic validation for Briefing output; tested.
- `src/fpl_intelligence/models/pipeline.py`: Pydantic models for pipeline intermediates; tested.
- `src/fpl_intelligence/eval/` (metrics, ranking, schema): all 26 unit tests pass.
- `src/fpl_intelligence/pipeline/steps.py`: all implemented steps (excluding `load_gw_context` and the two stubs) work correctly per unit and integration tests.
- `src/fpl_intelligence/db/player_repo.py` (`validate_data_freshness`, `fetch_player_metrics`): working; 4 integration tests pass.
- `validation.py` (`validate_pipeline_output`): working; tested in `test_steps_fixes.py`.
- Test suite: 79 of 87 tests pass.

### WHAT EXISTS BUT IS BROKEN OR INCOMPLETE

| Item | Failure point |
|------|--------------|
| `src/fpl_intelligence/db/player_repo.py` | Missing `fetch_current_gw()`. Called by `steps.load_gw_context()`. Causes `AttributeError` at step 3 of `run_gw()`. |
| `main.py` | BROKEN as a consequence. Cannot produce any output. |
| `src/fpl_intelligence/pipeline/runner.py` | BROKEN as a consequence. All 4 e2e tests fail. |
| `tests/test_sensitivity.py` | All 3 tests fail as a consequence of the above. |
| `tests/test_briefing_models.py` | Fails at collection. Requires `docs/contracts/test_cases.json` which does not exist anywhere in the project. |
| `src/fpl_intelligence/pipeline/steps.py` — `generate_editorial_brief()` | Intentional stub. Raises `NotImplementedError`. |
| `src/fpl_intelligence/pipeline/steps.py` — `log_run()` | Intentional stub. Raises `NotImplementedError`. |
| `src/fpl_intelligence/eval/runner.py` | Fully implemented but unreachable. No CLI entry point, no test against real data. |
| `data/briefs/`, `data/logs/` directories | Do not exist. The pipeline has never produced output. |

### WHAT IS ASSUMED BUT MISSING

| Item | Where assumed |
|------|--------------|
| `fetch_current_gw()` in `src/fpl_intelligence/db/player_repo.py` | Called by `steps.load_gw_context()` at `steps.py:75`. |
| `docs/contracts/test_cases.json` | Required by `tests/test_briefing_models.py:20`. |
| `analysis/experiments/hypothesis_registry.md` | Referenced in `README.md` as mandatory location for all hypotheses. |
| A notebook `01` | Numbering jumps from `00_spine_validation` to `02_state_descriptive_analysis`. |
| A CLI or script entry point for `src/fpl_intelligence/eval/runner.py` | Module is complete; no way to invoke it outside of tests. |
| Config constants for: nailed/rotation thresholds, `max_age_hours`, min eligible count, score range min, DGW rank threshold, top-15 coverage threshold | These are all hardcoded inline. |

### OPEN QUESTIONS FOR THE ANALYST

1. **`fetch_current_gw` implementation**: Two natural sources exist in the DB — `_metadata` (key `current_gameweek`, value `33`) and `events` (row with `is_current=1`, `id=33`). Which source should the implementation use?

2. **`gameweeks` table**: 25,566 rows with per-player per-GW stats. No `fixture` column, no per-row `ingested_at`. Its relationship to `player_histories` is ambiguous — is it a different aggregation of the same data, or a separate feed? No code in this project queries it.

3. **Notebook 01**: Is it missing, in progress, or intentionally absent?

4. **Fixture id=307 with NULL event** (team_h=13 vs team_a=8): Is this a known ingest artifact or a data error? No code guards against NULL events, though queries filtering `WHERE event = ?` would implicitly exclude it.

5. **`fixture_context` "OTHER" vs "DGW"** for fixture_count > 2: `player_gameweek_v1.py` returns `"OTHER"`; `player_gameweek_state.py` returns `"DGW"`. Which is correct? Is this intentional divergence or a bug?

6. **`generate_editorial_brief()` and `log_run()`**: Are these planned features with a delivery timeline, or permanently out of scope?

7. **Calibration bins always empty**: With `OVR_TOP_N=20`, `n_bins=10`, and `n_min=20`, every calibration call returns an empty list. A code comment documents this as "correct behaviour." Is `MIN_EVAL_POOL_SIZE` intended to be reduced, or is calibration a future feature that requires a larger signal pool?

8. **Two separate data access layers**: `analysis/dal/` (pandas-based, for notebooks and analysis scripts) and `src/fpl_intelligence/db/` (tuple-based, for the pipeline). Are these intended to remain separate indefinitely, or is convergence planned?
