"""Public DAL package exports.

Primary consumer interface:
    dal.pipeline.run(db_path, force, data_cutoff_gw) -> dict      (build mart + manifest)
    dal.pipeline.load(db_path) -> MartResult                       (read persisted mart)
"""

# --- primary result type ---
from dal.mart.mart_access import MartResult

# --- exceptions ---
from dal.exceptions import (
    DALContractViolation,
    DALError,
    DataFreshnessError,
    MartNotBuiltError,
    MartSchemaError,
)

__all__ = [
    # primary result type
    "MartResult",
    # exceptions
    "DALError",
    "DALContractViolation",
    "DataFreshnessError",
    "MartNotBuiltError",
    "MartSchemaError",
]
