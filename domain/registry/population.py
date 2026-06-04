"""Prepared-dataset output schema for registry builds.

The column contract for the prepared dataset the registry build consumes:
identity (player_id, gw, position), the signal set, and the target. It wraps
the domain signal set (``domain.registry_signals``) and lives with the registry
contract in ``domain/registry/``.
"""

from __future__ import annotations

from domain.registry_signals import REGISTRY_BUILD_INPUT_COLUMNS

OUTPUT_COLUMNS: tuple[str, ...] = (
    "player_id",
    "gw",
    "position",
    *REGISTRY_BUILD_INPUT_COLUMNS,
    "total_points",
)
