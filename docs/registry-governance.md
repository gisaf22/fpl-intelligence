# Registry Governance

See also: [signal-promotion-states.md](signal-promotion-states.md) · [architecture/layer-boundaries.md](architecture/layer-boundaries.md)

---

## Purpose

The signal registry is the single machine-readable contract between the research layer and the operational intelligence layer. It characterises each signal's statistical properties, lifecycle state, and eligibility for operational use.

**Plane classification:** The registry is part of the **Control Plane** — it configures intelligence behavior; it is not a runtime processing stage and it is not a peer of the intelligence layer. See [system-model.md](architecture/system-model.md) for the full 3-plane classification.

The registry lives in two forms:

| Form | Path | Role |
|---|---|---|
| Research (EDA output) | `studies/eda/findings/eda_03_joint_registry.csv` | Authoritative analytical output of system EDA. Exploratory state. |
| Operational (promoted) | `outputs/registry/gw{N}/registry.csv` | Built via the registry builder after lifecycle promotion. Safe for operational consumers. |

---

## Lifecycle States

The full lifecycle is: `exploratory → investigational → candidate → validated → operationalized`.

[signal-promotion-states.md](signal-promotion-states.md) is the authoritative owner of these
state definitions, their allowed consumers, and the promotion criteria for each transition — this
document does not restate them. The registry-relevant rule is: only `validated` signals may enter
the registry builder, and only `operationalized` signals may reach the scorer and report runner.

---

## Exploratory vs Operational Registries

**Exploratory registries** live under `studies/eda/`. They are the direct output of system EDA and contain unvalidated signals in exploratory state. Their `promotion_class` values reflect statistical characterisation, not lifecycle approval.

**Operational registries** live under `outputs/registry/`. They are built by `signals/characterisation/registry_build_runner.py` from validated or operationalized signals and have passed `validate_registry_contract()` before writing.

The distinction is enforced at the path level. Any path under `studies/eda/` is treated as exploratory regardless of its content.

---

## Runtime Enforcement

Two operational consumers enforce the lifecycle gate automatically:

**`intelligence/scoring/signal_selector.py::load_manifest_from_path(registry_path)`**
Calls `assert_operational_safe(registry_path)` before loading. Raises `LifecycleViolationError` if the path is under `studies/eda/`.

**`intelligence/reporting/weekly_report_runner.py::run_week(gw, registry_path, ...)`**
Calls `assert_operational_safe(registry_path)` after gw validation. Raises `LifecycleViolationError` if the path is under `studies/eda/`.

**Research consumers** (`signals/governance/registry_loader.py::load_registry`, registry builder) carry no lifecycle restriction. They may load any registry by path.

The gate is path-based, not content-based. A registry CSV copied out of `studies/eda/` and into `outputs/registry/` (via the registry builder) is safe for operational use.

---

## Promotion

To move a registry from exploratory to operational:

1. Signals must reach `validated` or `operationalized` status via lens study and formal confirmation (see [signal-promotion-states.md](signal-promotion-states.md)).
2. Run the registry builder: `python -m signals.characterisation.registry_build_runner --gw N --mode packaged --source-registry-path <validated-source>`.
3. The builder validates the contract and writes to `outputs/registry/gw{N}/registry.csv`.
4. Pass that path to the scorer and report runner via `--registry-path`.

No signal advances to synthesis without a confirmed registry entry. No operational consumer may consume a registry in exploratory state.

---

## What "Validated" Means Operationally

A signal is `validated` when it has:

- Passed the system EDA (`promotion_class` is `core_signal` or `review_signal`)
- Completed a lens study with confirmed methodology
- Met the success criteria in `signals/governance/EVAL_DESIGN.md`
- A registry entry with `downstream_status` in `{eligible, caveated}` (not `blocked`)

`validated` signals may enter synthesis. `operationalized` signals are active in the scorer.

---

## What the Scorer Is Allowed to Consume

The scorer (`intelligence/scoring/signal_selector.py`) consumes only the signals in an operational
registry that pass the selection filters (promotion class, role/leakage exclusion, non-null rho).
Those filters and their rationale are owned by
[architecture/explainability-model.md](architecture/explainability-model.md) — this document does
not restate them.

The registry-governance rule is the **path gate**: the registry must come from `outputs/registry/`,
not `studies/eda/`. Passing an exploratory registry path to the scorer raises
`LifecycleViolationError` at load time.

---

## Current State (2025-26 season)

The system EDA registry (`eda_03_joint_registry.csv`, 116 rows) is in exploratory state. No signals have completed lens validation. `SIGNAL_REGISTRY.md` reflects the pre-lens state.

Operational use of the scorer and report runner requires:
1. Completing at least one lens study per the locked `LENS_DESIGN.md`
2. Formally confirming signals against `EVAL_DESIGN.md`
3. Building an operational registry via the registry builder
4. Providing that registry path explicitly via `--registry-path`
