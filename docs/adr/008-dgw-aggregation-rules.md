# DGW aggregation rules

**Status:** Active  
**Date:** May 2026  
**Risks addressed:** SC-3, SC-7, SC-10  
**Implemented in:** `dal/fct/fct_player_gameweek.py`, `dal/validation/semantics.py`

---

## Context

A double gameweek (DGW) player has two fixtures in a single FPL gameweek. The curated layer must aggregate two fixture-grain rows into one gameweek-grain row. Different column categories require different aggregation strategies.

Three specific decisions were required during stabilization:

1. **`goals_conceded` aggregation method** (was wrong — SC-3)
2. **FPL metrics aggregation and normalization convention** (undocumented — SC-7)
3. **Triple gameweek (TGW) handling** (gap in defensive contract — SC-10)

---

## Decision 1 — `goals_conceded` uses sum, not mean

**Context:** `_build_team_defensive_records` in `opponent_context.py` was aggregating `goals_conceded` using `mean` across DGW fixtures.

**Decision:** Use `sum`.

**Rationale:** Goals conceded is an additive quantity. A team that conceded 1 goal in each of two DGW fixtures conceded 2 goals that gameweek — not 1. Averaging halved the apparent defensive weakness of any DGW team and created a systematic bias in rolling opponent defensive metrics (the rolling averages of `goals_conceded_roll3` etc. for DGW teams were systematically lower than reality).

This is the same principle applied to all other performance columns: the GW total is the sum of all fixture contributions. Conceding is no different from scoring goals or earning points in this respect.

**Analytical consequence:** All prior opponent defensive context values for DGW teams are wrong. The rolling defensive metrics for teams that played DGW fixtures are systematically underestimated. These outputs must be regenerated.

---

## Decision 2 — FPL metrics (`influence`, `creativity`, `threat`, `ict_index`) stored as per-fixture mean

**Context:** These columns were previously summed across DGW fixtures, requiring consumers to normalize by `fixture_count` when comparing across SGW and DGW rows. That consumer responsibility was unenforced and created a systematic DGW inflation bias whenever forgotten.

**Decision:** Store as per-fixture mean (`mean` aggregation, not `sum`). SGW value is unchanged (mean of one). DGW value is the average of the two fixtures. DGW and SGW rows are directly comparable without any consumer normalization step.

**Rationale:** Placing the normalization obligation at the DAL eliminates the risk entirely. A consumer cannot accidentally use the wrong value because there is no unnormalized version in the output. The column contract is unambiguous: `influence` always means per-fixture influence, regardless of fixture count.

**Analytical consequence:** For DGW rows, `influence` is now the per-fixture average, not the GW total. A player with `influence=50` in each DGW fixture now shows `influence=50`, not `influence=100`. Any prior analysis that used summed DGW values without normalization was already wrong; any that correctly normalized is unaffected.

**Alternatives considered:**
- **Sum with consumer normalization (prior approach):** Unenforced, producing silent bias when forgotten. Rejected.
- **Sum + separate `*_per_fixture` columns:** Two columns for the same concept. Consumers use the wrong one. Rejected.
- **First:** Loses the second fixture's signal. Rejected.

---

## Decision 3 — Triple gameweeks are not supported; `fixture_count ∉ {0,1,2}` raises immediately

**Context:** `validate_dgw_correctness` used `fixture_count >= 2` in some places for DGW detection, which would silently mislabel a triple gameweek (TGW) player as DGW-handled. TGW aggregation has not been designed and should not proceed silently.

**Decision:** `fixture_count ∈ {0, 1, 2}` is a hard contract bound. Any row with `fixture_count` outside this set causes `DALContractViolation` to be raised with an explicit TGW message.

**Rationale:** If a TGW occurs and the pipeline were to process it silently using DGW logic, the results would be wrong in multiple ways: row-count invariant violated (wrong aggregate), aggregation rules applied incorrectly (sum columns would include three fixtures, FDR avg/min/max would need a third value), and `fixture_count=3` would silently pass the DGW validation checks.

Raising immediately is the correct behavior. It ensures TGW data cannot enter the pipeline without an explicit contract amendment that addresses all the aggregation rules for three-fixture scenarios.

**Error message:**
```
fixture_count not in {0, 1, 2} for N rows.
Triple gameweeks are not supported by the current contract.
Update docs/adr/012-dal-design-rationale.md before ingesting TGW data.
```

**Downstream implication:** Before any triple gameweek GW data is ingested, the DAL contract must be amended to define aggregation rules for each column category with three fixtures, update the validation logic, add tests, and gate the ingestion.

---

## Aggregation rule summary for all DGW columns

| Column category | DGW rule | Rationale |
|---|---|---|
| Performance (points, goals, assists, xg, xa, xgi, minutes, saves, bonus, bps, cards) | sum | True GW total — cumulative across all fixtures |
| Goals conceded | sum | Additive quantity — total conceded across both fixtures |
| Clean sheets | count (0/1/2) | Per-fixture binary; count is more informative than sum for this field |
| Defensive / tactical (starts, penalties, own_goals) | sum | Cumulative fixture-level actions |
| FPL metrics (influence, creativity, threat, ict_index) | mean (per-fixture) | DAL normalizes at source — DGW and SGW values directly comparable |
| Dream team | max (0/1) | Weekly recognition — binary, not cumulative |
| FDR | avg / min / max | Average preserves comparability; min/max retained without requiring opponent IDs |
| Market signals (transfers, ownership, balance) | take-once | GW-level values at deadline — not fixture-level |
| `was_home` | NULL | Ambiguous for a player with both home and away fixtures in a DGW |
| Opponent ID | not stored | Ambiguous at GW grain for a player facing two different opponents |
