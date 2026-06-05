"""Normalized scoring verdict — one shape per (signal, position).

The consume-side read model (ADR-009 §4) that merges the foundation registry row
(promotion_class, layer_role, rho, downstream_status) with the lens/derived
governance verdict (resolve_governance) into a single object. The scorer reads this
instead of scattering raw registry-column reads alongside a separate governance lookup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.registry.governance_lookup import resolve_governance


@dataclass(frozen=True)
class SignalVerdict:
    """One normalized governance verdict for a (signal, position) scoring candidate."""

    signal: str
    position: str
    promotion_class: str | None  # foundation promotion class; None for blocked rows
    layer_role: str
    interpretation_caveat: str
    rho_pooled: float | None
    lifecycle_state: str  # from lens record, else foundation-derived (ADR-009 §1)
    leakage_risk: str
    downstream_status: str
    source_key: str  # governance source key for provenance in exclusion reasons


def _opt_float(value: Any) -> float | None:
    if value is None or value != value:  # None or NaN
        return None
    return float(value)


def _opt_str(value: Any) -> str | None:
    if value is None or value != value:  # None or NaN
        return None
    return str(value)


def resolve_verdict(row: dict[str, Any]) -> SignalVerdict:
    """Build the normalized verdict for one registry row (ADR-009 §4)."""
    signal = str(row["signal"])
    position = str(row["position"])
    downstream = str(row.get("downstream_status") or "eligible")
    gov = resolve_governance(signal, position, downstream)
    return SignalVerdict(
        signal=signal,
        position=position,
        promotion_class=_opt_str(row.get("promotion_class")),
        layer_role=str(row.get("layer_role") or ""),
        interpretation_caveat=str(row.get("interpretation_caveat") or ""),
        rho_pooled=_opt_float(row.get("rho_pooled")),
        lifecycle_state=gov.lifecycle_state,
        leakage_risk=gov.leakage_risk,
        downstream_status=gov.downstream_status,
        source_key=gov.key,
    )
