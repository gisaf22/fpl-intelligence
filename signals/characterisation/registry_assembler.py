"""Registry assembly from computed relationship section outputs."""

from __future__ import annotations

import pandas as pd

from signals.characterisation.association import assign_association_class, consolidate_flags
from signals.governance.promotion import enrich_promotion_class
from signals.governance.schema import REQUIRED_COLUMNS
from signals.governance.signal_layer_classifier import enrich_signal_layers

SECTION_KEY_COLUMNS: tuple[str, ...] = ("signal", "position")

STABILITY_COLUMNS: tuple[str, ...] = (
    "signal",
    "position",
    "temporal_stability",
)

DECOMPOSITION_COLUMNS: tuple[str, ...] = (
    "signal",
    "position",
    "rho_pooled",
    "rho_between",
    "rho_within",
    "within_share",
    "panel_class",
    "decomposition_flag",
    "n_players",
    "support_flag",
)

HAUL_COLUMNS: tuple[str, ...] = (
    "signal",
    "position",
    "rho_full",
    "rho_no_haul",
    "rho_drop",
    "haul_pct",
    "n_haul",
    "tail_sensitive",
    "support_flag",
)


def _require_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{frame_name} missing required columns: {missing}")


def _validate_section_keys(frame: pd.DataFrame, frame_name: str) -> None:
    _require_columns(frame, SECTION_KEY_COLUMNS, frame_name)
    duplicates = int(frame[list(SECTION_KEY_COLUMNS)].duplicated().sum())
    if duplicates:
        raise ValueError(f"{frame_name} has {duplicates} duplicate signal-position keys")


def assemble_registry_from_sections(
    geometry: pd.DataFrame,
    stability: pd.DataFrame,
    decomposition: pd.DataFrame,
    haul: pd.DataFrame,
    expected_n: int | None = None,
) -> pd.DataFrame:
    """Assemble the governed registry from computed relationship sections."""
    _validate_section_keys(geometry, "geometry")
    _validate_section_keys(stability, "stability")
    _validate_section_keys(decomposition, "decomposition")
    _validate_section_keys(haul, "haul")

    _require_columns(stability, STABILITY_COLUMNS, "stability")
    _require_columns(decomposition, DECOMPOSITION_COLUMNS, "decomposition")
    _require_columns(haul, HAUL_COLUMNS, "haul")

    if expected_n is not None:
        counts = {
            "geometry": len(geometry),
            "stability": len(stability),
            "decomposition": len(decomposition),
            "haul": len(haul),
        }
        mismatches = {name: count for name, count in counts.items() if count != expected_n}
        if mismatches:
            raise ValueError(f"section row counts do not match expected_n={expected_n}: {mismatches}")

    registry = geometry.copy()
    registry = registry.merge(
        stability[list(STABILITY_COLUMNS)],
        on=list(SECTION_KEY_COLUMNS),
        how="left",
    )
    registry = registry.merge(
        decomposition[list(DECOMPOSITION_COLUMNS)].rename(columns={"support_flag": "decomp_support_flag"}),
        on=list(SECTION_KEY_COLUMNS),
        how="left",
    )
    registry = registry.merge(
        haul[list(HAUL_COLUMNS)].rename(columns={"support_flag": "haul_support_flag"}),
        on=list(SECTION_KEY_COLUMNS),
        how="left",
    )

    flag_columns = ("support_flags", "decomp_support_flag", "haul_support_flag")
    registry["support_flags"] = [
        consolidate_flags(*[str(row.get(column) or "") for column in flag_columns])
        for row in registry.to_dict(orient="records")
    ]
    registry = registry.drop(columns=[column for column in flag_columns[1:] if column in registry.columns])

    registry["association_class"] = [assign_association_class(row) for row in registry.to_dict(orient="records")]
    registry = enrich_signal_layers(registry)
    registry = enrich_promotion_class(registry)

    extra_columns = [column for column in registry.columns if column not in REQUIRED_COLUMNS]
    return registry[[column for column in REQUIRED_COLUMNS if column in registry.columns] + extra_columns]
