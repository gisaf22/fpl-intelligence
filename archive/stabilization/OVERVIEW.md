# DAL Stabilization Overview

**Branch:** `stabilization/dal-hardening`  
**Status:** Complete — all six waves executed, 331 tests passing as of May 2026  

---

## What "stable" means

The DAL is stable when every call to `build_player_gameweek_spine()` and `build_player_gameweek_state()` produces output that satisfies all five dimensions simultaneously:

| Dimension | Definition |
|---|---|
| **Correctness** | Every value at every `(player_id, gw)` cell represents the true historical fact — no temporal leakage, no aggregation distortion, no silent substitution |
| **Determinism** | Two runs on the same DB produce byte-identical output regardless of SQLite row order, process environment, or within-session state |
| **Contract completeness** | Every column has a declared dtype, null rule, aggregation rule, and at least one enforcement path in the live build |
| **Robustness** | Any contract violation raises immediately at the layer where it occurs with enough diagnostic information to identify the root cause without a debugger |
| **Reproducibility** | Historical rows for GW ≤ N-1 are unchanged when GW N data is added, provided the source DB has not made retroactive corrections |

These dimensions are distinct. A pipeline can be deterministic and still produce reproducibly wrong output (SC-1, SC-2, SC-3 were exactly this). The stabilization addressed them in order of analytical risk: correctness first, then determinism, then enforcement, then architecture.

---

## Stabilization philosophy

Every code change during stabilization required a failing test committed first. The failure was the proof that the violation existed. No fix was committed without a corresponding test that demonstrated the defect before the fix and confirmed the correction after.

Waves were ordered by analytical risk severity, not implementation convenience. Analytical correctness (Wave 1) blocked everything else — no research could proceed on a pipeline with silent look-ahead leakage or incorrect DGW aggregation.

---

## Wave summary

| Wave | Objective | Risks addressed | Status |
|---|---|---|---|
| **Wave 1** — Corruption Blockers | Eliminate silent analytical corruption | SC-1, SC-2, SC-3, SC-4, SC-11 | Complete |
| **Wave 2** — Contract Enforcement | Ensure every declared contract is enforced in the live build | SC-5, SC-6, SC-8, V-1, V-2, V-3 | Complete |
| **Wave 3** — Determinism Hardening | Guarantee byte-identical output across runs | D-1, SC-9, F-1, F-2 | Complete |
| **Wave 4** — Invariant Expansion | Add missing invariants; formalize state layer contract | SC-13, SC-7, SC-10, SC-14, SC-15 | Complete |
| **Wave 5** — Architecture Cleanup | Remove structural confusion and dead code | A-1, A-2, A-3 | Complete |
| **Wave 6** — Observability | Full diagnosability from log output; environment overrides; reproducibility artifact | O-1 through O-6 | Complete |

Wave 1 was a hard gate — no lens study could proceed until all five corruption blockers were fixed. The most critical was SC-1 (`minutes_trend` look-ahead), which contaminated every rolling availability signal with future data.

---

## Document guide

| Document | What it contains |
|---|---|
| [docs/architecture/DAL_CONTRACT.md](../architecture/DAL_CONTRACT.md) | Authoritative behavioral contract — grain definitions, aggregation rules, null semantics, dtype guarantees, invariants, FIRST_COLS semantics, BGW/DGW rules, validation module specs |
| [docs/architecture/SYSTEM_CONTEXT.md](../architecture/SYSTEM_CONTEXT.md) | System overview — layers, consumers, document hierarchy |
| [docs/stabilization/EXECUTION_QUEUE.md](EXECUTION_QUEUE.md) | All six waves as ordered work items — prerequisites, blast radius, test specs, validation checklists, rollback notes |
| [docs/stabilization/RISKS.md](RISKS.md) | Master risk table — all 31 identified risks with severity, wave, and description |
| [docs/stabilization/TEST_COVERAGE.md](TEST_COVERAGE.md) | Invariant-to-validator mapping with test status, required fail-case tests, required pass-case tests |
| [docs/adr/007-bgw-team-semantics.md](../adr/007-bgw-team-semantics.md) | Decision note: BGW team_id temporal rule |
| [docs/adr/008-dgw-aggregation-rules.md](../adr/008-dgw-aggregation-rules.md) | Decision note: DGW aggregation and TGW non-support |
| [docs/adr/009-first-cols-ordering.md](../adr/009-first-cols-ordering.md) | Decision note: FIRST_COLS semantic classification |

