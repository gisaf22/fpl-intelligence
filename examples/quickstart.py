"""Quickstart: verify the DAL works end to end against a real database.

Usage:
    FPL_DB_PATH=/path/to/fpl.db python examples/quickstart.py
    python examples/quickstart.py /path/to/fpl.db
"""

from __future__ import annotations

import sys
from pathlib import Path

from dal import (
    build_player_gameweek_spine,
    build_player_gameweek_state,
    get_player_fixture_base,
    load_staged_entities,
)
from dal.config import DB_PATH as _DEFAULT_DB_PATH


def resolve_db_path() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).expanduser()
    return _DEFAULT_DB_PATH


def main() -> None:
    db_path = resolve_db_path()

    # ── Spine ──────────────────────────────────────────────────────────────
    try:
        staged = load_staged_entities(db_path)
        spine = build_player_gameweek_spine(get_player_fixture_base(staged), staged.events)
    except Exception as exc:
        sys.exit(f"ERROR: spine build failed — {exc}")

    print(f"Spine shape:    {spine.shape}")
    print(spine.head(3).to_string())
    print()

    # ── State features ─────────────────────────────────────────────────────
    try:
        state = build_player_gameweek_state(spine)
    except Exception as exc:
        sys.exit(f"ERROR: state build failed — {exc}")

    print(f"State shape:    {state.shape}")
    print(f"State columns:  {list(state.columns)}")
    print()

    # ── Summary ────────────────────────────────────────────────────────────
    gw_min, gw_max = int(spine["gw"].min()), int(spine["gw"].max())
    player_count = spine["player_id"].nunique()
    feature_count = state.shape[1] - spine.shape[1]

    print("── Summary ──────────────────────────────────────────")
    print(f"  Gameweek range : GW{gw_min} – GW{gw_max}")
    print(f"  Unique players : {player_count}")
    print(f"  State features : {feature_count} (spine had {spine.shape[1]} columns)")
    print("DAL OK")


if __name__ == "__main__":
    main()
