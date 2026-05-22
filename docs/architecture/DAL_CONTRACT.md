# DAL Contract

**Status:** Active  
**Scope:** `dal/` — staging, intermediate, curated, state, validation layers  
**Authority:** Any DAL code change must be consistent with this document. Deviations require updating this document first.

---

## Reproducibility guarantees

Three levels of guarantee, distinct in what they promise:

| Guarantee | Meaning | When it holds |
|---|---|---|
| **Deterministic** | Same DB state → byte-identical output across runs | Always, once determinism hardening is complete |
| **Append-monotonic** | Adding GW N data does not change GW ≤ N-1 rows | Upstream historical data is not retroactively corrected |
| **Source-stable** | Output history is fully immutable | Upstream corrections absent **and** ingestion is snapshot-versioned |

The DAL targets **deterministic** and **append-monotonic** guarantees. Source-stable guarantees require versioned snapshot ingestion, which is out of scope.

**Source mutation policy (Option A — snapshot semantics):** The pipeline reflects current DB truth at build time. If the FPL API retroactively corrects historical data (minutes, own goals, fixture rescheduling, bonus recalculation), a rebuild from the updated DB produces updated historical rows. This is documented and expected behavior — not a defect. Any prior analysis snapshots should be dated and treated as reflecting the DB at that point in time.

---

## Validation severity model

Three tiers:

| Tier | Class | Behavior | Examples |
|---|---|---|---|
| **FATAL** | `DALContractViolation` | Raises immediately; pipeline halts | Duplicate grain, null in never_null column, future data, BGW performance non-null, row count wrong |
| **WARNING** | `logger.warning` | Logged; pipeline continues | Unscheduled fixtures excluded |
| **AUDIT** | `logger.info("[AUDIT] ...")` | Logged for reconciliation visibility | team_id corrections from fixture data (mid-season transfers) |

AUDIT is not a degraded WARNING — it marks a known, applied correction whose existence should be visible for later reconciliation. team_id correction is an audit event, not a warning.

---

## Grain definitions

### Two grains — both enforced

**Fixture-grain** — a row exists because a fixture was played. One row per player per fixture.

```
grain: (player_id, fixture_id)
type:  fixture-grain
```

A player with two DGW fixtures has two rows. A player with no fixture in a BGW has zero rows. This is the event layer — rows exist only when something happened.

**Gameweek-grain** — a row exists because the FPL calendar demands it. One row per player per gameweek.

```
grain: (player_id, gw)
type:  gameweek-grain
```

Every player appears in every GW regardless of fixture count. BGWs are explicit rows. DGWs are single aggregated rows. This is the time-series layer — rows exist because the decision unit (the gameweek) demands them.

### Spine scope

The gameweek-grain spine is the cartesian product of the player universe and the GW range. Both are explicitly defined before construction begins.

**Player universe:** All players in the FPL API dataset for the season, including mid-season transfers, early-season departures, and late-season arrivals. Every player gets a row in every GW from GW 1 through GW 38, regardless of when they entered the season. Without this, rolling windows compute on incomplete history and training datasets have inconsistent row counts per player.

**GW range:** Fixed per season as GW 1–38, defined by the fixture calendar, not observed data. Rows for future GWs have fixture_count=0 and performance=0 until data is ingested — they are future rows, not BGW rows. BGW rows are GWs where the player's club had a scheduled fixture omission.

**Spine construction:**
```
spine = cartesian_product(player_universe, gw_range)
spine = left_join(spine, fixture_data, on=[player_id, gw])
# Rows with no fixture match → BGW or future row
# Apply defaults per aggregation rules section
```

**Row count invariant:**
```
len(spine) == len(player_universe) × len(gw_range)
```
This is a hard assertion. Any deviation means a player is missing from the universe definition or a GW is missing from the range — both are contract violations.

### Grain ownership per layer

```
staging     → fixture-grain (inherits from raw)
intermediate→ fixture-grain (enriched, not aggregated)
curated     → gameweek-grain (aggregated + completed)
state       → gameweek-grain (derived, same grain)
```

Grain change happens exactly once — in the curated layer. No other layer changes grain.

### Grain contract registry

Canonical machine-readable grain declarations. Validators consume this registry. Any new curated table must be registered here before validators are written.

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

`validate_grain_uniqueness` accepts a `dataset_name` that resolves against this registry rather than receiving `grain_cols` as a free argument — preventing validators from drifting away from declared grain over time.

