# Execution Queue

**Status:** All items complete as of May 2026  
**Rule:** No code change without a corresponding failing test committed first  
**Prerequisite reading:** [docs/architecture/DAL_CONTRACT.md](../architecture/DAL_CONTRACT.md)

This document is the ordered implementation record for all six stabilization waves. It is structured as actionable engineering work items, not narrative documentation.

---

## Prerequisites — before Wave 1 begins

### P-1: Create the golden test fixture database

A small, controlled SQLite DB with known values used throughout all test waves.

**Required contents:**
- At least 3 players
- At least 5 GWs
- One player with a BGW in GW 3
- One player with a DGW in GW 4
- One player who transfers teams between GW 2 and GW 3 (mid-season transfer)
- One DGW player with different fixture difficulties in the two fixtures
- Correct GW context (events table) for all GWs
- Fixture data where `goals_conceded` differs across the two DGW fixtures

**Location:** `tests/fixtures/test.db` — schema and creation script version-controlled.  
Any test asserting a specific numerical value must use this DB.

**Blast radius:** Zero — setup only.

---

### P-2: Write failing tests for SC-1, SC-2, SC-3, SC-4 before touching any source files

Each failing test is committed as its own commit before the corresponding fix. The failure is the proof that the violation exists.

**Blast radius:** Zero — read-only tests.

---

## Wave 1 — Corruption Blockers

**Objective:** Eliminate all silent analytical corruption. No lens study runs until this wave is complete and all tests pass.  
**Risks addressed:** SC-1, SC-2, SC-3, SC-4, SC-11  
**Validation gate:** All five failing tests committed before any source changes; all fix tests pass after.

---

### SC-1 — Fix `minutes_trend` look-ahead leak

**File:** `dal/state/player_gameweek_state.py`  
**Blast radius:** Medium — invalidates all prior `minutes_trend` values. All prior LENS-AVAIL analysis using `minutes_trend` must be discarded.

**Change:** In `_compute_minutes_trend`, replace:
```python
last3 = minutes_series.rolling(3, min_periods=3).mean()
```
with:
```python
last3 = minutes_series.shift(1).rolling(3, min_periods=3).mean()
```

Both `last3` and `prior3` windows must use the lag-1 convention. `prior3 = minutes_series.shift(3).rolling(3, min_periods=3).mean()` is already shifted by 3 — verify the shift is not double-applied.

**Test before fix (must fail after fix to confirm look-ahead existed):**
```
test_minutes_trend_includes_current_gw_before_fix:
    - Spine: player X has minutes = [0, 0, 0, 90] at GWs 1-4
    - Assert: GW 4's minutes_trend is NOT null (look-ahead present)
```

**Tests after fix:**
```
test_minutes_trend_lag1_convention:
    - Spine: player X has minutes = [0, 0, 0, 90] at GWs 1-4
    - Assert: GW 4's minutes_trend is None (shift(1) means GW 4 sees GWs 1,2,3 = [0,0,0])
    - Assert: GW 5's minutes_trend reflects the 90 at GW 4
    - Assert: minutes_trend is None for GW 1 for all players

test_all_rolling_windows_use_shift1:
    - For each column in _ROLL_COLS: assert roll3 for GW N uses only GW 1..N-1
    - Use golden DB where GW N has an anomalous value; assert it does not appear in GW N's roll3/roll5
```

---

### SC-4 — Derive `opponent_team_id` in intermediate layer

**File:** `dal/intermediate/player_fixture.py`  
**Blast radius:** Low — additive column.

**Change:** In `_resolve_player_side_context`, before dropping `home_team_id` and `away_team_id`:
```python
opponent_team_id = df["away_team_id"].where(is_home, df["home_team_id"])
df["opponent_team_id"] = opponent_team_id.astype("int64")
```

Retain `opponent_team_id` in the output of `get_player_fixture_base()`. Drop `home_team_id` and `away_team_id` after derivation as before. Update `DAL_CONTRACT.md` to declare `opponent_team_id` as a retained intermediate column before committing this change.

