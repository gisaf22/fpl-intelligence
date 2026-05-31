# fpl-intelligence — Project Context

---

## 1. Project purpose

fpl-intelligence is an analytical system for Fantasy Premier League built on top of
a SQLite source database populated by fpl-ingest. The 2025-26 season was the development
season: no live decisions were made using system outputs. The goal was to characterise
which signals associate reliably with FPL returns, test whether those signals combine
usefully, and validate the methodology before a predictive layer is added in 2026-27.

The system question, copied exactly from `signals/governance/EVAL_DESIGN.md` Section 2:

> What information, available before a gameweek, reliably associates with FPL returns
> in decision-relevant contexts — and how should that information be characterised to
> support transfer, captaincy, and chip decisions?

---

## 2. Methodology map

```
System question
└── System EDA — gates all lens studies
    └── Signal lifecycle
        ├── Lenses — signal characterisation
        │   ├── LENS-FORM
        │   ├── LENS-MARKET
        │   ├── LENS-FIXTURE-GW
        │   ├── LENS-FIXTURE-RUN (future)
        │   └── LENS-AVAIL
        ├── Signal registry — lifecycle tracking
        ├── SYNTH-01 — signal synthesis
        └── Experiments
            ├── EXP-FH-STACK
            └── EXP-FH-PREDICTOR
└── Evaluation — signals/governance/EVAL_DESIGN.md
```

System EDA runs once against the full dataset. The governed registry
(`studies/eda/findings/eda_03_joint_registry.csv`) is its authoritative output. No lens study
begins until the registry has real promotion_class values — this gate is now met.

Lenses characterise individual signal groups against the system question using Spearman rank
correlation with bootstrap confidence intervals. Each lens produces candidate signal statuses
for the registry. See `docs/decisions/001-spearman-as-evaluation-metric.md` for why Spearman.

The signal registry is the governance layer: every signal must be registered before entering
a lens study, and must have a confirmed lens status before entering synthesis.

SYNTH-01 tests whether confirmed signals combine to outperform individual signals and whether
form signals are conditioned by fixture difficulty. Composition uses additive weighted scoring;
see `docs/decisions/002-additive-weighted-scoring.md` for why.

Experiments (EXP-FH-STACK, EXP-FH-PREDICTOR) are backtesting simulations that test signal
discrimination in decision-relevant contexts — captaincy and transfer selection.

The evaluation framework (`signals/governance/EVAL_DESIGN.md`) defines success criteria and
failure conditions before results are known. It cannot be revised retrospectively.

---

## 3. Repository structure

```
fpl-intelligence/
├── dal/             — data access layer — staging, intermediate, fct, feat, mart
├── docs/            — architectural and governance documents
│   ├── architecture/   — system model, layer boundaries, operational flow, etc.
│   ├── decisions/      — ADRs: why Spearman, why additive weighting
│   ├── governance/     — threshold-registry, evaluation-gate-criteria, eng-issues-2026
│   └── studies/        — study designs and published results
├── domain/          — FPL scoring rules as typed constants (VERIFIED/UNVERIFIED)
├── examples/        — quickstart script for DAL end-to-end validation
├── intelligence/    — operational intelligence layer
│   ├── reporting/   — weekly report runner and output generators
│   └── scoring/     — player scoring from governed registry manifest
├── outputs/         — runtime artifacts (scorer HTML, registry CSVs, weekly reports)
├── population/      — named population filters: filter_performance, filter_participation
├── signals/         — signal governance layer
│   ├── characterisation/ — registry build pipeline, signal traceability, SIGNAL_REGISTRY.md
│   └── governance/       — EVAL_DESIGN.md, lifecycle, evaluation metadata, weight_registry.yaml
├── studies/         — analytical methodology layer
│   ├── eda/         — system EDA (complete, closed)
│   ├── experiments/ — experiment scaffolds
│   ├── kernels/     — reusable statistical kernels
│   ├── lenses/      — lens studies (FORM, MARKET, FIXTURE-GW, AVAIL — all complete)
│   ├── operational/ — phase9_backtest.py
│   └── synthesis/   — synth01_study.py
└── tests/           — test suite (928 tests)
```

Source database: `~/.fpl/fpl.db` (managed by fpl-ingest, path configurable via `FPL_DB_PATH` env var).

---

## 4. Document hierarchy

