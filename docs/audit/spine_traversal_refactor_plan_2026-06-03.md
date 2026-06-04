# Spine Traversal Refactor Plan

**Date:** 2026-06-03  
**Scope:** Diff-level refactor plan for improving navigability and deterministic traversal across the analytical spine.  
**Status:** Implemented through Phase 5. No runtime behavior changes.

**Revision note:** Phase 1 was adjusted during execution. Do not add `finding_key` or
`analysis_path` fields to `dal/feat/feat_schema.py::FeatureRecord`; that would make the DAL
own downstream finding pointers. Use `signals/characterisation/signal_traceability.yaml` as the
routing bridge instead, with a single `analysis_paths` map and tests that derive finding keys
from existing traceability fields.

## Constraints

- No new architecture layers.
- No new conceptual models.
- No renaming unless it removes ambiguity.
- No duplication of existing metadata.
- No rewrite of ADLC, system-model, or ontology.
- No big-bang refactors.
- No cross-folder restructuring unless required for correctness.
- Prefer adding fields over moving files.
- Prefer linking over duplicating.
- Prefer narrowing ambiguity over expanding scope.

## Phase 0: Validation / Prep

### Step 0.1

**Target file(s):**

- `signals/governance/evaluation_metadata.yaml`
- `signals/governance/synth01_decisions.yaml`
- `signals/governance/weight_registry.yaml`
- `dal/feat/feat_schema.py`

**Change type:** ADD

**Exact patch description:**

Add no production code. Add a validation test only:

Target file: `tests/test_spine_traversal_metadata.py`

```diff
+ def test_feature_registry_gate_values_are_non_empty():
+     for feature, record in FEATURE_REGISTRY.items():
+         assert record.gate
+
+ def test_weight_registry_signal_ids_resolve_when_present():
+     for module in weight_registry["modules"].values():
+         for entry in module["weights"].values():
+             if entry.get("signal_id") is not None:
+                 assert get_signal_governance_by_key(entry["signal_id"])
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: tests only
- Rollback safe: YES
- Runtime affected: NO

**Traversal validation after phase:** PARTIAL. Existing explicit `signal_id` values can be checked, but `signal_id: null` components still break deterministic Decision -> Finding traversal.

## Phase 1: Metadata Alignment

### Step 1.1

**Target file(s):**

- `dal/feat/feat_schema.py`

**Change type:** MODIFY

**Exact patch description:**

Extend `FeatureRecord` with explicit routing fields. Do not remove existing `gate`.

```diff
  class FeatureRecord:
      gate: str
+     finding_key: str | None = field(default=None)
+     analysis_path: str | None = field(default=None)
      scope: str
      positions: list[str]
      status: str