**Test before fix:**
```
test_opponent_team_id_raises_keyerror_before_fix:
    - Call build_player_opponent_defensive_context(player_fixture_base)
    - Assert KeyError is raised on "opponent_team_id"
```

**Tests after fix:**
```
test_opponent_team_id_present_in_player_fixture_base:
    - Assert "opponent_team_id" in get_player_fixture_base(db_path).columns

test_opponent_team_id_correctness:
    - For a home player in fixture F: assert opponent_team_id == away_team_id in F
    - For an away player in fixture F: assert opponent_team_id == home_team_id in F

test_opponent_team_id_never_null:
    - Assert player_fixture_base["opponent_team_id"].notna().all()
```

---

### SC-3 — Fix `goals_conceded` aggregation

**File:** `dal/state/opponent_context.py`  
**Prerequisite:** SC-4 must be complete.  
**Blast radius:** Medium — invalidates all prior DGW defensive context values. Regenerate opponent defensive context.

**Change:** In `_build_team_defensive_records`:
```python
# Before
goals_conceded=("goals_conceded", "mean")

# After
goals_conceded=("goals_conceded", "sum")
```

Rationale: goals conceded is additive. A team that conceded 1 goal in each of two DGW fixtures conceded 2 goals that GW, not 1. Averaging underestimates defensive weakness for DGW teams and creates a systematic bias in rolling opponent defensive metrics.

**Test before fix:**
```
test_goals_conceded_aggregation_uses_mean_before_fix:
    - Golden DB: team A conceded 1 goal in each DGW fixture
    - Assert team_def["goals_conceded"] == 1.0 (must fail after fix)
```

**Tests after fix:**
```
test_goals_conceded_aggregation_sums_across_fixtures:
    - Golden DB: team A conceded 1 goal in each DGW fixture
    - Assert team_def["goals_conceded"] == 2

test_goals_conceded_sgw_unchanged:
    - Golden DB: team B conceded 2 goals in a SGW
    - Assert team_def["goals_conceded"] == 2
```

---

### SC-2 — Fix BGW team_id temporal leakage

**Files:** `dal/curated/player_gameweek_spine.py`  
**Blast radius:** High — invalidates all BGW team_id values for transferred players. Regenerate the spine and any derived outputs.

**Contract decision (update DAL_CONTRACT.md first):** BGW rows carry the player's team as of the most recent non-BGW GW before the BGW — not the player's latest-known team across all GWs.

**Change:** In `_apply_bgw_defaults`, build `player_info` only from non-BGW rows. For each BGW row, look up the player's team from the most recent non-BGW GW at or before the current GW (backward merge / merge-as-of). The current implementation uses `sort_values("gw", ascending=False).drop_duplicates("player_id", keep="first")`, which returns the latest GW regardless of when the BGW occurs — this must change to a per-BGW lookup.

**Tests before fix:**
```
test_bgw_team_id_uses_latest_gw_before_fix:
    - Golden DB: player P at team A in GW 1-2, transfers to team B, GW 3 is BGW
    - Assert GW 3 BGW row has team_id == B (wrong — uses latest; must fail after fix)
```

**Tests after fix:**
```
test_bgw_team_id_uses_pre_bgw_team:
    - Golden DB: player P at team A in GW 1-2, BGW in GW 3, plays for team B from GW 4
    - Assert GW 3 BGW row has team_id == A (pre-transfer team)

test_bgw_team_id_never_null:
    - Assert team_id is not null for any BGW row

test_bgw_team_id_post_transfer:
    - Golden DB: player Q at team A in GW 1, transfers, BGW in GW 5 while at team B
    - Assert GW 5 BGW row has team_id == B (post-transfer team — correct for that GW)
```

---

### SC-11 — Replace missing GW context warning with immediate raise

**File:** `dal/curated/player_gameweek_spine.py`  
**Blast radius:** Low — failure mode change only.

**Change:** Replace the `logger.warning(...)` block for `missing_gws` with:
```python
if missing_gws:
    raise DALContractViolation(
        f"Events table is missing {len(missing_gws)} GW(s) required by fixture history: "
        f"{sorted(missing_gws)}. Spine cannot be built with incomplete GW context.",
        layer="curated",
        validation="build_player_gameweek_spine",
        n_violations=len(missing_gws),
        error_code="ROW_COUNT",
    )
```