| Document | Location | Purpose | Gates |
|---|---|---|---|
| EVAL_DESIGN.md | `signals/governance/EVAL_DESIGN.md` | Locked success criteria and failure conditions for 2025-26 methodology | All study findings must connect to a question defined here |
| SIGNAL_REGISTRY.md | `signals/characterisation/SIGNAL_REGISTRY.md` | Governance and truth layer for all signals — lifecycle status, lens outcomes, synthesis eligibility | No signal enters synthesis without a confirmed entry |
| EDA_08_DESIGN.md | `studies/eda/EDA_08_DESIGN.md` | Defines the seven system EDA layers and their gate decisions | All lens studies — no lens runs before EDA is complete |
| CONTEXT.md | `CONTEXT.md` | Current project state, structure, and rules for new sessions | New session orientation |
| DOWNSTREAM_DEPENDENCY_GOVERNANCE.md | `docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md` | Allowed and forbidden downstream import patterns; enforced by tests/test_downstream_governance.py | Any new module that accesses signals or DAL data |
| LENS_DESIGN.md (LENS-FORM) | `studies/lenses/form/LENS_DESIGN.md` | Study design for rolling output and attacking threat signals | LENS-FORM execution |
| LENS_DESIGN.md (LENS-MARKET) | `studies/lenses/market/LENS_DESIGN.md` | Study design for transfer and ownership signals | LENS-MARKET execution |
| LENS_DESIGN.md (LENS-FIXTURE-GW) | `studies/lenses/fixture_gw/LENS_DESIGN.md` | Study design for single-gameweek fixture difficulty signals | LENS-FIXTURE-GW execution |
| LENS_DESIGN.md (LENS-AVAIL) | `studies/lenses/avail/LENS_DESIGN.md` | Study design for minutes consistency and trend signals | LENS-AVAIL execution |

---

## 5. Current state

| Layer | Status | Notes |
|---|---|---|
| DAL layer | COMPLETE | fct/feat/mart restructure complete; Pandera FEAT_SCHEMA; pipeline run/load separation; 928 tests |
| domain/ | COMPLETE | FPL scoring rules as typed constants with VERIFIED/UNVERIFIED annotations |
| population/ | COMPLETE | Named population filters: filter_performance (≥60 min), filter_participation (≥1 min) |
| System EDA | COMPLETE | Governed registry is the authoritative output. Gate decisions in `studies/eda/findings/EDA_FINDINGS.md` |
| LENS-FORM | COMPLETE | Approved: xgi_roll3 (DEF), xgi_roll5 (DEF, MID). Records in `signals/governance/evaluation_metadata.yaml` |
| LENS-MARKET | COMPLETE | Approved: transfers_in (DEF, MID), purchase_price (DEF, FWD†), ownership_count (MID). Records in `evaluation_metadata.yaml` |
| LENS-FIXTURE-GW | COMPLETE | fdr_avg excluded (non-monotonic); reserved as binary moderator. Records in `evaluation_metadata.yaml` |
| LENS-AVAIL | COMPLETE | Approved: minutes_roll8 (DEF), minutes_roll3/roll8 (MID). Records in `evaluation_metadata.yaml` |
| LENS-GK | PENDING | No design yet. No governed GK signals. All GK scoring PROVISIONAL-EDITORIAL. Deferred to 2026/27 |
| LENS-FIXTURE-RUN | PENDING | Future lens. Deferred to 2026/27 |
| Signal registry | COMPLETE | SIGNAL_REGISTRY.md v2.0. evaluation_metadata.yaml v3.0 with lifecycle states and SYNTH-01 decisions |
| SYNTH-01 | COMPLETE | Partial rho weights set; decisions in `signals/governance/synth01_decisions.yaml`. 5/7 groups stable or improved on holdout GW 34–38 |
| Platform evaluation | COMPLETE | Changes 1–8 applied; Changes 1–2 implemented (domain/, population/); Change 3 design locked at `docs/studies/popthresh-01-design.md` |
| EXP-FH-STACK | DEFERRED | Blocked pending FDR stratification (2026/27) |
| EXP-FH-PREDICTOR | DEFERRED | Blocked pending FDR stratification (2026/27) |

† FWD purchase_price reversed on holdout GW 34–38 (rho = −0.095). Phase-conditional restriction required — see ENG-02 in `docs/governance/eng-issues-2026.md`.

---

## 6. What is next

**2026/27 season preparation**

The 9-phase Operational Convergence Plan and platform evaluation Changes 1–8 are complete. The active engineering issue backlog is `docs/governance/eng-issues-2026.md`.

Priority items:
- **ENG-01 (High):** Add CI/CD — no automated test runner exists
- **ENG-02 (High):** Restrict FWD purchase_price to GW ≤ 30 (end-of-season signal reversal)
- **ENG-04 (Medium):** Six unvalidated thresholds in intelligence/ — EVALUATION-DEFERRED
- **ENG-06 (Medium):** LENS-GK — no governed GK signals
- **ENG-07 (Medium):** FDR stratification in composite scorer (Phase 9 MATERIAL finding)
- **POPTHRESH-01:** Execute `studies/experiments/population_threshold_study.py` to validate 60-min boundary

See `outputs/operational-baseline.md` for Phase 9 validation results and full recommendation list.

---

## 7. DAL architecture summary

The DAL is a five-layer pipeline with strict one-way dependencies. All layers are complete
and contract-validated.

**Layer ordering (low → high):** staging → intermediate → fct → feat → mart

