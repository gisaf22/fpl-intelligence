# DAL Stabilization Plan

**Status:** Active  
**Scope:** `dal/` subsystem — all layers  
**Prerequisite:** Read `DAL_CONTRACT.md` before any implementation  
**Rule:** No code changes without the corresponding failing test committed first

---

## What "Stable" Means

The DAL is stable when every call to `build_player_gameweek_spine()` and
`build_player_gameweek_state()` produces output that satisfies all five dimensions
simultaneously:

| Dimension | Definition |
|---|---|
| **Correctness** | Every value at every `(player_id, gw)` cell represents the true historical fact for that player in that gameweek — no temporal leakage, no aggregation distortion, no silent substitution |
| **Determinism** | Two runs on the same DB produce byte-identical output regardless of SQLite row order, process environment, or within-session state |
| **Contract completeness** | Every column has a declared dtype, null rule, aggregation rule, and at least one enforcement path in the live build |
| **Robustness** | Any contract violation raises immediately at the layer where it occurs with enough diagnostic information to identify the root cause without a debugger |
| **Reproducibility** | Historical rows for GW ≤ N-1 are unchanged when GW N data is added, provided the source DB has not made retroactive corrections |

These dimensions are distinct. A pipeline can be deterministic and still produce
reproducibly wrong output (SC-1, SC-2, SC-3). The plan addresses them in order of
analytical risk: correctness first, then determinism, then enforcement, then
architecture.

---

## Reproducibility Guarantee Taxonomy

The plan distinguishes three levels of guarantee that are frequently conflated:

| Guarantee | Meaning | Holds when |
|---|---|---|
| **Deterministic** | Same DB state → same output | Always, after Wave 3 |
| **Append-monotonic** | GW N addition does not change GW ≤ N-1 rows | Upstream historical data is not retroactively corrected |
| **Source-stable** | Output history is immutable | Upstream corrections are absent **and** ingestion is snapshot-versioned |

This plan targets **deterministic** and **append-monotonic** guarantees. Source-stable
guarantees require versioned snapshot ingestion, which is out of scope for this
stabilization.

**Source mutation policy — Option A (snapshot semantics):** The pipeline reflects
current DB truth at build time. If the FPL API retroactively corrects historical data
(minutes, own goals, fixture rescheduling, bonus recalculation), a rebuild from the
updated DB will produce updated historical values. This is the documented and expected
behavior. It is not a pipeline defect. Any prior analysis snapshots should be dated and
treated as reflecting the DB at that point in time.

---

## Validation Severity Model

Three severity tiers — no more, no less at this stage:

| Tier | Class | Behavior | Examples |
|---|---|---|---|
| **FATAL** | `DALContractViolation` | Raises immediately; pipeline halts | Duplicate grain, null in never_null column, future data, BGW performance non-null, row count wrong |
| **WARNING** | `logger.warning` | Logged; pipeline continues | Missing GW context keys (now promoted to FATAL — see Wave 1), unscheduled fixtures excluded |
| **AUDIT** | `logger.info` with `[AUDIT]` prefix | Logged for reconciliation visibility | team_id corrections from fixture data (mid-season transfer corrections) |

The distinction between WARNING and AUDIT matters: a WARNING indicates potential
degradation; an AUDIT event indicates a known, applied correction whose existence
should be visible for later reconciliation. They are not the same. team_id correction
is an audit event, not a warning.

A formal severity enum is deferred — the three-tier model above covers all current
cases and can be formalized once the pipeline runs in CI with structured log ingestion.

---

## Grain Contract Registry

All DAL layer grains are declared here as the authoritative machine-readable source.
Validators consume this registry. If a new curated table is added, its grain must be
registered here before any validator is written.

Location of implementation: `dal/contracts.py` (new file, Wave 2)

```python
GRAIN_CONTRACTS = {
    "staging_players":          {"pk": ["player_id"],                        "duplicates_allowed": False},
    "staging_player_histories": {"pk": ["player_id", "fixture_id"],          "duplicates_allowed": False},
    "staging_fixtures":         {"pk": ["fixture_id"],                        "duplicates_allowed": False},
    "staging_teams":            {"pk": ["team_id"],                           "duplicates_allowed": False},
    "staging_events":           {"pk": ["gw"],                                "duplicates_allowed": False},
    "staging_element_types":    {"pk": ["position_code"],                     "duplicates_allowed": False},
    "player_fixture_base":      {"pk": ["player_id", "gw", "fixture_id"],    "duplicates_allowed": False},
    "player_gameweek_spine":    {"pk": ["player_id", "gw"],                  "duplicates_allowed": False},
    "player_gameweek_state":    {"pk": ["player_id", "gw"],                  "duplicates_allowed": False},
    "player_opponent_context":  {"pk": ["player_id", "gw"],                  "duplicates_allowed": False},
}
```

`validate_grain_uniqueness` is updated to accept a `dataset_name` that resolves
against this registry rather than receiving `grain_cols` directly as a free argument.
This prevents validators from drifting away from the declared grain over time.

---

## FIRST_COLS Semantic Registry

"Lowest fixture_id" is a hidden semantic policy. Determinism does not imply correctness.
Every column in `FIRST_COLS` must be classified into one of four semantic types:

