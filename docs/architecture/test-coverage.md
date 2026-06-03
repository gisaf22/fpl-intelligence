# Test Coverage Map

Structured mapping between DAL invariants, the validators that enforce them, and the actual test suite coverage.

**Status model:**

| Status | Meaning |
|---|---|
| **Verified** | Backed by a real test assertion in the test suite — the test name is cited |
| **Partial** | Test exists but covers only part of the invariant, or the assertion is weaker than the contract requires |
| **Unverified** | Contract states this holds; no test backs it up |
| **Missing** | No test exists for this invariant |

**Important:** "Verified" means a named test currently asserts this invariant. It does not mean the test is correct. See the notes column for known test quality issues.

---

## Grain invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Staging fixture-grain unique | `validate_grain_uniqueness` | staging | **Unverified** | Validator unit-tested in `test_validation_modules.py` (TestValidateGrainUniqueness) but no integration test calls it on real staging output | |
| Integrated fixture-grain unique | `validate_grain_uniqueness` | intermediate | **Missing** | — | No test at any level |
| Curated GW-grain unique | `validate_grain_uniqueness` | curated | **Verified** | `test_spine_grain_unique` (test_dal_grain.py) | |
| State GW-grain unique | `validate_grain_uniqueness` | state | **Verified** | `test_state_grain_unique` (test_dal_grain.py) | |

---

## Spine completeness invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| `validate_row_completeness` is called in live build | Build path monkeypatch | curated | **Verified** | `test_validate_row_completeness_called_in_spine_build` (test_wave2_contract_enforcement.py) | |
| BGW rows are present (not absent) | `validate_row_completeness` | curated | **Verified** | `test_spine_bgw_rows_present` (test_dal_completeness.py) | |
| Row count = n_players × n_gws | `validate_row_count_invariant` | curated | **Verified** | `test_spine_row_count_invariant` (test_dal_completeness.py) | |
| Time continuity per player (no GW gaps) | `validate_time_continuity` | curated | **Verified** | `test_spine_time_continuity` (test_dal_completeness.py) | |

---

## BGW correctness invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| BGW `fixture_count == 0` | `validate_bgw_correctness` | curated | **Verified** | `test_bgw_fixture_count_zero` (test_dal_bgw.py) | |
| BGW performance columns are NULL | `validate_bgw_correctness` (uses `.notna()`) | curated | **Partial** | `test_bgw_correctness_via_validator` (test_dal_bgw.py) **correctly** verifies this via the fixed validator. `test_bgw_performance_columns_zero` (test_dal_bgw.py) is **stale and misleading** — its docstring says "zero not null", it uses `!= 0` (which silently passes for `pd.NA`), and its name contradicts the current contract. The stale test passes currently because `pd.NA != 0` is falsy. | ⚠ `test_bgw_performance_columns_zero` contradicts the contract; should be renamed or deleted |
| BGW FDR columns are NULL | `validate_bgw_correctness` | curated | **Verified** | `test_bgw_fdr_columns_null` (test_dal_bgw.py) — uses `.notna()` correctly | |
| BGW opponent context columns are NULL | `validate_bgw_correctness` | curated | **Unverified** | No named test for this specifically | |
| BGW `team_id` from pre-BGW GW (not latest) | `_apply_bgw_defaults` logic | curated | **Verified** | `test_bgw_team_id_uses_pre_transfer_team` (test_wave1_sc2_bgw_team_id.py) | |

---

## DGW correctness invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| DGW `fixture_count == 2` | `validate_dgw_correctness` | curated | **Verified** | `test_dgw_fixture_count_two` (test_dal_dgw.py) | |
| DGW `home_count + away_count == 2` | `validate_dgw_correctness` | curated | **Verified** | `test_dgw_home_away_count_sums_to_two` (test_dal_dgw.py) | |
| DGW points = sum of both fixtures | `validate_dgw_correctness` | curated | **Verified** | `test_dgw_correctness_via_validator` (test_dal_dgw.py) via validator | No standalone arithmetic test; reliant on validator correctness |
| DGW `fdr_min <= fdr_avg <= fdr_max` | `validate_dgw_correctness` | curated | **Verified** | `test_dgw_fdr_ordering` (test_dal_dgw.py) | |
| DGW clean sheets ∈ {0, 1, 2} | `validate_dgw_correctness` | curated | **Verified** | `test_dgw_clean_sheet_count_in_bounds` (test_dal_dgw.py) | |
| TGW raises `DALContractViolation` | `validate_dgw_correctness` | curated | **Verified** | `test_fixture_count_out_of_bounds_fails` (test_validation_modules.py) | Unit test on validator only; no integration test with TGW data |
| `goals_conceded` sums across DGW fixtures | Aggregation logic | intermediate | **Verified** | `test_goals_conceded_sums_across_dgw_fixtures` (test_wave1_sc3_goals_conceded.py) | |

