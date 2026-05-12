# DAL_CONTRACT.md
# fpl-intelligence — Data Access Layer Contract

**Status:** ACTIVE — analytical stage contract
**Last updated:** GW 34, April 2026
**Owned by:** dal/
**Audience:** Engineers implementing or modifying the DAL,
Claude Code sessions, analytical layer design

---

## 1. Purpose and scope

This document is the authoritative contract for the
fpl-intelligence Data Access Layer. It defines what
every layer must produce, what invariants must hold,
what operations are permitted and forbidden, and how
validation is separated from transformation.

This is the analytical stage contract. It governs the
pipeline through the curated layer. The state layer
(derivation — rolling windows, lag features, trends)
is named here for completeness but its full contract
is documented separately when the feature engineering
layer is designed.

### What this contract governs

- Layer architecture and concern ownership
- Grain definitions and uniqueness guarantees
- Canonical gameweek-grain spine specification
- BGW and DGW handling rules
- Aggregation rules per column category
- Validation module design
- DAL integrity test requirements
- Anti-patterns and forbidden operations
- Known limitations and deferred decisions
- Refactor and implementation plan

### What this contract does not govern

- State layer feature engineering (deferred)
- ML modeling feature contracts (deferred)
- Research layer EDA and lens studies
- Naming convention migration (noted, deferred)

---

## 2. Grain definitions

### Two grains — explicit and enforced

**Fixture-grain** — a row exists because a fixture
was played. One row per player per fixture.

```
grain: (player_id, fixture_id)
type:  fixture-grain
```

A player with two DGW fixtures has two rows.
A player with no fixture in a BGW has zero rows.
This is the event layer — rows exist only when
something happened.

**Gameweek-grain** — a row exists because the FPL
calendar demands it. One row per player per gameweek.

```
grain: (player_id, gw)
type:  gameweek-grain
```

Every player appears in every GW regardless of
fixture count. BGWs are explicit rows. DGWs are
aggregated to a single row. This is the time-series
layer — rows exist because the decision unit
(the gameweek) demands them.

### Spine scope definition

The gameweek-grain spine is the cartesian product of
the player universe and the GW range. Both must be
explicitly defined before spine construction begins.

**Player universe**
All players appearing in the FPL API dataset for
the season. Includes players who transfer in or out
mid-season. Includes players who appear in early GWs
and disappear. Includes players who first appear in
later GWs. Every player gets a row in every GW from
GW 1 through GW 38 regardless of when they entered
the season.

Why: without this, mid-season transfers are missing
early GWs, rolling windows compute on incomplete
history, and training datasets have inconsistent
row counts per player.

**GW range**
Fixed per season as GW 1 through GW 38. Defined by
the fixture calendar, not by observed data. The spine
is constructed against the full calendar even if data
ingestion for later GWs is incomplete. Rows for future
GWs will have fixture_count=0 and performance=0 until
data is ingested — they are not BGW rows, they are
future rows. BGW rows are GWs where a fixture was
scheduled but the player's club had no fixture.

**Spine construction**
```
spine = cartesian_product(player_universe, gw_range)
spine = left_join(spine, fixture_data, on=[player_id, gw])
# Rows with no fixture match → BGW or future row
# Apply defaults per Section 5
```

**Row count invariant**
The spine must satisfy:
```
len(spine) == len(player_universe) × len(gw_range)
```
This is a hard assertion. Any deviation means a player
is missing from the universe definition or a GW is
missing from the range. Both are contract violations.

```python
def validate_row_count_invariant(df, n_players, n_gws):
    expected = n_players * n_gws
    actual   = len(df)
    assert actual == expected, (
        f"Row count violation: expected {expected} "
        f"({n_players} players × {n_gws} GWs), "
        f"got {actual}"
    )
```

### Grain ownership per layer

```
staging     → fixture-grain (inherits from raw)
integrated  → fixture-grain (enriched, not aggregated)
curated     → gameweek-grain (aggregated + completed)
state       → gameweek-grain (derived, same grain)
```

Grain change happens exactly once — in the curated
layer. No other layer changes grain.

### Grain uniqueness guarantee

Every layer must guarantee uniqueness of its declared
grain. Duplicates at any grain are a contract violation.

```python
# Enforcement pattern — called at end of every layer
def validate_grain_uniqueness(df, grain_cols, layer_name):
    dupes = (
        df.groupby(grain_cols)
        .size()
        .reset_index(name='count')
        .query('count > 1')
    )
    assert len(dupes) == 0, (
        f"{layer_name} grain violation: "
        f"{len(dupes)} duplicate ({', '.join(grain_cols)}) pairs\n"
        f"{dupes.head(10)}"
    )
```

---

## 3. Concern separation

Five concerns. Each is owned by exactly one layer.
No layer implements more than one concern in the
same module.

### Concern 1 — Transformation (staging)

Reshaping raw inputs into a normalised, typed,
consistently named form. No joins. No aggregation.
No derivation. No business logic.

Permitted:
- Column renaming
- Type casting
- String normalisation
- Null standardisation (raw nulls → typed nulls)
- Row deduplication of exact duplicates

Forbidden:
- Joins across tables
- Aggregation
- Derived columns
- Business logic of any kind
- Grain assumptions