**Tests:**
```
test_missing_gw_context_raises_immediately:
    - Mock get_gameweek_context to return events for GWs 1-4 only
    - Mock get_player_fixture_base to include fixture data for GW 5
    - Assert DALContractViolation raised at spine build, not at null semantics validation
    - Assert exception message names GW 5 as missing

test_missing_gw_context_does_not_return_partial_result:
    - Same setup; assert no DataFrame is returned
```

---

### Wave 1 validation checklist

- [ ] All 5 failing tests committed before any Wave 1 code changes
- [ ] All 5 fix tests pass after implementation
- [ ] All pre-existing DAL tests still pass
- [ ] Full spine build from real DB succeeds
- [ ] Full state build from real DB succeeds
- [ ] Spot-check: known mid-season transfer player has correct BGW team_id
- [ ] Spot-check: GW N's `minutes_trend` is null when player played 90 min in GW N for first time

**Rollback:** All Wave 1 changes are function-scoped. Any change can be reverted by file without affecting others. `opponent_context.py` is not integrated into the spine build — its fix can be reverted independently.

---

## Wave 2 — Contract Enforcement

**Objective:** Ensure every declared contract is enforced in the live build path.  
**Risks addressed:** SC-5, SC-6, SC-8, V-1, V-2, V-3

---

### SC-8 — Add GW context columns to `DTYPES`

**File:** `dal/curated/contracts.py`  
**Blast radius:** Low — additive to contract.

Add to `DTYPES`:
```python
"deadline_time":        "datetime64[ns]",
"finished":             "boolean",
"is_previous":          "boolean",
"is_live":              "boolean",
"is_next":              "boolean",
"average_entry_score":  "Float64",
"highest_score":        "Float64",
"transfers_made":       "int64",
```

Add to `NULL_RULES`:
```python
"deadline_time":        "never_null",
"finished":             "never_null",
"is_previous":          "never_null",
"is_live":              "never_null",
"is_next":              "never_null",
"transfers_made":       "never_null",
"average_entry_score":  "always_nullable",
"highest_score":        "always_nullable",
```

**Tests:**
```
test_all_spine_cols_present_in_dtypes:
    - Assert set(SPINE_COLS) == set(DTYPES.keys())

test_all_spine_cols_present_in_null_rules:
    - Assert set(SPINE_COLS) == set(NULL_RULES.keys())

test_gw_context_columns_have_correct_dtypes_in_built_spine:
    - Assert spine["finished"].dtype == "boolean"
    - Assert spine["deadline_time"].dtype == "datetime64[ns]"
```

---

### V-1, V-2 — Call `validate_column_contract` and `validate_row_completeness` in build

**File:** `dal/curated/player_gameweek_spine.py`  
**Blast radius:** Low — validation tightening.

Full validation call sequence in `_cast_and_validate` after Wave 2:
```python
def _cast_and_validate(result, n_players, n_gws, max_gw):
    for col, dtype in DTYPES.items():
        result[col] = result[col].astype(dtype)
    result = result.reset_index(drop=True)

    validate_column_contract(result, SPINE_COLS, DTYPES)
    validate_grain_uniqueness(result, "player_gameweek_spine")
    validate_row_completeness(result,
        result["player_id"].unique(), sorted(result["gw"].unique()))
    validate_row_count_invariant(result, n_players=n_players, n_gws=n_gws)
    validate_time_continuity(result)
    validate_no_future_data(result, reference_gw=max_gw)
    validate_bgw_correctness(result)
    validate_dgw_correctness(result)
    validate_null_semantics(result, NULL_RULES)

    return result
```

**Tests:**
```
test_validate_column_contract_called_in_spine_build:
    - Monkeypatch validate_column_contract to track calls
    - Run build_player_gameweek_spine
    - Assert exactly one call
```

---

### V-3 — Decouple `invariants.py` from `dal/curated/contracts.py`

**File:** `dal/validation/invariants.py`  
**Blast radius:** Low — refactor of import boundary.

