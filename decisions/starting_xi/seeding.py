"""Per-gameweek seed derivation (§2.9), shared by the squad sampler and the random rule.

Its own module because the two callers sit on opposite sides of the slice's tier contract
(`.importlinter`): `sampler.py` is Tier A and `rankers.py` is Tier B, and neither may import the
other. Import closure: `numpy` only.
"""

from __future__ import annotations

import numpy as np


def week_seed(seed: int, gw: int) -> int:
    """Derive gameweek *gw*'s seed from the master seed.

    A pure function of the master seed and the gameweek, and of nothing else — not of how many
    gameweeks are being built, nor of the order they are built in, nor of how many draws an
    earlier week consumed. That is what gives §2.8 its second determinism property: building a
    subset of the gameweeks reproduces those gameweeks' squads exactly.

    A single sequential stream consumed across the weeks would have neither property, because
    rejection consumes a data-dependent number of draws, so any change at an early week would
    shift every later one (§2.8).
    """
    state = int(np.random.SeedSequence([seed, gw]).generate_state(1, dtype=np.uint64)[0])
    # Dropped to 63 bits so the derived seed is a plain signed integer in the run record rather
    # than an object column. Collision across a season's gameweeks is ~1e-16.
    return state >> 1