**Opponent context is an intermediate-layer output (A-3):**
`dal/intermediate/opponent_context.py` operates on `player_fixture_base` (intermediate grain)
and produces rolling opponent defensive metrics at (player_id, gw) grain. It was previously
misclassified under `dal/state/` but correctly belongs to the intermediate layer as it does
not derive from the curated spine.

### Concern 2 — Enrichment (integrated)

Joining staging outputs to produce wider records.
Grain does not change. No aggregation. No derivation.

Permitted:
- Joins between staging outputs
- Adding context columns from reference tables
- Producing wider fixture-grain records

Forbidden:
- Aggregation of any kind
- Grain change
- Derived columns beyond direct join output
- Validation logic embedded in join code

### Concern 3 — Aggregation (curated)

Changing grain from fixture-grain to gameweek-grain.
Spine completion — producing complete (player, gw)
coverage including BGW rows. DGW and BGW semantic
enforcement.

**Aggregation boundary rule — critical**
All fixture-to-GW aggregation must complete before
spine join. The spine join may only introduce missing
rows and apply BGW defaults. No aggregation is
permitted after spine completion. This order is
non-negotiable.

```
Step 1: Aggregate fixture-grain → GW summaries
        (only for players and GWs with fixtures)
Step 2: Construct full spine (cartesian product)
Step 3: Left-join GW summaries onto spine
        (rows with no match become BGW rows)
Step 4: Apply BGW defaults to unmatched rows
Step 5: Validate — call validation modules
```

Any aggregation that occurs after Step 3 is a
contract violation. It risks mixing real aggregated
data with imputed BGW defaults in the same operation.

Permitted:
- Fixture-grain to gameweek-grain aggregation
- Spine completion via calendar cross-join
- BGW row insertion with explicit defaults
- DGW column aggregation per defined rules
- Calling validation modules after aggregation

Forbidden:
- Derivation (rolling, lag, trend)
- Enrichment (additional joins after aggregation)
- Embedded validation logic (use validation modules)
- Any operation that changes grain beyond
  fixture → gameweek
- Aggregation after spine join

### Concern 4 — Derivation (state)

Adding derived columns to gameweek-grain records.
Grain does not change. No joins. No aggregation.

Permitted:
- Rolling window calculations
- Lag features
- Trend signals
- Ratio and composite signals

Forbidden:
- Grain change
- Row count change
- Joins to external tables
- Introduction of new entities not in player_gw_base
- Aggregation
- Modification of non-derived columns
- Use of data from future GWs (temporal causality)

**State layer named constraints (enforced in
state layer contract when written):**
- Input must be player_gw_base only
- Must not change grain or row count
- All derived columns must be deterministic functions
  of (player_id, gw) and historical data only —
  no future data permitted
- Rolling window at GW N may only use GW N and earlier
- Every feature must be computable at prediction time
  without access to future GW data

**State layer rolling window specification (lag-1 convention):**
Rolling windows compute over *prior* GWs only (lag-1), not including the current GW.
A rolling window at GW N looks back to GW N-1, N-2, ... (not forward).
```
  At GW 6, roll5 looks at GWs 1-5 (5 prior GWs)
  At GW 7, roll5 looks at GWs 2-6 (5 prior GWs)
```
Edge case: NULL handling
- BGW rows (fixture_count=0) have NULL performance columns
- Pre-transfer rows for late-season joiners have NULL performance columns
- Rolling window calculations skip these NULLs (pandas skipna=True by default)
- If a player had 4 actual GWs + 1 BGW in a 5-GW window, roll5 computes from those 4 available values
- NULLs do not prevent the rolling from computing and do not count toward the window requirement
- Lower bound: A rolling window computes if at least 1 non-NULL value exists in the window

Justification: This ensures late-season transfers and scheduled BGWs do not artificially deflate
rolling signals. A player who joined at GW 10 does not get NaN for roll5 at GW 15 just because
GWs 1-9 are NULL — they get a meaningful average of their actual GWs (10-14).

**State layer is out of scope for this contract.**
Named here so the concern boundary is explicit.
Full state layer contract documented separately.

### Concern 5 — Validation (cross-cutting)

Assertions that invariants hold. No data changes.
Lives in standalone modules imported by any layer.
Not embedded inside transformation, enrichment,
or aggregation code.

```
dal/validation/
    grain.py          → grain uniqueness checks
    completeness.py   → row completeness checks
    semantics.py      → BGW/DGW correctness checks
    joins.py          → join safety checks
    contracts.py      → column contract checks
    nulls.py          → null semantics checks
```

Every validation function:
- Takes a dataframe and parameters
- Returns nothing on pass
- Raises AssertionError with descriptive message on fail
- Has no side effects

---

## 4. Validation module contract

### validate_grain_uniqueness

```python
validate_grain_uniqueness(df, grain_cols, layer_name)
```

Asserts no duplicate rows exist for the declared grain.
Called at the end of every layer function.
Failure means a join produced fan-out or a deduplication
step is missing.

### validate_row_completeness

```python
validate_row_completeness(df, player_ids, gw_range)
```

Asserts every (player_id, gw) combination exists in
the gameweek-grain spine. Called after curated layer
spine completion. Failure means BGW rows are missing
or a player is absent from a GW they should appear in.

