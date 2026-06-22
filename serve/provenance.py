"""Score provenance — traceability from serve module output to governance.

score_provenance() returns a complete audit trail for any player's score from
any intelligence module: which signals contributed, what weights they received,
which governance entry authorised those weights, what STATE values the player
had, and any caveats from the canonical decision-of-record at the player's position.

Caveats are read from evaluation_metadata.yaml via the domain governance read model
(ADR-010 ruling b), not from the retired signal_traceability.yaml — serve no longer
consumes governance state from that hand-maintained matrix (serve ↛ model is preserved:
the read model lives in the domain leaf).

Does not modify any production code path — callable independently with a
features DataFrame as input.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from domain.registry.governance_lookup import get_signal_governance
from domain.registry.governance_types import GovernanceMetadataError
from serve.weight_registry import get_module_weights, get_weight_metadata

# Map from module name → component → list of STATE columns that feed the component.
# Encodes the computational relationship between weight components and STATE values.
_MODULE_SIGNAL_MAP: dict[str, dict[str, list[str]]] = {
    "captain": {
        "form_score": ["xgi_roll5"],
        "involvement_score": ["xgi_roll3"],
        "fixture_score": ["fixture_context"],
        "minutes_score": ["minutes_roll3"],
    },
    "value": {
        "efficiency_score": ["xgi_roll5", "purchase_price"],
        "form_score": ["xgi_roll3"],
        "consistency_score": ["xgi_roll3", "xgi_roll5"],
    },
    "fixtures": {
        "team_attack_score": ["goals_scored"],
        "dgw_bonus_score": ["fixture_context"],
    },
    "transfers": {
        "recent_form_score": ["xgi_roll3"],
        "form_momentum_score": ["xgi_roll3", "xgi_roll5"],
        "fixture_score": ["fixture_context"],
        "involvement_score": ["xgi_roll3"],
        "minutes_stability_score": ["minutes_roll5"],
    },
}

_VALID_MODULES = frozenset(_MODULE_SIGNAL_MAP.keys())


def _get_caveats_for(signal: str, position: str) -> list[str]:
    """Return caveats for a signal at a position from the canonical decision-of-record.

    ADR-010 ruling (b): caveats are derived from evaluation_metadata.yaml (via the domain
    governance read model), not from the retired signal_traceability.yaml. A caveat is
    surfaced when the canonical verdict documents a limitation — downstream_status
    'caveated' or lifecycle_state excluded/not_applicable — using its behavioral_reason.
    Signals with no lens record (e.g. STATE-only columns like fixture_context) carry none.
    """
    try:
        gov = get_signal_governance(signal, position)
    except GovernanceMetadataError:
        return []
    if gov.downstream_status == "caveated" or gov.lifecycle_state in {"excluded", "not_applicable"}:
        reason = (gov.behavioral_reason or "").strip()
        if reason:
            return [reason]
    return []


def score_provenance(
    features: pd.DataFrame,
    player_id: int,
    gw: int,
    module: str,
) -> dict[str, Any]:
    """Return complete governance provenance for a player's score from a module.

    Parameters
    ----------
    features:
        Full DAL state output at (player_id, gw) grain — the same DataFrame
        passed to intelligence module functions.
    player_id:
        Player to look up.
    gw:
        Gameweek to look up.
    module:
        Intelligence module name: 'captain', 'value', 'fixtures', or 'transfers'.

    Returns
    -------
    dict with keys:
    - player_id, gw, module, position
    - registry_source: path to weight_registry.yaml section
    - signals: dict of component → {
          weight        — float weight from registry,
          signals       — list of STATE column(s) feeding this component,
          state_values  — dict of STATE column → value from features,
          registry_source — exact registry path for this weight,
          signal_id     — evaluation study signal ID (or null),
          provenance    — registry note text,
          caveats       — list of caveats from the canonical decision-of-record at position,
      }

    Raises
    ------
    ValueError if module is not registered, or player/gw not found in features.
    """
    if module not in _VALID_MODULES:
        raise ValueError(f"Module {module!r} not in provenance map. Valid modules: {sorted(_VALID_MODULES)}")

    mask = (features["player_id"] == player_id) & (features["gw"] == gw)
    player_row = features[mask]
    if player_row.empty:
        raise ValueError(f"score_provenance: no data for player_id={player_id}, gw={gw}.")

    row = player_row.iloc[0]
    position = str(row.get("position_label", "UNKNOWN"))
    weights = get_module_weights(module)
    signal_map = _MODULE_SIGNAL_MAP[module]

    signals_provenance: dict[str, Any] = {}
    for component, weight_value in weights.items():
        state_cols = signal_map.get(component, [])
        state_values = {col: (row[col] if col in row.index else None) for col in state_cols}

        try:
            meta = get_weight_metadata(module, component)
        except Exception:
            meta = {}

        caveats: list[str] = []
        for col in state_cols:
            caveats.extend(_get_caveats_for(col, position))

        signals_provenance[component] = {
            "weight": weight_value,
            "signals": state_cols,
            "state_values": state_values,
            "registry_source": (f"serve/weight_registry.yaml §modules.{module}.weights.{component}"),
            "signal_id": meta.get("signal_id"),
            "provenance": str(meta.get("note", "")).strip(),
            "caveats": caveats,
        }

    return {
        "player_id": int(player_id),
        "gw": int(gw),
        "module": module,
        "position": position,
        "registry_source": (f"serve/weight_registry.yaml §modules.{module}"),
        "signals": signals_provenance,
    }
