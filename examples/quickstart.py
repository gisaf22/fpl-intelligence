"""Quickstart: verify the DAL works end to end against a real database.

Usage:
    FPL_DB_PATH=/path/to/fpl.db python examples/quickstart.py
    python examples/quickstart.py /path/to/fpl.db
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_db_path() -> Path:
    # CLI argument takes precedence over env var; env var falls back to DAL default.
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser()
    env = os.environ.get("FPL_DB_PATH")
    if env:
        return Path(env).expanduser()
    # Let the DAL config supply its own default (~/.fpl/fpl.db).
    return None


def main() -> None:
    db_path = resolve_db_path()

    # ── Spine ──────────────────────────────────────────────────────────────
    try:
        from dal.access import get_curated_spine
        spine = get_curated_spine(db_path) if db_path else get_curated_spine()
    except Exception as exc:
        sys.exit(f"ERROR: get_curated_spine failed — {exc}")

    print(f"Spine shape:    {spine.shape}")
    print(spine.head(3).to_string())
    print()

    # ── State features ─────────────────────────────────────────────────────
    try:
        from dal.access import get_state_features
        state = get_state_features(spine)
    except Exception as exc:
        sys.exit(f"ERROR: get_state_features failed — {exc}")

    print(f"State shape:    {state.shape}")
    print(f"State columns:  {list(state.columns)}")
    print()

    # ── Summary ────────────────────────────────────────────────────────────
    gw_min, gw_max = int(spine["gw"].min()), int(spine["gw"].max())
    player_count = spine["player_id"].nunique()
    feature_count = state.shape[1] - spine.shape[1]   # net-new columns added by state layer

    print("── Summary ──────────────────────────────────────────")
    print(f"  Gameweek range : GW{gw_min} – GW{gw_max}")
    print(f"  Unique players : {player_count}")
    print(f"  State features : {feature_count} (spine had {spine.shape[1]} columns)")
    print("DAL OK")


if __name__ == "__main__":
    main()
