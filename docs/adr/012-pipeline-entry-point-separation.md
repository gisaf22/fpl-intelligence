# ADR-012 — Pipeline Entry Point Separation

**Status:** SUPERSEDED by ADR-013  
**Applies to:** `dal/pipeline.py`, all callers of `build()`  
**Raised:** 2026-05-28  
**Resolved:** 2026-05-29 — the analytics entry point gap is closed by ADR-013 (`get_analytics_dataset`). The `build()` → `run()` rename remains deferred.

---

## Problem

`build()` in `dal/pipeline.py` is misnamed. "Build" in software means producing a usable artifact from source. `build()` does not do that — it executes the pipeline, records per-layer status and timing in a manifest JSON, and returns that manifest dict. All DataFrames constructed during execution are discarded.

The name implies the caller gets something back. The caller gets a run record.

---

## Two Distinct Concerns

Currently conflated in a single function:

| Concern | Caller | What it needs | Right name |
|---|---|---|---|
| Did the pipeline run cleanly? | CI, pre-flight checks, ops | run record / manifest | `run()` |
| Give me the analytical dataset | research, lenses, scoring | mart DataFrame | — *(gap)* |

`validate_data_freshness()` already names its concern precisely. `build()` should follow the same standard.

---

## The Gap

There is no DAL-level entry point that answers the analytics question. Every downstream caller — `intelligence/scoring/runner.py`, research notebooks, lenses — re-runs the full 5-layer sequence themselves. The pipeline has no canonical "give me data" call. This means:

- The mart layer in `build()` is computed and immediately discarded (lines 180–186 of `pipeline.py`)
- Any caller that wants the mart pays the full pipeline cost again from scratch
- There is no single place to control how the mart is produced for analytics

---

## Options Considered

**Option A — `build()` returns a `BuildResult` (manifest + DataFrame)**  
Surface the mart that is already being built. Minimal code change; single call.  
Not chosen: `build()` is already used as a CI/validation tool in tests and CLI. Changing its return type is a breaking change. Also couples the health-check concern to data delivery.

**Option B — Persist the mart to Parquet; add `load()`**  
`build()` writes `mart_analytical.parquet` alongside the manifest. `load(db_path)` returns the mart, rebuilding only when the source hash changes.  
Not chosen now: requires managing an additional artifact (staleness, schema evolution, path conventions). The mart's "as-of" semantics need to be defined before introducing a persisted form. This is the right eventual answer for repeated analytics sessions.

**Option C — Keep `build()` as-is; add a separate `get_mart()`**  
`build()` remains the health-check tool. A new `get_mart(db_path)` runs the full sequence and returns `(mart, metadata)`.  
Not chosen now: adds code before the naming problem is resolved. Would be overtaken by Option B when mart persistence is introduced.

---

## Decision

**Deferred.** No code added. The gap is recorded here.

When this is revisited, the work is:
1. Rename `build()` → `run()` — the function name should match what it does
2. Implement Option B (`load()` with Parquet persistence) as the analytics entry point
3. Update all callers of `build()` and update the CLI entry point accordingly

---

## Conditions for Revisiting

- Analytics workflow requires repeated mart access within a session (rebuild cost becomes a friction point)
- A second downstream caller needs the mart beyond the scoring runner
- Mart persistence semantics are clear: what "as-of GW" means, how schema changes invalidate the file

---

## Current Workaround

Callers that need the mart run the pipeline sequence directly:

```python
staged = load_staged_entities(db_path)
player_fixture = get_player_fixture_base(staged)
spine = build_player_gameweek_spine(player_fixture, staged.events)
features = build_player_gameweek_state(spine)
mart = build_prepared_dataset(features, int(spine["gw"].max()))
```

This is the correct pattern until Option B is implemented. It is not a leak — it uses only the DAL public API via `dal.__init__` exports.
