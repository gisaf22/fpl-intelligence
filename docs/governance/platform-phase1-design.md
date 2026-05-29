# Platform Phase 1 — Design Document

**Status:** COMPLETE — implemented 2026-05-28; 909 tests passing (section 5.1 consolidation complete)  
**Date:** 2026-05-27  
**Owner:** Lead Platforms

---

## Capabilities

Assessed against `docs/architecture/platform-capabilities.md`.

| Capability    | Status | Notes |
|---|---|---|
| Determinism   | ✓ | No logic changes — existing determinism preserved |
| Observability | ✓ | Run manifest per build: per-layer status, row counts, timing, validation results |
| Contracts     | ✓ | Pandera `FEAT_SCHEMA` with `strict=False` at feat boundary (feat output includes all spine columns; governed subset enforced); `FEATURE_REGISTRY` links every column to its gate decision |
| Lineage       | ~ | Source db hash + per-layer fingerprint in manifest; row-level lineage deferred — not required at current scale |
| Idempotency   | ✓ | Pipeline runner skips layers whose source hash is unchanged; re-runs are safe |
| Testability   | ✓ | Shared fixtures in conftest; each layer independently testable without live DB; V-3 contract preserved |
| Operability   | ~ | CLI entry point added (`python -m dal.pipeline build`); error code vocabulary documented; error message quality reviewed at implementation |
| Evolvability  | ~ | Downstream governance tests already enforced; schema versioning (consumer reads stale schema) deferred |

---

## 1. Problem statement

The current system grew research-first and retrofitted platform concerns after the fact. This
produced three specific friction points:

1. **DAL layer blur** — `dal/curated/` (spine) and `dal/state/` (features) are siblings with no
   visible contract between them; the pipeline order is discoverable only by reading both.

2. **Scattered contracts** — `DTYPES`, `NULL_RULES`, `SPINE_COLS`, `_GOVERNED_ROLLING_COLS` are
   separate frozensets/dicts spread across files. The governed column set in
   `player_gameweek_state.py` references gate decisions via inline comments only; the link is
   not structural.

3. **No pipeline observability** — there is no way to ask "when did we last build features, did
   any validation fail, how has row count changed?" without re-running the pipeline.

Phase 1 solves these three problems without touching the research methodology or the validation
logic that is already correct and tested.

---

## 2. Code style principles

These apply to all Phase 1 code and to any existing code touched during Phase 1.

**No inner `def` or inner `class`.** Every named function and class is a module-level symbol —
independently importable, independently testable, visible in stack traces. A `def` nested inside
another `def` hides its logic and cannot be unit tested in isolation. Pandera's `DataFrameModel`
requires a `class Config` inner class — use `pa.DataFrameSchema` instead, which takes `strict`
as a constructor argument.

Lambdas are fine for simple single-expression transforms (e.g. `lambda x: x.shift(1).rolling(3).mean()`
passed to `groupby.transform`). They are expressions, not hidden definitions. Avoid lambdas
only when the logic branches, spans multiple steps, or is reused in three or more places — at
that point it deserves a name.

**Every architectural decision is stated and defensible.** A new engineer reading any module
should be able to answer: what does this layer produce, what contract does it enforce, and why?
Inline comments are not the mechanism — module-level docstrings, contracts, and schemas are.

---

## 3. What Phase 1 is NOT

- Not a DuckDB or Parquet migration — SQLite + pandas is the permanent choice at this scale
- Not a replacement of `dal/validation/` modules — they are correct and tested
- Not a scheduler or orchestration layer
- Not a prediction or serving layer
- Not a web interface

---

## 4. Changes

### 4.1 Directory rename — pipeline order readable from structure

**The `int` constraint:** `dal/int/` is an invalid Python package name — `int` is a builtin.
`from dal.int import ...` would shadow it. The prefix convention applies to filenames, not all
directory names.

Rule: rename directories where the current name obscures meaning; use dbt-style prefixes in
filenames throughout.

| Current dir | Target dir | Filename convention | Rationale |
|---|---|---|---|
| `dal/staging/` | `dal/staging/` | `stg_*.py` | Already clear; prefix in filenames |
| `dal/intermediate/` | `dal/intermediate/` | `int_*.py` | Already clear; prefix in filenames |
| `dal/curated/` | `dal/fct/` | `fct_*.py` | Fact table: what happened each GW |
| `dal/state/` | `dal/feat/` | `feat_*.py` | Derived features: what we infer |
| `dal/prepared/` | `dal/mart/` | `mart_*.py` | Analytical mart: study-ready dataset |
| `dal/validation/` | unchanged | unchanged | Cross-cutting, no rename needed |

