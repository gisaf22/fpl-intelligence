from __future__ import annotations

from enum import StrEnum


class DALError(Exception):
    """Base class for all DAL exceptions."""


class DataFreshnessError(DALError):
    """Raised when DB data does not meet freshness requirements for the target GW."""

    def __init__(self, message: str, *, gw: int) -> None:
        self.gw = gw
        super().__init__(message)


class MartNotBuiltError(DALError):
    """Raised by load() when the mart parquet is absent or the manifest is missing/failed.

    The caller must run dal.pipeline.run() to produce the artifact before load() can succeed.
    Catching this exception and continuing is always wrong — there is no mart to read.
    """


class MartSchemaError(DALError):
    """Raised by load() when the parquet column set does not match the current mart contract.

    Caused by a code change (e.g. FEATURE_REGISTRY column added/removed) that invalidated
    the cached parquet without changing the source DB hash. Run dal.pipeline.run(force=True).
    """


class ErrorCode(StrEnum):
    """Documented error code vocabulary for DALContractViolation.

    All DALContractViolation raises must use one of these constants so that
    consumers catching the exception know what to expect without reading source code.
    """
    GRAIN_DUPLICATE = "GRAIN_DUPLICATE"    # duplicate (player_id, gw) pairs
    ROW_COUNT       = "ROW_COUNT"          # n_players x n_gws invariant violated
    MISSING_COLUMNS = "MISSING_COLUMNS"    # required columns absent from layer output
    COLUMN_EXTRA    = "COLUMN_EXTRA"       # unexpected columns present in layer output
    DTYPE_MISMATCH  = "DTYPE_MISMATCH"    # column type does not match declared dtype
    NULL_VIOLATION  = "NULL_VIOLATION"     # never_null column contains nulls
    JOIN_SAFETY     = "JOIN_SAFETY"        # row loss or fan-out detected after join
    TIME_CONTINUITY = "TIME_CONTINUITY"   # gap in per-player GW sequence
    FUTURE_DATA     = "FUTURE_DATA"        # performance data present for future GW
    BGW_VIOLATION   = "BGW_VIOLATION"      # BGW row has non-null performance value
    DGW_VIOLATION   = "DGW_VIOLATION"      # DGW row has incorrect fixture counts


_VALID_CODES = frozenset(ErrorCode)


class DALContractViolation(DALError):
    """Raised when a DAL validation function detects that a contract invariant is broken.

    This is a programming error, not a runtime condition.
    No recovery is expected — the pipeline must stop, the code must be fixed,
    and the pipeline must be rerun from the point of violation.

    Catching this exception and continuing is a contract violation in itself.
    """

    def __init__(
        self,
        message: str,
        *,
        validation: str | None = None,
        n_violations: int | None = None,
        error_code: str | ErrorCode | None = None,
    ) -> None:
        if error_code is not None and error_code not in _VALID_CODES:
            raise ValueError(
                f"Invalid error_code {error_code!r}. Must be one of: {sorted(_VALID_CODES)}"
            )

        self.message = message
        self.validation = validation
        self.n_violations = n_violations
        self.error_code: str | ErrorCode | None = error_code

        super().__init__(self._format())

    def _format(self) -> str:
        parts = []
        if self.error_code is not None:
            parts.append(f"[{self.error_code}]")
        if self.validation is not None:
            parts.append(f"validation={self.validation}")
        if self.n_violations is not None:
            parts.append(f"n_violations={self.n_violations}")

        header = " ".join(parts)
        return f"{header}\n{self.message}" if header else self.message

    def __repr__(self) -> str:
        return (
            f"DALContractViolation("
            f"message={self.message!r}, "
            f"validation={self.validation!r}, "
            f"n_violations={self.n_violations!r}, "
            f"error_code={self.error_code!r}"
            f")"
        )