| Type | Meaning | Validation implication |
|---|---|---|
| `invariant_per_gw` | Value is identical across all fixtures in the GW — taking first is safe | Assert `group[col].nunique() == 1` |
| `canonical_first_fixture` | Intentionally takes the value from the earliest fixture; semantically significant | No further assertion; document explicitly |
| `temporally_first` | Takes the value from the fixture with the lowest kickoff time | Requires ordering by kickoff_time, not fixture_id |
| `representative_arbitrary` | No analytical semantics; any fixture's value is acceptable | Document explicitly; consider whether this column should be DGW-excluded |

Location of implementation: `dal/curated/contracts.py` alongside `FIRST_COLS`

```python
FIRST_COL_SEMANTICS = {
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
```

For all `invariant_per_gw` columns, an assertion is added in the aggregation step:
```python
for col in [c for c, s in FIRST_COL_SEMANTICS.items() if s == "invariant_per_gw"]:
    assert (df.groupby(["player_id", "gw"])[col].nunique() == 1).all(), \
        f"invariant_per_gw violated for {col}"
```

This assertion runs on the fixture-grain data before aggregation and is a FATAL
contract violation if it fails. It catches upstream API changes that silently alter
per-GW invariants.

---

## State Layer Causality Contract

The state layer is effectively feature engineering. Every derived column must declare
its causality class and warmup semantics before it is used in any lens study.

Location of implementation: `dal/state/contracts.py` (new file, Wave 4)

```python
STATE_COL_CONTRACTS = {
    "points_roll3": {
        "causality": "lagged",          # uses only GW 1..N-1
        "warmup_gws": 1,                # first non-null at GW 2
        "min_obs_for_reliability": 3,   # roll3 is reliable only when n_obs == 3
        "null_if_no_obs": True,
    },
    "minutes_roll3": {
        "causality": "lagged",
        "warmup_gws": 1,
        "min_obs_for_reliability": 3,
        "null_if_no_obs": True,
    },
    "minutes_trend": {
        "causality": "lagged",          # MUST use shift(1) — violation was SC-1
        "warmup_gws": 4,                # requires 3 prior + 3 prior-prior GWs
        "min_obs_for_reliability": 6,
        "null_if_no_obs": True,
    },
    "fixture_context": {
        "causality": "contemporaneous", # reflects current GW fixture structure
        "values": ["BGW", "SGW", "DGW"],
        "null_if_no_obs": False,
    },
}
```

Causality classes:

| Class | Meaning |
|---|---|
| `lagged` | Derived exclusively from GW 1..N-1; safe as a pre-GW feature |
| `contemporaneous` | Uses current GW metadata (fixture structure, not performance) |
| `future_derived` | **Forbidden** — any use raises immediately |

The `warmup_gws` value is the minimum GW index at which the column becomes non-null.
The `min_obs_for_reliability` value is the observation count at which the rolling
average is considered statistically established. This does not change how `min_periods`
works — it is metadata for downstream consumers to filter on when computing
correlations.

---

## Identified Risks — Master Table

All risks from the audit, with corrected severity and wave assignment:

| ID | Description | Severity | Wave |
|---|---|---|---|
| SC-1 | `minutes_trend` includes current-GW look-ahead | **Critical** | 1 |
| SC-2 | BGW team_id backfilled from latest-GW attributes (temporal leakage) | **Critical** | 1 |
| SC-3 | `goals_conceded` uses `mean` instead of `sum` for DGW teams | **Critical** | 1 |
| SC-4 | `opponent_team_id` column missing — module raises `KeyError` at runtime | **Critical** | 1 |
| SC-11 | Missing GW context logs warning then proceeds to guaranteed validation failure | **Critical** | 1 |
| SC-5 | `validate_bgw_correctness` uses `!= 0` on nullable types — misses `pd.NA` | **High** | 2 |
| SC-6 | `validate_no_future_data` uses `!= 0` on nullable types — same bug | **High** | 2 |
| SC-8 | 8 GW context columns absent from `DTYPES` — never cast or type-checked | **High** | 2 |
| V-1 | `validate_column_contract` exists but is never called in the live build | **High** | 2 |
| V-2 | `validate_row_completeness` exists but is never called in the live build | **Medium** | 2 |
| V-3 | `invariants.py` imports from `dal/curated/contracts.py` — upward coupling | **Medium** | 2 |
| D-1 | No `ORDER BY` in staging SQL — row order is filesystem-defined | **High** | 3 |
| SC-9 | `FIRST_COLS` aggregation result depends on staging row order | **High** | 3 |
| F-1 | `FIRST_COLS` semantic type undeclared — "lowest fixture_id" is a hidden policy | **High** | 3 |
| F-2 | `invariant_per_gw` columns not asserted for within-GW invariance | **High** | 3 |
| SC-13 | `fixture_context` maps `is_bgw=True` rows to `"SGW"` — BGW invisible | **Medium** | 4 |
| SC-7 | `influence`, `creativity`, `threat`, `ict_index` summed for DGW — undocumented | **Medium** | 4 |
| SC-10 | `fixture_count >= 2` for DGW but validation requires exactly 2 — TGW unsupported | **Medium** | 4 |
| SC-14 | `validate_xgc_001` checks GK only — defenders with inconsistent xgc pass | **Low** | 4 |
| SC-15 | `min_periods=1` produces single-observation means with no flag for consumers | **Low** | 4 (doc) |
| A-1 | `pipeline/` contains dead code that imports from nonexistent `analysis.source` | **Medium** | 5 |
| A-2 | `GrainViolationError` used in `opponent_context.py` — inconsistent exception hierarchy | **Medium** | 5 |
| A-3 | `opponent_context.py` lives in `state/` but operates on intermediate-layer data | **Medium** | 5 |
| O-1 | No staging-layer logging — entity row counts, column counts, timing invisible | **Medium** | 6 |
| O-2 | team_id correction logged at `INFO`, not `AUDIT` | **Medium** | 6 |
| O-3 | `DALContractViolation.layer` is optional — many raises omit it | **Medium** | 6 |
| O-4 | `DB_PATH` hardcoded to `~/.fpl/fpl.db` — no environment variable override | **Low** | 6 |
| O-5 | No hash-level reproducibility artifact — equality tests only | **Low** | 6 |
| O-6 | No timing instrumentation at layer boundaries | **Low** | 6 |

