# Testing Strategy

**Authoritative for:** what the test suite covers, how to run it, what the integration marker means, and why the suite is structured the way it is.

---

## Summary

| Metric | How to get the current value |
|--------|-------|
| Total tests | `pytest --collect-only -q \| tail -1` (do not hard-code — the CI job is the source of truth) |
| DB-free (unit) | `pytest -m "not integration"` |
| Integration (live DB) | `pytest` (requires live/fixture DB) |
| Import-linter contracts | 6 active (defined in `.importlinter`) |

> Test counts are intentionally **not hard-coded** here — they drift the moment a test is added.
> The CI job is authoritative. (A prior version of this table claimed "739 tests"; the suite has
> since grown well past that.)

---

## Running tests

```bash
pytest -m "not integration"   # DB-free unit + contract tests; fast
pytest                        # full suite (requires live/fixture DB)
lint-imports                  # import boundary enforcement (the 6 contracts in .importlinter)
```

`pytest -m "not integration"` is the right choice for fast feedback during development. It runs in seconds and covers all logic that does not require a live database connection. `pytest` (the full suite) is the gate for any PR or structural change.

`lint-imports` is separate from the test suite — it validates import boundaries, not behaviour. It should pass on every commit. If it fails, an import contract has been violated; fix the import before fixing tests.

---

## Test categories

### DAL correctness — `tests/stabilization/`

Six wave-based test files, one per stabilization wave. Each file is a permanent record of a defect that existed, its proof, and its fix. These tests cannot be deleted or weakened — they are the only guarantee that historical corruption bugs do not silently return.

| File | Wave | What it covers |
|------|------|---------------|
| `test_wave1_sc1_minutes_trend.py` | 1 | Look-ahead contamination in `minutes_trend` (SC-1) |
| `test_wave1_sc2_bgw_team_id.py` | 1 | BGW team_id temporal leakage for transferred players (SC-2) |
| `test_wave1_sc3_goals_conceded.py` | 1 | DGW goals_conceded averaging bias (SC-3) |
| `test_wave1_sc4_opponent_team_id.py` | 1 | Missing opponent_team_id crash (SC-4) |
| `test_wave1_sc11_missing_gw_context.py` | 1 | Missing GW context silent proceed (SC-11) |
| `test_wave2_contract_enforcement.py` | 2 | Validators present in live build; nullable comparison bugs |
| `test_wave3_determinism.py` | 3 | Byte-identical output; ORDER BY in staging; FIRST_COLS stability |
| `test_wave4_invariant_expansion.py` | 4 | fixture_context BGW/SGW labelling; TGW detection; min_periods |
| `test_wave5_architecture.py` | 5 | Exception hierarchy; layer classification |
| `test_wave6_observability.py` | 6 | Staging logs; environment override; reproducibility fingerprint |

All stabilization tests are marked `@pytest.mark.integration` — they require the golden test database at `tests/fixtures/`.

### DAL invariant suite — `tests/test_dal_*.py`

Comprehensive per-concern tests run against the constructed test database. These cover the complete set of DAL invariants defined in `dal/validation/` and `dal/fct/fct_contracts.py`.

| File(s) | Concern |
|---------|---------|
| `test_dal_grain.py` | Grain uniqueness at staging, curated, and state layers |
| `test_dal_completeness.py` | Row count = n_players × n_gws; BGW rows present; time continuity |
| `test_dal_bgw.py` | BGW null semantics; fixture_count=0; team_id temporal rule |
| `test_dal_dgw.py` | DGW aggregation; fixture_count=2; normalization convention |
| `test_dal_nulls.py` | NULL vs zero semantics across all SPINE_COLS |
| `test_dal_joins.py` | Join safety; no silent row loss at any merge site |
| `test_dal_invariants.py` | Cross-cutting invariants: future data prohibition, roll window lag-1 |
| `test_dal_prepared_dataset.py` | Prepared dataset cutoff semantics; GOVERNED_SIGNAL_COLUMNS |
| `test_dal_architecture.py` | Import boundary enforcement (unit — no DB required) |
| `test_validation_modules.py` | Validator unit tests (unit — no DB required) |
| `test_curated_spine.py`, `test_curated_state_boundary.py` | Spine and state layer boundaries |
| `test_staging.py`, `test_state.py` | Layer-level construction and output |
| `test_state_rolling_windows.py`, `test_state_stabilization.py` | State rolling window semantics |

### Governance enforcement — `tests/test_downstream_governance.py`

Static analysis tests that scan all `.py` files and notebooks for forbidden import patterns. No database required. Covers:

| Check | What it catches |
|-------|----------------|
| G-1 | `pipeline.*` imports — retired namespace |
| G-2 | `sqlite3` / `pd.read_sql` outside `dal/` — direct DB access bypass |
| G-3 | `dal.staging` / `dal.intermediate` imports outside DAL and tests |
| G-4 | Smoke test that `dal.pipeline.run` and `dal.pipeline.load` are importable |

