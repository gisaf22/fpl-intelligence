# System Model

**Authoritative for:** conceptual classification of system components — what each part of
the system is responsible for and why it exists (the **runtime / operational anatomy**).
**Not the analysis lifecycle.** How a question becomes a recommendation — the
explore → validate → model → serve → monitor stages — is owned by [adlc.md](adlc.md).
This doc and ADLC are **orthogonal views of one system**: ADLC describes *how analysis is
done*; this doc describes *what the running system is made of*. Neither supersedes the other.  
**Read this before:** [layer-boundaries.md](layer-boundaries.md), [registry-governance.md](../registry-governance.md), [runtime-execution.md](runtime-execution.md)

---

## The problem with "layers"

The import hierarchy in this repository — DAL → studies → signals → intelligence — describes dependency direction, not conceptual role. Treating it as the primary mental model creates confusion:

- It implies registry is just another step in a pipeline. It is not — it is configuration.
- It implies evaluation is a layer above intelligence. It is not — it is a separate measurement concern that is not yet fully implemented.
- It implies studies are an intermediate processing step. They are not — they are the research methodology that produces evidence for the registry.

The 3-plane model below is the correct mental model. The layer hierarchy is still accurate for import rules and dependency enforcement. Both models coexist; they describe different things.

---

## The 3-Plane Model

The system has three orthogonal planes. Each plane has a distinct purpose and a distinct relationship to time (offline vs. runtime vs. retrospective).

```
┌─────────────────────────────────────────────────────────┐
│  CONTROL PLANE  (Configuration)                         │
│  Defines how the system behaves                         │
│  registry · signal definitions · weights · thresholds   │
└────────────────────────────┬────────────────────────────┘
                             │ configures
                             ▼
┌─────────────────────────────────────────────────────────┐
│  EXECUTION PLANE  (Runtime Decision System)             │
│  Converts raw state → ranked decisions                  │
│  DAL · lifecycle gate · intelligence (scorer/reporter)  │
└────────────────────────────┬────────────────────────────┘
                             │ produces outputs
                             ▼
┌─────────────────────────────────────────────────────────┐
│  MEASUREMENT PLANE  (Partially Missing)                 │
│  Measures whether execution produces good decisions     │
│  evaluation concepts · backtesting · historical replay  │
└─────────────────────────────────────────────────────────┘
```

---

## Control Plane

**Purpose:** Defines what signals exist, what their properties are, how they are weighted, and what thresholds govern their use. Changes here change system behavior without touching execution code.

**Components:**

| Artifact / Component | Role |
|---|---|
| `signals/characterisation/SIGNAL_REGISTRY.md` | Lifecycle status for every named signal — the governance ledger |
| `outputs/registry/gw{N}/registry.csv` | Governed signal manifest: rho weights, promotion class, layer roles |
| `outputs/registry/gw{N}/build_metadata.json` | Registry build provenance: timestamp, source, schema version |
| `signals/characterisation/registry_build_runner.py` + `registry_assembler.py` | Assembles the governed artifact from confirmed signal evidence |
| `signals/governance/` | Lifecycle gate rules — what must be true before a signal enters the manifest |
| Static weights in `intelligence/` modules | Explicit scoring configuration (captain, transfer, value weights) |

**What it is not:** The Control Plane is not a runtime participant. The registry is read once per scoring run and does not change during execution. It is configuration, not a processing stage.

**Why the registry belongs here and not in Execution:** The registry does not transform data. It defines the rules under which data will be transformed. A football analogy: the registry is the tactical formation sheet, not the match. Changing the registry changes decisions without changing any pipeline code.

**How the Control Plane is populated:** Signal evidence flows upward from research (studies) through the governance gate into the governed manifest. These studies are not a runtime plane — they are **ADLC's explore / validate / model stages** viewed from the runtime angle: the evidence-generation process that justifies what the Control Plane declares. See [adlc.md](adlc.md) for the analysis lifecycle and [signal-promotion-states.md](../signal-promotion-states.md) for the signal's governance states.

---

## Execution Plane

**Purpose:** Takes raw database state and produces ranked, scored, human-readable decision outputs. This is the operational runtime.

**Components:**

| Component | Role |
|---|---|
| `dal/` | Transforms raw source data into the validated `(player_id, gw)` spine with state features |
| `signals/governance/lifecycle.py` | Runtime lifecycle gate — enforces that only governed registry paths reach the scorer |
| `intelligence/scoring/` | Applies registry-defined signal weights to DAL features; produces scored player tables |
| `intelligence/reporting/` | Produces weekly signal intelligence reports from scored outputs |
| `intelligence/intelligence_contracts.py` | Input validation — enforces that execution receives DAL-produced features, not research proxies |

**Data flow through Execution:**

```
fpl.db → DAL (validated features) → lifecycle gate → scorer (registry-weighted) → HTML / report
```

The execution plane is self-contained: given a database and a governed registry path, it produces the same output deterministically. It does not depend on which signals were investigated, which lens studies ran, or what the measurement plane has observed. The registry is the only interface.