---

## Wave Execution Plan

### Before Wave 1 Begins — Prerequisites

These must exist before any Wave 1 code changes are committed.

**P-1: Create the golden test fixture database**

A small, controlled SQLite DB with known values used throughout all test waves. The
DB must contain:

- At least 3 players
- At least 5 GWs
- One player with a BGW in GW 3
- One player with a DGW in GW 4
- One player who transfers teams between GW 2 and GW 3 (mid-season transfer)
- One DGW player with different fixture difficulties in the two fixtures
- Correct GW context (events table) for all GWs
- Fixture data where `goals_conceded` differs across the two DGW fixtures

This DB is the ground truth for all golden-value tests. Any test that asserts a
specific numerical value must use this DB. It lives at `tests/fixtures/test.db` and
its schema is version-controlled alongside its creation script.

**P-2: Write failing tests for SC-1, SC-2, SC-3, SC-4 before touching any source files**

Each failing test is committed as its own commit before the corresponding fix.
The failure is the proof that the violation exists.

---

### Wave 1 — Corruption Blockers

**Objective:** Eliminate all silent analytical corruption. No lens study runs until
this wave is complete and all tests pass.

**Risks addressed:** SC-1, SC-2, SC-3, SC-4, SC-11

#### SC-1: Fix `minutes_trend` look-ahead leak

**File:** [dal/state/player_gameweek_state.py](dal/state/player_gameweek_state.py)

**Change:** In `_compute_minutes_trend`, replace:
```python
last3 = minutes_series.rolling(3, min_periods=3).mean()
```
with:
```python
last3 = minutes_series.shift(1).rolling(3, min_periods=3).mean()
```

Both the `last3` and `prior3` windows must use the lag-1 convention. `prior3 =
minutes_series.shift(3).rolling(3, min_periods=3).mean()` is already shifted by 3,
which is correct for comparing the prior window to the window before it. Verify
that the shift is not double-applied.

**Tests before fix:**
```
test_minutes_trend_includes_current_gw_before_fix:
    - Spine: player X has minutes = [0, 0, 0, 90] at GWs 1-4
    - Assert: GW 4's minutes_trend is NOT null and reflects 90 minutes
    - This must FAIL after the fix (confirms the look-ahead existed)
```

**Tests after fix:**
```
test_minutes_trend_lag1_convention:
    - Spine: player X has minutes = [0, 0, 0, 90] at GWs 1-4
    - Assert: GW 4's minutes_trend is None (prior 3 GWs are all 0 → stable → BUT
      min_periods=3 requires 3 prior obs; shift(1) means GW 4 sees GWs 1,2,3 = [0,0,0])
    - Assert: GW 5's minutes_trend reflects the 90 at GW 4
    - Assert: minutes_trend is None for GW 1 for all players

test_all_rolling_windows_use_shift1:
    - For each column in _ROLL_COLS: assert roll3 for GW N uses only GW 1..N-1
    - Use golden DB where GW N has an anomalous value; assert it does not appear
      in GW N's roll3/roll5 values
```

**Invalidated outputs:** All saved `minutes_trend` values. All prior LENS-AVAIL
analysis using `minutes_trend` must be discarded.

---

#### SC-4 Prerequisite: Derive `opponent_team_id` in intermediate layer

**File:** [dal/intermediate/player_fixture.py](dal/intermediate/player_fixture.py)

**Change:** In `_resolve_player_side_context`, before dropping `home_team_id` and
`away_team_id`, derive:
```python
opponent_team_id = df["away_team_id"].where(is_home, df["home_team_id"])
df["opponent_team_id"] = opponent_team_id.astype("int64")
```

This column is retained in the output of `get_player_fixture_base()`. The columns
`home_team_id` and `away_team_id` are still dropped after derivation.

Update `DAL_CONTRACT.md` to declare `opponent_team_id` as a retained intermediate
column before committing this change.

**Tests before fix:**
```
test_opponent_team_id_raises_keyerror_before_fix:
    - Call build_player_opponent_defensive_context(player_fixture_base)
    - Assert KeyError is raised on "opponent_team_id"
    - This test is deleted or converted to a passing test after the fix
```

**Tests after fix:**
```
test_opponent_team_id_present_in_player_fixture_base:
    - Assert "opponent_team_id" in get_player_fixture_base(db_path).columns

test_opponent_team_id_correctness:
    - For a home player in fixture F: assert opponent_team_id == away_team_id in F
    - For an away player in fixture F: assert opponent_team_id == home_team_id in F
    - Use golden DB where home and away teams are known

test_opponent_team_id_never_null:
    - Assert player_fixture_base["opponent_team_id"].notna().all()
```

---

#### SC-3: Fix `goals_conceded` aggregation in opponent context

