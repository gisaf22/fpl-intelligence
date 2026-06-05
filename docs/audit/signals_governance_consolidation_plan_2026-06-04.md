# Signals → Governance Consolidation — Migration Plan

**Status:** PROPOSED (not started). The deferred "PR-8+" follow-on to the
signals-decomposition migration (`signals_decomposition_migration_plan_2026-06-04.md`,
completed at commit `6b8accf`).

**Scope of this doc:** dissolve `signals/governance/` so the `signals/` root package
disappears. This plan deliberately does **not** cover the `intelligence/ → serve/` rename
(captured in memory `project-phase7-signals-serve-consolidation`); that is a separate,
independent rename and is listed under §7 Out of scope.

> **Why a plan doc first.** `signals/governance/` is the governance core — the lifecycle
> gate, the operational load gate, the decision-of-record (`evaluation_metadata.yaml`), and
> the runtime governance lookup the scorer depends on. Moving it is not a mechanical `git mv`:
> it collides with a live import-linter contract (see §3). This doc maps every edge and
> forces the central design decision **before** any code moves.

---

## 0. Current state (post-decomposition, commit `6b8accf` + gw36 fix `20f8988`)

`signals/governance/` is all that remains of the `signals/` root. Contents:

| Artifact | Kind | Role |
|---|---|---|
| `governance.py` | code | `get_signal_governance(signal, position)`, `get_signal_governance_by_key(key)` — reads `evaluation_metadata.yaml`; the runtime governance **lookup** |
| `lifecycle.py` | code | `assert_operational_safe()` (path-based lifecycle gate), `LifecycleViolationError`, `LeakageViolationError` |
| `registry_loader.py` | code | operational load **gate** wrapper → delegates to `domain.registry.loader.load_registry` |
| `__init__.py` | code | re-export facade: `load_registry`, `validate_registry_contract`, `assert_operational_safe`, the three error types, `RegistryValidationError` |
| `evaluation_metadata.yaml` | data | the **decision-of-record** (≈48 KB; per-signal, per-position lifecycle/downstream/synth decisions) |
| `EVAL_DESIGN.md` | doc | locked success criteria / failure conditions for the 2025-26 methodology |

Internal imports of the moved code reach **only `domain.*`** (`domain.registry.{schema,loader,validation}`)
and itself. It imports nothing from `research`, `model`, or `intelligence`. → The body of the
move introduces **no new forbidden edges** on its own. The problem is entirely on the *consumer* side.

### Importers of `signals.governance.*`

**Production (3):**

| Importer | Layer | Imports |
|---|---|---|
| `intelligence/scoring/signal_selector.py` | intelligence | `get_signal_governance`, `LeakageViolationError`, `LifecycleViolationError`, `registry_loader.load_registry` |
| `intelligence/reporting/weekly_report_runner.py` | intelligence | `load_registry`, `validate_registry_contract` |
| `model/governance/promote.py` | model | `lifecycle.assert_operational_safe` |

**Tests (20 files):** `test_composite_key_migration`, `test_registry_assembly`,
`test_registry_build_parity`, `test_registry_build_runner`, `test_registry_contract`,
`test_registry_lifecycle`, `test_registry_promote`, `test_registry_semantics`,
`test_relationship_computation`, `test_runtime_consumer_alignment`,
`test_runtime_metadata_propagation`, `test_scorer_engine`, `test_scorer_signals`,
`test_spine_traversal_metadata`, `test_weekly_*` (insights, markdown_report, reports, runner,
signal_intelligence, snapshots).

### Runtime **path-string** references to `signals/governance/evaluation_metadata.yaml`

These are `Path(...)` reads, **not** Python imports — they must be repointed too if the data moves:

- `signals/governance/governance.py` (`_EVAL_METADATA_PATH` + 3 error-message strings)
- `model/governance/signal_traceability.yaml` (header comment + `evaluation_metadata:` field)
- `model/governance/SIGNAL_REGISTRY.md`, `model/assemble/synth01_candidates.yaml` (provenance comments)
- `CONTEXT.md` (§ several), plus EVAL_DESIGN.md references
- tests: `test_composite_key_migration`, `test_evaluation_metadata`,
  `test_runtime_metadata_propagation`, `test_traceability_completeness`

---

## 1. The central constraint (the reason this is risky)

`.importlinter` contract **`no_intelligence_to_research_or_model`** forbids `intelligence → model`.

