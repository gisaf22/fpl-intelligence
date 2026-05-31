"""Public DAL package exports.

Primary consumer interface:
    dal.pipeline.run(db_path, force, data_cutoff_gw) -> dict      (build mart + manifest)
    dal.pipeline.load(db_path) -> MartResult                       (read persisted mart)
"""

# --- primary result type ---
# --- exceptions ---
from dal.exceptions import (
    DALContractViolation,
    DALError,
    DataFreshnessError,
    MartNotBuiltError,
    MartSchemaError,
)
from dal.mart.mart_access import MartResult

__all__ = [
    "DALContractViolation",
    "DALError",
    "DataFreshnessError",
    "MartNotBuiltError",
    "MartResult",
    "MartSchemaError",
]