---

## Layer concerns

Five concerns. Each is owned by exactly one layer. No layer implements more than one concern in the same module.

### Staging — transformation only

Reshaping raw inputs into a normalised, typed, consistently named form.

Permitted: column renaming, type casting, string normalisation, null standardisation (raw nulls → typed nulls), deduplication of exact duplicates.

Forbidden: joins, aggregation, derived columns, business logic of any kind, grain assumptions.

### Intermediate — enrichment only

Joining staging outputs to produce wider fixture-grain records. Grain does not change.

Permitted: joins between staging outputs, adding context columns from reference tables, producing wider fixture-grain records.

Forbidden: aggregation of any kind, grain change, derived columns beyond direct join output, embedded validation logic.

**Opponent context** (`dal/intermediate/opponent_context.py`) operates on `player_fixture_base` (intermediate grain) and produces rolling opponent defensive metrics at `(player_id, gw)` grain. It belongs to the intermediate layer, not the state layer.

### Curated — aggregation and spine completion

Changing grain from fixture-grain to gameweek-grain. Spine completion. DGW and BGW semantic enforcement.

**Aggregation boundary rule — critical:** All fixture-to-GW aggregation must complete before the spine join. The spine join may only introduce missing rows and apply BGW defaults. No aggregation is permitted after spine completion.

```
Step 1: Aggregate fixture-grain → GW summaries (only for players/GWs with fixtures)
Step 2: Construct full spine (cartesian product)
Step 3: Left-join GW summaries onto spine (unmatched rows → BGW rows)
Step 4: Apply BGW defaults to unmatched rows
Step 5: Validate — call validation modules
```

Permitted: fixture-grain to gameweek-grain aggregation, spine completion, BGW row insertion with explicit defaults, DGW column aggregation per defined rules, calling validation modules after aggregation.

Forbidden: derivation (rolling, lag, trend), joins after aggregation, embedded validation logic, BGW row absence, aggregation after spine join.

### State — derivation only

Adding derived columns to gameweek-grain records. Grain does not change. No joins. No aggregation.

Permitted: rolling window calculations, lag features, trend signals, ratio and composite signals.

Forbidden: grain change, row count change, joins to external tables, aggregation, modification of non-derived columns, use of data from future GWs.

**Lag-1 convention:** Rolling windows compute over prior GWs only, not including the current GW. At GW N, roll5 looks at GWs N-5 through N-1.

**NULL handling in rolling windows:** BGW rows (fixture_count=0) have NULL performance columns. Rolling windows skip NULLs (pandas `skipna=True` default). A player with 4 actual GWs and 1 BGW in a 5-GW window computes roll5 from those 4 values. NULLs do not prevent rolling from computing and do not count toward the window requirement. This ensures late-season transfers and scheduled BGWs do not artificially deflate rolling signals.

### Validation — cross-cutting

Assertions that invariants hold. No data changes. Lives in standalone modules imported by any layer. Never embedded inside transformation, enrichment, or aggregation code.

```
dal/validation/
    grain.py          → grain uniqueness checks
    completeness.py   → row completeness checks
    semantics.py      → BGW/DGW correctness checks
    joins.py          → join safety checks
    contracts.py      → column contract checks
    nulls.py          → null semantics checks
    invariants.py     → system invariant checks
```

Every validation function: takes a dataframe and parameters, returns nothing on pass, raises with a descriptive message on fail, has no side effects.

---

## Validation module contracts

### validate_grain_uniqueness

```python
validate_grain_uniqueness(df, dataset_name)
```

Asserts no duplicate rows exist for the declared grain (resolved from GRAIN_CONTRACTS). Called at the end of every layer function. Failure means a join produced fan-out or a deduplication step is missing.

### validate_row_completeness

```python
validate_row_completeness(df, player_ids, gw_range)
```

Asserts every `(player_id, gw)` combination exists in the gameweek-grain spine. Called after curated spine completion. Failure means BGW rows are missing or a player is absent from a GW they should appear in.

### validate_bgw_correctness

```python
validate_bgw_correctness(df)
```

For all rows where `is_bgw=True`:
- `fixture_count == 0`
- All performance columns are NULL (not zero, not `pd.NA` treated as zero — must be explicitly null)
- `fdr_avg`, `fdr_min`, `fdr_max` are NULL
- Opponent context columns are NULL