---

## Definition of done

The subsystem was declared stable when all of the following held simultaneously:

### Test coverage
- Every validation function has at least one failing test and one passing test
- Every `FIRST_COLS` column classified in `FIRST_COL_SEMANTICS`; `invariant_per_gw` columns have enforcement tests
- Every `_ROLL_COLS` column has a look-ahead test confirming GW N's value does not depend on GW N's performance
- Golden DB produces exact known-value outputs for spine and state
- Reproducibility test passes: two-run exact equality verified by fingerprint hash

### Invariant coverage (all enforced in live build)
- Grain uniqueness at fixture-grain, GW-grain (curated), GW-grain (state)
- Row count = n_players × n_gws exactly
- Time continuity per player
- BGW correctness (fixture_count=0, performance=NULL, fdr=NULL, was_home=NULL)
- DGW correctness (fixture_count=2, home+away=2, fdr ordering valid)
- Null semantics (all SPINE_COLS covered)
- Column contract (exact SPINE_COLS set, exact DTYPES)
- Future data prohibition
- Row completeness
- Join safety at every merge site
- `invariant_per_gw` assertion before aggregation
- Lag-1 convention for all state rolling windows

### Contract completeness
- Every column in `SPINE_COLS` has an entry in `DTYPES`, `NULL_RULES`, and `FIRST_COL_SEMANTICS` or `SUM_COLS`
- Every column in `STATE_COL_CONTRACTS` has declared `causality`, `warmup_gws`, `min_obs_for_reliability`
- `opponent_team_id` declared in intermediate-layer contract
- TGW non-support documented with clear error message
- DGW summation semantics for FPL metrics documented with normalization convention
- Source mutation policy (Option A) documented
- BGW team_id semantic rule documented
- Append-monotonic vs deterministic vs source-stable guarantees documented

### Reproducibility
- Two-run spine fingerprint identical (hash, row count, schema)
- Historical rows unchanged when new GW data added (append-monotonic, subject to source-stable caveat)
- `FPL_DB_PATH` environment override works for test isolation

### Documentation
- `GRAIN_CONTRACTS` registry exists and covers all DAL layer outputs
- `STATE_COL_CONTRACTS` exists and covers all state layer columns
- `FIRST_COL_SEMANTICS` exists and covers all `FIRST_COLS` entries
- `DAL_CONTRACT.md` reflects all Wave 1–4 semantic decisions
- `CONTEXT.md` updated: `dal/` is the authoritative DAL; `pipeline/` is archived

---

## Deferred items

Items raised during stabilization and explicitly deferred:

| Item | Deferral rationale |
|---|---|
| Unified `COLUMN_CONTRACTS` registry | `DTYPES`, `NULL_RULES`, `FIRST_COLS`, `SUM_COLS`, `PERFORMANCE_COLS` already exist and are enforced. Unification is a significant refactor that could introduce regressions. Revisit after all waves complete. |
| Performance contracts with specific timing targets | Log timing in Wave 6. Enforce thresholds only after the pipeline runs in CI with a stable baseline established. |
| Full `DALValidationSeverity` enum | The FATAL/WARNING/AUDIT three-tier model covers all current cases. A formal enum adds complexity without immediate benefit. Revisit when a structured log aggregator is in use. |
| Structured log ingestion / telemetry | Out of scope for a single-analyst research system. Logging to stderr with structured prefixes is sufficient at current scale. |
