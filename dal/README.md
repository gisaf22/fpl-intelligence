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

## Entities & grain

The DAL is built from six source entities (staged in `dal/staging/stg_entities.py`) and resolves them
to one canonical analytical entity: the **player-gameweek**.

| Entity | Role | Native grain |
|---|---|---|
| `players` | The FPL player — the analytical subject | player |
| `element_types` | Position definitions (GK/DEF/MID/FWD) | position |
| `teams` | Premier League clubs | team |
| `events` | Gameweeks (GW 1–38) | gameweek |
| `fixtures` | Individual matches | fixture |
| `player_histories` | Per-player per-fixture performance records | player × fixture |

**Relationships:** a player belongs to one team and one element_type (position); a fixture belongs to
one event (gameweek) and two teams; a player_history row ties a player to a fixture. A double gameweek
(DGW) gives a player two fixtures in one event; a blank gameweek (BGW) gives zero (an explicit BGW row).

**Grain progression** (one-way, code-enforced):

```
player × fixture        →        player × gameweek
(player_histories)               (the canonical spine)
```

The canonical analytical grain is `(player_id, gw)` — unique and validated before any downstream layer
consumes it. Grain contracts are declared and enforced in [`dal/validation/grain.py`](validation/grain.py)
(`GRAIN_CONTRACTS`: `player_fixture_base`, `player_gameweek_spine`, `player_gameweek_state`,
`analytical_mart`).

**Not modeled as an entity:** the FPL *manager* population. Manager behaviour enters the system only as
population-aggregate Market signals (`transfers_in`, `transfers_out`, `ownership_count`) attached to the
player-gameweek row — there is no manager, squad, or league entity in the DAL. This is deliberate for the
single-season analytical scope.

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
