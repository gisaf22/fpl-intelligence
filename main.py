from __future__ import annotations

import argparse
from pathlib import Path

from fpl_intelligence.config import DB_PATH
from fpl_intelligence.pipeline.runner import run_gw


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FPL intelligence pipeline for a gameweek.")
    parser.add_argument("--gw", type=int, required=True, help="Gameweek number")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Path to FPL SQLite DB")
    parser.add_argument("--output-dir", type=Path, default=Path("data/briefs"), help="Output directory for briefing JSON")
    parser.add_argument("--log-path", type=Path, default=Path("data/logs/runs.jsonl"), help="Path to run log")
    args = parser.parse_args()

    result = run_gw(
        gw=args.gw,
        db_path=args.db,
        output_dir=args.output_dir,
        log_path=args.log_path,
    )
    print(result)


if __name__ == "__main__":
    main()
