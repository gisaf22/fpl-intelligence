"""FeatureSpec + FeaturePool — features as declared data (spec §3).

A ``FeatureSpec`` describes *one* model input as data: what it is, where it comes from, the
grain it lives at, and — the parts that make it defensible rather than a comment — that it is
**lag-safe** (asserted + property-tested, never trusted) and whether it is **known-future**
(the upcoming fixture's venue is allowed; anything else must be strictly prior).

A ``FeaturePool`` is the *one candidate pool per model* (resolved decision #3). Two models draw
from it: the ``minimal`` subset — 2-3 mechanistic features that are both a fast smoke-test and the
comparison **bar** the shipped model must beat — and the full pool the *selected* model regularizes
over. The delta between them is what selection bought.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Grain = Literal["player_gw", "team_gw"]


@dataclass(frozen=True)
class FeatureSpec:
    """One declared, lag-safe model input.

    Attributes:
        name:         the materialized column name (e.g. ``"xgi_roll3"``). The window is baked into
                      the name only for the already-frozen mart columns; new features carry ``window``
                      as a *swept* parameter (selected in the inner temporal split, never on eval).
        source:       the raw quantity the feature derives from (provenance root).
        transform:    how ``source`` is reduced over history (``roll`` mean today; ``ewma``/``slope``/
                      ``std``/``median`` are the §3 expansion axes).
        window:       window length in appearances for windowed transforms; ``None`` for point features
                      (e.g. ``was_home``). Swept inside the inner temporal split, not guessed.
        grain:        the natural grain the feature is built at — drives the join/broadcast to the
                      model's grain (resolved decision #4).
        lag_safe:     asserted here, **property-tested** in :func:`model.features.build.assert_lag_safe`.
        known_future: True only for quantities known before kickoff (venue). Everything else must be
                      strictly prior; a True here is a claim the build step is allowed to trust.
        rationale:    why this feature should carry signal (the mechanism).
        prior:        provenance from discovery (a families finding), non-authoritative (spec §8).
    """

    name: str
    source: str
    grain: Grain
    transform: Literal["roll", "ewma", "slope", "std", "median", "identity"] = "roll"
    window: int | None = 3
    lag_safe: bool = True
    known_future: bool = False
    rationale: str = ""
    prior: str = ""


@dataclass(frozen=True)
class FeaturePool:
    """The single candidate pool for a model; the minimal + selected models both draw from it.

    ``minimal`` names the mechanistic subset (also the comparison bar). ``candidates`` is the full
    pool the selected model regularizes over. ``minimal`` must be a subset of the pool's names.
    """

    name: str
    candidates: tuple[FeatureSpec, ...]
    minimal: tuple[str, ...]

    def __post_init__(self) -> None:
        names = {f.name for f in self.candidates}
        if len(names) != len(self.candidates):
            raise ValueError(f"{self.name}: duplicate feature names in pool")
        missing = set(self.minimal) - names
        if missing:
            raise ValueError(f"{self.name}: minimal features not in candidate pool: {sorted(missing)}")

    def spec(self, name: str) -> FeatureSpec:
        """The FeatureSpec for ``name`` (KeyError if absent)."""
        for f in self.candidates:
            if f.name == name:
                return f
        raise KeyError(f"{self.name}: no feature {name!r} in pool")

    def minimal_specs(self) -> tuple[FeatureSpec, ...]:
        """The mechanistic subset — fast smoke-test *and* the bar the selected model must beat."""
        return tuple(self.spec(n) for n in self.minimal)

    @property
    def names(self) -> tuple[str, ...]:
        """All candidate column names, pool order."""
        return tuple(f.name for f in self.candidates)
