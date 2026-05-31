"""Build metadata helpers for generated registry artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from signals.characterisation.config import REGISTRY_VERSION, SCHEMA_VERSION


def build_registry_metadata(
    registry: pd.DataFrame,
    gw: int,
    data_cutoff_gw: int,
    source_registry_path: str | Path,
    source_dataset_path: str | Path | None = None,
    build_mode: str = "packaged",
    comparison_summary: dict[str, int] | None = None,
    registry_version: str = REGISTRY_VERSION,
    schema_version: str = SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return metadata describing one generated registry artifact."""
    metadata = {
        "gw": gw,
        "data_cutoff_gw": data_cutoff_gw,
        "build_mode": build_mode,
        "source_dataset_path": str(
            source_dataset_path
            if source_dataset_path is not None
            else source_registry_path
        ),
        "source_registry_path": str(source_registry_path),
        "registry_version": registry_version,
        "schema_version": schema_version,
        "build_timestamp": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "row_count": int(len(registry)),
        "signal_count": int(registry["signal"].nunique()),
        "position_count": int(registry["position"].nunique()),
    }
    if comparison_summary is not None:
        metadata["comparison_summary"] = comparison_summary
    return metadata
