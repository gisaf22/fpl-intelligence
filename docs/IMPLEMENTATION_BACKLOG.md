# FPL Intelligence — Implementation Backlog

**Purpose:** Operational execution tracking only.
**Source of truth for scope:** `docs/IMPLEMENTATION_ROADMAP.md`

---

# Sprint A — Complete Signal Characterization Modules

## A1 — core/signals/stability.py
Status: DONE
Blocked by: nothing
PR:
Notes: Implemented. Heuristic: normalized median shift between blocks using pooled IQR as denominator. Thresholds STABLE=0.5, UNSTABLE=1.5. All-zero signals → stable (normalized shift = 0). One-valid-one-nan block → unstable (cannot pool). 33 tests passing.

## A2 — core/signals/redundancy.py
Status: DONE
Blocked by: nothing (parallel with A1)
PR:
Notes: Implemented. `compute_pairwise_rho`, `identify_redundant_pairs`, `compute_partial_rho`, `ALGEBRAIC_DECOMPOSITIONS` all present. Used by EDA-6 notebook (C1).

## A3 — tests/test_signals_stability.py
Status: DONE
Blocked by: A1 (module signatures must be locked)
PR:
Notes: 33 tests passing. Covers vocabulary completeness, all three homogeneity classifications, boundary conditions, all-zero edge case, all-nan edge case, one-valid-one-nan edge case, 3-block max pairwise, custom gw_column, custom gw_blocks, full pooling decision mapping.

## A4 — tests/test_signals_redundancy.py
Status: DONE
Blocked by: A2
PR:
Notes: 33 tests passing. Confirmed via pytest.

---

# Sprint B — EDA-4 and EDA-5 Execution

## B1 — research/eda/notebooks/eda_04_population_validity.ipynb
Status: DONE
Blocked by: —
PR:
Notes: Implemented. Orchestration-only. Calls `compute_dual_scope_rho()` + `classify_population_robustness()` from `analytics.signals.population`. Geometry passed as equal constants ("unknown") so classification is rho-shift-driven. Five output assertions enforced before write. Column renaming: n_filtered→primary_n, rho_filtered→rho_primary, rho_shift→delta_rho. NOTE: `eda_04_population_validity.csv` and `eda_04_dual_rho_bounds.csv` are not present in research/eda/findings/ — notebook was implemented but not executed. population_robustness is derived directly by the computed registry build pipeline, so these CSVs are not on the critical path.

## B2 — research/eda/notebooks/eda_05_signal_stability.ipynb
Status: DONE
Blocked by: —
PR:
Notes: Implemented. Orchestration-only. Calls `analytics.signals.stability.*`. Outputs `eda_05_signal_stability.csv` and `eda_05_pooling_decisions.csv` confirmed written to `research/eda/findings/`.

## B3 — EDA_FINDINGS.md EDA-4 and EDA-5 sections
Status: OBSOLETE
Notes: EDA_FINDINGS.md deleted. EDA-4 and EDA-5 findings are encoded in the governed registry (population_robustness, temporal_stability columns). Gate decisions migrated to docs/decisions/eda_01_analytical_foundations.md.

---

# Sprint C — EDA-6 and EDA-7 + Promotion Class Wiring

## C1 — research/eda/notebooks/eda_06_redundancy.ipynb
Status: DONE
Blocked by: —
PR:
Notes: Implemented. Orchestration-only. Calls `compute_pairwise_rho` per position, melts upper-triangle to long form for `eda_06_pairwise_rho.csv`. Calls `identify_redundant_pairs` then combines with `ALGEBRAIC_DECOMPOSITIONS` pairs into `eda_06_construct_map.csv` (relationship_type: algebraic_decomposition | statistical_redundancy, algebraic pairs take precedence). Calls `compute_partial_rho` for each flagged pair into `eda_06_partial_rho.csv`. Six output assertions enforced before write. Pair ordering is lexicographic throughout. NOTE: `eda_06_pairwise_rho.csv`, `eda_06_construct_map.csv`, `eda_06_partial_rho.csv` are not present in research/eda/findings/ — notebook was implemented but not executed. Redundancy relationships are encoded in `ALGEBRAIC_DECOMPOSITIONS` and `construct_relationship_present` in the registry.

## C2 — research/eda/notebooks/eda_07_signal_synthesis.ipynb
Status: DONE
Blocked by: B1, B2, C1
PR:
Notes: Implemented. Assembly-only notebook. Joins EDA-3 (association_class, downstream_status, signal_layer), EDA-4 (population_robustness), EDA-5 (temporal_stability via homogeneity rename), EDA-6 (construct_relationship_present boolean). Calls assign_promotion_class() per non-blocked row. Output grain (signal, position, population_scope), 105 rows, 10 output columns. No statistical/runtime fields emitted. All cardinality assertions pass. NOTE: `eda_07_signal_synthesis.csv` is not present in research/eda/findings/ — notebook was implemented but not executed. promotion_class is derived directly by the computed registry build pipeline via analytics.registry.promotion.