**dal/staging/** handles transformation: column renaming, type casting, null standardisation
against schema YAML files in `dal/staging/contracts/`. Six entity schemas (element_types,
teams, events, fixtures, players, player_histories). Schema-driven — `load_schema()` reads YAML,
`stage()` applies transforms. Filenames: `stg_*.py`.

**dal/intermediate/** handles enrichment: joining staging outputs to produce wider fixture-grain
records. Grain does not change. `int_player_fixture.py` produces the enriched fixture-grain table.
`int_fixture_context.py` classifies fixtures. `int_opponent_context.py` computes rolling opponent
defensive metrics. `validate_join_safety` is called after every join to prevent silent row loss.
Filenames: `int_*.py`.

**dal/fct/** changes grain from fixture-grain to gameweek-grain. `fct_player_gameweek.py`
produces the canonical `(player_id, gw)` base table (52 columns). Aggregates fixture data to GW
summaries before spine construction, cross-joins player universe × GW calendar, left-joins
aggregated data so unmatched rows become explicit BGW rows. Full validation suite runs on every
build. Filenames: `fct_*.py`.

**dal/feat/** adds derived columns (rolling windows, trend, fixture_context) to the fct spine
without changing grain or row count. Lag-1 convention throughout. `feat_schema.py` declares the
`FEAT_SCHEMA` Pandera contract and `FEATURE_REGISTRY` linking every column to its gate decision.
Filenames: `feat_*.py`.

**dal/mart/** wraps spine+feat with cutoff filtering and position string mapping. Entry
point for EDA, lenses, and modeling. `GOVERNED_SIGNAL_COLUMNS` is the canonical signal list.
Filenames: `mart_*.py`.

**dal/validation/** is a cross-cutting concern with 7 standalone modules split across two locations:
`dal/validation/` holds grain.py and joins.py; `dal/fct/validation/` holds completeness.py,
contracts.py, invariants.py, nulls.py, semantics.py.
`DALContractViolation` is raised for contract breaches. Validation modules must not import
from dal.fct/ — they accept layer-specific constants as parameters (V-3 contract).
`ErrorCode` class in `dal/exceptions.py` documents all valid error code strings.

**dal/pipeline.py** orchestrates the full build in layer order and writes a manifest JSON with
per-layer status, row counts, timing, and fingerprints. Entry point: `python -m dal.pipeline run`.

**Canonical entry points for downstream consumers:**
- `dal.pipeline.run(db_path, force, data_cutoff_gw)` — build all layers, write mart.parquet + manifest
- `dal.pipeline.load(db_path)` → `MartResult` — read persisted mart parquet (call run() first)
- `MartResult` carries: mart DataFrame, signals tuple, gw_range, data_cutoff_gw

Code-enforced contracts live in `dal/fct/fct_contracts.py` and `dal/feat/feat_contracts.py`.

---

## 8. Naming conventions

| Type | Convention | Examples |
|---|---|---|
| Lenses | LENS-[NAME] in uppercase | LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW, LENS-FIXTURE-RUN, LENS-AVAIL, LENS-GK |
| Signal IDs | [LENS]-[NNN] assigned sequentially | FORM-001, MARKET-001, FIXTURE-001, AVAIL-001 |
| Experiments | EXP-[NAME] in uppercase | EXP-FH-STACK, EXP-FH-PREDICTOR |
| Engineering issues | ENG-[NN] | ENG-01 (CI), ENG-02 (FWD purchase_price), etc. |
| DAL layer names | staging, intermediate, fct, feat, mart | dal/staging/, dal/intermediate/, dal/fct/, dal/feat/, dal/mart/ |
| DAL filename convention | stg\_, int\_, fct\_, feat\_, mart\_ | stg_entities, int_player_fixture, fct_player_gameweek, feat_player_gameweek, mart_analytical |

---

## 9. Rules — never break these

Design before code — always design in Claude UI first, no code until design is agreed

Every design document must include a capabilities table (Determinism, Observability, Contracts,
Lineage, Idempotency, Testability, Operability, Evolvability) before the changes section —
see `docs/architecture/platform-capabilities.md` for definitions and status symbols

No SQL outside `dal/`

No study runs without a LENS_DESIGN.md agreed in Claude UI first

No signals enter the signal registry without a confirmed lens status

No signals enter SYNTH-01 without a confirmed registry entry

DAL contracts are code-enforced — `dal/fct/fct_contracts.py`, `dal/feat/feat_contracts.py`, `dal/validation/`

The governed registry must have real promotion_class values before any lens study design begins — this gate is now met

---

## 10. How to start a new session

1. Read CONTEXT.md (this document)
2. Read `dal/pipeline.py` docstring for DAL entry points; read `dal/fct/fct_contracts.py` and `dal/feat/feat_contracts.py` for contract enforcement if any DAL work is planned
3. Read `docs/governance/eng-issues-2026.md` for active engineering issues
4. Read the relevant design document for the current task
5. Do not write code until the design is agreed in Claude UI
