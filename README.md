# FPL Intelligence

## Pipeline

| Stage | Directory | What it does |
|---|---|---|
| `dal` | `dal/` | Data access layer — canonical `(player_id, gw)` spine and features |
| `studies` | `studies/` | Analytical methodology — EDA, lenses, statistical kernels, experiments |
| `signals` | `signals/` | Signal lifecycle governance, registry build pipeline, evaluation framework |
| `intelligence` | `intelligence/` | Player scoring and weekly signal intelligence reporting |

## Quickstart

Verify the DAL works end to end against a real database in under two minutes:

```bash
FPL_DB_PATH=/path/to/fpl.db python examples/quickstart.py
# or pass the path directly
python examples/quickstart.py /path/to/fpl.db
```

The script calls `get_curated_spine` and `get_state_features`, prints shape and column
information, and exits with a non-zero code on any failure. See [examples/quickstart.py](examples/quickstart.py) for details.

## Layer Boundaries

- SQL belongs only in the DAL — no layer queries the source database directly.
- EDA notebooks must remain purely observational.
- No signal enters the registry without a confirmed lens status.
- No signal enters synthesis without a confirmed registry entry.

## Architecture

- [docs/system-purpose.md](docs/system-purpose.md) — mission, architectural intent, non-goals
- [docs/architecture/operational-flow.md](docs/architecture/operational-flow.md) — 3-command execution sequence and operational entry points
- [docs/research-lifecycle.md](docs/research-lifecycle.md) — signal lifecycle states and promotion criteria
- [docs/registry-governance.md](docs/registry-governance.md) — exploratory vs operational registries, runtime enforcement
- [docs/architecture/DAL_CONTRACT.md](docs/architecture/DAL_CONTRACT.md) — authoritative DAL behavioral contract
- [docs/architecture/layer-boundaries.md](docs/architecture/layer-boundaries.md) — component ownership and dependency rules
- [docs/architecture/](docs/architecture/) — full architecture reference