Resulting structure:

```
dal/
  staging/
    stg_entities.py
    stg_schema.py
    stg_transformer.py
  intermediate/
    int_player_fixture.py
    int_fixture_context.py
    int_opponent_context.py
  fct/
    fct_player_gameweek.py      ← was player_gameweek_spine.py
    fct_gameweek_context.py     ← was gameweek_context.py
    fct_contracts.py
  feat/
    feat_player_gameweek.py     ← was player_gameweek_state.py
    feat_schema.py              ← new: Pandera schema (see 4.2)
    feat_contracts.py
  mart/
    mart_analytical.py          ← was analytical_dataset.py
  validation/                   ← unchanged
  access.py                     ← unchanged; public function names stable (see 4.5)
  pipeline.py                   ← new (see 4.4)
  reproducibility.py            ← unchanged; integrated into pipeline runner (see 4.4)
  contracts.py                  ← grain keys updated to new layer names
  config.py                     ← unchanged
  exceptions.py                 ← error code vocabulary added (see 4.6)
```

Import paths read naturally:

```python
from dal.fct.fct_player_gameweek import build_player_gameweek
from dal.feat.feat_player_gameweek import build_player_gameweek_features
from dal.feat.feat_schema import FEAT_SCHEMA
```

The pipeline order `staging → intermediate → fct → feat → mart` is readable from directory names.
The two meaningful renames are `curated → fct` and `state → feat`; `staging` and `intermediate`
are already clear.

**Migration order:** Execute in layers — one step, suite green, then next:

1. `dal/` internal imports
2. `dal/contracts.py` grain key strings
3. `tests/`
4. `intelligence/`
5. `signals/`
6. `studies/`
7. `examples/quickstart.py`

Each step: rename, update imports, `pytest`, green before proceeding.

### 4.2 Pandera schema at the `feat` layer boundary

**Why Pandera, not Pydantic:** Pydantic validates records/objects and is already used in
fpl-ingest for that purpose (API responses, config). Using it here for DataFrame validation would
mean iterating rows or converting to dicts — the wrong tool for tabular data. Pandera is built
for DataFrames and is the right tool at layer boundaries in an analytical pipeline. Using both
across the two projects demonstrates judgment, not redundancy.

**Scope:** Pandera is used *only* at the `feat` layer output boundary. The existing
`dal/validation/` modules are not replaced — they handle business logic (BGW semantics, DGW
correctness, join safety) that Pandera cannot express as cleanly. The two coexist.

```python
# dal/feat/feat_schema.py
from dataclasses import dataclass
import pandera as pa

# pa.DataFrameSchema — not pa.DataFrameModel — to avoid the inner `class Config` pattern.
# strict=True is a constructor argument, not a nested class attribute.
FEAT_SCHEMA = pa.DataFrameSchema(
    columns={
        "player_id":            pa.Column(int,   nullable=False),
        "gw":                   pa.Column(int,   nullable=False),
        "xgi_roll3":            pa.Column(float, nullable=True),
        "xgi_roll5":            pa.Column(float, nullable=True),
        "xgc_roll3":            pa.Column(float, nullable=True),
        "xgc_roll5":            pa.Column(float, nullable=True),
        "clean_sheets_roll3":   pa.Column(float, nullable=True),
        "clean_sheets_roll5":   pa.Column(float, nullable=True),
        "goals_conceded_roll3": pa.Column(float, nullable=True),
        "goals_conceded_roll5": pa.Column(float, nullable=True),
        "minutes_roll3":        pa.Column(float, nullable=True),
        "minutes_roll5":        pa.Column(float, nullable=True),
        "minutes_roll8":        pa.Column(float, nullable=True),
        "minutes_trend":        pa.Column(object, nullable=True),
        "fixture_context":      pa.Column(str, pa.Check.isin(["BGW", "SGW", "DGW"])),
    },
    strict=True,  # replaces _GOVERNED_ROLLING_COLS frozenset + RuntimeError assertion
)


@dataclass
class FeatureRecord:
    gate: str             # lens study gate that approved this column
    scope: str            # Individual | Team | Match
    positions: list[str]  # positions for which this column is approved
    status: str           # APPROVED | CONDITIONAL


# Approval records — the link between schema column and gate decision.
# Replaces _COLUMN_META. Every column in FEAT_SCHEMA must have an entry here.
FEATURE_REGISTRY: dict[str, FeatureRecord] = {
    "xgi_roll3": FeatureRecord(
        gate="LENS-FORM FORM-001",
        scope="Individual",
        positions=["DEF", "MID"],
        status="APPROVED",
    ),
    "minutes_roll8": FeatureRecord(
        gate="LENS-AVAIL AVAIL-003",
        scope="Individual",
        positions=["DEF", "MID"],
        status="APPROVED",
    ),
    # ... all 13 columns
}
```