### validate_bgw_correctness

```python
validate_bgw_correctness(df)
```

For all rows where is_bgw=True:
- fixture_count == 0
- All performance columns (total_points, minutes,
  goals_scored, assists, xg, xa, xgi, goals_conceded,
  xgc, clean_sheets, yellow_cards, red_cards, saves,
  bonus, bps) are NULL
- fdr_avg, fdr_min, fdr_max are NULL
- opponent context columns are NULL

Failure means a BGW row has been populated with
fixture data that does not exist.

### validate_dgw_correctness

```python
validate_dgw_correctness(df)
```

For all rows where is_dgw=True:
- fixture_count == 2
- home_count + away_count == 2
- points_sum is the sum of both fixture points
- fdr_avg is not NULL
- fdr_min <= fdr_avg <= fdr_max

Failure means a DGW row has not been correctly
aggregated from its component fixtures.

### validate_null_semantics

```python
validate_null_semantics(df, rules)
```

Rules is a dict mapping column names to their
null semantic — either 'never_null', 'null_if_bgw',
or 'always_nullable'. Asserts each column conforms.

Failure means a column is null when it should not be,
or populated when it should be null (e.g. performance
columns populated in a BGW row).

### validate_join_safety

```python
validate_join_safety(left_n, right_n, result_n,
                     join_type, description)
```

For left joins: asserts result_n == left_n (no row loss).
For inner joins: asserts result_n <= min(left_n, right_n).
For cross joins: asserts result_n == left_n * right_n.

Failure means a join silently dropped or duplicated rows.
Called immediately after every join operation.

### validate_column_contract

```python
validate_column_contract(df, expected_cols, dtypes)
```

Asserts df.columns contains exactly expected_cols
with correct dtypes. No extra columns. No missing
columns. Called at layer output boundary.

### validate_time_continuity

```python
validate_time_continuity(df, player_col='player_id',
                          gw_col='gw')
```

For each player_id, asserts that GW values form a
contiguous sequence with no gaps within the defined
GW range.

```python
def validate_time_continuity(df, player_col='player_id',
                              gw_col='gw'):
    for player_id, group in df.groupby(player_col):
        gws = sorted(group[gw_col].tolist())
        expected = list(range(min(gws), max(gws) + 1))
        assert gws == expected, (
            f"Time continuity violation for "
            f"player_id={player_id}: "
            f"missing GWs {set(expected) - set(gws)}"
        )
```

Failure means a player has missing GW rows in the
spine. Rolling windows will silently misalign —
a 3-GW window at GW 15 will span incorrect GWs
if GW 13 is absent. Called after curated spine
completion and after validate_row_count_invariant.

### validate_row_count_invariant

```python
validate_row_count_invariant(df, n_players, n_gws)
```

Asserts len(df) == n_players × n_gws.
Called immediately after spine completion.
Failure means a player is missing from the universe
definition or a GW is missing from the range.
Both are spine scope violations per Section 2.

### validate_no_future_data

```python
validate_no_future_data(df, gw_col='gw',
                         reference_gw=None)
```

For curated layer: asserts that no row contains
data from a GW later than its own GW value.
Specifically — no performance column for row GW N
can be derived from fixture data at GW N+1 or later.

For current season operation where reference_gw is
provided: asserts that rows for GWs beyond
reference_gw have only BGW-equivalent defaults —
no performance data for future GWs.

Failure means temporal causality is violated.
Any ML model trained on this data will silently
overfit to future information.

---

## 5. Canonical gameweek-grain spine contract

This is the authoritative specification for the
curated layer output — the complete (player, gw)
table that all downstream analysis builds on.

### Canonical base table — player_gw_base

The curated layer produces the single canonical base
table. Its target name is player_gw_base. This table:

- Is the only permitted source for all downstream
  analytics and the state layer
- Is the only table used to define ML targets
- Is the only input allowed to the state layer
- Must not be bypassed by any downstream logic

This is a design principle and code review expectation.
Analysts pulling from the integrated layer or using
fixture-grain data to compute GW-level targets are
in violation of this contract.

The current implementation uses the name produced
by build_player_gameweek_spine(). The target name
player_gw_base will be adopted as part of the naming
migration noted in Section 9.

### Grain and completeness guarantee

```
grain:        (player_id, gw)
uniqueness:   enforced — exactly one row per pair
completeness: enforced — every player in player
              universe in every GW in gw_range
              (see spine scope in Section 2)
row_count:    enforced — n_players × n_gws exactly
BGW rows:     present — fixture_count=0, is_bgw=True
DGW rows:     present — fixture_count=2, is_dgw=True
              aggregated per rules in Section 6
fixture_count bounds: fixture_count ∈ {0, 1, 2}
              This bound is explicitly enforced.
              Logic must not assume max=2 in code —
              use fixture_count == 2 not
              fixture_count > 1 for DGW detection.
              Future edge cases (postponements
              rescheduled within GW) may produce
              fixture_count=3 in rare circumstances.
              The system must not silently mishandle
              these — they should raise a validation
              error pending explicit design decision.
```

### Temporal causality guarantee

For any row (player_id, gw):
- All columns must be computable using data from
  that GW and earlier only
- No performance column may contain data from a
  future GW
- This applies strictly to the curated layer

