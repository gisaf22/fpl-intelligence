# Analytical Architecture Audit — fpl-intelligence

**Date:** 2026-06-01
**Auditor role:** Analytical Systems Auditor — Code-Truth Bound, Non-Designing
**Epistemic rule:** Docs declare intended design. Code defines actual behavior. Divergence is a finding.
**Scope:** Correctness, traceability, evaluation integrity, governance consistency, absence of silent analytical errors.
**Status:** Complete. 7 findings. 3 Critical/High requiring code or YAML changes; 4 Medium/Low requiring doc-only corrections.

---

## 1. Executive Summary

The platform architecture is substantially sound. The 4-layer import hierarchy (DAL → studies → signals → intelligence) is respected by studies and signals. The domain layer (`domain/fpl_scoring.py`) and population layer (`population/populations.py`) are implemented correctly and consumed by the appropriate modules. Governance gates (lifecycle, scoring selector, FWD scope guards, availability positional guards) are all implemented in code as documented.

Seven findings are confirmed, none of which affect day-one correctness of the scoring outputs. The most analytically significant finding is that `signal_traceability.yaml` has not been updated to reflect SYNTH-01 decisions: 14 signal-position pairs have stale `lifecycle_state: candidate` values when their authoritative state in `evaluation_metadata.yaml` is `approved` or `excluded`. This creates a silent divergence between the machine-readable governance YAML and the completed study record. The most operationally significant finding is that `intelligence_contracts.py` imports directly from `dal.feat`, a forbidden sub-layer boundary crossing per `layer-boundaries.md`.

Two intelligence modules (`value.py`, `transfers.py`) are missing the MID xgi_roll3 scope guard that captain.py correctly implements following G-SYNTH1-07. This is a silent analytical error: xgi_roll3 is scored at MID in those modules despite being `excluded` there by SYNTH-01.

The remaining findings are documentation staleness (stale file paths, stale status labels in governance docs) that create navigability and maintenance risk but no runtime errors.

No findings contradict or re-open completed study decisions.

---

## 2. Layer Map — Actual System

The following map reflects actual code, not documentation.

```
fpl.db (source data, populated by fpl-ingest)
    |
dal/                 — deterministic (player_id, gw) spine
    staging/         — column rename, type cast, null standardisation
    intermediate/    — join staging into fixture-grain records
    fct/             — aggregate fixture-grain to gameweek-grain
    feat/            — rolling windows, lag features, trend signals
    mart/            — filter to cutoff GW, add position label; governed public API
    |
    |--- (canonical entry: dal.pipeline.run() / dal.pipeline.load())
    |
studies/             — analytical methodology: EDA, lenses, kernels, synthesis
    eda/             — one-time dataset characterisation; closed
    lenses/          — per-signal-group characterisation (FORM, AVAIL, MARKET, FIXTURE-GW)
    kernels/         — domain-agnostic statistical utilities
    synthesis/       — SYNTH-01 signal combination study
    experiments/     — backtesting and population experiments
    operational/     — phase backtest
    |
signals/             — lifecycle governance and registry build pipeline
    characterisation/ — population builder, signal traceability YAML, weight registry
    governance/      — evaluation metadata, lifecycle gate, schema, registry loader
    |
domain/              — FPL game rules as typed importable constants (fpl_scoring.py)
population/          — named analytical populations (filter_performance, filter_participation)
    |
intelligence/        — operational scoring and weekly reporting
    captain.py       — captaincy ranking
    value.py         — value player ranking
    transfers.py     — transfer target ranking
    fixtures.py      — fixture opportunity ranking
    availability.py  — availability risk classification
    scoring/         — scoring engine, signal selector, renderer
    intelligence_contracts.py  — shared validation and normalization utilities
```

**Layer dependency direction observed in code:**
- `studies/` imports only from `dal.pipeline`, `dal.config` — compliant
- `signals/` imports from `dal.mart` (mart public API) — compliant
- `intelligence/` imports from `dal.feat.feat_schema` (sub-layer, VIOLATION — see Finding F-02)
- `domain/` and `population/` are cross-cutting modules; consumed by signals, intelligence, and population builder

**Modules not importing from upper layers (correctly isolated):**
- `dal/` — no imports from studies, signals, or intelligence
- `studies/eda/` — signal constants inlined, not imported (compliant; comment-noted in code)
- `studies/kernels/` — no governance imports (compliant per layer-boundaries.md)

---

## 3. Layer-by-Layer Findings

### DAL Layer