Failure means a BGW row has been populated with fixture data that does not exist.

**Implementation note:** Use `.notna()` not `!= 0` when checking for violations on nullable Int64/Float64 types. `pd.NA != 0` returns `pd.NA` (falsy), which silently misses `pd.NA` violations.

### validate_dgw_correctness

```python
validate_dgw_correctness(df)
```

For all rows where `is_dgw=True`:
- `fixture_count == 2`
- `home_count + away_count == 2`
- `fdr_avg` is not NULL
- `fdr_min <= fdr_avg <= fdr_max`

`fixture_count` must be in `{0, 1, 2}`. Triple gameweeks are not supported — any row with `fixture_count` outside this set raises `DALContractViolation` with an explicit TGW message.

### validate_null_semantics

```python
validate_null_semantics(df, rules)
```

Rules map column names to `'never_null'`, `'null_if_bgw'`, or `'always_nullable'`. Asserts each column conforms. Failure means a column is null when it should not be, or populated when it should be null.

### validate_join_safety

```python
validate_join_safety(left_n, right_n, result_n, join_type, description)
```

Left joins: asserts `result_n == left_n` (no row loss). Inner joins: asserts `result_n <= min(left_n, right_n)`. Cross joins: asserts `result_n == left_n * right_n`. Called immediately after every join operation.

### validate_column_contract

```python
validate_column_contract(df, expected_cols, dtypes)
```

Asserts `df.columns` contains exactly `expected_cols` with correct dtypes. No extra columns. No missing columns. Called at layer output boundary.

### validate_time_continuity

```python
validate_time_continuity(df, player_col='player_id', gw_col='gw')
```

For each `player_id`, asserts GW values form a contiguous sequence with no gaps within the defined GW range. Failure means a player has missing GW rows — rolling windows will silently misalign.

### validate_row_count_invariant

```python
validate_row_count_invariant(df, n_players, n_gws)
```

Asserts `len(df) == n_players × n_gws`. Failure means a player is missing from the universe or a GW is missing from the range.

### validate_no_future_data

```python
validate_no_future_data(df, gw_col='gw', reference_gw=None, performance_cols=None)
```

Asserts no performance column contains data from a GW later than the row's own GW value. `performance_cols` is passed explicitly by the caller — this function imports nothing from `dal/curated/`. Failure means temporal causality is violated and any ML model trained on this data silently overfits to future information.

**Implementation note:** Use `.notna()` not `!= 0` for nullable type checks (same issue as SC-5/SC-6).

---

## Canonical spine specification

### Canonical base table

The curated layer produces `player_gw_base` — the single canonical base table. All downstream analytics and the state layer must use this table as their only source. It must not be bypassed.

```
grain:        (player_id, gw)
uniqueness:   enforced — exactly one row per pair
completeness: enforced — every player in every GW
row_count:    enforced — n_players × n_gws exactly
BGW rows:     present — fixture_count=0, is_bgw=True
DGW rows:     present — fixture_count=2, is_dgw=True
fixture_count bounds: {0, 1, 2} — TGW raises immediately
```

### Temporal causality guarantee

For any row `(player_id, gw)`, all columns must be computable using data from that GW and earlier only. No performance column may contain data from a future GW. Violation means ML models will silently overfit to future information.

### Identity columns — never null

| Column | Dtype | Notes |
|---|---|---|
| `player_id` | `int64` | FPL player identifier |
| `gw` | `int64` | Gameweek number (1–38) |
| `player_name` | `string` | Display name |
| `team_id` | `int64` | Current team — see BGW team_id rule |
| `position_code` | `int64` | FPL position (1=GK, 2=DEF, 3=MID, 4=FWD) |
| `position_label` | `string` | Human-readable position label |

**BGW team_id rule:** For BGW rows (`fixture_count=0, is_bgw=True`), `team_id` carries the player's team as of the most recent non-BGW GW strictly before the BGW. This is temporally causal — it uses only information available prior to the BGW. It is NOT the player's latest-known team across all GWs. For a player who transfers between GW 2 and GW 4 with a BGW in GW 3, the GW 3 row carries `team_id` from GW 2, not GW 4.

Implementation: `_build_player_info` is called on non-BGW rows only. For each BGW row, `team_id` is filled from the most recent non-BGW GW at or before that GW (merge-as-of / backward lookup).

