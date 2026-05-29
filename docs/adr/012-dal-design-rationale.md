# DAL design rationale

**Status:** Active  
**Date:** May 2026  
**Supersedes:** `docs/architecture/DAL_CONTRACT.md` (deleted — code-enforced contracts live in `dal/contracts.py`, `dal/fct/fct_contracts.py`, `dal/feat/feat_contracts.py`, `dal/validation/`)

---

## Reproducibility model

The pipeline targets **deterministic** and **append-monotonic** guarantees, not source-stable guarantees.

**Source mutation policy (snapshot semantics):** The pipeline reflects current DB truth at build time. If the FPL API retroactively corrects historical data (minutes, bonus recalculation, fixture rescheduling), a rebuild from the updated DB produces updated historical rows. This is expected behavior, not a defect. Prior analysis snapshots should be dated and treated as reflecting the DB at that point in time.

Source-stable guarantees require versioned snapshot ingestion, which is out of scope.

---

## Validation severity model

Three tiers:

| Tier | Class | Behavior |
|---|---|---|
| **FATAL** | `DALContractViolation` | Raises immediately; pipeline halts |
| **WARNING** | `logger.warning` | Logged; pipeline continues |
| **AUDIT** | `logger.info("[AUDIT] ...")` | Logged for reconciliation visibility |

AUDIT is not a degraded WARNING. It marks a known, applied correction whose existence should be visible for later reconciliation. `team_id` correction during mid-season transfers is an audit event — the correction is expected and correct; it should be observable, not silenced.

---

## Null semantics

```
NULL  = context does not exist (no fixture, no opponent, no difficulty)
Zero  = observed outcome of zero (player played, scored zero points)
```

These must never be conflated.

**Forbidden anti-patterns:**
- `fdr=0` for BGW — implies a fixture with zero difficulty. BGW FDR must be NULL.
- `total_points=NULL` for a player who played — NULL means unknown, not zero. A player who played and scored zero has `total_points=0`.
- `transfers_in=NULL` for BGW — market signals exist regardless of fixtures. BGW market is 0, not NULL.
- Using `!= 0` to check nullable `Int64`/`Float64` columns — `pd.NA != 0` returns `pd.NA` (falsy), silently missing violations. Use `.notna()`.

---

## Rolling window conventions

**Lag-1 convention:** Rolling windows compute over prior GWs only, not including the current GW. At GW N, `roll5` looks at GWs N-5 through N-1. This ensures rolling signals are causal — they reflect only what was known before the GW.

**BGW skip:** BGW rows (`fixture_count=0`) have NULL performance columns. Rolling windows skip NULLs (`skipna=True`). A player with 4 actual GWs and 1 BGW in a 5-GW window computes `roll5` from those 4 values. NULLs do not prevent rolling from computing and do not count toward the window requirement. This ensures BGWs and late-season transfers do not artificially deflate rolling signals.

---

## State layer causality classes

Derived columns in the feat layer must declare a causality class:

| Class | Meaning |
|---|---|
| `lagged` | Derived from GW 1..N-1 only — safe as a pre-GW feature |
| `contemporaneous` | Uses current GW metadata (fixture structure, not performance) |
| `future_derived` | **Forbidden** — raises immediately |

`warmup_gws`: minimum GW index at which the column becomes non-null.  
`min_obs_for_reliability`: observation count at which the rolling average is statistically established. Metadata for downstream consumers — does not change `min_periods` behavior.

---

## Known limitations

**Opponent ID at DGW grain:** Not stored. A DGW player faces two different opponents — no single `opponent_id` is meaningful at GW grain. Available at fixture-grain in the intermediate layer. ML feature engineering derives opponent-level features from fixture-grain before joining to GW grain.

**Triple gameweek (TGW) non-support:** `fixture_count ∈ {0, 1, 2}` is a hard bound. Any row outside this range raises `DALContractViolation`. TGW aggregation rules have not been designed. Before any TGW data is ingested, this ADR must be amended with per-column aggregation rules, updated validation, and tests.

**`was_home` for DGW and BGW:** NULL for both. A DGW player with one home and one away fixture has no single `was_home` value. Use `home_count` / `away_count` for DGW context.

**Rotation vs injury vs BGW:** A player with `minutes=0` in a SGW could be rotation, injured, or suspended. `starts=0` does not distinguish these. Lineups data would allow finer distinction; deferred pending data source availability.

**Advanced defensive metrics:** FPL API does not provide tackles, recoveries, or clearance/block/interception data. Deferred pending a separate match events source.
