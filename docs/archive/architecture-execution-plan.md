# Architecture Execution Plan
## Ontology → EDA → Representation → STATE

**Version:** 1.2
**Created:** 2026-05-24
**Updated:** 2026-05-26 — Phase 4 complete; Phase 5 early cleanup implemented
**Status:** In Progress

---

## How to use this document

Work phases sequentially. Within each phase, complete and verify all tasks before marking the phase done. Mark each task `[x]` as completed and tested. Do not start a new phase until all prior phase tasks are verified.

**Task states:**
- `[ ]` — not started
- `[~]` — in progress
- `[x]` — completed and verified

---

## Phase 1 — Make Ontology Operational

**Objective:** The ontology is currently human-readable only. Make it machine-readable so code can consult signal identity. This is the foundation all downstream phases depend on.
**Gate:** A YAML ontology artifact exists; scope annotations in STATE will derive from it; a consistency test passes.

- [x] Add `temporal_type` field to `docs/foundations/signal-ontology.md` for all 23 signals
  - rate: minutes
  - count: total_points, bonus, bps, goals_scored, assists, saves, penalties_saved, goals_conceded, transfers_in, transfers_out, fixture_count
  - stock: ownership_count, purchase_price
  - indicator: clean_sheets, was_home
  - estimate: xg, xa, xgi, xgc, fdr_avg, fdr_max, fdr_min
- [x] Create `docs/foundations/signal-ontology.yaml` — one entry per signal with: `signal`, `family`, `scope`, `temporal_type`, `semantic_constraint`
- [x] Add scope consistency test — for all signals appearing in both ontology YAML and STATE_CONTRACT.md, `scope` values must match
- [x] Update signal-ontology.md version and produced date

**Verification:** YAML loads without error. Consistency test passes. Ontology document and YAML are in sync.

- [x] Phase 1 verified and complete

---

## Phase 2 — Formalize Signal Behavior Profiles

**Objective:** Each EDA-studied signal gets a structured behavior profile. Makes EDA → representation design traceable. Redundancy map drives spine review — signals flagged as fully redundant may be removed from CURATED, which changes what STATE can derive.
**Gate:** EDA coverage mapped against ontology. Gap studies designed. All signals with sufficient EDA backing have behavior profiles. Redundancy map and sparsity map produced. Spine reviewed against redundancy map.

### Step 1 — Assess EDA coverage against ontology

- [x] Map EDA evidence against all 23 ontology signals — for each signal record: which EDA study covered it, which gate decisions apply, what questions remain unanswered
- [x] Classify each signal as: `covered` (sufficient EDA to write a profile), `partial` (some EDA but gaps remain), or `unstudied` (no EDA backing)
- [x] Produce EDA gap list — for each `partial` or `unstudied` signal, specify what study question needs to run before a behavior profile can be written — see `studies/eda/findings/EDA_COVERAGE_MAP.md`
- [x] Re-implement EDA design framework — update `EVAL_DESIGN.md` to anchor EDA study scope to the ontology: completeness defined by family coverage not study count; standard study pipeline (raw association → redundancy → rolling window) formalised; Context and stock signal exclusions derived from family rules not ad-hoc findings
- [x] Redefine scope of each existing EDA study (EDA-0 through EDA-7) against the updated framework — document what each covered, what it was bounded by, and what it cannot answer
- [x] Design EDA-8 within the updated framework — scope by signal family; Layer 1 (raw association) for saves GK, xgc, penalties_saved; Layer 2 (rolling window lens) for assists; add design document to `studies/eda/` before any code runs

### Step 2 — Write behavior profiles (covered signals only)

- [x] Create `docs/foundations/signal-behavior-profiles.yaml`
- [x] Write behavior profile for each `covered` signal — fields: `persistence_class`, `sparsity_level`, `redundancy_flags`, `gate_decisions`, `representation_implications`
  - [x] xgi (FORM)
  - [x] xgi_roll3, xgi_roll5 (FORM)
  - [x] minutes, minutes_roll8 (AVAIL)
  - [x] transfers_in, transfers_out (MARKET)
  - [x] ownership_count (MARKET)
  - [x] purchase_price (MARKET)
  - [x] fdr_avg (FIXTURE-GW)
  - [x] clean_sheets, goals_conceded, goals_scored, assists (FIXTURE-GW / FORM)
  - [x] saves, penalties_saved, bps, bonus, xgc, xa, xg — stub only until gap studies run
- [x] Produce redundancy map — document: xa → xgi, xg → xgi (FWD partial_rho 0.93, MID 0.74), fdr_max/min → fdr_avg (rho 1.0)
- [x] Produce sparsity classification per Event signal — flag penalties_saved as structurally sparse
- [x] Review spine (CURATED) against redundancy map — for each fully-redundant signal (xa, fdr_max, fdr_min), decide: remove from spine or retain with explicit rationale