### Schedule columns — never null

| Column | Dtype | Notes |
|---|---|---|
| `fixture_count` | `int64` | 0 (BGW), 1 (SGW), 2 (DGW) |
| `is_bgw` | `boolean` | True if `fixture_count == 0` |
| `is_dgw` | `boolean` | True if `fixture_count == 2` |
| `home_count` | `int64` | Number of home fixtures (0/1/2) |
| `away_count` | `int64` | Number of away fixtures (0/1/2) |

### Performance columns — null if BGW, sum if DGW

| Column | Dtype | Notes |
|---|---|---|
| `total_points` | `Int64` | GW points total |
| `minutes` | `Int64` | Minutes played total |
| `goals_scored` | `Int64` | Goals scored total |
| `assists` | `Int64` | Assists total |
| `clean_sheets` | `Int64` | Clean sheets (0/1/2 for DGW) |
| `yellow_cards` | `Int64` | Yellow cards total |
| `red_cards` | `Int64` | Red cards total |
| `saves` | `Int64` | Saves total (GK) |
| `bonus` | `Int64` | Bonus points total |
| `bps` | `Int64` | Bonus point system score total |
| `xg` | `Float64` | Expected goals total |
| `xa` | `Float64` | Expected assists total |
| `xgi` | `Float64` | Expected goal involvement total |
| `goals_conceded` | `Int64` | Goals conceded total |
| `xgc` | `Float64` | Expected goals conceded |

BGW default: NULL for all performance columns. DGW rule: sum across both fixtures. NULL ≠ zero — see null semantics section.

### Defensive and tactical columns — null if BGW, sum if DGW

| Column | Dtype | Notes |
|---|---|---|
| `starts` | `Int64` | Matches started (0/1/2 for DGW) |
| `penalties_saved` | `Int64` | Penalties saved total |
| `penalties_missed` | `Int64` | Penalties missed total |
| `own_goals` | `Int64` | Own goals total |

`starts` is a binary per-fixture indicator (1 = started). DGW sum counts total matches started: 0/1/2.

Note: `tackles`, `recoveries`, `clearances_blocks_interceptions`, and `defensive_contribution` are not in the FPL API dataset and are deferred.

### Fixture difficulty columns — null if BGW

| Column | Dtype | Notes |
|---|---|---|
| `fdr_avg` | `Float64` | Average FDR across fixtures |
| `fdr_min` | `Float64` | Easiest fixture FDR |
| `fdr_max` | `Float64` | Hardest fixture FDR |

BGW default: NULL — no fixture, no difficulty. DGW rule: avg/min/max computed across both fixtures. Opponent ID at gameweek-grain is not stored for DGW — ambiguous for a player facing two different opponents. Deferred to ML feature engineering.

### FPL metrics — null if BGW, sum if DGW

| Column | Dtype | Notes |
|---|---|---|
| `influence` | `Float64` | Influence score total |
| `creativity` | `Float64` | Creativity score total |
| `threat` | `Float64` | Threat score total |
| `ict_index` | `Float64` | ICT index total |

DGW rule: sum across both fixtures. **Normalization convention:** consumers comparing these values across SGW and DGW rows must normalize by `fixture_count` (`normalized_influence = influence / fixture_count`). Failure to normalize creates a systematic DGW inflation bias.

### Dream team indicator

| Column | Dtype | Notes |
|---|---|---|
| `in_dreamteam` | `Int64` | 0 or 1, always nullable |

BGW default: 0 — market recognition exists regardless of fixtures. DGW rule: max (0 or 1) — dreamteam selection is a weekly recognition, not per-fixture cumulative.

### Market signals — never null

| Column | Dtype | Notes |
|---|---|---|
| `transfers_in` | `int64` | Players transferred in this GW |
| `ownership_count` | `int64` | Ownership count at GW deadline |
| `transfers_balance` | `int64` | Net transfer balance this GW |
| `transfers_out` | `int64` | Players transferred out this GW |

BGW default: 0. DGW rule: take-once — GW-level values recorded at deadline, not per fixture. Summing would double-count.

### Pricing — never null

| Column | Dtype | Notes |
|---|---|---|
| `purchase_price` | `float64` | Player price at GW deadline (e.g. 6.5 = £6.5m) |

### Context — always nullable

