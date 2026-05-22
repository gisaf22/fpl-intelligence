# Registry Governance

See also: [research-lifecycle.md](research-lifecycle.md) · [architecture/layer-boundaries.md](architecture/layer-boundaries.md)

---

## Purpose

The signal registry is the single machine-readable contract between the research layer and the operational intelligence layer. It characterises each signal's statistical properties, lifecycle state, and eligibility for operational use.

**Plane classification:** The registry is part of the **Control Plane** — it configures intelligence behavior; it is not a runtime processing stage and it is not a peer of the intelligence layer. See [system-model.md](architecture/system-model.md) for the full 3-plane classification.

The registry lives in two forms:

| Form | Path | Role |
|---|---|---|
| Research (EDA output) | `signals/eda/findings/eda_03_joint_registry.csv` | Authoritative analytical output of system EDA. Exploratory state. |
| Operational (promoted) | `outputs/registry/gw{N}/registry.csv` | Built via the registry builder after lifecycle promotion. Safe for operational consumers. |

---

## Lifecycle States

The full lifecycle is: `exploratory → investigational → candidate → validated → operationalized`

**What each state means for registry consumption:**

- `exploratory` — System EDA output only. No signal may be used operationally. Consumers: EDA notebooks, registry builder.
- `investigational` — Active lens study in progress. No synthesis or operational use.
- `candidate` — Lens study complete, pending formal confirmation. No operational use.
- `validated` — Confirmed against evaluation criteria. May enter synthesis and the registry builder.
- `operationalized` — Active in the synthesis pipeline. Eligible for scorer and report runner.

---

## Exploratory vs Operational Registries

**Exploratory registries** live under `signals/eda/`. They are the direct output of system EDA and contain unvalidated signals in exploratory state. Their `promotion_class` values reflect statistical characterisation, not lifecycle approval.

**Operational registries** live under `outputs/registry/`. They are built by `registry/runner.py` from validated or operationalized signals and have passed `validate_registry_contract()` before writing.

The distinction is enforced at the path level. Any path under `signals/eda/` is treated as exploratory regardless of its content.

---

## Runtime Enforcement

Two operational consumers enforce the lifecycle gate automatically:

**`scorer/signals.py::load_manifest_from_path(registry_path)`**
Calls `assert_operational_safe(registry_path)` before loading. Raises `LifecycleViolationError` if the path is under `signals/eda/`.

**`report/runner.py::run_week(gw, registry_path, ...)`**
Calls `assert_operational_safe(registry_path)` after gw validation. Raises `LifecycleViolationError` if the path is under `signals/eda/`.

**Research consumers** (`core/governance/loader.py::load_registry`, registry builder) carry no lifecycle restriction. They may load any registry by path.

The gate is path-based, not content-based. A registry CSV copied out of `signals/eda/` and into `outputs/registry/` (via the registry builder) is safe for operational use.

---

## Promotion

To move a registry from exploratory to operational:

1. Signals must reach `validated` or `operationalized` status via lens study and formal confirmation (see [research-lifecycle.md](research-lifecycle.md)).
2. Run the registry builder: `python -m registry.runner --gw N --mode packaged --source-registry-path <validated-source>`.
3. The builder validates the contract and writes to `outputs/registry/gw{N}/registry.csv`.
4. Pass that path to the scorer and report runner via `--registry-path`.

No signal advances to synthesis without a confirmed registry entry. No operational consumer may consume a registry in exploratory state.

---

## What "Validated" Means Operationally

A signal is `validated` when it has:

- Passed the system EDA (`promotion_class` is `core_signal` or `review_signal`)
- Completed a lens study with confirmed methodology
- Met the success criteria in `signals/evaluation/EVAL_DESIGN.md`
- A registry entry with `downstream_status` in `{eligible, caveated}` (not `blocked`)

`validated` signals may enter synthesis. `operationalized` signals are active in the scorer.

---

## What the Scorer Is Allowed to Consume

The scorer (`scorer/signals.py`) filters the operational registry to signals where:

- `promotion_class` is `core_signal` or `review_signal`
- `layer_role` is not `points_component` (leakage) or `contribution_index` (outcome-component)
- `abs(rho_pooled) >= 0.15`

The registry must come from `outputs/registry/`, not `signals/eda/`. Passing an exploratory registry path to the scorer raises `LifecycleViolationError` at load time.

---

## Current State (2025-26 season)

The system EDA registry (`eda_03_joint_registry.csv`, 116 rows) is in exploratory state. No signals have completed lens validation. `SIGNAL_REGISTRY.md` reflects the pre-lens state.

Operational use of the scorer and report runner requires:
1. Completing at least one lens study per the locked `LENS_DESIGN.md`
2. Formally confirming signals against `EVAL_DESIGN.md`
3. Building an operational registry via the registry builder
4. Providing that registry path explicitly via `--registry-path`
