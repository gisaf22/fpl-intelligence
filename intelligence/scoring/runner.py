"""CLI entry point for the player scoring harness.

Orchestration only: wires DAL → signals → engine → renderer → disk.
All business logic lives in engine.py and signals.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dal.access import get_curated_spine, get_state_features
from intelligence.scoring.contracts import ScorerInput, ScorerOutput
from intelligence.scoring.engine import NoDataForGameweek, score
from intelligence.scoring.renderer import render
from intelligence.scoring.signals import load_manifest_from_path


def _load_registry_meta(registry_path: Path) -> dict:
    meta_path = registry_path.parent / "build_metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def run_scorer(input: ScorerInput) -> Path:
    """Execute the full scoring pipeline and write the HTML output file.

    Returns the path to the written HTML file.
    Raises NoDataForGameweek (caught by main) if GW has no data.
    """
    spine = get_curated_spine(input.db_path)
    state = get_state_features(spine)

    manifest = load_manifest_from_path(input.registry_path)
    raw_output = score(state, manifest, input.gw)

    registry_meta = _load_registry_meta(input.registry_path)
    output = ScorerOutput(
        gw=raw_output.gw,
        scored_at=raw_output.scored_at,
        players=raw_output.players,
        manifest=raw_output.manifest,
        registry_path=str(input.registry_path),
        registry_meta=registry_meta,
    )

    html_content = render(output)

    input.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = input.output_dir / f"gw{input.gw}_player_scores.html"
    out_path.write_text(html_content, encoding="utf-8")

    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score FPL players for a gameweek and write an HTML report."
    )
    parser.add_argument(
        "--gw",
        type=int,
        required=True,
        help="Target gameweek number.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        required=True,
        help="Path to the FPL SQLite database.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write the HTML output file.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        required=True,
        help=(
            "Registry CSV path. Must be a lifecycle-promoted registry from "
            "outputs/registry/, not an exploratory artifact from studies/eda/."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    scorer_input = ScorerInput(
        gw=args.gw,
        db_path=args.db_path,
        output_dir=args.output_dir,
        registry_path=args.registry_path,
    )

    try:
        out_path = run_scorer(scorer_input)
    except NoDataForGameweek as exc:
        print(f"No data for GW{args.gw}: {exc}", file=sys.stderr)
        return 1

    print(f"GW{args.gw} scoring complete")
    print(f"  output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
