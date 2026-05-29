# dal/

Data Access Layer for fpl-intelligence. Produces the canonical `(player_id, gw)` spine used by all downstream analytics.

## Layers

| Layer | Grain | Concern |
|---|---|---|
| `staging/` | fixture | Type-cast raw SQLite tables to canonical schemas |
| `intermediate/` | fixture | Enrich with team/position/fixture context via joins |
| `fct/` | gameweek | Aggregate to GW grain, complete spine with BGW rows |
| `feat/` | gameweek | Derive rolling windows, lag features, trend signals |
| `mart/` | gameweek | Filter to cutoff GW, add position label — governed analytical output |
| `validation/` | — | Cross-cutting assertion modules (grain uniqueness, join safety) |

## Entry point

```python
from dal import get_analytics_dataset

result = get_analytics_dataset(db_path)
df = result.mart           # full (player_id, gw) analytical dataset
signals = result.signals   # governed signal columns (from FEATURE_REGISTRY)
```

`data_cutoff_gw` defaults to the max GW in the spine. Pass it explicitly for retrospective analysis.

## Contracts

All contracts are code-enforced:

| Location | Governs |
|---|---|
| `dal/fct/fct_contracts.py` | FCT spine columns, dtypes, null rules, aggregation semantics |
| `dal/feat/feat_schema.py` | Feature columns, Pandera schema, FEATURE_REGISTRY |
| `dal/feat/feat_contracts.py` | Feature column metadata (causality, warmup, min_obs) |
| `dal/fct/validation/` | FCT-layer validators (completeness, invariants, null semantics, BGW/DGW) |
| `dal/validation/` | Cross-cutting validators (grain uniqueness, join safety) |
| `dal/exceptions.py` | `ErrorCode` vocabulary, `DALContractViolation` |

**Null semantics invariant:** NULL = context does not exist (no fixture, no opponent). Zero = observed outcome of zero. Never conflate — `fdr_avg=NULL` for a BGW row is not the same as `total_points=0` for a player who played and scored nothing.