```

Populate only governed features with known mappings:

```diff
  "xgi_roll3": FeatureRecord(
      gate="LENS-FORM FORM-001",
+     finding_key="xgi_roll3@form:total_points",
+     analysis_path="studies/lenses/form/study.py",
```

```diff
  "xgi_roll5": FeatureRecord(
      gate="LENS-FORM FORM-002",
+     finding_key="xgi_roll5@form:total_points",
+     analysis_path="studies/lenses/form/study.py",
```

```diff
  "minutes_roll3": FeatureRecord(
      gate="LENS-AVAIL AVAIL-001",
+     finding_key="minutes_roll3@avail:played_next_gw",
+     analysis_path="studies/lenses/avail/study.py",
```

```diff
  "minutes_roll5": FeatureRecord(
      gate="LENS-AVAIL AVAIL-002",
+     finding_key="minutes_roll5@avail:played_next_gw",
+     analysis_path="studies/lenses/avail/study.py",
```

```diff
  "minutes_roll8": FeatureRecord(
      gate="LENS-AVAIL AVAIL-003",
+     finding_key="minutes_roll8@avail:played_next_gw",
+     analysis_path="studies/lenses/avail/study.py",
```

For conditional/pre-lens features:

```diff
+     finding_key=None,
+     analysis_path=None,
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: any code constructing `FeatureRecord`; currently local registry only
- Rollback safe: YES
- Runtime affected: NO, if defaults are used and no validation enforces non-null yet

### Step 1.2

**Target file(s):**

- `tests/test_spine_traversal_metadata.py`

**Change type:** MODIFY

**Exact patch description:**

```diff
+ def test_approved_feature_records_have_routing_metadata():
+     for feature, record in FEATURE_REGISTRY.items():
+         if record.status == "APPROVED":
+             assert record.finding_key is not None, feature
+             assert record.analysis_path is not None, feature
```

**Dependency safety check:**

- Upstream dependencies impacted: `FEATURE_REGISTRY` metadata only
- Downstream dependencies impacted: tests only
- Rollback safe: YES
- Runtime affected: NO

**Traversal validation after phase:** PARTIAL. Feature -> Analysis -> Finding is deterministic for approved feature columns. Finding -> Decision still breaks for decision components with `signal_id: null`.

## Phase 2: Routing Determinism

### Step 2.1

**Target file(s):**

- `signals/governance/weight_registry.yaml`

**Change type:** MODIFY

**Exact patch description:**

For every decision weight with `signal_id: null`, add `derived_from`. Do not invent findings.

```diff
      fixture_score:
        value: 0.20
        signal: fixture_context
        signal_id: null
+       derived_from:
+         - fixture_context
```

```diff
      consistency_score:
        value: 0.20
        signal: xgi_roll3_vs_xgi_roll5_divergence
        signal_id: null
+       derived_from:
+         - xgi_roll3@form:total_points
+         - xgi_roll5@form:total_points
```

```diff
      team_attack_score:
        value: 0.35
        signal: goals_scored
        signal_id: null
+       derived_from:
+         - goals_scored
```

```diff
      dgw_bonus_score:
        value: 0.25
        signal: fixture_context
        signal_id: null
+       derived_from:
+         - fixture_context
```

```diff
      form_momentum_score:
        value: 0.25
        signal: xgi_roll3_minus_xgi_roll5
        signal_id: null
+       derived_from:
+         - xgi_roll3@form:total_points
+         - xgi_roll5@form:total_points
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: metadata readers only; existing loader ignores unknown fields
- Rollback safe: YES
- Runtime affected: NO

### Step 2.2

**Target file(s):**

- `tests/test_spine_traversal_metadata.py`

**Change type:** MODIFY

**Exact patch description:**

```diff
+ def test_weight_entries_have_signal_id_or_derived_from():
+     for module_name, module in weight_registry["modules"].items():
+         for weight_name, entry in module["weights"].items():
+             assert entry.get("signal_id") is not None or entry.get("derived_from"), (
+                 module_name,
+                 weight_name,
+             )
```

**Dependency safety check:**

- Upstream dependencies impacted: `weight_registry.yaml` metadata
- Downstream dependencies impacted: tests only
- Rollback safe: YES
- Runtime affected: NO

**Traversal validation after phase:** PARTIAL, close to deterministic. Decision -> upstream feature/finding is explicit, but `derived_from` may point to raw/governed feature names instead of resolvable finding keys for editorial components.

## Phase 3: Duplication Removal

### Step 3.1

**Target file(s):**

- `docs/foundations/representation-rules.md`

**Change type:** MODIFY

**Exact patch description:**

Remove stale `_COLUMN_META` authority reference.

```diff
- All STATE columns must carry `_COLUMN_META` with `scope`, `temporal_type`, `causality`, `behavioral_reason`, `source_gate_decisions`, and `leakage_risk` (where applicable) per governance §7.
+ All STATE columns must be registered in `dal/feat/feat_schema.py::FEATURE_REGISTRY` with scope, causality, approval status, routing metadata, and the gate/finding reference where applicable.
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: docs only
- Rollback safe: YES
- Runtime affected: NO

### Step 3.2

**Target file(s):**

- `docs/architecture/analytical-architecture.md`

**Change type:** MODIFY

**Exact patch description:**

Narrow “findings live in four artifacts” into a routing rule. Keep the same artifacts.

```diff
- Findings are durable but spread across four artifacts by kind. Pointers only — read the artifact
- for content:
+ Findings are routed by kind. Use this order; do not choose between artifacts ad hoc:
```

```diff
+ 1. Lens verdict for `signal@lens:target[#POS]` -> `signals/governance/evaluation_metadata.yaml`
+ 2. Synthesis/composition verdict for position-scoped weights -> `signals/governance/synth01_decisions.yaml`
+ 3. Narrative verdict slug for human-readable decision history -> `docs/decisions/`
+ 4. EDA gate finding only when no lens verdict exists yet -> `studies/eda/findings/`
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: docs only
- Rollback safe: YES
- Runtime affected: NO

**Traversal validation after phase:** PARTIAL. Artifact priority is now deterministic in docs. Runtime metadata is deterministic for approved features and declared decisions. Remaining break: some editorial `derived_from` entries are traceable but not governed findings.

## Phase 4: Navigation Clarity

**Status:** DONE. Implemented with the traceability routing bridge from the revision note.

### Step 4.1

**Target file(s):**

- `docs/navigation-map.md`

**Change type:** ADD

**Exact patch description:**

Add one short traversal section after “Quick orientation”.

```diff
+ ## Spine traversal
+
+ To trace a feature to a decision:
+
+ 1. Start with `dal/feat/feat_schema.py::FEATURE_REGISTRY` for feature status and approved positions.
+ 2. Resolve the feature and position in `signals/characterisation/signal_traceability.yaml`.
+ 3. Use `analysis_paths` for the study/lens implementation.
+ 4. Derive the finding key as `signal@lens:target[#POS]` and resolve the verdict in `signals/governance/evaluation_metadata.yaml`.
+ 5. Search that key in `signals/governance/synth01_decisions.yaml` for composition decisions.
+ 6. Search that key or listed `derived_from` values in `signals/governance/weight_registry.yaml` for intelligence usage.
+
+ If a feature has no evaluated traceability route, treat it as conditional/pre-lens and do not assume it is operationally governed.
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: docs only
- Rollback safe: YES
- Runtime affected: NO

### Step 4.2

**Target file(s):**

- `docs/architecture/analytical-architecture.md`

**Change type:** MODIFY

**Exact patch description:**

Patch the Feature and Decision rows only.

```diff
- [representation-rules.md], [representation-governance.md], [feat_schema.py] `FEATURE_REGISTRY`
+ [feat_schema.py] `FEATURE_REGISTRY` for column status; [signal_traceability.yaml] for finding routing; [representation-rules.md] and [representation-governance.md] for admissibility rules
```

```diff
- Part governed, part editorial
+ Governed where `signal_id` resolves; editorial where registry marks `PROVISIONAL-EDITORIAL` and uses `derived_from`
```

**Dependency safety check:**

- Upstream dependencies impacted: none
- Downstream dependencies impacted: docs only
- Rollback safe: YES
- Runtime affected: NO

**Traversal validation after phase:** YES for approved feature columns that have traceability routes. PARTIAL for editorial decision composites, because they are traceable but intentionally not governed findings.

## Phase 5: Optional Cleanup

**Status:** DONE. `derived_from` is structured as `features` plus `findings`, and tests enforce the shape.

### Step 5.1

**Target file(s):**

- `signals/governance/weight_registry.yaml`

**Change type:** MODIFY

**Exact patch description:**

Normalize `derived_from` values to distinguish governed findings from raw features.

```diff
- derived_from:
-   - fixture_context
+ derived_from:
+   features:
+     - fixture_context
+   findings: []
```

```diff
- derived_from:
-   - xgi_roll3@form:total_points
-   - xgi_roll5@form:total_points
+ derived_from:
+   features:
+     - xgi_roll3
+     - xgi_roll5
+   findings:
+     - xgi_roll3@form:total_points
+     - xgi_roll5@form:total_points
```

**Dependency safety check:**

- Upstream dependencies impacted: `weight_registry.yaml` metadata shape
- Downstream dependencies impacted: tests added in this plan
- Rollback safe: YES
- Runtime affected: NO, unless code starts parsing `derived_from`

### Step 5.2

**Target file(s):**

- `tests/test_spine_traversal_metadata.py`

**Change type:** MODIFY

**Exact patch description:**

```diff
- assert entry.get("signal_id") is not None or entry.get("derived_from")
+ derived = entry.get("derived_from")
+ assert entry.get("signal_id") is not None or derived
+ if derived:
+     assert "features" in derived
+     assert "findings" in derived
```

**Dependency safety check:**

- Upstream dependencies impacted: `weight_registry.yaml` metadata shape
- Downstream dependencies impacted: tests only
- Rollback safe: YES
- Runtime affected: NO

**Traversal validation after phase:** YES for governed Feature -> Analysis -> Finding -> Decision traversal. PARTIAL only where the system is intentionally editorial/provisional; those paths become explicit as feature-derived, not falsely governed.

## Excluded Changes

- No folder moves.
- No ontology rewrite.
- No ADLC rewrite.
- No system-model rewrite.
- No new governance layer.
- No runtime behavior change.
- No decision-weight recalibration.
- No deletion of historical decision artifacts.