**What belongs here vs. Control Plane:** If it transforms data at runtime, it belongs in Execution. If it declares how data should be transformed, it belongs in Control.

---

## Measurement Plane

**Purpose:** Measures whether the execution plane is producing decisions that lead to good FPL outcomes. This closes the loop: evidence → registry → execution → measurement → new evidence.

**This plane is not fully implemented.**

> This is the runtime-anatomy view of the same gap ADLC names as its **`monitor`** stage.
> The forward-looking spec lives in `signals/governance/EVAL_DESIGN.md`; ADLC `monitor` is
> the lifecycle counterpart. This section describes *what the plane is* — it does not re-derive
> the build-out plan. See those two for that.

| Capability | Status |
|---|---|
| Structural validation (tests) | Present — verifies correctness of execution logic |
| Explainability (execution trace) | Present — allows auditing of individual scores |
| Backtest against actual GW returns | Not implemented |
| Historical replay across seasons | Not implemented |
| Decision quality metrics | Not implemented |
| Feedback loop into signal registry | Not implemented |

**Why tests and explainability are NOT Measurement Plane:**

- **Tests** verify that the execution plane behaves according to its specification. They tell you whether the code is correct, not whether the decisions are good.
- **Explainability** is an execution trace artifact — it shows how a score was computed. It allows a human to audit the Execution Plane. It does not measure decision quality.

Measurement requires ground truth: actual FPL returns for the gameweeks the system scored. Without that, there is no measurement — only execution.

**What partial measurement exists today:**

The evaluation framework (`signals/governance/EVAL_DESIGN.md`) defines success criteria and failure conditions for the 2025-26 methodology. This is a forward-looking measurement contract — it defines what "good" looks like so results can be compared after the season. It is the design specification for the Measurement Plane, not the Measurement Plane itself.

**What full measurement requires:**
1. Capturing system outputs at the time of each GW decision
2. Observing actual GW returns
3. Comparing predicted ranking to actual performance
4. Aggregating across enough GWs to assess statistical significance
5. Feeding results back to inform registry updates for the following season

None of steps 2-5 are implemented yet.

---

## Component classification table

| Component | Plane | Notes |
|---|---|---|
| `dal/` | Execution | Transforms raw state into validated features |
| `dal/staging/`, `dal/intermediate/`, `dal/fct/`, `dal/feat/` | Execution | Sub-pipeline within DAL |
| `signals/governance/` | Execution | Runtime gate enforcement |
| `intelligence/scoring/` | Execution | Applies Control Plane weights to produce ranked output |
| `intelligence/reporting/` | Execution | Weekly report from scored output |
| `outputs/registry/gw{N}/registry.csv` | Control | Governed signal manifest — configures scorer behavior |
| `signals/characterisation/registry_build_runner.py` + `registry_assembler.py` | Control | Writes the governed manifest |
| `signals/characterisation/SIGNAL_REGISTRY.md` | Control | Lifecycle ledger |
| Static weights in `intelligence/` modules | Control | Explicit scoring configuration |
| `studies/eda/` | Research methodology | Evidence base for Control Plane; one-time and non-repeatable |
| `studies/lenses/` | Research methodology | Per-signal characterisation; produces evidence for registry promotion |
| `studies/kernels/` | Research methodology | Statistical utilities consumed by lens studies |
| `studies/experiments/` | Emerging Measurement | Backtesting simulations — closest current approximation of Measurement Plane |
| `signals/governance/EVAL_DESIGN.md` | Measurement (design only) | Defines success criteria; the contract the Measurement Plane must satisfy |
| Tests (`tests/`) | Structural validation | Verifies execution correctness — NOT Measurement Plane |
| Explainability outputs | Execution trace | Enables auditing of scores — NOT Measurement Plane |

---

## What is missing

The gap between this system and a fully closed-loop system is the Measurement Plane:

1. **Backtest infrastructure.** No mechanism exists to replay decisions against historical GW returns at scale.
2. **Decision quality metrics.** No agreed measure of whether the scorer's rankings predicted actual FPL performance.
3. **Feedback loop.** No mechanism to carry measurement findings back into the registry or lifecycle.

These are not bugs. They are the explicit scope boundary for 2025-26, which is the development season. The registry, lifecycle, and evaluation framework are designed so that measurement can be added when real-season outcomes are available.

The existence of `studies/experiments/` (backtesting) represents the first step toward the Measurement Plane — but experiments run against historical data are a proxy, not a substitute.

---

## Relationship to the layer model

The 4-layer import hierarchy (DAL → studies → signals → intelligence) and the 3-plane model describe the same system from different angles:

| Question | Use |
|---|---|
| Which module can import from which? | Layer model ([layer-boundaries.md](layer-boundaries.md)) |
| What is each part of the system for? | Plane model (this document) |
| How does a decision get made (runtime)? | [runtime-execution.md](runtime-execution.md) |
| How is the model researched and chosen? | [adlc.md](adlc.md) |

The layer model enforces structural integrity. The plane model provides cognitive clarity. Neither supersedes the other.
