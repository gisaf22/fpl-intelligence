# ADR-013 — Mart Access Interface

**Status:** Active  
**Date:** 2026-05-29  
**Supersedes:** ADR-012-pipeline-entry-point-separation (deferred gap now resolved)  
**Implements:** The "give me data" concern identified in ADR-012 §The Gap

---

## Problem

`dal.access` (deleted in the Platform Phase 1 restructure) was the single-call consumer
interface for the analytical dataset. Its deletion left two problems:

1. No stable named entry point — every caller must reconstruct the 5-layer sequence
   (`staging → intermediate → fct → feat → mart`) themselves.
2. The mart is computed and discarded inside `dal.pipeline.build()` — callers who want the
   analytical dataset pay the full pipeline cost again from scratch, with no single place
   to control how it is produced.

---

## Forces

- **Layer opacity:** callers should not need to know `fct`, `feat`, or the pipeline sequence.
  That knowledge belongs inside the DAL, not scattered across callers.
- **Typed result over raw DataFrame:** a raw `pd.DataFrame` return gives the caller no signal
  about what is in it — no governed columns list, no GW range, no cutoff applied. A typed
  result object makes all of this immediately discoverable.
- **Single responsibility:** `dal.pipeline.build()` answers "did the pipeline run cleanly?"
  (CI, ops, pre-flight). It must not be conflated with "give me data" (analytics, lenses,
  scoring). These are different callers with different needs.
- **No premature persistence:** Parquet-backed `load()` is the right long-term answer for
  repeated analytics sessions. It is not the right answer now — mart persistence semantics
  (as-of GW, schema evolution, invalidation) are not yet defined. Introducing it before those
  semantics exist creates more risk than value.

---

## Options

**Option A — `get_mart(db_path) -> pd.DataFrame`**  
Simplest. Runs the pipeline, returns the mart DataFrame.  
Rejected: untyped, no metadata surface (signals, GW range, cutoff). Callers must
re-derive `GOVERNED_SIGNAL_COLUMNS` and `data_cutoff_gw` themselves — the same
knowledge-scattering problem as before.

**Option B — `get_analytics_dataset(db_path, data_cutoff_gw) -> MartResult`** *(chosen)*  
Returns a frozen dataclass carrying `mart`, `signals`, `gw_range`, `data_cutoff_gw`.
Callers destructure what they need. Governed signal list is embedded in the result —
callers never need to import `FEATURE_REGISTRY` or `GOVERNED_SIGNAL_COLUMNS` directly.

**Option C — Parquet persistence with `load()`**  
`build()` writes `mart_analytical.parquet`; `load(db_path)` reads it, rebuilding on
source-hash change. Right eventual answer for repeated sessions. Deferred: requires
defining what "as-of GW" means for the file, how schema changes invalidate it, and
where the file lives. Out of scope until a second analytics caller exists that makes
rebuild cost measurable.

---

## Decision

**Option B.** `get_analytics_dataset(db_path, data_cutoff_gw=None) -> MartResult`

`MartResult` is a `frozen=True` dataclass:

```python
@dataclass(frozen=True)
class MartResult:
    mart: pd.DataFrame          # full analytical dataset at (player_id, gw) grain
    signals: tuple[str, ...]    # governed signal columns (from FEATURE_REGISTRY)
    gw_range: tuple[int, int]   # (min_gw, max_gw) inclusive bounds in mart
    data_cutoff_gw: int         # GW at which rows were cut off
```

`frozen=True` prevents field reassignment on the result container. The `mart` DataFrame
itself remains mutable — callers who need a snapshot copy it explicitly.

`data_cutoff_gw=None` defaults to the max GW in the FCT spine. Callers doing retrospective
analysis pass an explicit cutoff to reproduce a prior-GW dataset.

---

## Caller contract

```python
from dal import get_analytics_dataset

result = get_analytics_dataset(db_path)
df = result.mart                    # full dataset
signals = result.signals            # governed columns — use for feature selection
min_gw, max_gw = result.gw_range    # GW bounds actually present
```

Callers import from `dal` directly. `dal.mart.mart_access` is an internal module —
its path is not part of the stable interface.

---

## What this replaces

| Deleted | Replacement |
|---|---|
| `dal.access.get_state_features(db_path)` | `dal.get_analytics_dataset(db_path)` |
| `dal.access.get_curated_spine(db_path)` | No direct replacement. Spine columns are present in `MartResult.mart`. Callers who need the raw FCT spine call `build_player_gameweek_spine()` directly. |

---

## Separation of concerns (with pipeline.build)

| Function | Caller | Returns | Concern |
|---|---|---|---|
| `dal.get_analytics_dataset()` | lenses, scoring, EDA | `MartResult` | Give me data |
| `dal.pipeline.build()` | CI, ops, pre-flight | manifest dict | Did it run cleanly? |

`pipeline.build()` is not the analytics entry point and must not become one. The mart
DataFrame it constructs internally is discarded by design — its job is to validate the
pipeline end-to-end, not to deliver data.

---

## When to revisit

- A second analytics caller appears that makes per-call rebuild cost measurable
- Mart schema evolution requires invalidating cached results (triggers Option C)
- `data_cutoff_gw` semantics need to be stable across pipeline runs (Parquet as-of snapshot)