**Status: Compliant.** Public API (`dal.pipeline.run()`, `dal.pipeline.load()`, `dal.mart.*`) is correctly bounded. Internal sub-layers (`dal.feat`, `dal.fct`, `dal.staging`, `dal.intermediate`) are not imported by any layer except one (see F-02 below).

`POSITION_CODE_MAP` exported from `dal.mart.__init__` is consumed by `signals/characterisation/population_builder.py` and `intelligence/scoring/engine.py`. Both are permitted consumers of the mart public API.

### Studies Layer

**Status: Compliant.** All study files import only from `dal.pipeline`, `dal.config`, or `studies.kernels`. No imports from `signals.*` or `intelligence.*` in any study module. `studies/eda/geometry.py` and `studies/eda/semantics.py` inline schema constants from `signals.governance.schema` rather than importing them — this is correctly noted in comments and is compliant.

### Signals Layer

**Status: One documentation finding (F-05, F-06).** The layer itself is structurally correct. `signals/characterisation/population_builder.py` imports from `dal.mart` (mart public API, not a sub-layer). Lifecycle gate (`assert_operational_safe()`) is implemented and wired. `evaluation_metadata.yaml` reflects full post-SYNTH-01 state. `signal_traceability.yaml` is stale — see F-01.

### Domain and Population Layers

**Status: Compliant.** `domain/fpl_scoring.py` defines FPL scoring constants with VERIFIED/UNVERIFIED annotations. `population/populations.py` implements `filter_performance` (minutes >= CLEAN_SHEET_MIN_MINUTES) and `filter_participation` (minutes >= APPEARANCE_MIN_MINUTES) with correct derivation from domain constants. Consumed correctly by population_builder.py and referenced by availability.py.

### Intelligence Layer

**Status: Two code findings (F-02, F-03).** Scope guards and eligibility gates are implemented. Weights are loaded dynamically from the YAML registry. No hardcoded weights in scoring modules. The MID scope guard for xgi_roll3 (G-SYNTH1-07) is present in captain.py but absent from value.py and transfers.py.

---

## 4. Cross-Layer Violations

### V-01: intelligence_contracts.py imports from dal.feat sub-layer

**File:** `intelligence/intelligence_contracts.py:13`
**Code:** `from dal.feat.feat_schema import FEATURE_REGISTRY`
**Rule violated:** `docs/architecture/layer-boundaries.md §Key boundary rules`: "Direct imports from `dal.staging`, `dal.intermediate`, `dal.fct`, or `dal.feat` are forbidden outside the DAL."
**Effect:** `_REQUIRED_STATE_COLS` is derived from `FEATURE_REGISTRY.keys()`. Any change to `dal.feat.feat_schema` (an internal DAL concern) now propagates directly to intelligence-layer validation. The mart public API already governs what state columns are available; this import couples intelligence to DAL internals unnecessarily.
**Severity:** High

### V-02: signal_traceability.yaml lifecycle states not updated post-SYNTH-01

**File:** `signals/characterisation/signal_traceability.yaml`
**Authority:** `signals/governance/evaluation_metadata.yaml`
**Details:** 14 signal-position pairs have `lifecycle_state: candidate` in signal_traceability.yaml. Their authoritative state in evaluation_metadata.yaml (per the SYNTH-01 `per_position` decisions) is:

| Signal | Position | traceability.yaml | evaluation_metadata.yaml |
|--------|----------|-------------------|--------------------------|
| xgi_roll3 | DEF | candidate | approved |
| xgi_roll3 | MID | candidate | excluded (G-SYNTH1-07) |
| xgi_roll5 | DEF | candidate | approved |
| xgi_roll5 | MID | candidate | approved |
| minutes_roll3 | MID | candidate | approved |
| minutes_roll5 | MID | candidate | excluded (G-SYNTH1-10) |
| minutes_roll8 | DEF | candidate | approved |
| minutes_roll8 | MID | candidate | approved |
| transfers_in | DEF | candidate | approved |
| transfers_in | MID | candidate | approved |
| ownership_count | DEF | candidate | excluded (G-SYNTH1-05) |
| ownership_count | MID | candidate | approved |
| purchase_price | DEF | candidate | approved |
| purchase_price | FWD | candidate | excluded (G-SYNTH1-14) |

The signal_traceability.yaml schema does not have a `synth01_decision` field. Any governance tool or review that reads lifecycle state from signal_traceability.yaml rather than evaluation_metadata.yaml will see pre-SYNTH-01 state.

