"""Runtime lifecycle enforcement for signal registries.

Operational intelligence consumers (scorer, report runner) must not load
registries from exploratory research output directories. Research consumers
(EDA notebooks, registry builder) carry no such restriction.

Usage:
    from domain.registry.lifecycle import assert_operational_safe
    assert_operational_safe(registry_path)   # raises LifecycleViolationError if exploratory
"""

from __future__ import annotations

from pathlib import Path

# All path prefixes that contain exploratory-state research outputs.
# Registries under these paths are not eligible for operational consumption.
_EXPLORATORY_PREFIXES: tuple[Path, ...] = (Path("research/findings"),)


class LifecycleViolationError(ValueError):
    """Raised when an operational consumer attempts to load an exploratory registry,
    or when a signal with lifecycle_state=excluded or downstream_status=blocked
    is loaded by a scoring consumer.

    Exploratory registries live under research/findings/ and represent unvalidated
    research outputs. Operational consumers (scorer, report runner) must consume
    only registries that have been promoted through the research lifecycle and
    written to outputs/registry/.
    """


class LeakageViolationError(ValueError):
    """Raised when a signal with leakage_risk=direct is loaded by an operational consumer.

    Direct leakage means the signal is a computational component of the scoring
    target (e.g. bonus, bps). Loading such a signal in a scoring context would
    contaminate the output with target information.
    """


def is_exploratory_path(path: str | Path) -> bool:
    """Return True if path is under a known exploratory-output directory."""
    parts = Path(path).parts
    return any(parts[: len(p.parts)] == p.parts for p in _EXPLORATORY_PREFIXES)


def assert_operational_safe(path: str | Path) -> None:
    """Raise LifecycleViolationError if path is an exploratory registry artifact.

    Call this before loading a registry in any operational consumer. Research
    consumers (EDA notebooks, registry builder) should not call this gate.
    """
    if is_exploratory_path(path):
        raise LifecycleViolationError(
            f"Operational consumer cannot load exploratory registry at {str(path)!r}. "
            "Registries under research/findings/ are exploratory-state artifacts and have not "
            "passed lifecycle promotion. Use a registry from outputs/registry/ built via "
            "the registry builder after signals are promoted through the research lifecycle. "
            "See docs/registry-governance.md for the promotion process."
        )
