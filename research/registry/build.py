"""CLI entry point for building the registry finding.

Research builds the *raw evidence* finding (computed relationship sections +
association class) and writes it to an exploratory research location (under
research/findings/). It stops there — it does not enrich, validate the contract,
or publish to outputs/registry/. Governance enrichment (signal-layer semantics +
promotion class), contract validation, the lifecycle gate, and publication are
governance concerns: see ``model.governance.promote``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from domain.registry.loader import load_registry
from research.registry.assembler import assemble_registry_from_sections
from research.registry.comparison import compare_registries
from research.registry.config import (
    DEFAULT_SOURCE_REGISTRY_PATH,
    assign_gw_block,
    default_finding_output_dir,
)
from research.registry.input_contracts import validate_prepared_dataset
from research.registry.metadata import build_registry_metadata
from research.registry.sections import SectionBuildConfig, compute_relationship_sections

BUILD_MODES: tuple[str, ...] = ("packaged", "computed")


@dataclass(frozen=True)
class RegistryBuildResult:
    """Finding locations and counts from one registry build.

    ``finding_path`` points at an exploratory research artifact (under
    research/findings/). It is not operationally consumable until promoted by
    ``model.governance.promote``.
    """

    gw: int
    data_cutoff_gw: int
    build_mode: str
    source_registry_path: Path
    source_dataset_path: Path
    finding_dir: Path
    finding_path: Path
    metadata_path: Path
    comparison_path: Path | None
    n_rows: int


def _load_tabular(path: str | Path) -> pd.DataFrame:
    source_path = Path(path)
    if source_path.suffix.lower() == ".csv":
        return pd.read_csv(source_path)
    if source_path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(source_path)
    raise ValueError(f"Unsupported tabular input format for {source_path}; use CSV or Parquet")


def _signals_from_metadata(signal_metadata: pd.DataFrame | None) -> tuple[str, ...]:
    if signal_metadata is None:
        return ()
    if "signal" not in signal_metadata.columns:
        raise ValueError("signal metadata missing required columns: ['signal']")
    if "status" in signal_metadata.columns:
        signal_metadata = signal_metadata[signal_metadata["status"].astype(str).str.upper().eq("INCLUDE")]
    return tuple(dict.fromkeys(signal_metadata["signal"].astype(str)))


def _build_computed_registry(
    prepared_data_path: str | Path,
    data_cutoff_gw: int,
    signals: list[str] | tuple[str, ...] | None = None,
    signal_metadata_path: str | Path | None = None,
    n_bootstrap: int = 200,
) -> pd.DataFrame:
    data = _load_tabular(prepared_data_path)
    signal_metadata = pd.read_csv(signal_metadata_path) if signal_metadata_path is not None else None
    signal_list = tuple(signals or _signals_from_metadata(signal_metadata))
    if not signal_list:
        raise ValueError("computed registry builds require --signals or --signal-metadata-path")
    data = validate_prepared_dataset(
        data=data,
        signals=signal_list,
        data_cutoff_gw=data_cutoff_gw,
    )
    data["gw_block"] = data["gw"].map(assign_gw_block)

    sections = compute_relationship_sections(
        data=data,
        signals=signal_list,
        config=SectionBuildConfig(n_bootstrap=n_bootstrap),
        signal_metadata=signal_metadata,
    )
    return assemble_registry_from_sections(
        geometry=sections.geometry,
        stability=sections.stability,
        decomposition=sections.decomposition,
        haul=sections.haul,
        expected_n=len(sections.geometry),
    )


def run_registry_build(
    gw: int,
    source_registry_path: str | Path = DEFAULT_SOURCE_REGISTRY_PATH,
    finding_dir: str | Path | None = None,
    data_cutoff_gw: int | None = None,
    build_mode: str = "packaged",
    prepared_data_path: str | Path | None = None,
    signals: list[str] | tuple[str, ...] | None = None,
    signal_metadata_path: str | Path | None = None,
    compare_registry_path: str | Path | None = None,
    n_bootstrap: int = 200,
) -> RegistryBuildResult:
    """Build the gameweek-scoped registry finding and write it to research/findings/.

    This stops at the raw evidence finding: it does not enrich, validate the
    registry contract, or publish to outputs/registry/. Governance enrichment +
    promotion is a governance concern — call
    ``model.governance.promote.promote_registry`` on the finding artifact.
    """
    if gw <= 0:
        raise ValueError(f"gw must be positive, got {gw}")
    if build_mode not in BUILD_MODES:
        raise ValueError(f"build_mode must be one of {BUILD_MODES}, got {build_mode!r}")

    cutoff = gw if data_cutoff_gw is None else data_cutoff_gw
    if cutoff <= 0:
        raise ValueError(f"data_cutoff_gw must be positive, got {cutoff}")
    if cutoff > gw:
        raise ValueError(f"data_cutoff_gw cannot be greater than gw: {cutoff} > {gw}")

    source_path = Path(source_registry_path)
    target_dir = Path(finding_dir) if finding_dir is not None else default_finding_output_dir(gw)

    source_dataset_path = source_path
    comparison_summary: dict[str, int] | None = None
    comparison_path: Path | None = None

    if build_mode == "packaged":
        registry = load_registry(source_path)
    else:
        if prepared_data_path is None:
            raise ValueError("computed registry builds require prepared_data_path")
        source_dataset_path = Path(prepared_data_path)
        registry = _build_computed_registry(
            prepared_data_path=source_dataset_path,
            data_cutoff_gw=cutoff,
            signals=signals,
            signal_metadata_path=signal_metadata_path,
            n_bootstrap=n_bootstrap,
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    finding_path = target_dir / "registry.csv"
    metadata_path = target_dir / "build_metadata.json"

    registry.to_csv(finding_path, index=False)

    reference_path = (
        Path(compare_registry_path)
        if compare_registry_path is not None
        else source_path
        if build_mode == "computed"
        else None
    )
    if reference_path is not None and reference_path.exists():
        reference = load_registry(reference_path)
        comparison = compare_registries(reference=reference, candidate=registry)
        comparison_path = target_dir / "registry_comparison.csv"
        comparison.differences.to_csv(comparison_path, index=False)
        comparison_summary = comparison.summary

    metadata = build_registry_metadata(
        registry=registry,
        gw=gw,
        data_cutoff_gw=cutoff,
        source_registry_path=source_path,
        source_dataset_path=source_dataset_path,
        build_mode=build_mode,
        comparison_summary=comparison_summary,
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return RegistryBuildResult(
        gw=gw,
        data_cutoff_gw=cutoff,
        build_mode=build_mode,
        source_registry_path=source_path,
        source_dataset_path=source_dataset_path,
        finding_dir=target_dir,
        finding_path=finding_path,
        metadata_path=metadata_path,
        comparison_path=comparison_path,
        n_rows=len(registry),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for registry build workflow."""
    parser = argparse.ArgumentParser(
        description="Build the gameweek-scoped registry finding (research/findings/). Promote separately."
    )
    parser.add_argument(
        "--gw",
        type=int,
        required=True,
        help="Gameweek number for the registry finding folder.",
    )
    parser.add_argument(
        "--source-registry-path",
        type=Path,
        default=DEFAULT_SOURCE_REGISTRY_PATH,
        help=f"Source registry CSV path. Default: {DEFAULT_SOURCE_REGISTRY_PATH}",
    )
    parser.add_argument(
        "--finding-dir",
        type=Path,
        default=None,
        help="Finding output directory. Default: research/findings/registry_builds/gw{gw}",
    )
    parser.add_argument(
        "--data-cutoff-gw",
        type=int,
        default=None,
        help="Maximum gameweek represented by the registry. Default: --gw.",
    )
    parser.add_argument(
        "--mode",
        choices=BUILD_MODES,
        default="packaged",
        help="Build source mode. Default: packaged.",
    )
    parser.add_argument(
        "--prepared-data-path",
        type=Path,
        default=None,
        help="Prepared analytical dataset for computed mode.",
    )
    parser.add_argument(
        "--signals",
        nargs="+",
        default=None,
        help="Signals to compute in computed mode.",
    )
    parser.add_argument(
        "--signal-metadata-path",
        type=Path,
        default=None,
        help="Optional signal metadata CSV for computed mode.",
    )
    parser.add_argument(
        "--compare-registry-path",
        type=Path,
        default=None,
        help=("Reference registry for computed comparison. Default in computed mode: --source-registry-path."),
    )
    parser.add_argument(
        "--n-bootstrap",
        type=int,
        default=200,
        help="Bootstrap iterations for computed monotonicity confidence.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    result = run_registry_build(
        gw=args.gw,
        source_registry_path=args.source_registry_path,
        finding_dir=args.finding_dir,
        data_cutoff_gw=args.data_cutoff_gw,
        build_mode=args.mode,
        prepared_data_path=args.prepared_data_path,
        signals=args.signals,
        signal_metadata_path=args.signal_metadata_path,
        compare_registry_path=args.compare_registry_path,
        n_bootstrap=args.n_bootstrap,
    )
    print(f"GW{result.gw} registry finding built")
    print(f"  mode:     {result.build_mode}")
    print(f"  source:   {result.source_registry_path}")
    print(f"  dataset:  {result.source_dataset_path}")
    print(f"  rows:     {result.n_rows}")
    print(f"  finding:  {result.finding_path}")
    if result.comparison_path is not None:
        print(f"  compare:  {result.comparison_path}")
    print(f"  metadata: {result.metadata_path}")
    print("  next:     promote via model.governance.promote to publish to outputs/registry/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