## C3 — EDA_FINDINGS.md EDA-6 and EDA-7 sections
Status: OBSOLETE
Notes: EDA_FINDINGS.md deleted. EDA-6 findings encoded in ALGEBRAIC_DECOMPOSITIONS (core/signals/redundancy.py) and construct_relationship_present registry column. EDA-7 findings encoded in promotion_class column with coherence assertions at build time.

---

# Sprint D — Computed Registry Authority + Parity Test

## D1 — dal/prepared/analytical_dataset.py
Status: DONE
Blocked by: nothing (depends only on existing curated spine)
PR:
Notes: Implemented. Created dal/prepared/ package. build_prepared_dataset() is pure/testable (takes spine DataFrame directly). main() wires CLI and DB load. GOVERNED_SIGNAL_COLUMNS tuple matches EDA registry signal set. position_code → position via POSITION_CODE_MAP {1:GK, 2:DEF, 3:MID, 4:FWD}. BGW rows excluded naturally: None >= 60 → False.

## D2 — tests/test_dal_prepared_dataset.py
Status: DONE
Blocked by: D1
PR:
Notes: 19 tests passing. All unit tests — no DB dependency. Tests inject synthetic spine directly into build_prepared_dataset(). Covers schema contract, position mapping for all 4 codes, grain uniqueness, grain violation detection, minutes filter boundary, BGW exclusion, GW cutoff enforcement, missing column error. No integration marks needed because build_prepared_dataset() takes a DataFrame, not a db_path.

## D3 — tests/test_registry_build_parity.py
Status: DONE
Blocked by: D1, C2 (EDA-7 synthesis CSV must be present)
PR:
Notes: 5 integration tests passing. Reproducibility gate: re-runs computed build (GW6-33, minutes>=60, 29 signals) and compares against seed registry. Assertions: schema parity (set-based), row count == 116 (29 signals x 4 positions), no duplicate keys, rho_pooled within 0.02 absolute tolerance for all non-null pairs. Seed registry at research/eda/findings/eda_03_joint_registry.csv (exploratory EDA-3 archived as eda_03_joint_registry_exploratory.csv). red_cards added to signal list and SIGNAL_LAYER_MAPPING (discipline layer) — row count increased from 112 to 116. Root cause of original 0.02 failure: exploratory EDA-3 was built from minutes>=1 population against an older DB snapshot — not a pipeline defect.

## D4 — End-to-end reproducibility smoke test (manual)
Status: DONE
Blocked by: D1, D3
PR:
Notes: Executed the computed build sequence: (1) build_prepared_dataset GW6-33 → data/prepared_gw33.csv (5,736 rows). (2) registry_build.runner --mode computed --prepared-data-path data/prepared_gw33.csv --gw 33 → outputs/registry/gw33/registry.csv (116 rows, exit 0). (3) Seed registry copied to eda_03_joint_registry.csv. Parity test passes. Computed registry is now the authoritative reference. gw_block derivation added to runner.py (_assign_gw_block) — fixes temporal_stability="insufficient_data" that affected all rows in the original build.

---

# Sprint E — Weekly Signal Intelligence

## E1 — weekly/signal_intelligence.py
Status: DONE
Blocked by: D3 (computed registry with real promotion_class values required)
PR:
Notes: Implemented. Three functions: build_stable_signal_observations (core_signal + review_signal rows — 8 core_signal rows present after gw_block fix), build_positional_signal_summary (4 rows, one per position), build_context_condition_notes (context + exposure layers). All strings from governed template constants. write_signal_intelligence() write helper included. Original seed had no core_signal rows due to missing gw_block in runner — fixed in D4 followup.

## E2 — tests/test_weekly_signal_intelligence.py
Status: DONE
Blocked by: E1 (module signatures must be locked)
PR:
Notes: 29 tests passing. Covers schema, forbidden-phrase scan (rank, player_id, ranking, predicted score, captaincy, transfer recommendation), template rendering spot-checks for all three functions, NaN rho renders as n/a, blocked rows excluded, empty-input safety, write integration.

## E3 — Wire signal_intelligence into weekly/runner.py
Status: DONE
Blocked by: E1, E2
PR:
Notes: write_signal_intelligence() called after registry load. Three new paths added to WeeklyRunResult: stable_signal_observations_path, positional_signal_summary_path, context_condition_notes_path. All weekly tests passing (42 tests).