`FEAT_SCHEMA` is a module-level constant. `strict=True` means any column produced by
`feat_player_gameweek.py` that is not declared here raises a `SchemaError` at validation time.
`FEATURE_REGISTRY` replaces `_COLUMN_META`. Together they are the single source of truth: what
columns exist, what types they must be, and which gate decision authorised them.

### 4.3 Run manifest — one JSON file per pipeline build

Every pipeline build writes a manifest alongside the source db. Per-layer fingerprints are
computed by `dal/reproducibility.py:compute_spine_fingerprint()` — already exists, integrated
here rather than invented again.

```json
{
  "run_id": "gw38_20260528_143022",
  "built_at": "2026-05-28T14:30:22Z",
  "source_db_path": "~/.fpl/fpl.db",
  "source_db_hash": "sha256:abc123...",
  "gw_range": [1, 38],
  "layers": {
    "staging":      {"rows": 61200, "duration_ms": 88,  "status": "OK", "fingerprint": "sha256:..."},
    "intermediate": {"rows": 61200, "duration_ms": 124, "status": "OK", "fingerprint": "sha256:..."},
    "fct":          {"rows": 44820, "cols": 52,  "duration_ms": 312, "status": "OK", "fingerprint": "sha256:..."},
    "feat":         {"rows": 44820, "cols": 82,  "duration_ms": 88,  "status": "OK", "fingerprint": "sha256:..."},
    "mart":         {"rows": 41040, "cols": 82,  "duration_ms": 44,  "status": "OK", "fingerprint": "sha256:..."}
  },
  "validation": {
    "fct":  {"grain": "PASS", "completeness": "PASS", "bgw": "PASS", "dgw": "PASS"},
    "feat": {"grain": "PASS", "pandera_schema": "PASS"}
  }
}
```

If a layer fails validation, the manifest records `"status": "FAIL"` with the `error_code` and
message, and subsequent layers do not run. The manifest path is derived from `FPL_DB_PATH`.

### 4.4 Pipeline runner — `dal/pipeline.py`

Single responsibility: orchestrate a build in layer order, run pre-flight checks, write the
manifest, manage the source-hash cache.

```python
# dal/pipeline.py

def validate_data_freshness(db_path: Path, gw: int) -> None:
    """Pre-flight check: source DB contains data for the target GW.

    Called automatically by build() before any layer runs. Raises DataFreshnessError
    if the GW is absent or if prior-GW player_histories are missing.

    Moved here from dal/access.py — this is a pipeline concern, not an access concern.
    dal/access.py consumers (get_curated_spine etc.) read already-built data and do
    not need a freshness check.
    """
    ...

def build(db_path: Path = DB_PATH, force: bool = False) -> dict:
    """Run all layers in order. Returns the manifest dict."""
    ...

def build_spine(db_path: Path, force: bool = False) -> pd.DataFrame: ...
def build_features(spine: pd.DataFrame, force: bool = False) -> pd.DataFrame: ...
def build_dataset(features: pd.DataFrame, cutoff_gw: int) -> pd.DataFrame: ...
```

Cache rule: if the manifest for the current `source_db_hash` shows `"status": "OK"` for that
layer, return cached. `force=True` bypasses.

CLI: `python -m dal.pipeline build` — runs `build()`, prints manifest summary to stdout.

**`validate_data_freshness` moved from `dal/access.py` to here.** `dal/access.py` is a read
surface — consumers call it to retrieve already-built data. Pre-flight checks belong to the
build surface. Consumers who call `get_curated_spine()` directly bypass the check by design;
they are reading already-validated output.

### 4.5 `dal/access.py` — public API, names unchanged

Public function names are a stable contract for all downstream consumers. Internal rename does
not require public rename.

