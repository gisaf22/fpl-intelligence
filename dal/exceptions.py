from __future__ import annotations

from typing import Optional


class DataFreshnessError(Exception):
    """Raised when DB data does not meet freshness requirements for the target GW."""
    pass


_VALID_LAYERS = frozenset({"staging", "intermediate", "curated", "state"})
_VALID_CODES = frozenset({
    "GRAIN_DUPLICATE", "BGW_NONZERO", "DGW_WRONG_COUNT", "NULL_SEMANTICS",
    "TIME_GAP", "ROW_COUNT", "FUTURE_DATA", "JOIN_ROW_LOSS", "JOIN_FANOUT",
    "COLUMN_MISSING", "COLUMN_EXTRA", "DTYPE_MISMATCH",
})


class DALContractViolation(Exception):
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
        layer: Optional[str] = None,
        validation: Optional[str] = None,
        n_violations: Optional[int] = None,
        error_code: Optional[str] = None,
    ) -> None:
        if layer is not None and layer not in _VALID_LAYERS:
            raise ValueError(
                f"Invalid layer {layer!r}. Must be one of: {sorted(_VALID_LAYERS)}"
            )
        if error_code is not None and error_code not in _VALID_CODES:
            raise ValueError(
                f"Invalid error_code {error_code!r}. Must be one of: {sorted(_VALID_CODES)}"
            )

        self.message = message
        self.layer = layer
        self.validation = validation
        self.n_violations = n_violations
        self.error_code = error_code

        super().__init__(self._format())

    def _format(self) -> str:
        parts = []
        if self.error_code is not None:
            parts.append(f"[{self.error_code}]")
        if self.layer is not None:
            parts.append(f"layer={self.layer}")
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
            f"layer={self.layer!r}, "
            f"validation={self.validation!r}, "
            f"n_violations={self.n_violations!r}, "
            f"error_code={self.error_code!r}"
            f")"
        )