Violation means ML models will silently overfit
to future information. validate_no_future_data
is called at curated layer output boundary.

### Column specification

#### Identity columns — never null

```
player_id        int64    FPL player identifier
gw               int64    Gameweek number (1-38)
player_name      string   Display name
team_id          int64    Current team identifier — see BGW team_id rule below
position_code    int64    FPL position code (1=GK, 2=DEF, 3=MID, 4=FWD)
position_label   string   Human-readable position label
```

**BGW team_id semantic rule:**
For BGW rows (fixture_count=0, is_bgw=True), team_id carries the player's team as of
the most recent non-BGW GW strictly before the BGW. This is temporally causal — it
uses only information available prior to the BGW and reflects the club the player was
representing at that point in the season.

It is NOT the player's latest-known team across all GWs. For a player who transfers
teams between GW 2 and GW 4 with a BGW in GW 3, the GW 3 BGW row carries team_id
from GW 2 (the last played GW), not GW 4 (the post-transfer GW).

Implementation constraint: `_build_player_info` is called on non-BGW rows only.
For each BGW row in the spine, team_id is filled from the most recent non-BGW GW
at or before that GW, using a merge-as-of / backward lookup on the aggregated
fixture data.

#### Schedule columns — never null

```
fixture_count    int64    0 (BGW), 1 (SGW), 2 (DGW)
is_bgw           boolean  True if fixture_count == 0
is_dgw           boolean  True if fixture_count == 2
home_count       int64    Number of home fixtures (0/1/2)
away_count       int64    Number of away fixtures (0/1/2)
```

#### Performance columns — null if BGW, sum if DGW

```
total_points     Int64    GW points total (nullable)
minutes          Int64    Minutes played total (nullable)
goals_scored     Int64    Goals scored total (nullable)
assists          Int64    Assists total (nullable)
clean_sheets     Int64    Clean sheets (0/1/2 for DGW, nullable)
yellow_cards     Int64    Yellow cards total (nullable)
red_cards        Int64    Red cards total (nullable)
saves            Int64    Saves total (GK, nullable)
bonus            Int64    Bonus points total (nullable)
bps              Int64    Bonus point system score total (nullable)
xg               Float64  Expected goals total (nullable)
xa               Float64  Expected assists total (nullable)
xgi              Float64  Expected goal involvement total (nullable)
goals_conceded   Int64    Goals conceded total (nullable)
xgc              Float64  Expected goals conceded (nullable)
```

BGW default: NULL for all performance columns (including goals_conceded and xgc).
DGW rule: sum across both fixtures.
Rationale: NULL semantics — BGW has no fixture context, so performance is undefined (NULL), not zero. Rolling window calculations in state layer skip NULL values (pandas rolling default). Historical analysis of fixture-grain data handles DGW aggregation correctly.

#### Defensive and tactical columns — null if BGW, sum if DGW

```
starts           Int64    Matches started (0/1/2 for DGW, nullable)
penalties_saved  Int64    Penalties saved total (nullable)
penalties_missed Int64    Penalties missed total (nullable)
own_goals        Int64    Own goals total (nullable)
```

BGW default: NULL for all defensive/tactical columns.
DGW rule: sum across both fixtures (except `starts` which counts total matches started: 0/1/2).
Rationale: Fixture-grain defensive actions sum across all GW fixtures. `starts` is a binary per-fixture indicator (1 = started, 0 = did not start), so sum across DGW fixtures gives count of matches started (0/1/2). NULL for BGW because no fixture context exists.

**Note:** `tackles`, `recoveries`, `clearances_blocks_interceptions`, and `defensive_contribution` are not in the FPL API dataset and are deferred. See Section 10.

#### Fixture difficulty columns — null if BGW

```
fdr_avg          Float64  Average FDR across fixtures (nullable)
fdr_min          Float64  Easiest fixture FDR (nullable)
fdr_max          Float64  Hardest fixture FDR (nullable)
```

BGW default: NULL — no fixture, no difficulty.
DGW rule: avg/min/max computed across both fixtures.
Rationale: average preserves difficulty signal in a
form comparable across SGW and DGW records. Min and
max retained for analytical completeness without
storing opponent IDs at this grain.

Opponent ID at gameweek-grain is not stored for DGW —
deferred to ML feature engineering stage. See Section 9.

#### FPL influence/creativity/threat metrics — null if BGW, sum if DGW

```
influence        Float64  Influence score total (nullable)
creativity       Float64  Creativity score total (nullable)
threat           Float64  Threat score total (nullable)
ict_index        Float64  ICT index (influence+creativity+threat) total (nullable)
```

BGW default: NULL — no fixture context.
DGW rule: sum across both fixtures.
Rationale: FPL's Influence/Creativity/Threat are per-fixture metrics. Sum preserves additive nature for GW aggregation. ict_index is composite but follows same rule (sum of component scores). Analytical layers can compute derived metrics (rate per match, per minute) as needed.

#### Dream team indicator — always nullable

```
in_dreamteam     Int64    Whether player was in FPL dreamteam (0/1, nullable)
```

BGW default: 0 — market recognition exists regardless of fixtures.
DGW rule: max (0 or 1) — either the player was in dreamteam that GW or not, not cumulative across fixtures.
Rationale: Dreamteam selection is a weekly recognition, not per-fixture. A DGW player is either in or out of the official dreamteam for that GW.