---

## Null semantics invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Identity columns never null | `validate_null_semantics` | curated | **Verified** | `test_identity_columns_never_null` (test_dal_nulls.py) | |
| Schedule columns never null | `validate_null_semantics` | curated | **Verified** | `test_schedule_columns_never_null` (test_dal_nulls.py) | |
| Performance columns null only when no fixture | `validate_null_semantics` | curated | **Verified** | `test_performance_columns_null_for_bgw` (test_dal_nulls.py) | |
| FDR columns null iff BGW | `validate_null_semantics` | curated | **Verified** | `test_fdr_columns_null_for_bgw` (test_dal_nulls.py) | |
| Market columns never null | `validate_null_semantics` | curated | **Verified** | `test_market_columns_never_null` (test_dal_nulls.py) | |

---

## Column contract invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Exact column set — no extras, no missing | `validate_column_contract` | curated | **Verified** | `test_curated_column_set_exact` (test_dal_invariants.py) | |
| Exact dtypes for all columns | `validate_column_contract` | curated | **Verified** | `test_curated_column_dtypes_exact` (test_dal_invariants.py) | |
| `SPINE_COLS == DTYPES.keys()` | Static assertion | curated | **Verified** | `test_all_spine_cols_present_in_dtypes` (test_wave2_contract_enforcement.py) | |
| `SPINE_COLS == NULL_RULES.keys()` | Static assertion | curated | **Verified** | `test_all_spine_cols_present_in_null_rules` (test_wave2_contract_enforcement.py) | |
| `validate_column_contract` called in live build | Build path monkeypatch | curated | **Verified** | `test_validate_column_contract_called_in_spine_build` (test_wave2_contract_enforcement.py) | |

---

## Join safety invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Spine → state: no row loss | Row count check | state | **Verified** | `test_spine_to_state_no_row_loss` (test_dal_joins.py) | |
| Spine → state: no fan-out | `validate_grain_uniqueness` | state | **Verified** | `test_spine_to_state_no_fan_out` (test_dal_joins.py) | Uses free-form grain list, not GRAIN_CONTRACTS registry |
| Staging → integrated: no row loss | `validate_join_safety` | intermediate | **Missing** | — | Validator unit-tested in isolation; no test on real staging → integrated join |
| Integrated → curated: no row loss | `validate_join_safety` | curated | **Missing** | — | Same gap |
| Curated spine join: no fan-out | `validate_join_safety` | curated | **Missing** | — | Same gap |

---

## Temporal causality invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| No performance data for future GWs | `validate_no_future_data` (uses `.notna()`) | curated | **Verified** | `test_no_future_data` (test_dal_invariants.py) | |
| `minutes_trend` uses lag-1 convention | Rolling logic with `shift(1)` | state | **Verified** | `test_minutes_trend_lag1_convention` (test_wave1_sc1_minutes_trend.py) | |
| All `_ROLL_COLS` use lag-1 convention | Rolling logic | state | **Verified** | `test_roll5_at_gw_n_uses_gw_n_minus_1_back` (test_state_rolling_windows.py) | |

---

## Determinism invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Two-run exact equality (spine) | `pd.testing.assert_frame_equal` | curated | **Verified** | `test_full_pipeline_is_reproducible` (test_wave3_determinism.py) | Primary regression test; should run on every PR |
| Staging SQL contains `ORDER BY` | Static check on `_build_query` | staging | **Verified** | `test_staging_sql_contains_order_by_*` ×6 (test_wave3_determinism.py) | All 6 entities covered |
| Pre-aggregation sort by `fixture_id` | Aggregation sort logic | curated | **Verified** | Covered by `test_full_pipeline_is_reproducible` end-to-end | No dedicated sort-isolation test |
| Spine fingerprint identical across runs | `compute_spine_fingerprint` | curated | **Verified** | `test_spine_fingerprint_identical_across_runs` (test_wave6_observability.py) | |

---

## FIRST_COLS semantic invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| `FIRST_COL_SEMANTICS` registry exists | Static import check | curated | **Verified** | `test_first_col_semantics_registry_exists` (test_wave3_determinism.py) | |
| All `FIRST_COLS` entries classified in `FIRST_COL_SEMANTICS` | Static completeness check | curated | **Unverified** | — | No test asserts that every key in FIRST_COLS has a corresponding entry in FIRST_COL_SEMANTICS |
| `invariant_per_gw` assertion fires on violation | `_assert_invariant_per_gw_columns` | curated | **Verified** | `test_invariant_per_gw_assertion_catches_violation` (test_wave3_determinism.py) | |

---

