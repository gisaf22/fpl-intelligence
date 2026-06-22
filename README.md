# FPL Intelligence

## Pipeline

| Stage | Directory | What it does |
|---|---|---|
| `dal` | `dal/` | Data access layer — canonical `(player_id, gw)` spine and features |
| `domain` | `domain/` | Shared leaf — FPL scoring rules as typed constants + registry contracts/loaders |
| `research` | `research/` | Analytical methodology — foundation EDA, family lenses, statistical kernels, findings |
| `model` | `model/` | Governance (registry build, semantics, evaluation metadata) + composition weights |
| `serve` | `serve/` | Player scoring and weekly signal intelligence reporting |

Layer order (low → high): `dal → research → model → serve`, with `domain` as the shared leaf.

## Quickstart

Verify the DAL works end to end against a real database in under two minutes:

```bash
FPL_DB_PATH=/path/to/fpl.db python examples/quickstart.py
# or pass the path directly
python examples/quickstart.py /path/to/fpl.db
```

The script calls `dal.pipeline.load()`, prints shape and column
information, and exits with a non-zero code on any failure. See [examples/quickstart.py](examples/quickstart.py) for details.

## Layer Boundaries

- SQL belongs only in the DAL — no layer queries the source database directly.
- EDA notebooks must remain purely observational.
- No signal enters the registry without a confirmed lens status.
- No signal enters synthesis without a confirmed registry entry.

## Architecture

- [docs/system-purpose.md](docs/system-purpose.md) — mission, architectural intent, non-goals
- [docs/architecture/runtime-execution.md](docs/architecture/runtime-execution.md) — execution sequence and operational entry points
- [docs/signal-promotion-states.md](docs/signal-promotion-states.md) — signal lifecycle states and promotion criteria
- [docs/registry-governance.md](docs/registry-governance.md) — exploratory vs operational registries, runtime enforcement
- [dal/README.md](dal/README.md) — DAL design rationale (code contracts in `dal/fct/fct_contracts.py`, `dal/feat/feat_contracts.py`)
- [docs/architecture/layer-boundaries.md](docs/architecture/layer-boundaries.md) — component ownership and dependency rules
- [docs/architecture/](docs/architecture/) — full architecture reference
