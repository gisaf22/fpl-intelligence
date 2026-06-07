"""Canonical codec for the ADR-003 composite finding key.

Single source of truth for the ``signal@lens:target[#POSITION]`` grammar — its
construction and parsing. Pure string vocabulary (no pandas, no governance), so it
lives in ``domain`` and is importable by every layer: the governance lookup parses
keys with it, the synth composition study builds keys with it.

  build_key("xgi_roll3", "form", "total_points")        -> "xgi_roll3@form:total_points"
  build_key("purchase_price", "market", "total_points", "FWD")
                                          -> "purchase_price@market:total_points#FWD"
  parse_key("minutes_roll3@avail:played_next_gw#MID")
      -> FindingKey(signal="minutes_roll3", lens="avail",
                    target="played_next_gw", position="MID")

The lens is the canonical lowercase token itself (``form``/``avail``/``market``/
``fixture_gw``) — there is no uppercase display label and no normalisation step
(ADR-003 amendment, ADR-010 follow-up). ``build_key`` validates the lens is canonical
rather than silently transforming it. ``target`` is assumed already-canonical (the
token that appears in the key, e.g. ``total_points``); callers map any data-column
alias to the token before building.
"""

from __future__ import annotations

import re
from typing import NamedTuple

_MALFORMED = "Malformed composite key {key!r}. Expected 'signal@lens:target[#POSITION]' (ADR-003)."
_CANONICAL_LENS = re.compile(r"^[a-z0-9_]+$")


class FindingKeyError(ValueError):
    """Raised when a composite finding key is malformed (ADR-003)."""


class FindingKey(NamedTuple):
    """Parsed ADR-003 finding key. ``position`` is None for a lens finding."""

    signal: str
    lens: str
    target: str
    position: str | None


def _require_canonical_lens(lens: str) -> str:
    """Return the lens if it is already canonical, else raise (no silent normalisation)."""
    if not _CANONICAL_LENS.match(lens):
        raise FindingKeyError(
            f"Non-canonical lens {lens!r}: lens must be a lowercase token [a-z0-9_] "
            "(e.g. 'form', 'avail', 'fixture_gw') — there is no uppercase label (ADR-003 amendment)."
        )
    return lens


def build_key(signal: str, lens: str, target: str, position: str | None = None) -> str:
    """Build a composite finding key. ``lens`` must be the canonical lowercase token.

    With ``position`` the key is position-scoped (``…#POSITION``), as the synth
    composition study emits; without it, it is the parent lens-finding key.
    """
    key = f"{signal}@{_require_canonical_lens(lens)}:{target}"
    return f"{key}#{position}" if position else key


def parse_key(key: str) -> FindingKey:
    """Parse a composite finding key into its parts.

    Raises FindingKeyError if the key is malformed. The lens is returned verbatim
    (keys carry the canonical token).
    """
    finding_part, had_hash, position = key.partition("#")
    try:
        signal, lens_target = finding_part.split("@", 1)
        lens, target = lens_target.split(":", 1)
    except ValueError as exc:
        raise FindingKeyError(_MALFORMED.format(key=key)) from exc
    if not signal or not lens or not target or (had_hash and not position):
        raise FindingKeyError(_MALFORMED.format(key=key))
    return FindingKey(signal=signal, lens=lens, target=target, position=position or None)
