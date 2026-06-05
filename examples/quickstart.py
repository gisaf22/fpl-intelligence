"""Quickstart: verify the DAL works end to end against a real database.

Builds the mart (if not already built) and reads it back via the canonical
entry point ``dal.pipeline.load()``, prints shape and column information, and
exits with a non-zero code on any failure.

Usage:
    FPL_DB_PATH=/path/to/fpl.db python examples/quickstart.py
    python examples/quickstart.py /path/to/fpl.db
"""

from __future__ import annotations

import sys
from pathlib import Path

from dal.config import DB_PATH as _DEFAULT_DB_PATH
from dal.exceptions import MartNotBuiltError
from dal.pipeline import load, run


def resolve_db_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser()
    return _DEFAULT_DB_PATH


def main() -> None:
    db_path = resolve_db_path()

    # ── Load the mart, building it first if no cached artifact exists ────────
    try:
        try:
            result = load(db_path)
        except MartNotBuiltError:
            print("No cached mart found — building (staging → … → mart)…")
            run(db_path)
            result = load(db_path)
    except Exception as exc:
        sys.exit(f"ERROR: mart build/load failed — {exc}")

    mart = result.mart
    gw_min, gw_max = result.gw_range

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"Mart shape:     {mart.shape}")
    print(f"Mart columns:   {list(mart.columns)}")
    print()
    print("── Summary ──────────────────────────────────────────")
    print(f"  Gameweek range : GW{gw_min} - GW{gw_max}")
    print(f"  Data cutoff GW : GW{result.data_cutoff_gw}")
    print(f"  Unique players : {mart['player_id'].nunique()}")
    print(f"  Governed signals : {len(result.signals)}")
    print("DAL OK")


if __name__ == "__main__":
    main()
