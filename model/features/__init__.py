"""Feature engineering for the term models — declared, lag-safe columns from specs.

Features are **data, not code** (spec §3): each is a :class:`~model.features.spec.FeatureSpec`
declaring its grain, lag-safety, provenance and swept window, and :mod:`model.features.build`
turns a spec into a lag-safe column with a leakage property assertion. One candidate pool per
model; the *minimal* and *selected* models both draw from that pool.
"""

from __future__ import annotations

from model.features.build import add_lagged_rolls, assert_lag_safe, broadcast, materialize
from model.features.spec import FeaturePool, FeatureSpec

__all__ = ["FeaturePool", "FeatureSpec", "add_lagged_rolls", "assert_lag_safe", "broadcast", "materialize"]