| Function | Status | Change |
|---|---|---|
| `get_curated_spine(db_path)` | Keep, name unchanged | Docstring updated to reference `dal/fct/` |
| `get_state_features(spine)` | Keep, name unchanged | Docstring updated to reference `dal/feat/` |
| `validate_data_freshness(db_path, gw)` | **Remove** — moved to `dal/pipeline.py` | Consumers import from `dal.pipeline` |

### 4.6 Error code vocabulary — `dal/exceptions.py`

`DALContractViolation` already has an `error_code` field. The valid codes are undocumented.
Add them as constants so consumers catching the exception know what to expect:

```python
# dal/exceptions.py

class ErrorCode:
    GRAIN_DUPLICATE    = "GRAIN_DUPLICATE"    # duplicate (player_id, gw) pairs
    ROW_COUNT          = "ROW_COUNT"          # n_players × n_gws invariant violated
    MISSING_COLUMNS    = "MISSING_COLUMNS"    # required columns absent from layer output
    DTYPE_MISMATCH     = "DTYPE_MISMATCH"     # column type does not match declared dtype
    NULL_VIOLATION     = "NULL_VIOLATION"     # never_null column contains nulls
    JOIN_SAFETY        = "JOIN_SAFETY"        # row loss or fan-out detected after join
    TIME_CONTINUITY    = "TIME_CONTINUITY"    # gap in per-player GW sequence
    FUTURE_DATA        = "FUTURE_DATA"        # performance data present for future GW
    BGW_VIOLATION      = "BGW_VIOLATION"      # BGW row has non-null performance value
    DGW_VIOLATION      = "DGW_VIOLATION"      # DGW row has incorrect fixture counts
```

All `DALContractViolation` raises throughout `dal/` must use one of these constants.

---

## 5. Test harness

### 5.1 What to cut or consolidate

| File | Action | Reason |
|---|---|---|
| `test_dal_grain.py` | Cut | Fully covered by `test_curated_spine.py`, `test_validation_modules.py`, and the assertion inside `build_player_gameweek_spine` |
| `test_state_stabilization.py` | Cut | Subsumed by `test_curated_state_boundary.py` which tests the same properties with more cases |
| `test_dal_bgw.py` + `test_dal_nulls.py` | Merge into `test_dal_bgw_dgw.py` | Both hit live DB to test NULL semantics from overlapping angles |
| `test_state.py` | Reduce to 2–3 integration smoke tests | Governance lock and column assertions are done better in `test_state_architecture.py` |
| `test_dal_invariants.py` | Reduce to 2 | Column contract and dtype checks already unit-tested in `test_validation_modules.py`; keep only no-future-data and column set smoke tests |

### 5.2 Shared fixtures — `conftest.py`

Every test file currently builds its own synthetic DataFrame. Extract to shared fixtures:

```python
# tests/conftest.py

@pytest.fixture
def db_path() -> Path:
    return Path(__file__).parent / "fixtures" / "test.db"

@pytest.fixture
def minimal_spine_df() -> pd.DataFrame:
    """Minimal valid (player_id, gw) spine for unit tests. No live DB required."""
    ...

@pytest.fixture
def minimal_feat_df(minimal_spine_df) -> pd.DataFrame:
    """Minimal spine + all 13 governed feature columns. No live DB required."""
    ...
```

All new unit tests use these fixtures. Existing synthetic factories in test files remain until
their test file is touched; migrate on contact.

### 5.3 New tests to add

**`test_feat_schema.py`** — unit, no live DB

```python
def test_valid_feat_df_passes_schema(minimal_feat_df)
def test_extra_column_raises_schema_error(minimal_feat_df)       # strict=True enforcement
def test_wrong_column_type_raises_schema_error(minimal_feat_df)
def test_invalid_fixture_context_raises_schema_error(minimal_feat_df)
def test_every_schema_column_has_registry_entry()                # FEAT_SCHEMA ↔ FEATURE_REGISTRY
def test_every_registry_entry_has_schema_column()                # reverse direction
```

Capabilities: **Contracts**, **Evolvability**

**`test_pipeline.py`** — unit, no live DB

```python
def test_manifest_written_after_successful_build()
def test_manifest_contains_required_fields()        # run_id, source_db_hash, gw_range, layers
def test_manifest_records_per_layer_fingerprint()   # reproducibility.py integration
def test_cache_hit_skips_rebuild()                  # same hash → no rebuild
def test_force_true_rebuilds_despite_cache()
def test_failed_layer_stops_pipeline()              # FAIL in manifest, next layer not run
def test_failed_layer_records_error_code()          # ErrorCode constant, not bare string
def test_manifest_hash_is_stable()                  # same source → same hash
def test_validate_data_freshness_raises_on_missing_gw()
def test_validate_data_freshness_raises_on_stale_histories()
```

