"""DAL pipeline runner — orchestrates the full build and manages the run manifest.

Entry points:
    python -m dal.pipeline run    — build all layers, write mart.parquet + manifest
    python -m dal.pipeline load   — print manifest summary for the last build

Public API:
    run(db_path, force, data_cutoff_gw, mart_path)  → manifest dict
    load(db_path, mart_path)                        → MartResult

Separation of concerns:
    run()  answers "did the pipeline produce a valid mart artifact?"  (CI / ops)
    load() answers "give me the mart DataFrame"                       (analytics / intelligence)

Intelligence and studies must call load() — never the internal layer builders directly.

Risks documented in the design session (2026-05-29):
    - Atomic write: parquet written to .tmp then renamed — live path is never partial
    - Schema invalidation: manifest records mart_schema; load() validates before returning
    - Fail-closed on DALContractViolation: existing parquet deleted before re-raising
    - Stale .tmp cleanup: run() removes any leftover .tmp before starting
    - Concurrent writers: unsupported; single-writer assumption documented
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from dal.config import DB_PATH
from dal.exceptions import DALContractViolation, MartNotBuiltError, MartSchemaError
from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.mart.mart_access import MartResult
from dal.mart.mart_analytical import GOVERNED_SIGNAL_COLUMNS, build_prepared_dataset
from dal.reproducibility import compute_spine_fingerprint
from dal.staging import StagedEntities, load_staged_entities

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _manifest_path(db_path: Path) -> Path:
    return db_path.with_suffix(".manifest.json")


def _mart_path(db_path: Path) -> Path:
    return db_path.with_suffix(".mart.parquet")


def _mart_tmp_path(mart_path: Path) -> Path:
    return mart_path.parent / (mart_path.name + ".tmp")


# ---------------------------------------------------------------------------
# Manifest / schema helpers
# ---------------------------------------------------------------------------


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if path.exists():
        try:
            return json.loads(path.read_text())  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            return None
    return None


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(json.dumps(manifest, indent=2))


def _hash_db(db_path: Path) -> str:
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _normalise_dtype(dtype_str: str) -> str:
    # Parquet round-trips can change the dtype string representation of string
    # columns: pandas writes object, pyarrow reads back as str/string depending on
    # version. Treat all three as equivalent so fingerprints survive the round-trip.
    if dtype_str in ("object", "str", "string"):
        return "string"
    return dtype_str


def _mart_schema_fingerprint(df: pd.DataFrame) -> dict[str, Any]:
    """Column names + normalised dtypes — used as the schema cache-invalidation key."""
    cols = sorted(df.columns.tolist())
    return {
        "columns": cols,
        "dtypes": {col: _normalise_dtype(str(df[col].dtype)) for col in cols},
    }


def _schema_matches(recorded: dict[str, Any], df: pd.DataFrame) -> bool:
    current = _mart_schema_fingerprint(df)
    return (  # type: ignore[no-any-return]
        recorded.get("columns") == current["columns"] and recorded.get("dtypes") == current["dtypes"]
    )


def _cache_valid(existing: dict[str, Any], source_hash: str, mrt_path: Path) -> bool:
    """True only when all four cache-hit conditions hold."""
    if existing.get("source_db_hash") != source_hash:
        return False
    all_ok = all(info.get("status") == "OK" for info in existing.get("layers", {}).values())
    if not all_ok:
        return False
    if not mrt_path.exists():
        return False
    # Older manifests without mart_schema are always cache misses.
    if "mart_schema" not in existing:
        return False
    return True


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------


def run(
    db_path: Path = DB_PATH,
    force: bool = False,
    data_cutoff_gw: int | None = None,
    mart_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Run all layers and write mart.parquet + manifest.json.

    Layer order: staging → intermediate → fct → feat → mart.

    Cache behaviour (force=False):
        Returns the existing manifest immediately if all four hold:
          1. source_db_hash matches the current DB file hash
          2. All layers recorded OK in the manifest
          3. mart.parquet exists at mart_path
          4. mart_schema fingerprint is present in the manifest
        Use force=True after code changes that affect mart output (e.g. new column
        in FEATURE_REGISTRY) without changing the source DB.

    Atomic write:
        mart is written to mart.parquet.tmp then os.rename()'d to mart.parquet.
        A crash mid-write leaves a .tmp but the live parquet is never corrupt.
        Any leftover .tmp from a prior crash is removed at the start of each run.

    Fail-closed on DALContractViolation:
        The existing mart.parquet (if any) is deleted before re-raising so that
        load() cannot return a stale artifact after a contract failure.

    Non-DAL exceptions (unexpected errors in a layer):
        Recorded as FAIL in the manifest; the function returns the manifest dict
        rather than raising. The parquet is NOT written. The previous parquet (if
        any) is left in place — it reflects a prior successful build, not the
        failed one.

    Concurrent writers: unsupported. Two simultaneous run() calls produce
        undefined behaviour. The atomic rename prevents corruption but not a
        stale result from a lost race.

    Args:
        data_cutoff_gw: if None, defaults to the max GW present in the FCT spine.
        mart_path: if None, defaults to db_path with .mart.parquet suffix.
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Source DB not found: {db_path}")

    mpath = manifest_path or _manifest_path(db_path)
    mrt_path = mart_path or _mart_path(db_path)
    tmp_path = _mart_tmp_path(mrt_path)

    # Remove any stale .tmp from a prior crash before doing anything else.
    if tmp_path.exists():
        tmp_path.unlink()

    source_hash = _hash_db(db_path)
    existing = _load_manifest(mpath)
    if not force and existing and _cache_valid(existing, source_hash, mrt_path):
        return existing

    now = datetime.now(UTC)
    manifest: dict[str, Any] = {
        "run_id": now.strftime("run_%Y%m%d_%H%M%S"),
        "built_at": now.isoformat(),
        "source_db_path": str(db_path),
        "source_db_hash": source_hash,
        "mart_path": str(mrt_path),
        "layers": {},
    }

    # --- staging ---
    t0 = time.perf_counter()
    try:
        staged: StagedEntities = load_staged_entities(db_path)
        manifest["layers"]["staging"] = {
            "rows": len(staged.player_histories),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation as exc:
        manifest["layers"]["staging"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        if mrt_path.exists():
            mrt_path.unlink()
        raise
    except Exception as exc:
        manifest["layers"]["staging"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- intermediate ---
    t0 = time.perf_counter()
    try:
        player_fixture = get_player_fixture_base(staged)
        manifest["layers"]["intermediate"] = {
            "rows": len(player_fixture),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation as exc:
        manifest["layers"]["intermediate"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        if mrt_path.exists():
            mrt_path.unlink()
        raise
    except Exception as exc:
        manifest["layers"]["intermediate"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- fct ---
    t0 = time.perf_counter()
    try:
        spine = build_player_gameweek_spine(player_fixture, staged.events)
        fingerprint = compute_spine_fingerprint(spine)
        manifest["layers"]["fct"] = {
            "rows": len(spine),
            "cols": len(spine.columns),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
            "fingerprint": fingerprint,
        }
        manifest["gw_range"] = [int(spine["gw"].min()), int(spine["gw"].max())]
    except DALContractViolation as exc:
        manifest["layers"]["fct"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        if mrt_path.exists():
            mrt_path.unlink()
        raise
    except Exception as exc:
        manifest["layers"]["fct"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- feat ---
    t0 = time.perf_counter()
    try:
        features = build_player_gameweek_state(spine)
        manifest["layers"]["feat"] = {
            "rows": len(features),
            "cols": len(features.columns),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation as exc:
        manifest["layers"]["feat"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        if mrt_path.exists():
            mrt_path.unlink()
        raise
    except Exception as exc:
        manifest["layers"]["feat"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- mart ---
    t0 = time.perf_counter()
    try:
        cutoff = data_cutoff_gw if data_cutoff_gw is not None else int(spine["gw"].max())
        mart = build_prepared_dataset(features, cutoff)
        manifest["layers"]["mart"] = {
            "rows": len(mart),
            "cols": len(mart.columns),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
        manifest["data_cutoff_gw"] = cutoff
        manifest["mart_schema"] = _mart_schema_fingerprint(mart)
    except DALContractViolation as exc:
        manifest["layers"]["mart"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        if mrt_path.exists():
            mrt_path.unlink()
        raise
    except Exception as exc:
        manifest["layers"]["mart"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- atomic parquet write ---
    # Write to .tmp; os.rename() is atomic on POSIX (same filesystem).
    # A crash between write and rename leaves .tmp but the live path is untouched.
    mart.to_parquet(tmp_path, index=False)
    os.rename(tmp_path, mrt_path)

    _write_manifest(mpath, manifest)
    return manifest


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


def load(
    db_path: Path = DB_PATH,
    mart_path: Path | None = None,
    manifest_path: Path | None = None,
) -> MartResult:
    """Read the persisted mart parquet and return a MartResult.

    Does NOT trigger a rebuild. If the parquet is absent or the manifest is
    missing/failed, raises MartNotBuiltError — call run() first.

    Raises MartSchemaError if the parquet column set does not match the schema
    recorded in the manifest. This means a code change invalidated the cached
    parquet without changing the source DB hash. Fix: run(force=True).

    Does NOT re-validate row-level data — trusts the pipeline that produced it.
    Does NOT apply additional GW filtering — the mart was already filtered at build time.

    Staleness: MartResult carries source_db_hash and data_cutoff_gw. Callers
    that need to verify currency (e.g. scorer checking GW coverage) should
    inspect these fields — load() does not reject a stale-but-valid artifact.
    """
    mpath = manifest_path or _manifest_path(db_path)
    mrt_path = mart_path or _mart_path(db_path)

    manifest = _load_manifest(mpath)
    if manifest is None:
        raise MartNotBuiltError(f"No manifest found at {mpath}. Run dal.pipeline.run() to build the mart.")

    failed = [name for name, info in manifest.get("layers", {}).items() if info.get("status") != "OK"]
    if failed:
        raise MartNotBuiltError(f"Last build recorded failures in: {failed}. Run dal.pipeline.run() to rebuild.")

    if not mrt_path.exists():
        raise MartNotBuiltError(f"mart.parquet not found at {mrt_path}. Run dal.pipeline.run() to build the mart.")

    mart = pd.read_parquet(mrt_path)

    recorded_schema = manifest.get("mart_schema")
    if recorded_schema is None or not _schema_matches(recorded_schema, mart):
        raise MartSchemaError(
            "mart.parquet schema does not match the current mart contract. "
            "A code change invalidated the cached parquet. "
            "Run dal.pipeline.run(force=True) to rebuild."
        )

    cutoff = manifest.get("data_cutoff_gw", int(mart["gw"].max()))
    gw_min = int(mart["gw"].min()) if len(mart) else 0
    gw_max = int(mart["gw"].max()) if len(mart) else 0

    return MartResult(
        mart=mart,
        signals=GOVERNED_SIGNAL_COLUMNS,
        gw_range=(gw_min, gw_max),
        data_cutoff_gw=cutoff,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_manifest(manifest: dict[str, Any]) -> None:
    layers = manifest.get("layers", {})
    print(f"Run:    {manifest.get('run_id')}")
    print(f"DB:     {manifest.get('source_db_path')}")
    print(f"GW:     {manifest.get('gw_range')}")
    print(f"Cutoff: GW{manifest.get('data_cutoff_gw')}")
    print(f"Mart:   {manifest.get('mart_path')}")
    for layer, info in layers.items():
        print(f"  {layer}: {info.get('status')} (rows={info.get('rows', '?')}, {info.get('duration_ms', '?')}ms)")


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "run":
        force = "--force" in sys.argv
        result = run(force=force)
        _print_manifest(result)
        failed = [n for n, i in result.get("layers", {}).items() if i.get("status") != "OK"]
        sys.exit(1 if failed else 0)

    elif cmd == "load":
        try:
            mart_result = load()
            print(f"mart shape : {mart_result.mart.shape}")
            print(f"gw range   : {mart_result.gw_range}")
            print(f"cutoff gw  : {mart_result.data_cutoff_gw}")
            print(f"signals    : {len(mart_result.signals)}")
        except (MartNotBuiltError, MartSchemaError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    else:
        print("Usage: python -m dal.pipeline [run|load] [--force]")
        sys.exit(1)
