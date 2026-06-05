"""Promotion of a registry finding to the operational registry.

Governance promotes a research *finding*: research builds it (``research.registry.build``)
and writes the raw evidence finding under research/findings/ (exploratory).
Promotion reads that artifact file-based — **no import of research** — applies
governance enrichment (signal-layer semantics + promotion class), validates the
enriched registry against the contract, asserts the publication target is an
operational (non-exploratory) location, and publishes it to outputs/registry/.

Enrichment is governance's responsibility, not the build's: the research build
emits raw evidence; the decision of how each signal is classified (signal_layer,
downstream_status, promotion_class) is applied here. Enrichment is idempotent, so
promoting an already-enriched finding re-derives the same governance columns.

This is the governance half of the build/promote split: research builds, governance
enriches + promotes. The build never publishes; this is the only path to outputs/registry/.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from domain.registry.lifecycle import assert_operational_safe
from domain.registry.loader import load_registry
from domain.registry.schema import OPERATIONAL_REGISTRY_DIR
from domain.registry.validation import validate_registry_contract
from model.governance.promotion import enrich_promotion_class
from model.governance.semantics import enrich_signal_layers


@dataclass(frozen=True)
class RegistryPromotionResult:
    """Locations and counts from one registry promotion."""

    gw: int
    finding_path: Path
    output_dir: Path
    registry_path: Path
    metadata_path: Path
    n_rows: int


def default_operational_output_dir(gw: int) -> Path:
    """Return the operational registry directory for a gameweek (outputs/registry/gw{gw})."""
    return OPERATIONAL_REGISTRY_DIR / f"gw{gw}"


def promote_registry(
    finding_path: str | Path,
    gw: int,
    output_dir: str | Path | None = None,
) -> RegistryPromotionResult:
    """Validate a registry finding and publish it to the operational registry.

    Reads the finding (file-based), enforces the registry contract, asserts the
    target is an operational (non-exploratory) location, then writes it to
    outputs/registry/. Raises before writing any output if the contract fails or
    the target is an exploratory path.
    """
    if gw <= 0:
        raise ValueError(f"gw must be positive, got {gw}")

    source_finding = Path(finding_path)
    target_dir = Path(output_dir) if output_dir is not None else default_operational_output_dir(gw)

    # Governance must publish to an operational location, never back into an
    # exploratory research/findings/ path.
    assert_operational_safe(target_dir)

    registry = load_registry(source_finding)
    # Governance enrichment: apply signal-layer semantics + promotion class to the
    # raw evidence finding before validating against the full contract. Idempotent.
    registry = enrich_signal_layers(registry)
    registry = enrich_promotion_class(registry)
    validate_registry_contract(registry)

    target_dir.mkdir(parents=True, exist_ok=True)
    registry_path = target_dir / "registry.csv"
    metadata_path = target_dir / "promotion_metadata.json"

    registry.to_csv(registry_path, index=False)

    metadata = {
        "gw": gw,
        "finding_path": str(source_finding),
        "registry_path": str(registry_path),
        "row_count": len(registry),
        "signal_count": int(registry["signal"].nunique()),
        "position_count": int(registry["position"].nunique()),
        "promoted_at": datetime.now(UTC).isoformat(),
        "validated": True,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return RegistryPromotionResult(
        gw=gw,
        finding_path=source_finding,
        output_dir=target_dir,
        registry_path=registry_path,
        metadata_path=metadata_path,
        n_rows=len(registry),
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the registry promotion workflow."""
    parser = argparse.ArgumentParser(
        description="Promote a registry finding (research/findings/) to outputs/registry/."
    )
    parser.add_argument(
        "--gw",
        type=int,
        required=True,
        help="Gameweek number for the operational registry folder.",
    )
    parser.add_argument(
        "--finding-path",
        type=Path,
        required=True,
        help="Path to the built registry finding CSV (from research.registry.build).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Operational output directory. Default: outputs/registry/gw{gw}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    result = promote_registry(
        finding_path=args.finding_path,
        gw=args.gw,
        output_dir=args.output_dir,
    )
    print(f"GW{result.gw} registry promoted")
    print(f"  finding:  {result.finding_path}")
    print(f"  rows:     {result.n_rows}")
    print(f"  registry: {result.registry_path}")
    print(f"  metadata: {result.metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