The most operationally significant discrepancy: xgi_roll3@MID shows `lifecycle_state: candidate` in the traceability YAML, while the authoritative record in evaluation_metadata.yaml shows `lifecycle_state: excluded, synth01_decision: EXCLUDED-REDUNDANT` (G-SYNTH1-07). This means the machine-readable document that exists to surface the MID exclusion does not surface it.

The signal_traceability.yaml also has no `synth01_decision`, `composition_weight`, or `composition_role` fields for any entry — SYNTH-01 outcome data exists only in evaluation_metadata.yaml.

**Severity:** Critical

### V-03: value.py and transfers.py missing MID xgi_roll3 scope guard (G-SYNTH1-07)

**Files:** `intelligence/value.py:114–116`, `intelligence/transfers.py:107–109`
**Governance decision:** evaluation_metadata.yaml xgi_roll3@MID `synth01_decision: EXCLUDED-REDUNDANT` (G-SYNTH1-07), `lifecycle_state: excluded`.
**captain.py status:** Guard is correctly implemented. Lines 102–105:
```python
fwd_mask = eligible["position_label"] == "FWD"
mid_mask = eligible["position_label"] == "MID"
eligible["_xgi_roll5_scored"] = eligible["xgi_roll5"].where(~fwd_mask, 0.0)
eligible["_xgi_roll3_scored"] = eligible["xgi_roll3"].where(~(fwd_mask | mid_mask), 0.0)
```
**value.py and transfers.py status:** Only `fwd_mask` is applied. xgi_roll3 is scored at MID with full values.

In value.py: xgi_roll3@MID contributes to `form_score` (30% weight) and to `_consistency_raw` which drives `consistency_score` (20% weight). Combined, xgi_roll3@MID contributes to approximately 50% of value_score for MID players despite being excluded at MID by SYNTH-01.

In transfers.py: xgi_roll3@MID drives both `recent_form_score` (30% weight) and `involvement_score` (15% weight) — a total of 45% of transfer_score for MID players.

This is a silent scoring error, not a runtime error. MID players will be differentiated by a signal whose contribution at that position was evaluated and rejected.

The signal-traceability-matrix.md Consumer Module Map entry for value.py and transfers.py does not flag the missing MID guard. The captain.py section correctly documents the violation and flags GAP-TRACE-09 as resolved, but no corresponding GAP-TRACE entry exists for value.py and transfers.py.

**Severity:** High

---

## 5. Analytical Risk Register

| ID | Finding | Severity | File(s) | Behavioral Impact |
|----|---------|----------|---------|-------------------|
| F-01 | signal_traceability.yaml: 14 lifecycle states pre-SYNTH-01 (all `candidate`; should include `approved`/`excluded`) | Critical | `signals/characterisation/signal_traceability.yaml` | Machine-readable governance YAML misrepresents SYNTH-01 outcomes; xgi_roll3@MID appears eligible when excluded |
| F-02 | intelligence_contracts.py imports `dal.feat.feat_schema` — forbidden sub-layer boundary crossing | High | `intelligence/intelligence_contracts.py:13` | Couples intelligence-layer validation to DAL internal schema; change to FEATURE_REGISTRY silently alters runtime column requirements |
| F-03 | value.py and transfers.py missing MID guard for xgi_roll3 (G-SYNTH1-07 EXCLUDED-REDUNDANT) | High | `intelligence/value.py:116`, `intelligence/transfers.py:108` | xgi_roll3 scored at MID in value.py (~50% influence) and transfers.py (45% influence) despite SYNTH-01 exclusion; MID rankings silently differentiated by excluded signal |
| F-04 | signal-traceability-matrix.md §intelligence/scoring/signals.py: references non-existent file, marks SCORE-T-01 `CONTRADICTS-GATE` when it is `RESOLVED` | Medium | `docs/governance/signal-traceability-matrix.md:285–298` | Doc states an active analytical conflict that no longer exists; misleads future reviewers |
| F-05 | signal-traceability-matrix.md GAP-TRACE-09 marked OPEN; captain.py has the fix | Medium | `docs/governance/signal-traceability-matrix.md:314` | Open gap register item that is actually closed; creates false maintenance debt in governance doc |
| F-06 | layer-boundaries.md: stale directory names throughout — `signals/lifecycle/`, `signals/registry/`, `signals/evaluation/`, `intelligence/_base.py` | Low | `docs/architecture/layer-boundaries.md:67,77–85,100,120–122,136` | Authoritative boundary document references directories that do not exist; navigability and onboarding risk |
| F-07 | threshold-registry.md REG-T-01 references `signals/registry/population.py:13` — stale path | Low | `docs/governance/threshold-registry.md:148` | Threshold entry points to a file that does not exist (path renamed; MINUTES_THRESHOLD constant also removed) |

