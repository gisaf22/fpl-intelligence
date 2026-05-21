"""Configuration defaults for registry build workflows."""

from __future__ import annotations

from pathlib import Path

from core.governance.schema import DEFAULT_REGISTRY_PATH


DEFAULT_REGISTRY_BUILD_OUTPUT_ROOT = Path("outputs/registry")
DEFAULT_SOURCE_REGISTRY_PATH = DEFAULT_REGISTRY_PATH
REGISTRY_VERSION = "eda_03_joint.v1"
SCHEMA_VERSION = "registry_contract.v1"


def default_registry_output_dir(gw: int) -> Path:
    """Return the default registry build output directory for a gameweek."""
    return DEFAULT_REGISTRY_BUILD_OUTPUT_ROOT / f"gw{gw}"


def assign_gw_block(gw: int) -> str:
    """Map a gameweek number to its season block label."""
    if gw <= 14:
        return "early"
    if gw <= 24:
        return "mid"
    return "late"
