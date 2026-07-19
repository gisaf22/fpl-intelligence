"""Frozen-vector assertions for the term goldens (spec §10.5).

When the god-files were deleted, each term's "reproduce the god-file to the bit" golden was migrated onto
a checked-in regression record captured while the god-file reference was still live and green. A record is
deliberately compact but drift-sensitive: the count of scored rows, the 6dp sum of predictions (any change
to the fit moves it), and a few 4dp spot values. Gate tables freeze their per-position key numbers the
same way. This is not a test module (no ``test_`` prefix) — it is the shared assertion helper.
"""

from __future__ import annotations

import numpy as np


def assert_frozen(got: np.ndarray, n_scored: int, sum6: float,
                  spot_idx: list[int], spot_vals: list[float]) -> None:
    """Assert a walk-forward prediction vector against its frozen regression record."""
    nn = ~np.isnan(got)
    assert int(nn.sum()) == n_scored, f"n_scored {int(nn.sum())} != {n_scored}"
    assert round(float(np.nansum(got)), 6) == sum6, f"sum6 {round(float(np.nansum(got)), 6)} != {sum6}"
    for i, v in zip(spot_idx, spot_vals):
        assert round(float(got[i]), 4) == v, f"idx {i}: {got[i]!r} != {v}"
