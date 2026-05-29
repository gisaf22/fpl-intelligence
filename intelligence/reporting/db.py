"""DB entry point for weekly runs — GW resolution and freshness validation."""

from __future__ import annotations

from pathlib import Path

from dal import validate_data_freshness  # noqa: F401
from dal.fct.fct_gameweek_context import resolve_target_gw  # noqa: F401