Capabilities: **Observability**, **Idempotency**, **Operability**, **Lineage**

**`test_layer_isolation.py`** — unit, no live DB

```python
def test_fct_builds_from_synthetic_input(minimal_spine_df)
def test_feat_builds_from_minimal_spine(minimal_spine_df)
def test_mart_builds_from_minimal_feat_df(minimal_feat_df)
```

Capabilities: **Testability** — suite runs fully without `~/.fpl/fpl.db`

**`test_error_codes.py`** — unit

```python
def test_all_error_code_constants_are_strings()
def test_dal_contract_violation_accepts_error_code()
def test_grain_duplicate_uses_correct_error_code()   # parametrized per code
```

Capabilities: **Operability**

### 5.4 Pytest configuration — `pyproject.toml`

Add `unit` marker alongside existing `integration` marker:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests that require a live database (deselect with '-m not integration')",
    "unit: marks tests that run without any external dependencies",
]
```

Add `pandera` to main dependencies:

```toml
dependencies = [
    ...
    "pandera>=0.19",
]
```

Standard invocations:
- `pytest -m unit` — fast, no DB required, CI-safe
- `pytest -m integration` — requires `~/.fpl/fpl.db`
- `pytest` — full suite

---

## 6. What stays unchanged

- All `dal/validation/` modules — correct, tested, no logic changes
- All business validation logic inside build functions — no logic changes
- `dal/access.py` public function names — `get_curated_spine`, `get_state_features` stable
- SQLite as source — permanent choice at this scale
- pandas as the in-memory layer
- The signal registry / lens methodology — entirely separate concern

---

## 7. Document updates required on completion

These must be done as the final step of Phase 1 — not as an afterthought:

1. ~~`docs/architecture/DAL_CONTRACT.md`~~ — deleted; replaced by `docs/adr/012-dal-design-rationale.md` and code contracts in `dal/fct/fct_contracts.py`
2. `CONTEXT.md` section 7 (DAL architecture summary) — update layer names and entry points
3. `CONTEXT.md` section 8 (naming conventions) — update "DAL target names" from deferred to done
4. `dal/access.py` docstrings — update references from `dal/curated/`, `dal/state/` to `dal/fct/`, `dal/feat/`

---

## 8. Success criteria

Phase 1 is complete when:

1. ✅ Directory names and filenames follow the agreed convention (`fct/`, `feat/`, `mart/`, `stg_*`, `int_*`, `fct_*`, `feat_*`, `mart_*`)
2. ✅ `FEAT_SCHEMA` in `dal/feat/feat_schema.py` is the single source of truth for governed feature columns; `strict=False` (feat output includes all spine columns; governed subset validated)
3. ✅ `FEATURE_REGISTRY` maps every schema column to its gate approval record
4. ✅ No inner `def` or inner `class` anywhere in `dal/`
5. ✅ `python -m dal.pipeline build` runs end-to-end and produces a manifest JSON with per-layer fingerprints
6. ✅ `validate_data_freshness` lives in `dal/pipeline.py`; removed from `dal/access.py`
7. ✅ `ErrorCode` constants documented in `dal/exceptions.py`; all `DALContractViolation` raises use them
8. ✅ `pandera>=0.19` in `pyproject.toml` dependencies; `unit` marker declared in pytest config
9. ✅ Migration executed in order: `dal/` → `tests/` → `intelligence/` → `signals/` → `studies/` → `examples/`; suite green at each step
10. ✅ All existing tests pass; new tests in `test_feat_schema.py`, `test_pipeline.py`, `test_layer_isolation.py`, `test_error_codes.py`
11. ✅ `DAL_CONTRACT.md` updated (subsequently deleted 2026-05-28 — replaced by ADR 012 + code contracts); `CONTEXT.md` sections 3, 5, 7 and 8 updated

---

## 9. What this does NOT solve

- `dal/validation/` modules remain bespoke — Pandera is at the boundary only
- Signal registry remains YAML
- No scheduler — manual `python -m dal.pipeline build`
- Schema versioning (consumer reads stale schema) — deferred
- No web interface
