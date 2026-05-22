# dal/

Data Access Layer for fpl-intelligence. Produces the canonical `(player_id, gw)` spine used by all downstream analytics.

## Layers

| Layer | Grain | Concern |
|---|---|---|
| `staging/` | fixture | Type-cast raw SQLite tables to canonical schemas |
| `intermediate/` | fixture | Enrich with team/position/fixture context via joins |
| `curated/` | gameweek | Aggregate to GW grain, complete spine with BGW rows |
| `state/` | gameweek | Derive rolling windows, lag features, trend signals |
| `validation/` | — | Shared assertion modules called by all layers |

## Entry points

```python
from dal.access import get_curated_spine, get_state_features

spine = get_curated_spine(db_path)        # canonical (player_id, gw) spine
state = get_state_features(db_path)       # spine + rolling/lag features
```

> **Internal/test use only:** `build_player_gameweek_spine` and `build_player_gameweek_state` are valid constructors but are not the recommended consumer path. Prefer `dal.access` for all application and notebook code.

## Contract

See [DAL_CONTRACT.md](DAL_CONTRACT.md) for grain definitions, column specifications, aggregation rules, and validation invariants.