**File:** [dal/state/opponent_context.py](dal/state/opponent_context.py)

**Change:** In `_build_team_defensive_records`:
```python
# Before
goals_conceded=("goals_conceded", "mean")

# After
goals_conceded=("goals_conceded", "sum")
```

**Rationale:** Goals conceded is an additive quantity. A team that conceded 1 goal in
each of two DGW fixtures conceded 2 goals in that GW, not 1. Averaging
underestimates defensive weakness for DGW teams and creates a systematic bias in the
rolling opponent defensive metrics.

**Tests before fix:**
```
test_goals_conceded_aggregation_uses_mean_before_fix:
    - Golden DB: team A conceded 1 goal in fixture 1, 1 goal in fixture 2 (DGW)
    - Assert team_def["goals_conceded"] == 1.0 for team A in that GW
    - This must FAIL after the fix
```

**Tests after fix:**
```
test_goals_conceded_aggregation_sums_across_fixtures:
    - Golden DB: team A conceded 1 goal in each DGW fixture
    - Assert team_def["goals_conceded"] == 2 for team A in that GW

test_goals_conceded_sgw_unchanged:
    - Golden DB: team B conceded 2 goals in a SGW
    - Assert team_def["goals_conceded"] == 2 (sum of one fixture = same value)
```

**Invalidated outputs:** All prior opponent defensive context results for any DGW
team. These must be regenerated.

---

#### SC-2: Fix BGW team_id temporal leakage

**Files:** [dal/curated/player_gameweek_spine.py](dal/curated/player_gameweek_spine.py)

**Contract decision (update DAL_CONTRACT.md first):**

BGW rows carry the player's team as of the most recent non-BGW GW **before** the
BGW. This is temporally causal — it uses only information available prior to the BGW.
It is not the player's latest-known team across all GWs.

Implementation strategy in `_apply_bgw_defaults`:
- Build `player_info` only from non-BGW rows: `df[df["fixture_id"].notna()]`
- For each BGW row, look up the player's team from the most recent non-BGW GW at or
  before the current GW, not from the overall latest GW

The current `_build_player_info` uses `sort_values("gw", ascending=False)
.drop_duplicates("player_id", keep="first")`, which returns the latest GW
regardless of when the BGW occurs. This must be changed to a per-BGW lookup.

**Tests before fix:**
```
test_bgw_team_id_uses_latest_gw_before_fix:
    - Golden DB: player P is at team A in GW 1-2, transfers to team B, GW 3 is BGW
    - Assert GW 3 BGW row has team_id == B (wrong — uses latest)
    - This must FAIL after the fix
```

**Tests after fix:**
```
test_bgw_team_id_uses_pre_bgw_team:
    - Golden DB: player P at team A in GW 1-2, BGW in GW 3, plays for team B from GW 4
    - Assert GW 3 BGW row has team_id == A (pre-transfer team)

test_bgw_team_id_never_null:
    - After fix: assert team_id is not null for any BGW row

test_bgw_team_id_post_transfer:
    - Golden DB: player Q at team A in GW 1, transfers, BGW in GW 5 while at team B
    - Assert GW 5 BGW row has team_id == B (post-transfer team — correct for that GW)
```

**Invalidated outputs:** All prior analyses that used BGW team_id for team-context
joins. Regenerate the spine and any derived outputs.

---

#### SC-11: Replace missing GW context warning with immediate raise

**File:** [dal/curated/player_gameweek_spine.py](dal/curated/player_gameweek_spine.py)

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
    - Same setup as above
    - Assert no DataFrame is returned
```

---

#### Wave 1 Validation Checklist

Before proceeding to Wave 2:

- [ ] All 5 failing tests committed before any Wave 1 code changes
- [ ] All 5 fix tests pass after implementation
- [ ] All pre-existing DAL tests still pass
- [ ] Full spine build from real DB succeeds
- [ ] Full state build from real DB succeeds
- [ ] Spot-check: known mid-season transfer player has correct BGW team_id
- [ ] Spot-check: GW N's `minutes_trend` is null when player played 90 min in GW N for first time

**Rollback:** All Wave 1 changes are function-scoped. Any change can be reverted by
file without affecting others. `opponent_context.py` is not integrated into the spine
build — its fix can be reverted independently.

---

### Wave 2 — Contract Enforcement

**Objective:** Ensure every declared contract is enforced in the live build path.
No validation function that exists should be uncalled.

**Risks addressed:** SC-5, SC-6, SC-8, V-1, V-2, V-3

#### SC-8: Add GW context columns to `DTYPES`

**File:** [dal/curated/contracts.py](dal/curated/contracts.py)

Add to `DTYPES`:
```python
"deadline_time":        "datetime64[ns]",
"finished":             "boolean",
"is_previous":          "boolean",
"is_live":              "boolean",
"is_next":              "boolean",
"average_entry_score":  "Float64",     # nullable: early GWs may be null
"highest_score":        "Float64",     # nullable: early GWs may be null
"transfers_made":       "int64",
```

Add the same columns to `NULL_RULES` with appropriate rules:
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
    - Build spine from golden DB
    - Assert spine["finished"].dtype == "boolean"
    - Assert spine["deadline_time"].dtype == "datetime64[ns]"
```

---

#### V-1, V-2: Call `validate_column_contract` and `validate_row_completeness` in build

**File:** [dal/curated/player_gameweek_spine.py](dal/curated/player_gameweek_spine.py)

