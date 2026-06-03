"""Weight registry loader for operational intelligence modules.

Loads module composition weights from signals/governance/weight_registry.yaml.
Raises on any missing module or weight entry — no silent defaults or fallbacks.
"""

from __future__ import annotations

import functools
from pathlib import Path

import yaml

_WEIGHT_REGISTRY_PATH = Path("signals/governance/weight_registry.yaml")


class WeightRegistryError(KeyError):
    """Raised when a module or weight entry is missing from the weight registry."""


@functools.lru_cache(maxsize=1)
def _load_raw() -> dict:
    """Load and cache the raw weight_registry.yaml."""
    path = _WEIGHT_REGISTRY_PATH
    if not path.exists():
        raise FileNotFoundError(f"Weight registry not found at {path}. Run from the project root directory.")
    with path.open() as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Weight registry at {path} must be a YAML mapping, got {type(data).__name__}")
    return data


def get_module_weights(module: str) -> dict[str, float]:
    """Return the weight dict for a module from the governance registry.

    Parameters
    ----------
    module:
        Module name — one of 'captain', 'value', 'fixtures', 'transfers'.

    Returns
    -------
    dict mapping component_name → float weight value.

    Raises
    ------
    WeightRegistryError if the module or any weight entry is absent.
    FileNotFoundError if weight_registry.yaml cannot be found.
    """
    data = _load_raw()
    modules = data.get("modules", {})
    if module not in modules:
        raise WeightRegistryError(
            f"Module {module!r} not found in weight registry "
            f"({_WEIGHT_REGISTRY_PATH}). Add an entry to register this module's weights. "
            "Every weight must have a governance source — no hardcoded dicts allowed."
        )
    module_data = modules[module]
    weights_data = module_data.get("weights")
    if not weights_data:
        raise WeightRegistryError(f"No weights defined for module {module!r} in registry ({_WEIGHT_REGISTRY_PATH}).")
    result: dict[str, float] = {}
    for key, entry in weights_data.items():
        if "value" not in entry:
            raise WeightRegistryError(
                f"Weight {key!r} in module {module!r} has no 'value' field in {_WEIGHT_REGISTRY_PATH}."
            )
        result[key] = float(entry["value"])
    return result


def get_weight_metadata(module: str, weight_key: str) -> dict:
    """Return full metadata for a specific weight component.

    Includes signal, signal_id, note, and provenance fields.

    Raises WeightRegistryError if module or weight_key not found.
    """
    data = _load_raw()
    modules = data.get("modules", {})
    if module not in modules:
        raise WeightRegistryError(f"Module {module!r} not in weight registry.")
    weights_data = modules[module].get("weights", {})
    if weight_key not in weights_data:
        raise WeightRegistryError(f"Weight {weight_key!r} not found for module {module!r} in weight registry.")
    return dict(weights_data[weight_key])


def get_module_metadata(module: str) -> dict:
    """Return top-level metadata for a module (provenance, note, etc.)."""
    data = _load_raw()
    modules = data.get("modules", {})
    if module not in modules:
        raise WeightRegistryError(f"Module {module!r} not in weight registry.")
    meta = dict(modules[module])
    meta.pop("weights", None)
    return meta
