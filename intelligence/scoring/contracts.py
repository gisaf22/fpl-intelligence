"""Data contracts for all scorer module boundaries.

These dataclasses are the only shapes that cross module boundaries.
Engine returns ScorerOutput. Renderer accepts ScorerOutput.
Runner wires them together and owns all I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScorerInput:
    """Parameters passed from the CLI into the runner."""

    gw: int
    db_path: Path
    output_dir: Path
    registry_path: Path


@dataclass(frozen=True)
class ConfirmedSignal:
    """A signal cleared for use in the composite score."""

    signal: str
    position: str
    rho_pooled: float
    direction: int  # +1 if higher raw value = better, -1 if lower = better
    promotion_class: str  # 'core_signal' or 'review_signal'


@dataclass(frozen=True)
class CaveatedSignal:
    """A signal excluded from the composite score, with the reason shown."""

    signal: str
    position: str
    reason: str  # human-readable exclusion reason
    promotion_class: str  # 'core_signal' or 'review_signal'


@dataclass(frozen=True)
class SignalManifest:
    """Single source of truth for which signals are used and why."""

    confirmed: list[ConfirmedSignal]
    caveated: list[CaveatedSignal]
    positions_covered: dict[str, list[str]]  # position → signal names (confirmed only)


@dataclass
class PlayerScore:
    """Scored output for one player in one gameweek."""

    player_id: int
    player_name: str
    position: str
    rank: int
    composite_score: float  # [0, 1] — multiply by 10 at render time
    signal_values: dict[str, float | None]  # raw value per confirmed signal
    signal_normalised: dict[str, float | None]  # [0,1] normalised per confirmed signal


@dataclass(frozen=True)
class ScorerOutput:
    """Complete scorer result for one gameweek, ready for the renderer."""

    gw: int
    scored_at: str  # ISO-8601 UTC timestamp
    players: list[PlayerScore]
    manifest: SignalManifest
    registry_path: str = ""  # path used; empty string if not provided
    registry_meta: dict[str, object] = field(default_factory=dict)  # build_metadata.json contents if available
