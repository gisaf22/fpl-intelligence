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
(research/eda/findings/eda_03_joint_registry.csv) is its authoritative output. No lens study
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
├── archive/         — retired code from pre-refactor pipeline and analysis eras
├── docs/            — architectural and analytical decision logs
│   └── decisions/   — PINNED decision entries per signal and design choice
├── outputs/         — GW briefing outputs
│   └── gw_34/       — GW 34 outputs
├── archive/         — retired code (pipeline_legacy/ — dead code archived in Wave 5)
├── dal/             — data access layer (DAL) — staging, intermediate, curated, state, validation
├── research/        — analytical methodology layer
│   ├── eda/         — system EDA design, notebooks, and findings
│   ├── evaluation/  — evaluation framework (EVAL_DESIGN.md)
│   ├── experiments/ — experiment scaffolds (EXP-FH-STACK, EXP-FH-PREDICTOR)
│   ├── lenses/      — lens study designs and archived pre-methodology results
│   ├── registry/    — signal registry (SIGNAL_REGISTRY.md)
│   └── runs/        — study run logs and archive
├── CONTEXT.md       — this document
├── KANBAN.md        — feature board and task tracking
├── fpl.db           — SQLite source database
└── main.py          — pipeline entry point
```

---

## 4. Document hierarchy

| Document | Location | Purpose | Gates |
|---|---|---|---|
| DAL_CONTRACT.md | dal/DAL_CONTRACT.md | Authoritative contract for all DAL layers — grain, aggregation rules, validation modules, 8-phase refactor plan | Any DAL code change; deviations require updating this document first |
| EVAL_DESIGN.md | research/evaluation/EVAL_DESIGN.md | Defines success criteria and failure conditions for the 2025-26 methodology before results are known | All study findings must connect to a question defined here |
| SIGNAL_REGISTRY.md | research/registry/SIGNAL_REGISTRY.md | Governance and truth layer for all signals — lifecycle status, lens outcomes, synthesis eligibility | No signal enters synthesis without a confirmed entry; no signal is referenced in a study without being registered |
| EDA_DESIGN.md | research/eda/EDA_DESIGN.md | Defines the seven system EDA layers and their gate decisions | All lens studies — no lens runs before EDA is complete and findings documented |
| EDA_NOTEBOOKS.md | research/eda/EDA_NOTEBOOKS.md | Complete brief for each EDA notebook with questionnaire items | Each EDA notebook run — provides the execution specification |
| CONTEXT.md | CONTEXT.md | Current project state, structure, and rules for new sessions | New session orientation |
| KANBAN.md | KANBAN.md | Feature board tracking all work items with status and task checklists | Session planning — read at start of every session |
| LENS_DESIGN.md (LENS-FORM) | research/lenses/form/LENS_DESIGN.md | Study design for rolling output and attacking threat signals | LENS-FORM execution — study cannot run without agreed design; pending rerun under locked methodology |
| LENS_DESIGN.md (LENS-MARKET) | research/lenses/market/LENS_DESIGN.md | Study design for transfer and ownership signals | LENS-MARKET execution; pending rerun under locked methodology |
| LENS_DESIGN.md (LENS-FIXTURE-GW) | research/lenses/fixture-gw/LENS_DESIGN.md | Study design for single-gameweek fixture difficulty signals | LENS-FIXTURE-GW execution; pending rerun under locked methodology |
| LENS_DESIGN.md (LENS-AVAIL) | research/lenses/avail/LENS_DESIGN.md | Study design for minutes consistency and trend signals | LENS-AVAIL execution; pending rerun under locked methodology |

---

## 5. Current state

| Layer | Status | Notes |
|---|---|---|
| DAL layer | COMPLETE | Staging, integrated, curated, state layers built; all F-DAL-001 through F-DAL-006 done |
| Validation modules | COMPLETE | All 7 modules in dal/validation/; 25 tests passing |
| System EDA | COMPLETE | Governed registry is the authoritative output. Gate decisions in docs/decisions/eda_01_analytical_foundations.md |
| LENS-FORM | PENDING | Old SA results archived; redesign and rerun required under locked methodology |
| LENS-MARKET | PENDING | Old SB results archived; redesign and rerun required under locked methodology |
| LENS-FIXTURE-GW | PENDING | Old SC results archived; redesign and rerun required under locked methodology |
| LENS-AVAIL | PENDING | Old SE results archived; redesign and rerun required under locked methodology |
| LENS-FIXTURE-RUN | PENDING | Future lens; scaffold exists, no design yet |
| Signal registry | READY | Governed registry at research/eda/findings/eda_03_joint_registry.csv has promotion_class values. Lens studies may proceed. |
| SYNTH-01 | BLOCKED ON Signal registry | No synthesis directory; cannot begin until confirmed signals exist in registry |
| EXP-FH-STACK | BLOCKED ON SYNTH-01 | Scaffold exists; no code or findings |
| EXP-FH-PREDICTOR | BLOCKED ON SYNTH-01 | Scaffold exists; no code or findings |
| Evaluation framework | COMPLETE | EVAL_DESIGN.md active and locked; success criteria and failure definitions written |

---

## 6. What is next

- Design LENS-FORM in Claude UI against the governed registry before writing any lens code — this is the first lens to run as it has the richest archived baseline. Gate decisions are in docs/decisions/eda_01_analytical_foundations.md.
- Design and run remaining lenses (LENS-MARKET, LENS-FIXTURE-GW, LENS-AVAIL) in sequence after LENS-FORM confirms or revises signal candidates.
- Register confirmed signals in SIGNAL_REGISTRY.md after each lens study completes — no signal enters synthesis without a confirmed registry entry.

---

## 7. DAL architecture summary

The staging layer (dal/staging.py) handles transformation: column renaming, type
casting, string normalisation, and null standardisation against schema YAML files in
dal/schema/. No joins, no aggregation, no business logic. Six entity schemas are
defined (element_types, teams, events, fixtures, players, player_histories). The staging
engine is schema-driven — load_schema() reads a YAML file and stage() applies all transforms
to return a canonical DataFrame.

The integrated layer (dal/integrated/) handles enrichment: joining staging outputs to
produce wider fixture-grain records. Grain does not change at this layer. player_fixture_base.py
produces the enriched fixture-grain table. fixture_context.py classifies each fixture as BGW,
SGW, or DGW. Validation is separated from join logic — validate_join_safety is called after
every join to prevent silent row loss or fan-out.

The curated layer (dal/curated/player_gameweek_spine.py) changes grain from
fixture-grain to gameweek-grain and produces the canonical base table (player_gw_base). It
aggregates fixture data to GW summaries before spine construction, cross-joins the player
universe against the full GW calendar to build a complete spine, then left-joins aggregated
data onto the spine so unmatched rows become explicit BGW rows. The output contains 33 columns
covering identity, schedule, performance, FDR, market signals, and pricing. BGW handling and
DGW aggregation rules are defined per column category in DAL_CONTRACT.md Section 6. The curated
layer has 25 DAL integrity tests covering grain uniqueness, spine completeness, BGW correctness,
DGW correctness, null semantics, join safety, and system invariants.

Validation is a cross-cutting concern (dal/validation/) with 7 standalone modules:
grain.py, completeness.py, semantics.py, joins.py, contracts.py, nulls.py, invariants.py.
The custom exception DALContractViolation is raised for contract breaches. The 10 core
validation functions cover grain uniqueness, row completeness, BGW correctness, DGW correctness,
null semantics, join safety, column contracts, time continuity, row count invariant, and future
data prohibition. The 8-phase refactor plan in DAL_CONTRACT.md Section 11 governs all further
DAL changes. See DAL_CONTRACT.md for the full specification.

---

## 8. Naming conventions

| Type | Convention | Examples |
|---|---|---|
| Lenses | LENS-[NAME] in uppercase | LENS-FORM, LENS-MARKET, LENS-FIXTURE-GW, LENS-FIXTURE-RUN, LENS-AVAIL |
| Signal IDs | [LENS]-[NNN] assigned sequentially | FORM-001, MARKET-001, FIXTURE-001, AVAIL-001, FIXRUN-001 |
| Experiments | EXP-[NAME] in uppercase | EXP-FH-STACK, EXP-FH-PREDICTOR |
| Run logs | [LENS]-[NAME]_YYYYMMDD_HHMMSS.json in research/runs/ | LENS-FORM_20260501_120000.json |
| DAL current names | staging, integrated, curated, state | dal/staging.py, dal/curated/ |
| DAL target names (deferred migration) | stg\_, int\_, fct\_, feat\_ | stg_players, int_fixture_base, fct_player_gw_base, feat_player_gw_state |

---

## 9. Rules — never break these

Design before code — always design in Claude UI first, no code until design is agreed

No SQL outside dal/

No study runs without a LENS_DESIGN.md agreed in Claude UI first

No signals enter the signal registry without a confirmed lens status

No signals enter SYNTH-01 without a confirmed registry entry

DAL_CONTRACT.md is the source of truth for the DAL — any deviation requires updating
the contract first

The governed registry must have real promotion_class values before any lens study design begins — this gate is now met

Two tracks always aligned — pipeline and research move together

---

## 10. How to start a new session

1. Read CONTEXT.md (this document)
2. Read KANBAN.md for current task state
3. Read the relevant design document for the current task
4. Do not write code until the design is agreed in Claude UI
