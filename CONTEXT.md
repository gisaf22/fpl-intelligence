# fpl-intelligence — Project Context

---

## 1. Project purpose

fpl-intelligence is an analytical system for Fantasy Premier League built on top of
a SQLite source database populated by fpl-ingest. The 2025-26 season is the development
season: no live decisions are made using system outputs. The goal is to characterise
which signals associate reliably with FPL returns, test whether those signals combine
usefully, and validate the methodology before a predictive layer is added in 2026-27.

The system question, copied exactly from EVAL_DESIGN.md Section 2:

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
└── Evaluation — EVAL_DESIGN.md
```

System EDA runs once against the full dataset. The governed registry
(studies/eda/findings/eda_03_joint_registry.csv) is its authoritative output. No lens study
begins until the registry has real promotion_class values — this gate is now met.

Lenses characterise individual signal groups against the system question using Spearman rank
correlation with bootstrap confidence intervals. Each lens produces candidate signal statuses
for the registry.

The signal registry is the governance layer: every signal must be registered before entering
a lens study, and must have a confirmed lens status before entering synthesis.

SYNTH-01 tests whether confirmed signals combine to outperform individual signals and whether
form signals are conditioned by fixture difficulty.

Experiments (EXP-FH-STACK, EXP-FH-PREDICTOR) are backtesting simulations that test signal
discrimination in decision-relevant contexts — captaincy and transfer selection.

The evaluation framework (EVAL_DESIGN.md) defines success criteria and failure conditions
before results are known. It cannot be revised retrospectively.

---

## 3. Repository structure

```
fpl-intelligence/
├── archive/         — retired code (pipeline_legacy/) and planning documents
├── dal/             — data access layer — staging, intermediate, curated, state, validation, prepared
├── docs/            — architectural and decision documents
│   ├── architecture/   — DAL_CONTRACT.md, DOWNSTREAM_DEPENDENCY_GOVERNANCE.md, SYSTEM_CONTEXT.md
│   ├── decisions/      — per-signal and design decision records
│   └── stabilization/  — stabilization wave history and Phase 11 plan
├── examples/        — quickstart script for DAL end-to-end validation
├── intelligence/    — operational intelligence layer
│   ├── reporting/   — weekly registry snapshot runner and output generators
│   └── scoring/     — player scoring from governed registry manifest
├── outputs/         — runtime artifacts (scorer HTML, registry CSVs, weekly reports)
├── signals/         — signal governance layer
│   ├── evaluation/  — EVAL_DESIGN.md (locked evaluation framework)
│   ├── lifecycle/   — lifecycle enforcement, registry loading, promotion schema
│   └── registry/    — registry build pipeline (runner, assembly, config, inputs)
├── studies/         — analytical methodology layer
│   ├── eda/         — system EDA notebooks and findings (complete, closed)
│   ├── experiments/ — experiment scaffolds (blocked on synthesis)
│   ├── kernels/     — reusable statistical kernels
│   └── lenses/      — lens study scaffolds (pre-investigational)
└── tests/           — test suite (739 tests as of Phase 11)
```

Source database: `~/.fpl/fpl.db` (managed by fpl-ingest, path configurable via `FPL_DB_PATH` env var).

---

## 4. Document hierarchy

| Document | Location | Purpose | Gates |
|---|---|---|---|
| DAL_CONTRACT.md | docs/architecture/DAL_CONTRACT.md | Authoritative contract for all DAL layers — grain, aggregation rules, validation modules, invariants | Any DAL code change; deviations require updating this document first |
| EVAL_DESIGN.md | signals/evaluation/EVAL_DESIGN.md | Defines success criteria and failure conditions for the 2025-26 methodology before results are known | All study findings must connect to a question defined here |
| SIGNAL_REGISTRY.md | signals/registry/SIGNAL_REGISTRY.md | Governance and truth layer for all signals — lifecycle status, lens outcomes, synthesis eligibility | No signal enters synthesis without a confirmed entry; no signal is referenced in a study without being registered |
| EDA_DESIGN.md | signals/eda/EDA_DESIGN.md | Defines the seven system EDA layers and their gate decisions | All lens studies — no lens runs before EDA is complete and findings documented |
| EDA_NOTEBOOKS.md | signals/eda/EDA_NOTEBOOKS.md | Complete brief for each EDA notebook with questionnaire items | Each EDA notebook run — provides the execution specification |
| CONTEXT.md | CONTEXT.md | Current project state, structure, and rules for new sessions | New session orientation |
| DOWNSTREAM_DEPENDENCY_GOVERNANCE.md | docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md | Allowed and forbidden downstream import patterns; enforced by tests/test_downstream_governance.py | Any new signals/registry module that accesses data |
| LENS_DESIGN.md (LENS-FORM) | signals/lenses/form/LENS_DESIGN.md | Study design for rolling output and attacking threat signals | LENS-FORM execution — study cannot run without agreed design; pending rerun under locked methodology |
| LENS_DESIGN.md (LENS-MARKET) | signals/lenses/market/LENS_DESIGN.md | Study design for transfer and ownership signals | LENS-MARKET execution; pending rerun under locked methodology |
| LENS_DESIGN.md (LENS-FIXTURE-GW) | signals/lenses/fixture-gw/LENS_DESIGN.md | Study design for single-gameweek fixture difficulty signals | LENS-FIXTURE-GW execution; pending rerun under locked methodology |
| LENS_DESIGN.md (LENS-AVAIL) | signals/lenses/avail/LENS_DESIGN.md | Study design for minutes consistency and trend signals | LENS-AVAIL execution; pending rerun under locked methodology |

---

## 5. Current state

| Layer | Status | Notes |
|---|---|---|
| DAL layer | COMPLETE | All six stabilization waves complete; 739 tests passing |
| Validation modules | COMPLETE | All 7 modules in dal/validation/; fully decoupled from curated layer (V-3) |
| System EDA | COMPLETE | Governed registry is the authoritative output. Gate decisions in docs/decisions/eda_01_analytical_foundations.md |
| LENS-FORM | PENDING | Old SA results archived; redesign and rerun required under locked methodology |
| LENS-MARKET | PENDING | Old SB results archived; redesign and rerun required under locked methodology |
| LENS-FIXTURE-GW | PENDING | Old SC results archived; redesign and rerun required under locked methodology |
| LENS-AVAIL | PENDING | Old SE results archived; redesign and rerun required under locked methodology |
| LENS-FIXTURE-RUN | PENDING | Future lens; scaffold exists, no design yet |
| Signal registry | READY | SIGNAL_REGISTRY.md is empty (placeholder). Governed signal set is in studies/eda/findings/eda_03_joint_registry.csv — promotion_class values confirmed. |
| SYNTH-01 | BLOCKED ON Signal registry | No synthesis directory; cannot begin until confirmed signals exist in registry |
| EXP-FH-STACK | BLOCKED ON SYNTH-01 | Scaffold exists; no code or findings |
| EXP-FH-PREDICTOR | BLOCKED ON SYNTH-01 | Scaffold exists; no code or findings |
| Evaluation framework | COMPLETE | EVAL_DESIGN.md active and locked; success criteria and failure definitions written |

---

## 6. What is next

**Phase 11 — Operational Usability Stabilization (active)**

Executing the operational maturity stabilization plan. Eleven slices defined in
`docs/stabilization/STABILIZATION_EXECUTION_PLAN.md`.

- **Critical path (S1–S9):** CONTEXT.md truth alignment, ROADMAP correction, governance test hardening, dependency hygiene, integration test marking, conftest fixture, Makefile targets, registry artifact bootstrap, scorer HTML explainability.
- **Polish (S10–S11):** Stale doc archival, `tests/helpers/` rename.

After S9 the system is operationally mature and portfolio-grade. S10–S11 are cosmetic improvements.

---

## 7. DAL architecture summary

The DAL is a five-layer pipeline with strict one-way dependencies. All six stabilization waves
(Wave 1–6) are complete. The DAL produces deterministic, contract-validated output.

**Layer ordering (low → high):** staging → intermediate → curated → state → prepared

**dal/staging/** handles transformation: column renaming, type casting, null standardisation
against schema YAML files in `dal/staging/contracts/`. Six entity schemas (element_types,
teams, events, fixtures, players, player_histories). Schema-driven — `load_schema()` reads YAML,
`stage()` applies transforms. Logs entity row counts and timing after each staging call.

**dal/intermediate/** handles enrichment: joining staging outputs to produce wider fixture-grain
records. Grain does not change. `player_fixture.py` produces the enriched fixture-grain table.
`fixture_context.py` classifies fixtures. `opponent_context.py` computes rolling opponent
defensive metrics. `validate_join_safety` is called after every join to prevent silent row loss.

**dal/curated/** changes grain from fixture-grain to gameweek-grain. `player_gameweek_spine.py`
produces the canonical `(player_id, gw)` base table (52 columns). Aggregates fixture data to GW
summaries before spine construction, cross-joins player universe × GW calendar, left-joins
aggregated data so unmatched rows become explicit BGW rows. Full validation suite runs on every
build: grain, completeness, BGW/DGW correctness, null semantics, join safety, invariants.

**dal/state/** adds derived columns (rolling windows, trend, fixture_context) to the curated
spine without changing grain or row count. Lag-1 convention throughout. `dal/state/STATE_CONTRACT.md`
documents all 30 derived columns. State output has runtime schema guards and grain assertions.

**dal/prepared/** wraps spine+state with cutoff filtering and position string mapping. Entry
point for EDA, lenses, and modeling. `GOVERNED_SIGNAL_COLUMNS` is the canonical signal list.

**dal/validation/** is a cross-cutting concern with 7 standalone modules: grain.py,
completeness.py, semantics.py, joins.py, contracts.py, nulls.py, invariants.py.
`DALContractViolation` is raised for contract breaches. Validation modules must not import
from dal.curated/ — they accept layer-specific constants as parameters (V-3 contract).

**Canonical entry points for downstream consumers:**
- `dal.access.get_curated_spine()` — historical (player_id, gw) spine
- `dal.access.get_state_features(spine)` — spine + 30 derived state columns
- `dal.prepared.analytical_dataset.build_prepared_dataset(spine, cutoff_gw)` — EDA/modeling dataset

See `docs/architecture/DAL_CONTRACT.md` for the full behavioral specification.

---

## 8. Naming conventions

| Type | Convention | Examples |
|---|---|---|
| Lenses | LENS-[NAME] in uppercase | LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW, LENS-FIXTURE-RUN, LENS-AVAIL |
| Signal IDs | [LENS]-[NNN] assigned sequentially | FORM-001, MARKET-001, FIXTURE-001, AVAIL-001, FIXRUN-001 |
| Experiments | EXP-[NAME] in uppercase | EXP-FH-STACK, EXP-FH-PREDICTOR |
| Run logs | [LENS]-[NAME]_YYYYMMDD_HHMMSS.json in signals/runs/ | LENS-FORM_20260501_120000.json |
| DAL current names | staging, intermediate, curated, state, prepared | dal/staging/, dal/intermediate/, dal/curated/, dal/state/, dal/prepared/ |
| DAL target names (deferred migration) | stg\_, int\_, fct\_, feat\_ | stg_players, int_fixture_base, fct_player_gw_base, feat_player_gw_state |

---

## 9. Rules — never break these

Design before code — always design in Claude UI first, no code until design is agreed

No SQL outside dal/

No study runs without a LENS_DESIGN.md agreed in Claude UI first

No signals enter the signal registry without a confirmed lens status

No signals enter SYNTH-01 without a confirmed registry entry

docs/architecture/DAL_CONTRACT.md is the source of truth for the DAL — any deviation requires updating
the contract first

The governed registry must have real promotion_class values before any lens study design begins — this gate is now met

Two tracks always aligned — pipeline and research move together

---

## 10. How to start a new session

1. Read CONTEXT.md (this document)
2. Read docs/architecture/DAL_CONTRACT.md if any DAL work is planned
3. Read the relevant design document for the current task
4. Do not write code until the design is agreed in Claude UI