Today the two `intelligence/` importers reach the governance core via `intelligence → signals`,
which **is** allowed — that is precisely why `signals/` sits below `intelligence/` in the layer
order and why PR-7 kept it. If `signals/governance/` folds wholesale into `model/governance/`,
then `intelligence/scoring/signal_selector.py` and `intelligence/reporting/weekly_report_runner.py`
would import `model.governance.*` → **contract violation**, and the gate goes red.

So the consolidation cannot be a single relocation. The governance core splits along a
**decide vs. consume** seam:

- **Decision / authoring side** — `evaluation_metadata.yaml`, `EVAL_DESIGN.md`, the governance
  vocabulary, promotion. Consumed by `model/`. Natural home: **`model/governance/`**.
- **Runtime-consumption side** — the operational load gate (`registry_loader`), the lifecycle
  gate (`assert_operational_safe`), and the governance **lookup** (`get_signal_governance`) used
  by the scorer (including the gw36 fix). Consumed by `intelligence/`. Must live somewhere
  `intelligence/` is *allowed* to import.

`intelligence/` may import `dal` and `domain` (the shared leaf), and layers at or below it. It
may **not** import `model` or `research`. So the runtime-consumption side has only two legal homes.

---

## 2. Target-design options (the decision to make before coding)

### Option A — Runtime gate/lookup → `domain.registry.*`; decision data → `model/governance/` (recommended)

- Move `lifecycle.py` and `registry_loader.py` into `domain/registry/` (they already delegate to
  `domain.registry.loader`; `assert_operational_safe` is path-policy = a contract concern, which is
  what `domain/registry/` already owns). Lifecycle/load gates become `domain.registry.lifecycle` /
  `domain.registry.loader`.
- Move `evaluation_metadata.yaml` + `EVAL_DESIGN.md` into `model/governance/`.
- `get_signal_governance` is the tension point: it *reads* the decision data. Resolve by making
  it a **pure reader in `domain`** parameterised on the data path, with `model/governance/`
  owning the *path constant* — OR keep the lookup in `domain.registry` reading a path the
  decision-of-record publishes. Either way intelligence imports only `domain`.
- **Pros:** honours `intelligence ↛ model`; `domain/registry/` already owns the registry contract
  + pure loader, so the gate/lookup sit beside their natural kin; smallest contract churn.
- **Cons:** `domain` (the leaf) reading a file that *lives* under `model/governance/` is
  conceptually slightly inverted (a path string, not an import — so not a contract breach, but
  worth a doc note). Mitigate by having `model/governance/` own the path constant and `domain`
  receive it.

### Option B — Everything → `model/governance/`; relax the intelligence contract

- Fold the whole core into `model/governance/`; amend `no_intelligence_to_research_or_model` to
  permit `intelligence → model.governance` (a carve-out).
- **Pros:** literally matches the deferred-memory phrasing ("fold signals into model/governance").
- **Cons:** punches a hole in the cleanest boundary in the system. `intelligence → model` is a
  deliberate firewall (intelligence consumes governed *artifacts*, not model code). Rejecting.

### Option C — Do nothing; keep `signals/` as the governance layer

- The status quo PR-7 settled on. `signals/` stays as the dedicated governance layer between
  `research`/`model` and `intelligence`.
- **Pros:** zero risk; the layering is already coherent (intelligence reads governance below it).
- **Cons:** leaves a single-subpackage root package; doesn't realise the object-primary doctrine's
  final topology. Legitimate to choose if the consolidation isn't worth the churn.

**Recommendation: Option A.** It is the only target that both removes `signals/` *and* keeps every
import-linter contract intact (after the root-package edit in §3). If the appetite for risk is low,
Option C (stop here) is entirely defensible — record it and close the deferred thread.

---

## 3. `.importlinter` changes (Option A)

- `root_packages`: **remove `signals`**.
- Delete contract `no_signals_to_research_or_intelligence` (source package gone).
- Remove `signals` from `forbidden_modules` in `no_research_to_downstream` and
  `no_dal_to_system_layers`.
- `no_intelligence_to_research_or_model`: **unchanged** — Option A keeps the intelligence-facing
  code in `domain`, so the contract stays green. (This is the whole point of choosing A.)
- `no_model_to_research_analysis`: unchanged; moved code imports only `domain`, never
  `research.{foundation,families,findings}`.

