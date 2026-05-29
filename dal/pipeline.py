"""DAL pipeline runner — orchestrates the full build in layer order and manages the run manifest.

Entry point: python -m dal.pipeline build

This module owns:
  - build: full pipeline orchestration (staging → intermediate → fct → feat → mart)
  - run manifest: JSON record of per-layer status, fingerprints, row counts, timing

db_path is the only I/O reference in this module. All layer functions below staging
receive DataFrames — they never touch db_path.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dal.config import DB_PATH
from dal.exceptions import DALContractViolation
from dal.fct.fct_player_gameweek import build_player_gameweek_spine
from dal.feat.feat_player_gameweek import build_player_gameweek_state
from dal.intermediate.int_player_fixture import get_player_fixture_base
from dal.mart.mart_analytical import build_prepared_dataset
from dal.reproducibility import compute_spine_fingerprint
from dal.staging import StagedEntities, load_staged_entities


def _hash_db(db_path: Path) -> str:
    """Return a SHA-256 hex digest of the source database file."""
    h = hashlib.sha256()
    with open(db_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _manifest_path(db_path: Path) -> Path:
    return db_path.with_suffix(".manifest.json")


def _load_manifest(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
    return None


def _write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2))


def build(
    db_path: Path = DB_PATH,
    force: bool = False,
    manifest_path: Path | None = None,
) -> dict:
    """Run all layers in order and return the manifest dict.

    Layer order: staging → intermediate → fct → feat → mart.
    If force=False and the manifest shows a successful build for the current source
    hash, the cached result is returned immediately.

    db_path is the only I/O reference. All downstream layers receive DataFrames.
    Writes a manifest JSON to manifest_path (defaults to db_path with .manifest.json suffix).
    """
    if not db_path.exists():
        raise FileNotFoundError(f"Source DB not found: {db_path}")

    mpath = manifest_path if manifest_path is not None else _manifest_path(db_path)
    source_hash = _hash_db(db_path)
    existing = _load_manifest(mpath)
    if not force and existing and existing.get("source_db_hash") == source_hash:
        all_ok = all(layer.get("status") == "OK" for layer in existing.get("layers", {}).values())
        if all_ok:
            return existing

    now = datetime.now(timezone.utc)
    manifest: dict = {
        "run_id": now.strftime("build_%Y%m%d_%H%M%S"),
        "built_at": now.isoformat(),
        "source_db_path": str(db_path),
        "source_db_hash": source_hash,
        "layers": {},
        "validation": {},
    }

    # --- staging layer ---
    t0 = time.perf_counter()
    try:
        staged: StagedEntities = load_staged_entities(db_path)
        manifest["layers"]["staging"] = {
            "rows": len(staged.player_histories),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation:
        raise
    except Exception as exc:
        manifest["layers"]["staging"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- intermediate layer ---
    t0 = time.perf_counter()
    try:
        player_fixture = get_player_fixture_base(staged)
        manifest["layers"]["intermediate"] = {
            "rows": len(player_fixture),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation:
        raise
    except Exception as exc:
        manifest["layers"]["intermediate"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- fct layer ---
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
    except DALContractViolation:
        raise
    except Exception as exc:
        manifest["layers"]["fct"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- feat layer ---
    t0 = time.perf_counter()
    try:
        features = build_player_gameweek_state(spine)
        manifest["layers"]["feat"] = {
            "rows": len(features),
            "cols": len(features.columns),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation:
        raise
    except Exception as exc:
        manifest["layers"]["feat"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    # --- mart layer ---
    t0 = time.perf_counter()
    try:
        cutoff_gw = int(spine["gw"].max())
        mart = build_prepared_dataset(features, cutoff_gw)
        manifest["layers"]["mart"] = {
            "rows": len(mart),
            "cols": len(mart.columns),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "status": "OK",
        }
    except DALContractViolation:
        raise
    except Exception as exc:
        manifest["layers"]["mart"] = {"status": "FAIL", "error": str(exc)}
        _write_manifest(mpath, manifest)
        return manifest

    _write_manifest(mpath, manifest)
    return manifest


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        result = build()
        layers = result.get("layers", {})
        status_lines = [
            f"  {layer}: {info.get('status')} "
            f"(rows={info.get('rows', '?')}, {info.get('duration_ms', '?')}ms)"
            for layer, info in layers.items()
        ]
        print(f"Run: {result.get('run_id')}")
        print("\n".join(status_lines))
        failed = [name for name, info in layers.items() if info.get("status") != "OK"]
        if failed:
            print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: python -m dal.pipeline build")
        sys.exit(1)
