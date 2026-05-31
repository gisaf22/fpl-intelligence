"""Analytical mart — governed output layer for analytics consumers.

Primary interfaces:
    dal.pipeline.run(db_path, force) -> dict          (CI / ops)
    dal.pipeline.load(db_path) -> MartResult          (persisted artifact)

Internal builders (for pipeline.py and tests only):
    build_prepared_dataset, GOVERNED_SIGNAL_COLUMNS, POSITION_CODE_MAP
"""

from dal.mart.mart_access import MartResult
from dal.mart.mart_analytical import (
    GOVERNED_SIGNAL_COLUMNS,
    POSITION_CODE_MAP,
    build_prepared_dataset,
)

__all__ = [
    "MartResult",
    "GOVERNED_SIGNAL_COLUMNS",
    "POSITION_CODE_MAP",
    "build_prepared_dataset",
]