## Intermediate layer invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| `opponent_team_id` present in fixture base | Column check | intermediate | **Verified** | `test_opponent_team_id_overrides_staging_for_home_player` + `_away_player` (test_wave1_sc4_opponent_team_id.py) | |
| `opponent_team_id` correct for home/away | Logic assertion | intermediate | **Verified** | Both tests above | |
| `opponent_team_id` never null | Null check | intermediate | **Verified** | `test_opponent_team_id_never_null_after_fix` (test_wave1_sc4_opponent_team_id.py) | |

---

## State layer invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| `fixture_context` ∈ `{"BGW", "SGW", "DGW"}` only | `STATE_COL_CONTRACTS` / assertion | state | **Verified** | `test_fixture_context_bgw_rows` + `test_fixture_context_exhaustive` (test_wave4_invariant_expansion.py) | |
| `xgc_001` invariance holds for all positions | `validate_xgc_001` | intermediate | **Verified** | `test_validate_xgc_001_callable_on_all_positions` (test_wave4_invariant_expansion.py) | Tests callability; does not test with data where a non-GK defender has inconsistent xgc |
| `STATE_COL_CONTRACTS` covers all state columns | Static coverage check | state | **Partial** | `test_state_col_contracts_covers_fixture_context` + `test_state_col_contracts_covers_minutes_trend` (test_wave4_invariant_expansion.py) | Only spot-checks two columns; no test asserts all state columns are registered |

---

## Environment and observability invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| `FPL_DB_PATH` env override resolves correctly | `dal.config.DB_PATH` | config | **Verified** | `test_fpl_db_path_env_override` (test_wave6_observability.py) | |
| Validation layer importable without curated imports | Import isolation test | validation | **Verified** | `test_invariants_module_has_no_curated_imports` (test_wave2_contract_enforcement.py) | |
| All `DALContractViolation` raises include `layer=` | Audit grep | all layers | **Verified** | `test_all_contract_violations_have_layer` (test_wave6_observability.py) | |

---

## Fixture-coverage invariants

The curated fixture DB (`tests/fixtures/test.db`, built by `create_test_db.py`) is a first-class
test artifact (ADLC §5). These meta-tests assert each hard case is *present* in the built DB, so
edge-case coverage is itself tested — a botched fixture refactor fails loudly instead of silently
dropping a scenario. All assert against the built DB via the `db_path` fixture (never live `~/.fpl/fpl.db`).

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| BGW scenario present (played-round gap) | meta-test | fixture | **Verified** | `test_fixture_has_bgw` (test_fixture_coverage.py) | P1/P4 have no GW3 row (T1 blank) |
| DGW scenario present (>1 row per round) | meta-test | fixture | **Verified** | `test_fixture_has_dgw` (test_fixture_coverage.py) | P2/P3 two rows in GW4 (SC-3) |
| Mid-season transfer present | meta-test | fixture | **Verified** | `test_fixture_has_midseason_transfer` (test_fixture_coverage.py) | P3 T1→T2 derived-team change (SC-2) |
| Zero-minute appearance present | meta-test | fixture | **Verified** | `test_fixture_has_zero_minute` (test_fixture_coverage.py) | P4 GW1 — real 0, not BGW NULL (SC-5) |
| Warm-up sub present | meta-test | fixture | **Verified** | `test_fixture_has_warmup_sub` (test_fixture_coverage.py) | P4 GW2 — starts=0, minutes>0 (SC-6) |
| Red card present | meta-test | fixture | **Verified** | `test_fixture_has_red_card` (test_fixture_coverage.py) | P4 GW4 — red_cards>0 (SC-7) |
| Multi-position present (≥3 element_type) | meta-test | fixture | **Verified** | `test_fixture_has_multiple_positions` (test_fixture_coverage.py) | GK + MID + DEF |

---

## Static typing invariants

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Production type surface clean | `uv run mypy` | dal / signals / intelligence / domain / population | **Verified** | **blocking CI gate** (`.github/workflows/ci.yml`) | Was `continue-on-error` (documentation); flipped to blocking in Phase 5 after fixing the 10 surfaced errors. Scope set by `[tool.mypy] files=`; `studies/` excluded by design. |

---

## Governance key-grammar invariants

The composite signal-finding key scheme (ADR-003) replaced the opaque `FORM-*`/`AVAIL-*`/
`G-SYNTH1-*` codes with self-describing `signal@lens:target[#POSITION]` keys. These migration
tests are the contract that a botched migration must fail — they hold the loader's lookup
semantics and the YAML↔YAML cross-reference honest. All in `test_composite_key_migration.py`.