#### Market signals — never null, GW-level values

```
transfers_in     int64    Players transferred in this GW
ownership_count  int64    Ownership count at GW deadline
transfers_balance int64   Net transfer balance this GW
transfers_out    int64    Players transferred out this GW
```

BGW default: 0 — market activity exists regardless
of fixture count.
DGW rule: take-once — these are GW-level values, not
fixture-level. No aggregation needed.
Rationale: market signals are recorded at GW deadline,
not per fixture. A DGW player has one transfers_in
value for the week, not two. transfers_out mirrors
transfers_in (net outflow from the squad).

#### Pricing columns — never null

```
purchase_price   float64  Player price at GW deadline in FPL units
                          (e.g. 6.5 = £6.5m)
```

#### Context columns — always nullable

```
was_home         boolean  True if home fixture, False if away.
                          NULL for DGW records (ambiguous — use
                          home_count / away_count instead).
                          NULL for BGW records (no fixture).
```

fixture_context is not stored as a column.
It is derivable on demand from is_bgw and is_dgw:
  SGW: is_bgw=False, is_dgw=False
  DGW: is_dgw=True
  BGW: is_bgw=True
Use those boolean columns directly in downstream
analysis rather than deriving a string column.

#### Gameweek context columns — sourced from events table

```
deadline_time        str     GW deadline timestamp (never null)
finished             int64   Whether GW is finished — never null
is_previous          int64   Whether this is the previous GW — never null
is_live              int64   Whether this GW is in progress — never null
is_next              int64   Whether this is the next GW — never null
transfers_made       int64   Total transfers made this GW — never null
average_entry_score  Int64   Average manager score (null for future GWs)
highest_score        Int64   Highest score this GW (null for future GWs)
```

These columns are joined from the events table at GW grain and apply equally
to SGW, DGW, and BGW rows — every player row for a given GW carries the same
gameweek metadata.

---

## 6. Aggregation rules — explicit and justified

### Null semantics — canonical rule

This rule applies across all layers and all columns.

```
NULL  = context does not exist
        (no fixture, no opponent, no difficulty)

Zero  = observed outcome of zero
        (player played, scored zero points)
```

These must never be conflated.

**Forbidden anti-patterns:**
- Using 0 for missing FDR when no fixture exists —
  FDR=0 implies a fixture with zero difficulty, which
  is meaningless. BGW FDR must be NULL.
- Using NULL for performance metrics when a player
  played — NULL implies unknown, not zero. A player
  who played 90 minutes and scored zero points has
  total_points=0, not NULL.
- Using NULL for market signals in BGW — transfers_in
  and ownership_count exist regardless of fixtures.
  BGW market signals are 0 (no transfers), not NULL.

**Enforcement:** validate_null_semantics is called
at the curated layer output boundary with the rules
defined in Section 5 column specification.

### Rule table — per column category

| Column category | SGW rule | DGW rule | BGW default | Justification |
|---|---|---|---|---|
| Performance (points, goals, assists, xg, xa, xgi, minutes, saves, bonus, bps, cards) | direct | sum | NULL | True GW total — what actually happened |
| Clean sheets | direct | count (0/1/2) | NULL | Per-fixture clean sheet, not binary — preserves DGW information |
| Defensive/tactical (starts, penalties_saved, penalties_missed, own_goals) | direct | sum | NULL | Cumulative fixture-level actions across GW |
| FPL metrics (influence, creativity, threat, ict_index) | direct | sum | NULL | Additive per-fixture scores across GW |
| Dream team indicator (in_dreamteam) | direct | max (0/1) | 0 | Weekly recognition, not cumulative |
| FDR | direct | avg, min, max | NULL | Average comparable across GW types; min/max retained without requiring opponent ID |
| Market signals (transfers_in, transfers_out, ownership, balance) | direct | take-once | 0 | GW-level values, not fixture-level |
| Position | direct | take-once | direct | Invariant within player |
| Schedule (fixture_count, is_bgw, is_dgw, home_count, away_count) | derived | derived | explicit | Structural columns derived from fixture presence |
| Opponent ID | direct | NOT STORED | NULL | Ambiguous at GW grain for DGW — deferred |
| was_home | direct | NULL | NULL | Ambiguous for DGW — use home_count / away_count |

### Ambiguous cases — explicit decisions

**Clean sheet in DGW**
A player can keep a clean sheet in one DGW fixture
and concede in the other. clean_sheets column stores
the count (0, 1, or 2) not a binary flag. This
preserves the full information. Downstream analyses
that need a binary "kept at least one clean sheet"
derive it as clean_sheets > 0. The DAL does not make
this analytical choice on behalf of downstream users.

**FDR in DGW**
fdr_avg = mean(fdr_fixture_1, fdr_fixture_2).
fdr_min = min(fdr_fixture_1, fdr_fixture_2).
fdr_max = max(fdr_fixture_1, fdr_fixture_2).
All three stored. Analytical layers choose which
to use based on their question. The DAL provides
the complete picture without deciding.