The import `from dal.curated.contracts import PERFORMANCE_COLS` couples the validation layer to the curated layer. Change `validate_no_future_data` to accept `performance_cols` as a parameter:

```python
def validate_no_future_data(
    df: pd.DataFrame,
    gw_col: str = "gw",
    reference_gw=None,
    performance_cols=None,  # caller passes PERFORMANCE_COLS
) -> None:
```

Call sites pass `PERFORMANCE_COLS` explicitly. The validation module imports nothing from `dal/curated/`.

**Tests:**
```
test_validate_no_future_data_importable_without_curated:
    - import dal.validation.invariants without importing dal.curated
    - Assert no ImportError
```

---

### SC-5, SC-6 — Fix nullable type comparisons in validators

**Files:** `dal/validation/semantics.py`, `dal/validation/invariants.py`  
**Blast radius:** Low — validation correctness fix.

**SC-5** (`validate_bgw_correctness`):
```python
# Wrong: pd.NA != 0 returns pd.NA (falsy), silently misses pd.NA values
bad = bgw[bgw[col] != 0]

# Correct: non-null performance on BGW row is the violation
bad = bgw[bgw[col].notna()]
```

**SC-6** (`validate_no_future_data`):
```python
# Wrong: same nullable type issue
bad = future_rows[future_rows[col] != 0]

# Correct: future rows with non-null performance are the violation
bad = future_rows[future_rows[col].notna()]
```

**Test before fix (must demonstrate the bug):**
```
test_bgw_validator_silently_misses_pd_na_before_fix:
    - Build DataFrame with is_bgw=True, total_points=Int64(5)
    - With current code: assert validate_bgw_correctness DOES NOT raise (the bug)
    - After fix: assert validate_bgw_correctness RAISES
```

---

### Wave 2 validation checklist

- [ ] `set(SPINE_COLS) == set(DTYPES.keys())` asserted in a test
- [ ] `set(SPINE_COLS) == set(NULL_RULES.keys())` asserted in a test
- [ ] `validate_column_contract` called in live build
- [ ] `validate_row_completeness` called in live build
- [ ] `validate_bgw_correctness` correctly identifies Int64 non-null violations
- [ ] `invariants.py` imports nothing from `dal/curated/`
- [ ] All Wave 1 tests still pass

---

## Wave 3 — Determinism Hardening

**Objective:** Two runs on the same DB produce byte-identical output regardless of SQLite row storage order.  
**Risks addressed:** D-1, SC-9, F-1, F-2

---

### D-1 — Add ORDER BY to all staging SQL queries

**File:** `dal/staging/transformer.py`  
**Blast radius:** Low — output is equivalent, just deterministically ordered.

`_build_query` must produce ordered results. Canonical ORDER BY per entity:

| Entity | ORDER BY |
|---|---|
| players | `id` |
| player_histories | `element, fixture` |
| fixtures | `id` |
| teams | `id` |
| events | `id` |
| element_types | `id` |

Implementation: add `pk_columns` to each schema YAML and use in `_build_query`:
```python
def _build_query(schema: Schema) -> str:
    source_cols = ", ".join(f'"{col.source}"' for col in schema.columns)
    order_clause = ", ".join(f'"{pk}"' for pk in schema.pk_columns)
    return f'SELECT {source_cols} FROM "{schema.source_table}" ORDER BY {order_clause}'
```

**Tests:**
```
test_staging_sql_contains_order_by:
    - For each entity schema: assert "ORDER BY" in _build_query(schema)

test_staging_output_row_order_is_stable:
    - Call get_staged_players(db_path) twice
    - Assert pd.testing.assert_frame_equal(result1, result2, check_like=False)
```

---

### SC-9, F-1 — Explicit sort before aggregation + FIRST_COLS semantic registry

**Files:** `dal/curated/player_gameweek_spine.py`, `dal/curated/contracts.py`  
**Blast radius:** Low — determinism fix.

In `build_player_gameweek_spine`, sort before aggregation:
```python
df = df.sort_values(["player_id", "gw", "fixture_id"]).reset_index(drop=True)
aggregated = _aggregate_to_gw_grain(df)
```