| Invariant | Validator | Layer | Status | Test | Notes |
|---|---|---|---|---|---|
| Findings carry composite `key`, not retired `signal_id` | meta-test | governance | **Verified** | `test_every_finding_has_composite_key_not_old_code` | killed namespace gone as a key field |
| Finding key == derive(signal, lens, target) — no drift | meta-test | governance | **Verified** | `test_finding_key_equals_derived_form` | key is a pure function of its own fields |
| Every finding key resolves via composite lookup | loader | governance | **Verified** | `test_every_finding_key_resolves_by_key` | resolves-all (findings) |
| Every synth decision key resolves to its parent finding | loader | governance | **Verified** | `test_every_synth_decision_key_resolves_to_a_finding`, `test_synth_decision_key_is_parent_finding_plus_position` | resolves-all (decisions); `{key}#POS` nests under parent |
| Eval↔synth cross-ref self-validates (`{key}#{pos}`) | meta-test | governance | **Verified** | `test_eval_cross_reference_matches_finding_key_plus_position`, `test_cross_reference_targets_exist_in_synth_decisions` | no dangling / drifted cross-references |
| Composite lookup hard-fails on missing / malformed / unknown position | loader | governance | **Verified** | `test_missing_key_raises`, `test_missing_position_in_key_raises`, `test_malformed_key_raises` | raises `GovernanceMetadataError`, never a silent default |
| minutes_roll3 collision resolves to opposite verdicts by key | loader | governance | **Verified** | `test_minutes_roll3_collision_resolves_to_opposite_verdicts_by_key` | form-rejected vs avail-approved — the bare column hides this |
| Retired namespaces absent from key fields (both YAMLs) | meta-test | governance | **Verified** | `test_no_retired_codes_in_key_fields` | `FORM-*`/`AVAIL-*`/`MARKET-*`/`FIXTURE-*`/`G-SYNTH1-*` no longer load-bearing keys |

---

## Coverage summary

| Category | Total | Verified | Partial | Unverified | Missing |
|---|---|---|---|---|---|
| Grain | 4 | 2 | 0 | 1 | 1 |
| Spine completeness | 4 | 4 | 0 | 0 | 0 |
| BGW correctness | 5 | 3 | 1 | 1 | 0 |
| DGW correctness | 7 | 7 | 0 | 0 | 0 |
| Null semantics | 5 | 5 | 0 | 0 | 0 |
| Column contract | 5 | 5 | 0 | 0 | 0 |
| Join safety | 5 | 2 | 0 | 0 | 3 |
| Temporal causality | 3 | 3 | 0 | 0 | 0 |
| Determinism | 4 | 4 | 0 | 0 | 0 |
| FIRST_COLS semantics | 3 | 2 | 0 | 1 | 0 |
| Intermediate layer | 3 | 3 | 0 | 0 | 0 |
| State layer | 3 | 1 | 2 | 0 | 0 |
| Env / observability | 3 | 3 | 0 | 0 | 0 |
| Fixture coverage | 7 | 7 | 0 | 0 | 0 |
| Static typing | 1 | 1 | 0 | 0 | 0 |
| Governance key grammar | 8 | 8 | 0 | 0 | 0 |
| **Total** | **70** | **60** | **3** | **3** | **4** |

---

## Gaps requiring action

### Missing tests (4)

| Gap | Category | Priority |
|---|---|---|
| Integrated fixture-grain uniqueness has no test at any level | Grain | High — intermediate grain is entirely untested |
| Staging → intermediate join: no row loss | Join safety | High — silent row loss here would propagate through all layers |
| Intermediate → curated join: no row loss | Join safety | High — same issue |
| Curated spine join: no fan-out | Join safety | Medium — covered implicitly by grain uniqueness test |

### Unverified invariants (3)

| Gap | Category | Priority |
|---|---|---|
| Staging fixture-grain: validator tested in isolation but never called on real staging output in integration | Grain | Medium |
| BGW opponent context columns are NULL | BGW correctness | Medium |
| All `FIRST_COLS` entries classified in `FIRST_COL_SEMANTICS` | FIRST_COLS | Low — registry exists; completeness of classification not asserted |

### Partial tests requiring cleanup (3)

| Gap | Issue | Priority |
|---|---|---|
| `test_bgw_performance_columns_zero` | Name says "zero", docstring says "zero not null", uses `!= 0` which silently passes for `pd.NA`. Contradicts the current contract (BGW performance = NULL, not zero). `test_bgw_correctness_via_validator` correctly covers this invariant — the stale test should be renamed to `test_bgw_performance_columns_null` and updated to use `.notna()` | High — misleading test name creates false confidence |
| `test_validate_xgc_001_callable_on_all_positions` | Tests that the function is callable on all-position data; does not test with data where a non-GK defender has an inconsistent xgc value. Does not verify the invariant actually fires. | Medium |
| `STATE_COL_CONTRACTS` coverage | Only 2 of N state columns spot-checked; no test asserts full coverage | Low |