**Minutes in DGW**
Sum is correct. A player who plays 90 minutes in
both DGW fixtures played 180 minutes that GW. Rolling
window signals (minutes_roll3) will see 180 minutes
for DGW GWs. This is analytically correct — a DGW
appearance genuinely represents more playing time.
The signal layer documents this as a known DGW effect,
not a data error.

**xG and xA in DGW**
Sum is correct for historical totals. A DGW player
with xgi_sum=0.8 (0.4 per fixture) looks identical
to a SGW player with xgi=0.8 from one game when
viewed at GW grain. This is a known limitation of
GW-grain aggregation documented in the research layer.
The DAL does not attempt to normalise this — the
research layer handles it as a DGW caveat in signal
studies.

**Starts in DGW**
`starts` is a binary per-fixture indicator (1 = player started, 0 = did not start).
In a DGW, sum across both fixtures (0/1/2) to count total matches started.
A player who started both DGW matches has starts=2, one match has starts=1, neither has starts=0.
This accurately reflects GW participation level and is comparable to SGW records (SGW: 0 or 1).

**Defensive metrics in DGW**
Tackles, recoveries, clearances, and other defensive actions are summed across both fixtures.
A player with 5 tackles in fixture 1 and 3 in fixture 2 has tackles=8 for the GW.
This is the true cumulative defensive contribution for that week. Analytical layers can 
normalize (per match, per minute) as needed.

