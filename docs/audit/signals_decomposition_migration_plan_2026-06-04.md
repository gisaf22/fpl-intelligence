# Signals Layer — Decomposition Migration Plan

**Date:** 2026-06-04
**Author:** Principal Analytics Engineer
**Status:** READY FOR EXECUTION (decisions resolved below)
**Predecessor:** `research_migration_phase5_2026-06-03.md` (studies → research/model, complete)
**Nature:** dependency-safe dismantling of `signals/` into the finalized role architecture. **Not** an architecture exercise — all ownership is frozen (see §0).

---

## 0. Frozen architecture + resolved placement decisions

Ownership is final (do not revisit). The four decisions that were open at plan-time are **resolved here** so the plan is executable:

| Open question | Resolution | Rationale |
|---|---|---|
| Where does the **registry contract** live? (`shared/` forbidden as a new bucket) | **`domain/registry/`** | The contract is imported by the producer (research), the validator/gate (governance), and the consumer (serve). The only layer below all three is `domain/`. Using it is **not** a new bucket — `domain/` already hosts below-all definitions (`fpl_scoring`, `signal_layers`). |
| Where do **module-blend weights** go? (`serve/` does not exist yet) | **`intelligence/`** (the current serve layer) | They are consumed only by `intelligence/`. Placing them with their consumer **decouples** this migration from the deferred `intelligence → serve` rename. They ride that later rename for free. |
| Is the **source only `signals/`?** | **No** — source = `signals/` **+** `model/governance/{registry_sections,semantics}.py` | Phase 5 parked *construction* (`registry_sections`, computes via `research.kernels`) and *ontology application* (`semantics`) inside governance. The frozen rule "governance does not construct" makes these mislocated. They must move to research as part of this migration. "Governance is decision-only" is this plan's **target**, not its precondition. |
| Where does **traceability** live? (cross-cutting, no new bucket) | **`model/governance/` as generated, read-only views** | Lineage owns no state; it projects state owned elsewhere. With no new bucket permitted, the least-bad existing home is governance (it is the decision-of-record's lineage). Explicitly marked generated/read-only. |

**Frozen ownership (reference):**

```
domain/        ontology · meaning · signal vocabulary · targets · registry CONTRACT (schema/validation/loader)
research/      statistical computation (kernels) · population prep · registry CONSTRUCTION (the finding)
model/governance/   validation-enforcement · lifecycle gate · decision-of-record · promotion/publication · traceability views
model/assemble/     weighting · composition · SYNTH outputs
intelligence/(serve) scoring · recommendations · module-blend weights
```

**Invariant the registry resolution rests on:** the registry is a **research finding** (`research/findings/records/`). Research **builds** it; governance **promotes** it (validate → gate → publish to `outputs/registry/`). Research stops at the finding; governance never constructs.

---

## 1. Dependency Map (current → target)

| # | Responsibility | Current location | Target | Type |
|---|---|---|---|---|
| D1 | Signal-layer vocabulary (`SIGNAL_LAYER_*`) | `governance/signal_layer_classifier.py`, `governance/schema.py`, `domain/signal_layers.py` (3 copies) | **`domain/signal_layers.py`** (converge to 1) | dedup |
| D2 | Registry contract: schema, PK, types, all `*_VALUES` | `governance/schema.py` | **`domain/registry/schema.py`** | move (split out of governance) |
| D3 | Registry validation rules | `governance/validation.py` | **`domain/registry/validation.py`** (rules); enforcement *call* stays governance | move + keep caller |
| D4 | Registry typed loader | `governance/registry_loader.py` | **`domain/registry/loader.py`**; `load_registry(operational=True)` gate wrapper stays governance | move + keep wrapper |
| D5 | Statistical computation: geometry | `characterisation/geometry.py` (dup of `research/kernels/geometry.py`) | **delete**; importers → `research.kernels.geometry` | dedup-delete |
| D6 | Association-class computation | `characterisation/association.py` | **`research/kernels/association.py`** | move |
| D7 | Population preparation | `characterisation/population_builder.py` | **`research/registry/population_builder.py`** | move |
| D8 | Section computation (rho/geometry/stability/haul) | `model/governance/registry_sections.py` | **`research/registry/sections.py`** (out of governance) | move |
| D9 | Ontology application (enrich_signal_layers) | `model/governance/semantics.py` + `governance/signal_layer_classifier.py` (dup) | **`research/registry/semantics.py`** (converge to 1) | move + dedup |
| D10 | Registry assembly (sections → rows) | `characterisation/registry_assembler.py` | **`research/registry/assembler.py`** | move |
| D11 | Promotion-class enrichment | `governance/promotion.py` | **`research/registry/promotion.py`** (computed during build) | move |
| D12 | Input contracts (prepared-data checks) | `characterisation/registry_build_contracts.py` | **`research/registry/input_contracts.py`** | move |
| D13 | Parity/comparison helpers | `characterisation/comparison.py` | **`research/registry/comparison.py`** | move |
| D14 | Build metadata/provenance | `characterisation/metadata.py` | **`research/registry/metadata.py`** | move |
| D15 | Build config + signal-set/output constants | `characterisation/{config,population}.py` | config → **`research/registry/config.py`**; signal-set → **`domain/`**; output schema → **`domain/registry/`** | split |
| D16 | Build CLI (construct the finding) | `characterisation/registry_build_runner.py` | **`research/registry/build.py`** (build-only) | move + behaviour split |
| D17 | **Promotion/publication** (→ `outputs/registry/`) | (inside `registry_build_runner.py` today) | **`model/governance/promote.py`** (new thin entrypoint) | extract |
| D18 | Decision-of-record + access | `governance/governance.py`, `evaluation_metadata.yaml` | **stays `model/governance/`** | keep |
| D19 | Lifecycle / operational gate | `governance/lifecycle.py` | **stays `model/governance/`** | keep |
| D20 | SYNTH decisions + candidates | `governance/synth01_decisions.yaml`, `characterisation/synth01_candidates.yaml` | **`model/assemble/`** (+ repoint `composition_study` writer) | move + repoint writer |
| D21 | Module-blend scoring weights | `governance/weight_registry.yaml` | **`intelligence/`** (= future serve) | move |
| D22 | Traceability / lineage | `characterisation/signal_traceability.yaml`, `SIGNAL_REGISTRY.md` | **`model/governance/`** (generated views) | move (mark generated) |

---

## 2. PR Phasing Strategy

Seven PRs, ordered low→high coupling, each independently green. Shims bridge the two high-fan-out moves (contract, construction). Import-linter is updated **in the PR that changes the package graph**, never deferred.

> Convention (inherited from Phase 5): `git mv` for moves; re-export shims for broad importer sets; verify each PR with `ruff check . && uv run mypy --config-file pyproject.toml && uv run lint-imports && python -m pytest -q`; one PR = one commit; pause for review.

---

### PR-1 — Converge signal-layer vocabulary to domain
- **Goal:** one source of truth for `SIGNAL_LAYER_VALUES` / `SIGNAL_LAYER_MAPPING` (D1).
- **Moves:** none (dedup). `domain/signal_layers.py` is already canonical.
- **Modified:** delete the inline copies in `governance/schema.py` and `governance/signal_layer_classifier.py`; import from `domain.signal_layers`. Leave `model/governance/semantics.py` importing domain (already does).
- **Shims:** none.
- **Risk:** 2/5.
- **Tests:** `test_registry_semantics`, `test_registry_contract`, `test_registry_assembly`.
- **Rollback:** revert PR (pure import-source change).

### PR-2 — Registry contract → `domain/registry/`
- **Goal:** make the contract an interface below all consumers (D2, D3, D4).
- **Moves:** `git mv` `schema.py → domain/registry/schema.py`, `validation.py → domain/registry/validation.py`, `registry_loader.py → domain/registry/loader.py`.
- **Modified:** add `domain` (already a root pkg) — extend `.importlinter` so `domain/registry` is covered by the domain leaf rule. Leave **re-export shims** at `signals/governance/{schema,validation,registry_loader}.py` (`from domain.registry.X import *`) so the 26+ importers stay green this PR. `governance` keeps the gate wrapper `load_registry(operational=True)` (imports `domain.registry.loader` + `lifecycle`).
- **Shims:** 3 re-export modules in `signals/governance/` (removed in PR-7).
- **Risk:** 3/5 (highest fan-out, but shimmed → mechanical).
- **Tests:** `test_registry_contract`, `test_registry_lifecycle`, `test_runtime_consumer_alignment`, `test_scorer_signals`, `test_registry_build_parity`.
- **Rollback:** revert PR (shims make it isolatable).

### PR-3 — Registry construction → `research/registry/` (the big one)
- **Goal:** move all finding-construction into research and **evacuate construction from governance** (D5–D16); dedup geometry/association into `research/kernels` (legal once the pipeline is in research: `research → research.kernels`).
- **Moves (`git mv`):**
  - `characterisation/{population_builder, registry_assembler, registry_build_contracts→input_contracts, comparison, metadata, config}.py → research/registry/`
  - `characterisation/registry_build_runner.py → research/registry/build.py`
  - `governance/promotion.py → research/registry/promotion.py`
  - **`model/governance/registry_sections.py → research/registry/sections.py`** (reverses the Phase-5 mis-placement)
  - **`model/governance/semantics.py → research/registry/semantics.py`** (converge with `signal_layer_classifier`'s enrich; delete the duplicate)
  - `characterisation/association.py → research/kernels/association.py`
  - **delete** `characterisation/geometry.py`; repoint to `research.kernels.geometry`
- **Modified:** repoint the dynamic `importlib.import_module("model.governance.registry_sections")` → static `from research.registry.sections import …` (now same-layer; remove the importlib indirection — it was only there to dodge the old boundary). Split `characterisation/population.py`: signal-set list → `domain/`, output schema → `domain/registry/`. Update `.importlinter`: drop nothing yet; confirm `research → research.kernels` legal and `research ↛ model/serve` holds.
- **Shims:** temporary re-exports at old `signals/characterisation/*` paths for the import set, removed in PR-7.
- **Risk:** 4/5.
- **Tests:** `test_registry_assembly`, `test_registry_build_runner`, `test_registry_build_parity`, `test_registry_build_inputs`, `test_relationship_computation`, `test_relationship_geometry`, `test_signals_redundancy`, `test_signals_stability`.
- **Rollback:** revert PR (shims isolate; pytest is the **only** net for the de-`importlib`'d edge — run full suite, not scoped).

### PR-4 — Promotion/publication → `model/governance/promote.py`
- **Goal:** separate *build the finding* (research, PR-3) from *promote it* (governance) (D17).
- **Moves:** none.
- **Modified:** extract the validate + publish-to-`outputs/registry/` half of the old runner into a thin `model/governance/promote.py` that **reads the finding artifact** (file-based, no import of research) and calls `domain.registry.validation` + the lifecycle gate. `research/registry/build.py` now stops at writing the finding to `research/findings/records/`.
- **Shims:** none.
- **Risk:** 3/5 (behaviour split — guard with the parity test).
- **Tests:** `test_registry_build_parity`, `test_registry_lifecycle`, `test_registry_promotion`, `test_runtime_consumer_alignment`.
- **Rollback:** revert PR.

### PR-5 — Assembly artifacts → `model/assemble/`; module weights → `intelligence/`
- **Goal:** put weighting/composition with assembly, scoring weights with serve (D20, D21).
- **Moves (`git mv`):** `governance/synth01_decisions.yaml`, `characterisation/synth01_candidates.yaml → model/assemble/`; `governance/weight_registry.yaml → intelligence/`.
- **Modified:** repoint `model/assemble/composition_study.py` `OUT_PATH` → new `model/assemble/` path (the writer); repoint `intelligence/weight_registry.py` loader path; repoint `evaluation_metadata`'s `synth01_decision_id` references. **Atomic** writer+readers in this PR (the governance↔assembly cycle artifact).
- **Shims:** none (data files; repoint all readers/writers together).
- **Risk:** 3/5.
- **Tests:** `test_composite_key_migration`, `test_runtime_consumer_alignment`, `test_spine_traversal_metadata`, `test_runtime_metadata_propagation`.
- **Rollback:** revert PR.

### PR-6 — Traceability → governance generated-views
- **Goal:** house lineage as a read-only projection (D22).
- **Moves (`git mv`):** `characterisation/signal_traceability.yaml`, `characterisation/SIGNAL_REGISTRY.md → model/governance/`.
- **Modified:** repoint `intelligence/provenance.py` + any readers; add a one-line header to each marking it **generated / read-only / projection**.
- **Risk:** 2/5.
- **Tests:** `test_spine_traversal_metadata`, `test_weekly_*` (snapshot/provenance).
- **Rollback:** revert PR.

### PR-7 — Cleanup: remove shims, delete `signals/`, finalize contracts
- **Goal:** finish the dismantling (the green-gate work my critique flagged).
- **Moves:** delete the PR-2/PR-3 re-export shims; `git rm` the now-empty `signals/` tree.
- **Modified:** **rewrite `.importlinter`** — drop `signals` as a root package; re-base the contracts onto the final graph (`domain` leaf incl. `domain.registry`; `research ↛ model/serve`; `model.governance ↛ research.{foundation,families,findings}` kernels-exempt; `intelligence ↛ research/model` except the assemble/governance artifacts it legitimately consumes). Flip guard tests (`test_dal_architecture`, `test_intelligence_outputs`, `test_downstream_governance`) to the signals-free graph. Refresh docs (`CONTEXT.md` §3, `layer-boundaries.md`, `navigation-map.md`).
- **Risk:** 3/5 (import-linter + guard flips — proven failure point if omitted).
- **Tests:** full suite + `lint-imports` (contracts kept) + the 3 guard tests.
- **Rollback:** revert PR.

---

## 3. Dependency Risk Analysis

| Risk | Classification | Mitigation |
|---|---|---|
| `signals → research` forbidden, but construction needs `research.kernels` | **TEMPORARY BUT REQUIRED** | Resolved by PR-3: once construction *is* research, the edge is `research → research.kernels` (legal). Until PR-3 lands, the geometry fork stays. |
| Dynamic `importlib` edge (`registry_build_runner → model.governance.registry_sections`) invisible to import-linter | **TEMPORARY BUT REQUIRED** | PR-3 converts it to a static same-layer import. **pytest is the only safety net** — run full suite on PR-3, never scoped. |
| `model/assemble → signals/governance` write (`composition_study` OUT_PATH) | **TEMPORARY BUT REQUIRED** | PR-5 repoints writer + all readers atomically. Cycle dissolves because both ends land in `model/assemble`. |
| governance↔assembly feedback (`lifecycle_state=approved` written by SYNTH) | **SAFE (sequenced)** | It is a temporal pipeline, not a static cycle: assembly *recommends*, governance *records*. No PR introduces a mutual import. |
| Contract in `domain/` imported by all layers | **SAFE** | `domain/` is the leaf; all edges point down. No upward import created. |
| `signals` root package disappears from `.importlinter` | **BLOCKER if omitted** | PR-7 rewrites contracts. Proven this-session ("Module 'signals' does not exist"). Non-optional. |
| Splitting `schema.py` / vocab dedup cannot use history-preserving `git mv` | **SAFE (accepted)** | Splits are edits, not moves; history for the split-out file is acceptable to break. Flagged so no PR pretends otherwise. |

**No remaining static dependency cycles** after PR-7. The two real entanglements (dynamic import, assembly→governance write) are each dissolved by a single atomic PR.

---

## 4. Migration Ordering Logic (sequencing only)

1. **PR-1 first (vocab dedup):** independent, zero-fan-out, removes a triplicate that would otherwise have to be reconciled mid-move. Smallest safe warm-up.
2. **PR-2 before PR-3 (contract before construction):** construction code imports the contract; moving the contract to `domain/` first (with shims) means PR-3's construction move lands importing the *final* contract location, not a soon-to-move one. Avoids double-churn on the 26 contract importers.
3. **PR-3 before PR-4 (build before promote-split):** you cannot cleanly extract "promote" until the build code is in research; doing them together would be an un-reviewable mega-PR.
4. **PR-3 carries the geometry/association dedup** because the dedup only becomes *legal* once the importers are in research — sequencing it earlier would force a forbidden `signals → research` edge.
5. **PR-5 / PR-6 after construction:** assembly artifacts and traceability reference the registry; moving them after the registry's home is settled avoids repointing twice.
6. **PR-7 last (shims + delete + contracts):** shims must outlive every importer move; the `.importlinter` rewrite and `signals/` deletion are only safe once nothing references the old paths. This is the green-gate finale.

This order minimizes: **import breakage** (shims + contract-first), **cycle formation** (each entanglement dissolved in its own atomic PR), **test churn** (each module repointed once, not twice), **cross-layer contamination** (construction leaves governance in PR-3, so governance is decision-only from that point forward).

---

## 5. Final Execution Checklist

| Step | git-mv group (intent) | Validation scope | Rollback trigger |
|---|---|---|---|
| **PR-1** | (no move) dedup vocab → `domain/signal_layers.py` | `pytest -q -k "semantics or registry_contract or assembly"` then full | any registry/semantics test red |
| **PR-2** | contract trio → `domain/registry/` + shims | full `pytest` + `lint-imports` | any contract/loader/lifecycle test red, or lint-imports broken |
| **PR-3** | construction → `research/registry/`; sections+semantics out of `model/governance`; geometry/association dedup | **full `pytest`** (dynamic-edge net) + `mypy` + `lint-imports` | any build/relationship/redundancy test red; mypy regressions |
| **PR-4** | extract `model/governance/promote.py` | `pytest -q -k "parity or lifecycle or promotion or consumer_alignment"` then full | parity test drift > tolerance, or gate test red |
| **PR-5** | SYNTH → `model/assemble/`; weights → `intelligence/`; repoint writer+readers | full `pytest` | composite-key or consumer-alignment test red |
| **PR-6** | traceability → `model/governance/` (generated) | `pytest -q -k "metadata or weekly or snapshot"` then full | provenance/snapshot test red |
| **PR-7** | rm shims; `git rm signals/`; rewrite `.importlinter`; flip guard tests; docs | full `pytest` + `lint-imports` (N kept, 0 broken) + `ruff` | any guard test red, lint-imports broken, or residual `signals.*` import found |

Repo-green gate after **every** PR: `ruff check . && uv run mypy --config-file pyproject.toml && uv run lint-imports && python -m pytest -q`.

---

## 6. Test Traceability

Every move is guarded by an existing test; no PR relies on a test it also writes. Mapping (responsibility → guarding test):

| Responsibility moved | Guarding test(s) | PR |
|---|---|---|
| signal-layer semantics | `test_registry_semantics` | 1 |
| registry contract/loader | `test_registry_contract`, `test_runtime_consumer_alignment` | 2 |
| lifecycle gate | `test_registry_lifecycle` | 2, 4 |
| section computation / geometry | `test_relationship_computation`, `test_relationship_geometry` | 3 |
| registry assembly | `test_registry_assembly`, `test_registry_build_parity` | 3, 4 |
| redundancy/stability kernels | `test_signals_redundancy`, `test_signals_stability` | 3 |
| promotion/publication | `test_registry_promotion`, `test_registry_build_parity` | 4 |
| SYNTH/weights | `test_composite_key_migration`, `test_runtime_metadata_propagation` | 5 |
| traceability/provenance | `test_spine_traversal_metadata`, `test_weekly_*` | 6 |
| layer boundaries | `test_dal_architecture`, `test_intelligence_outputs`, `test_downstream_governance` | 7 |

**Gap flagged (not a blocker):** the 4 production lenses lack study-logic tests (see `project-research-layer-redesign` memory); the registry-build parity test (`test_registry_build_parity`) is the primary correctness anchor for PR-3/PR-4 and is **integration-gated** (skips without a live DB) — CI must run it against the fixture DB, or PR-3/PR-4 lose their main net. Confirm fixture coverage before PR-3.

---

## 7. Out of scope (explicit)

- **`intelligence → serve` rename** — separate deferred effort (29 importers). Module weights land in `intelligence/` and ride that rename later. This plan does not touch it.
- **G-EDA*/LENS-* code retirement** — superseded/optional doc-hygiene; unrelated.
- **Full-season study re-open** — separate analytical effort.
- No new layers, no `production/` bucket, no ownership changes. Construction is research; governance promotes.
</content>
