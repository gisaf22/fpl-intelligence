# Architecture Boundaries

## Ownership model

Each component owns a specific concern. A component that reads another's output is a
consumer — it must not re-implement the producing component's logic. Cross-concern
duplication is a contract violation.

---

## DAL (`dal/`)

**Owns:** Raw data transformation into the canonical `(player_id, gw)` gameweek-grain spine.

| Sub-layer | Concern |
|---|---|
| `staging/` | Column rename, type cast, null standardisation — no joins, no aggregation |
| `intermediate/` | Join staging outputs into enriched fixture-grain records |
| `curated/` | Aggregate fixture-grain to gameweek-grain; complete spine with BGW rows |
| `state/` | Derive rolling windows, lag features, and trend signals |
| `validation/` | Shared assertion modules called by any layer |

**Does not own:** Signal characterisation, signal scoring, analytical methodology, ML
feature engineering.

**Contract:** [docs/architecture/DAL_CONTRACT.md](architecture/DAL_CONTRACT.md). All DAL
behaviour is specified there. Code must match the contract; the contract is not derived from
the code.

**Consumers:** All downstream layers. Entry points are `dal.access.get_curated_spine` and
`dal.access.get_state_features`. Imports from `dal.staging` or `dal.intermediate` are
forbidden outside the DAL. See
[docs/architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md](architecture/DOWNSTREAM_DEPENDENCY_GOVERNANCE.md).

---

## System EDA (`signals/eda/`)

**Owns:** One-time characterisation of the full dataset that gates all lens work.

- EDA study design (`EDA_DESIGN.md`)
- EDA notebooks (`signals/eda/notebooks/`)
- EDA findings and the governed signal registry output (`signals/eda/findings/`)

**Does not own:** Signal lifecycle status (owned by signal registry), lens study methodology,
operational signal values.

**Contract:** EDA is non-repeatable. Its governed registry output is the authoritative source
for `promotion_class` values. Once closed, EDA findings cannot be revised.

**Consumers:** Signal registry tooling. EDA findings inform registry population; they do not
directly gate synthesis.

---

## Signal Registry (`signals/registry/`)

**Owns:** Lifecycle status for every named signal.

- `SIGNAL_REGISTRY.md` — the authoritative record of every signal's lifecycle state,
  `promotion_class`, and lens study status
- The rules governing promotion between lifecycle states (see
  [docs/research-lifecycle.md](research-lifecycle.md))

**Does not own:** Signal computation logic (owned by `core/signals/`), lens study results
(owned by the individual lens study), EDA findings.

**Contract:** No signal may be used in synthesis or scoring without a `validated` entry in
this registry. No lens study may begin without a prior registry entry. This registry is the
single source of truth for signal status.

**Consumers:** Registry builder (`registry/`), `signals/synthesis/`, `signals/experiments/`,
`core/governance/`.

---

## Lens Studies (`signals/lenses/`)

**Owns:** Per-signal-group characterisation studies.

- The `LENS_DESIGN.md` for each lens (locked before study execution)
- Notebooks and run outputs for each lens study
- The determination of whether a signal reaches `candidate` status

**Does not own:** Signal lifecycle promotion decisions (owned by registry + `EVAL_DESIGN.md`),
signal computation utilities (owned by `core/signals/`), DAL access patterns.

**Contract:** Every lens study must have a locked `LENS_DESIGN.md` before any code runs.
Methodology may not be revised retrospectively once results are produced. Each lens covers
one signal group; scopes must not overlap.

**Consumers:** Signal registry (receives lens study outcomes), `core/governance/` (receives
lens metadata).

---

## Core (`core/`)

**Owns:** Cross-cutting analytical utilities not specific to a single lens or layer.

- Signal computation functions (`core/signals/`)
- Governance rule enforcement (`core/governance/`)
- Player and team relationship data (`core/relationships/`)
- Target variable definitions (`core/target/`)

**Does not own:** Signal lifecycle decisions (owned by registry), DAL transformations, lens
study methodology.

**Contract:** `core/` modules are stateless utilities — they compute, they do not govern.
Governance decisions belong to the registry.

**Consumers:** Lens studies, synthesis, registry builder, scorer.

---

## Registry Builder (`registry/`)

**Owns:** Assembling the governed signal registry artifact from confirmed signals.

- The build pipeline that reads the signal registry and produces the output artifact
- Comparison, metadata, and population logic for the artifact

**Does not own:** Signal lifecycle decisions (owned by `signals/registry/SIGNAL_REGISTRY.md`),
signal computation (owned by `core/signals/`), lens study outputs.

**Contract:** The registry builder is a read-only consumer of the signal registry. It
assembles what the registry marks as confirmed — it does not promote or demote signals.

**Consumers:** Intelligence layer (`scorer/`, `report/`), ML experiments.

---

## Intelligence Layer (`scorer/`, `report/`)

**Owns:** Operational decision support outputs.

- Weekly signal scoring (`scorer/`)
- Weekly signal intelligence report (`report/`)
- Operational interpretation of synthesised signal values

**Does not own:** Signal characterisation (owned by lens studies), signal lifecycle decisions
(owned by registry), DAL transformations.

**Contract:** The intelligence layer may only consume signals with `operationalized` status.
It must not re-implement signal computation or introduce novel signal logic. All signal
values flow from `signals/synthesis/` outputs.

**Consumers:** End users (FPL decision makers).

---

## ML Experiments (`signals/experiments/`)

**Owns:** Backtesting simulations using confirmed signals as features.

- Experiment designs (`EXP-FH-STACK`, `EXP-FH-PREDICTOR`)
- Experiment run logs and results
- Conclusions about whether ML combinations outperform synthesis baselines

**Does not own:** Signal lifecycle decisions, synthesis outputs (consumed, not owned), DAL
access.

**Contract:** Experiments consume `validated` or `operationalized` signals only. Experiment
results do not feed back into the signal registry or intelligence layer without a new lens
study. Experiments are sandboxed — findings motivate future research; they do not bypass
the lifecycle gate.

**Consumers:** Research conclusions only. Experiment outputs are not operational intelligence
inputs.

---

## Ownership non-overlap

| Concern | Single owner |
|---|---|
| All SQL queries | DAL |
| Raw data transformation | DAL (`staging/`) |
| Fixture context enrichment | DAL (`intermediate/`) |
| Canonical `(player_id, gw)` spine | DAL (`curated/`) |
| Rolling/lag feature derivation | DAL (`state/`) |
| Validation assertions | DAL (`validation/`) |
| Dataset-level signal characterisation | System EDA |
| Signal lifecycle status | Signal registry |
| Per-group signal methodology and results | Lens studies |
| Cross-cutting compute utilities | `core/` |
| Registry artifact assembly | Registry builder |
| Operational signal scoring | Intelligence layer |
| ML feature experiments | ML experiments |

No two components share ownership of any row in this table. If a proposed change would
require two components to govern the same concern, the boundary must be resolved before
the change proceeds.