**FPL metrics (influence, creativity, threat, ict_index) in DGW — SC-7 declared intent**
These are summed across fixtures. A player with influence=50 and creativity=40 (90 total ICT)
in fixture 1, and influence=35, creativity=45 (80 total ICT) in fixture 2, has:
- influence = 85
- creativity = 85
- threat = (sum of threat values from both fixtures)
- ict_index = 170 (sum of both fixtures' ict_index values)
This preserves the full FPL signal contribution for the GW. Note: ict_index is composite, so
summing makes sense (it's already the sum of influence+creativity+threat per fixture).

Normalization convention for DGW comparisons: consumers comparing influence, creativity,
threat, or ict_index across SGW and DGW rows must normalize by fixture_count:
  normalized_influence = influence / fixture_count
Failure to normalize creates a systematic DGW inflation bias in signal studies.

**TGW (triple gameweek) non-support**
The pipeline assumes fixture_count ∈ {0, 1, 2}. Triple gameweeks are not supported.
If a triple gameweek is announced, the pipeline requires a contract amendment before
the affected GW data is ingested. validate_dgw_correctness will raise DALContractViolation
for any row with fixture_count not in {0, 1, 2} with an explicit TGW error message.

---

## 7. System invariants

These invariants apply to the entire DAL system.
They are not layer-specific. They must hold at
every layer output boundary.

### Determinism invariant

Given identical inputs, all DAL outputs must be
identical. No randomness. No order-dependent
operations. No timestamp-dependent logic.

Implications:
- Joins must produce deterministic output regardless
  of input row ordering
- Aggregations must use deterministic functions
  (sum, min, max, count — not sample or random)
- Any sort operation must specify a complete,
  unambiguous sort key
- No use of Python's random, numpy.random, or
  pandas.sample without a fixed seed

Failure means results cannot be reproduced, tests
become flaky, and debugging is intractable.

### Temporal causality invariant

No dataset may contain information from future GWs.
For any row at (player_id, gw=N), all column values
must be derivable from data available at or before
GW N.

This applies strictly to curated layer outputs.
It applies with equal strictness to the state layer
when that contract is written.

Without this invariant, ML models trained on this
data silently learn from the future. Evaluation
becomes invalid. The failure is not detectable
from model outputs alone — it requires data audit.

### Time continuity invariant

For each player in the spine, GW values must form
a contiguous sequence with no gaps from GW 1 to
GW 38. A player absent from GW 13 must have a BGW
row at GW 13 — they must not simply be missing.

Without this invariant, rolling windows silently
misalign. A 3-GW rolling window at GW 15 spans
GW 15, 14, 13. If GW 13 is absent, the window
silently spans GW 15, 14, 12 instead. The error
is undetectable without explicit continuity checks.

---

## 8. Forbidden operations — anti-patterns

### Forbidden in staging

- Joining across tables
- Assuming grain of raw input without asserting it
- Computing any aggregate or derived value
- Implementing business logic (BGW/DGW handling)

**Why:** Staging is transformation only. Business
logic in staging is untestable as a unit and creates
hidden dependencies between raw data structure and
business rules.

### Forbidden in integrated

- Aggregating any column
- Changing grain from fixture to GW
- Embedding validation logic in join code
- Silent row loss in joins (always validate_join_safety)

**Why:** Integrated is enrichment only. Aggregation
in the enrichment layer means BGW/DGW logic is spread
across two layers and cannot be tested or changed
independently.

### Forbidden in curated

- Derivation (rolling, lag, trend)
- Joining additional tables after spine completion
- Embedding validation logic inside aggregation code
- Leaving BGW rows absent (absence must never encode meaning)
- Using None/NaN to represent zero for performance columns

**Why:** Curated is aggregation and spine completion
only. Mixing derivation into the aggregation layer
means rolling windows are computed on partially-complete
data. BGW row absence creates silent null propagation
in all downstream rolling calculations.

### Forbidden across all layers

- Missing row encoding semantics (absence ≠ zero)
- Implicit grain assumptions without assertion
- Validation logic embedded in transformation code
- Any operation that produces silent row loss or duplication
- Computing rolling features before spine is complete

---

## 9. DAL integrity tests vs EDA-0

### Separation of concerns

DAL integrity tests and EDA-0 both validate data
correctness but they ask different questions and
live in different layers.

```
DAL integrity tests
  Question:  Does the DAL produce correct outputs?
  Scope:     DAL layer invariants — grain, completeness,
             BGW/DGW semantics, null rules, join safety
  Lives in:  pipeline/tests/
  Runs when: Every DAL code change
  Frequency: Continuous — part of test suite
  Owner:     DAL layer

EDA-0
  Question:  Is the analytical dataset correct
             for this specific study?
  Scope:     Study-specific — lag alignment, rolling
             window construction, leakage check,
             join row count for study population
  Lives in:  research/eda/notebooks/
  Runs when: Before each study programme
  Frequency: Per study cycle
  Owner:     Research layer
```

EDA-0 assumes DAL integrity tests pass. It does not
re-test DAL invariants. If EDA-0 finds a BGW null
issue, that is a DAL test gap — the fix goes in
pipeline/tests/, not in EDA-0.

### Required DAL integrity tests

These tests must exist and pass at all times.

**Grain tests**
```
test_staging_fixture_grain_unique
test_integrated_fixture_grain_unique
test_curated_gw_grain_unique
```

**Completeness tests**
```
test_curated_spine_complete
  — every (player_id, gw) pair exists for season range
test_curated_bgw_rows_present
  — BGW GWs have explicit rows, not absent rows
```

**BGW correctness tests**
```
test_bgw_fixture_count_zero
test_bgw_performance_columns_zero
test_bgw_fdr_columns_null
test_bgw_opponent_columns_null
```

**DGW correctness tests**
```
test_dgw_fixture_count_two
test_dgw_home_away_count_sums_to_two
test_dgw_points_sum_matches_fixtures
test_dgw_fdr_avg_between_min_and_max
test_dgw_clean_sheet_count_zero_one_or_two
```

**Null semantics tests**
```
test_identity_columns_never_null
test_schedule_columns_never_null
test_performance_columns_null_only_if_no_fixture
test_fdr_columns_null_iff_bgw
test_market_columns_never_null
```

**Join safety tests**
```
test_staging_to_integrated_no_row_loss
test_integrated_to_curated_no_row_loss
test_curated_spine_join_no_fan_out
```

**Column contract tests**
```
test_curated_column_set_exact
test_curated_column_dtypes_exact
```

**System invariant tests**
```
test_curated_time_continuity
  — every player has contiguous GW sequence, no gaps
test_curated_row_count_invariant
  — len(spine) == n_players × n_gws exactly
test_curated_no_future_data
  — no performance data exists for GWs beyond
    the current ingested GW
test_curated_fixture_count_in_bounds
  — fixture_count ∈ {0, 1, 2} for all rows
test_curated_determinism
  — same inputs produce identical outputs across runs
```

### Current test coverage — gaps

The existing 76 tests cover:
- Column presence (curated and state)
- Basic spine construction
- Some null handling

Current gaps against this contract:
- No explicit BGW row presence test
- No DGW aggregation correctness tests
- No join safety tests
- No null semantics enforcement tests
- No grain uniqueness tests for staging or integrated
- No spine completeness test across full season range

These gaps are the implementation backlog for the
DAL integrity test suite. They do not invalidate
existing tests — they are additive.

---

## 10. Known limitations and deferred decisions

### Opponent ID at DGW gameweek-grain

Not stored at GW grain for DGW records. Ambiguous —
a player faces two different opponents and there is
no single opponent_id that is meaningful. Both
opponent IDs are available at fixture-grain in the
integrated layer. ML feature engineering will derive
opponent-level features (is_top_six_opponent,
opponent_attacking_xg_avg) from fixture-grain before
joining to GW grain. Deferred to ML feature
engineering stage.

### Rotation vs injury vs BGW — played status ambiguity

A player with minutes=0 in a SGW could have:
- Not been selected (rotation)
- Been injured and not played
- Been suspended

These are not distinguishable from performance data
alone. The BGW row (fixture_count=0) is
distinguishable — the player had no fixture. But
within SGW and DGW records, a player with minutes=0
has an ambiguous reason. The `starts` column (now in
spine contract, Section 5) provides a binary indicator
of whether the player was in the starting lineup, which
distinguishes selected-and-started from not-selected.
A player with starts=1 but minutes=0 was selected as
a starter but unused. A player with starts=0 could be
rotation, injured, or suspended. Lineups data will
eventually allow finer distinction (starter vs bench vs
not-selected). The `starts` column is the current
best-available signal for participation status.

### was_home for DGW and BGW records

was_home is present in the spine for SGW records
(True if home fixture, False if away). It is NULL
for DGW records — a player with one home and one
away DGW fixture has no single was_home value.
Use home_count and away_count instead for DGW
home/away context. It is also NULL for BGW records
where no fixture exists. Downstream analyses that
need home/away context for DGW records must access
fixture-grain data in the integrated layer.
Documented as a known limitation of GW-grain
aggregation.

### Advanced defensive metrics (tackles, recoveries, clearances, defensive_contribution)

The FPL API does not provide fine-grained defensive action metrics (tackles, recoveries, 
defensive clearances/blocks/interceptions, or derived defensive contribution scores) at the 
gameweek level. These would require a separate lineups/match events data source. Currently 
documented as deferred pending availability of additional data sources. Available defensive 
signal is limited to `starts` (player started fixture) and `own_goals`. Deferred — not a 
blocking concern at this stage.

### State layer contract

Derivation concern — rolling windows, lag features,
trend signals. Out of scope for this contract.
Full state layer contract documented when feature
engineering layer is designed. The concern boundary
is defined here (Section 3) so the separation is
explicit even though the contract is deferred.

### Staging null validation

dal/staging.py contains an inline null
check in _validate_non_nullable_columns that
raises ValueError for schema-declared nullable=False
columns. This is embedded validation logic in the
transformation layer. No validation module currently
accepts a Schema object — validate_null_semantics
operates on semantic rules specific to the curated
layer. A future validate_schema_nullability(df, schema)
module would allow staging to use the validation
layer properly. Deferred — not a blocking concern
at this stage.

### Naming convention migration

Current layer names (staging, integrated, curated,
state) are retained. Industry-standard prefixes
(stg_, int_, fct_, feat_) are the target convention.
Migration is a future task that requires coordinated
test updates. Current names are documented as legacy.
Target names are noted here for awareness.

```
Current → Target
staging    → stg_
integrated → int_
curated    → fct_ (fact table — complete, aggregated)
state      → feat_ (feature table — derived signals)
```

---

## 11. Implementation status

All eight refactor phases are complete as of May 2026.

```
Phase 1   Validation modules        ✓ complete
Phase 2   Integrity test suite      ✓ complete
Phase 3   BGW spine completion      ✓ complete
Phase 4   DGW aggregation           ✓ complete
Phase 4b  Defensive/FPL metrics     ✓ complete
Phase 5   Null semantics            ✓ complete
Phase 6   Join safety               ✓ complete
Phase 7   Concern separation        ✓ complete
Phase 8   Column contract           ✓ complete
```

The DAL is stable. 331 tests pass. Column contract enforced via `SPINE_COLS` and `DTYPES` in `dal/curated/contracts.py` — `test_dal_invariants.py` derives its expected set directly from those constants.

---

## Document control

This document is the source of truth for the DAL
contract. Claude Code implements against this document.
Any deviation requires updating this document first.

Permitted updates:
- Adding new column specifications with justification
- Documenting new known limitations
- Updating the refactor plan as phases complete

Not permitted:
- Changing aggregation rules without updating tests
- Adding deferred decisions to active scope without
  a corresponding implementation phase
- Removing known limitations without implementing
  the deferred solution

| Version | Date | Change |
|---|---|---|
| 1.0 | April 2026 | Initial contract. Five concerns defined. Canonical spine specified. BGW/DGW rules documented. Eight-phase refactor plan. |
| 1.1 | April 2026 | Added spine scope definition (player universe, GW range, cartesian product, row count invariant). Added canonical base table designation (player_gw_base). Added aggregation boundary rule (aggregation before spine join). Added time continuity invariant. Added null semantics canonical rule with anti-patterns. Added fixture_count ∈ {0,1,2} explicit bound. Added temporal causality guarantee to spine section. Added Section 7 system invariants (determinism, temporal causality, time continuity). Added validate_time_continuity, validate_row_count_invariant, validate_no_future_data to validation modules. Added system invariant tests. Strengthened state layer named constraints. Sections renumbered to 11. |
| 1.2 | April 2026 | Phase 8 finalisation. Six column gaps resolved. fixture_context removed from contract — derivable on demand from is_bgw and is_dgw. was_home added to spine and Section 5 (SGW: populated, DGW/BGW: NULL, always_nullable). position_label removed from spine — redundant with position_code. purchase_price, goals_conceded, xgc added to Section 5 with null rules. test_curated_column_set_exact and test_curated_column_dtypes_exact written. Column contract fully enforced. |
| 1.3 | May 2026 | Expanded column specification (Section 5). Added defensive/tactical columns (starts, tackles, recoveries, clearances_blocks_interceptions, defensive_contribution, penalties_saved, penalties_missed, own_goals). Added FPL metrics (influence, creativity, threat, ict_index, in_dreamteam). Added transfers_out to market signals. Updated aggregation rule table (Section 6) with four new categories and justifications. Added ambiguous case documentation for starts, defensive metrics, and FPL metrics in DGW. Updated Section 10 known limitations — starts column addresses rotation/injury ambiguity. Added Phase 4b (Defensive/FPL metrics column aggregation) to refactor plan with test specifications. |
| 1.4 | May 2026 | Column spec corrections. Added position_label (never null, string). Added gameweek context columns (deadline_time, finished, is_previous, is_live, is_next, transfers_made, average_entry_score, highest_score) — joined at GW grain, present on all rows. Corrected dtypes: player_name string not str, is_bgw/is_dgw boolean not bool, fdr_avg/min/max Float64 not float64. Fixed transfers_balance aggregation rule: GW-grain value (first, not sum) — summing doubled DGW values. Section 11 refactor plan collapsed to completion summary — all phases done, 331 tests passing. |