| Column | Dtype | Notes |
|---|---|---|
| `was_home` | `boolean` | True = home, False = away. NULL for DGW (ambiguous) and BGW (no fixture) |

For DGW home/away context, use `home_count` / `away_count` instead.

`fixture_context` is not stored as a column — it is derivable on demand:
```
SGW: is_bgw=False, is_dgw=False
DGW: is_dgw=True
BGW: is_bgw=True
```

### Gameweek context columns — sourced from events table

| Column | Dtype | Null rule |
|---|---|---|
| `deadline_time` | `str` | never null |
| `finished` | `int64` | never null |
| `is_previous` | `int64` | never null |
| `is_live` | `int64` | never null |
| `is_next` | `int64` | never null |
| `transfers_made` | `int64` | never null |
| `average_entry_score` | `Int64` | always nullable (null for future GWs) |
| `highest_score` | `Int64` | always nullable (null for future GWs) |

Joined at GW grain — every player row for a given GW carries the same gameweek metadata regardless of SGW/DGW/BGW status.

---

## Aggregation rules

### Null semantics — canonical rule

```
NULL  = context does not exist (no fixture, no opponent, no difficulty)
Zero  = observed outcome of zero (player played, scored zero points)
```

These must never be conflated.

**Forbidden anti-patterns:**
- `fdr=0` for BGW — implies a fixture with zero difficulty. BGW FDR must be NULL.
- `total_points=NULL` for a player who played — NULL implies unknown, not zero. A player who played and scored zero has `total_points=0`.
- `transfers_in=NULL` for BGW — market signals exist regardless of fixtures. BGW market is 0, not NULL.

### Rule table

| Column category | SGW | DGW | BGW default | Justification |
|---|---|---|---|---|
| Performance (points, goals, assists, xg, xa, xgi, minutes, saves, bonus, bps, cards) | direct | sum | NULL | True GW total |
| Clean sheets | direct | count (0/1/2) | NULL | Per-fixture clean sheet — preserves DGW info |
| Defensive/tactical (starts, penalties, own_goals) | direct | sum | NULL | Cumulative fixture-level actions |
| FPL metrics (influence, creativity, threat, ict_index) | direct | sum | NULL | Additive per-fixture scores; normalize by fixture_count for comparisons |
| Dream team | direct | max (0/1) | 0 | Weekly recognition, not cumulative |
| FDR | direct | avg/min/max | NULL | Average comparable across GW types |
| Market signals (transfers_in/out, ownership, balance) | direct | take-once | 0 | GW-level values, not fixture-level |
| Pricing, position | direct | take-once | direct | Invariant within GW |
| Schedule columns | derived | derived | explicit | Structural — from fixture presence |
| Opponent ID | direct | NOT STORED | NULL | Ambiguous at GW grain for DGW |
| `was_home` | direct | NULL | NULL | Ambiguous for DGW |

### Ambiguous cases — explicit decisions

**Clean sheet in DGW:** `clean_sheets` stores the count (0, 1, or 2) not a binary flag. Downstream analyses that need binary derive `clean_sheets > 0`. The DAL does not make this choice on behalf of consumers.

**FDR in DGW:** `fdr_avg = mean(fdr_1, fdr_2)`, `fdr_min = min`, `fdr_max = max`. All three stored. Analytical layers choose based on their question.

**Minutes in DGW:** Sum is correct. A player who plays 90 minutes in both DGW fixtures played 180 minutes that GW. Rolling window signals will see 180 — this is analytically correct. DGW represents more playing time.

**xG/xA in DGW:** Sum for historical totals. A DGW player with `xgi_sum=0.8` (0.4 per fixture) looks identical to a SGW player with `xgi=0.8`. This is a known limitation of GW-grain aggregation — documented in the research layer, not handled at the DAL level.

**Starts in DGW:** Binary per-fixture indicator (1 = started). Sum gives total matches started: 0/1/2. Comparable to SGW records.

**FPL metrics in DGW:** Summed across fixtures. A player with `influence=50` in fixture 1 and `influence=35` in fixture 2 has `influence=85`. Declared analytically intentional. Consumers must normalize by `fixture_count` when comparing across SGW and DGW rows.

**TGW non-support:** `fixture_count ∈ {0, 1, 2}`. Triple gameweeks are not supported. `validate_dgw_correctness` raises `DALContractViolation` for any row outside these bounds with an explicit TGW message. If a triple gameweek is announced, the contract requires amendment before that GW data is ingested.

