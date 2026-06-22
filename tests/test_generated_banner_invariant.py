"""ADR-010 §1.2 / Phase 2 — no GENERATED banner without a generator.

The invariant: a committed artifact may declare itself GENERATED only if a registered
generator reproduces it. This closes the signal_traceability.yaml class of defect —
a hand-maintained file wearing a "GENERATED" banner with no producer (a shadow
representation, ADR-010 ruling b) — permanently, by making it a test failure.

Two checks:
  1. Every artifact carrying a GENERATED banner is in GENERATORS (else: add a generator
     or drop the banner).
  2. Every registered generator reproduces its committed artifact (semantic equality).

The reverse is allowed: a registered generator whose committed file omits the banner is
fine here (the dedicated drift test still guards reproduction). This test guards the
banner→generator direction.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from model.governance.generate_evaluation_metadata import generate
from model.governance.generate_synth01_decisions import generate as generate_synth01

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent

# Source trees that hold committed artifacts (excludes tests/, docs/, archive/, .venv/).
_SCAN_DIRS = ("domain", "dal", "research", "model", "serve", "outputs")
_SCAN_SUFFIXES = (".yaml", ".yml", ".csv")

# Banner token, matched case-insensitively in the first few comment lines of a file.
_BANNER_TOKEN = "generated"
_BANNER_SCAN_LINES = 8


def _normalize_eval_metadata(data: dict[str, Any]) -> dict[str, Any]:
    """Drop free-text version_note; index findings by key so list order is irrelevant."""
    out = copy.deepcopy(data)
    out.pop("version_note", None)
    out["evaluation_findings"] = {e["key"]: e for e in out["evaluation_findings"]}
    return out


def _committed_eval_metadata() -> dict[str, Any]:
    with (REPO_ROOT / "model/governance/evaluation_metadata.yaml").open() as fh:
        return yaml.safe_load(fh)


def _check_eval_metadata() -> None:
    """Regenerate evaluation_metadata.yaml and assert it matches the committed copy."""
    assert _normalize_eval_metadata(generate()) == _normalize_eval_metadata(_committed_eval_metadata()), (
        "evaluation_metadata.yaml does not match its generator output — regenerate with "
        "`python -m model.governance.generate_evaluation_metadata`."
    )


def _normalize_synth01(data: dict[str, Any]) -> dict[str, Any]:
    """Index decisions by key so list order is irrelevant."""
    out = copy.deepcopy(data)
    out["decisions"] = {d["key"]: d for d in out["decisions"]}
    return out


def _check_synth01_decisions() -> None:
    """Regenerate synth01_decisions.yaml and assert it matches the committed copy."""
    with (REPO_ROOT / "model/assemble/synth01_decisions.yaml").open() as fh:
        committed = yaml.safe_load(fh)
    assert _normalize_synth01(generate_synth01()) == _normalize_synth01(committed), (
        "synth01_decisions.yaml does not match its generator output — regenerate with "
        "`python -m model.governance.generate_synth01_decisions`."
    )


# Registry: committed GENERATED artifact -> a check that proves its generator reproduces it.
# To add a new generated artifact: register its reproduction check here. To stop a file
# being treated as generated: remove its GENERATED banner.
GENERATORS: dict[str, Callable[[], None]] = {
    "model/governance/evaluation_metadata.yaml": _check_eval_metadata,
    "model/assemble/synth01_decisions.yaml": _check_synth01_decisions,
}


def _has_generated_banner(path: Path) -> bool:
    """True if any of the file's first comment lines declares it GENERATED."""
    try:
        with path.open(encoding="utf-8") as fh:
            for _, line in zip(range(_BANNER_SCAN_LINES), fh):
                stripped = line.strip()
                if not stripped.startswith("#"):
                    # First non-comment line ends the banner region.
                    break
                if _BANNER_TOKEN in stripped.lower():
                    return True
    except (OSError, UnicodeDecodeError):
        return False
    return False


def _discover_generated_artifacts() -> list[Path]:
    """All committed source artifacts carrying a GENERATED banner."""
    found: list[Path] = []
    for d in _SCAN_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() in _SCAN_SUFFIXES and _has_generated_banner(path):
                found.append(path)
    return found


def test_every_generated_banner_has_a_generator() -> None:
    """A file may claim GENERATED only if a generator is registered for it (ADR-010 §1.2)."""
    discovered = {p.relative_to(REPO_ROOT).as_posix() for p in _discover_generated_artifacts()}
    unregistered = sorted(discovered - GENERATORS.keys())
    assert not unregistered, (
        "These files carry a GENERATED banner but have no registered generator "
        f"(ADR-010 §1.2): {unregistered}. Either add a generator and register it in "
        "GENERATORS, or remove the GENERATED banner (a hand-maintained file is not generated)."
    )


@pytest.mark.parametrize("artifact", sorted(GENERATORS))
def test_registered_generator_reproduces_artifact(artifact: str) -> None:
    """Each registered generator reproduces its committed artifact."""
    GENERATORS[artifact]()
