# Risk Register

All risks identified during DAL stabilization, with severity, wave assignment, and description.

**Status:** All 31 risks addressed. Waves 1–6 complete as of May 2026.

---

## Risk taxonomy

**Severity:**
- **Critical** — silent analytical corruption; invalidates research outputs
- **High** — potential for undetected data errors or validation failures
- **Medium** — structural or operational gap that reduces system quality
- **Low** — minor issue with a documented mitigation or workaround

**Category prefixes:**
- `SC` — correctness (silent corruption or incorrect aggregation)
- `V` — validation (enforcement gap)
- `D` — determinism
- `F` — FIRST_COLS semantics
- `A` — architecture
- `O` — observability

---

## Wave 1 — Corruption Blockers (Critical/High)

| ID | Description | Severity | Status |
|---|---|---|---|
| SC-1 | `minutes_trend` includes current-GW look-ahead via missing `shift(1)` — all availability signals contaminated with future data | **Critical** | Fixed Wave 1 |
| SC-2 | BGW `team_id` backfilled from latest-GW attributes rather than pre-BGW team — temporal leakage for transferred players | **Critical** | Fixed Wave 1 |
| SC-3 | `goals_conceded` uses `mean` instead of `sum` for DGW teams — defensive weakness underestimated by 50% for any DGW team | **Critical** | Fixed Wave 1 |
| SC-4 | `opponent_team_id` column missing — module raises `KeyError` at runtime before any defensive context can be computed | **Critical** | Fixed Wave 1 |
| SC-11 | Missing GW context logs a warning then proceeds, guaranteeing a downstream validation failure; should raise immediately | **Critical** | Fixed Wave 1 |

**Wave 1 analytical impact:** SC-1 contaminated every rolling availability signal with future data. SC-2 contaminated team context for any player who transferred clubs during a BGW GW. SC-3 systematically underestimated defensive weakness for DGW teams. SC-4 caused a runtime crash. SC-11 allowed partial pipeline state to persist silently.

---

## Wave 2 — Contract Enforcement (High/Medium)

| ID | Description | Severity | Status |
|---|---|---|---|
| SC-5 | `validate_bgw_correctness` uses `!= 0` on nullable types — `pd.NA != 0` returns `pd.NA` (falsy), silently misses `pd.NA` violations | **High** | Fixed Wave 2 |
| SC-6 | `validate_no_future_data` uses `!= 0` on nullable types — same nullable comparison bug | **High** | Fixed Wave 2 |
| SC-8 | 8 GW context columns absent from `DTYPES` — never cast or type-checked, allowing silent dtype drift | **High** | Fixed Wave 2 |
| V-1 | `validate_column_contract` exists but is never called in the live build — column contract unenforced | **High** | Fixed Wave 2 |
| V-2 | `validate_row_completeness` exists but is never called in the live build — spine completeness unenforced | **Medium** | Fixed Wave 2 |
| V-3 | `invariants.py` imports from `dal/curated/contracts.py` — upward coupling prevents validation layer from being tested independently | **Medium** | Fixed Wave 2 |

---

## Wave 3 — Determinism Hardening (High)

| ID | Description | Severity | Status |
|---|---|---|---|
| D-1 | No `ORDER BY` in staging SQL — row order is filesystem-defined; two runs on the same DB can produce different row ordering | **High** | Fixed Wave 3 |
| SC-9 | `FIRST_COLS` aggregation result depends on staging row order — "first" without a stable sort is non-deterministic | **High** | Fixed Wave 3 |
| F-1 | `FIRST_COLS` semantic type undeclared — "lowest fixture_id" is a hidden aggregation policy with no contract backing | **High** | Fixed Wave 3 |
| F-2 | `invariant_per_gw` columns not asserted for within-GW invariance — upstream API changes can silently violate the assumption | **High** | Fixed Wave 3 |

---

## Wave 4 — Invariant Expansion (Medium/Low)

| ID | Description | Severity | Status |
|---|---|---|---|
| SC-13 | `fixture_context` maps `is_bgw=True` rows to `"SGW"` — BGW rows are invisible to any lens filter on `fixture_context == "SGW"` | **Medium** | Fixed Wave 4 |
| SC-7 | `influence`, `creativity`, `threat`, `ict_index` summed for DGW — semantically intentional but undocumented; normalization convention not stated | **Medium** | Fixed Wave 4 (doc) |
| SC-10 | `fixture_count >= 2` used for DGW detection in some places but validation requires exactly 2 — TGW would silently mislabel as DGW | **Medium** | Fixed Wave 4 (doc + error msg) |
| SC-14 | `validate_xgc_001` checks GK only — defenders with inconsistent xgc silently pass | **Low** | Fixed Wave 4 |
| SC-15 | `min_periods=1` produces single-observation means with no flag for consumers; research using roll3 at GW 2 may not know it has only 1 observation | **Low** | Fixed Wave 4 (doc) |

---

## Wave 5 — Architecture Cleanup (Medium)

| ID | Description | Severity | Status |
|---|---|---|---|
| A-1 | `pipeline/` contains dead code that imports from nonexistent `analysis.source` — source of confusion about which DAL implementation is authoritative | **Medium** | Fixed Wave 5 |
| A-2 | `GrainViolationError` used in `opponent_context.py` — inconsistent exception hierarchy; `DALContractViolation` is the canonical exception | **Medium** | Fixed Wave 5 |
| A-3 | `opponent_context.py` lives in `state/` but operates on intermediate-layer data — misclassified layer creates confusion about concern boundaries | **Medium** | Fixed Wave 5 |

---

## Wave 6 — Observability (Medium/Low)

| ID | Description | Severity | Status |
|---|---|---|---|
| O-1 | No staging-layer logging — entity row counts, column counts, and timing are invisible; unexpected entity sizes go unnoticed | **Medium** | Fixed Wave 6 |
| O-2 | team_id correction logged at `INFO`, not `AUDIT` — corrections are invisible to reconciliation review | **Medium** | Fixed Wave 6 |
| O-3 | `DALContractViolation.layer` is optional — many raises omit it, making triage harder | **Medium** | Fixed Wave 6 |
| O-4 | `DB_PATH` hardcoded to `~/.fpl/fpl.db` — no environment variable override; test isolation requires patching internals | **Low** | Fixed Wave 6 |
| O-5 | No hash-level reproducibility artifact — equality tests only verify shape/content but do not produce a stable fingerprint for archiving | **Low** | Fixed Wave 6 |
| O-6 | No timing instrumentation at layer boundaries — performance regressions are not visible without external profiling | **Low** | Fixed Wave 6 |

---

## Silent failure patterns

These were the most dangerous failure modes because they produced no errors — only wrong results.

| Pattern | Risk IDs | Description |
|---|---|---|
| Look-ahead contamination | SC-1 | Rolling window included current GW performance; prior outputs are analytically invalid |
| Temporal team leakage | SC-2 | BGW rows carried post-BGW team for players who transferred; prior team-context joins are tainted |
| DGW averaging bias | SC-3 | Goals conceded halved for DGW teams; defensive metrics systematically wrong |
| Silent validator bypass | SC-5, SC-6 | `pd.NA != 0` returns falsy NA, not True — violations passed silently through the validator |
| Uncalled validator | V-1, V-2 | Column contract and row completeness validators existed but were never invoked |
| Non-deterministic first | SC-9 | `FIRST_COLS` result depended on staging row order, which SQLite does not guarantee |
| BGW label contamination | SC-13 | BGW rows silently included in "SGW" groups in any `fixture_context == "SGW"` filter |