Add `FIRST_COL_SEMANTICS` to `dal/curated/contracts.py` as specified in `docs/architecture/DAL_CONTRACT.md`.

---

### F-2 — Assert `invariant_per_gw` columns before aggregation

**File:** `dal/curated/player_gameweek_spine.py`  
**Blast radius:** Low — validation addition.

Before `_aggregate_to_gw_grain`:
```python
_assert_invariant_per_gw_columns(df)
```

`_assert_invariant_per_gw_columns` raises `DALContractViolation` if any column declared `invariant_per_gw` has more than one distinct value within any `(player_id, gw)` group.

**Tests:**
```
test_invariant_per_gw_assertion_catches_violation:
    - Construct fixture-grain frame where purchase_price differs across two fixtures for same (player_id, gw)
    - Assert DALContractViolation raised before aggregation

test_full_pipeline_is_reproducible:
    - Run build_player_gameweek_spine(db_path) twice
    - Assert pd.testing.assert_frame_equal(result1, result2, check_like=False)
    - This is the primary determinism regression test; runs on every PR
```

---

### Wave 3 validation checklist

- [ ] Reproducibility test passes (two-run exact equality)
- [ ] `invariant_per_gw` assertion fires correctly on a crafted violation
- [ ] All `FIRST_COLS` entries classified in `FIRST_COL_SEMANTICS`
- [ ] `ORDER BY` present in all 6 entity staging queries
- [ ] All Wave 1 and Wave 2 tests still pass

---

## Wave 4 — Invariant Expansion

**Objective:** Add missing invariants; formalize the state layer contract. Fixes analytical gaps that are not silent corruption but would affect research quality.  
**Risks addressed:** SC-13, SC-7, SC-10, SC-14, SC-15 (documentation)

---

### SC-13 — `fixture_context` three-way label

**File:** `dal/state/player_gameweek_state.py`  
**Blast radius:** Medium — any research filter on `fixture_context == "SGW"` will now correctly exclude BGW rows. All lens notebooks using this filter must be audited.

**Change:**
```python
# Before: BGW rows get "SGW" — incorrect
df["fixture_context"] = df["is_dgw"].map({True: "DGW", False: "SGW"})

# After: three-way classification
conditions = [df["is_bgw"], df["is_dgw"]]
choices = ["BGW", "DGW"]
df["fixture_context"] = np.select(conditions, choices, default="SGW")
```

Update `STATE_COL_CONTRACTS` to declare valid values for `fixture_context` as `{"BGW", "SGW", "DGW"}`.

**Tests:**
```
test_fixture_context_bgw_rows:
    - Build state from spine with known BGW rows
    - Assert fixture_context == "BGW" for all is_bgw==True rows
    - Assert "SGW" does not appear for any is_bgw==True row

test_fixture_context_exhaustive:
    - Assert fixture_context.dropna().isin({"BGW", "SGW", "DGW"}).all()
```

---

### SC-7 — Declare DGW summation semantics for FPL metrics

**Decision:** No code change. DGW summation of `influence`, `creativity`, `threat`, `ict_index` is declared analytically intentional.

**Required action:** Ensure `DAL_CONTRACT.md` states explicitly:
- These columns use `sum` aggregation for DGW
- Consumers comparing across SGW and DGW must normalize: `normalized_influence = influence / fixture_count`

See [docs/decisions/dgw_aggregation_rules.md](../decisions/dgw_aggregation_rules.md).

---

### SC-10 — Document TGW non-support

**Decision:** No code change beyond ensuring the error message in `validate_dgw_correctness` is explicit:
```python
raise DALContractViolation(
    f"fixture_count not in {{0, 1, 2}} for {len(bad_bounds)} rows. "
    f"Triple gameweeks are not supported by the current contract. "
    f"Update DAL_CONTRACT.md before ingesting TGW data.",
    ...
)
```

---

### SC-14 — Expand `validate_xgc_001` to all positions

**File:** `dal/intermediate/opponent_context.py`  
**Blast radius:** Low — validation expansion.

