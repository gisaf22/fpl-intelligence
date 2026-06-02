"""Mart layer schema contract — the prescriptive Pandera schema for the analytical mart.

Why this exists
---------------
The analytical mart is the *serving boundary*: every downstream consumer (intelligence,
transfers, studies, registry, notebooks) reads it. Yet the strongest upstream contract
(feat ``FEAT_SCHEMA``) sits one layer earlier, and the pipeline's ``mart_schema`` fingerprint
is *descriptive* — it records whatever was built — rather than *prescriptive*. That leaves a
gap: a refactor that drops a column, flips a dtype, or silently NaNs a derived column passes
build + ``load()`` and only surfaces as a downstream crash or wrong numbers.

This schema closes the gap by making the boundary fail-closed: ``build_prepared_dataset``
refuses to ship a mart that violates it (raising ``DALContractViolation``, which the pipeline
mart layer turns into a deleted parquet + hard stop).

Scope (enforcement, not bureaucracy)
------------------------------------
- **Governed signals** are derived from ``FEATURE_REGISTRY`` (single source of truth): we
  assert each still reaches the boundary with its declared nullability and allowed values.
  Dtype/value enforcement for signals stays in feat's ``FEAT_SCHEMA`` — no duplication.
- **Non-signal columns consumers depend on** (identity, grain, market price, key measures,
  structural flags) are hand-declared. ``strict=False`` so incidental pass-through columns are
  allowed without enumerating every one.
- **Grain uniqueness** ``(player_id, gw)`` is enforced via ``dal.validation.grain``.
"""

from __future__ import annotations

import pandera.pandas as pa
from pandera.errors import SchemaError, SchemaErrors

from dal.exceptions import DALContractViolation, ErrorCode
from dal.feat.feat_schema import FEATURE_REGISTRY
from dal.validation.grain import validate_grain_uniqueness

POSITIONS = ["GK", "DEF", "MID", "FWD"]


def _signal_columns() -> dict[str, pa.Column]:
    """Derive signal-column checks from FEATURE_REGISTRY (presence + nullability + values).

    We deliberately do NOT pin signal dtypes here — that lives in feat ``FEAT_SCHEMA``. At the
    serving boundary we guarantee each governed signal is still present, with its declared
    nullability and (for categoricals) its allowed values.
    """
    cols: dict[str, pa.Column] = {}
    for name, rec in FEATURE_REGISTRY.items():
        nullable = True if rec.null_if_no_obs is None else rec.null_if_no_obs
        checks = pa.Check.isin(rec.values) if rec.values else None
        cols[name] = pa.Column(nullable=nullable, checks=checks, required=True)
    return cols


# Hand-declared non-signal surface. dtypes match the in-memory mart (validation runs at build
# time, pre-parquet): numpy int64/float64 for dense columns, pandas nullable Int64/boolean for
# columns that are NULL on BGW rows. String columns omit dtype on purpose — the pandas string
# representation (object/string/str) is unstable across versions, and the high-value guarantee
# there is non-nullability + allowed values, not the storage dtype.
_NON_SIGNAL_COLUMNS: dict[str, pa.Column] = {
    # identity / grain
    "player_id":      pa.Column(int, nullable=False),
    "gw":             pa.Column(int, nullable=False),
    # `position` is mart-derived (mapped from position_code) — guard against silent NaN
    "position":       pa.Column(nullable=False, checks=pa.Check.isin(POSITIONS)),
    "position_code":  pa.Column(int, nullable=False, checks=pa.Check.isin([1, 2, 3, 4])),
    "team_id":        pa.Column(int, nullable=False),
    "player_name":    pa.Column(nullable=False),
    # market price (per-GW; consumer-critical — efficiency = xgi / purchase_price)
    "purchase_price": pa.Column(float, nullable=False, checks=pa.Check.ge(0)),
    # key performance measures (NULL on BGW rows by design)
    "minutes":        pa.Column("Int64", nullable=True, checks=pa.Check.ge(0)),
    "total_points":   pa.Column("Int64", nullable=True),
    # structural flags
    "is_bgw":         pa.Column("boolean", nullable=False),
    "is_dgw":         pa.Column("boolean", nullable=False),
}

MART_SCHEMA = pa.DataFrameSchema(
    columns={**_NON_SIGNAL_COLUMNS, **_signal_columns()},
    strict=False,   # allow incidental pass-through columns
    coerce=False,   # detect dtype drift rather than silently fixing it
)


def _classify(failure_cases) -> ErrorCode | None:
    """Best-effort map a Pandera failure report to a DAL ErrorCode (None if ambiguous)."""
    cols = getattr(failure_cases, "columns", [])
    if failure_cases is None or "check" not in list(cols):
        return None
    checks = failure_cases["check"].astype(str).str.lower()
    if checks.str.contains("column_in_dataframe").any():
        return ErrorCode.MISSING_COLUMNS
    if checks.str.contains("dtype").any():
        return ErrorCode.DTYPE_MISMATCH
    if checks.str.contains("nullable").any():
        return ErrorCode.NULL_VIOLATION
    return None


def validate_mart(df) -> None:
    """Fail-closed validation of the analytical mart at the serving boundary.

    Runs grain uniqueness ``(player_id, gw)`` then the prescriptive Pandera schema. Any
    violation raises ``DALContractViolation`` so the pipeline mart layer deletes the stale
    parquet and stops — the malformed mart never reaches a consumer.
    """
    validate_grain_uniqueness(df, "analytical_mart")
    try:
        MART_SCHEMA.validate(df, lazy=True)
    except (SchemaError, SchemaErrors) as exc:
        failure_cases = getattr(exc, "failure_cases", None)
        n = len(failure_cases) if failure_cases is not None else None
        raise DALContractViolation(
            message=f"analytical mart schema violation:\n{exc}",
            validation="validate_mart",
            n_violations=n,
            error_code=_classify(failure_cases),
        ) from exc