### Step 3 — Run gap studies and complete profiles

- [x] Run each designed gap study — record findings using gate decision format (G-EDA{N}-{NN})
- [x] Add findings to `EDA_FINDINGS.md`
- [x] Complete behavior profiles for previously stubbed signals

**Verification:** EDA coverage map exists. Gap studies designed before any code runs. All 23 ontology signals have a behavior profile (complete or explicitly stubbed with gap study reference). Redundancy map cites G-EDA IDs. Spine review decision recorded for each flagged signal.

- [x] Phase 2 verified and complete

---

## Phase 3 — Create Representation Rules

**Objective:** Translate behavior profiles into explicit rules governing allowed and forbidden transforms per signal family.
**Gate:** Representation Rules document exists; every signal family has documented allowed and forbidden transforms.

- [x] Create `docs/foundations/representation-governance.md` — transformation governance framework defining: core philosophy (semantic admissibility vs behavioral justification), representation decision flow, temporal type admissibility constraints, behavioral profile characteristics, representation decision matrix, STATE materialization rules, anti-patterns
- [x] Create `docs/foundations/representation-rules.md`
- [x] Write rules for Event signals — allowed windows, sparse-signal exception (penalties_saved), team-scope labeling requirement
- [x] Write rules for Process signals — rolling mean allowed; xa_roll* forbidden (G-EDA6-02); xg_roll* FWD forbidden (G-EDA6-03); xgc REJECTED-BEHAVIORAL (G-EDA8-05); xgc labeled team-derived if ever used
- [x] Write rules for Participation signals — all three windows justified; minutes_trend CONDITIONAL (threshold undocumented; Phase 4 task)
- [x] Write rules for Market signals — no rolling transforms; point-in-time only
- [x] Write rules for Structural Tier signals — no rolling transforms
- [x] Write rules for Context signals — no rolling transforms; fdr_max/min REJECTED-SEMANTIC (G-EDA6-01); fdr_avg binary moderator CONDITIONAL (SYNTH-01)
- [x] Write rules for Allocation signals — all representations REJECTED-BEHAVIORAL (target leakage; G-EDA7-06)
- [x] Write rules for Outcome signal — rolling mean as predictor REJECTED-BEHAVIORAL; lag-1 approved as naive baseline only (G-EDA7-02)

**Verification:** Every signal family has a rule entry. No family is uncovered.

- [x] Phase 3 verified and complete

---

## Phase 4 — Stabilize STATE Contracts

**Objective:** Close gaps between code and documentation. STATE_CONTRACT.md accurately reflects what the code produces, with scope and behavioral rationale derived from the ontology and behavior profiles.
**Gate:** STATE contract fields are accurate, annotated, and consistent with the representation rules.

- [x] Fix STATE_CONTRACT.md column count to match post-cleanup code output — 29 columns (13 metrics × 2 + minutes_roll8 + minutes_trend + fixture_context)
- [x] Add `scope` annotation to every derived column in STATE_CONTRACT.md — scope values match ontology YAML; Team-scope noted for xgc, clean_sheets, goals_conceded
- [x] Add `behavioral_why` to every derived column in STATE_CONTRACT.md — one sentence per column sourced from behavior profiles and gate decisions
- [x] Add `lifecycle_state` to every derived column in STATE_CONTRACT.md — values: `operational` (minutes_roll8, fixture_context), `conditional` (xgi_roll3/5, clean_sheets/goals_conceded roll3/5, minutes_roll3/5, minutes_trend, points_roll5), `rejected` (all others); all REJECTED-BEHAVIORAL columns documented
- [x] Document `minutes_trend` 30-minute threshold rationale — editorial judgment; no formal behavioral study; documented in STATE_CONTRACT.md §minutes_trend rationale
- [x] Document `minutes_trend` overlapping windows — GW N-3 shared by last3 and prior3; conservative dampening effect; not corrected; fix path documented
- [x] Verify every STATE derived column is covered by an approved rule entry in representation-rules.md — confirmed; all 29 columns trace to a family rule and gate decision
- [x] Verify schema guard `_state_derived` matches STATE_CONTRACT.md — guard updated to `w in (3, 5)` + explicit `minutes_roll8`; matches 29-column contract

**Verification:** Read STATE_CONTRACT.md and player_gameweek_state.py side by side. Column count, column names, scope, behavioral_why, and lifecycle_state must be consistent across both. Every column maps to a representation rule. No two columns may share ambiguous governance status. Run test suite — no STATE schema test failures.

- [x] Phase 4 verified and complete

---

## Phase 5 — Refactor STATE Materialization

