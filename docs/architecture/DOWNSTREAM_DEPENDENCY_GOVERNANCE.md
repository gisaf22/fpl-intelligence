# Downstream Dependency Governance

**Updated:** 2026-05-21 — `core.*` and `registry.*` import paths retired following architecture
migration (Decision 007/008). Replaced with `signals.lifecycle.*` and `studies.kernels.*`.

## Canonical data sources

| Source | Module | What it provides |
|--------|--------|-----------------|
| **Curated spine** | `dal.curated.player_gameweek_spine` | `(player_id, gw)` grain — 52 columns of historical performance, fixture context, and market data. Canonical historical truth. |
| **State features** | `dal.state.player_gameweek_state` | Spine + 30 derived columns: rolling windows (roll3/roll5), `minutes_trend`, `fixture_context`. Canonical analytical feature source. |
| **Prepared dataset** | `dal.prepared.analytical_dataset` | State output filtered to a cutoff GW, with string `position` column. Entry point for EDA, stability, and redundancy analysis. |

## Allowed downstream dependencies

Downstream modules (signals/, studies/, intelligence/) may import:

```python
# Convenience helpers (canonical entry points)
from dal.access import get_curated_spine, get_state_features
from dal import get_curated_spine, get_state_features

# Direct spine/state constructors
from dal.curated.player_gameweek_spine import build_player_gameweek_spine
from dal.state.player_gameweek_state import build_player_gameweek_state

# Prepared dataset (EDA / modeling)
from dal.prepared.analytical_dataset import build_prepared_dataset, GOVERNED_SIGNAL_COLUMNS

# DB path
from dal.config import DB_PATH

# Signal governance — lifecycle enforcement, promotion, schema validation
# (migrated from core.governance.* per Decision 007)
from signals.lifecycle import lifecycle, loader, promotion, schema, semantics, validation

# Statistical kernels — domain-agnostic utilities
# (migrated from core.signals.*, core.relationships.*, core.target.* per Decision 007)
from studies.kernels.*
```

## Forbidden patterns

| Pattern | Why forbidden |
|---------|--------------|
| `from dal.staging import ...` | Staging is a DAL-internal layer. Downstream access to raw staged tables bypasses grain validation, BGW/DGW semantics, and column contracts. |
| `from dal.intermediate import ...` | Intermediate is a DAL-internal layer. Downstream access rebuilds joins that the spine has already resolved. |
| `import sqlite3` / `pd.read_sql(...)` outside DAL | Direct DB queries bypass all DAL contracts. Column names, types, and GW semantics are not guaranteed. |
| `from pipeline.config import ...` | `pipeline.*` is a retired namespace. Use `dal.config` instead. |
| `from core.*` | `core/` has been deleted. Use `signals.lifecycle.*` for governance; `studies.kernels.*` for statistical utilities. |
| `from registry.*` | `registry/` has been deleted. Registry build pipeline now lives in `signals/registry/`. |
| Reimplementing rolling windows outside STATE | The lag-1 convention, BGW handling, and warmup semantics are encoded in `build_player_gameweek_state`. Duplicating these creates semantic drift. |
| Reconstructing `(player_id, gw)` grain from joins | The curated spine already performs fixture → GW aggregation with validated DGW/BGW semantics. |

## Why spine and state are the single semantic truth source

**Curated spine** encodes decisions that are non-trivial to reproduce:
- Fixture → gameweek aggregation with correct DGW summation rules
- BGW scaffold rows for players without fixtures (preserving temporal continuity)
- Column contracts enforced at construction time
- Validated grain uniqueness at `(player_id, gw)`

**State features** encode analytical conventions that must not drift:
- Lag-1 shift before rolling windows — GW N features use only GWs 1..N−1 (no look-ahead)
- `minutes_trend` uses a specific 3-vs-prior-3 comparison with 30-minute thresholds
- `fixture_context` (BGW/SGW/DGW) is derived from the spine's `fixture_count`, not recomputed

Any module that reconstructs these independently will eventually diverge from the canonical definition, silently producing different results for the same player-gameweek.

## Enforcement

Static checks are in [tests/test_downstream_governance.py](../../tests/test_downstream_governance.py):

| Check | What it catches |
|-------|----------------|
| G-1 | `pipeline.*` imports in .py files and notebooks |
| G-2 | `sqlite3` / `pd.read_sql` outside DAL |
| G-3 | `dal.staging` / `dal.intermediate` imports outside DAL and tests |
| G-4 | Smoke test that `dal.access` and `dal.prepared` are importable |