In `_cast_and_validate`, the full validation call sequence after Wave 2:

```python
def _cast_and_validate(result, n_players, n_gws, max_gw):
    for col, dtype in DTYPES.items():
        result[col] = result[col].astype(dtype)
    result = result.reset_index(drop=True)

    validate_column_contract(result, SPINE_COLS, DTYPES)           # NEW: exact columns + dtypes
    validate_grain_uniqueness(result, "player_gameweek_spine")     # updated to use grain registry
    validate_row_completeness(result,                              # NEW: explicit pair coverage
        result["player_id"].unique(), sorted(result["gw"].unique()))
    validate_row_count_invariant(result, n_players=n_players, n_gws=n_gws)
    validate_time_continuity(result)
    validate_no_future_data(result, reference_gw=max_gw)
    validate_bgw_correctness(result)
    validate_dgw_correctness(result)
    validate_null_semantics(result, NULL_RULES)

    return result
```

---

#### V-3: Decouple `invariants.py` from `dal/curated/contracts.py`

**File:** [dal/validation/invariants.py](dal/validation/invariants.py)

The import `from dal.curated.contracts import PERFORMANCE_COLS` couples the
validation layer to the curated layer. Validation must be independently testable.

Change `validate_no_future_data` and any other function that uses `PERFORMANCE_COLS`
to accept it as a parameter:

```python
def validate_no_future_data(
    df: pd.DataFrame,
    gw_col: str = "gw",
    reference_gw=None,
    performance_cols=None,   # caller passes PERFORMANCE_COLS
) -> None:
```

Call sites pass `PERFORMANCE_COLS` explicitly. The validation module imports nothing
from `dal/curated/`.

**Tests:**
```
test_validate_no_future_data_importable_without_curated:
    - import dal.validation.invariants without importing dal.curated
    - Assert no ImportError

test_validate_column_contract_called_in_spine_build:
    - Monkeypatch validate_column_contract to track calls
    - Run build_player_gameweek_spine
    - Assert exactly one call
```

---

#### SC-5, SC-6: Fix nullable type comparisons in validators

**Files:**
- [dal/validation/semantics.py](dal/validation/semantics.py)
- [dal/validation/invariants.py](dal/validation/invariants.py)

**SC-5** — In `validate_bgw_correctness`, for `PERFORMANCE_COLS` on BGW rows:
```python
# Wrong: pd.NA != 0 returns pd.NA (falsy), silently misses pd.NA values
bad = bgw[bgw[col] != 0]

# Correct: performance columns on BGW rows must be null; non-null is the violation
bad = bgw[bgw[col].notna()]
```

**SC-6** — In `validate_no_future_data`:
```python
# Wrong: same nullable type issue
bad = future_rows[future_rows[col] != 0]

# Correct: future rows with non-null performance are the violation
bad = future_rows[future_rows[col].notna()]
```

**Tests before fix** (must demonstrate the bug):
```
test_bgw_validator_silently_misses_pd_na_before_fix:
    - Build DataFrame with is_bgw=True, total_points=pd.NA (Int64)
    - Assert validate_bgw_correctness passes (NA is correct — this should pass after fix too)
    - Build DataFrame with is_bgw=True, total_points=Int64(5)
    - With current code: assert validate_bgw_correctness DOES NOT raise (the bug)
    - After fix: assert validate_bgw_correctness RAISES
```

---

#### Wave 2 Validation Checklist

- [ ] `set(SPINE_COLS) == set(DTYPES.keys())` asserted in a test
- [ ] `set(SPINE_COLS) == set(NULL_RULES.keys())` asserted in a test
- [ ] `validate_column_contract` called in live build
- [ ] `validate_row_completeness` called in live build
- [ ] `validate_bgw_correctness` correctly identifies Int64 non-null violations
- [ ] `invariants.py` imports nothing from `dal/curated/`
- [ ] All Wave 1 tests still pass

---

### Wave 3 — Determinism Hardening

**Objective:** Guarantee two runs on the same DB produce byte-identical output
regardless of SQLite row storage order.

**Risks addressed:** D-1, SC-9, F-1, F-2

#### D-1: Add ORDER BY to all staging SQL queries

**File:** [dal/staging/transformer.py](dal/staging/transformer.py)

`_build_query` must produce ordered results. The canonical PK per entity:

| Entity | ORDER BY |
|---|---|
| players | `id` |
| player_histories | `element, fixture` |
| fixtures | `id` |
| teams | `id` |
| events | `id` |
| element_types | `id` |

This requires each schema YAML to declare a `pk_columns` field, or the ORDER BY
clause is constructed from the schema's declared PK columns. The simpler approach:
add `pk_columns` to each YAML and use it in `_build_query`.

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

#### SC-9, F-1: Explicit sort before aggregation + FIRST_COLS semantic registry

**Files:**
- [dal/curated/player_gameweek_spine.py](dal/curated/player_gameweek_spine.py)
- [dal/curated/contracts.py](dal/curated/contracts.py)

In `build_player_gameweek_spine`, sort the fixture-grain frame before aggregation:
```python
df = df.sort_values(["player_id", "gw", "fixture_id"]).reset_index(drop=True)
aggregated = _aggregate_to_gw_grain(df)
```

Add `FIRST_COL_SEMANTICS` to `dal/curated/contracts.py` as specified in the
Semantic Registry section above.

---

#### F-2: Assert `invariant_per_gw` columns before aggregation

