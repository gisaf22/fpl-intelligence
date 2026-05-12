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
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
spine = build_player_gameweek_spine(db_path)   # canonical (player_id, gw) spine

from dal.state.player_gameweek_state import build_player_gameweek_state
state = build_player_gameweek_state(spine)     # spine + rolling/lag features
```

## Contract

See [DAL_CONTRACT.md](DAL_CONTRACT.md) for grain definitions, column specifications, aggregation rules, and validation invariants.