---

## 6. Minimal Fix Plan

This section lists the minimum changes required to close each Critical and High finding. No finding in this section requires a new module, a new architectural layer, or a new governance mechanism. Low/Medium findings are documentation corrections only.

### Fix F-01 — Update signal_traceability.yaml lifecycle states (Critical)

**What to change:** For each of the 14 discrepant entries in `signals/characterisation/signal_traceability.yaml`, update `lifecycle_state` and `downstream_status` to match the authoritative values in `signals/governance/evaluation_metadata.yaml`. Add `synth01_decision` and `synth01_decision_id` fields to the YAML schema and populate them from `evaluation_metadata.yaml`.

The minimum required updates to prevent the most harmful stale state are:
- xgi_roll3@MID: `lifecycle_state: excluded`, `downstream_status: blocked`, `synth01_decision: EXCLUDED-REDUNDANT`, `synth01_decision_id: G-SYNTH1-07`
- xgi_roll5@MID: `lifecycle_state: excluded`, `downstream_status: blocked`, `synth01_decision: EXCLUDED-REDUNDANT`, `synth01_decision_id: G-SYNTH1-10`
- ownership_count@DEF: `lifecycle_state: excluded`, `downstream_status: blocked`, `synth01_decision: EXCLUDED-REDUNDANT`, `synth01_decision_id: G-SYNTH1-05`
- purchase_price@FWD: `lifecycle_state: excluded`, `downstream_status: blocked`, `synth01_decision: FWD-SINGLE-SIGNAL`, `synth01_decision_id: G-SYNTH1-14`
- All 10 remaining discrepancies: update `lifecycle_state` from `candidate` to `approved` and `downstream_status` from `eligible`/`caveated` to `approved`.

Also update `consumer_modules` for xgi_roll3@MID to note the zeroing guard is present only in captain.py and missing in value.py and transfers.py.

**Files:** `signals/characterisation/signal_traceability.yaml`

### Fix F-02 — Remove forbidden dal.feat import from intelligence_contracts.py (High)

**What to change:** Replace the `from dal.feat.feat_schema import FEATURE_REGISTRY` import and its derived `_REQUIRED_STATE_COLS` with an explicit frozenset of the required column names at the call site.

The current code at line 13–17:
```python
from dal.feat.feat_schema import FEATURE_REGISTRY
_REQUIRED_STATE_COLS: frozenset[str] = frozenset(FEATURE_REGISTRY.keys())
```

The replacement is a hardcoded frozenset of the 13 feature column names that FEATURE_REGISTRY currently defines. These columns are the governed mart contract — they belong in the mart's public API, not in an internal schema import. If the mart's public API exports a constant enumerating its governed feature columns, use that. If it does not, define the frozenset explicitly in intelligence_contracts.py with a comment referencing `dal/mart/__init__.py:GOVERNED_SIGNAL_COLUMNS` as the source of truth.

**Files:** `intelligence/intelligence_contracts.py`

### Fix F-03 — Add MID xgi_roll3 scope guard to value.py and transfers.py (High)

**value.py:** At line 114, change the scope guard from FWD-only to FWD+MID for xgi_roll3. The pattern to follow is captain.py lines 102–105. Specifically, line 116 currently reads:
```python
xgi_roll3_scored = eligible["xgi_roll3"].fillna(0).where(~fwd_mask, 0.0)
```
It must be changed to:
```python
mid_mask = eligible["position_label"] == "MID"
xgi_roll3_scored = eligible["xgi_roll3"].fillna(0).where(~(fwd_mask | mid_mask), 0.0)
```
This guard must also be applied to the consistency calculation: `_consistency_raw` at line 123 uses `xgi_roll3_scored` as an operand, so it will be corrected automatically by fixing the guard at line 116. Add a module-level comment documenting the MID guard and citing G-SYNTH1-07 (matching the comment style in captain.py lines 99–101).

**transfers.py:** At line 107, the guard is:
```python
fwd_mask = eligible["position_label"] == "FWD"
xgi_roll3_scored = eligible["xgi_roll3"].fillna(0).where(~fwd_mask, 0.0)
```
It must be changed to include MID. Because `involvement_score` and `recent_form_score` both call `normalize_within_position(eligible, "_xgi_roll3_scored")` from the same source column (lines 123, 132), correcting the source mask at line 108 corrects both scores automatically.