**File:** [dal/curated/player_gameweek_spine.py](dal/curated/player_gameweek_spine.py)

Before the `_aggregate_to_gw_grain` call, add:
```python
_assert_invariant_per_gw_columns(df)
```

Where `_assert_invariant_per_gw_columns` raises `DALContractViolation` if any column
declared `invariant_per_gw` has more than one distinct value within any
`(player_id, gw)` group.

**Tests:**
```
test_invariant_per_gw_assertion_catches_violation:
    - Construct a fixture-grain frame where purchase_price differs across two fixtures
      for the same (player_id, gw)
    - Assert DALContractViolation raised before aggregation

test_full_pipeline_is_reproducible:
    - Run build_player_gameweek_spine(db_path) twice
    - Assert pd.testing.assert_frame_equal(result1, result2, check_like=False)
    - This is the primary determinism regression test and runs on every PR
```

---

#### Wave 3 Validation Checklist

- [ ] Reproducibility test passes (two-run exact equality)
- [ ] `invariant_per_gw` assertion fires correctly on a crafted violation
- [ ] All FIRST_COLS entries classified in `FIRST_COL_SEMANTICS`
- [ ] `ORDER BY` present in all 6 entity staging queries
- [ ] All Wave 1 and Wave 2 tests still pass

---

### Wave 4 — Invariant Expansion

**Objective:** Add missing invariants and formalize the state layer contract. Fixes
analytical gaps that are not silent corruption but would affect research quality.

**Risks addressed:** SC-13, SC-7, SC-10, SC-14, SC-15 (documentation)

#### SC-13: `fixture_context` three-way label

**File:** [dal/state/player_gameweek_state.py](dal/state/player_gameweek_state.py)

Change:
```python
# Before: BGW rows get "SGW" — incorrect
df["fixture_context"] = df["is_dgw"].map({True: "DGW", False: "SGW"})

# After: three-way classification
conditions = [df["is_bgw"], df["is_dgw"]]
choices = ["BGW", "DGW"]
df["fixture_context"] = np.select(conditions, choices, default="SGW")
```

**Contract change required:** Declare in `STATE_COL_CONTRACTS` (new Wave 4 file):
valid values for `fixture_context` are `{"BGW", "SGW", "DGW"}`.

**Downstream breakage:** Any research code filtering `fixture_context == "SGW"` will
now correctly exclude BGW rows. This is the correct behavior — previously they were
included by accident. All lens notebooks using this filter must be audited before
continuing studies.

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

#### SC-7: Declare DGW summation semantics for FPL indices

**Decision:** Summation of `influence`, `creativity`, `threat`, `ict_index` across DGW
fixtures is declared **analytically intentional** with a documented normalization
convention. No code change.

**Rationale:** These per-match FPL indices are not strictly additive, but summing
them across two matches is not analytically harmful provided consumers normalize by
`fixture_count` when comparing SGW and DGW rows. Changing the aggregation to `mean`
or `first` would invalidate prior spine data and introduce a different set of semantic
problems (mean obscures high-performance DGW weeks; `first` is arbitrary).

**Required action:** Update `DAL_CONTRACT.md` Section 6 to explicitly state:
- `influence`, `creativity`, `threat`, `ict_index` use `sum` aggregation for DGW
- Consumers comparing these values across SGW and DGW rows must normalize by `fixture_count`
- Example: `normalized_influence = influence / fixture_count`

---

#### SC-10: Document TGW non-support

**Decision:** Triple gameweeks are not supported. `validate_dgw_correctness` will
raise `DALContractViolation` if `fixture_count` is 3 for any row.

Update `DAL_CONTRACT.md` to state explicitly: the pipeline assumes `fixture_count ∈
{0, 1, 2}`. If a triple gameweek is announced, the pipeline requires a contract
amendment before the affected GW data is ingested.

No code change beyond ensuring the error message in `validate_dgw_correctness` is
clear:
```python
raise DALContractViolation(
    f"fixture_count not in {{0, 1, 2}} for {len(bad_bounds)} rows. "
    f"Triple gameweeks are not supported by the current contract. "
    f"Update DAL_CONTRACT.md before ingesting TGW data.",
    ...
)
```

---

#### SC-14: Expand `validate_xgc_001` to all positions

**File:** [dal/state/opponent_context.py](dal/state/opponent_context.py)

Change the `_validate_contracts` call from:
```python
validate_xgc_001(analytics_90[analytics_90["position_code"] == 1])
```
to:
```python
validate_xgc_001(analytics_90)
```

The xgc invariance contract — that all 90-minute players in the same team/fixture
share the same xgc — should hold for all positions, not just goalkeepers.

---

#### State Layer Contract File

**New file:** `dal/state/contracts.py`

Create `STATE_COL_CONTRACTS` as specified in the Causality Contract section of this
document. The minimum required entries before LENS-AVAIL begins:
- All `_ROLL_COLS` entries with `causality: "lagged"`, correct `warmup_gws`, and
  `min_obs_for_reliability`
- `fixture_context` with `causality: "contemporaneous"` and `values`
- `minutes_trend` with explicit `causality: "lagged"` and `warmup_gws: 4`

---

#### Wave 4 Validation Checklist

- [ ] `fixture_context` produces "BGW", "SGW", "DGW" — no other values
- [ ] DGW summation semantics documented in DAL_CONTRACT.md
- [ ] TGW non-support documented in DAL_CONTRACT.md with clear error message
- [ ] `STATE_COL_CONTRACTS` exists with all `_ROLL_COLS` covered
- [ ] All lens studies audited for `fixture_context == "SGW"` filters
- [ ] All previous wave tests still pass

