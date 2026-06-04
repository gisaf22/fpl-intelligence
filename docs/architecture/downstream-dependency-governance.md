# Downstream Dependency Governance

**Updated:** 2026-05-21 — `core.*` and `registry.*` import paths retired following architecture
migration (Decision 007/008). Replaced with `signals.governance.*` and `research.kernels.*`.
The `signals.lifecycle.*` / `signals.evaluation.*` / `signals.registry.*` packages were later
merged into `signals.governance.*` (lifecycle, promotion, schema, validation) and
`signals.characterisation.*` (registry build) in the signals package restructure.

## Canonical data sources

| Source | Module | What it provides |
|--------|--------|-----------------|
| **Mart** | `dal.pipeline.load()` | Full analytical dataset at `(player_id, gw)` grain — spine + governed feature columns, filtered to cutoff GW. Returns a `MartResult`. |
| **MartResult** | `dal.mart.mart_access.MartResult` | Typed result: `mart` DataFrame, `signals` tuple, `gw_range`, `data_cutoff_gw`. |

## Allowed downstream dependencies

Downstream modules (signals/, research/, model/, intelligence/) may import:

```python
# Canonical entry point — always use this to load data
from dal.pipeline import load as load_mart   # returns MartResult
from dal.pipeline import run                 # build mart.parquet + manifest (ops/CI only)
from dal.mart.mart_access import MartResult  # type annotation

# DB path
from dal.config import DB_PATH

# Signal governance — lifecycle enforcement, promotion, schema validation
from signals.governance import lifecycle, registry_loader, promotion, schema, validation, governance

# Statistical kernels — domain-agnostic utilities
from research.kernels.*
```

## Forbidden patterns

| Pattern | Why forbidden |
|---------|--------------|
| `from dal.staging import ...` | Staging is a DAL-internal layer. Downstream access to raw staged tables bypasses grain validation, BGW/DGW semantics, and column contracts. |
| `from dal.intermediate import ...` | Intermediate is a DAL-internal layer. Downstream access rebuilds joins that the spine has already resolved. |
| `import sqlite3` / `pd.read_sql(...)` outside DAL | Direct DB queries bypass all DAL contracts. Column names, types, and GW semantics are not guaranteed. |
| `from pipeline.config import ...` | `pipeline.*` is a retired namespace. Use `dal.config` instead. |
| `from core.*` | `core/` has been deleted. Use `signals.governance.*` for governance; `research.kernels.*` for statistical utilities. |
| `from registry.*` | `registry/` has been deleted. Registry build pipeline now lives in `signals/characterisation/`. |
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
| G-4 | Smoke test that `dal.pipeline.run` and `dal.pipeline.load` are importable |