These tests catch architectural regressions that `lint-imports` does not — specifically imports that are technically valid Python but violate the DAL contract.

### Registry lifecycle — `tests/test_registry_*.py`

| File | Covers |
|------|--------|
| `test_registry_lifecycle.py` | `assert_operational_safe()` path gate; `LifecycleViolationError` raises |
| `test_registry_promotion.py` | Promotion rules and state transition logic |
| `test_registry_semantics.py` | Registry CSV schema validation |
| `test_registry_contract.py` | Contract enforcement: required columns, dtypes |
| `test_registry_assembly.py` | Registry build assembly logic |
| `test_registry_build_inputs.py` | Input validation for registry build pipeline |
| `test_registry_build_parity.py` | Parity between EDA registry and built artifact |
| `test_registry_build_runner.py` | End-to-end registry build runner |

### Intelligence and scorer — `tests/test_scorer_*.py`, `tests/test_intelligence_*.py`

| File | Covers |
|------|--------|
| `test_scorer_signals.py` | Signal selection filters; confirmed vs caveated classification |
| `test_scorer_engine.py` | Normalisation; weighted composite; rank computation |
| `test_intelligence_outputs.py` | Intelligence layer output functions; eligibility filters |

All scorer and intelligence tests are DB-free (unit). They use fixture DataFrames, not a live DAL build.

### Evaluation helpers — `tests/test_evaluation_*.py`

Tests for the evaluation modules now in `tests/helpers/` (moved from `signals/governance/` during S11). These helpers provide baselines, metrics, and temporal integrity checks used across evaluation studies.

| File | Covers |
|------|--------|
| `test_evaluation_core.py` | Core metric computations: mean_return, hit_rate, regret |
| `test_evaluation_captain.py` | Captain heuristic evaluation against baselines |
| `test_evaluation_transfers.py` | Transfer target heuristic evaluation |
| `test_evaluation_features.py` | Feature lift: rolling rho vs single-game lag rho |

### Weekly reporting — `tests/test_weekly_*.py`

Tests for the weekly reporting pipeline: snapshots, signal intelligence summaries, markdown output, and runner orchestration.

### Study validation — `tests/test_*_study.py`, `tests/test_*_validation.py`

| File | Covers |
|------|--------|
| `test_rolling_xgi_study.py` | Rolling xGI horizon study reproducibility |
| `test_rolling_xgi_real_validation.py` | Real-data xGI validation |
| `test_minutes_stability_study.py` | MINSTAB-01 study reproducibility |

### Signal characterisation — `tests/test_signals_*.py`

| File | Covers |
|------|--------|
| `test_signals_stability.py` | Signal stability computation |

### Integration tests — `tests/test_integrated_*.py`

| File | Covers |
|------|--------|
| `test_integrated.py` | Full pipeline: DAL → registry → scorer, end to end |
| `test_integrated_pipeline.py` | DAL pipeline integration with real DB |
| `test_integrated_research.py` | Research pipeline integration |

---

## The integration marker

Tests marked `@pytest.mark.integration` require a live database (`FPL_DB_PATH` or the golden test DB at `tests/fixtures/`). They are excluded from the unit lane (`pytest -m "not integration"`).

**What requires the integration marker:**
- Any test that calls `build_player_gameweek_spine()`, `build_player_gameweek_state()`, or any DAL builder
- Any test that reads from a SQLite database, even the golden test fixture
- Any test that relies on the full constructed spine shape or real row counts

**What does not require the integration marker:**
- Tests that use fixture DataFrames constructed in the test itself
- Tests that scan source code (governance checks)
- Tests that call pure computation functions with in-memory inputs
- Tests that load the registry CSV from `outputs/registry/gw36/` (the committed bootstrap)

**CI implication:** the DB-free lane (`pytest -m "not integration"`) runs in CI on every push. The full suite (`pytest`) requires a database artifact and runs on demand or in a dedicated integration stage.

---

## Import boundary enforcement

Beyond `pytest`, two additional enforcement tools run directly:

```bash
lint-imports       # import-linter — verifies the layer contracts in .importlinter
```

A supplementary grep check (no `from research.*` imports outside `research/` and `tests/`) catches
direct cross-layer Python imports that bypass the file-based interface.

`lint-imports` enforces the six import contracts defined in `.importlinter` (one per layer boundary). The `.importlinter` file is the source of truth for the contracts. A violation fails the build.

`check-study-imports` catches a specific high-value violation that `lint-imports` may miss: direct Python imports from `research.families.*`, `research.foundation.*`, or `research.kernels.*` outside of `research/` and `tests/`. These would bypass the file-based cross-layer interface enforced by the import contracts.