---

### Wave 5 — Architecture Cleanup

**Objective:** Remove structural confusion, fix cross-layer violations, eliminate
dead code. No analytical outputs are changed.

**Risks addressed:** A-1, A-2, A-3

#### A-1: Archive `pipeline/`

Move `pipeline/` to `archive/pipeline_legacy/`. It imports from `analysis.source`
which does not exist. It will fail on import. It is a source of confusion about which
implementation is authoritative.

Update `CONTEXT.md` structure table to reflect `dal/` as the sole authoritative DAL.

**Tests:**
```
test_no_import_from_pipeline:
    - grep dal/ and research/ for "from pipeline" or "import pipeline"
    - Assert zero matches
```

---

#### A-2: Retire `GrainViolationError`

**File:** [dal/exceptions.py](dal/exceptions.py)

Replace all usages of `GrainViolationError` (currently only in `opponent_context.py`)
with `DALContractViolation`. Remove `GrainViolationError` from `exceptions.py`.

**Tests:**
```
test_grain_violation_error_not_used:
    - grep all .py files for "GrainViolationError"
    - Assert only zero matches (or only the deletion comment if kept as a tombstone)
```

---

#### A-3: Reclassify `opponent_context.py` to intermediate layer

**File:** Move `dal/state/opponent_context.py` → `dal/intermediate/opponent_context.py`

The module operates on `player_fixture_base` (intermediate grain). It does not
consume the curated spine. Its correct layer is intermediate, not state.

Update all imports. Update `DAL_CONTRACT.md` to document opponent context as an
intermediate-layer output.

---

#### Wave 5 Validation Checklist

- [ ] `pipeline/` archived — no remaining imports from it
- [ ] `GrainViolationError` removed — zero usages
- [ ] `opponent_context.py` at intermediate layer — all imports updated
- [ ] All previous wave tests still pass
- [ ] Full spine and state build succeed from real DB

---

### Wave 6 — Observability and Maintainability

**Objective:** Make the DAL fully diagnosable from log output alone without a debugger.
Add environment override for test isolation. Add hash-level reproducibility artifact.

**Risks addressed:** O-1, O-2, O-3, O-4, O-5, O-6

#### O-1: Add staging-layer logging

**File:** [dal/staging/transformer.py](dal/staging/transformer.py)

After each `stage()` call returns, log:
```
[DAL:staging:{entity}] staged | rows={n} cols={c} elapsed_ms={t}
```

Log at `INFO` level. This makes unexpected entity sizes (a new FPL API field, a
dropped player, an empty fixture table) immediately visible.

---

#### O-2: Elevate team_id correction to AUDIT level

**File:** [dal/intermediate/player_fixture.py](dal/intermediate/player_fixture.py)

Change `logger.info(...)` to `logger.info("[AUDIT] ...")` for team_id corrections.
Document in the observability model that AUDIT events are info-level messages with
the `[AUDIT]` prefix, suitable for reconciliation review.

---

#### O-3: Populate `layer=` on all `DALContractViolation` raises

Audit every raise site. All raises must include `layer=`. Update `validate_grain_uniqueness`
to accept an optional `layer` parameter and pass it through to the exception.

---

#### O-4: `FPL_DB_PATH` environment variable override

**File:** [dal/config.py](dal/config.py)

```python
import os
from pathlib import Path

DB_PATH: Path = Path(os.environ.get("FPL_DB_PATH", "~/.fpl/fpl.db")).expanduser()
```

This enables test-time DB override without patching internals.

**Tests:**
```
test_fpl_db_path_env_override:
    - Set FPL_DB_PATH to the golden test DB path
    - Assert dal.config.DB_PATH resolves to the test DB
```

---

#### O-5: Hash-level reproducibility artifact

**File:** `dal/__init__.py` or a new `dal/reproducibility.py`