**Objective:** Remove Category C representations. Add scope metadata in code. STATE produces only governed, approved representations.
**Gate:** Every column STATE produces is in the representation rules approved set and carries governance metadata in code; schema guard enforces it. Column count (currently 29) is a consequence of this constraint, not the invariant itself.

> **Note:** The roll8 removal and xa removal were marked done 2026-05-24 but were not reflected in the code. They were correctly implemented in Phase 4 execution (2026-05-26) once the Phase 4 contract documentation confirmed the target schema.

- [x] Remove roll8 variants from `_ROLL_COLS` loop for all signals except `minutes` — implemented 2026-05-26
- [x] Remove xa from `_ROLL_COLS` — xa_roll3 and xa_roll5 no longer produced (G-EDA6-02) — implemented 2026-05-26
- [x] Update `_state_derived` schema guard to match the reduced column set — implemented 2026-05-26
- [x] Update STATE_CONTRACT.md to reflect cleaned schema (column counts, metrics list) — done as part of Phase 4
- [x] Add `_COLUMN_META` dictionary in `player_gameweek_state.py` — per derived column: `scope`, `causality`, `behavioral_reason`, `source_gate_decisions` — implemented 2026-05-26
- [x] Run full test suite — no STATE test failures — 750 passed, 2 skipped — implemented 2026-05-26
- [x] Add architecture test: confirm `xa_roll3`, `xa_roll5` are NOT in the output DataFrame — `tests/test_state_architecture.py` — implemented 2026-05-26
- [x] Add architecture test: confirm `xg_roll8`, `xa_roll8`, etc. are NOT in the output DataFrame — `tests/test_state_architecture.py` — implemented 2026-05-26
- [x] Confirm final column count: 13 metrics × 2 windows = 26, + minutes_roll8, + minutes_trend, + fixture_context = 29 — architecture test asserts this — implemented 2026-05-26

**Verification:** `build_player_gameweek_state()` output column count matches STATE_CONTRACT.md. Schema guard passes. Architecture tests pass. No redundant or excluded columns present.

- [x] Phase 5 verified and complete

---

## Phase 6 — Tighten Evaluation Governance

**Objective:** Evaluation findings formally govern operational eligibility. No operational threshold exists without analytical provenance.
**Gate:** MIN_RHO resolved; evaluation metadata structured per signal-position pair; operational thresholds cite evaluation records.

- [x] Document evaluation gate criteria explicitly — `docs/governance/evaluation-gate-criteria.md`; three gates (CI, decision relevance, block stability ≥ 2/3); decision_class and lifecycle_state vocabularies defined — implemented 2026-05-26
- [x] Add structured evaluation metadata to signal registry — `signals/evaluation/evaluation_metadata.yaml`; all 15 signal entries × positions with rho_pooled, rho_ci_lower, rho_ci_upper, block_stability_count, decision_class, lifecycle_state; 13 validation tests pass — implemented 2026-05-26
- [~] After SYNTH-01: determine whether a minimum rho threshold is appropriate; if yes, anchor value to SYNTH-01 finding with citation; if no, remove `MIN_RHO` entirely from `intelligence/scoring/signals.py` — MIN_RHO annotated as PROVISIONAL-EDITORIAL pending SYNTH-01; three incorrectly-caveated signals documented (xgi_roll3 DEF, xgi_roll5 DEF, purchase_price DEF); resolution deferred to Phase 8
- [x] Verify no operational file contains a hardcoded analytical threshold without citation — MIN_RHO is the only unexplained analytical threshold; editorial composition weights in captain.py, value.py, fixtures.py are labeled and tracked in Phase 7 — verified 2026-05-26

**Verification:** Signal registry contains structured evaluation fields. `intelligence/scoring/signals.py` contains no unexplained threshold constants. Evaluation gate criteria are documented in a referenceable form.

- [x] Phase 6 verified and complete (MIN_RHO resolution deferred to Phase 8 per plan)

---

## Phase 7 — Align Operational Consumption

**Objective:** All operational logic traces to evaluation findings or is explicitly labeled provisional.
**Gate:** No unjustified hardcoded weights or thresholds in `intelligence/decision/` modules.

- [x] Audit all hardcoded weights and thresholds in `intelligence/decision/` — list each with current provenance status — all weights in captain.py, value.py, fixtures.py, transfers.py, availability.py audited — implemented 2026-05-26
- [x] Categorize each as: `evaluation-derived` (cite finding), `provisional-editorial` (label with date), or `unjustified` (must resolve) — all weights categorized as provisional-editorial; no evaluation-derived weights; no unjustified items remain — implemented 2026-05-26
- [x] Add module-level provenance docstring to each decision module noting weight source and status — `## Weight provenance` sections added to captain.py, value.py, fixtures.py, transfers.py; `## Threshold provenance` added to availability.py — all document known governance inconsistencies — implemented 2026-05-26
- [x] Resolve all `unjustified` items — no unjustified items found; all constants are provisional-editorial with dates — implemented 2026-05-26
- [ ] After SYNTH-01: replace `provisional-editorial` weights with SYNTH-01-derived composition values

