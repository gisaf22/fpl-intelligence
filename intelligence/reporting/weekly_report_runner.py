"""Weekly registry snapshot runner.

Phase 3 deliberately keeps the weekly entry point narrow: load the governed
EDA-3 registry, validate the contract, and write a reproducible weekly
snapshot. Later phases add summaries, insight cards, and markdown reports on
top of this same entry point.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from intelligence.reporting.insight_card_writer import write_insight_cards
from intelligence.reporting.reports import write_weekly_markdown_report, write_weekly_report_tables
from intelligence.reporting.signal_intelligence import write_signal_intelligence
from intelligence.reporting.snapshots import write_snapshot_changes
from signals.governance import load_registry, validate_registry_contract

DEFAULT_WEEKLY_OUTPUT_ROOT = Path("outputs/weekly")


@dataclass(frozen=True)
class WeeklyRunResult:
    """Output locations and row counts from one weekly runner execution."""

    gw: int
    registry_path: Path
    output_dir: Path
    registry_snapshot_path: Path
    snapshot_changes_path: Path
    signal_summary_path: Path
    summary_by_position_path: Path
    summary_by_layer_path: Path
    stable_performance_signals_path: Path
    insight_cards_path: Path
    weekly_report_path: Path
    stable_signal_observations_path: Path
    positional_signal_summary_path: Path
    context_condition_notes_path: Path
    n_rows: int


def default_output_dir(gw: int) -> Path:
    """Return the default weekly output directory for a gameweek."""
    return DEFAULT_WEEKLY_OUTPUT_ROOT / f"gw{gw}"


def run_week(gw: int, registry_path: str | Path, output_dir: str | Path | None = None) -> WeeklyRunResult:
    """Run the Phase 3 weekly snapshot flow.

    The registry is loaded and validated before the output directory is
    created. That prevents invalid registry artifacts from producing partial
    weekly outputs.

    Enforces lifecycle governance: raises LifecycleViolationError if
    registry_path is an exploratory-state artifact from studies/eda/.
    """
    if gw <= 0:
        raise ValueError(f"gw must be positive, got {gw}")

    registry_path = Path(registry_path)
    target_dir = Path(output_dir) if output_dir is not None else default_output_dir(gw)

    registry = load_registry(registry_path, operational=True)
    validate_registry_contract(registry)

    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = target_dir / "registry_snapshot.csv"
    registry.to_csv(snapshot_path, index=False)
    snapshot_changes_path = write_snapshot_changes(
        current_snapshot=registry,
        gw=gw,
        output_dir=target_dir,
    )
    report_paths = write_weekly_report_tables(registry, gw=gw, output_dir=target_dir)
    insight_cards_path = write_insight_cards(
        signal_summary=pd.read_csv(report_paths["signal_summary"]),
        summary_by_position=pd.read_csv(report_paths["summary_by_position"]),
        summary_by_layer=pd.read_csv(report_paths["summary_by_layer"]),
        stable_performance_signals=pd.read_csv(
            report_paths["stable_performance_signals"]
        ),
        output_dir=target_dir,
    )
    signal_intelligence_paths = write_signal_intelligence(
        registry=registry,
        gw=gw,
        output_dir=target_dir,
    )
    weekly_report_path = write_weekly_markdown_report(
        signal_summary=pd.read_csv(report_paths["signal_summary"]),
        summary_by_position=pd.read_csv(report_paths["summary_by_position"]),
        summary_by_layer=pd.read_csv(report_paths["summary_by_layer"]),
        stable_performance_signals=pd.read_csv(
            report_paths["stable_performance_signals"]
        ),
        insight_cards=pd.read_csv(insight_cards_path),
        output_dir=target_dir,
    )

    return WeeklyRunResult(
        gw=gw,
        registry_path=registry_path,
        output_dir=target_dir,
        registry_snapshot_path=snapshot_path,
        snapshot_changes_path=snapshot_changes_path,
        signal_summary_path=report_paths["signal_summary"],
        summary_by_position_path=report_paths["summary_by_position"],
        summary_by_layer_path=report_paths["summary_by_layer"],
        stable_performance_signals_path=report_paths["stable_performance_signals"],
        insight_cards_path=insight_cards_path,
        weekly_report_path=weekly_report_path,
        stable_signal_observations_path=signal_intelligence_paths["stable_signal_observations"],
        positional_signal_summary_path=signal_intelligence_paths["positional_signal_summary"],
        context_condition_notes_path=signal_intelligence_paths["context_condition_notes"],
        n_rows=len(registry),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for weekly runner."""
    parser = argparse.ArgumentParser(
        description="Generate governed weekly FPL signal intelligence outputs."
    )
    parser.add_argument(
        "--gw",
        type=int,
        required=True,
        help="Gameweek number for the output folder and snapshot metadata.",
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
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: outputs/weekly/gw{gw}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    result = run_week(
        gw=args.gw,
        registry_path=args.registry_path,
        output_dir=args.output_dir,
    )
    print(f"GW{result.gw} weekly snapshot complete")
    print(f"  registry: {result.registry_path}")
    print(f"  rows:     {result.n_rows}")
    print(f"  snapshot: {result.registry_snapshot_path}")
    print(f"  changes:  {result.snapshot_changes_path}")
    print(f"  summary:  {result.signal_summary_path}")
    print(f"  insights: {result.insight_cards_path}")
    print(f"  report:   {result.weekly_report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