---

## FIRST_COLS semantic registry

Columns resolved by taking the lowest `fixture_id` in a DGW. "Lowest fixture_id" is a hidden semantic policy — determinism does not imply correctness. Every column in `FIRST_COLS` must be classified:

| Type | Meaning | Validation implication |
|---|---|---|
| `invariant_per_gw` | Value is identical across all fixtures in the GW — taking first is safe | Assert `group[col].nunique() == 1` before aggregation |
| `canonical_first_fixture` | Intentionally takes value from the earliest fixture; semantically significant | No further assertion; documented explicitly |
| `temporally_first` | Takes value from the fixture with the lowest kickoff time | Requires ordering by `kickoff_time`, not `fixture_id` |
| `representative_arbitrary` | No analytical semantics; any fixture's value is acceptable | Document explicitly; consider DGW exclusion |

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

**Enforcement for `invariant_per_gw` columns:** Before aggregation, assert that every column declared `invariant_per_gw` has exactly one distinct value within each `(player_id, gw)` group. This is a FATAL contract violation if it fails — it catches upstream API changes that silently alter per-GW invariants.

---

## State layer causality contract

Every derived column in the state layer must declare its causality class and warmup semantics before use in any lens study.

```python
STATE_COL_CONTRACTS = {
    "points_roll3": {
        "causality": "lagged",
        "warmup_gws": 1,
        "min_obs_for_reliability": 3,
        "null_if_no_obs": True,
    },
    "minutes_roll3": {
        "causality": "lagged",
        "warmup_gws": 1,
        "min_obs_for_reliability": 3,
        "null_if_no_obs": True,
    },
    "minutes_trend": {
        "causality": "lagged",
        "warmup_gws": 4,
        "min_obs_for_reliability": 6,
        "null_if_no_obs": True,
    },
    "fixture_context": {
        "causality": "contemporaneous",
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

`warmup_gws`: minimum GW index at which the column becomes non-null.  
`min_obs_for_reliability`: observation count at which the rolling average is statistically established. Metadata for downstream consumers when computing correlations — does not change how `min_periods` works.

**`fixture_context` values:** `{"BGW", "SGW", "DGW"}` — no other values. Any lens filter on `fixture_context == "SGW"` correctly excludes BGW rows.

---

## System invariants

Three invariants apply across the entire DAL at every layer output boundary.

### Determinism invariant

Given identical inputs, all DAL outputs must be identical. No randomness. No order-dependent operations. No timestamp-dependent logic.

Implications: joins must produce deterministic output regardless of input row ordering; aggregations must use deterministic functions; sort operations must specify a complete unambiguous sort key; all staging SQL queries must include `ORDER BY` on declared PK columns.

### Temporal causality invariant

No dataset may contain information from future GWs. For any row at `(player_id, gw=N)`, all column values must be derivable from data available at or before GW N.

Without this invariant, ML models trained on this data silently learn from the future. Evaluation becomes invalid. The failure is not detectable from model outputs alone.

### Time continuity invariant

For each player in the spine, GW values must form a contiguous sequence with no gaps from GW 1 to GW 38. A player absent from GW 13 must have a BGW row — they must not simply be missing.

Without this invariant, rolling windows silently misalign. A 3-GW window at GW 15 spans GWs 15, 14, 13. If GW 13 is absent, the window silently spans 15, 14, 12 instead.

---

## Forbidden operations

### Staging

- Joining across tables
- Assuming grain without asserting it
- Computing any aggregate or derived value
- Implementing business logic (BGW/DGW handling)

### Intermediate

- Aggregating any column
- Changing grain from fixture to GW
- Embedding validation logic in join code
- Silent row loss in joins (always call `validate_join_safety`)

### Curated

- Derivation (rolling, lag, trend)
- Joining additional tables after spine completion
- Embedding validation logic inside aggregation code
- Leaving BGW rows absent (absence must never encode meaning)
- Using None/NaN to represent zero for performance columns

### Across all layers

- Missing row encoding semantics (absence ≠ zero)
- Implicit grain assumptions without assertion
- Validation logic embedded in transformation code
- Any operation that produces silent row loss or duplication
- Computing rolling features before spine is complete

---

## Required integrity tests

### Grain tests
```
test_staging_fixture_grain_unique
test_integrated_fixture_grain_unique
test_curated_gw_grain_unique
```

### Completeness tests
```
test_curated_spine_complete          — every (player_id, gw) pair exists for season range
test_curated_bgw_rows_present        — BGW GWs have explicit rows, not absent rows
```

### BGW correctness tests
```
test_bgw_fixture_count_zero
test_bgw_performance_columns_null
test_bgw_fdr_columns_null
test_bgw_opponent_columns_null
```

### DGW correctness tests
```
test_dgw_fixture_count_two
test_dgw_home_away_count_sums_to_two
test_dgw_points_sum_matches_fixtures
test_dgw_fdr_avg_between_min_and_max
test_dgw_clean_sheet_count_zero_one_or_two
```

### Null semantics tests
```
test_identity_columns_never_null
test_schedule_columns_never_null
test_performance_columns_null_only_if_no_fixture
test_fdr_columns_null_iff_bgw
test_market_columns_never_null
```

### Join safety tests
```
test_staging_to_integrated_no_row_loss
test_integrated_to_curated_no_row_loss
test_curated_spine_join_no_fan_out
```

### Column contract tests
```
test_curated_column_set_exact
test_curated_column_dtypes_exact
```

### System invariant tests
```
test_curated_time_continuity          — no GW gaps per player
test_curated_row_count_invariant      — len(spine) == n_players × n_gws
test_curated_no_future_data           — no performance data beyond current ingested GW
test_curated_fixture_count_in_bounds  — fixture_count ∈ {0, 1, 2} for all rows
test_curated_determinism              — same inputs produce identical outputs across runs
```

---

## Known limitations and deferred decisions

### Opponent ID at DGW gameweek-grain

Not stored at GW grain for DGW records. A player faces two different opponents — there is no single opponent_id that is meaningful. Both are available at fixture-grain in the intermediate layer. ML feature engineering will derive opponent-level features from fixture-grain before joining to GW grain. Deferred to ML feature engineering stage.

### Rotation vs injury vs BGW — played status ambiguity

A player with `minutes=0` in a SGW could have not been selected (rotation), been injured, or been suspended. These are not distinguishable from performance data alone. The `starts` column distinguishes started-but-unused from not-selected. A player with `starts=0` could be any of: rotation, injured, or suspended. Lineups data would allow finer distinction. `starts` is the current best-available signal.

### `was_home` for DGW and BGW

NULL for DGW (player had one home and one away fixture — no single value is meaningful) and NULL for BGW (no fixture). Use `home_count` and `away_count` for DGW home/away context. Downstream analyses needing per-fixture home/away context for DGW records must use fixture-grain data in the intermediate layer.

### Advanced defensive metrics

FPL API does not provide fine-grained defensive action metrics (tackles, recoveries, clearances/blocks/interceptions, defensive contribution). These require a separate match events data source. Deferred pending data source availability.

### State layer full contract

The state layer concern boundary is defined here but its full feature engineering contract is documented separately in `dal/state/contracts.py`. The concern is named here so the separation is explicit.

### Staging null validation

`dal/staging/` contains an inline null check (`_validate_non_nullable_columns`) that raises `ValueError` for schema-declared non-nullable columns. This is embedded validation logic. A future `validate_schema_nullability(df, schema)` module would allow staging to use the validation layer properly. Not a blocking concern.

### Naming convention migration

Current layer names (staging, integrated, curated, state) are retained. Target convention is `stg_`, `int_`, `fct_`, `feat_`. Migration requires coordinated test updates and is deferred.

### Temporary staging exception — report/db.py (Phase 9)

`report/db.py::validate_data_freshness` retains a direct call to `dal.staging.get_staged_player_histories`. This is an explicitly allowed exception pending Phase 10 (report/ → intelligence/reporting/ migration).

- **Caller:** `report/db.py` — `validate_data_freshness`
- **Staging function:** `get_staged_player_histories(db_path)`
- **Why not curated yet:** No curated accessor exists for player_histories freshness checks; introducing one solely for this call would be premature abstraction before the report layer is moved.
- **Resolution:** Phase 10 — when `report/` moves into `intelligence/reporting/`, this check should be re-evaluated and routed through an appropriate curated or state accessor.
- **All other staging access** in `report/db.py` was removed in Phase 9; `resolve_target_gw` now routes through `dal.curated.gameweek_context`.
