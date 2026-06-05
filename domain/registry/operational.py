"""Operational gate wrapper around the typed registry loader.

The pure typed loader is ``domain.registry.loader`` (the shared leaf). This
wrapper adds the lifecycle gate: when ``operational=True`` the path is asserted
to be a promoted operational artifact (not an exploratory research/findings
output) before the typed load is delegated. Operational consumers (scorer,
report runner) call this; research consumers use the pure loader directly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from domain.registry.loader import load_registry as _load_registry_typed
from domain.registry.schema import RESEARCH_REGISTRY_PATH


def load_registry(
    path: str | Path = RESEARCH_REGISTRY_PATH,
    *,
    operational: bool = False,
) -> pd.DataFrame:
    """Load a registry CSV and normalize dtypes for downstream use.

    When operational=True, asserts the path is a promoted operational artifact
    (not an exploratory research/findings/ output) before reading.
    """
    registry_path = Path(path)
    if operational:
        from domain.registry.lifecycle import assert_operational_safe

        assert_operational_safe(registry_path)
    return _load_registry_typed(registry_path)