Net: 7 contracts → 6 (one deleted), `signals` removed from 3 places. Verify `lint-imports`
reports **6 kept, 0 broken** post-migration.

---

## 4. PR phasing (Option A) — low → high risk, gate green each PR

> Convention carried from the prior migration: one PR = one commit; pause for review after each;
> full green gate (`ruff check . && uv run mypy && uv run lint-imports && python -m pytest -q`)
> before every commit; map definition sites + importers before editing; `git mv` for history.

- **C-PR-1 — Lifecycle gate → `domain/registry/lifecycle.py`.** `git mv signals/governance/lifecycle.py`.
  Repoint `model/governance/promote.py` and the two `intelligence/` importers + tests from
  `signals.governance.lifecycle` → `domain.registry.lifecycle`. Lowest risk (path-policy code,
  no data). Gate green.
- **C-PR-2 — Operational load gate → `domain/registry/`.** Fold `registry_loader.py` into
  `domain.registry.loader` (or a sibling `domain/registry/operational.py`). Repoint
  `intelligence/*` + tests. The pure typed loader already lives here, so this reunites the gate
  with the loader it wraps.
- **C-PR-3 — Decision data → `model/governance/`.** `git mv evaluation_metadata.yaml` +
  `EVAL_DESIGN.md` into `model/governance/`. Introduce a single path constant
  (`model/governance` owns it). Repoint **every** `Path("signals/governance/evaluation_metadata.yaml")`
  string (§0 list) + the doc references. This is the largest churn PR (string refs are easy to miss
  — grep `signals/governance` to zero before committing).
- **C-PR-4 — Governance lookup placement.** Move `get_signal_governance{,_by_key}` to its Option-A
  home (`domain.registry`, reading the path constant published by `model/governance/`). Repoint
  `intelligence/scoring/signal_selector.py` (incl. the gw36 fix), the traceability/spine tests.
- **C-PR-5 — Delete `signals/`, finalize contracts.** Remove the now-empty `signals/governance/__init__.py`
  + `signals/` root. Apply the §3 `.importlinter` edits. Refresh docs: `CONTEXT.md`,
  `docs/architecture/layer-boundaries.md` (the "Signals (`signals/`)" section + system-architecture
  diagram + ownership table rows pointing at `signals/governance/*`), `docs/navigation-map.md`.
  Gate must show **6 kept, 0 broken**.

---

## 5. Risk analysis

- **Highest:** the intelligence↛model contract (§1). Mitigated entirely by Option A's placement;
  if Option B were chosen instead, this becomes a permanent architectural concession.
- **Sneaky:** the ~9 `Path("signals/governance/evaluation_metadata.yaml")` string references
  (§0). These are not caught by mypy or import-linter — only by tests that actually load the file.
  `test_evaluation_metadata`, `test_traceability_completeness`, `test_composite_key_migration`,
  `test_runtime_metadata_propagation` are the safety net; confirm they exercise the new path.
- **Doc drift:** `layer-boundaries.md` has a whole "Signals" ownership section + ownership-table
  rows; `CONTEXT.md` cites `signals/governance/EVAL_DESIGN.md` repeatedly. Budget real edit time.
- **Guard tests:** `test_dal_architecture`, `test_intelligence_outputs`, `test_downstream_governance`
  — verify these stay green (Option A keeps intelligence's edges legal, so they should not flip).

---

## 6. Test traceability

| PR | Primary proof |
|---|---|
| C-PR-1 | `test_registry_lifecycle`, `test_registry_promote`, `test_scorer_signals` |
| C-PR-2 | `test_registry_contract`, `test_registry_build_runner`, `test_weekly_runner` |
| C-PR-3 | `test_evaluation_metadata`, `test_traceability_completeness`, `test_composite_key_migration`, `test_runtime_metadata_propagation` |
| C-PR-4 | `test_scorer_signals` (incl. gw36 guard), `test_spine_traversal_metadata`, `test_runtime_consumer_alignment` |
| C-PR-5 | `lint-imports` (6 kept, 0 broken); full suite green |

---

## 7. Out of scope (explicit)

- **`intelligence/ → serve/` rename** — independent; touches all runtime modules + the
  `test_dal_architecture` guard string + the `intelligence` root package. Separate plan if pursued.
- **Regenerating any registry / re-running studies** — the gw36 drift is already resolved in code
  (`20f8988`); no artifact regeneration is in this plan.
- **Changing governance semantics or the decision-of-record content** — pure relocation only.