**Verification:** No decision module contains unlabeled hardcoded weights. Every threshold either cites an evaluation finding or carries a `provisional-editorial` label with date.

- [x] Phase 7 verified and complete (SYNTH-01 replacement deferred to Phase 8)

---

## Phase 8 — Composite and Synthesis Work

**Objective:** Run SYNTH-01 cleanly on the justified representation set. Propagate findings forward. Establish signal onboarding checklist.
**Gate:** SYNTH-01 complete with gate decisions; operational weights updated; onboarding checklist written.

- [ ] Run SYNTH-01 on the cleaned signal set from Phase 5 (9 confirmed signals across DEF/MID/FWD)
  - Does xgi_roll5 add beyond xgi_roll3 at any position?
  - Does fdr_avg condition form signal value as binary moderator?
  - Does minutes_roll8 add beyond minutes_roll5?
  - What composition weights per position?
- [ ] Document SYNTH-01 findings using gate decision format (G-SYNTH1-NN)
- [ ] Update Representation Rules if new window choices are empirically justified by SYNTH-01
- [ ] Update evaluation metadata — advance lifecycle_state for validated signals
- [ ] Replace provisional editorial weights in `intelligence/decision/` with SYNTH-01 composition weights
- [ ] Write signal onboarding checklist — `docs/governance/signal-onboarding-checklist.md`
  - Step 1: Ontology classification (family, scope, temporal_type)
  - Step 2: EDA behavior profile (persistence, sparsity, redundancy, gate decisions)
  - Step 3: Representation rules (allowed/forbidden transforms, justification)
  - Step 4: STATE addition (behavioral_reason, source_gate_decisions, schema guard update, contract update)
  - Step 5: Evaluation (rho, CI, block stability)
  - Step 6: Signal registry entry (lifecycle_state update)
  - Step 7: Operational eligibility (approved representations, provenance)

**Verification:** SYNTH-01 gate decisions documented. Operational weights updated with citations. Onboarding checklist covers all 7 steps.

- [ ] Phase 8 verified and complete

---

## Signal Engineering Candidates

Design ideas captured for future onboarding via the Phase 8 checklist. Not scheduled.

### Opponent Context Features

**Concept:** Enrich the player-gameweek frame with opponent-derived rolling aggregates — position-specific fixture context that FDR cannot provide.

**Proposed features:**
- `opp_goals_conceded_roll3` — opponent's goals conceded in last 3 GWs → defensive weakness; relevant for FWD/MID
- `opp_goals_scored_roll3` — opponent's goals scored in last 3 GWs → attacking threat; relevant for DEF/GKP
- xg-based variants (`opp_xgc_roll3`, `opp_xg_roll3`) for smoother estimates

**Why better than FDR:** position-specific, dynamic, continuous. FDR is a coarse 1–5 integer updated infrequently.

**Architecture note:** these are feature engineering layer constructs, not raw signals. They require a join step (player → fixture → opponent → opponent rolling stats) that current STATE materialization does not perform. They sit in a cross-entity enrichment layer between raw data and STATE, or as a parallel enrichment step.

**Governance note:** representation rules derive from source signal families (goals_conceded = Event → rolling admissible; xg = Process → rolling admissible). The opponent entity mapping changes the use case — these are not player-scope signals and do not inherit player-scope rejection decisions (e.g., xgc REJECTED-BEHAVIORAL as a *player* signal does not apply when xgc is used as an *opponent attribute*).

**Next step when ready:** ontology classification decision → EDA study by position → representation rules → STATE/enrichment addition → evaluation.

---

## Status Summary

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Make Ontology Operational | Complete |
| Phase 2 | Formalize Signal Behavior Profiles (EDA coverage → gap design → profiles) | Complete |
| Phase 3 | Create Representation Rules | Complete |
| Phase 4 | Stabilize STATE Contracts | Complete |
| Phase 5 | Refactor STATE Materialization — governed representations only | Complete |
| Phase 6 | Tighten Evaluation Governance | Complete (MIN_RHO resolution deferred to Phase 8) |
| Phase 7 | Align Operational Consumption | Complete (SYNTH-01 weight replacement deferred to Phase 8) |
| Phase 8 | Composite and Synthesis Work | Not started |

---

*Execution plan v1.5 — 2026-05-26 — Phase 7 complete; provenance docstrings added to all 5 intelligence modules; all weights labeled provisional-editorial with governance inconsistencies documented; 763 tests passing*