Change:
```python
# Before: GK only
validate_xgc_001(analytics_90[analytics_90["position_code"] == 1])

# After: all positions
validate_xgc_001(analytics_90)
```

The xgc invariance contract — that all 90-minute players in the same team/fixture share the same xgc — should hold for all positions, not just goalkeepers.

---

### SC-15 — Document `min_periods=1` behavior

**Decision:** No code change. Add metadata to `STATE_COL_CONTRACTS` entries:
- `min_obs_for_reliability` communicates the observation count at which the rolling average is statistically established
- This does not change how `min_periods` works — it is metadata for downstream consumers to filter on when computing correlations

---

### State layer contract file

**New file:** `dal/state/contracts.py`

Create `STATE_COL_CONTRACTS` as specified in `docs/architecture/DAL_CONTRACT.md`. Minimum required entries before LENS-AVAIL begins:
- All `_ROLL_COLS` entries with `causality: "lagged"`, correct `warmup_gws`, and `min_obs_for_reliability`
- `fixture_context` with `causality: "contemporaneous"` and `values`
- `minutes_trend` with `causality: "lagged"` and `warmup_gws: 4`

---

### Wave 4 validation checklist

- [ ] `fixture_context` produces "BGW", "SGW", "DGW" — no other values
- [ ] DGW summation semantics documented in `DAL_CONTRACT.md`
- [ ] TGW non-support documented with clear error message
- [ ] `STATE_COL_CONTRACTS` exists with all `_ROLL_COLS` covered
- [ ] All lens studies audited for `fixture_context == "SGW"` filters
- [ ] All previous wave tests still pass

---

## Wave 5 — Architecture Cleanup

**Objective:** Remove structural confusion, fix cross-layer violations, eliminate dead code. No analytical outputs change.  
**Risks addressed:** A-1, A-2, A-3

---

### A-1 — Archive `pipeline/`

**Action:** Move `pipeline/` to `archive/pipeline_legacy/`. It imports from `analysis.source` which does not exist — it fails on import. It is a source of confusion about which implementation is authoritative.

Update `CONTEXT.md` structure table to reflect `dal/` as the sole authoritative DAL.

**Blast radius:** Zero — no live code references this module.

**Test:**
```
test_no_import_from_pipeline:
    - grep dal/ and research/ for "from pipeline" or "import pipeline"
    - Assert zero matches
```

---

### A-2 — Retire `GrainViolationError`

**File:** `dal/exceptions.py`  
**Blast radius:** Low — exception hierarchy cleanup.

Replace all uses of `GrainViolationError` (currently only in `opponent_context.py`) with `DALContractViolation`. Remove `GrainViolationError` from `exceptions.py`.

**Test:**
```
test_grain_violation_error_not_used:
    - grep all .py files for "GrainViolationError"
    - Assert zero matches
```

---

### A-3 — Move `opponent_context.py` to intermediate layer

**Action:** Move `dal/state/opponent_context.py` → `dal/intermediate/opponent_context.py`

The module operates on `player_fixture_base` (intermediate grain). It does not consume the curated spine. Its correct layer is intermediate, not state. Update all imports.

**Blast radius:** Low — module relocation; all imports must be updated.

---

### Wave 5 validation checklist

- [ ] `pipeline/` archived — no remaining imports from it
- [ ] `GrainViolationError` removed — zero usages
- [ ] `opponent_context.py` at intermediate layer — all imports updated
- [ ] All previous wave tests still pass
- [ ] Full spine and state build succeed from real DB

---

## Wave 6 — Observability and Maintainability

**Objective:** Make the DAL fully diagnosable from log output alone without a debugger. Add environment override for test isolation. Add hash-level reproducibility artifact.  
**Risks addressed:** O-1, O-2, O-3, O-4, O-5, O-6

---

### O-1 — Add staging-layer logging

**File:** `dal/staging/transformer.py`

After each `stage()` call returns, log at INFO level:
```
[DAL:staging:{entity}] staged | rows={n} cols={c} elapsed_ms={t}
```

Makes unexpected entity sizes immediately visible (new FPL API field, dropped player, empty fixture table).

---

### O-2 — Elevate team_id correction to AUDIT level

