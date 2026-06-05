"""Canonical codec for the ADR-003 composite finding key.

Single source of truth for the ``signal@lens:target[#POSITION]`` grammar — its
construction, parsing, and lens-token normalisation. Pure string vocabulary (no
pandas, no governance), so it lives in ``domain`` and is importable by every
layer: the governance lookup parses keys with it, the synth composition study
builds keys with it.

  build_key("xgi_roll3", "FORM", "total_points")        -> "xgi_roll3@form:total_points"
  build_key("purchase_price", "MARKET", "total_points", "FWD")
                                          -> "purchase_price@market:total_points#FWD"
  parse_key("minutes_roll3@avail:played_next_gw#MID")
      -> FindingKey(signal="minutes_roll3", lens_token="avail",
                    target="played_next_gw", position="MID")

``target`` is assumed already-canonical (the token that appears in the key, e.g.
``total_points``); callers map any data-column alias to the token before building.
"""

from __future__ import annotations

from typing import NamedTuple

_MALFORMED = "Malformed composite key {key!r}. Expected 'signal@lens:target[#POSITION]' (ADR-003)."


class FindingKeyError(ValueError):
    """Raised when a composite finding key is malformed (ADR-003)."""


class FindingKey(NamedTuple):
    """Parsed ADR-003 finding key. ``position`` is None for a lens finding."""

    signal: str
    lens_token: str
    target: str
    position: str | None


def lens_token(lens: str) -> str:
    """Normalise a lens label to its key token (ADR-003): lowercase, '-' -> '_'."""
    return lens.lower().replace("-", "_")


def build_key(signal: str, lens: str, target: str, position: str | None = None) -> str:
    """Build a composite finding key. ``lens`` is normalised; ``target`` is taken as-is.

    With ``position`` the key is position-scoped (``…#POSITION``), as the synth
    composition study emits; without it, it is the parent lens-finding key.
    """
    key = f"{signal}@{lens_token(lens)}:{target}"
    return f"{key}#{position}" if position else key


def parse_key(key: str) -> FindingKey:
    """Parse a composite finding key into its parts.

    Raises FindingKeyError if the key is malformed. The lens token is returned
    verbatim (keys already carry the normalised token).
    """
    finding_part, had_hash, position = key.partition("#")
    try:
        signal, lens_target = finding_part.split("@", 1)
        token, target = lens_target.split(":", 1)
    except ValueError as exc:
        raise FindingKeyError(_MALFORMED.format(key=key)) from exc
    if not signal or not token or not target or (had_hash and not position):
        raise FindingKeyError(_MALFORMED.format(key=key))
    return FindingKey(signal=signal, lens_token=token, target=target, position=position or None)