```python
import hashlib
import pandas as pd

def compute_spine_fingerprint(df: pd.DataFrame) -> dict:
    """Return a reproducibility fingerprint for an output spine."""
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

Log the fingerprint at the end of `build_player_gameweek_spine`. In the
reproducibility test, assert the fingerprint is identical across two runs.

---

#### O-6: Timing instrumentation

**File:** [dal/curated/player_gameweek_spine.py](dal/curated/player_gameweek_spine.py)

Add `time.perf_counter()` calls at spine entry and exit:
```
[DAL:curated:spine] build complete | rows=17893 elapsed_ms=1204
```

No performance threshold enforcement at this stage — log and trend.

---

#### Wave 6 Validation Checklist

- [ ] `FPL_DB_PATH` override works in test context
- [ ] Spine fingerprint is identical across two runs (logged)
- [ ] All `DALContractViolation` raises include `layer=`
- [ ] Staging logs entity row counts at INFO level
- [ ] team_id corrections use `[AUDIT]` prefix
- [ ] All previous wave tests still pass

---

## Immediate Execution Queue

Ordered strictly by analytical risk. Each item is independent unless noted.

| # | Item | Files | Prerequisite | Blast Radius |
|---|---|---|---|---|
| 1 | Create golden test fixture DB | `tests/fixtures/test.db`, creation script | None | Zero |
| 2 | Write failing test for SC-1 (`minutes_trend` look-ahead) | `tests/state/test_player_gameweek_state.py` | Item 1 | Zero |
| 3 | Fix SC-1 (`minutes_trend` shift(1)) | `dal/state/player_gameweek_state.py` | Item 2 | Medium — invalidates all prior `minutes_trend` values |
| 4 | Write failing test for SC-4 (`opponent_team_id` KeyError) | `tests/state/test_opponent_context.py` | Item 1 | Zero |
| 5 | Derive `opponent_team_id` in intermediate layer | `dal/intermediate/player_fixture.py` | Item 4 | Low — additive column |
| 6 | Fix SC-3 (`goals_conceded` sum) | `dal/state/opponent_context.py` | Item 5 | Medium — invalidates DGW defensive context values |
| 7 | Write failing test for SC-2 (BGW team_id leakage) | `tests/curated/test_player_gameweek_spine.py` | Item 1 | Zero |
| 8 | Update DAL_CONTRACT.md with BGW team_id rule | `dal/DAL_CONTRACT.md` | Item 7 | Zero |
| 9 | Fix SC-2 (BGW team_id uses pre-BGW team) | `dal/curated/player_gameweek_spine.py` | Item 8 | High — invalidates all BGW team_id values for transferred players |
| 10 | Fix SC-11 (missing GW context raises, not warns) | `dal/curated/player_gameweek_spine.py` | None | Low — failure mode change only |

Items 2-3, 4-6, and 7-9 are three independent chains that can proceed in parallel.
Item 10 is fully independent. Item 1 must come first.

---

## Definition of Done

The subsystem is declared stable when all of the following are true simultaneously:

### Test coverage
- [ ] Every validation function has at least one test that makes it fail and one that makes it pass
- [ ] Every `FIRST_COLS` column classified in `FIRST_COL_SEMANTICS`; `invariant_per_gw` columns have enforcement tests
- [ ] Every `_ROLL_COLS` column has a look-ahead test asserting GW N's value does not depend on GW N's performance
- [ ] Golden DB produces exact known-value outputs for spine and state
- [ ] Reproducibility test passes: two-run exact equality verified by fingerprint hash

### Invariant coverage (all enforced in live build)
- [ ] Grain uniqueness at fixture-grain, GW-grain (curated), GW-grain (state)
- [ ] Row count = n_players × n_gws exactly
- [ ] Time continuity per player
- [ ] BGW correctness (fixture_count=0, performance=NULL, fdr=NULL, was_home=NULL)
- [ ] DGW correctness (fixture_count=2, home+away=2, fdr ordering valid)
- [ ] Null semantics (all SPINE_COLS covered)
- [ ] Column contract (exact SPINE_COLS set, exact DTYPES)
- [ ] Future data prohibition
- [ ] Row completeness
- [ ] Join safety at every merge site
- [ ] `invariant_per_gw` assertion before aggregation
- [ ] Lag-1 convention for all state rolling windows

### Contract completeness
- [ ] Every column in `SPINE_COLS` has an entry in `DTYPES`, `NULL_RULES`, and `FIRST_COL_SEMANTICS` or `SUM_COLS`
- [ ] Every column in `STATE_COL_CONTRACTS` has declared `causality`, `warmup_gws`, `min_obs_for_reliability`
- [ ] `opponent_team_id` declared in intermediate-layer contract
- [ ] TGW non-support documented with clear error message
- [ ] DGW summation semantics for FPL indices documented with normalization convention
- [ ] Source mutation policy (Option A) documented in DAL_CONTRACT.md
- [ ] BGW team_id semantic rule documented in DAL_CONTRACT.md
- [ ] Append-monotonic vs deterministic vs source-stable guarantees documented

### Reproducibility
- [ ] Two-run spine fingerprint is identical (hash, row count, schema)
- [ ] Historical rows unchanged when new GW data added (append-monotonic, subject to source-stable caveat)
- [ ] `FPL_DB_PATH` environment override works for test isolation

### Documentation
- [ ] `GRAIN_CONTRACTS` registry exists and covers all DAL layer outputs
- [ ] `STATE_COL_CONTRACTS` exists and covers all state layer columns
- [ ] `FIRST_COL_SEMANTICS` exists and covers all `FIRST_COLS` entries
- [ ] `DAL_CONTRACT.md` updated to reflect all Wave 1-4 semantic decisions
- [ ] `CONTEXT.md` updated: `dal/` is the authoritative DAL; `pipeline/` is archived

---

## Deferred Items

The following were raised in the stabilization assessment and are explicitly deferred
with rationale:

| Item | Deferral rationale |
|---|---|
| Unified `COLUMN_CONTRACTS` registry merging all existing contract constants | `DTYPES`, `NULL_RULES`, `FIRST_COLS`, `SUM_COLS`, `PERFORMANCE_COLS` already exist and are enforced. A unification is a significant refactor that could introduce regressions in the enforcement layer it aims to improve. Revisit after all waves complete. |
| Performance contracts with specific second targets | Log timing now (Wave 6). Enforce thresholds only after the pipeline runs in CI with a stable execution environment and baseline established. |
| Full `DALValidationSeverity` enum (five levels) | The FATAL / WARNING / AUDIT three-tier model covers all current cases. A formal enum adds infrastructure complexity without immediate analytical benefit. Revisit when a structured log aggregator is in use. |
| Structured log ingestion / telemetry pipeline | Out of scope for a single-analyst research system. Logging to stderr with structured prefixes is sufficient at current scale. |