**File:** `dal/intermediate/player_fixture.py`

Change `logger.info(...)` to `logger.info("[AUDIT] ...")` for team_id corrections. AUDIT events are info-level messages with the `[AUDIT]` prefix, suitable for reconciliation review.

---

### O-3 — Populate `layer=` on all `DALContractViolation` raises

Audit every raise site. All raises must include `layer=`. Update `validate_grain_uniqueness` to accept an optional `layer` parameter and pass it through to the exception.

---

### O-4 — `FPL_DB_PATH` environment variable override

**File:** `dal/config.py`
```python
import os
from pathlib import Path

DB_PATH: Path = Path(os.environ.get("FPL_DB_PATH", "~/.fpl/fpl.db")).expanduser()
```

Enables test-time DB override without patching internals.

**Test:**
```
test_fpl_db_path_env_override:
    - Set FPL_DB_PATH to the golden test DB path
    - Assert dal.config.DB_PATH resolves to the test DB
```

---

### O-5 — Hash-level reproducibility artifact

**File:** `dal/reproducibility.py`
```python
import hashlib
import pandas as pd

def compute_spine_fingerprint(df: pd.DataFrame) -> dict:
    row_hashes = pd.util.hash_pandas_object(df, index=True)
    content_hash = hashlib.sha256(row_hashes.values.tobytes()).hexdigest()
    return {
        "sha256": content_hash,
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(df[col].dtype) for col in df.columns},
    }
```

Log the fingerprint at the end of `build_player_gameweek_spine`. In the reproducibility test, assert the fingerprint is identical across two runs.

---

### O-6 — Timing instrumentation

**File:** `dal/curated/player_gameweek_spine.py`

Add `time.perf_counter()` at spine entry and exit:
```
[DAL:curated:spine] build complete | rows=17893 elapsed_ms=1204
```

No performance threshold enforcement — log and trend.

---

### Wave 6 validation checklist

- [ ] `FPL_DB_PATH` override works in test context
- [ ] Spine fingerprint is identical across two runs (logged)
- [ ] All `DALContractViolation` raises include `layer=`
- [ ] Staging logs entity row counts at INFO level
- [ ] team_id corrections use `[AUDIT]` prefix
- [ ] All previous wave tests still pass

---

## Immediate execution order (Wave 1 priority queue)

Ordered strictly by analytical risk. Items 2–3, 4–6, and 7–9 are three independent chains that can proceed in parallel. Item 10 is fully independent. Item 1 must come first.

| # | Item | Files | Prerequisite | Blast radius |
|---|---|---|---|---|
| 1 | Create golden test fixture DB | `tests/fixtures/test.db`, creation script | None | Zero |
| 2 | Write failing test for SC-1 (`minutes_trend` look-ahead) | `tests/state/test_player_gameweek_state.py` | Item 1 | Zero |
| 3 | Fix SC-1 (`minutes_trend` shift(1)) | `dal/state/player_gameweek_state.py` | Item 2 | Medium — invalidates all prior `minutes_trend` |
| 4 | Write failing test for SC-4 (`opponent_team_id` KeyError) | `tests/state/test_opponent_context.py` | Item 1 | Zero |
| 5 | Derive `opponent_team_id` in intermediate layer | `dal/intermediate/player_fixture.py` | Item 4 | Low — additive column |
| 6 | Fix SC-3 (`goals_conceded` sum) | `dal/state/opponent_context.py` | Item 5 | Medium — invalidates DGW defensive context |
| 7 | Write failing test for SC-2 (BGW team_id leakage) | `tests/curated/test_player_gameweek_spine.py` | Item 1 | Zero |
| 8 | Update `DAL_CONTRACT.md` with BGW team_id rule | `dal/DAL_CONTRACT.md` | Item 7 | Zero |
| 9 | Fix SC-2 (BGW team_id uses pre-BGW team) | `dal/curated/player_gameweek_spine.py` | Item 8 | High — invalidates all BGW team_id for transferred players |
| 10 | Fix SC-11 (missing GW context raises, not warns) | `dal/curated/player_gameweek_spine.py` | None | Low — failure mode change only |
