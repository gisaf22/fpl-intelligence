# FPL Intelligence — Execution Guide

**Scope:** How to run the system end-to-end. Current architecture only.

---

## Prerequisites

- `FPL_DB_PATH` set to a valid `fpl.db` path (managed by fpl-ingest)
- Python environment active (`uv sync` or `.venv`)

---

## 3-Command Sequence

```bash
# Step 1: Build analytical dataset (requires live DB)
python -m dal.prepared.analytical_dataset \
  --gw 36 --output-path outputs/prepared_gw36.csv

# Step 2: Build governed registry artifact
python -m signals.registry.runner \
  --gw 36 \
  --source-registry-path studies/eda/findings/eda_03_joint_registry.csv \
  --output-dir outputs/registry/gw36

# Step 3: Generate weekly signal intelligence outputs
python -m intelligence.reporting.runner \
  --gw 36 \
  --registry-path outputs/registry/gw36/registry.csv
```

Replace `36` with the target gameweek. After S7 (Makefile targets) these are also available as `make prepare GW=36`, `make build-registry GW=36`, `make weekly GW=36`.

---

## Layer Ownership

| Layer | Directory | Owns |
|---|---|---|
| DAL | `dal/` | Data loading, staging, curated spine, state features, prepared datasets |
| Signal governance | `signals/` | Lifecycle enforcement, registry build pipeline, evaluation framework |
| Analytical methodology | `studies/` | EDA notebooks, signal kernels, experiment scaffolds, lens studies |
| Operational intelligence | `intelligence/` | Player scoring, weekly reporting |

**Dependency direction:** `intelligence/` → `signals/` → `studies/` → `dal/`  
No layer imports from a layer above it. SQL belongs in `dal/` only.

---

## Entry Points

| Operation | Module | Notes |
|---|---|---|
| DAL validation | `examples/quickstart.py` | DB-free structural check + live-DB spine test |
| Prepared dataset | `dal.prepared.analytical_dataset` | Requires DB; output consumed by registry builder |
| Registry build | `signals.registry.runner` | Source: `studies/eda/findings/eda_03_joint_registry.csv` |
| Player scoring | `intelligence.scoring.runner` | Requires registry artifact + DB |
| Weekly report | `intelligence.reporting.runner` | Requires registry artifact only |

---

## Lifecycle Gate

`signals/lifecycle/lifecycle.py:assert_operational_safe()` enforces that operational runners
consume registry artifacts from `outputs/registry/`, not directly from `studies/eda/`.
The bootstrap artifact (`outputs/registry/gw36/`) must exist before scoring or reporting runs.

---

## Non-Goals

- ML model training or feature engineering
- Captaincy or transfer scoring
- Player-level ranking systems
- Dashboards or UI components
- Predictive backtesting
