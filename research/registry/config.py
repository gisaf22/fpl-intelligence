"""Configuration defaults for registry build workflows."""

from __future__ import annotations

from pathlib import Path

from domain.registry.schema import RESEARCH_REGISTRY_PATH

# Build writes the finding to an exploratory research location (under
# research/findings/, which the lifecycle gate marks exploratory). Promotion to
# the operational outputs/registry/ is a governance concern (model.governance.promote).
DEFAULT_FINDING_OUTPUT_ROOT = Path(__file__).parent.parent.parent / "research/findings/registry_builds"

# The registry builder is a research tool: it reads the EDA registry and packages it.
# It is not an operational consumer and does not enforce lifecycle gating.
DEFAULT_SOURCE_REGISTRY_PATH = RESEARCH_REGISTRY_PATH

REGISTRY_VERSION = "eda_03_joint.v1"
SCHEMA_VERSION = "registry_contract.v1"


def default_finding_output_dir(gw: int) -> Path:
    """Return the default registry-build finding directory for a gameweek.

    Lives under research/findings/ — an exploratory location. The build stops
    here; governance promotes the finding to outputs/registry/.
    """
    return DEFAULT_FINDING_OUTPUT_ROOT / f"gw{gw}"


def assign_gw_block(gw: int) -> str:
    """Map a gameweek number to its season block label."""
    if gw <= 14:
        return "early"
    if gw <= 24:
        return "mid"
    return "late"
