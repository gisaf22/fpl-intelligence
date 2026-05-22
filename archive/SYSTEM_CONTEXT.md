# System Context

**What this is:** A high-level map of the fpl-intelligence system — what it's for, how it's structured, and where the DAL fits within it.

---

## Project purpose

fpl-intelligence is an analytical system for Fantasy Premier League, built on a SQLite source database populated by fpl-ingest. The 2025–26 season is the development season: no live decisions are made from system outputs. The goal is to characterise which signals reliably associate with FPL returns, test whether those signals combine usefully, and validate the methodology before a predictive layer is added in 2026–27.

The central question the system is designed to answer:

> What information, available before a gameweek, reliably associates with FPL returns in decision-relevant contexts — and how should that information be characterised to support transfer, captaincy, and chip decisions?

---

## System layers

```
Source database (fpl.db — populated by fpl-ingest)
    ↓
DAL — data access layer (dal/)
    Staging → Intermediate → Curated → State
    ↓
Signals layer (signals/)
    Signal characterisation (lenses)
    Signal synthesis (SYNTH-01)
    Backtesting (experiments)
    ↓
Registry — governed signal registry builder (registry/)
    ↓
Evaluation (signals/evaluation/EVAL_DESIGN.md)
```

### DAL

Transforms raw FPL API data into a clean, validated, deterministic gameweek-grain spine. Every downstream layer consumes the DAL output as its only data source — no layer queries the source database directly.

Four sub-layers, each owning one concern:

| Layer | Location | Concern |
|---|---|---|
| Staging | `dal/staging/` | Column rename, type cast, null standardisation — no joins, no aggregation |
| Intermediate | `dal/intermediate/` | Join staging outputs into enriched fixture-grain records |
| Curated | `dal/curated/` | Aggregate fixture-grain to gameweek-grain; complete the spine with BGW rows |
| State | `dal/state/` | Add derived features (rolling windows, lags, trends) to the gameweek-grain spine |

Validation is a cross-cutting concern (`dal/validation/`) — standalone modules called by any layer, never embedded in transformation code.

The DAL contract is in [docs/architecture/DAL_CONTRACT.md](DAL_CONTRACT.md). Any DAL code change must be consistent with that document.

### Signals layer

Characterises signals against the system question using a defined methodology:

- **System EDA** — one-time study of the full dataset; produces the governed signal registry
- **Lenses** — per-signal-group studies (LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW, LENS-AVAIL) using Spearman rank correlation with bootstrap confidence intervals
- **Signal registry** — lifecycle governance; signals must be registered before a lens study and confirmed before synthesis
- **SYNTH-01** — tests whether confirmed signals combine to outperform individuals
- **Experiments** — backtesting simulations for captaincy and transfer selection decisions

### Registry

`registry/` is the governed signal registry builder — assembles promoted signals from the signals layer into the output registry.

### Evaluation framework

`signals/evaluation/EVAL_DESIGN.md` defines success criteria and failure conditions before results are known. This document cannot be revised retrospectively.

---

## Document hierarchy

| Document | Location | Purpose |
|---|---|---|
| DAL_CONTRACT.md | `docs/architecture/DAL_CONTRACT.md` | Authoritative behavioral contract for the DAL — grain, aggregation rules, validation module specs, invariants |
| SYSTEM_CONTEXT.md | `docs/architecture/SYSTEM_CONTEXT.md` | This document — system map and layer boundaries |
| Stabilization overview | `docs/stabilization/OVERVIEW.md` | What DAL stability means and how the stabilization was structured |
| EVAL_DESIGN.md | `signals/evaluation/EVAL_DESIGN.md` | Success criteria and failure conditions for the 2025–26 methodology |
| SIGNAL_REGISTRY.md | `signals/registry/SIGNAL_REGISTRY.md` | Lifecycle status for every signal; gates lens and synthesis work |
| EDA_DESIGN.md | `signals/eda/EDA_DESIGN.md` | System EDA layer definitions and gate decisions |
| CONTEXT.md | `CONTEXT.md` | Project state, rules, and session orientation |

---

## Key boundaries

**SQL only in DAL.** No SQL outside `dal/`. The research layer reads DAL output DataFrames only.

**Single canonical base table.** The curated layer output (`player_gw_base`) is the only permitted source for all downstream analytics and the state layer. Analysts pulling from the intermediate layer or using fixture-grain data to compute GW-level targets are in violation of the contract.

**Design before code.** No code is written until a design is agreed in Claude UI. No lens study runs without a `LENS_DESIGN.md`. No signals enter the registry without a confirmed lens status.

---

## Current DAL status

All eight DAL refactor phases complete as of May 2026. 331 tests passing.

| Phase | Concern | Status |
|---|---|---|
| 1 | Validation modules | Complete |
| 2 | Integrity test suite | Complete |
| 3 | BGW spine completion | Complete |
| 4 | DGW aggregation | Complete |
| 4b | Defensive/FPL metrics column aggregation | Complete |
| 5 | Null semantics | Complete |
| 6 | Join safety | Complete |
| 7 | Concern separation | Complete |
| 8 | Column contract | Complete |

For the stabilization history (risks identified, waves executed, decisions made), see [`docs/stabilization/`](../stabilization/).