**Files:** `intelligence/value.py`, `intelligence/transfers.py`

### Fix F-04 — Update signal-traceability-matrix.md scoring module section (Medium)

**What to change:**
1. Rename the `### intelligence/scoring/signals.py` section heading to `### intelligence/scoring/signal_selector.py` — the file was renamed and the old name does not exist.
2. Replace the SCORE-T-01 row that marks the constant as `CONTRADICTS-GATE` with a note that SCORE-T-01 was `RESOLVED` (Phase 8, G-OPS-02) and MIN_RHO was removed. Reference the threshold-registry.md entry.
3. Remove or update the "Resolution is blocked until SYNTH-01" caveat — SYNTH-01 is complete and all three affected signals received APPROVED decisions.

**Files:** `docs/governance/signal-traceability-matrix.md:285–298`

### Fix F-05 — Close GAP-TRACE-09 in signal-traceability-matrix.md (Medium)

**What to change:** Change GAP-TRACE-09 status from OPEN to RESOLVED with a date. The current text at line 314 reads:
```
| GAP-TRACE-09 | xgi_roll3 consumed at MID in captain.py ... | captain.py | **OPEN** — fix: add `mid_mask` ...
```

The fix described in GAP-TRACE-09 is present in captain.py. The entry should be marked RESOLVED for captain.py. However, the fix is absent from value.py and transfers.py (F-03 above). The GAP-TRACE entry should be updated to note that captain.py is resolved and to open a new GAP-TRACE-10 for value.py and transfers.py, or expand GAP-TRACE-09 to cover all three modules.

This correction is dependent on F-03 being fixed. If F-03 is fixed first, GAP-TRACE-09 may be marked fully RESOLVED for all three modules simultaneously.

**Files:** `docs/governance/signal-traceability-matrix.md:314`

### Fix F-06 — Update stale directory names in layer-boundaries.md (Low)

**What to change:** Update all references from the renamed directories:
- `signals/lifecycle/` → `signals/governance/`
- `signals/registry/` → `signals/characterisation/` (for the population and registry build artifacts) or `signals/governance/` (for lifecycle enforcement)
- `signals/evaluation/` → `signals/governance/` (evaluation_metadata.yaml lives there)
- `signals/lifecycle/lifecycle.py:assert_operational_safe()` → `signals/governance/lifecycle.py:assert_operational_safe()`
- `signals/registry/runner.py` → check actual runner file location and update reference
- `intelligence/_base.py` → `intelligence/intelligence_contracts.py`
- `signals/registry/SIGNAL_REGISTRY.md` → update to actual location if file exists, or remove if deleted

**Files:** `docs/architecture/layer-boundaries.md`

### Fix F-07 — Update REG-T-01 file path in threshold-registry.md (Low)

**What to change:** The REG-T-01 entry at line 148 references `signals/registry/population.py:13`. The actual file is `signals/characterisation/population.py`. Additionally, MINUTES_THRESHOLD has been removed from that file (replaced by import of CLEAN_SHEET_MIN_MINUTES from domain.fpl_scoring). Update the entry to reference the current module path and note that the constant was replaced by the domain layer constant. Mark the disposition as reflecting the population layer change.

**Files:** `docs/governance/threshold-registry.md:142–152`

---

## 7. Non-Recommendations

The following items were examined and are explicitly not flagged as findings, per the audit scope constraints.

**PENDING-EVAL-01/02/03 (consistency_score, team_goals_roll5, form_momentum_score):** These are novel metrics in production with EVALUATION-DEFERRED status, tracked in `docs/governance/pending-evaluation-register.md`. They are not findings in this audit. Their analytical risk is documented and their governance status is known.

**GK position signals:** GK signals are excluded by ontological design (G-EDA3-01). Not re-examined.

**Change 3 (population_threshold_study.py):** Deferred to 2026/27 calibration program per `platform-evaluation-2026.md`. Not a finding.

**SYNTH-01 composition decisions (G-SYNTH1-* gates):** All G-SYNTH1-* decisions are final. The audit confirms the decisions are recorded in evaluation_metadata.yaml. The audit does not re-evaluate them.

**GAP-TRACE-04 and GAP-TRACE-05** (transfers_in/ownership_count and 12 defensive signals not yet consumed): These are Phase 6 post-SYNTH-01 items. No current module claims to consume them. Not findings.

