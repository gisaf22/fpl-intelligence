"""Score provenance — traceability from intelligence module output to governance.

score_provenance() returns a complete audit trail for any player's score from
any intelligence module: which signals contributed, what weights they received,
which governance entry authorised those weights, what STATE values the player
had, and any caveats from signal_traceability.yaml at the player's position.

Does not modify any production code path — callable independently with a
features DataFrame as input.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from intelligence.weight_registry import get_module_weights, get_weight_metadata

_TRACEABILITY_PATH = Path("signals/characterisation/signal_traceability.yaml")

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


@functools.lru_cache(maxsize=1)
def _load_traceability() -> list[dict]:
    """Load and cache signal_traceability.yaml entries."""
    path = _TRACEABILITY_PATH
    if not path.exists():
        raise FileNotFoundError(f"Signal traceability not found at {path}. Run from the project root directory.")
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Signal traceability at {path} must be a YAML mapping, got {type(data).__name__}")
    entries: list[dict] = data.get("entries", [])
    return entries


def _get_caveats_for(signal: str, position: str) -> list[str]:
    """Return caveats from signal_traceability.yaml for a signal at a position."""
    entries = _load_traceability()
    caveats = []
    for entry in entries:
        if entry.get("signal") == signal and entry.get("position") == position:
            caveat = entry.get("caveat")
            if caveat and str(caveat).strip():
                caveats.append(str(caveat).strip())
    return caveats


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
          caveats       — list of caveats from signal_traceability.yaml at position,
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
            "registry_source": (f"signals/characterisation/weight_registry.yaml §modules.{module}.weights.{component}"),
            "signal_id": meta.get("signal_id"),
            "provenance": str(meta.get("note", "")).strip(),
            "caveats": caveats,
        }

    return {
        "player_id": int(player_id),
        "gw": int(gw),
        "module": module,
        "position": position,
        "registry_source": (f"signals/characterisation/weight_registry.yaml §modules.{module}"),
        "signals": signals_provenance,
    }
