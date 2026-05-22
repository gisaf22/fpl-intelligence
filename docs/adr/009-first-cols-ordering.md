# FIRST_COLS ordering semantics

**Status:** Active  
**Date:** May 2026  
**Risks addressed:** SC-9, F-1, F-2  
**Implemented in:** `dal/curated/contracts.py` (`FIRST_COL_SEMANTICS`), `dal/curated/player_gameweek_spine.py`

---

## Context

When aggregating from fixture-grain to gameweek-grain, some columns cannot be summed, averaged, or counted. For these columns — player name, position, team, price, market signals — the curated layer takes the value from the "first" fixture in the gameweek.

The original implementation did not define what "first" meant. It relied on whichever row happened to appear first in the DataFrame, which in turn depended on the order of rows returned by the staging SQL queries. SQLite does not guarantee row ordering without `ORDER BY`. Two runs on the same database could return rows in different orders, meaning "first" was non-deterministic.

Beyond determinism, there was a deeper problem: "first" conflates several distinct semantic intents. For some columns, "first" is safe because the value is identical across all fixtures in the gameweek. For others, "first" is intentional — the earliest fixture's value is what you want. For still others, the ordering semantics were never stated, making it impossible to know if taking the first value was correct or arbitrary.

---

## Decision

Every column in `FIRST_COLS` is classified into one of four semantic types:

| Type | Meaning | Enforcement |
|---|---|---|
| `invariant_per_gw` | Value is identical across all fixtures in the GW — taking first is safe | Assert `group[col].nunique() == 1` before aggregation |
| `canonical_first_fixture` | Intentionally takes the value from the earliest fixture — semantically significant | Documented explicitly; no further assertion needed |
| `temporally_first` | Takes value from the fixture with the lowest kickoff time | Requires ordering by `kickoff_time`, not `fixture_id` |
| `representative_arbitrary` | No analytical semantics — any value is acceptable | Documented explicitly; consider whether the column should be DGW-excluded |

The classification is declared in `FIRST_COL_SEMANTICS` in `dal/curated/contracts.py`.

For determinism: the fixture-grain frame is sorted by `["player_id", "gw", "fixture_id"]` before any aggregation. This makes "first" mean "lowest fixture_id" consistently and reproducibly.

For `invariant_per_gw` columns: an assertion (`_assert_invariant_per_gw_columns`) runs before aggregation. If any column declared invariant has more than one distinct value within a `(player_id, gw)` group, a `DALContractViolation` is raised before the aggregation proceeds. This catches upstream API changes that silently violate the invariance assumption.

---

## Current classification

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

All current `FIRST_COLS` entries are classified as either `invariant_per_gw` or `canonical_first_fixture`. None are currently `temporally_first` or `representative_arbitrary`.

---

## Rationale for each classification

**`invariant_per_gw` columns:** Player name, position, and team do not change within a gameweek by construction — the FPL API records these at the GW deadline. Purchase price and all market signals (ownership, transfers in/out, balance) are also recorded at the GW deadline and are the same value regardless of fixture count. For these columns, taking the first value is safe — but the invariance is now asserted rather than assumed.

**`was_home` as `canonical_first_fixture`:** `was_home` is NULL for DGW rows by contract (a player with one home and one away fixture in a DGW has no single `was_home` value). In practice, the column is set to NULL for DGW regardless of which fixture is "first." The classification `canonical_first_fixture` reflects that if it were not NULL, the earliest fixture's value would be the intended semantics.

---

## Rationale for the `invariant_per_gw` assertion

Without an assertion, the code silently assumes that player name, team_id, and price are invariant within a GW. This was true historically — but if the FPL API ever returns different team_id values for the same player across two DGW fixtures (due to a transfer recorded mid-GW, or a data error), the pipeline would silently take one value without any signal that the invariance was broken.

The assertion converts this silent assumption into an explicit contract check. A violation would mean the FPL API has returned inconsistent data for a player within a single GW — a data quality issue that should be investigated before the pipeline proceeds.

---

## Alternatives considered

**No classification (original state — rejected):** The original code had no documented semantics for FIRST_COLS. The ordering was implicit, non-deterministic, and unverified. Rejected because it made determinism testing impossible and left analytical correctness unverifiable.

**Always sort by `kickoff_time` instead of `fixture_id` (considered):** Kickoff time is more analytically meaningful than fixture_id for "first." However, fixture_id ordering is already used consistently across the codebase and is itself correlated with kickoff order within a GW. Switching to kickoff_time would require schema changes (adding kickoff_time to the aggregation sort key). Deferred — if `temporally_first` columns are added in future, kickoff_time ordering should be introduced at that point.

**Use `mean` for all FIRST_COLS (rejected):** Mean is not applicable to categorical or ID columns (team_id, position_code). Sum is also not applicable. First is the only sensible aggregation for these columns, provided the semantics are clearly stated.

---

## Downstream implications

- Any column added to `FIRST_COLS` in the future must be classified in `FIRST_COL_SEMANTICS` before being accepted into the build.
- If a new column is `temporally_first`, the aggregation sort key must be updated to use `kickoff_time`.
- If a new column is `representative_arbitrary`, document why it is in the spine at all — an arbitrary column is a candidate for removal.
- The `_assert_invariant_per_gw_columns` check means that any FPL API data quality issue producing within-GW variation in a supposedly-invariant column will surface as a pipeline failure, not a silent wrong result.