**FWD×purchase_price decay (MARKET-T-01):** Signal excluded from scoring pending SYNTH-02 phase-conditional evaluation. Exclusion is correctly recorded. Not a finding.

**9 EVALUATION-DEFERRED thresholds** (AVAIL-T-01/02/03, CAPT-T-01, VAL-T-01, TRANS-T-01, FIX-T-01, REG-T-01, STATE-T-01): All classified and carrying to 2026/27 calibration. Their deferred status is the intended state.

**weight_registry.yaml PROVISIONAL-EDITORIAL provenance:** All four modules carry this provenance. This is a known, documented status. Not a finding.

**import-linter not installed:** No import-linter is configured in pyproject.toml. Layer boundary enforcement is via runtime tests. This is the actual configuration; the absence of import-linter is not a violation of any documented constraint.

**studies/eda inlining signals.governance.schema constants:** `studies/eda/geometry.py` and `studies/eda/semantics.py` inline constants rather than importing from `signals.governance.schema`. This is correct; layer-boundaries.md §Studies prohibits importing from `signals.*`.

---

## 8. Out-of-Scope Confirmations

The following areas were inspected and confirmed clean. No action required.

**Layer isolation — studies:** All lens study files (`studies/lenses/*/study.py`, `studies/synthesis/synth01_study.py`, `studies/operational/phase9_backtest.py`, `studies/eda/eda_08_study.py`) import only from `dal.pipeline` and `dal.config`. No imports from `signals.*` or `intelligence.*`.

**Lifecycle gate wiring:** `signals/governance/lifecycle.py:assert_operational_safe()` is wired in the registry loader. `_EXPLORATORY_PREFIXES = (Path("studies/eda"),)` is the correct path restriction.

**FWD scope guard — captain.py, value.py, transfers.py:** All three modules zero xgi_roll3 and xgi_roll5 for FWD players before normalization. The all-zero group produces 0.5 from `normalize_within_position` (neutral, not removed).

**MID scope guard — captain.py:** Lines 102–105 correctly zero xgi_roll3 for both FWD and MID positions (`~(fwd_mask | mid_mask)`). G-SYNTH1-07 is implemented here.

**fdr_avg exclusion — fixtures.py:** fdr_avg is retained as informational column `fdr_window_avg` only. It does not enter `fixture_opportunity_score`. GAP-TRACE-02 resolved correctly.

**minutes_roll8 positional guard — availability.py:** `_MINUTES_ROLL8_POSITIONS = frozenset({"DEF", "MID"})` is enforced. `long_horizon_flag` is not assigned for GK or FWD. GAP-TRACE-03 resolved correctly.

**fixture_context consumption:** All three modules that consume fixture context (captain.py, transfers.py, fixtures.py) read from the STATE `fixture_context` column, not from `is_dgw` on the spine. GAP-TRACE-06 resolved correctly.

**MIN_RHO removal:** `intelligence/scoring/signal_selector.py` has no `MIN_RHO` constant. Comment at line 44 documents its removal (G-OPS-02). SCORE-T-01 is correctly RESOLVED in threshold-registry.md.

**population_builder.py population consumption:** Uses `filter_performance(df)` from `population.populations`, correctly linked to `CLEAN_SHEET_MIN_MINUTES` from `domain.fpl_scoring`. Change 2 implemented correctly.

**domain/fpl_scoring.py constants:** VERIFIED/UNVERIFIED annotations are present. `CLEAN_SHEET_MIN_MINUTES = FULL_APPEARANCE_MIN_MINUTES = 60` correctly expresses they are the same game rule. Change 1 implemented correctly.

**Weight loading:** All four intelligence modules call `get_module_weights(module_name)` from `intelligence/weight_registry.py`. No weights are hardcoded in module files.

**dal.mart public API consumption:** `dal.mart.__init__` exports `POSITION_CODE_MAP`, `GOVERNED_SIGNAL_COLUMNS`, `MartResult`, `build_prepared_dataset`. These are consumed by `population_builder.py` and `scoring/engine.py` — both are correct mart-layer consumers, not sub-layer bypasses.

**CAPT-T-01 file reference:** `threshold-registry.md §CAPT-T-01` references `intelligence/captain.py:49`. The actual constant `_MIN_MINUTES_ROLL3 = 45.0` is at line 32 in the current file. This is a minor line number drift, not a path error, and does not constitute a governance concern.
